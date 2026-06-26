"""Local sector ego-graph layout (edge/server/mapgraph) — pure, deterministic."""

from __future__ import annotations

import re

from edge.core.models import Game, Player, Sector, Ship, UniverseState
from edge.server import mapgraph


def _strip(markup: str) -> str:
    return re.sub(r"\[/?[^\]]*\]", "", markup)


def _world(*, explored: frozenset[int], here: int = 2) -> UniverseState:
    """A small branching universe:  1 - 2 - 3 - 4  with a 2 - 5 - 6 spur.

    Core hops: 1=0, 2=1, 3=2, 4=3, 5=2, 6=3 (so sector 1 sits toward the Core of
    the player's sector 2, and 3/4/5/6 sit deeper).
    """
    state = UniverseState.new(Game(id=1, seed=1, config_version=1, created_at="t"))
    state.sectors = {
        1: Sector(id=1, region_id=1, warps_out=(2,), distance_band="Hub"),
        2: Sector(id=2, region_id=1, warps_out=(1, 3, 5), distance_band="Hub"),
        3: Sector(id=3, region_id=1, warps_out=(2, 4), distance_band="Frontier"),
        4: Sector(id=4, region_id=1, warps_out=(3,), distance_band="Frontier"),
        5: Sector(id=5, region_id=1, warps_out=(2, 6), distance_band="Hub"),
        6: Sector(id=6, region_id=1, warps_out=(5,), distance_band="Frontier"),
    }
    state.rebuild_adjacency()
    state.core_hops = {1: 0, 2: 1, 3: 2, 4: 3, 5: 2, 6: 3}
    state.spatial_ids = {1: 101, 2: 102, 3: 203, 4: 204, 5: 105, 6: 206}
    state.ships = {1: Ship(id=1, type_id="t", name="S", owner_player_id=1, sector_id=here,
                           holds_total=10, turns_per_warp=1)}
    state.players = {1: Player(id=1, name="you", ship_id=1, latinum=0, turns_remaining=99,
                               explored_sectors=explored, entered_from={2: 1})}
    return state


def _rows(state: UniverseState, **kw: object) -> str:
    rows, _legend, _nodes = mapgraph.build_local_map(state, state.players[1], **kw)  # type: ignore[arg-type]
    return "\n".join(rows)


def test_current_sector_is_centered_with_gravity_order() -> None:
    state = _world(explored=frozenset({1, 2, 3, 5}))
    blob = _rows(state)
    assert "(102@)" in blob  # the player's sector, highlighted
    # On the row carrying both, the toward-Core neighbour (101) sits left of you.
    center = next(line for line in blob.splitlines() if "(102@)" in line)
    assert "(101)" in center and center.index("(101)") < center.index("(102@)")


def test_unexplored_neighbours_show_their_id_faintly() -> None:
    # Sector 5 is an immediate (1-hop) neighbour but unexplored. Like the warp list,
    # its spatial id is shown (only its contents stay fogged) and it renders faint.
    state = _world(explored=frozenset({1, 2, 3}))
    blob = _rows(state)
    assert "(203)" in blob       # explored neighbour (sector 3) shows its id
    assert "[dim](105)" in blob  # unexplored neighbour shows its id, faintly


def test_deep_fog_beyond_the_immediate_ring_is_pruned() -> None:
    # Only the immediate ring shows unexplored sectors; charted-only beyond it keeps
    # the deep fog from swarming the map. Sector 6 (2 hops, unexplored) is dropped.
    explored = frozenset({1, 2, 3, 5})  # 5 explored, so its unexplored neighbour 6 is 2 hops
    blob = _rows(_world(explored=explored))
    assert "(105)" in blob       # explored 1-hop neighbour present
    assert "(206)" not in blob   # sector 6 (deep, uncharted) is pruned, not shown


def test_route_overlay_highlights_and_off_map_pointer() -> None:
    state = _world(explored=frozenset({1, 2, 3, 4, 5, 6}))
    # A route to an in-view sector lights the path in the route highlight.
    on_map = _rows(state, route=[2, 3])
    assert "bold yellow" in on_map
    # A destination beyond the local radius gets a directional pointer instead.
    far = _rows(state, route=[2, 3, 4, 99])  # 99 is off the local map
    assert "→ S99" in far


def test_one_way_warp_is_drawn_faintly() -> None:
    # Sever 4's return edge so 3 → 4 is one-way; the connector renders dim.
    state = _world(explored=frozenset({1, 2, 3, 4, 5}))
    state.sectors[4] = Sector(id=4, region_id=1, warps_out=(), distance_band="Frontier")
    state.rebuild_adjacency()
    assert "[dim]" in _rows(state)  # the one-way 3→4 connector is faint


def test_nodes_expose_clickable_boxes_excluding_current() -> None:
    state = _world(explored=frozenset({1, 2, 3, 5}))
    rows, _legend, nodes = mapgraph.build_local_map(state, state.players[1])
    here = state.ships[1].sector_id
    assert nodes and all(n.sector_id != here for n in nodes)  # you aren't a route target
    for n in nodes:
        cell = _strip(rows[n.row])[n.col0:n.col1]  # the box frames exactly this label
        assert cell.startswith(f"({n.display_id}")


def test_layout_is_deterministic() -> None:
    a = _world(explored=frozenset({1, 2, 3, 5}))
    b = _world(explored=frozenset({1, 2, 3, 5}))
    assert _rows(a) == _rows(b)
