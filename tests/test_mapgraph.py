"""Local sector ego-graph layout (edge/server/mapgraph) — pure, deterministic."""

from __future__ import annotations

import re

from edge.core.models import Game, Planet, Player, Sector, Ship, UniverseState
from edge.server import mapgraph


def _strip(markup: str) -> str:
    return re.sub(r"\[/?[^\]]*\]", "", markup)


# Glyphs whose strokes reach a horizontal neighbour (mirror of mapgraph's arms), used
# to tell a real drawn line from two connectors that merely abut.
_RIGHT_ARM = set("─╭╰")
_LEFT_ARM = set("─╮╯")


def _phantom_bridges(state: UniverseState, player: Player, here: int,
                     max_width: int) -> list[tuple[int, int]]:
    """Pairs of *non-adjacent* sectors joined on one row by an unbroken, arm-connected
    run of connector glyphs — i.e. a line that visually reads as a warp but is not one.
    """
    rows, _legend, nodes = mapgraph.build_local_map(state, player, max_width=max_width)
    grid = [_strip(r).ljust(400) for r in rows]
    labels: dict[int, list[tuple[int, int, int]]] = {}
    for n in nodes:
        labels.setdefault(n.row, []).append((n.col0, n.col1, n.sector_id))
    for y, r in enumerate(grid):  # `here` is not in `nodes`; find it by its @-marked id
        for m in re.finditer(r"\(\d+@\)", r):
            labels.setdefault(y, []).append((m.start(), m.end(), here))
    found: list[tuple[int, int]] = []
    for _row, items in sorted(labels.items()):
        items.sort()
        for (_a0, a1, asid), (b0, _b1, bsid) in zip(items, items[1:]):
            adjacent = (bsid in state.adjacency.get(asid, ())
                        or asid in state.adjacency.get(bsid, ()))
            if adjacent or b0 <= a1:
                continue
            row = grid[_row]
            if any(row[x] == " " for x in range(a1, b0)):
                continue  # a blank breaks the run — reads as separate
            chain = row[a1] in (_LEFT_ARM | _RIGHT_ARM) and all(
                row[x - 1] in _RIGHT_ARM and row[x] in _LEFT_ARM for x in range(a1 + 1, b0)
            ) and row[b0 - 1] in _RIGHT_ARM
            if chain:
                found.append((asid, bsid))
    return found


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


def test_fit_to_width_grows_reach_to_fill_the_screen() -> None:
    # Sectors 4 and 6 sit two hops out (offset +2) — only a reach ≥ 2 includes them.
    state = _world(explored=frozenset({1, 2, 3, 4, 5, 6}))
    wide = _rows(state, max_width=1000)
    assert "(204)" in wide and "(206)" in wide  # a wide screen pulls in the far ring
    assert "(102@)" in wide                      # still centered on you


def test_fit_to_width_falls_back_to_reach_one_when_narrow() -> None:
    # A width too small even for the immediate ring still shows it (reach never < 1),
    # but never reaches the two-hop sectors.
    state = _world(explored=frozenset({1, 2, 3, 4, 5, 6}))
    narrow = _rows(state, max_width=8)
    assert "(105)" in narrow      # the 1-hop neighbour is present
    assert "(204)" not in narrow  # the 2-hop sector is not (reach clamped to 1)


def test_content_codes_are_painted_in_legend_colours() -> None:
    # A planet sits in the Hub sector 5 (band tint cyan). The `(id)` keeps the band
    # tint, but the `@` content code is recoloured to its legend colour (green), so a
    # node reads its contents in the same palette as the legend (PT-50).
    state = _world(explored=frozenset({1, 2, 3, 5}))
    state.planets = {1: Planet(id=1, sector_id=5, name="Aur", planet_type="barren")}
    blob = _rows(state, max_width=200)
    assert "[cyan](105)" in blob  # the id keeps the Hub band tint
    assert "[green]@" in blob     # the planet code is painted its legend green, not cyan


def _one_way_span_world() -> UniverseState:
    """A world reproducing the PT-56 phantom: a **one-way** warp Z→A joins two sectors
    three gravity columns apart, so its long line runs straight along the center row —
    past the intervening node M (sector 4). M's own warps are **vertical** (to N1/N2 in
    its own column) plus a real link to the player's sector, so its horizontal borders
    carry no real edge and the foreign line reads as a warp *through* it. All labels are
    six characters wide, so no label padding hides the bridge from the detector.

    Columns (core_hops − here_core): A −3 · {N1,M,N2} −1 · here 0 · Z +1.
    """
    state = UniverseState.new(Game(id=1, seed=1, config_version=1, created_at="t"))
    state.sectors = {
        1: Sector(id=1, region_id=1, warps_out=(), distance_band="Hub"),  # A: one-way sink
        4: Sector(id=4, region_id=1, warps_out=(5, 7, 8), distance_band="Frontier"),  # M
        5: Sector(id=5, region_id=1, warps_out=(4, 6), distance_band="Frontier"),  # here
        6: Sector(id=6, region_id=1, warps_out=(5, 1), distance_band="Deep"),  # Z → A (one-way)
        7: Sector(id=7, region_id=1, warps_out=(4,), distance_band="Frontier"),  # N1 (M's column)
        8: Sector(id=8, region_id=1, warps_out=(4,), distance_band="Frontier"),  # N2 (M's column)
    }
    state.rebuild_adjacency()
    state.core_hops = {1: 0, 4: 2, 5: 3, 6: 4, 7: 2, 8: 2}
    state.spatial_ids = {1: 1010, 4: 7040, 5: 305, 6: 4060, 7: 7010, 8: 7080}
    state.ships = {1: Ship(id=1, type_id="t", name="S", owner_player_id=1, sector_id=5,
                           holds_total=10, turns_per_warp=1)}
    state.players = {1: Player(id=1, name="you", ship_id=1, latinum=0, turns_remaining=99,
                               explored_sectors=frozenset(state.sectors), entered_from={5: 6})}
    return state


def test_a_one_way_long_span_warp_does_not_bridge_the_node_it_passes() -> None:
    # PT-56 regression. Without the sever this bridges sector 1010 to the non-adjacent
    # 7040 (a straight line through 7040's row); the sever erases the foreign connector
    # at 7040's border, so no non-adjacent pair reads as a warp.
    state = _one_way_span_world()
    player = state.players[1]
    for width in (60, 80, 120):
        assert _phantom_bridges(state, player, here=5, max_width=width) == []


def test_the_sever_leaves_real_edges_intact() -> None:
    # The pass-through node keeps its genuine warps — the vertical links to its column
    # neighbours survive, so the fix removes only the foreign line, never a real edge.
    state = _one_way_span_world()
    rows, _legend, _nodes = mapgraph.build_local_map(state, state.players[1], max_width=80)
    assert any("│" in _strip(r) for r in rows)  # 7040's real vertical warps still drawn


def test_fit_to_width_never_exceeds_the_budget() -> None:
    # Budgets at/above the immediate ring's width: the fit never lays out wider than
    # asked (a narrower budget than even reach 1 is the separate fallback case above).
    state = _world(explored=frozenset({1, 2, 3, 4, 5, 6}))
    for budget in (30, 40, 60, 100):
        rows, _legend, _nodes = mapgraph.build_local_map(
            state, state.players[1], max_width=budget)
        assert max(len(_strip(r)) for r in rows) <= budget
