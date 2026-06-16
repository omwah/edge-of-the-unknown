"""WP3 — movement helpers: warp legality and pathfinding (DESIGN §9)."""

from __future__ import annotations

from edge.core.movement import can_warp, shortest_path, warp_targets

# A small directional graph: 1<->2, 2->3 (one-way), 3<->4.
ADJ: dict[int, tuple[int, ...]] = {
    1: (2,),
    2: (1, 3),
    3: (4,),
    4: (3,),
}


def test_warp_targets_and_legality() -> None:
    assert warp_targets(ADJ, 2) == (1, 3)
    assert can_warp(ADJ, 1, 2)
    assert not can_warp(ADJ, 1, 3)  # no direct edge
    assert not can_warp(ADJ, 9, 1)  # unknown sector


def test_shortest_path_respects_direction() -> None:
    assert shortest_path(ADJ, 1, 4) == [1, 2, 3, 4]
    assert shortest_path(ADJ, 1, 1) == [1]
    # 3->2 does not exist (2->3 is one-way), so 4 cannot reach 1.
    assert shortest_path(ADJ, 4, 1) is None


def test_shortest_path_route_lock() -> None:
    # The full graph is reachable; an `allowed` set restricts which sectors a path
    # may traverse (the route-lock used by multi-hop travel, WP-C).
    assert shortest_path(ADJ, 1, 4, allowed={1, 2, 3, 4}) == [1, 2, 3, 4]
    assert shortest_path(ADJ, 1, 4, allowed={1, 2, 4}) is None  # 3 not uncovered
    assert shortest_path(ADJ, 1, 3, allowed={1, 2}) is None  # destination not uncovered
    assert shortest_path(ADJ, 1, 1, allowed=set()) == [1]  # src is always reachable
