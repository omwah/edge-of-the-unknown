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
from edge.tui.widgets import NeighborRow


async def _new_game_at_stardock(app: EdgeApp, pilot: object) -> object:
    """Press New game, then warp the player to the StarDock and dock (press P)."""
    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    svc = app.service
    assert svc is not None
    dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)
    path = shortest_path(svc.state.adjacency, 1, dock.sector_id)
    assert path is not None
    for hop in path[1:]:
        svc.apply(1, Warp(to_sector=hop))
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
        assert view.sector.sector_id == 1 and view.turns == 250


async def test_sidebar_neighbor_click_warps() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        start = svc.game_view(1).sector.sector_id
        rows = app.screen.query(NeighborRow)
        assert rows
        first = rows.first()
        target = first._sector_id
        await pilot.click(first)
        await pilot.pause()
        moved = svc.game_view(1).sector.sector_id
        assert moved == target != start


async def test_log_hotkey_opens_computer_with_signpost() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("g")  # Log -> Computer, folded in (WP-B)
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)
        from textual.widgets import DataTable

        rows = app.screen.query_one("#log-table", DataTable)
        cells = [str(rows.get_cell_at((r, 1))) for r in range(rows.row_count)]
        assert any("StarDock" in c for c in cells)


async def test_travel_prompt_warps_along_known_route() -> None:
    from textual.widgets import Input

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        # Uncover a neighbour with a two-way edge, then travel back to the Core (1).
        a = next(s for s in svc.state.sectors[1].warps_out
                 if 1 in svc.state.sectors[s].warps_out)
        svc.apply(1, Warp(to_sector=a))
        await pilot.press("w")  # open the travel prompt (WP-C)
        await pilot.pause()
        assert isinstance(app.screen, TravelPromptScreen)
        # The prompt takes a *spatial* display id (§5.1) — type Sector 1's spatial id.
        app.screen.query_one("#travel-input", Input).value = str(svc.state.spatial_ids[1])
        await pilot.press("enter")
        await pilot.pause()
        assert svc.game_view(1).sector.sector_id == 1


async def test_sector_title_shows_spatial_id() -> None:
    """The game screen renders the sector's spatial display id, not the internal id (§5.1)."""
    from textual.widgets import Static

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        spatial = svc.state.spatial_ids[1]  # the player starts at internal sector 1
        assert spatial != 1  # the spatial id genuinely differs from the internal id
        title = str(app.screen.query_one("#title", Static).render())
        assert f"[{spatial}]" in title


async def test_arrow_keys_move_warp_focus() -> None:
    """Arrow keys move focus between warp buttons by their on-screen layout (round-2).

    The current-sector marker (grid centre) is auto-focused on the fresh game screen
    (no priming Tab), so the first arrow press moves *relative to the current sector*;
    further presses step by grid geometry — Right/Left along a row, Down/Up a column.
    """
    from edge.tui.widgets import CurrentSectorMarker, WarpButton, WarpGrid

    def land(buttons: dict, start: tuple[int, int], delta: tuple[int, int], max_row: int):
        r, c = start[0] + delta[0], start[1] + delta[1]
        while 0 <= r <= max_row and 0 <= c < 3:
            if (r, c) in buttons:
                return (r, c)
            r, c = r + delta[0], c + delta[1]
        return None

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        # No Tab pressed: the current-sector marker holds focus as the anchor.
        assert isinstance(app.focused, CurrentSectorMarker)

        grid = app.screen.query_one(WarpGrid)
        children = list(grid.children)
        pos = {c: (i // 3, i % 3) for i, c in enumerate(children)}
        buttons = {pos[c]: c for c in children if isinstance(c, WarpButton)}
        max_row = (len(children) - 1) // 3
        centre = pos[app.focused]  # the marker's grid position (1, 1)

        # First press from the centre lands on the warp in that screen direction.
        keys = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
        first = next(((k, land(buttons, centre, d, max_row)) for k, d in keys.items()
                      if land(buttons, centre, d, max_row) is not None), None)
        assert first is not None
        key, target = first
        await pilot.press(key)
        await pilot.pause()
        assert app.focused is buttons[target]

        # Right/Left along a row, relative to the now-focused warp button.
        row_pair = next(((p, (p[0], p[1] + 1)) for p in buttons if (p[0], p[1] + 1) in buttons), None)
        assert row_pair is not None
        src, dst = row_pair
        buttons[src].focus()
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        assert app.focused is buttons[dst]
        await pilot.press("left")
        await pilot.pause()
        assert app.focused is buttons[src]


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


async def test_dock_and_buy_upgrade() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game_at_stardock(app, pilot)
        holds0 = svc.state.ships[1].holds_total
        await pilot.press("u")  # Hardware: buy the first upgrade
        await pilot.pause()
        amount = svc.config.economy.first_upgrade_amount
        cost = svc.config.economy.first_upgrade_latinum
        assert svc.state.ships[1].holds_total == holds0 + amount
        assert svc.state.players[1].latinum == 2_000 - cost
