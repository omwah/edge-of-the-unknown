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

_last_mesh_coords: dict[int, tuple[int, int]] = {}
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


def _connect_group(out: OutEdges, group: list[int], cfg: BigBangConfig, rng: random.Random) -> None:
    """Wire one group: a random spanning tree, then edges toward avg degree ~2.5."""
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
        extra = rng.randint(cfg.bridges_min, cfg.bridges_max) - 1
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


def build_graph(cfg: BigBangConfig, rng: random.Random) -> tuple[OutEdges, list[list[int]]]:
    """Build the warp graph and return its adjacency plus the region groups."""
    n = cfg.sector_count
    cap = cfg.max_warps_per_sector
    out: OutEdges = {sid: set() for sid in range(1, n + 1)}

    if cfg.topology_mode == "mesh":
        # 1. Grid geometry
        R = math.isqrt(n)
        if R * R < n:
            R = math.isqrt(n) + 1
        C = (n + R - 1) // R

        # Keep exactly n coordinates
        all_coords: list[tuple[int, int]] = []
        for r in range(R):
            for c in range(C):
                if len(all_coords) < n:
                    all_coords.append((r, c))
        coords_set = set(all_coords)

        def get_grid_neighbors(coord: tuple[int, int]) -> list[tuple[int, int]]:
            r, c = coord
            candidates = [
                (r - 1, c),
                (r + 1, c),
                (r - 1, c - 1),
                (r - 1, c + 1),
                (r + 1, c - 1),
                (r + 1, c + 1),
            ]
            return [(nr, nc) for nr, nc in candidates if (nr, nc) in coords_set]

        # 2. Grow contiguous clusters using BFS on coordinate grid
        from collections import deque
        unassigned = set(all_coords)
        groups_coords: list[list[tuple[int, int]]] = []

        # Grow Core cluster first
        core_target = cfg.core_sector_count
        core_coords: list[tuple[int, int]] = []
        grid_seed = (R // 2, C // 2)
        if grid_seed not in unassigned:
            grid_seed = next(iter(unassigned))
            
        queue = deque([grid_seed])
        visited = {grid_seed}
        while queue and len(core_coords) < core_target:
            cur = queue.popleft()
            core_coords.append(cur)
            for nbr in get_grid_neighbors(cur):
                if nbr in unassigned and nbr not in visited:
                    visited.add(nbr)
                    queue.append(nbr)
                    
        for coord in core_coords:
            unassigned.remove(coord)
        groups_coords.append(core_coords)

        # Grow outer clusters
        while unassigned:
            size = rng.randint(cfg.cluster_min, cfg.cluster_max)
            grid_seed = rng.choice(list(unassigned))
            group_coords: list[tuple[int, int]] = []
            queue = deque([grid_seed])
            visited = {grid_seed}
            while queue and len(group_coords) < size:
                cur = queue.popleft()
                group_coords.append(cur)
                for nbr in get_grid_neighbors(cur):
                    if nbr in unassigned and nbr not in visited:
                        visited.add(nbr)
                        queue.append(nbr)
            
            for coord in group_coords:
                unassigned.remove(coord)
                
            if len(group_coords) < cfg.cluster_min and len(groups_coords) > 1:
                # Merge leftover with closest outer cluster (index >= 1)
                best_group_idx = 1
                best_dist = 999999
                for c_left in group_coords:
                    for g_idx in range(1, len(groups_coords)):
                        for c_g in groups_coords[g_idx]:
                            d = abs(c_left[0] - c_g[0]) + abs(c_left[1] - c_g[1])
                            if d < best_dist:
                                best_dist = d
                                best_group_idx = g_idx
                groups_coords[best_group_idx].extend(group_coords)
            else:
                groups_coords.append(group_coords)

        # 3. Map coordinates to sector IDs
        coord_to_sid = {}
        groups = []
        next_sid = 1
        for gc in groups_coords:
            group_sids = []
            for coord in gc:
                coord_to_sid[coord] = next_sid
                group_sids.append(next_sid)
                next_sid += 1
            groups.append(group_sids)

        # Save coordinate map to module cache
        global _last_mesh_coords, _last_mesh_grid_size
        _last_mesh_coords = {coord_to_sid[coord]: coord for coord in all_coords}
        _last_mesh_grid_size = (R, C)

        # 4. Allowed grid edges
        allowed_edges = set()
        for coord in all_coords:
            u = coord_to_sid[coord]
            for nbr in get_grid_neighbors(coord):
                v = coord_to_sid[nbr]
                if u < v:
                    allowed_edges.add((u, v))

        # 5. Connect clusters internally
        sector_to_group = {}
        for g_idx, group in enumerate(groups):
            for s in group:
                sector_to_group[s] = g_idx

        for g_idx, group in enumerate(groups):
            group_set = set(group)
            internal_candidates = [
                (u, v) for (u, v) in allowed_edges
                if u in group_set and v in group_set
            ]
            
            # Internal spanning tree using grid edges
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

            # Add extra internal edges up to target density
            target_edges = int(cfg.intra_group_degree * len(group) / 2)
            current_edges = len(group) - 1
            rng.shuffle(internal_candidates)
            for u, v in internal_candidates:
                if current_edges >= target_edges:
                    break
                if v not in out[u]:
                    if add_bidirectional(out, u, v, cap):
                        current_edges += 1

        # 6. Inter-cluster bridging spanning tree
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

        # Add extra bridges for mesh density
        extra_bridges = int(len(groups) * 0.3)
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

        return out, groups

    core = list(range(1, cfg.core_sector_count + 1))
    carve_core(out, core, rng, cap)
    other = _cluster_groups(list(range(cfg.core_sector_count + 1, n + 1)), cfg, rng)
    groups = [core, *other]
    for group in other:
        if cfg.topology_mode == "planar":
            _connect_group_planar(out, group, cfg, rng)
        else:
            _connect_group(out, group, cfg, rng)
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
    """A text report of a generated universe (the `--inspect` dev view, §5)."""
    from collections import Counter

    bands = Counter(s.distance_band for s in state.sectors.values())
    classes = Counter(p.klass.name for p in state.ports.values())
    dock = next((p for p in state.ports.values() if p.klass is PortClass.STARDOCK), None)
    degrees = [len(s.warps_out) for s in state.sectors.values()]
    lines = [
        f"seed={state.game.seed}  sectors={len(state.sectors)}  regions={len(state.regions)}",
        f"ports={len(state.ports)}  planets={len(state.planets)}  "
        f"max_warps={max(degrees) if degrees else 0}",
        "bands:        " + ", ".join(f"{b}={n}" for b, n in sorted(bands.items())),
        "port classes: " + ", ".join(f"{c}={n}" for c, n in sorted(classes.items())),
        f"stardock:     sector {dock.sector_id}" if dock else "stardock:     MISSING",
    ]
    return "\n".join(lines)
