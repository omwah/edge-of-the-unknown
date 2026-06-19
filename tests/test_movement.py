"""WP3 — movement helpers: warp legality and pathfinding (DESIGN §9).

WP14 extends this with the route describers `plan_route` / `plan_route_legs`.
"""

from __future__ import annotations

from edge.core.movement import (
    can_warp,
    plan_route,
    plan_route_legs,
    shortest_path,
    warp_targets,
)

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


# --- WP14: plan_route / plan_route_legs ---


def test_plan_route_hops_cost_and_one_way() -> None:
    plan = plan_route(ADJ, 1, 4, allowed=None, turns_per_warp=2)
    assert plan.reachable
    assert [h.sector_id for h in plan.hops] == [2, 3, 4]
    assert plan.turn_cost == 3 * 2  # hops * turns_per_warp
    # 2->3 is one-way (no 3->2 edge); 1->2 and 3->4 are two-way.
    assert [h.one_way for h in plan.hops] == [False, True, False]


def test_plan_route_same_sector_is_empty() -> None:
    plan = plan_route(ADJ, 2, 2, allowed=None, turns_per_warp=2)
    assert plan.reachable
    assert plan.hops == ()
    assert plan.turn_cost == 0


def test_plan_route_unreachable_when_fogged() -> None:
    # 3 not uncovered: no route 1->4 within `allowed`.
    plan = plan_route(ADJ, 1, 4, allowed={1, 2, 4}, turns_per_warp=2)
    assert not plan.reachable
    assert plan.hops == ()
    assert plan.turn_cost == 0


def test_plan_route_legs_concatenates() -> None:
    # you(1) -> 3 -> 1: leg one is [2, 3]; leg two is unreachable (3 can't reach 1).
    plan = plan_route_legs(ADJ, 1, [3, 1], allowed=None, turns_per_warp=1)
    assert not plan.reachable  # fails closed on the unreachable return leg
    assert plan.hops == ()

    # you(1) -> 3 -> 4: both legs reachable; hops concatenate.
    plan2 = plan_route_legs(ADJ, 1, [3, 4], allowed=None, turns_per_warp=1)
    assert plan2.reachable
    assert [h.sector_id for h in plan2.hops] == [2, 3, 4]
    assert plan2.dst == 4
    assert plan2.turn_cost == 3


def test_plan_route_is_a_valid_walk() -> None:
    plan = plan_route(ADJ, 1, 4, allowed=None, turns_per_warp=1)
    walk = [plan.src, *(h.sector_id for h in plan.hops)]
    for a, b in zip(walk, walk[1:], strict=False):
        assert b in ADJ.get(a, ())  # every step is a real warp edge
