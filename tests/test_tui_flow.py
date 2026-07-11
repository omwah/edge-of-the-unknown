"""WP8/WP9 — Textual Pilot flow over the live service (DESIGN §13).

Drives the real app: new game, navigate to the StarDock, dock, trade, and buy
the first upgrade — asserting the underlying game state changes through the UI.
Navigation between sectors is done via the service (clicking each warp button is
fiddly); the dock/trade/upgrade interactions are exercised through the UI.
"""

from __future__ import annotations

from edge.core.movement import shortest_path
from edge.core.rules import Warp
from edge.tui.app import EdgeApp
from edge.tui.screens.computer import ComputerScreen
from edge.tui.screens.stardock import StarDockScreen
from edge.tui.screens.travel import TravelPromptScreen
from edge.tui.widgets import NavRose


async def _warp_player_to(svc: object, target: int) -> None:
    """Warp the player from wherever they are to `target` along the shortest path."""
    start = svc.game_view(1).sector.sector_id  # type: ignore[attr-defined]
    path = shortest_path(svc.state.adjacency, start, target)  # type: ignore[attr-defined]
    assert path is not None
    for hop in path[1:]:
        svc.apply(1, Warp(to_sector=hop))  # type: ignore[attr-defined]


async def _new_game_at_stardock(app: EdgeApp, pilot: object) -> object:
    """Press New game, then make sure the player is at the StarDock and dock (press P).

    The default config starts the player *at* the StarDock, so the warp is usually a
    no-op; it still resolves for configs that start the player elsewhere.
    """
    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    svc = app.service
    assert svc is not None
    dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)
    await _warp_player_to(svc, dock.sector_id)
    await pilot.press("p")  # dock -> StarDockScreen  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    return svc


async def test_new_game_pushes_live_game_screen() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert app.service is not None
        view = app.service.game_view(1)
        # The default config starts the player at the StarDock.
        dock = next(p for p in app.service.state.ports.values() if p.klass.value == 9)
        assert view.sector.sector_id == dock.sector_id and view.turns == 250


async def test_nav_rose_click_warps() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        start = svc.game_view(1).sector.sector_id
        rose = app.screen.query_one(NavRose)
        assert rose._hits
        node = rose._hits[0]
        target = node.sector_id
        compass = rose.query_one("#rose-compass")
        await pilot.click(compass, offset=(node.col0, node.row))
        await pilot.pause()
        moved = svc.game_view(1).sector.sector_id
        assert moved == target != start


async def test_enter_warps_selected_node() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        start = svc.game_view(1).sector.sector_id
        # The nav rose auto-focuses; Enter warps to its selected neighbour.
        assert isinstance(app.focused, NavRose)
        rose = app.focused
        target = rose._hits[rose._idx].sector_id
        await pilot.press("enter")
        await pilot.pause()
        moved = svc.game_view(1).sector.sector_id
        assert moved == target != start


async def test_nav_rose_focuses_the_return_warp_after_travel() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        start = svc.game_view(1).sector.sector_id
        rose = app.screen.query_one(NavRose)
        target = rose._hits[rose._idx].sector_id
        await pilot.press("enter")
        await pilot.pause()
        assert svc.game_view(1).sector.sector_id == target
        rose = app.screen.query_one(NavRose)
        selected = rose._hits[rose._idx].sector_id
        assert selected == start
        assert rose._warps[selected].kind == "backtrack"
        # A second hop (back to the origin) re-homes on the sector just left again;
        # selection follows the latest movement rather than a stale first route.
        await pilot.press("enter")
        await pilot.pause()
        rose = app.screen.query_one(NavRose)
        selected = rose._hits[rose._idx].sector_id
        assert svc.game_view(1).sector.sector_id == start
        assert selected == target
        assert rose._warps[selected].kind == "backtrack"


async def test_wormhole_art_is_clickable_and_warps() -> None:
    """A wormhole sector renders clickable discovery art whose hotspot warps to the
    far side of the one-way edge (§7)."""
    from dataclasses import replace

    from edge.core.enums import DiscoveryKind
    from edge.core.movement import one_way_exits
    from edge.tui.widgets import ClickableEntry, SectorScene

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        wh = next((d for d in svc.state.discoveries.values()
                   if d.kind is DiscoveryKind.WORMHOLE), None)
        assert wh is not None  # the default universe has at least one one-way edge
        exit_sector = one_way_exits(svc.state.adjacency, wh.sector_id)[0]

        # Drop the player onto the wormhole sector and rebuild the view.
        svc.state.ships[1] = replace(svc.state.ships[1], sector_id=wh.sector_id)
        await app.screen.recompose()
        await pilot.pause()

        scene = app.screen.query_one(SectorScene)
        scene.render()  # populates _hotspots
        hot = [h for h in scene._hotspots if h[4] == "wormhole"]
        assert hot and hot[0][5] == exit_sector

        # Clicking the wormhole art warps to the far side of the one-way edge.
        await app.screen.on_clickable_entry_picked(
            ClickableEntry.Picked("wormhole", exit_sector))
        await pilot.pause()
        assert svc.game_view(1).sector.sector_id == exit_sector
        # The source is not an outbound neighbour at a real one-way arrival, so
        # backtrack-default focus safely falls back to the first available warp.
        rose = app.screen.query_one(NavRose)
        assert all(w.kind != "backtrack" for w in rose._warps.values())
        assert rose._idx == 0


async def test_log_hotkey_opens_computer_log() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("g")  # Log -> Computer (log tab), folded in (WP-B)
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)
        from textual.widgets import DataTable

        # The Computer opens on the log tab (empty at a fresh game — the beacon is gone).
        assert app.screen.query_one("#log-table", DataTable) is not None


async def test_computer_market_tab_shows_the_order_book() -> None:
    """WP48: the Computer's Market tab renders (fog-respecting) without error."""
    from textual.widgets import DataTable

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("c")  # open the Computer
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)
        app.screen.show_subview("market")
        await pilot.pause()
        table = app.screen.query_one("#market-table", DataTable)
        assert table is not None
        if table.display:  # orders charted — rows render
            assert table.row_count >= 1
        else:  # WP-UI19: an empty book shows the shared EmptyState instead
            from edge.tui.chrome import EmptyState
            assert app.screen.query_one("#market").query(EmptyState)


async def test_travel_prompt_warps_along_known_route() -> None:
    from textual.widgets import Input

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        # Uncover a neighbour with a two-way edge, then travel back to the start sector.
        start = svc.game_view(1).sector.sector_id
        a = next(s for s in svc.state.sectors[start].warps_out
                 if start in svc.state.sectors[s].warps_out)
        svc.apply(1, Warp(to_sector=a))
        await pilot.press("w")  # open the travel prompt (WP-C)
        await pilot.pause()
        assert isinstance(app.screen, TravelPromptScreen)
        # The prompt takes a *spatial* display id (§5.1) — type the start sector's id.
        app.screen.query_one("#field-input", Input).value = str(svc.state.spatial_ids[start])
        await pilot.press("enter")
        await pilot.pause()
        assert svc.game_view(1).sector.sector_id == start


async def test_sector_title_shows_spatial_id() -> None:
    """The game screen renders the sector's spatial display id, not the internal id (§5.1)."""
    from edge.tui.widgets import SectorScene

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        start = svc.game_view(1).sector.sector_id  # the player's start sector (the StarDock)
        spatial = svc.state.spatial_ids[start]
        assert spatial != start  # the spatial id genuinely differs from the internal id
        title = app.screen.query_one(SectorScene).render().plain
        assert f"[{spatial}]" in title


async def test_arrow_keys_move_nav_rose_selection_by_layout() -> None:
    """Arrow keys move the nav rose's selection to the nearest warp *on screen*, not by
    insertion order: from the top-left home node, Right lands on a node to its right and
    Down on one below it.

    The rose auto-focuses on the fresh game screen (no priming Tab).
    """
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()

        rose = app.screen.query_one(NavRose)
        assert isinstance(app.focused, NavRose)
        if len(rose._hits) < 2:
            return  # a lone-exit sector has nothing to move to

        home = rose._hits[0]  # top-left by (row, col0)
        hx = (home.col0 + home.col1) / 2
        assert rose._idx == 0

        await pilot.press("right")
        await pilot.pause()
        if rose._idx != 0:  # a node lies to the right → the selection moved rightward
            sel = rose._hits[rose._idx]
            assert (sel.col0 + sel.col1) / 2 > hx

        rose._idx = 0
        rose.refresh()
        await pilot.press("down")
        await pilot.pause()
        if rose._idx != 0:  # a node lies below → the selection moved downward
            assert rose._hits[rose._idx].row > home.row

        # The home node is top-left, so at least one of Right/Down must find a neighbour.
        rose._idx = 0
        await pilot.press("right")
        await pilot.pause()
        if rose._idx == 0:
            await pilot.press("down")
            await pilot.pause()
        assert rose._idx != 0


def test_nearest_node_moves_by_screen_layout() -> None:
    """The shared arrow-nav helper picks the nearest node in the pressed direction."""
    from edge.core.dto import MapNodeDTO

    from edge.tui.widgets import _nearest_node

    nodes = [
        MapNodeDTO(sector_id=1, display_id=1, row=0, col0=0, col1=3),    # top-left
        MapNodeDTO(sector_id=2, display_id=2, row=0, col0=10, col1=13),  # top-right
        MapNodeDTO(sector_id=3, display_id=3, row=4, col0=0, col1=3),    # bottom-left
    ]
    assert _nearest_node(nodes, 0, 1, 0) == 1     # right from top-left → top-right
    assert _nearest_node(nodes, 0, 0, 1) == 2     # down  from top-left → bottom-left
    assert _nearest_node(nodes, 0, -1, 0) is None  # nothing to the left of top-left
    assert _nearest_node(nodes, 0, 0, -1) is None  # nothing above the top row
    assert _nearest_node(nodes, 1, -1, 0) == 0    # left  from top-right → top-left
    assert _nearest_node(nodes, 2, 0, -1) == 0    # up    from bottom-left → top-left (nearest across)

    # In-beam (same-column) wins over an off-column sector: pressing Up prefers the sector
    # whose column overlaps (row 0) over a nearer one (row 2) that sits off to the side.
    aligned = [
        MapNodeDTO(sector_id=1, display_id=1, row=4, col0=10, col1=13),  # 0: current
        MapNodeDTO(sector_id=2, display_id=2, row=2, col0=0, col1=3),    # 1: nearer row, off-column
        MapNodeDTO(sector_id=3, display_id=3, row=0, col0=10, col1=13),  # 2: same column, farther row
    ]
    assert _nearest_node(aligned, 0, 0, -1) == 2  # Up → the in-beam sector, not the off-column one
    assert _nearest_node(aligned, 0, -1, 0) == 1  # Left → the only sector to the left

    # Don't skip an intervening aligned sector: Up steps to the NEAREST in-beam sector,
    # not a farther one that is also in the column.
    stacked = [
        MapNodeDTO(sector_id=1, display_id=1, row=6, col0=5, col1=8),  # 0: current
        MapNodeDTO(sector_id=2, display_id=2, row=4, col0=5, col1=8),  # 1: same column, nearer
        MapNodeDTO(sector_id=3, display_id=3, row=0, col0=5, col1=8),  # 2: same column, farther
    ]
    assert _nearest_node(stacked, 0, 0, -1) == 1  # the nearest above, not the farther aligned one

    # The reported bug: a sector *just above* (columns overlap) is chosen over a farther one
    # in the column that merely happens to be perfectly centre-aligned.
    just_above = [
        MapNodeDTO(sector_id=1, display_id=1, row=6, col0=5, col1=9),   # 0: current (centre 7)
        MapNodeDTO(sector_id=2, display_id=2, row=4, col0=6, col1=10),  # 1: just above, overlaps (centre 8)
        MapNodeDTO(sector_id=3, display_id=3, row=0, col0=5, col1=9),   # 2: far above, centred (centre 7)
    ]
    assert _nearest_node(just_above, 0, 0, -1) == 1  # the near overlapping sector, not the far centred one


def test_nearest_node_horizontal_steps_to_adjacent_column() -> None:
    """Left/Right steps to the nearest adjacent *column*, row-nearest, not a far same-row node.

    Reproduces the reported bugs against a slice of the local-map layout: a straight
    up/down neighbour (its column overlaps) must never count as left/right, and a node
    that merely shares a row across the map must not beat the adjacent column.
    """
    from edge.core.dto import MapNodeDTO

    from edge.tui.widgets import _nearest_node

    # Two gravity columns left-aligned to fixed x (col A at 0, col B at 14), with a
    # stacked node directly above the cursor in its own column (col C at 28).
    #   colA: (r2) up-left        colC-above: (r0) straight up
    #   cursor (r4, colC)         colB: (r4) far right, same row
    #   colA: (r6) down-left
    nodes = [
        MapNodeDTO(sector_id=10, display_id=10, row=4, col0=28, col1=35),  # 0: cursor (col C)
        MapNodeDTO(sector_id=11, display_id=11, row=0, col0=28, col1=36),  # 1: straight up (col C)
        MapNodeDTO(sector_id=12, display_id=12, row=2, col0=14, col1=22),  # 2: up-left (col B)
        MapNodeDTO(sector_id=13, display_id=13, row=6, col0=14, col1=21),  # 3: down-left (col B)
        MapNodeDTO(sector_id=14, display_id=14, row=4, col0=42, col1=51),  # 4: right, adjacent col
        MapNodeDTO(sector_id=15, display_id=15, row=4, col0=200, col1=207),  # 5: far right, same row
    ]
    # Left must not grab the straight-up/down same-column node; it steps to col B, and
    # among col B picks the row-nearest (up-left over down-left is a tie broken by "up").
    assert _nearest_node(nodes, 0, -1, 0) == 2   # left → up-left (nearer/upper), not node 1
    # Right steps to the *adjacent* column, never the far same-row node across the map.
    assert _nearest_node(nodes, 0, 1, 0) == 4    # right → adjacent col, not the far same-row 5


def test_nearest_node_tie_prefers_warp_linked_then_upper() -> None:
    """On an exact column/row-distance tie, the warp-linked candidate wins; else the upper."""
    from edge.core.dto import MapNodeDTO

    from edge.tui.widgets import _nearest_node

    # Cursor at (r4) with an equidistant pair one row up and one row down in the next column.
    up = MapNodeDTO(sector_id=2, display_id=2, row=3, col0=14, col1=21)
    down = MapNodeDTO(sector_id=3, display_id=3, row=5, col0=14, col1=21)
    cursor_plain = MapNodeDTO(sector_id=1, display_id=1, row=4, col0=0, col1=7)
    assert _nearest_node([cursor_plain, up, down], 0, 1, 0) == 1  # tie → prefer upper (index 1)

    # Same geometry, but the cursor warps to the *lower* node — the link wins over "up".
    cursor_linked = MapNodeDTO(sector_id=1, display_id=1, row=4, col0=0, col1=7,
                               neighbors=frozenset({3}))
    assert _nearest_node([cursor_linked, up, down], 0, 1, 0) == 2  # linked lower node (index 2)


async def test_selected_nav_node_inverts_only_its_cell() -> None:
    """The selected warp highlights just its baked compass cell (reverse), not the whole line."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()

        rose = app.screen.query_one(NavRose)
        assert isinstance(app.focused, NavRose)
        node = rose._hits[rose._idx]
        text = rose.query_one("#rose-compass").render()
        reversed_spans = [s for s in text.spans if s.style and "reverse" in str(s.style)]
        # Exactly the focused node's cell is inverted: its span width matches the
        # node's baked label box, well short of the whole rendered rose.
        node_width = node.col1 - node.col0
        assert any(s.end - s.start == node_width for s in reversed_spans)
        assert max(s.end for s in reversed_spans) < len(text.plain)


def test_route_confirmation_summarizes_course_without_replanning() -> None:
    """WP-UI13 confirmation exposes all decision inputs already present in the DTO."""
    from edge.core.dto import RouteDTO, RouteHopDTO
    from edge.tui.screens.computer import ComputerScreen

    route = RouteDTO(
        origin_display=101, dest_display=404,
        hops=[RouteHopDTO(202, "(202)", False), RouteHopDTO(404, "(404)", True)],
        turn_cost=4, turns_remaining=20, affordable=True, reachable=True, reason="",
        hazards=["Black hole at (404)", "Encounter risk on 1 hop (deepest band: Void)"],
        summary="2 hops · 4 turns · 1 one-way", avoids=[303],
    )

    text = ComputerScreen._route_confirmation(route)
    assert "Route to S404" in text
    assert "2 hops · 4 turns" in text
    assert "Avoid list honored: S303" in text
    assert "Interruption risk: Encounter risk on 1 hop" in text
    assert "Black hole at (404)" in text


async def test_dock_and_trade_buys_fuel() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        assert isinstance(app.screen, StarDockScreen)
        await pilot.press("t")  # trade the highlighted row (Fuel Ore) -> buy
        await pilot.pause()
        from edge.core.enums import Commodity

        assert svc.state.ships[1].cargo.get(Commodity.FUEL_ORE, 0) > 0
        assert svc.state.players[1].latinum < 2_000  # spent latinum buying


async def test_trade_keeps_highlighted_row() -> None:
    """Trading the highlighted row must not reset the cursor to the top, so the
    same commodity can be traded repeatedly without re-selecting it each time."""
    from textual.widgets import DataTable

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _new_game_at_stardock(app, pilot)
        assert isinstance(app.screen, StarDockScreen)
        table = app.screen.query_one("#commodities", DataTable)
        assert table.row_count > 1
        table.move_cursor(row=1, animate=False)  # highlight a non-top row
        await pilot.pause()
        await pilot.press("t")  # trade the highlighted row
        await pilot.pause()
        assert table.cursor_row == 1  # cursor stays put across the refresh


async def test_trade_panel_standard_explains_price_stock_and_hold_impact() -> None:
    """WP-UI14 keeps the full aligned matrix plus selected-row decision detail."""
    from textual.widgets import DataTable, Static

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _new_game_at_stardock(app, pilot)
        table = app.screen.query_one("#commodities", DataTable)
        labels = [str(column.label) for column in table.columns.values()]
        assert labels == [
            "Commodity", "Port", "Stock / capacity", "Unit price", "Aboard", "Action"]
        detail = str(app.screen.query_one("#trade-detail", Static).render())
        assert "Port sells / you buy" in detail
        assert "stock" in detail and "unit" in detail and "est." in detail and "holds" in detail


async def test_trade_panel_compact_moves_numbers_into_selected_detail() -> None:
    """Compact retains the action matrix while secondary numbers remain available below."""
    from textual.widgets import DataTable, Static

    app = EdgeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await _new_game_at_stardock(app, pilot)
        table = app.screen.query_one("#commodities", DataTable)
        labels = [str(column.label) for column in table.columns.values()]
        assert labels == ["Commodity", "Port", "Action"]
        detail = str(app.screen.query_one("#trade-detail", Static).render())
        assert "stock" in detail and "unit" in detail and "holds" in detail


async def test_trade_panel_explains_a_hard_port_purse_cap() -> None:
    """A buyer unable to settle the quick trade says so before the captain acts."""
    from dataclasses import replace as _replace

    from textual.widgets import DataTable, Static

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None and svc.config.economy.market.enabled
        port = next(p for p in svc.state.ports.values()
                    if any(line.mode.name == "BUY" for line in p.commodities))
        bought = next(line.commodity for line in port.commodities if line.mode.name == "BUY")
        player = svc.state.players[1]
        ship = svc.state.ships[player.ship_id]
        cargo = dict(ship.cargo)
        cargo[bought] = 10
        svc.state.ships[ship.id] = _replace(ship, sector_id=port.sector_id, cargo=cargo)
        svc.state.ports[port.id] = _replace(port, latinum=0)
        await pilot.press("p")
        await pilot.pause()
        table = app.screen.query_one("#commodities", DataTable)
        view = svc.current_port_view(1)
        assert view is not None
        buy_row = next(i for i, line in enumerate(view.commodities) if line.mode == "BUY")
        table.move_cursor(row=buy_row, animate=False)
        await pilot.pause()
        detail = str(app.screen.query_one("#trade-detail", Static).render())
        assert "Port buys / you sell" in detail
        assert "purse caps payment (0 available)" in detail


async def test_dock_and_haggle_accepts_fair_counter() -> None:
    """Press H, counter at the fair price (improvement 0 ⇒ always accepted), and the
    deal goes through as a HaggleOffer — the path playtesting found missing."""
    from textual.widgets import Input

    from edge.core.enums import Commodity
    from edge.core.events import Haggled
    from edge.tui.screens.haggle import HaggleScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        assert isinstance(app.screen, StarDockScreen)
        port = svc.current_port_view(1)
        assert port is not None
        fair = next(c for c in port.commodities if c.name == "Fuel Ore").price

        await pilot.press("h")  # open the haggle modal on the highlighted row (Fuel Ore)
        await pilot.pause()
        assert isinstance(app.screen, HaggleScreen)
        # Countering at the fair price does not favour the player → accepted with p=1.0.
        app.screen.query_one("#haggle-input", Input).value = str(fair)
        await pilot.press("enter")
        await pilot.pause()

        assert svc.state.ships[1].cargo.get(Commodity.FUEL_ORE, 0) > 0  # bought via haggle
        assert svc.state.players[1].latinum < 2_000  # spent latinum
        assert any(isinstance(e, Haggled) for e in svc._repo.load_events())  # logged as a haggle


async def test_haggle_walk_away_makes_no_trade() -> None:
    from edge.tui.screens.haggle import HaggleScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        await pilot.press("h")
        await pilot.pause()
        assert isinstance(app.screen, HaggleScreen)
        await pilot.press("escape")  # walk away — no offer made
        await pilot.pause()
        assert isinstance(app.screen, StarDockScreen)
        assert svc.state.players[1].latinum == 2_000  # nothing spent


async def test_descend_explore_log_flow() -> None:
    """The §13 named flow: survey a planet → descend → explore a site → log it."""
    from collections import defaultdict

    from edge.core.rules import Warp
    from edge.tui.screens.planet import PlanetScreen
    from edge.tui.screens.surface import SurfaceScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None

        # A reachable planet whose lowest-slot site is obvious (so one Explore at the
        # starter sensor reveals the row-0 site, which Log then collects).
        by_planet: dict[int, list[object]] = defaultdict(list)
        for d in svc.state.discoveries.values():
            if d.planet_id is not None:
                by_planet[d.planet_id].append(d)
        target = None
        for _pid, ds in by_planet.items():
            slot0 = min(ds, key=lambda d: d.site_slot)
            if not slot0.hidden and shortest_path(svc.state.adjacency, svc.game_view(1).sector.sector_id, slot0.sector_id) is not None:
                target = slot0
                break
        assert target is not None
        for hop in shortest_path(svc.state.adjacency, svc.game_view(1).sector.sector_id, target.sector_id)[1:]:
            svc.apply(1, Warp(to_sector=hop))

        await pilot.press("s")  # survey planet -> PlanetScreen
        await pilot.pause()
        assert isinstance(app.screen, PlanetScreen)
        await pilot.press("d")  # descend -> SurfaceScreen
        await pilot.pause()
        assert isinstance(app.screen, SurfaceScreen)
        await pilot.press("e")  # survey the next site (the obvious slot-0 one)
        await pilot.pause()
        await pilot.press("l")  # log the highlighted (now revealed) site
        await pilot.pause()
        assert target.id in svc.state.players[1].codex


async def test_clicking_planet_descends() -> None:

    from edge.core.rules import Warp
    from edge.tui.screens.planet import PlanetScreen, PlanetSprite
    from edge.tui.screens.surface import SurfaceScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        # A reachable planet — survey it to open the orbit view, then click its sprite.
        planet = next(
            pl for pl in svc.state.planets.values()
            if shortest_path(svc.state.adjacency, svc.game_view(1).sector.sector_id, pl.sector_id) is not None
        )
        for hop in shortest_path(svc.state.adjacency, svc.game_view(1).sector.sector_id, planet.sector_id)[1:]:
            svc.apply(1, Warp(to_sector=hop))
        await pilot.press("s")  # survey planet -> PlanetScreen
        await pilot.pause()
        assert isinstance(app.screen, PlanetScreen)
        await pilot.click(app.screen.query_one(PlanetSprite))  # click descends
        await pilot.pause()
        assert isinstance(app.screen, SurfaceScreen)


async def test_stardock_hardware_buys_then_engine_room_installs() -> None:
    from textual.widgets import TabbedContent

    from edge.tui.component_workbench import ComponentWorkbench
    from edge.tui.screens.engine_room import EngineRoomScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        assert isinstance(app.screen, StarDockScreen)
        app.screen.query_one(TabbedContent).active = "hardware"
        await pilot.pause()
        lat0 = svc.state.players[1].latinum
        await pilot.press("b")  # buy the highlighted component (Tier-I, affordable)
        await pilot.pause()
        loose = sum(svc.state.ships[1].components.values())
        assert loose == 1 and svc.state.players[1].latinum < lat0
        # Slot it in the shared component workbench: select the carried part and an
        # empty destination, then invoke Install / swap.
        await pilot.press("e")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, EngineRoomScreen)
        workbench = screen.query_one(ComponentWorkbench)
        await pilot.click(screen.query(".workbench-component").first())
        await pilot.pause()
        flat_index = next(
            index
            for index, slot in enumerate(
                slot for subsystem in workbench.subsystems for slot in subsystem.slots
            )
            if slot.state == "empty"
        )
        await pilot.click(list(screen.query(".workbench-slot"))[flat_index])
        await pilot.press("u")
        await pilot.pause()
        assert sum(svc.state.ships[1].components.values()) == 0  # the loose part was installed


def _inject_species(svc: object, roster_id: str):  # type: ignore[no-untyped-def]
    """Place a friendly roster species in the player's current sector + stock latinum."""
    from dataclasses import replace

    from edge.core.models import AlienSpecies

    sc = svc.config.roster.species_by_id(roster_id)  # type: ignore[attr-defined]
    ship = svc.state.ships[1]  # type: ignore[attr-defined]
    species = AlienSpecies(
        id=1, roster_id=roster_id, name=sc.name, archetype_id=sc.archetype_id,
        sector_id=ship.sector_id, home_band="Hub", tech_level=sc.tech_level,
        base_disposition=0.9, disposition_center=sc.disposition_center,
        disposition_variance=sc.disposition_variance, alliance_id=sc.alliance_id,
        trade_posture=sc.trade_posture, treaty_mode=sc.treaty_mode, persona=sc.persona,
    )
    svc.state.species[1] = species  # type: ignore[attr-defined]
    svc.state.players[1] = replace(svc.state.players[1], latinum=100_000)  # type: ignore[attr-defined]
    return species


async def test_hail_opens_contact_then_buys_tech() -> None:
    from textual.widgets import Static

    from edge.tui.screens.contact import AlienContactScreen, OfferPickerScreen
    from edge.tui.widgets import ClickableEntry

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        _inject_species(svc, "selvani")  # converter (II) latinum offer
        await pilot.press("h")  # hail the species in this sector
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        # The persona-voiced opener renders.
        assert str(app.screen.query_one("#speech", Static).render())
        # Buy tech: with no other species met, the baseline menu is 1 coordinates / 2 Trade.
        # The Trade reply opens the tech offer picker modal.
        await pilot.press("2")
        await pilot.pause()
        assert isinstance(app.screen, OfferPickerScreen)
        # Select the (only) available tech offer from the picker modal.
        await pilot.click(app.screen.query(ClickableEntry).first())
        await pilot.pause()
        assert sum(svc.state.ships[1].components.values()) == 1


async def _click_hotspot(pilot, scene, *, dest=None, ref=None) -> None:
    """Click the centre of the first SectorScene hotspot matching dest/ref."""
    spot = next(s for s in scene._hotspots
                if (dest is None or s[4] == dest) and (ref is None or s[5] == ref))
    cx, cy = (spot[0] + spot[2]) // 2, (spot[1] + spot[3]) // 2
    await pilot.click(scene, offset=(cx, cy))
    await pilot.pause()


async def test_click_ship_hails_that_specific_species() -> None:
    """Two contacts in the sector: clicking the second ship sprite hails it, not the first."""
    from edge.core.models import AlienSpecies
    from edge.tui.screens.contact import AlienContactScreen
    from edge.tui.widgets import SectorScene

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        _inject_species(svc, "vesk")  # id 1, the "first" ship (H would hail this one)
        sc2 = svc.config.roster.species_by_id("selvani")
        sector_id = svc.state.ships[1].sector_id
        svc.state.species[2] = AlienSpecies(
            id=2, roster_id="selvani", name=sc2.name, archetype_id=sc2.archetype_id,
            sector_id=sector_id, home_band="Hub", tech_level=sc2.tech_level,
            base_disposition=0.9, disposition_center=sc2.disposition_center,
            disposition_variance=sc2.disposition_variance, alliance_id=sc2.alliance_id,
            trade_posture=sc2.trade_posture, treaty_mode=sc2.treaty_mode, persona=sc2.persona)
        await app.screen.recompose()  # render the now-present ships
        await pilot.pause()
        scene = app.screen.query_one(SectorScene)
        await _click_hotspot(pilot, scene, dest="contact", ref=2)  # click Selvani's sprite
        assert isinstance(app.screen, AlienContactScreen)
        met = svc.state.players[1].species_attitudes
        # Reputation is keyed by species kind: clicking ship 2 hails the Selvani, not the Vesk.
        assert "selvani" in met and "vesk" not in met


async def test_click_planet_art_opens_survey() -> None:
    """Clicking the planet sprite (not just its text entry) surveys the planet."""
    from edge.core.rules import Warp
    from edge.tui.screens.planet import PlanetScreen
    from edge.tui.widgets import SectorScene

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        # Reach any sector that holds a planet (the art is drawn from sector.planets).
        planet = next(p for p in svc.state.planets.values()
                      if shortest_path(svc.state.adjacency, svc.game_view(1).sector.sector_id, p.sector_id) is not None)
        for hop in shortest_path(svc.state.adjacency, svc.game_view(1).sector.sector_id, planet.sector_id)[1:]:
            svc.apply(1, Warp(to_sector=hop))
        await app.screen.recompose()
        await pilot.pause()
        scene = app.screen.query_one(SectorScene)
        await _click_hotspot(pilot, scene, dest="planet")
        assert isinstance(app.screen, PlanetScreen)


async def test_click_port_art_docks() -> None:
    """Clicking the port sprite docks, the same as pressing P or its text entry."""
    from edge.core.rules import Warp
    from edge.tui.screens.port import PortScreen
    from edge.tui.screens.stardock import StarDockScreen
    from edge.tui.widgets import SectorScene

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        port = next(p for p in svc.state.ports.values()
                    if shortest_path(svc.state.adjacency, svc.game_view(1).sector.sector_id, p.sector_id) is not None)
        for hop in shortest_path(svc.state.adjacency, svc.game_view(1).sector.sector_id, port.sector_id)[1:]:
            svc.apply(1, Warp(to_sector=hop))
        await app.screen.recompose()
        await pilot.pause()
        scene = app.screen.query_one(SectorScene)
        await _click_hotspot(pilot, scene, dest="port")
        assert isinstance(app.screen, (PortScreen, StarDockScreen))


async def test_sector_view_caps_ship_sprites_and_keeps_overflow_hailable() -> None:
    """<= scene.max_ships_shown ship sprites, but every contact stays hailable."""
    from edge.core.models import AlienSpecies
    from edge.tui.widgets import SectorScene

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        # Three contacts in one sector — one more than the sprite cap (default 2).
        sector_id = svc.state.ships[1].sector_id
        # Clear any species the big bang staged here (the StarDock hub seeds contacts)
        # so we control the exact set under test.
        svc.state.species = {i: sp for i, sp in svc.state.species.items() if sp.sector_id != sector_id}
        for sid, roster_id in ((1, "vesk"), (2, "selvani"), (3, "vesk")):
            sc = svc.config.roster.species_by_id(roster_id)
            svc.state.species[sid] = AlienSpecies(
                id=sid, roster_id=roster_id, name=f"{sc.name} {sid}",
                archetype_id=sc.archetype_id, sector_id=sector_id, home_band="Hub",
                tech_level=sc.tech_level, base_disposition=0.9,
                disposition_center=sc.disposition_center,
                disposition_variance=sc.disposition_variance, alliance_id=sc.alliance_id,
                trade_posture=sc.trade_posture, treaty_mode=sc.treaty_mode, persona=sc.persona)
        await app.screen.recompose()
        await pilot.pause()
        scene = app.screen.query_one(SectorScene)
        # The header is composited at the top of the scene.
        assert "[" in scene.render().plain
        # All three contacts remain individually hailable (sprite cap + overflow list).
        contact_refs = {s[5] for s in scene._hotspots if s[4] == "contact"}
        assert contact_refs == {1, 2, 3}


async def test_haggle_session_stays_open_across_a_rejected_round() -> None:
    from textual.widgets import Input

    from edge.tui.screens.haggle import HaggleScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        assert isinstance(app.screen, StarDockScreen)
        await pilot.press("h")  # open the multi-round haggle on the highlighted commodity
        await pilot.pause()
        assert isinstance(app.screen, HaggleScreen)
        # A lowball counter (StarDock sells → the player buys) insults them: the round is
        # spent but the session stays open for another try.
        app.screen.query_one("#haggle-input", Input).value = "1"
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, HaggleScreen)  # not dismissed — multi-round
        assert svc.state.players[1].haggle_attempts  # the spent round was recorded


async def test_computer_dossier_lists_a_met_species() -> None:
    from textual.widgets import DataTable

    from edge.tui.screens.computer import ComputerScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        _inject_species(svc, "vesk")
        await pilot.press("h")  # hail → marks the species met
        await pilot.pause()
        await pilot.press("f")  # Farewell → leave contact
        await pilot.pause()
        await pilot.press("c")  # open the computer
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)
        app.screen.show_subview("dossier")
        await pilot.pause()
        table = app.screen.query_one("#dossier-table", DataTable)
        assert table.row_count == 1
        assert "Vesk" in str(table.get_cell_at((0, 0)))


async def test_continue_focused_and_new_game_confirms_when_save_exists() -> None:
    """With a save present, Continue takes focus and New game asks before clobbering it."""
    from textual.widgets import Button

    from edge.tui.screens.confirm import ConfirmScreen
    from edge.tui.screens.game import GameScreen
    from edge.tui.screens.main_menu import MainMenuScreen

    # First run writes a save into the (isolated) scratch save dir.
    async with EdgeApp().run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()

    # Second run: a save now exists.
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, MainMenuScreen)
        assert app.focused is app.screen.query_one("#continue", Button)  # Continue is focused
        # New game asks first; "Keep save" (Esc) returns to the menu, no game started.
        await pilot.press("n")
        await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, MainMenuScreen)
        assert app.service is None
        # Confirming overwrites and starts a fresh game.
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        assert app.service is not None


async def test_continue_reloads_saved_game() -> None:
    """Pressing Continue replays the saved command log back to where the player left off."""
    from edge.tui.screens.game import GameScreen

    app1 = EdgeApp()
    async with app1.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app1.service
        assert svc is not None
        start = svc.game_view(1).sector.sector_id
        target = svc.state.sectors[start].warps_out[0]
        svc.apply(1, Warp(to_sector=target))  # a durable command in the save's log
        moved = svc.game_view(1).sector.sector_id

    app2 = EdgeApp()
    async with app2.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("c")  # Continue
        await pilot.pause()
        assert isinstance(app2.screen, GameScreen)
        assert app2.service is not None
        assert app2.service.game_view(1).sector.sector_id == moved  # resumed, not reset


async def test_stardock_shipyard_swaps_hull() -> None:
    from dataclasses import replace

    from textual.widgets import TabbedContent

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        svc.state.players[1] = replace(svc.state.players[1], latinum=50_000)  # afford a hull
        app.screen.query_one(TabbedContent).active = "shipyard"
        await pilot.pause()
        await pilot.press("b")  # buy the highlighted hull (Scout Marauder)
        await pilot.pause()
        assert svc.state.ships[1].type_id == "scout_marauder"
        assert svc.state.players[1].latinum < 50_000


async def test_trade_plot_route_and_engage() -> None:
    """WP14: Trade tab → [P] plots the round trip → [G] engages and travels (§11)."""
    from textual.widgets import DataTable

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        # Starting at the StarDock, only it is explored; chart the whole map so the
        # (fog-gated) pair finder scores a pair and the route can plot through it.
        from dataclasses import replace
        svc.state.players[1] = replace(
            svc.state.players[1], explored_sectors=frozenset(svc.state.sectors))
        assert svc.computer_view(1).pairs  # the default seed has a scored pair
        await pilot.press("escape")  # undock back to the game screen
        await pilot.pause()
        await pilot.press("c")  # open the Computer on the Trade tab
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)

        before = svc.state.ships[1].sector_id
        await pilot.press("p")  # plot the highlighted pair's round trip
        await pilot.pause()
        assert app.screen._active_subview() == "route"
        assert app.screen.query_one("#route-table", DataTable).row_count >= 1

        await pilot.press("g")  # engage
        await pilot.pause()
        assert not isinstance(app.screen, ComputerScreen)  # popped back to the game
        assert svc.state.ships[1].sector_id != before  # advanced off the buy port


async def test_codex_plot_route_to_a_logged_find() -> None:
    """WP14: a logged discovery → Codex [P] routes to the find's sector (§11)."""
    from textual.widgets import DataTable

    from edge.core.rules import Salvage, Warp

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None

        # Seed the codex: warp to the nearest obvious open-space find and salvage it.
        sensor = svc.state.ships[1].sensor_rating
        diff = svc.config.discovery.sensor_difficulty  # type: ignore[union-attr]
        candidates = []
        for d in svc.state.discoveries.values():
            if d.planet_id is not None:
                continue
            path = shortest_path(svc.state.adjacency, svc.game_view(1).sector.sector_id, d.sector_id)
            if path is None:
                continue
            if not d.hidden:
                candidates.append((len(path), path, d))
            elif sensor >= diff[d.rarity_tier.name] and len(path) >= 2:
                candidates.append((len(path), path, d))
        candidates.sort(key=lambda t: t[0])
        _, path, disc = candidates[0]
        for hop in path[1:]:
            svc.apply(1, Warp(to_sector=hop))
        svc.apply(1, Salvage(discovery_id=disc.id))
        assert disc.id in svc.state.players[1].codex

        app.push_screen(ComputerScreen(svc, 1, initial_tab="codex"))
        await pilot.pause()
        await pilot.press("p")  # plot a route to the highlighted find
        await pilot.pause()
        assert app.screen._active_subview() == "route"
        # The plotted route targets the find's sector and renders its hops.
        assert app.screen._engage_target == disc.sector_id  # type: ignore[attr-defined]
        route = svc.route_view(1, disc.sector_id)
        assert app.screen.query_one("#route-table", DataTable).row_count == len(route.hops)


async def test_leads_tab_lists_logged_tip_plots_and_engages_route() -> None:
    """§6.7: a logged tip shows on the Leads tab → [P] routes over the full graph → [G] flies it,
    charting the uncharted course without any manual warping (the coordinates are the map)."""
    from textual.widgets import DataTable

    from edge.core.models import LocationRef
    from edge.core.rules import AcceptLead

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        # Isolate the regular discovery tip: the roaming Entity would out-rank it (§7, WP36).
        from edge.core.discovery import entity_species
        _ent = entity_species(svc.state, svc.config)
        if _ent is not None:
            del svc.state.species[_ent.id]
        sp = _inject_species(svc, "vesk")  # friendly, in the player's sector
        ship = svc.state.ships[1]
        player = svc.state.players[1]
        # Nearest unexplored rare+ find, so the route's turn cost fits the starting budget.
        candidates = []
        for d in svc.state.discoveries.values():
            if d.rarity_tier.value < 3 or d.sector_id in player.explored_sectors or d.found_by:
                continue
            path = shortest_path(svc.state.adjacency, ship.sector_id, d.sector_id)
            if path is not None:
                candidates.append((len(path), d))
        candidates.sort(key=lambda t: t[0])
        disc = candidates[0][1]
        svc.state.species_knowledge[sp.roster_id] = (
            LocationRef("discovery", disc.id, disc.sector_id),)
        svc.apply(1, AcceptLead(sp.id))  # log the tip (as the contact screen's [accept_lead] does)
        assert len(svc.state.players[1].leads) == 1
        assert disc.sector_id not in svc.state.players[1].explored_sectors

        app.push_screen(ComputerScreen(svc, 1, initial_tab="leads"))
        await pilot.pause()
        # The logged tip is listed (one data row, not the empty-state placeholder).
        assert app.screen.query_one("#leads-table", DataTable).row_count == 1
        await pilot.press("p")  # plot a route to the highlighted lead
        await pilot.pause()
        assert app.screen._active_subview() == "route"
        assert app.screen._engage_target == disc.sector_id  # type: ignore[attr-defined]
        # The tip points somewhere unvisited, so the route plans over the full graph and is
        # reachable (not the "explore a path first" empty state of an explored-only plot).
        route = svc.route_view(1, disc.sector_id, full_graph=True)
        assert route.reachable and route.hops
        assert app.screen._route.reachable  # type: ignore[attr-defined]
        assert app.screen.query_one("#route-table", DataTable).row_count == len(route.hops)

        from edge.tui.screens.confirm import ConfirmScreen
        await pilot.press("g")  # engage — fly the plotted lead route through uncharted space
        await pilot.pause()
        if isinstance(app.screen, ConfirmScreen):  # WP75: band-risk hazards confirm first
            await pilot.press("y")
            await pilot.pause()
        assert svc.state.ships[1].sector_id == disc.sector_id  # arrived at the tip
        assert disc.sector_id in svc.state.players[1].explored_sectors  # charted en route


async def test_map_tab_renders_local_graph_and_overlays_route() -> None:
    """§10/§11: the Map tab shows the local ego-graph centered on the player, and a
    plotted route lights up on it (the LocalMapView re-bakes with the overlay)."""
    from edge.tui.widgets import LocalMapView

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        # Warp one hop so the local map has a charted neighbour to route back to.
        start = svc.state.ships[1].sector_id
        svc.apply(1, Warp(to_sector=svc.state.adjacency[start][0]))

        app.push_screen(ComputerScreen(svc, 1, initial_tab="map"))
        await pilot.pause()
        view = app.screen.query_one("#local-map", LocalMapView)
        assert "@" in "\n".join(view._map.rows)  # type: ignore[attr-defined]  # you-marker present
        assert "bold yellow" not in "\n".join(view._map.rows)  # type: ignore[attr-defined]

        # Plot a route back to where we came from; the Map tab overlays it in the highlight.
        here = svc.state.ships[1].sector_id
        came_from = svc.state.players[1].entered_from[here]
        app.screen._after_route_prompt(  # type: ignore[attr-defined]
            svc.state.spatial_ids.get(came_from, came_from))
        await pilot.pause()
        assert "bold yellow" in "\n".join(view._map.rows)  # type: ignore[attr-defined]


async def test_clicking_a_map_sector_plots_a_route() -> None:
    """A clicked sector node on the Map plots a route to it and opens the Route tab."""

    from edge.tui.widgets import LocalMapView

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        start = svc.state.ships[1].sector_id
        svc.apply(1, Warp(to_sector=svc.state.adjacency[start][0]))  # one charted neighbour

        app.push_screen(ComputerScreen(svc, 1, initial_tab="map"))
        await pilot.pause()
        view = app.screen.query_one("#local-map", LocalMapView)
        # The came-from sector is charted and on the map → click its node for real, so the
        # widget's coordinate hit-test (padding offset included) is exercised end to end.
        here = svc.state.ships[1].sector_id
        came_from = svc.state.players[1].entered_from[here]
        node = next(n for n in view._map.nodes if n.sector_id == came_from)  # type: ignore[attr-defined]
        pad = view.styles.padding
        await pilot.click(view, offset=(node.col0 + pad.left, node.row + pad.top))
        await pilot.pause()

        assert app.screen._active_subview() == "route"  # opened the Route tab
        assert app.screen._engage_target == came_from  # type: ignore[attr-defined]
        assert app.screen._route.reachable  # type: ignore[attr-defined]  # a real route was plotted


async def test_map_arrow_keys_select_and_enter_plots_route() -> None:
    """Arrow keys move a sector cursor around the Map tab; Enter plots a route to it."""

    from edge.tui.widgets import LocalMapView

    app = EdgeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None

        app.push_screen(ComputerScreen(svc, 1, initial_tab="map"))
        await pilot.pause()
        view = app.screen.query_one("#local-map", LocalMapView)
        view.focus()
        await pilot.pause()
        assert app.focused is view
        if len(view._hits) < 2:  # type: ignore[attr-defined]
            return  # a lone-neighbour sector has nothing to navigate

        # The cursor starts on the home (top-left) node; a Right then Down moves it off.
        assert view._idx == 0  # type: ignore[attr-defined]
        await pilot.press("right")
        await pilot.press("down")
        await pilot.pause()
        assert view._idx != 0  # type: ignore[attr-defined]  # the arrow keys moved the selection

        # Enter plots a route to the selected sector and opens the Route tab.
        selected = view._hits[view._idx].sector_id  # type: ignore[attr-defined]
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen._active_subview() == "route"
        assert app.screen._engage_target == selected  # type: ignore[attr-defined]


async def test_computer_screen_remembers_last_tab() -> None:
    """[C] reopens the Computer on whichever tab was last viewed (not always Trade)."""

    from edge.tui.screens.computer import ComputerScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("c")  # open the Computer — defaults to the Trade tab
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)
        assert app.screen._active_subview() == "trade"

        app.screen.show_subview("codex")  # switch tabs
        await pilot.pause()
        assert app.computer_tab == "codex"  # the switch is remembered on the app
        await pilot.press("c")  # [C] closes the Computer from within
        await pilot.pause()
        assert not isinstance(app.screen, ComputerScreen)

        await pilot.press("c")  # reopen — should land back on Codex, not Trade
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)
        assert app.screen._active_subview() == "codex"


async def test_ports_directory_lists_and_plots_route() -> None:
    """WP15: Ports tab lists charted ports → [P] plots a route to one (§11)."""
    from textual.widgets import DataTable

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        directory = svc.computer_view(1).ports
        assert directory  # at least the StarDock is charted
        await pilot.press("escape")  # undock back to the game screen
        await pilot.pause()
        await pilot.press("c")  # open the Computer
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)

        app.screen.show_subview("ports")
        await pilot.pause()
        assert app.screen.query_one("#ports-table", DataTable).row_count == len(directory)

        await pilot.press("p")  # plot a route to the highlighted (nearest) port
        await pilot.pause()
        assert app.screen._active_subview() == "route"
        assert app.screen._engage_target == directory[0].sector_id  # type: ignore[attr-defined]


async def test_say_do_menu_converse_and_trade() -> None:
    """WP17: Ask about… (subject picker) → speech updates; a Trade reply buys tech; Farewell closes."""
    from dataclasses import replace

    from textual.widgets import Static

    from edge.core.models import AlienSpecies
    from edge.tui.screens.contact import AlienContactScreen, OfferPickerScreen, SubjectPickerScreen
    from edge.tui.widgets import ClickableEntry

    app = EdgeApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        _inject_species(svc, "selvani")  # id=1, in the player's sector (lone latinum offer)
        sc = svc.config.roster.species_by_id("vesk")
        ship = svc.state.ships[1]
        svc.state.species[2] = AlienSpecies(  # a second *met* species: the ask-about subject
            id=2, roster_id="vesk", name="Vesk", archetype_id=sc.archetype_id,
            sector_id=ship.sector_id + 999, home_band="Hub", tech_level=sc.tech_level,
            base_disposition=0.9, disposition_center=sc.disposition_center,
            disposition_variance=sc.disposition_variance, alliance_id=sc.alliance_id,
            trade_posture=sc.trade_posture, treaty_mode=sc.treaty_mode, persona=sc.persona)
        svc.state.players[1] = replace(svc.state.players[1],
                                       species_attitudes={"selvani": 0.0, "vesk": 0.0})

        await pilot.press("h")  # hail the Selvani
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)

        # Ask about… (reply 1) → subject picker → pick Vesk → the speech narrates the Vesk.
        await pilot.press("1")
        await pilot.pause()
        assert isinstance(app.screen, SubjectPickerScreen)
        await pilot.click(app.screen.query(ClickableEntry).first())
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        assert "Vesk" in str(app.screen.query_one("#speech", Static).render())

        # Back out of the dossier node (b), then buy tech (reply 3 → offer picker modal).
        await pilot.press("b")
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()
        assert isinstance(app.screen, OfferPickerScreen)
        # Select the (only) available latinum offer from the picker modal.
        await pilot.click(app.screen.query(ClickableEntry).first())
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        assert sum(svc.state.ships[1].components.values()) == 1

        # Farewell (f) speaks its parting line and breaks contact.
        await pilot.press("f")
        await pilot.pause()
        assert not isinstance(app.screen, AlienContactScreen)


async def test_branching_choices_render_and_drive_transition() -> None:
    """§6.7: a node's authored choices show as numbered replies; '1' transitions.

    The whole menu is authored choices now; a species that authors its own greeting replies
    (Vesk) overrides the generic baseline. Here we drive the Vesk's greeting → workshop branch.
    """
    from edge.tui.screens.contact import AlienContactScreen
    from edge.tui.widgets import ClickableEntry

    app = EdgeApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        _inject_species(svc, "vesk")  # serial_formal persona authors greeting choices

        await pilot.press("h")  # hail → contact screen on the greeting node
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        # The greeting node carries authored replies → numbered choices, not the derived menu.
        body = " ".join(str(e.render()) for e in app.screen.query(ClickableEntry))
        assert "[1]" in body
        view = app.screen._view()  # type: ignore[attr-defined]
        assert view.choices and view.choices[0].next_context == "branch.vesk_workshop"

        await pilot.press("1")  # pick the first reply → transition to the workshop node
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        assert app.screen._active_context == "branch.vesk_workshop"  # type: ignore[attr-defined]
        actions = {c.action for c in app.screen._view().choices}  # type: ignore[attr-defined]
        assert "trade" in actions and "leave" in actions


async def test_log_coordinates_freezes_the_offer_line() -> None:
    """Logging a tip keeps the speech panel on the line just acted on — it must not auto-cycle
    to the next tip the alien would offer (§6.7). Selvani falls back to the generic baseline menu,
    so Ask-for-coordinates and (on the offer node) Log-coordinates are numbered replies."""
    from textual.widgets import Static

    from edge.core.models import LocationRef
    from edge.tui.screens.contact import AlienContactScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        sp = _inject_species(svc, "selvani")  # baseline menu; friendly, in the player's sector
        # Point the species at a real, reachable, unexplored rare+ discovery so it volunteers a tip.
        ship = svc.state.ships[1]
        player = svc.state.players[1]
        disc = next(
            d for d in svc.state.discoveries.values()
            if d.rarity_tier.value >= 3 and d.sector_id not in player.explored_sectors
            and d.found_by is None
            and shortest_path(svc.state.adjacency, ship.sector_id, d.sector_id) is not None)
        svc.state.species_knowledge[sp.roster_id] = (
            LocationRef("discovery", disc.id, disc.sector_id),)

        await pilot.press("h")  # hail
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)

        # Ask for coordinates (reply 1, with no other species met) → the offer line shows.
        await pilot.press("1")
        await pilot.pause()
        assert app.screen._active_context == "offer_coordinates"  # type: ignore[attr-defined]
        offer_line = str(app.screen.query_one("#speech", Static).render())
        assert any(ch.isdigit() for ch in offer_line)  # the line carries {coords}

        # Log coordinates (reply 1 on the offer node).
        await pilot.press("1")
        await pilot.pause()
        assert isinstance(app.screen, AlienContactScreen)
        # Frozen on the logged line — it did NOT cycle to the next tip / the no-tip branch.
        assert str(app.screen.query_one("#speech", Static).render()) == offer_line
        assert len(svc.state.players[1].leads) == 1


async def test_question_mark_opens_help_with_warp_legend() -> None:
    from textual.widgets import Static

    from edge.tui.screens.help import HelpScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        text = " ".join(str(s.render()) for s in app.screen.query(Static))
        assert "Warp Color" in text
        for label in ("Coreward", "Outward", "Cross-band", "Backtrack", "One-way",
                      "Avoided", "Known hazard", "Unexplored", "Sector Codes"):
            assert label in text
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


async def test_ticker_expands_and_collapses_on_divider_click() -> None:
    from edge.tui.widgets import Ticker, _TickerDivider

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        ticker = app.screen.query_one(Ticker)
        assert not ticker.has_class("expanded")
        await pilot.click(app.screen.query_one(_TickerDivider))
        await pilot.pause()
        assert ticker.has_class("expanded")
        await pilot.click(app.screen.query_one(_TickerDivider))
        await pilot.pause()
        assert not ticker.has_class("expanded")


async def test_stale_encounter_screen_never_strands_the_player() -> None:
    """A resolved fight can't trap the player (the double-push regression).

    A stale EncounterScreen (no live encounter) self-heals: any combat key pops it
    instead of parroting "no live encounter", Esc closes it, and the game screen's
    resume hook never stacks a second copy while one is already open.
    """
    from edge.tui.screens.encounter import EncounterScreen
    from edge.tui.screens.game import GameScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        assert svc.encounter_view(1) is None
        # Simulate the stale screen a double-push used to leave behind.
        app.push_screen(EncounterScreen(svc, 1))
        await pilot.pause()
        await pilot.press("f")  # a combat key on a resolved fight pops, not "no live encounter"
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        app.push_screen(EncounterScreen(svc, 1))
        await pilot.pause()
        await pilot.press("escape")  # Esc closes a resolved engagement too
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        # The resume guard: with an EncounterScreen already up, resuming the game
        # screen must not stack another (one pop returns straight to the ship).
        game = app.screen
        assert isinstance(game, GameScreen)
        assert not any(isinstance(s, EncounterScreen) for s in app.screen_stack)


async def test_base_key_opens_unified_base_screen() -> None:
    """WP80 — `B` on the game screen opens the state-gated BaseScreen for the base here.

    The player is teleported (state mutation, no Warp — no encounters/hazards) onto a
    starbase sector; the unified base view must open, and Esc must return to the game.
    Every base sector hosts a market port (WP78), so a Trade tab is always present.
    """
    from dataclasses import replace as _replace

    from edge.tui.screens.base import BaseScreen
    from edge.tui.screens.game import GameScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        assert svc.state.starbases, "default universe should hold at least one base"
        base = svc.state.starbases[min(svc.state.starbases)]
        ship = svc.state.ships[svc.state.players[1].ship_id]
        svc.state.ships[ship.id] = _replace(ship, sector_id=base.sector_id)
        await pilot.press("b")
        await pilot.pause()
        assert isinstance(app.screen, BaseScreen)
        view = svc.current_starbase_view(1)
        assert view is not None and view.market_port_id is not None
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)


async def test_base_hosted_market_trades_inside_base_screen() -> None:
    """A base-hosted port is a Trade tab, not a second PortScreen navigation layer."""
    from dataclasses import replace as _replace

    from textual.widgets import DataTable, TabbedContent

    from edge.tui.screens.base import BaseScreen
    from edge.tui.widgets import TradePanel

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        ship = svc.state.ships[svc.state.players[1].ship_id]
        base = None
        sell_row = -1
        for candidate in svc.state.starbases.values():
            svc.state.ships[ship.id] = _replace(ship, sector_id=candidate.sector_id)
            view = svc.current_starbase_view(1)
            port = svc.current_port_view(1)
            if view is not None and view.market_open and port is not None:
                sell_row = next((i for i, line in enumerate(port.commodities)
                                 if line.mode == "SELL"), -1)
                if sell_row >= 0:
                    base = candidate
                    break
        assert base is not None, "generated bases should include an open supplier market"

        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, BaseScreen)
        assert app.screen.query_one(TabbedContent).active == "trade"
        assert app.screen.query_one(TradePanel)
        table = app.screen.query_one("#commodities", DataTable)
        table.move_cursor(row=sell_row, animate=False)
        before = svc.state.players[1].latinum
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, BaseScreen)
        assert svc.state.players[1].latinum < before


async def test_compact_stardock_uses_shared_service_selector() -> None:
    """WP-UI15 replaces the overflowing compact tab rail with the shared selector."""
    from textual.widgets import Select, TabbedContent, Tabs

    from edge.tui.widgets import ServiceHub

    app = EdgeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await _new_game_at_stardock(app, pilot)
        hub = app.screen.query_one(ServiceHub)
        selector = hub.query_one("#service-selector", Select)
        assert selector.display
        assert not hub.query_one(Tabs).display
        selector.value = "bank"
        await pilot.pause()
        assert hub.query_one(TabbedContent).active == "bank"


async def test_base_service_hub_explains_unavailable_facilities() -> None:
    """Unavailable base services stay discoverable and name their prerequisite."""
    from dataclasses import replace as _replace

    from textual.widgets import Select, Static, TabbedContent

    from edge.tui.screens.base import BaseScreen
    from edge.tui.widgets import ServiceHub

    app = EdgeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        ship = svc.state.ships[svc.state.players[1].ship_id]
        base = next(b for b in svc.state.starbases.values()
                    if not svc.starbase_view(1, b.id).hardware)
        svc.state.ships[ship.id] = _replace(ship, sector_id=base.sector_id)
        await pilot.press("b")
        await pilot.pause()
        assert isinstance(app.screen, BaseScreen)
        hub = app.screen.query_one(ServiceHub)
        selector = hub.query_one("#service-selector", Select)
        selector.value = "hardware"
        await pilot.pause()
        assert hub.query_one(TabbedContent).active == "hardware"
        explanation = str(hub.query_one("#hardware .service-unavailable", Static).render())
        assert "Hardware unavailable" in explanation
        assert "friendly base" in explanation


async def test_list_picker_keyboard_navigation() -> None:
    """The shared ListPicker is fully keyboard-driven: ↑/↓ move the highlight,
    Enter confirms it, Esc cancels — no mouse required (and wrap-around works)."""
    from edge.tui.screens.picker import ListPicker

    app = EdgeApp()
    async with app.run_test(size=(80, 30)) as pilot:
        picked: list[object] = []
        app.push_screen(ListPicker("Pick one", [("Alpha", "a"), ("Beta", "b"), ("Gamma", "c")]),
                        picked.append)
        await pilot.pause()
        await pilot.press("down", "down", "enter")   # → third row
        await pilot.pause()
        assert picked == ["c"]
        picked.clear()
        app.push_screen(ListPicker("Pick one", [("Alpha", "a"), ("Beta", "b")]), picked.append)
        await pilot.pause()
        await pilot.press("up", "enter")             # wraps to the last row
        await pilot.pause()
        assert picked == ["b"]
        picked.clear()
        app.push_screen(ListPicker("Pick one", [("Alpha", "a")]), picked.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert picked == [None]


async def test_help_is_contextual_to_the_current_screen() -> None:
    """`?` works on every screen (app-level) and shows *that* screen's keys: the
    StarDock help lists dock verbs and skips the sector view's warp legend."""
    from textual.widgets import Static

    from edge.tui.screens.help import HelpScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await _new_game_at_stardock(app, pilot)  # StarDockScreen on top
        assert isinstance(app.screen, StarDockScreen)
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        text = " ".join(str(s.render()) for s in app.screen.query(Static))
        assert "StarDock" in text and "Recruit" in text
        assert "Warp Color" not in text  # the legend belongs to the sector view only
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, StarDockScreen)


async def test_corp_screen_charters_with_derived_tag_and_buttons() -> None:
    """The corp screen is panel/button-driven: chartering asks for a name only
    (the ⟨TAG⟩ is derived internally), and the treasury buttons issue the
    commands without hotkeys."""
    from textual.widgets import Button, Input

    from edge.tui.screens.corp import CorpScreen, _FormCorpModal, _derive_tag

    assert _derive_tag("Edge of the Unknown", 3) == "EOT"
    assert _derive_tag("Vanguard", 3) == "VAN"

    app = EdgeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        from dataclasses import replace as _replace
        svc.state.players[1] = _replace(svc.state.players[1], latinum=50_000)  # afford the fee
        await pilot.press("t")  # game screen → corp screen
        await pilot.pause()
        assert isinstance(app.screen, CorpScreen)
        await pilot.click("#btn-form")
        await pilot.pause()
        assert isinstance(app.screen, _FormCorpModal)
        app.screen.query_one("#field-input", Input).value = "Edge of the Unknown"
        await pilot.click("#field-submit")
        await pilot.pause()
        corp = next(iter(svc.state.corporations.values()))
        assert corp.name == "Edge of the Unknown"
        assert corp.tag == _derive_tag("Edge of the Unknown", svc.config.corp.tag_max_len)
        # Back on the corp screen, the panels are up; Deposit is a button click.
        assert isinstance(app.screen, CorpScreen)
        before = corp.bank_balance
        assert app.screen.query(Button)  # panels rendered with buttons
        await pilot.click("#btn-deposit")
        await pilot.pause()
        corp = svc.state.corporations[corp.id]
        assert corp.bank_balance == before + 1_000


async def test_territory_screen_rows_and_deployed_table() -> None:
    """Each deployable renders as a stable vertical row with art, stock, purpose,
    legality, and a focusable button; deploying via the button chain works,
    and the resulting force shows up in the 'Deployed in this sector' table."""
    from dataclasses import replace as _replace

    from textual.widgets import Button, DataTable

    from edge.tui.screens.stardock import _AmountInput
    from edge.tui.screens.territory import TerritoryScreen, _DeployRow, _ModePicker

    app = EdgeApp()
    async with app.run_test(size=(120, 44)) as pilot:
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        # Move out of the Core (deployment barred there) and stock some fighters.
        ship = svc.state.ships[svc.state.players[1].ship_id]
        outside = next(s.id for s in svc.state.sectors.values() if not s.is_galactic_core)
        svc.state.ships[ship.id] = _replace(ship, sector_id=outside, fighters=40)
        await pilot.press("d")  # game screen → deploy screen
        await pilot.pause()
        assert isinstance(app.screen, TerritoryScreen)
        rows = list(app.screen.query(_DeployRow))
        assert len(rows) >= 6  # fighters, armid, limpet, beacon, probe, interdictor
        await pilot.click("#go-fighters")
        await pilot.pause()
        assert isinstance(app.screen, _AmountInput)  # count prompt
        await pilot.press("2", "5", "enter")
        await pilot.pause()
        assert isinstance(app.screen, _ModePicker)   # mode picked from a list
        await pilot.press("enter")                   # defensive (first row)
        await pilot.pause()
        assert svc.state.sector_forces[outside].fighters == 25
        # The reopened screen lists the new force in the deployed table.
        assert isinstance(app.screen, TerritoryScreen)
        table = app.screen.query_one("#deployed-table", DataTable)
        assert table.row_count >= 1
        assert app.focused is app.screen.query_one("#go-fighters", Button)


async def test_planet_citadel_panel_builds_via_button() -> None:
    """The planet screen's stores + citadel blocks are widget panels: a stores
    DataTable, staged citadel art, and a Build button that opens the timed build."""
    from dataclasses import replace as _replace

    from textual.widgets import DataTable

    from edge.core.enums import Commodity
    from edge.core.models import Ownership
    from edge.tui.screens.planet import PlanetScreen, _citadel_stage

    app = EdgeApp()
    async with app.run_test(size=(120, 44)) as pilot:
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        planet = next(iter(svc.state.planets.values()))
        svc.state.planets[planet.id] = _replace(
            planet, owner=Ownership("player", 1), colonists=1_000,
            stores={Commodity.EQUIPMENT: 10_000})
        svc.state.players[1] = _replace(svc.state.players[1], latinum=200_000)
        ship = svc.state.ships[svc.state.players[1].ship_id]
        svc.state.ships[ship.id] = _replace(ship, sector_id=planet.sector_id)
        await pilot.press("s")  # survey planet → PlanetScreen
        await pilot.pause()
        assert isinstance(app.screen, PlanetScreen)
        app.screen.query_one("#stores-table", DataTable)  # stores are tabular now
        assert _citadel_stage(app.screen._planet) == "site"  # unbuilt art stage
        await pilot.click("#btn-build")
        await pilot.pause()
        assert svc.state.planets[planet.id].citadel_progress >= 0  # build opened
        assert isinstance(app.screen, PlanetScreen)  # screen reopened
        assert _citadel_stage(app.screen._planet) == "building"  # scaffolding art


async def test_planet_and_surface_responsive_priority_at_all_tiers() -> None:
    """WP-UI16: compact prioritizes workflows; larger tiers retain scene art."""
    from textual.widgets import Static

    from edge.tui.dummy import sample_planet, sample_surface
    from edge.tui.screens.planet import PlanetScreen
    from edge.tui.screens.surface import SurfaceScreen

    for size, tier in [((80, 24), "compact"), ((100, 34), "standard"), ((120, 40), "wide")]:
        app = EdgeApp(plain=True)
        async with app.run_test(size=size) as pilot:
            app.push_screen(PlanetScreen(sample_planet()))
            await pilot.pause()
            assert app.screen.has_class(tier)
            assert app.screen.query_one("#identity-panel").display
            assert app.screen.query_one("#orbit-art").display is (tier != "compact")

            app.pop_screen()
            app.push_screen(SurfaceScreen(sample_surface()))
            await pilot.pause()
            assert app.screen.has_class(tier)
            assert app.screen.query_one("#terrain").display is (tier != "compact")
            assert app.screen.query_one("#site-art").display is (tier != "compact")
            detail = app.screen.query_one("#site-detail", Static).render().plain
            assert "Rarity" in detail and "Status" in detail and "Reward" in detail


async def test_surface_site_buttons_track_selection() -> None:
    """WP-UI16: survey and collect are mouse-visible and selection-aware."""
    from textual.widgets import Button, DataTable

    from edge.tui.dummy import sample_surface
    from edge.tui.screens.surface import SurfaceScreen

    app = EdgeApp(plain=True)
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(SurfaceScreen(sample_surface()))
        await pilot.pause()
        survey = app.screen.query_one("#btn-survey", Button)
        collect = app.screen.query_one("#btn-collect", Button)
        assert not survey.disabled
        assert collect.disabled
        table = app.screen.query_one("#sites", DataTable)
        table.move_cursor(row=1, animate=False)
        await pilot.pause()
        assert not collect.disabled


async def test_contact_replies_are_responsive_and_keyboard_focusable() -> None:
    """WP-UI17: speech/replies win compact space and arrows reach every reply."""
    from dataclasses import replace

    from edge.tui.dummy import sample_contact
    from edge.tui.screens.contact import AlienContactScreen, ContactReply

    for size, tier in [((80, 24), "compact"), ((100, 34), "standard"), ((120, 40), "wide")]:
        app = EdgeApp(plain=True)
        async with app.run_test(size=size) as pilot:
            app.ui_settings = replace(app.ui_settings, show_disabled_options=True)
            app.push_screen(AlienContactScreen(sample_contact()))
            await pilot.pause()
            assert app.screen.has_class(tier)
            assert app.screen.query_one("#portrait-box").display is (tier != "compact")
            replies = list(app.screen.query(ContactReply))
            assert len(replies) == len(sample_contact().choices)
            await pilot.press("down")
            assert app.focused is replies[0]
            await pilot.press("down")
            assert app.focused is replies[1]
            await pilot.press("enter")  # no-service harness: dispatches safely


async def test_compact_combat_dashboard_keeps_round_result_and_odds() -> None:
    """WP-UI18: combat remains keyboard-playable with persistent reducer results."""
    from dataclasses import replace
    from types import SimpleNamespace

    from edge.core.events import CombatRound
    from edge.tui.dummy import sample_encounter_view
    from edge.tui.screens.encounter import EncounterScreen

    class CombatService:
        def __init__(self) -> None:
            self.view = sample_encounter_view()

        def encounter_view(self, player_id: int):
            return self.view

        def engine_room_view(self, player_id: int):
            return SimpleNamespace(subsystems=[])

        def apply(self, player_id: int, command):
            self.view = replace(self.view, round_no=self.view.round_no + 1,
                                shields_pct=self.view.shields_pct - 4)
            return [CombatRound(player_id, self.view.species_id, self.view.round_no,
                                command.action, 12, 4, 3)]

    service = CombatService()
    app = EdgeApp(plain=True)
    async with app.run_test(size=(80, 24)) as pilot:
        app.push_screen(EncounterScreen(service, 1))
        await pilot.pause()
        assert app.screen.has_class("compact")
        advice = app.screen.query_one("#enc-advice").render().plain
        assert "hard floor 10%" in advice and "FIRING ARC" in advice
        await pilot.press("f")
        await pilot.pause()
        result = app.screen.query_one("#enc-result").render().plain
        assert "FIRE" in result and "damage dealt 12" in result and "damage taken 4" in result
