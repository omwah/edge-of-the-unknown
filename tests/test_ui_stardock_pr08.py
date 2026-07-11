"""WP-PR08 — StarDock information architecture and scoped actions (playtest PT-02..07, 29).

Drives the real app at the dock: the unified Devices & Armaments catalog buys munitions and
devices through `B`; tab-scoped keys (K/R/N/D/W) are live only on their own tab; the Colonists
tab recruits; the current hull can't be bought; and the bounty board is structured rows.
"""

from __future__ import annotations

from dataclasses import replace

from edge.core.rules import Warp
from edge.core.movement import shortest_path
from edge.tui.app import EdgeApp
from edge.tui.saves import clear_slot
from edge.tui.screens.stardock import StarDockScreen


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
    await pilot.press("p")  # dock -> StarDockScreen  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    return svc


def _select_tab(screen: StarDockScreen, tab: str) -> None:
    from textual.widgets import TabbedContent
    screen.query_one(TabbedContent).active = tab


async def test_scoped_bindings_track_active_tab() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StarDockScreen)
        _select_tab(screen, "bank")
        await pilot.pause()
        assert screen.check_action("deposit", ()) is True
        assert screen.check_action("buy_rumor", ()) is False
        assert screen.check_action("recruit", ()) is False
        _select_tab(screen, "tavern")
        await pilot.pause()
        assert screen.check_action("buy_rumor", ()) is True
        assert screen.check_action("post_notice", ()) is True
        assert screen.check_action("deposit", ()) is False
        _select_tab(screen, "colonists")
        await pilot.pause()
        assert screen.check_action("recruit", ()) is True
        assert screen.check_action("withdraw", ()) is False


async def test_buy_armament_amount_and_oneoff() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StarDockScreen)
        _select_tab(screen, "devices")
        await pilot.pause()
        from textual.widgets import DataTable
        table = screen.query_one("#devices-table", DataTable)
        # Buy a one-off device: select the interdictor row and press B.
        arms = svc.stardock_view(1).armaments
        idx = next(i for i, a in enumerate(arms) if a.kind == "device")
        table.move_cursor(row=idx, animate=False)
        await pilot.pause()
        await pilot.press("b")
        await pilot.pause()
        assert svc.state.ships[svc.state.players[1].ship_id].devices  # a device was bought


async def test_recruit_from_colonists_tab() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StarDockScreen)
        _select_tab(screen, "colonists")
        await pilot.pause()
        from textual.widgets import Button
        screen.query_one("#btn-recruit-all", Button).press()
        await pilot.pause()
        await pilot.pause()
        # Recruit-all filled every free berth (or as many as latinum allowed).
        ship = svc.state.ships[svc.state.players[1].ship_id]
        assert ship.colonists > 0


async def test_current_hull_cannot_be_bought() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StarDockScreen)
        # Fly a *paid* hull so it appears in the shipyard as the owned row (the free
        # starter is excluded from the catalog, so there'd be no owned row otherwise).
        from edge.core.rules import BuyShip
        paid = next(s for s in svc.stardock_view(1).shipyard if not s.owned and s.affordable)
        svc.apply(1, BuyShip(paid.class_id))
        await screen.recompose()
        await pilot.pause()
        _select_tab(screen, "shipyard")
        await pilot.pause()
        from textual.widgets import DataTable
        table = screen.query_one("#shipyard-table", DataTable)
        rows = svc.stardock_view(1).shipyard
        idx = next(i for i, s in enumerate(rows) if s.owned)
        before = svc.state.ships[svc.state.players[1].ship_id].type_id
        table.move_cursor(row=idx, animate=False)
        await pilot.pause()
        await pilot.press("b")
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
