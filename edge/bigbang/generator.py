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
from edge.bigbang.inhabitants import ground_target_counts, seed_inhabitants
from edge.bigbang.embedding import compute_embedding
from edge.bigbang.naming import NameGenerator
from edge.bigbang.numbering import assign_spatial_ids, assign_spiral_spatial_ids
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
_last_spiral_coords: dict[int, tuple[float, float]] = {}

_MAX_ATTEMPTS = 16


class BigBangError(Exception):
    """Generation failed validation after the bounded retries."""


def _cluster_groups(
    sectors: list[int], cluster_min: int, cluster_max: int, rng: random.Random
) -> list[list[int]]:
    """Partition `sectors` into contiguous groups of size [cluster_min, cluster_max]."""
    groups: list[list[int]] = []
    i = 0
    n = len(sectors)
    while i < n:
        size = rng.randint(cluster_min, cluster_max)
        group = sectors[i : i + size]
        # Fold a too-small trailing remainder into the previous group.
        if len(group) < cluster_min and groups:
            groups[-1].extend(group)
        else:
            groups.append(group)
        i += size
    return groups


class TopologyMode:
    """Base class for all topology builders (DESIGN §5)."""

    def __init__(self, cfg: BigBangConfig, rng: random.Random) -> None:
        self.rng: random.Random = rng
        self.sector_count: int = cfg.sector_count
        self.max_warps_per_sector: int = cfg.max_warps_per_sector
        self.core_sector_count: int = cfg.core_sector_count
        self.cluster_min: int = cfg.cluster_min
        self.cluster_max: int = cfg.cluster_max
        self.intra_group_degree: float = cfg.intra_group_degree
        self.inter_group_degree: float = cfg.inter_group_degree
        self.one_way_chance: float = cfg.one_way_chance

    def build(self, out: OutEdges) -> list[list[int]]:
        """Build the topology and return the region groups (the Core is group 0)."""
        raise NotImplementedError


class ClusteredTopology(TopologyMode):
    """Base class for topologies built by clustering and bridging groups."""

    def build(self, out: OutEdges) -> list[list[int]]:
        n = self.sector_count
        cap = self.max_warps_per_sector
        core = list(range(1, self.core_sector_count + 1))
        carve_core(out, core, self.rng, cap)
        other = _cluster_groups(
            list(range(self.core_sector_count + 1, n + 1)),
            self.cluster_min,
            self.cluster_max,
            self.rng,
        )
        groups = [core, *other]
        for group in other:
            self._connect_group(out, group)
        self._bridge_groups(out, groups)
        add_ring_motifs(out, groups, self.rng, cap, count=max(1, n // 50))
        return groups

    def _connect_group(self, out: OutEdges, group: list[int]) -> None:
        raise NotImplementedError

    def _bridge_groups(self, out: OutEdges, groups: list[list[int]]) -> None:
        raise NotImplementedError

    def _connect_group_standard(self, out: OutEdges, group: list[int]) -> None:
        """Wire one group: a random spanning tree, then edges toward avg degree ~2.5.

        The intra-cluster connector shared by the `trunk` and `expansive` modes
        (`planar` and `mesh` have their own)."""
        cap = self.max_warps_per_sector
        if len(group) < 2:
            return
        order = group[:]
        self.rng.shuffle(order)
        for idx in range(1, len(order)):
            add_bidirectional(out, order[idx], self.rng.choice(order[:idx]), cap)
        target_edges = int(self.intra_group_degree * len(group) / 2)
        current = sum(len(out[s] & set(group)) for s in group) // 2
        attempts = 0
        while current < target_edges and attempts < target_edges * 4:
            a, b = self.rng.sample(group, 2)
            if add_bidirectional(out, a, b, cap):
                current += 1
            attempts += 1


class TrunkTopology(ClusteredTopology):
    """Trunk topology builder (DESIGN §5)."""

    def __init__(self, cfg: BigBangConfig, rng: random.Random) -> None:
        super().__init__(cfg, rng)
        topo = cfg.active_topology()
        self.bridges_min: int = topo.bridges_min
        self.bridges_max: int = topo.bridges_max

    def _connect_group(self, out: OutEdges, group: list[int]) -> None:
        self._connect_group_standard(out, group)

    def _bridge_groups(self, out: OutEdges, groups: list[list[int]]) -> None:
        """`trunk` bridging (§5 step 2): a bidirectional spanning tree, then extra
        (maybe one-way) bridges. A group spanning tree rooted at the Core funnels
        outer-band traffic through the few tree bridges — the trunk-and-branches
        universe of chokepoints (the original, byte-identical algorithm)."""
        cap = self.max_warps_per_sector

        def _bridge(g1: list[int], g2: list[int], one_way: bool) -> None:
            for _ in range(6):  # a few member-pair tries in case of cap saturation
                a, b = self.rng.choice(g1), self.rng.choice(g2)
                ok = (
                    add_directed(out, a, b, cap)
                    if one_way
                    else add_bidirectional(out, a, b, cap)
                )
                if ok:
                    return

        # Spanning tree: each group links to a random earlier one (two-way) -> all
        # groups (incl. the core at index 0) mutually reachable.
        for i in range(1, len(groups)):
            _bridge(groups[i], groups[self.rng.randrange(i)], one_way=False)
        # Extra bridges per group for texture; some directional.
        for i, group in enumerate(groups):
            extra = self.rng.randint(self.bridges_min, self.bridges_max) - 1
            for _ in range(max(0, extra)):
                j = self.rng.randrange(len(groups))
                if j != i:
                    _bridge(
                        group,
                        groups[j],
                        one_way=self.rng.random() < self.one_way_chance,
                    )


class ExpansiveTopology(ClusteredTopology):
    """Expansive topology builder (DESIGN §5)."""

    def _connect_group(self, out: OutEdges, group: list[int]) -> None:
        self._connect_group_standard(out, group)

    def _bridge_groups(self, out: OutEdges, groups: list[list[int]]) -> None:
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
        cap = self.max_warps_per_sector
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
                    ok = (
                        add_directed(out, a, b, cap)
                        if one_way
                        else add_bidirectional(out, a, b, cap)
                    )
                    if ok:
                        return True
            return False

        non_core = list(range(1, len(groups)))
        self.rng.shuffle(non_core)
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
            self.rng.shuffle(outer_order)
            made = attempts = 0
            while made < 2 and attempts < 16:
                gi = outer_order[made % len(outer_order)]
                if _link(gi, self.rng.choice(inner)):
                    made += 1
                attempts += 1

        # Extra chords/one-ways: a little richer routing within the larger rings.
        for ring in rings:
            if len(ring) >= 3:
                for _ in range(self.rng.randint(0, 2)):
                    gi, gj = self.rng.sample(ring, 2)
                    _link(gi, gj, one_way=self.rng.random() < self.one_way_chance)


class PlanarTopology(ClusteredTopology):
    """Planar topology builder (DESIGN §5)."""

    def _connect_group(self, out: OutEdges, group: list[int]) -> None:
        """Wire one group internally as a planar outer-planar graph with zero crossings."""
        cap = self.max_warps_per_sector
        k = len(group)
        if k < 2:
            return
        if k == 2:
            add_bidirectional(out, group[0], group[1], cap)
            return

        # 1. Connect the outer cycle (always planar)
        order = group[:]
        self.rng.shuffle(order)
        for idx in range(k):
            add_bidirectional(out, order[idx], order[(idx + 1) % k], cap)

        # 2. Add non-crossing internal chords to satisfy the target intra-group degree
        target_edges = int(self.intra_group_degree * k / 2)
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
            u, v = sorted(self.rng.sample(range(k), 2))
            if v == u + 1 or (u == 0 and v == k - 1):
                continue
            if not crosses(u, v):
                if add_bidirectional(out, order[u], order[v], cap):
                    chords.append((u, v))
                    current += 1

    def _bridge_groups(self, out: OutEdges, groups: list[list[int]]) -> None:
        """`planar` bridging: connects clusters using a planar spiderweb meta-graph.

        1. Stratify the clusters into concentric rings (Ring 0 is the Core).
        2. Assign each cluster in a ring a nominal angle around the Core.
        3. Connect adjacent clusters within the same ring to form cycle ring roads.
        4. Connect each cluster in Ring R to its nearest angular neighbor in Ring R-1.
        5. Link the clusters by finding sectors with the lowest internal degree.
        """
        cap = self.max_warps_per_sector
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
        self.rng.shuffle(outer_indices)

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


class SpiralTopology(TopologyMode):
    """Dense concentric rings numbered outward from sector 1.

    Sector 1 has ``max_warps_per_sector`` neighbours, ring ``r`` has
    ``max_warps_per_sector * r`` sectors, and IDs advance around one ring before
    continuing onto the next.  The canonical six-warp configuration resembles a
    hexagonal tiling; larger caps add short ring chords to keep most sectors full.
    """

    def build(self, out: OutEdges) -> list[list[int]]:
        cap = self.max_warps_per_sector
        if cap < 6:
            raise ValueError("spiral topology requires max_warps_per_sector >= 6")
        if self.sector_count <= cap:
            raise ValueError(
                "spiral topology requires more sectors than max_warps_per_sector"
            )

        rings = self._concentric_rings()

        # Every ring is a cycle in internal-id order.  Ring 1 is therefore the
        # requested 2-3-4-5-6-7-2 neighbourhood around sector 1.
        for ring in rings[1:]:
            if len(ring) == 2:
                add_bidirectional(out, ring[0], ring[1], cap)
            elif len(ring) >= 3:
                for idx, sector_id in enumerate(ring):
                    add_bidirectional(out, sector_id, ring[(idx + 1) % len(ring)], cap)

        if len(rings) > 1:
            for sector_id in rings[1]:
                add_bidirectional(out, 1, sector_id, cap)

        # Close the numerical spiral between rings.  Edges inside a ring already
        # connect n <-> n+1; this seam connects the last ID of ring r to the first
        # ID of ring r+1, making monotonically increasing sector/spatial IDs one
        # continuous navigable path through the whole universe.
        for ring_index in range(1, len(rings) - 1):
            add_bidirectional(
                out,
                rings[ring_index][-1],
                rings[ring_index + 1][0],
                cap,
            )

        # Triangulate each annulus.  The first pass gives every outer sector an
        # inward warp; the second gives every inner sector one additional outward
        # warp.  Together with the two ring neighbours this fills every completed
        # interior sector to degree six without crossing or exceeding the cap.
        for ring_index in range(2, len(rings)):
            inner = rings[ring_index - 1]
            outer = rings[ring_index]
            inner_count = len(inner)
            outer_count = len(outer)
            for idx, sector_id in enumerate(outer):
                inward = inner[(idx * inner_count) // outer_count]
                add_bidirectional(out, sector_id, inward, cap)
            for idx, sector_id in enumerate(inner):
                outer_idx = (
                    (idx * outer_count + inner_count - 1) // inner_count - 1
                ) % outer_count
                add_bidirectional(out, sector_id, outer[outer_idx], cap)

        self._densify_rings(out, rings)
        self._rewire_wormholes(out)

        self._cache_spiral_coords(rings)
        core = list(range(1, min(self.core_sector_count, self.sector_count) + 1))
        other = _cluster_groups(
            list(range(len(core) + 1, self.sector_count + 1)),
            self.cluster_min,
            self.cluster_max,
            self.rng,
        )
        return [core, *other]

    def _concentric_rings(self) -> list[list[int]]:
        """Partition sequential IDs into rings of size ``cap * radius``."""
        rings = [[1]]
        next_sector = 2
        radius = 1
        while next_sector <= self.sector_count:
            stop = min(
                self.sector_count + 1,
                next_sector + self.max_warps_per_sector * radius,
            )
            rings.append(list(range(next_sector, stop)))
            next_sector = stop
            radius += 1
        return rings

    def _densify_rings(self, out: OutEdges, rings: list[list[int]]) -> None:
        """Add increasingly long ring chords until endpoints reach the warp cap.

        Short offsets are attempted first, retaining the concentric local shape.
        A simple undirected graph can leave a small parity residue on the outer
        boundary; every addition still passes through the shared degree-cap guard.
        """
        cap = self.max_warps_per_sector
        for ring in rings[1:]:
            for offset in range(2, len(ring) // 2 + 1):
                for idx, sector_id in enumerate(ring):
                    add_bidirectional(
                        out,
                        sector_id,
                        ring[(idx + offset) % len(ring)],
                        cap,
                    )

    def _rewire_wormholes(self, out: OutEdges) -> None:
        """Replace eligible two-way chords with paired, distant one-way exits.

        The numerical backbone ``n <-> n+1`` is never eligible, so spatial IDs
        remain traversable in order.  Both ends of a selected chord become
        wormhole sources, and neither sources nor destinations may be in Core
        Space.  The discovery pass recognizes these one-way exits and force-places
        the corresponding ``WORMHOLE`` discoveries later in generation.
        """
        if self.one_way_chance <= 0.0:
            return
        core_last = min(self.core_sector_count, self.sector_count)
        candidates = [
            (source, target)
            for source in range(core_last + 1, self.sector_count + 1)
            for target in out[source]
            if source < target
            and target > core_last
            and source in out[target]
            and target - source > 1
        ]
        self.rng.shuffle(candidates)
        wormhole_sources: set[int] = set()
        min_jump = max(self.max_warps_per_sector * 3, self.sector_count // 4)
        non_core_count = self.sector_count - core_last
        break_budget = round(self.one_way_chance * non_core_count / 2)
        breaks_made = 0

        for source, other_end in candidates:
            if breaks_made >= break_budget:
                break
            if source in wormhole_sources or other_end in wormhole_sources:
                continue
            source_target = self._distant_target(
                out, source, core_last, min_jump, {source, other_end}
            )
            if source_target is None:
                continue
            other_target = self._distant_target(
                out,
                other_end,
                core_last,
                min_jump,
                {source, other_end, source_target},
            )
            if other_target is None:
                continue

            out[source].remove(other_end)
            out[other_end].remove(source)
            source_added = add_directed(
                out, source, source_target, self.max_warps_per_sector
            )
            other_added = add_directed(
                out, other_end, other_target, self.max_warps_per_sector
            )
            if not source_added or not other_added:
                out[source].discard(source_target)
                out[other_end].discard(other_target)
                add_bidirectional(
                    out, source, other_end, self.max_warps_per_sector
                )
                continue
            wormhole_sources.update((source, other_end))
            breaks_made += 1

    def _distant_target(
        self,
        out: OutEdges,
        source: int,
        core_last: int,
        min_jump: int,
        blocked: set[int],
    ) -> int | None:
        """Choose a non-Core, genuinely one-way destination far along the spiral."""
        choices = [
            target
            for target in range(core_last + 1, self.sector_count + 1)
            if target not in blocked
            and abs(target - source) >= min_jump
            and target not in out[source]
            and source not in out[target]
        ]
        return self.rng.choice(choices) if choices else None

    @staticmethod
    def _cache_spiral_coords(rings: list[list[int]]) -> None:
        """Cache an exact concentric layout for the inspector and nav bearings."""
        coords: dict[int, tuple[float, float]] = {1: (0.0, 0.0)}
        for radius, ring in enumerate(rings[1:], start=1):
            for idx, sector_id in enumerate(ring):
                angle = 2.0 * math.pi * idx / len(ring)
                coords[sector_id] = (
                    radius * math.cos(angle),
                    radius * math.sin(angle),
                )
        global _last_spiral_coords
        _last_spiral_coords = coords


_MESH_NEIGHBOR_OFFSETS: tuple[_Coord, ...] = (
    (-1, 0),
    (1, 0),
    (-1, -1),
    (-1, 1),
    (1, -1),
    (1, 1),
)


class MeshTopology(TopologyMode):
    """Mesh topology builder (DESIGN §5)."""

    def build(self, out: OutEdges) -> list[list[int]]:
        """Generate the `mesh` topology (§5): lay all sectors on a 2D grid, partition it into
        contiguous clusters, then connect within and bridge between using only grid edges.
        Returns the region groups (the Core is group 0) and caches the grid layout for the
        mesh embedding step back in `generate`."""
        R, C, all_coords = self._mesh_grid_geometry(self.sector_count)
        coords_set = set(all_coords)

        groups_coords = self._partition_mesh_coords(R, C, all_coords, coords_set)
        groups, coord_to_sid = self._assign_mesh_sector_ids(groups_coords)

        # Cache the coord layout for generate()'s mesh embedding — a module-level build cache
        # like core_hops/adjacency, recomputed identically on every regeneration.
        global _last_mesh_coords, _last_mesh_grid_size
        _last_mesh_coords = {coord_to_sid[coord]: coord for coord in all_coords}
        _last_mesh_grid_size = (R, C)

        allowed_edges = self._mesh_allowed_edges(all_coords, coord_to_sid, coords_set)
        sector_to_group = {s: gi for gi, group in enumerate(groups) for s in group}

        for group in groups:
            self._connect_group_mesh(out, group, allowed_edges)
        self._bridge_groups_mesh(out, groups, allowed_edges, sector_to_group)
        return groups

    def _grid_neighbors(self, coord: _Coord, coords_set: set[_Coord]) -> list[_Coord]:
        """The in-bounds grid cells adjacent to `coord` (the two vertical cells plus the two
        diagonals on each of the rows above and below), in a fixed order. That order seeds the
        BFS growth below, so it must stay stable for reproducible generation."""
        r, c = coord
        return [
            (r + dr, c + dc)
            for dr, dc in _MESH_NEIGHBOR_OFFSETS
            if (r + dr, c + dc) in coords_set
        ]

    def _mesh_grid_geometry(self, n: int) -> tuple[int, int, list[_Coord]]:
        """Size a near-square R×C grid holding exactly `n` cells and list those cells in
        row-major order (the trailing row may be partial). Purely geometric — no RNG."""
        R = math.isqrt(n)
        if R * R < n:
            R += 1
        C = (n + R - 1) // R
        all_coords = [(r, c) for r in range(R) for c in range(C)][:n]
        return R, C, all_coords

    def _bfs_grow(
        self, seed: _Coord, limit: int, unassigned: set[_Coord], coords_set: set[_Coord]
    ) -> list[_Coord]:
        """Flood-fill a contiguous cluster of up to `limit` cells outward from `seed`, visiting
        only still-`unassigned` grid cells (the seed itself is always taken). No RNG — the
        randomness is in the caller's choice of seed and size."""
        coords: list[_Coord] = []
        queue = deque([seed])
        visited = {seed}
        while queue and len(coords) < limit:
            cur = queue.popleft()
            coords.append(cur)
            for nbr in self._grid_neighbors(cur, coords_set):
                if nbr in unassigned and nbr not in visited:
                    visited.add(nbr)
                    queue.append(nbr)
        return coords

    def _merge_into_nearest_cluster(
        self, groups_coords: list[list[_Coord]], leftover: list[_Coord]
    ) -> None:
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
        self,
        R: int,
        C: int,
        all_coords: list[_Coord],
        coords_set: set[_Coord],
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
        core_coords = self._bfs_grow(
            core_seed, self.core_sector_count, unassigned, coords_set
        )
        for coord in core_coords:
            unassigned.remove(coord)
        groups_coords.append(core_coords)

        # Outer clusters: pick a random unassigned seed and grow a random-sized blob from it.
        while unassigned:
            size = self.rng.randint(self.cluster_min, self.cluster_max)
            seed = self.rng.choice(list(unassigned))
            group_coords = self._bfs_grow(seed, size, unassigned, coords_set)
            for coord in group_coords:
                unassigned.remove(coord)
            if len(group_coords) < self.cluster_min and len(groups_coords) > 1:
                self._merge_into_nearest_cluster(groups_coords, group_coords)
            else:
                groups_coords.append(group_coords)
        return groups_coords

    def _assign_mesh_sector_ids(
        self, groups_coords: list[list[_Coord]]
    ) -> tuple[list[list[int]], dict[_Coord, int]]:
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
        self,
        all_coords: list[_Coord],
        coord_to_sid: dict[_Coord, int],
        coords_set: set[_Coord],
    ) -> set[tuple[int, int]]:
        """Every grid-adjacent sector pair `(u, v)` with `u < v` — the only edges any mesh pass
        may add, which is what keeps the warp graph spatially coherent (no crossing warps)."""
        allowed: set[tuple[int, int]] = set()
        for coord in all_coords:
            u = coord_to_sid[coord]
            for nbr in self._grid_neighbors(coord, coords_set):
                v = coord_to_sid[nbr]
                if u < v:
                    allowed.add((u, v))
        return allowed

    def _connect_group_mesh(
        self,
        out: OutEdges,
        group: list[int],
        allowed_edges: set[tuple[int, int]],
    ) -> None:
        """Wire one mesh cluster: a spanning tree over its grid edges, then extra grid edges
        toward the target intra-group degree. The grid-constrained counterpart of
        `_connect_group_standard` / `_connect_group_planar`."""
        cap = self.max_warps_per_sector
        group_set = set(group)
        internal_candidates = [
            (u, v) for (u, v) in allowed_edges if u in group_set and v in group_set
        ]

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
        target_edges = int(self.intra_group_degree * len(group) / 2)
        current_edges = len(group) - 1
        self.rng.shuffle(internal_candidates)
        for u, v in internal_candidates:
            if current_edges >= target_edges:
                break
            if v not in out[u] and add_bidirectional(out, u, v, cap):
                current_edges += 1

    def _bridge_groups_mesh(
        self,
        out: OutEdges,
        groups: list[list[int]],
        allowed_edges: set[tuple[int, int]],
        sector_to_group: dict[int, int],
    ) -> None:
        """Bridge the mesh clusters over grid edges: first a spanning tree across the clusters
        (each new bridge prefers the least-saturated endpoints, ties broken by the seed), then
        extra bridges toward the target inter-group degree. The grid-constrained counterpart of
        `_bridge_groups_trunk` / `_expansive` / `_planar`."""
        cap = self.max_warps_per_sector

        # Spanning tree over clusters: greedily attach an unconnected cluster via the grid edge
        # whose endpoints have the fewest warps so far (`self.rng.random()` breaks ties).
        connected_groups = {0}
        unconnected_groups = set(range(1, len(groups)))
        while unconnected_groups:
            valid_bridges = []
            for u, v in allowed_edges:
                g_u = sector_to_group[u]
                g_v = sector_to_group[v]
                if (g_u in connected_groups) != (g_v in connected_groups):
                    valid_bridges.append((u, v, g_u, g_v))
            if not valid_bridges:
                break
            valid_bridges.sort(
                key=lambda item: (
                    len(out[item[0]]) + len(out[item[1]]),
                    self.rng.random(),
                )
            )
            u, v, g_u, g_v = valid_bridges[0]
            add_bidirectional(out, u, v, cap)
            new_g = g_v if g_u in connected_groups else g_u
            connected_groups.add(new_g)
            unconnected_groups.remove(new_g)

        # Extra inter-cluster bridges up to the configured density (shuffled for seeded variety).
        target_bridge_edges = int(self.inter_group_degree * len(groups) / 2)
        extra_bridges = max(0, target_bridge_edges - (len(groups) - 1))
        candidate_extra = [
            (u, v)
            for (u, v) in allowed_edges
            if sector_to_group[u] != sector_to_group[v] and v not in out[u]
        ]
        self.rng.shuffle(candidate_extra)
        added = 0
        for u, v in candidate_extra:
            if added >= extra_bridges:
                break
            one_way = self.rng.random() < self.one_way_chance
            ok = (
                add_directed(out, u, v, cap)
                if one_way
                else add_bidirectional(out, u, v, cap)
            )
            if ok:
                added += 1


TOPOLOGY_MODES: dict[str, type[TopologyMode]] = {
    "trunk": TrunkTopology,
    "expansive": ExpansiveTopology,
    "planar": PlanarTopology,
    "mesh": MeshTopology,
    "spiral": SpiralTopology,
}


def build_graph(
    cfg: BigBangConfig, rng: random.Random
) -> tuple[OutEdges, list[list[int]]]:
    """Build the warp graph and return its adjacency plus the region groups."""
    n = cfg.sector_count
    out: OutEdges = {sid: set() for sid in range(1, n + 1)}

    mode_class = TOPOLOGY_MODES.get(cfg.topology_mode)
    if mode_class is None:
        raise ValueError(f"Unknown topology mode: {cfg.topology_mode}")

    builder = mode_class(cfg, rng)
    groups = builder.build(out)
    return out, groups


def generate(
    config: GameConfig, seed: int, *, created_at: str = "1970-01-01T00:00:00Z"
) -> UniverseState:
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
            id=1,
            seed=seed,
            config_version=config.config_version,
            created_at=created_at,
            core_governing_alliance_id=gov,
        )
        state = UniverseState.new(game)  # runtime rng = Random(seed), left untouched
        state.topology_mode = cfg.topology_mode

        sector_to_region = {
            sid: gi + 1 for gi, group in enumerate(groups) for sid in group
        }
        core_ids = set(range(1, cfg.core_sector_count + 1))

        names_cfg = config.names
        region_gen = NameGenerator(
            names_cfg.regions if names_cfg else None, "Region", build_rng
        )

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
        state.spatial_ids = (
            assign_spiral_spatial_ids(out)
            if cfg.topology_mode == "spiral"
            else assign_spatial_ids(groups, state.core_hops, active_bands)
        )  # §5.1 display ids
        if cfg.topology_mode == "mesh":
            global _last_mesh_coords, _last_mesh_grid_size
            R, C = _last_mesh_grid_size
            state.sector_pos = {
                sid: (float(coord[1] - C / 2.0), float(coord[0] - R / 2.0))
                for sid, coord in _last_mesh_coords.items()
            }
        elif cfg.topology_mode == "spiral":
            state.sector_pos = dict(_last_spiral_coords)
        else:
            state.sector_pos = compute_embedding(
                out, state.core_hops, seed=seed
            )  # §5.1 nav-rose layout

        _populate.populate(state, config, build_rng)
        salt_discoveries(state, config, attempt)  # §7 finds on an independent sub-RNG

        try:
            populate_species(
                state, config
            )  # §6 aliens + home clusters on an independent sub-RNG
            from edge.bigbang.station_archetypes import assign_station_archetypes
            assign_station_archetypes(state, config)  # fixed roster-driven builders (§5)
            # The inhabited universe (GW-WP09-PRE): native peoples, populations, and
            # citadel holdings. After the cast and its home clusters exist (it reads
            # both), before the raid caches that key off hostile homeworlds.
            seed_inhabitants(state, config)
            salt_raid_caches(
                state, config
            )  # §7/§10 legendary caches on hostile homeworlds (WP44)
            # §6.7 intel: give each species kind the places it can tip the player toward.
            state.species_knowledge = build_species_knowledge(state, seed)
            _validate.validate(state, config)
        except (_validate.ValidationError, HomeClusterError) as exc:
            last_error = exc
            continue
        return state

    raise BigBangError(
        f"big bang failed validation after {_MAX_ATTEMPTS} attempts: {last_error}"
    )


def summarize(state: UniverseState) -> str:
    """A text report of a generated universe (the `--stats` dev view, §5)."""
    from collections import Counter

    # Helper function for title case conversion
    def to_title_case(name: str) -> str:
        if name.upper() == "STARDOCK":
            return "Stardock"
        return name.replace("_", " ").title()

    # Spacing and table formatting helper
    def format_table(
        title: str, rows: list[tuple[str, str]], width: int = 45
    ) -> list[str]:
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

    one_way_count = 0
    for sid, s in state.sectors.items():
        for target in s.warps_out:
            target_sector = state.sectors.get(target)
            if target_sector is None or sid not in target_sector.warps_out:
                one_way_count += 1

    edges_histogram: list[str] = [
        "Exiting Edges",
        "-------------",
    ]
    max_deg_count = (
        max(list(deg_counts.values()) + [one_way_count])
        if (deg_counts or one_way_count > 0)
        else 0
    )
    max_label_len = max([7] + [len(str(d)) for d in range(1, max_deg + 1)])
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

    if max_deg_count > 0:
        width = int(round(one_way_count * 40 / max_deg_count))
        if width == 0 and one_way_count > 0:
            width = 1
    else:
        width = 0
    one_way_bar = "█" * width
    one_way_label = f"  {'One-Way':<{max_label_len}}"
    edges_histogram.append(f"{one_way_label}  {one_way_bar} ({one_way_count})")

    # Port Classes histogram helper
    # Ordered by frequency/count (ascending), then by formatted label (alphabetically).
    from edge.core.enums import PORT_CLASS_TRADES, PortMode, Commodity

    def get_port_label(klass: PortClass) -> str:
        if klass is PortClass.STARDOCK:
            return "Stardock"
        trades = PORT_CLASS_TRADES[klass]
        mnemonic = "".join("B" if trades[c] is PortMode.BUY else "S" for c in Commodity)
        return f"Class {klass.value} ({mnemonic})"

    classes_counts = Counter(p.klass for p in state.ports.values())
    formatted_class_names = {
        klass: get_port_label(klass) for klass in classes_counts.keys()
    }
    sorted_classes = sorted(
        classes_counts.items(),
        key=lambda item: -1 if item[0] is PortClass.STARDOCK else item[0].value,
    )
    max_class_count = max(classes_counts.values()) if classes_counts else 0

    port_classes_header = (
        f"Port Classes ({', '.join(to_title_case(c.value) for c in Commodity)})"
    )
    port_classes_histogram: list[str] = [
        port_classes_header,
        "-" * len(port_classes_header),
    ]
    max_class_label_len = max(
        (len(name) for name in formatted_class_names.values()), default=0
    )
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
    dock = next(
        (p for p in state.ports.values() if p.klass is PortClass.STARDOCK), None
    )

    # Species by band histogram helper
    species_counts = Counter(sp.home_band for sp in state.species.values())
    max_species_total = max(species_counts.values()) if species_counts else 0

    BAND_ORDER = ["Hub", "Frontier", "Deep", "Void"]
    band_order_map = {name.lower(): idx for idx, name in enumerate(BAND_ORDER)}
    sorted_bands = sorted(
        bands.keys(), key=lambda b: (band_order_map.get(b.lower(), len(BAND_ORDER)), b)
    )
    species_by_band_histogram: list[str] = [
        "Species By Band",
        "---------------",
    ]
    all_species_names = [sp.name for sp in state.species.values()]
    global_max_label_len = max([5] + [len(name) for name in all_species_names])

    for idx, b in enumerate(sorted_bands):
        if idx > 0:
            species_by_band_histogram.append("")

        species_by_band_histogram.append(to_title_case(b))

        band_species = Counter(
            sp.name for sp in state.species.values() if sp.home_band == b
        )
        total_in_band = species_counts.get(b, 0)

        sorted_band_species = sorted(
            band_species.items(), key=lambda item: (item[1], item[0])
        )

        for name, count in sorted_band_species:
            if max_species_total > 0:
                width = int(round(count * 40 / max_species_total))
                if width == 0 and count > 0:
                    width = 1
            else:
                width = 0
            bar = "█" * width
            species_by_band_histogram.append(
                f"  {name:<{global_max_label_len}}  {bar} ({count})"
            )

        if max_species_total > 0:
            width = int(round(total_in_band * 40 / max_species_total))
            if width == 0 and total_in_band > 0:
                width = 1
        else:
            width = 0
        total_bar = "█" * width
        species_by_band_histogram.append(
            f"  {'Total':<{global_max_label_len}}  {total_bar} ({total_in_band})"
        )

    # Discoveries by band histogram helper
    discovery_counts = Counter(
        state.sectors[d.sector_id].distance_band for d in state.discoveries.values()
    )
    discoveries_by_band_histogram: list[str] = [
        "Discoveries By Band",
        "-------------------",
    ]
    max_discovery_total = max(discovery_counts.values()) if discovery_counts else 0

    all_discovery_kinds = [
        to_title_case(d.kind.value) for d in state.discoveries.values()
    ]
    global_max_disc_label_len = max([5] + [len(kind) for kind in all_discovery_kinds])

    for idx, b in enumerate(sorted_bands):
        if idx > 0:
            discoveries_by_band_histogram.append("")

        discoveries_by_band_histogram.append(to_title_case(b))

        band_discoveries = Counter(
            to_title_case(d.kind.value)
            for d in state.discoveries.values()
            if state.sectors[d.sector_id].distance_band == b
        )
        total_in_band = discovery_counts.get(b, 0)

        sorted_band_discoveries = sorted(
            band_discoveries.items(), key=lambda item: (item[1], item[0])
        )

        for kind, count in sorted_band_discoveries:
            if max_discovery_total > 0:
                width = int(round(count * 40 / max_discovery_total))
                if width == 0 and count > 0:
                    width = 1
            else:
                width = 0
            bar = "█" * width
            discoveries_by_band_histogram.append(
                f"  {kind:<{global_max_disc_label_len}}  {bar} ({count})"
            )

        if max_discovery_total > 0:
            width = int(round(total_in_band * 40 / max_discovery_total))
            if width == 0 and total_in_band > 0:
                width = 1
        else:
            width = 0
        total_bar = "█" * width
        discoveries_by_band_histogram.append(
            f"  {'Total':<{global_max_disc_label_len}}  {total_bar} ({total_in_band})"
        )

    # Planets by band histogram helper
    planet_counts = Counter(
        state.sectors[p.sector_id].distance_band for p in state.planets.values()
    )
    planets_by_band_histogram: list[str] = [
        "Planets By Band",
        "---------------",
    ]
    max_planet_total = max(planet_counts.values()) if planet_counts else 0

    all_planet_types = [to_title_case(p.planet_type) for p in state.planets.values()]
    global_max_planet_label_len = max([5] + [len(pt) for pt in all_planet_types])

    for idx, b in enumerate(sorted_bands):
        if idx > 0:
            planets_by_band_histogram.append("")

        planets_by_band_histogram.append(to_title_case(b))

        band_planets = Counter(
            to_title_case(p.planet_type)
            for p in state.planets.values()
            if state.sectors[p.sector_id].distance_band == b
        )
        total_in_band = planet_counts.get(b, 0)

        sorted_band_planets = sorted(
            band_planets.items(), key=lambda item: (item[1], item[0])
        )

        for pt, count in sorted_band_planets:
            if max_planet_total > 0:
                width = int(round(count * 40 / max_planet_total))
                if width == 0 and count > 0:
                    width = 1
            else:
                width = 0
            bar = "█" * width
            planets_by_band_histogram.append(
                f"  {pt:<{global_max_planet_label_len}}  {bar} ({count})"
            )

        if max_planet_total > 0:
            width = int(round(total_in_band * 40 / max_planet_total))
            if width == 0 and total_in_band > 0:
                width = 1
        else:
            width = 0
        total_bar = "█" * width
        planets_by_band_histogram.append(
            f"  {'Total':<{global_max_planet_label_len}}  {total_bar} ({total_in_band})"
        )

    cluster_sizes = list(Counter(s.region_id for s in state.sectors.values()).values())
    min_cluster = min(cluster_sizes) if cluster_sizes else 0
    max_cluster = max(cluster_sizes) if cluster_sizes else 0
    avg_cluster = sum(cluster_sizes) / len(cluster_sizes) if cluster_sizes else 0.0

    universe_structure_rows = [
        ("  Seed", str(state.game.seed)),
        ("  Topology Mode", to_title_case(state.topology_mode)),
        ("  Sectors", str(len(state.sectors))),
        ("  Regions", str(len(state.regions))),
        ("  Max Warps", str(max_deg)),
        ("  Min Sectors / Cluster", str(min_cluster)),
        ("  Max Sectors / Cluster", str(max_cluster)),
        ("  Avg Sectors / Cluster", f"{avg_cluster:.1f}"),
    ]

    stardock_val = f"Sector {dock.sector_id}" if dock else "Missing"
    # Who lives here, and what the ground game has to work with (GW-WP09-PRE): the
    # inhabited count, and the target set a *fresh* player would find — worlds that
    # route to assault, and inhabited friendly worlds whose survey has settlements.
    # (Aliased: `load_default_config` is imported further down this function, which
    # would make the bare name local for the whole body and unbound up here.)
    from edge.config import load_default_config as _default_config

    inhabited = sum(1 for p in state.planets.values() if p.population)
    population = sum(p.colonists for p in state.planets.values())
    assaultable, friendly_inhabited = ground_target_counts(state, _default_config())
    economic_rows = [
        ("  Ports", str(len(state.ports))),
        ("  Planets", str(len(state.planets))),
        ("  Inhabited Worlds", f"{inhabited} ({population:,} people)"),
        ("  Assaultable / Friendly", f"{assaultable} / {friendly_inhabited}"),
        ("  Stardock", stardock_val),
    ]

    band_rows = [(f"  {to_title_case(b)}", str(bands[b])) for b in sorted_bands]

    alliance_rows = []
    core_size = sum(1 for s in state.sectors.values() if s.is_galactic_core)
    gov_id = state.game.core_governing_alliance_id
    gov_alliance = state.alliances.get(gov_id) if gov_id is not None else None
    gov_name = gov_alliance.name if gov_alliance else "Federation"
    alliance_rows.append((f"  {gov_name} (The Core)", f"{core_size} Sectors"))

    if state.home_clusters:
        for alliance_id, sectors in sorted(
            state.home_clusters.items(),
            key=lambda item: (
                state.alliances[item[0]].name
                if item[0] in state.alliances
                else f"Alliance {item[0]}"
            ),
        ):
            name_obj = state.alliances.get(alliance_id)
            name = name_obj.name if name_obj else f"Alliance {alliance_id}"
            alliance_rows.append((f"  {name}", f"{len(sectors)} Sectors"))

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
        name: sum(disps) / len(disps) for name, disps in name_to_dispositions.items()
    }

    max_sp_name_len = max((len(name) for name in avg_dispositions.keys()), default=0)
    sorted_avg_disps = sorted(
        avg_dispositions.items(), key=lambda item: (-item[1], item[0])
    )
    for name, disp in sorted_avg_disps:
        width = int(round(disp * 20))
        width = max(0, min(20, width))
        bar = "█" * width + " " * (20 - width)
        label = to_title_case(disposition_band(disp, aliens_cfg))
        disposition_rows.append(
            f"  {name:<{max_sp_name_len}}  {bar} {disp:.2f}  {label}"
        )

    # Average disposition for all species per band
    band_disposition_rows: list[str] = [
        "Average Disposition By Band",
        "---------------------------",
    ]
    band_to_disps = defaultdict(list)
    for sp in state.species.values():
        band_to_disps[sp.home_band].append(sp.base_disposition)

    band_avg_disps = {}
    for b in sorted_bands:
        disps = band_to_disps.get(b, [])
        band_avg_disps[b] = sum(disps) / len(disps) if disps else 0.0

    max_band_name_len = max((len(to_title_case(b)) for b in sorted_bands), default=0)
    for b in sorted_bands:
        disp = band_avg_disps[b]
        width = int(round(disp * 20))
        width = max(0, min(20, width))
        bar = "█" * width + " " * (20 - width)
        label = to_title_case(disposition_band(disp, aliens_cfg))
        band_disposition_rows.append(
            f"  {to_title_case(b):<{max_band_name_len}}  {bar} {disp:.2f}  {label}"
        )

    lines = []
    lines.extend(format_table("Universe Structure", universe_structure_rows, width=45))
    lines.append("")
    lines.extend(format_table("Economic & Points Of Interest", economic_rows, width=45))
    lines.append("")
    lines.extend(format_table("Distance Bands", band_rows, width=45))
    lines.append("")
    lines.extend(format_table("Alliance Clusters", alliance_rows, width=45))
    lines.append("")
    lines.extend(edges_histogram)
    lines.append("")
    lines.extend(port_classes_histogram)
    lines.append("")
    lines.extend(species_by_band_histogram)
    lines.append("")
    lines.extend(disposition_rows)
    lines.append("")
    lines.extend(band_disposition_rows)
    lines.append("")
    lines.extend(discoveries_by_band_histogram)
    lines.append("")
    lines.extend(planets_by_band_histogram)

    return "\n".join(lines)
