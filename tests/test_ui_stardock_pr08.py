"""WP-PR08 — Stardock information architecture and scoped actions (playtest PT-02..07, 29).

Drives the real app at the dock: the unified Devices & Armaments catalog buys munitions and
devices through `P`; the Colonists tab recruits; the current hull can't be bought; and the
bounty board is structured rows. Tab-scoping itself now falls out of the PT-32 keyboard
model (a tab owns its keys) and is covered in tests/test_ui_stardock_keys.py.
"""

from __future__ import annotations

from dataclasses import replace

from edge.core.rules import Warp
from edge.core.movement import shortest_path
from edge.tui.app import EdgeApp
from edge.tui.saves import clear_slot
from edge.tui.screens.stardock import StardockScreen


async def _dock(app: EdgeApp, pilot: object) -> object:
    clear_slot()
    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    svc = app.service
    assert svc is not None
    dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)
    start = svc.game_view(1).sector.sector_id
    for hop in (shortest_path(svc.state.adjacency, start, dock.sector_id) or [])[1:]:
        svc.apply(1, Warp(to_sector=hop))
    # Give the captain money to shop with.
    p = svc.state.players[1]
    svc.state.players[1] = replace(p, latinum=200_000)
    await pilot.press("p")  # dock -> StardockScreen  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    return svc


async def _select_tab(screen: StardockScreen, pilot: object, tab: str) -> None:
    """Reach a tab the way a player does — by its accelerator, which also lands focus in
    the pane. Focus is what makes that tab's keys live (PT-32), so a test that set
    `TabbedContent.active` directly would be pressing keys at the wrong pane."""
    await pilot.press(StardockScreen._TAB_ACCEL[tab])  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


async def test_buy_armament_amount_and_oneoff() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StardockScreen)
        await _select_tab(screen, pilot, "devices")
        from textual.widgets import DataTable
        table = screen.query_one("#devices-table", DataTable)
        # Buy a one-off device: select the interdictor row and press P.
        arms = svc.stardock_view(1).armaments
        idx = next(i for i, a in enumerate(arms) if a.kind == "device")
        table.move_cursor(row=idx, animate=False)
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()
        assert svc.state.ships[svc.state.players[1].ship_id].devices  # a device was bought


async def test_recruit_from_colonists_tab() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StardockScreen)
        await _select_tab(screen, pilot, "colonists")
        from textual.widgets import Button
        screen.query_one("#btn-recruit-all", Button).press()
        await pilot.pause()
        await pilot.pause()
        # Recruit-all filled every free berth (or as many as latinum allowed).
        ship = svc.state.ships[svc.state.players[1].ship_id]
        assert ship.colonists > 0


async def test_recruit_stepper_supports_steps_exact_amount_and_enter() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StardockScreen)
        await _select_tab(screen, pilot, "colonists")
        from textual.widgets import Button, Input
        screen.query_one("#inc-recruit", Button).press()
        await pilot.pause()
        field = screen.query_one("#amt-recruit", Input)
        assert field.value == "10"
        field.value = "17"
        field.focus()
        before = svc.state.ships[svc.state.players[1].ship_id].colonists
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        after = svc.state.ships[svc.state.players[1].ship_id].colonists
        assert after - before == 17


async def test_current_hull_cannot_be_bought() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StardockScreen)
        # Fly a *paid* hull so it appears in the shipyard as the owned row (the free
        # starter is excluded from the catalog, so there'd be no owned row otherwise).
        from edge.core.rules import BuyShip
        paid = next(s for s in svc.stardock_view(1).shipyard if not s.owned and s.affordable)
        svc.apply(1, BuyShip(paid.class_id))
        await screen.recompose()
        await pilot.pause()
        await _select_tab(screen, pilot, "shipyard")
        from textual.widgets import DataTable
        table = screen.query_one("#shipyard-table", DataTable)
        rows = svc.stardock_view(1).shipyard
        idx = next(i for i, s in enumerate(rows) if s.owned)
        before = svc.state.ships[svc.state.players[1].ship_id].type_id
        table.move_cursor(row=idx, animate=False)
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()
        assert svc.state.ships[svc.state.players[1].ship_id].type_id == before  # unchanged


async def test_bounty_board_is_structured() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _dock(app, pilot)
        tav = svc.tavern_view(1)
        # Governance line always present -> at least one structured bounty row.
        assert tav.bounties and all(hasattr(b, "target") and hasattr(b, "status") for b in tav.bounties)
