"""WP-PR06 — the belt orbit screen hides colony/descent affordances (playtest PT-30).

A belt renders a spatial "orbit" readout, not the colony stores/citadel/descend controls of a
landable world, and its Descend binding is disabled so the footer never advertises a landing the
reducer would reject. Legality comes from the projected `landable`/`colonizable` capabilities,
never from a label.
"""

from __future__ import annotations

from edge.core.dto import PlanetDTO
from edge.tui.app import EdgeApp
from edge.tui.screens.planet import PlanetScreen


def _belt_dto() -> PlanetDTO:
    return PlanetDTO(
        planet_id=9, name="The Scatter", ptype="asteroid_belt", owner="unowned",
        colonizable=False, claimable=False, owned_by_you=False, colonists=0,
        habitability_cap=0, stores=[], allocation=[], ship_colonists=0,
        ship_colonist_capacity=50, landable=False, extractable=True,
    )


def _terrestrial_dto() -> PlanetDTO:
    return PlanetDTO(
        planet_id=10, name="Eden", ptype="terrestrial_warm", owner="unowned",
        colonizable=True, claimable=True, owned_by_you=False, colonists=0,
        habitability_cap=100000, stores=[("Fuel Ore", 0)], allocation=[],
        ship_colonists=0, ship_colonist_capacity=50, landable=True, extractable=False,
    )


async def test_belt_orbit_hides_descent_and_stores() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        app.push_screen(PlanetScreen(_belt_dto()))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, PlanetScreen)
        # Descend is barred (no surface) — the binding is inactive.
        assert screen.check_action("descend", ()) is False
        # The belt shows an orbital readout, not a colony stores table.
        assert screen.query("#orbital-panel")
        assert not screen.query("#stores-table")


async def test_terrestrial_orbit_keeps_descent_and_stores() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        app.push_screen(PlanetScreen(_terrestrial_dto()))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, PlanetScreen)
        assert screen.check_action("descend", ()) is True
        assert screen.query("#stores-table")
        assert not screen.query("#orbital-panel")
