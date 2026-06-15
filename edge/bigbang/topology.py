"""Graph primitives, the Core carve, motifs, and distance bands (DESIGN §5).

The warp graph is a directional adjacency of `int -> set[int]` (one-way bridges
are possible, §5). Phase-1 generation uses plain dicts rather than networkx:
the cluster+bridge build is simple, and plain dicts keep `bigbang` under clean
`mypy --strict` (networkx ships no type stubs). networkx remains available for
later richer motifs/pathfinding per §3.

Every edge addition respects the out-degree cap (`max_warps_per_sector`, the
TW2002 ≤ 6 canon), so the degree invariant holds by construction.
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Iterable, Mapping

from edge.core.config import DistanceBand

OutEdges = dict[int, set[int]]


def add_directed(out: OutEdges, a: int, b: int, cap: int) -> bool:
    """Add a one-way warp a -> b if legal and under the out-degree cap."""
    if a == b or b in out[a] or len(out[a]) >= cap:
        return False
    out[a].add(b)
    return True


def add_bidirectional(out: OutEdges, a: int, b: int, cap: int) -> bool:
    """Add a two-way warp a <-> b only if both ends stay under the cap."""
    if a == b or b in out[a] or len(out[a]) >= cap or len(out[b]) >= cap:
        return False
    out[a].add(b)
    out[b].add(a)
    return True


def bfs_distances(out: Mapping[int, Iterable[int]], src: int) -> dict[int, int]:
    """Forward hop distance from `src` to every reachable sector.

    Accepts any int-iterable adjacency, so it works on both the build-time
    `OutEdges` (sets) and the runtime adjacency (tuples).
    """
    dist = {src: 0}
    queue: deque[int] = deque([src])
    while queue:
        cur = queue.popleft()
        for nxt in out.get(cur, ()):
            if nxt not in dist:
                dist[nxt] = dist[cur] + 1
                queue.append(nxt)
    return dist


def carve_core(out: OutEdges, core_ids: list[int], rng: random.Random, cap: int) -> None:
    """Interlink the Core Space (a ring + a few chords) so it is well-connected.

    Done before the rest is clustered, so the core sectors keep spare degree for
    the cluster bridges and the guaranteed exit (DESIGN §5 step 4).
    """
    n = len(core_ids)
    for i in range(n):
        add_bidirectional(out, core_ids[i], core_ids[(i + 1) % n], cap)
    for _ in range(n):  # a handful of chords for redundancy
        a, b = rng.sample(core_ids, 2)
        add_bidirectional(out, a, b, cap)


def add_ring_motifs(out: OutEdges, groups: list[list[int]], rng: random.Random,
                    cap: int, count: int) -> None:
    """A light, purely-additive motif pass: a few extra intra-group ring edges.

    Additive only (never removes edges), so connectivity is preserved. Tunnels
    and deadends are deferred to a later phase (DESIGN §5 step 3)."""
    eligible = [g for g in groups if len(g) >= 3]
    for _ in range(count):
        if not eligible:
            return
        group = rng.choice(eligible)
        a, b = rng.sample(group, 2)
        add_bidirectional(out, a, b, cap)


def band_for_hops(hops: int, bands: list[DistanceBand]) -> str:
    """The band name whose [min_hops, max_hops] contains `hops`."""
    for band in bands:
        if band.min_hops <= hops <= band.max_hops:
            return band.name
    return bands[-1].name  # beyond the configured range -> outermost band


def compute_bands(out: OutEdges, src: int, bands: list[DistanceBand]) -> dict[int, str]:
    """Assign every reachable sector its distance band (DESIGN §5 step 5)."""
    return {sec: band_for_hops(hops, bands) for sec, hops in bfs_distances(out, src).items()}
