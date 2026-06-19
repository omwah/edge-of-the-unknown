"""Movement: warp legality, turn costs, and pathfinding (DESIGN §9).

Pure helpers over the warp graph. Warps are directional (one-way bridges are
possible, §5), so adjacency and pathfinding respect direction. Turn costs follow
TWINSTR.DOC: a warp costs the ship's `turns_per_warp`, docking costs 1 (§9).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

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


@dataclass(frozen=True)
class RouteHop:
    """One traversed sector on a planned route (excludes the origin)."""

    sector_id: int  # internal id
    one_way: bool  # reverse edge absent — the return leg differs


@dataclass(frozen=True)
class RoutePlan:
    """A costed, annotated plan over the warp graph (§11, the route planner)."""

    src: int
    dst: int
    hops: tuple[RouteHop, ...]  # excludes src; empty iff src == dst
    reachable: bool  # a route exists within `allowed`
    turn_cost: int  # len(hops) * turns_per_warp


def _annotate(
    adjacency: Adjacency, path: Sequence[int], turns_per_warp: int
) -> RoutePlan:
    """Turn a sector walk (incl. src) into a costed, one-way-flagged plan."""
    src, dst = path[0], path[-1]
    hops: list[RouteHop] = []
    for prev, node in zip(path, path[1:], strict=False):
        # `prev -> node` was traversed; one-way iff the reverse edge is absent.
        one_way = prev not in adjacency.get(node, ())
        hops.append(RouteHop(sector_id=node, one_way=one_way))
    return RoutePlan(
        src=src,
        dst=dst,
        hops=tuple(hops),
        reachable=True,
        turn_cost=len(hops) * turns_per_warp,
    )


def plan_route(
    adjacency: Adjacency,
    src: int,
    dst: int,
    *,
    allowed: set[int] | None,
    turns_per_warp: int,
) -> RoutePlan:
    """Describe the fewest-hop route `src -> dst` as a costed, annotated plan.

    Composes `shortest_path` (so it honours the directional graph and the
    `allowed` route-lock) with a per-hop annotation: each hop's `one_way` flag
    records whether the reverse edge is absent (no direct way back). An
    unreachable destination yields `reachable=False` with no hops; `src == dst`
    yields an empty, zero-cost plan. Pure — no I/O (§11, mirrors `shortest_path`).
    """
    path = shortest_path(adjacency, src, dst, allowed)
    if path is None:
        return RoutePlan(src=src, dst=dst, hops=(), reachable=False, turn_cost=0)
    return _annotate(adjacency, path, turns_per_warp)


def plan_route_legs(
    adjacency: Adjacency,
    src: int,
    waypoints: Sequence[int],
    *,
    allowed: set[int] | None,
    turns_per_warp: int,
) -> RoutePlan:
    """Chain `plan_route` across `[src, *waypoints]` and concatenate the legs.

    For the Trade tie-in's `you -> buy-port -> sell-port` round trip: each leg is
    independently route-locked, and the first unreachable leg makes the whole plan
    `reachable=False` (fails closed). The returned plan's `dst` is the final
    waypoint; its hops are every leg's hops in order.
    """
    hops: list[RouteHop] = []
    current = src
    for waypoint in waypoints:
        leg = plan_route(
            adjacency, current, waypoint, allowed=allowed, turns_per_warp=turns_per_warp
        )
        if not leg.reachable:
            dst = waypoints[-1] if waypoints else src
            return RoutePlan(src=src, dst=dst, hops=(), reachable=False, turn_cost=0)
        hops.extend(leg.hops)
        current = waypoint
    return RoutePlan(
        src=src,
        dst=current,
        hops=tuple(hops),
        reachable=True,
        turn_cost=len(hops) * turns_per_warp,
    )
