"""The big bang: deterministic universe generation from (seed, config) (DESIGN §5).

Pipeline (Phase-1 subset): carve the Core, cluster the rest, bridge the groups
(a bidirectional spanning tree guarantees reachability, then extra/one-way
bridges add texture), a light ring-motif pass, distance bands, populate, and
validate — regenerating with a perturbed sub-seed on failure.

Two RNGs, deliberately separate: a *build* RNG `Random((seed, attempt))` drives
generation (so retries are deterministic), while the runtime `UniverseState.rng`
is `Random(seed)` and is left untouched here — gameplay randomness advances only
through the command log, keeping `(seed, command log)` replay exact (§3).
"""

from __future__ import annotations

import math
import random
from collections import deque

from edge.bigbang import populate as _populate
from edge.bigbang import validate as _validate
from edge.bigbang.aliens import HomeClusterError, populate_species
from edge.bigbang.discoveries import salt_discoveries, salt_raid_caches
from edge.bigbang.embedding import compute_embedding
from edge.bigbang.naming import NameGenerator
from edge.bigbang.numbering import assign_spatial_ids
from edge.bigbang.topology import (
    OutEdges,
    add_bidirectional,
    add_directed,
    add_ring_motifs,
    bfs_distances,
    carve_core,
    compute_bands,
)
from edge.core.config import BigBangConfig, GameConfig
from edge.core.enums import PortClass
from edge.core.models import Game, Region, Sector, UniverseState
from edge.dialogue.intel import build_species_knowledge

_Coord = tuple[int, int]  # a grid cell (row, col), used only by the mesh topology

_last_mesh_coords: dict[int, _Coord] = {}
_last_mesh_grid_size: tuple[int, int] = (0, 0)

_MAX_ATTEMPTS = 16


class BigBangError(Exception):
    """Generation failed validation after the bounded retries."""


def _cluster_groups(sectors: list[int], cfg: BigBangConfig, rng: random.Random) -> list[list[int]]:
    """Partition `sectors` into contiguous groups of size [cluster_min, cluster_max]."""
    groups: list[list[int]] = []
    i = 0
    n = len(sectors)
    while i < n:
        size = rng.randint(cfg.cluster_min, cfg.cluster_max)
        group = sectors[i : i + size]
        # Fold a too-small trailing remainder into the previous group.
        if len(group) < cfg.cluster_min and groups:
            groups[-1].extend(group)
        else:
            groups.append(group)
        i += size
    return groups


def _connect_group_standard(out: OutEdges, group: list[int], cfg: BigBangConfig, rng: random.Random) -> None:
    """Wire one group: a random spanning tree, then edges toward avg degree ~2.5.

    The intra-cluster connector shared by the `trunk` and `expansive` modes
    (`planar` and `mesh` have their own — see `_connect_group_planar` and the
    grid pass in `_build_mesh_graph`)."""
    cap = cfg.max_warps_per_sector
    if len(group) < 2:
        return
    order = group[:]
    rng.shuffle(order)
    for idx in range(1, len(order)):
        add_bidirectional(out, order[idx], rng.choice(order[:idx]), cap)
    target_edges = int(cfg.intra_group_degree * len(group) / 2)
    current = sum(len(out[s] & set(group)) for s in group) // 2
    attempts = 0
    while current < target_edges and attempts < target_edges * 4:
        a, b = rng.sample(group, 2)
        if add_bidirectional(out, a, b, cap):
            current += 1
        attempts += 1


def _connect_group_planar(out: OutEdges, group: list[int], cfg: BigBangConfig, rng: random.Random) -> None:
    """Wire one group internally as a planar outer-planar graph with zero crossings."""
    cap = cfg.max_warps_per_sector
    k = len(group)
    if k < 2:
        return
    if k == 2:
        add_bidirectional(out, group[0], group[1], cap)
        return

    # 1. Connect the outer cycle (always planar)
    order = group[:]
    rng.shuffle(order)
    for idx in range(k):
        add_bidirectional(out, order[idx], order[(idx + 1) % k], cap)

    # 2. Add non-crossing internal chords to satisfy the target intra-group degree
    target_edges = int(cfg.intra_group_degree * k / 2)
    current = k
    attempts = 0
    chords: list[tuple[int, int]] = []  # indices into order, u < v

    def crosses(u: int, v: int) -> bool:
        for x, y in chords:
            if u < x < v < y or x < u < y < v:
                return True
        return False

    while current < target_edges and attempts < target_edges * 8:
        attempts += 1
        u, v = sorted(rng.sample(range(k), 2))
        if v == u + 1 or (u == 0 and v == k - 1):
            continue
        if not crosses(u, v):
            if add_bidirectional(out, order[u], order[v], cap):
                chords.append((u, v))
                current += 1


def _bridge_groups_planar(out: OutEdges, groups: list[list[int]], cfg: BigBangConfig, rng: random.Random) -> None:
    """`planar` bridging: connects clusters using a planar spiderweb meta-graph.
    
    1. Stratify the clusters into concentric rings (Ring 0 is the Core).
    2. Assign each cluster in a ring a nominal angle around the Core.
    3. Connect adjacent clusters within the same ring to form cycle ring roads.
    4. Connect each cluster in Ring R to its nearest angular neighbor in Ring R-1.
    5. Link the clusters by finding sectors with the lowest internal degree.
    """
    cap = cfg.max_warps_per_sector
    if len(groups) < 2:
        return

    def _find_portal(g_idx: int) -> int | None:
        group = groups[g_idx]
        group_set = set(group)
        degrees = {s: len(out[s] & group_set) for s in group}
        sorted_secs = sorted(group, key=lambda s: (degrees[s], len(out[s]), s))
        for s in sorted_secs:
            if len(out[s]) < cap:
                return s
        return None

    def _link_clusters(g1_idx: int, g2_idx: int) -> bool:
        if g1_idx == g2_idx:
            return False
        a = _find_portal(g1_idx)
        b = _find_portal(g2_idx)
        if a is not None and b is not None:
            return add_bidirectional(out, a, b, cap)
        return False

    outer_indices = list(range(1, len(groups)))
    rng.shuffle(outer_indices)
    
    ring_width = max(3, math.isqrt(len(outer_indices)))
    rings: list[list[int]] = [[0]]
    for start in range(0, len(outer_indices), ring_width):
        rings.append(outer_indices[start : start + ring_width])

    angles: dict[int, float] = {0: 0.0}
    for ring in rings:
        k = len(ring)
        if ring == rings[0]:
            continue
        for idx, g_idx in enumerate(ring):
            angles[g_idx] = (idx / k) * 2 * math.pi

    # 1. Wire ring roads/cycles within each concentric ring
    for ring in rings:
        k = len(ring)
        if k >= 2:
            for idx in range(k):
                _link_clusters(ring[idx], ring[(idx + 1) % k])

    # 2. Radial spokes: Connect Ring R clusters to closest Ring R-1 cluster by angle
    for r in range(1, len(rings)):
        inner, outer = rings[r - 1], rings[r]
        for g_outer in outer:
            theta_outer = angles[g_outer]
            best_inner = inner[0]
            best_diff = 2 * math.pi
            for g_inner in inner:
                diff = abs(theta_outer - angles[g_inner])
                diff = min(diff, 2 * math.pi - diff)
                if diff < best_diff:
                    best_diff = diff
                    best_inner = g_inner
            _link_clusters(g_outer, best_inner)


def _bridge_groups_trunk(out: OutEdges, groups: list[list[int]], cfg: BigBangConfig, rng: random.Random) -> None:
    """`trunk` bridging (§5 step 2): a bidirectional spanning tree, then extra
    (maybe one-way) bridges. A group spanning tree rooted at the Core funnels
    outer-band traffic through the few tree bridges — the trunk-and-branches
    universe of chokepoints (the original, byte-identical algorithm)."""
    cap = cfg.max_warps_per_sector
    topo = cfg.active_topology()  # trunk block: its bridges_min/bridges_max range

    def _bridge(g1: list[int], g2: list[int], one_way: bool) -> None:
        for _ in range(6):  # a few member-pair tries in case of cap saturation
            a, b = rng.choice(g1), rng.choice(g2)
            ok = add_directed(out, a, b, cap) if one_way else add_bidirectional(out, a, b, cap)
            if ok:
                return

    # Spanning tree: each group links to a random earlier one (two-way) -> all
    # groups (incl. the core at index 0) mutually reachable.
    for i in range(1, len(groups)):
        _bridge(groups[i], groups[rng.randrange(i)], one_way=False)
    # Extra bridges per group for texture; some directional.
    for i, group in enumerate(groups):
        extra = rng.randint(topo.bridges_min, topo.bridges_max) - 1
        for _ in range(max(0, extra)):
            j = rng.randrange(len(groups))
            if j != i:
                _bridge(group, groups[j], one_way=rng.random() < cfg.one_way_chance)


def _bridge_groups_expansive(out: OutEdges, groups: list[list[int]], cfg: BigBangConfig, rng: random.Random) -> None:
    """`expansive` bridging (§5 step 2): a band-lattice web with no chokepoints.

    Stratify the groups into concentric rings (the Core is ring 0), then build:
      * a **ring road** — each ring's groups wired into a cycle, so a band can be
        circled without diving back toward the Core (lateral 2-edge-connectivity);
      * **≥2 radial spokes** between each consecutive ring pair, on distinct outer
        groups, so the rings are radially 2-edge-connected too.
    Cycles-plus-two-spokes make the whole graph **bridgeless**: no single
    inter-region warp is a cut edge, so every group keeps two edge-disjoint paths
    to the Core. Spoke demand is only ~2 per ring boundary (not per group), so the
    10-sector Core is never swamped — the failure mode of a per-group inward rule.
    Ring membership is seeded (a shuffle) so the shape varies per seed.
    """
    cap = cfg.max_warps_per_sector
    if len(groups) < 2:
        return

    def _link(gi: int, gj: int, one_way: bool = False) -> bool:
        # Bridge two groups, preferring member sectors with the most spare degree
        # (a shuffle gives seeded variety among equally-spare endpoints; the stable
        # sort preserves it) so no single sector saturates.
        if gi == gj:
            return False
        a_opts = sorted(groups[gi], key=lambda s: len(out[s]))
        b_opts = sorted(groups[gj], key=lambda s: len(out[s]))
        for a in a_opts:
            for b in b_opts:
                ok = add_directed(out, a, b, cap) if one_way else add_bidirectional(out, a, b, cap)
                if ok:
                    return True
        return False

    non_core = list(range(1, len(groups)))
    rng.shuffle(non_core)
    ring_width = max(2, math.isqrt(len(non_core)))
    rings: list[list[int]] = [[0]]  # ring 0 is the Core group
    for start in range(0, len(non_core), ring_width):
        rings.append(non_core[start : start + ring_width])

    # Ring roads: wire each ring's groups into a cycle (a 2-group ring is a single
    # link — its redundancy comes from the spokes below).
    for ring in rings:
        k = len(ring)
        if k >= 2:
            for idx in range(k):
                _link(ring[idx], ring[(idx + 1) % k])

    # Radial spokes: ≥2 bridges between each consecutive ring pair, spread across
    # distinct outer groups so no single group becomes a radial cut vertex.
    for r in range(1, len(rings)):
        inner, outer = rings[r - 1], rings[r]
        outer_order = outer[:]
        rng.shuffle(outer_order)
        made = attempts = 0
        while made < 2 and attempts < 16:
            gi = outer_order[made % len(outer_order)]
            if _link(gi, rng.choice(inner)):
                made += 1
            attempts += 1

    # Extra chords/one-ways: a little richer routing within the larger rings.
    for ring in rings:
        if len(ring) >= 3:
            for _ in range(rng.randint(0, 2)):
                gi, gj = rng.sample(ring, 2)
                _link(gi, gj, one_way=rng.random() < cfg.one_way_chance)


# --- mesh topology (§5): a regular 2D grid partitioned into contiguous clusters ---
#
# Unlike trunk/expansive/planar (which cluster a 1-D range of sector ids and bridge the
# groups abstractly), mesh lays every sector on a 2D grid and only ever wires spatially
# adjacent cells. The pipeline mirrors the others — partition, connect within, bridge
# between — but every step is constrained to grid edges, so the helpers are mesh-specific.
#
# Determinism note: the RNG call order across these helpers is load-bearing for
# golden-master replays. `_bfs_grow`'s neighbour order, and each `rng.*` call below, must
# stay in this exact sequence when editing.

_MESH_NEIGHBOR_OFFSETS: tuple[_Coord, ...] = ((-1, 0), (1, 0), (-1, -1), (-1, 1), (1, -1), (1, 1))


def _grid_neighbors(coord: _Coord, coords_set: set[_Coord]) -> list[_Coord]:
    """The in-bounds grid cells adjacent to `coord` (the two vertical cells plus the two
    diagonals on each of the rows above and below), in a fixed order. That order seeds the
    BFS growth below, so it must stay stable for reproducible generation."""
    r, c = coord
    return [(r + dr, c + dc) for dr, dc in _MESH_NEIGHBOR_OFFSETS if (r + dr, c + dc) in coords_set]


def _mesh_grid_geometry(n: int) -> tuple[int, int, list[_Coord]]:
    """Size a near-square R×C grid holding exactly `n` cells and list those cells in
    row-major order (the trailing row may be partial). Purely geometric — no RNG."""
    R = math.isqrt(n)
    if R * R < n:
        R += 1
    C = (n + R - 1) // R
    all_coords = [(r, c) for r in range(R) for c in range(C)][:n]
    return R, C, all_coords


def _bfs_grow(seed: _Coord, limit: int, unassigned: set[_Coord], coords_set: set[_Coord]) -> list[_Coord]:
    """Flood-fill a contiguous cluster of up to `limit` cells outward from `seed`, visiting
    only still-`unassigned` grid cells (the seed itself is always taken). No RNG — the
    randomness is in the caller's choice of seed and size."""
    coords: list[_Coord] = []
    queue = deque([seed])
    visited = {seed}
    while queue and len(coords) < limit:
        cur = queue.popleft()
        coords.append(cur)
        for nbr in _grid_neighbors(cur, coords_set):
            if nbr in unassigned and nbr not in visited:
                visited.add(nbr)
                queue.append(nbr)
    return coords


def _merge_into_nearest_cluster(groups_coords: list[list[_Coord]], leftover: list[_Coord]) -> None:
    """Fold a runt cluster into the outer cluster (index >= 1, never the Core at 0) whose
    nearest cell is closest to it by Manhattan distance."""
    best_idx = 1
    best_dist = 999999
    for c_left in leftover:
        for g_idx in range(1, len(groups_coords)):
            for c_g in groups_coords[g_idx]:
                d = abs(c_left[0] - c_g[0]) + abs(c_left[1] - c_g[1])
                if d < best_dist:
                    best_dist = d
                    best_idx = g_idx
    groups_coords[best_idx].extend(leftover)


def _partition_mesh_coords(
    cfg: BigBangConfig, rng: random.Random, R: int, C: int,
    all_coords: list[_Coord], coords_set: set[_Coord],
) -> list[list[_Coord]]:
    """Partition the grid into contiguous clusters: a deterministic central Core cluster
    first, then seeded outer clusters of size [cluster_min, cluster_max], folding any
    too-small leftover into its nearest existing outer cluster."""
    unassigned = set(all_coords)
    groups_coords: list[list[_Coord]] = []

    # Core cluster: grown from the grid centre so the Core sits in the middle of the mesh.
    # Deterministic (no RNG) — the Core must not vary with the seed.
    core_seed = (R // 2, C // 2)
    if core_seed not in unassigned:
        core_seed = next(iter(unassigned))
    core_coords = _bfs_grow(core_seed, cfg.core_sector_count, unassigned, coords_set)
    for coord in core_coords:
        unassigned.remove(coord)
    groups_coords.append(core_coords)

    # Outer clusters: pick a random unassigned seed and grow a random-sized blob from it.
    while unassigned:
        size = rng.randint(cfg.cluster_min, cfg.cluster_max)
        seed = rng.choice(list(unassigned))
        group_coords = _bfs_grow(seed, size, unassigned, coords_set)
        for coord in group_coords:
            unassigned.remove(coord)
        if len(group_coords) < cfg.cluster_min and len(groups_coords) > 1:
            _merge_into_nearest_cluster(groups_coords, group_coords)
        else:
            groups_coords.append(group_coords)
    return groups_coords


def _assign_mesh_sector_ids(groups_coords: list[list[_Coord]]) -> tuple[list[list[int]], dict[_Coord, int]]:
    """Number the cells 1..n cluster-by-cluster, returning the sector-id groups (Core is
    group 0) and the coord→sector-id map used to translate grid edges into warps."""
    coord_to_sid: dict[_Coord, int] = {}
    groups: list[list[int]] = []
    next_sid = 1
    for gc in groups_coords:
        group_sids: list[int] = []
        for coord in gc:
            coord_to_sid[coord] = next_sid
            group_sids.append(next_sid)
            next_sid += 1
        groups.append(group_sids)
    return groups, coord_to_sid


def _mesh_allowed_edges(
    all_coords: list[_Coord], coord_to_sid: dict[_Coord, int], coords_set: set[_Coord],
) -> set[tuple[int, int]]:
    """Every grid-adjacent sector pair `(u, v)` with `u < v` — the only edges any mesh pass
    may add, which is what keeps the warp graph spatially coherent (no crossing warps)."""
    allowed: set[tuple[int, int]] = set()
    for coord in all_coords:
        u = coord_to_sid[coord]
        for nbr in _grid_neighbors(coord, coords_set):
            v = coord_to_sid[nbr]
            if u < v:
                allowed.add((u, v))
    return allowed


def _connect_group_mesh(
    out: OutEdges, group: list[int], allowed_edges: set[tuple[int, int]],
    cfg: BigBangConfig, rng: random.Random,
) -> None:
    """Wire one mesh cluster: a spanning tree over its grid edges, then extra grid edges
    toward the target intra-group degree. The grid-constrained counterpart of
    `_connect_group_standard` / `_connect_group_planar`."""
    cap = cfg.max_warps_per_sector
    group_set = set(group)
    internal_candidates = [(u, v) for (u, v) in allowed_edges if u in group_set and v in group_set]

    # Spanning tree: repeatedly add a grid edge that joins the connected set to a new cell,
    # until every cell in the cluster is reachable (or no such edge remains).
    connected = {group[0]}
    unconnected = set(group[1:])
    while unconnected:
        tree_edge = None
        for u, v in internal_candidates:
            if (u in connected) != (v in connected):
                tree_edge = (u, v)
                break
        if tree_edge is None:
            break
        u, v = tree_edge
        add_bidirectional(out, u, v, cap)
        connected.add(u)
        connected.add(v)
        unconnected.discard(u)
        unconnected.discard(v)

    # Extra internal edges up to the configured density (shuffled for seeded variety).
    target_edges = int(cfg.intra_group_degree * len(group) / 2)
    current_edges = len(group) - 1
    rng.shuffle(internal_candidates)
    for u, v in internal_candidates:
        if current_edges >= target_edges:
            break
        if v not in out[u] and add_bidirectional(out, u, v, cap):
            current_edges += 1


def _bridge_groups_mesh(
    out: OutEdges, groups: list[list[int]], allowed_edges: set[tuple[int, int]],
    sector_to_group: dict[int, int], cfg: BigBangConfig, rng: random.Random,
) -> None:
    """Bridge the mesh clusters over grid edges: first a spanning tree across the clusters
    (each new bridge prefers the least-saturated endpoints, ties broken by the seed), then
    extra bridges toward the target inter-group degree. The grid-constrained counterpart of
    `_bridge_groups_trunk` / `_expansive` / `_planar`."""
    cap = cfg.max_warps_per_sector

    # Spanning tree over clusters: greedily attach an unconnected cluster via the grid edge
    # whose endpoints have the fewest warps so far (`rng.random()` breaks ties).
    connected_groups = {0}
    unconnected_groups = set(range(1, len(groups)))
    while unconnected_groups:
        valid_bridges = []
        for (u, v) in allowed_edges:
            g_u = sector_to_group[u]
            g_v = sector_to_group[v]
            if (g_u in connected_groups) != (g_v in connected_groups):
                valid_bridges.append((u, v, g_u, g_v))
        if not valid_bridges:
            break
        valid_bridges.sort(key=lambda item: (len(out[item[0]]) + len(out[item[1]]), rng.random()))
        u, v, g_u, g_v = valid_bridges[0]
        add_bidirectional(out, u, v, cap)
        new_g = g_v if g_u in connected_groups else g_u
        connected_groups.add(new_g)
        unconnected_groups.remove(new_g)

    # Extra inter-cluster bridges up to the configured density (shuffled for seeded variety).
    target_bridge_edges = int(cfg.inter_group_degree * len(groups) / 2)
    extra_bridges = max(0, target_bridge_edges - (len(groups) - 1))
    candidate_extra = [
        (u, v) for (u, v) in allowed_edges
        if sector_to_group[u] != sector_to_group[v] and v not in out[u]
    ]
    rng.shuffle(candidate_extra)
    added = 0
    for u, v in candidate_extra:
        if added >= extra_bridges:
            break
        if add_bidirectional(out, u, v, cap):
            added += 1


def _build_mesh_graph(out: OutEdges, cfg: BigBangConfig, rng: random.Random) -> list[list[int]]:
    """Generate the `mesh` topology (§5): lay all sectors on a 2D grid, partition it into
    contiguous clusters, then connect within and bridge between using only grid edges.
    Returns the region groups (the Core is group 0) and caches the grid layout for the
    mesh embedding step back in `generate`."""
    R, C, all_coords = _mesh_grid_geometry(cfg.sector_count)
    coords_set = set(all_coords)

    groups_coords = _partition_mesh_coords(cfg, rng, R, C, all_coords, coords_set)
    groups, coord_to_sid = _assign_mesh_sector_ids(groups_coords)

    # Cache the coord layout for generate()'s mesh embedding — a module-level build cache
    # like core_hops/adjacency, recomputed identically on every regeneration.
    global _last_mesh_coords, _last_mesh_grid_size
    _last_mesh_coords = {coord_to_sid[coord]: coord for coord in all_coords}
    _last_mesh_grid_size = (R, C)

    allowed_edges = _mesh_allowed_edges(all_coords, coord_to_sid, coords_set)
    sector_to_group = {s: gi for gi, group in enumerate(groups) for s in group}

    for group in groups:
        _connect_group_mesh(out, group, allowed_edges, cfg, rng)
    _bridge_groups_mesh(out, groups, allowed_edges, sector_to_group, cfg, rng)
    return groups


def build_graph(cfg: BigBangConfig, rng: random.Random) -> tuple[OutEdges, list[list[int]]]:
    """Build the warp graph and return its adjacency plus the region groups."""
    n = cfg.sector_count
    cap = cfg.max_warps_per_sector
    out: OutEdges = {sid: set() for sid in range(1, n + 1)}

    if cfg.topology_mode == "mesh":
        groups = _build_mesh_graph(out, cfg, rng)
        return out, groups

    core = list(range(1, cfg.core_sector_count + 1))
    carve_core(out, core, rng, cap)
    other = _cluster_groups(list(range(cfg.core_sector_count + 1, n + 1)), cfg, rng)
    groups = [core, *other]
    for group in other:
        if cfg.topology_mode == "planar":
            _connect_group_planar(out, group, cfg, rng)
        else:
            _connect_group_standard(out, group, cfg, rng)
    if cfg.topology_mode == "expansive":
        _bridge_groups_expansive(out, groups, cfg, rng)
    elif cfg.topology_mode == "planar":
        _bridge_groups_planar(out, groups, cfg, rng)
    else:
        _bridge_groups_trunk(out, groups, cfg, rng)
    add_ring_motifs(out, groups, rng, cap, count=max(1, n // 50))
    return out, groups


def generate(config: GameConfig, seed: int, *, created_at: str = "1970-01-01T00:00:00Z") -> UniverseState:
    """Generate a validated universe from `(seed, config)`; raise on repeated failure."""
    cfg = config.bigbang
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        build_rng = random.Random(f"{seed}-{attempt}")  # str seed: deterministic, typed
        out, groups = build_graph(cfg, build_rng)
        active_bands = cfg.active_bands()  # per-mode hop thresholds (§5 step 5)
        bands = compute_bands(out, 1, active_bands)

        gov = config.roster.core_governing_alliance_id if config.roster else 1
        game = Game(
            id=1, seed=seed, config_version=config.config_version,
            created_at=created_at, core_governing_alliance_id=gov,
        )
        state = UniverseState.new(game)  # runtime rng = Random(seed), left untouched
        state.topology_mode = cfg.topology_mode

        sector_to_region = {sid: gi + 1 for gi, group in enumerate(groups) for sid in group}
        core_ids = set(range(1, cfg.core_sector_count + 1))
        
        names_cfg = config.names
        region_gen = NameGenerator(names_cfg.regions if names_cfg else None, "Region", build_rng)
        
        state.regions = {
            gi + 1: Region(id=gi + 1, name=region_gen.draw())
            for gi in range(len(groups))
        }
        state.sectors = {
            sid: Sector(
                id=sid,
                region_id=sector_to_region[sid],
                warps_out=tuple(sorted(out[sid])),
                distance_band=bands.get(sid, active_bands[-1].name),
                is_galactic_core=sid in core_ids,
            )
            for sid in out
        }
        state.rebuild_adjacency()
        state.core_hops = bfs_distances(out, 1)  # gravity-arrow cache (§11, WP-C)
        state.spatial_ids = assign_spatial_ids(groups, state.core_hops, active_bands)  # §5.1 display ids
        if cfg.topology_mode == "mesh":
            global _last_mesh_coords, _last_mesh_grid_size
            R, C = _last_mesh_grid_size
            state.sector_pos = {
                sid: (float(coord[1] - C / 2.0), float(coord[0] - R / 2.0))
                for sid, coord in _last_mesh_coords.items()
            }
        else:
            state.sector_pos = compute_embedding(out, state.core_hops, seed=seed)  # §5.1 nav-rose layout

        _populate.populate(state, config, build_rng)
        salt_discoveries(state, config, attempt)  # §7 finds on an independent sub-RNG

        try:
            populate_species(state, config)  # §6 aliens + home clusters on an independent sub-RNG
            salt_raid_caches(state, config)  # §7/§10 legendary caches on hostile homeworlds (WP44)
            # §6.7 intel: give each species kind the places it can tip the player toward.
            state.species_knowledge = build_species_knowledge(state, seed)
            _validate.validate(state, config)
        except (_validate.ValidationError, HomeClusterError) as exc:
            last_error = exc
            continue
        return state

    raise BigBangError(f"big bang failed validation after {_MAX_ATTEMPTS} attempts: {last_error}")


def summarize(state: UniverseState) -> str:
    """A text report of a generated universe (the `--stats` dev view, §5)."""
    from collections import Counter

    # Helper function for title case conversion
    def to_title_case(name: str) -> str:
        if name.upper() == "STARDOCK":
            return "StarDock"
        return name.replace("_", " ").title()

    # Spacing and table formatting helper
    def format_table(title: str, rows: list[tuple[str, str]], width: int = 45) -> list[str]:
        section_lines = [
            title,
            "-" * width,
        ]
        for key, val in rows:
            # Spacing between key and value
            space_count = max(1, width - len(key) - len(val))
            section_lines.append(f"{key}{' ' * space_count}{val}")
        return section_lines

    # Exiting edges histogram helper
    # We want a text histogram showing the number of sectors for each number of edges exiting it.
    degrees = [len(s.warps_out) for s in state.sectors.values()]
    max_deg = max(degrees) if degrees else 0
    deg_counts = Counter(degrees)

    edges_histogram: list[str] = [
        "Exiting Edges",
        "-------------",
    ]
    max_deg_count = max(deg_counts.values()) if deg_counts else 0
    max_label_len = len(str(max_deg))
    for d in range(1, max_deg + 1):
        count = deg_counts.get(d, 0)
        if max_deg_count > 0:
            width = int(round(count * 40 / max_deg_count))
            if width == 0 and count > 0:
                width = 1
        else:
            width = 0
        bar = "█" * width
        label = f"  {d:<{max_label_len}}"
        edges_histogram.append(f"{label}  {bar} ({count})")

    # Port Classes histogram helper
    # Ordered by frequency/count (ascending), then by formatted label (alphabetically).
    from edge.core.enums import PORT_CLASS_TRADES, PortMode, Commodity
    
    def get_port_label(klass: PortClass) -> str:
        if klass is PortClass.STARDOCK:
            return "StarDock"
        trades = PORT_CLASS_TRADES[klass]
        mnemonic = "".join("B" if trades[c] is PortMode.BUY else "S" for c in Commodity)
        return f"Class {klass.value} ({mnemonic})"

    classes_counts = Counter(p.klass for p in state.ports.values())
    formatted_class_names = {klass: get_port_label(klass) for klass in classes_counts.keys()}
    sorted_classes = sorted(
        classes_counts.items(),
        key=lambda item: (item[1], formatted_class_names[item[0]])
    )
    max_class_count = max(classes_counts.values()) if classes_counts else 0

    port_classes_header = f"Port Classes ({', '.join(to_title_case(c.value) for c in Commodity)})"
    port_classes_histogram: list[str] = [
        port_classes_header,
        "-" * len(port_classes_header),
    ]
    max_class_label_len = max((len(name) for name in formatted_class_names.values()), default=0)
    for klass, count in sorted_classes:
        name_tc = formatted_class_names[klass]
        if max_class_count > 0:
            width = int(round(count * 40 / max_class_count))
            if width == 0 and count > 0:
                width = 1
        else:
            width = 0
        bar = "█" * width
        label = f"  {name_tc:<{max_class_label_len}}"
        port_classes_histogram.append(f"{label}  {bar} ({count})")

    # Prepare other sections
    bands = Counter(s.distance_band for s in state.sectors.values())
    dock = next((p for p in state.ports.values() if p.klass is PortClass.STARDOCK), None)

    # Species by band histogram helper
    species_counts = Counter(sp.home_band for sp in state.species.values())
    
    BAND_ORDER = ["Hub", "Frontier", "Deep", "Void"]
    band_order_map = {name.lower(): idx for idx, name in enumerate(BAND_ORDER)}
    sorted_bands = sorted(
        bands.keys(),
        key=lambda b: (band_order_map.get(b.lower(), len(BAND_ORDER)), b)
    )
    species_by_band_histogram: list[str] = [
        "Species By Band",
        "---------------",
    ]
    max_species_total = max(species_counts.values()) if species_counts else 0

    # Calculate global max label length for formatting across all bands and species
    all_species_names = [sp.name for sp in state.species.values()]
    global_max_label_len = max([5] + [len(name) for name in all_species_names])

    for idx, b in enumerate(sorted_bands):
        if idx > 0:
            species_by_band_histogram.append("")

        # Band header
        species_by_band_histogram.append(to_title_case(b))

        # Get count of each species name in this band
        band_species = Counter(sp.name for sp in state.species.values() if sp.home_band == b)
        total_in_band = species_counts.get(b, 0)

        # Sort species by count ascending, then name alphabetically
        sorted_band_species = sorted(band_species.items(), key=lambda item: (item[1], item[0]))

        # 1. Species rows
        for name, count in sorted_band_species:
            if max_species_total > 0:
                width = int(round(count * 40 / max_species_total))
                if width == 0 and count > 0:
                    width = 1
            else:
                width = 0
            bar = "█" * width
            species_by_band_histogram.append(f"  {name:<{global_max_label_len}}  {bar} ({count})")

        # 2. Total row
        if max_species_total > 0:
            width = int(round(total_in_band * 40 / max_species_total))
            if width == 0 and total_in_band > 0:
                width = 1
        else:
            width = 0
        total_bar = "█" * width
        species_by_band_histogram.append(f"  {'Total':<{global_max_label_len}}  {total_bar} ({total_in_band})")

    universe_structure_rows = [
        ("  Seed", str(state.game.seed)),
        ("  Topology Mode", to_title_case(state.topology_mode)),
        ("  Sectors", str(len(state.sectors))),
        ("  Regions", str(len(state.regions))),
        ("  Max Warps", str(max_deg)),
    ]

    stardock_val = f"Sector {dock.sector_id}" if dock else "Missing"
    economic_rows = [
        ("  Ports", str(len(state.ports))),
        ("  Planets", str(len(state.planets))),
        ("  StarDock", stardock_val),
    ]

    band_rows = [
        (f"  {to_title_case(b)}", str(bands[b]))
        for b in sorted_bands
    ]

    # Species dispositions table helper
    disposition_rows: list[str] = [
        "Species Dispositions",
        "--------------------",
    ]
    from collections import defaultdict
    from edge.config import load_default_config
    from edge.core.aliens import disposition_band

    aliens_cfg = load_default_config().aliens
    name_to_dispositions = defaultdict(list)
    for sp in state.species.values():
        name_to_dispositions[sp.name].append(sp.base_disposition)

    avg_dispositions = {
        name: sum(disps) / len(disps)
        for name, disps in name_to_dispositions.items()
    }

    max_sp_name_len = max((len(name) for name in avg_dispositions.keys()), default=0)
    for name in sorted(avg_dispositions.keys()):
        disp = avg_dispositions[name]
        width = int(round(disp * 20))
        width = max(0, min(20, width))
        bar = "█" * width + " " * (20 - width)
        label = to_title_case(disposition_band(disp, aliens_cfg))
        disposition_rows.append(f"  {name:<{max_sp_name_len}}  {bar} {disp:.2f}  {label}")

    lines = []
    lines.extend(format_table("Universe Structure", universe_structure_rows, width=45))
    lines.append("")
    lines.extend(format_table("Economic & Points Of Interest", economic_rows, width=45))
    lines.append("")
    lines.extend(format_table("Distance Bands", band_rows, width=45))
    lines.append("")
    lines.extend(edges_histogram)
    lines.append("")
    lines.extend(port_classes_histogram)
    lines.append("")
    lines.extend(species_by_band_histogram)
    lines.append("")
    lines.extend(disposition_rows)

    return "\n".join(lines)
