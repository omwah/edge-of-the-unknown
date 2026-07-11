"""WP-PR07 — the transfer workbench (playtest PT-10/PT-11).

One editor hauls goods between ship and colony and settles colonists onto an owned world
(the top-up the old flow rejected). Drives the real service: rows carry aboard/stores/berth
readouts, per-row Load/Unload apply through the reducer, and Load-all/Unload-all move
everything the holds and stores allow.
"""

from __future__ import annotations

from dataclasses import replace

from edge.core.enums import Commodity
from edge.core.models import Ownership, Planet
from edge.tui.app import EdgeApp
from edge.tui.saves import clear_slot
from edge.tui.screens.transfer import TransferWorkbenchScreen


async def _new_game(app: EdgeApp, pilot: object) -> object:
    clear_slot()
    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    return app.service


def _own_colony_here(svc: object) -> int:
    """Put a player-owned colony in the ship's sector; stock the ship with cargo + colonists."""
    state = svc.state  # type: ignore[attr-defined]
    ship = state.ships[state.players[1].ship_id]
    prof = svc._config.planets.types["terrestrial_warm"]  # type: ignore[attr-defined]
    pid = (max(state.planets) + 1) if state.planets else 1
    state.planets[pid] = Planet(
        id=pid, sector_id=ship.sector_id, name="Homestead", planet_type="terrestrial_warm",
        owner=Ownership("player", 1), colonists=100, habitability_cap=prof.habitability,
        stores={Commodity.EQUIPMENT: 40})
    state.ships[ship.id] = replace(
        ship, cargo={Commodity.FUEL_ORE: 30}, colonists=200, colonist_capacity=1000)
    return pid


async def test_settle_colonists_from_workbench() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game(app, pilot)
        pid = _own_colony_here(svc)
        app.push_screen(TransferWorkbenchScreen(svc, 1, pid))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, TransferWorkbenchScreen)
        # Type an exact colonist amount and settle it.
        screen._set_amount("colonists", 150)  # type: ignore[attr-defined]
        screen._do_row("colonists", to_planet=True)  # type: ignore[attr-defined]
        await pilot.pause()
        planet = svc.state.planets[pid]
        ship = svc.state.ships[svc.state.players[1].ship_id]
        assert planet.colonists == 250 and ship.colonists == 50


async def test_stepper_and_load_unload_all() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game(app, pilot)
        pid = _own_colony_here(svc)
        app.push_screen(TransferWorkbenchScreen(svc, 1, pid))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, TransferWorkbenchScreen)
        # The + stepper advances by 10 from 0.
        from textual.widgets import Button
        screen.query_one("#inc-fuel_ore", Button).press()
        await pilot.pause()
        assert screen._amount("fuel_ore") == 10  # type: ignore[attr-defined]
        # Unload all pushes every aboard commodity into stores.
        screen.action_unload_all()
        await pilot.pause()
        planet = svc.state.planets[pid]
        ship = svc.state.ships[svc.state.players[1].ship_id]
        assert planet.stores.get(Commodity.FUEL_ORE, 0) == 30  # the 30 fuel ore moved down
        assert ship.cargo.get(Commodity.FUEL_ORE, 0) == 0
        # Load all pulls it back into the holds.
        screen.action_load_all()
        await pilot.pause()
        ship = svc.state.ships[svc.state.players[1].ship_id]
        assert ship.cargo.get(Commodity.FUEL_ORE, 0) == 30


async def test_workbench_refused_on_unowned_world() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game(app, pilot)
        pid = _own_colony_here(svc)
        # Flip it unowned; the PlanetScreen's opener must refuse.
        svc.state.planets[pid] = replace(svc.state.planets[pid], owner=Ownership("none"))
        from edge.tui.screens.planet import PlanetScreen
        app.push_screen(PlanetScreen(svc.planet_view(1, pid), svc, 1))
        await pilot.pause()
        app.screen.action_transfer()  # type: ignore[attr-defined]
        await pilot.pause()
        # No workbench opened over an unowned world.
        assert not isinstance(app.screen, TransferWorkbenchScreen)


def _has_scrollable_ancestor(widget) -> bool:
    from textual.widget import Widget
    parent = widget.parent
    while isinstance(parent, Widget):
        if parent.is_scrollable:
            return True
        parent = parent.parent
    return False


async def test_workbench_controls_reachable_at_80x24() -> None:
    """WP-PR07 §8.1: every control in the transfer modal is on-screen or inside a
    keyboard-scrollable container at the compact 80x24 floor."""
    app = EdgeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        svc = await _new_game(app, pilot)
        pid = _own_colony_here(svc)
        app.push_screen(TransferWorkbenchScreen(svc, 1, pid))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, TransferWorkbenchScreen)
        region = screen.region
        for widget in screen.query("*"):
            if not widget.can_focus or not widget.display or widget.disabled:
                continue
            assert widget.region.intersection(region) or _has_scrollable_ancestor(widget), (
                f"transfer control {widget.id or type(widget).__name__} is off-screen "
                "with no scrollable ancestor at 80x24"
            )


async def test_enter_in_amount_field_submits_unload() -> None:
    """WP-PR07 §8.1: Enter in a commodity's amount field unloads it to the colony."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _new_game(app, pilot)
        pid = _own_colony_here(svc)
        app.push_screen(TransferWorkbenchScreen(svc, 1, pid))
        await pilot.pause()
        screen = app.screen
        from textual.widgets import Input
        field = screen.query_one("#amt-fuel_ore", Input)
        field.focus()
        field.value = "30"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        planet = svc.state.planets[pid]
        assert planet.stores.get(Commodity.FUEL_ORE, 0) == 30  # unloaded via Enter
