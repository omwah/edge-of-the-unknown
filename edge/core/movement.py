"""Movement: warp legality, turn costs, and pathfinding (DESIGN §9).

Pure helpers over the warp graph. Warps are directional (one-way bridges are
possible, §5), so adjacency and pathfinding respect direction. Turn costs follow
TWINSTR.DOC: a warp costs the ship's `turns_per_warp`, docking costs 1 (§9).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping

Adjacency = Mapping[int, tuple[int, ...]]


class MovementError(Exception):
    """An illegal move (no such warp, or out of turns)."""


def warp_targets(adjacency: Adjacency, sector_id: int) -> tuple[int, ...]:
    """The sectors reachable in one hop from `sector_id`."""
    return adjacency.get(sector_id, ())


def can_warp(adjacency: Adjacency, from_sector: int, to_sector: int) -> bool:
    """Whether a single direct warp `from_sector -> to_sector` is legal."""
    return to_sector in warp_targets(adjacency, from_sector)


def shortest_path(
    adjacency: Adjacency, src: int, dst: int, allowed: set[int] | None = None
) -> list[int] | None:
    """Fewest-hop path from `src` to `dst` (inclusive), or None if unreachable.

    BFS over the directional graph — the route planner's primitive (§11). Returns
    `[src]` when `src == dst`. When `allowed` is given, the path may only traverse
    sectors in that set (`src` excepted) — the route-lock used by multi-hop travel,
    so the player can only `TravelTo` a destination whose route they've uncovered.
    """
    if src == dst:
        return [src]

    def passable(node: int) -> bool:
        return allowed is None or node in allowed

    if not passable(dst):
        return None
    prev: dict[int, int] = {src: src}
    queue: deque[int] = deque([src])
    while queue:
        current = queue.popleft()
        for nxt in adjacency.get(current, ()):
            if nxt in prev or not passable(nxt):
                continue
            prev[nxt] = current
            if nxt == dst:
                path = [dst]
                while path[-1] != src:
                    path.append(prev[path[-1]])
                path.reverse()
                return path
            queue.append(nxt)
    return None
