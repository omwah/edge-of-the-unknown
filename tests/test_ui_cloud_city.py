"""WP-PR2-15c — the Cloud City orbit screen (playtest PT-54).

A gas giant explains itself before it offers anything: until a staging area is built it shows
no stores table and no colony affordance, only the prerequisite and a `[S] Build staging area`
button gated on the projected blocker — the reducer's own words, so the greyed control and the
refusal can never say different things. Once staged, it reads as the colony it now is.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from edge.core.dto import PlanetDTO
from edge.tui.app import EdgeApp
from edge.tui.screens.planet import PlanetScreen

TIERS = [(80, 24), (100, 34), (160, 48)]  # compact · standard · wide


def _jovian(*, size: int = 0, blocker: str = "", equipment: int = 200,
            next_cost: int = 50) -> PlanetDTO:
    return PlanetDTO(
        planet_id=11, name="Bespin", ptype="jovian",
        owner="you" if size else "unowned",
        colonizable=size > 0, claimable=False, owned_by_you=size > 0,
        colonists=1_200 if size else 0, habitability_cap=size * 5_000,
        stores=[("Fuel Ore", 400)] if size else [], allocation=[],
        ship_colonists=0, ship_colonist_capacity=100,
        landable=True, extractable=True,
        cloud_city=True, cloud_city_size=size, cloud_city_max_size=4,
        cloud_city_next_cost=next_cost, cloud_city_blocker=blocker,
        ship_equipment=equipment,
    )


@asynccontextmanager
async def _orbit(planet: PlanetDTO,
                 size: tuple[int, int] = (100, 34)) -> AsyncIterator[PlanetScreen]:
    """Open the orbit view over `planet` at a terminal size, and hand back the live screen."""
    app = EdgeApp()
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        app.push_screen(PlanetScreen(planet))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, PlanetScreen)
        yield screen


@pytest.mark.parametrize("tier", TIERS)
async def test_an_unstaged_gas_giant_offers_the_build_and_no_stores(tier: tuple[int, int]) -> None:
    async with _orbit(_jovian(), tier) as screen:
        assert not screen.query("#stores-table")  # nothing can be stored yet — nothing is shown
        assert screen.query("#btn-build-city")    # the affordance *is* the prerequisite
        assert screen.check_action("build_city", ()) is True


@pytest.mark.parametrize("tier", TIERS)
async def test_a_staged_city_reads_as_the_colony_it_is(tier: tuple[int, int]) -> None:
    async with _orbit(_jovian(size=2, next_cost=150), tier) as screen:
        assert screen.query("#stores-table")     # stores exist now
        assert screen.query("#btn-build-city")   # …and the city can still grow
        assert screen.check_action("build_city", ()) is True


async def test_a_blocked_build_greys_the_button_and_says_why() -> None:
    blocker = "need 50 equipment aboard to build (have 10)"
    async with _orbit(_jovian(blocker=blocker, equipment=10)) as screen:
        assert not screen.query("#btn-build-city")  # no button to press into a refusal
        rendered = " ".join(str(getattr(w, "renderable", "")) for w in screen.query("Static"))
        assert blocker in rendered
        # The key stays live — pressing it explains, rather than doing nothing silently.
        assert screen.check_action("build_city", ()) is True


async def test_a_built_out_city_retires_the_verb() -> None:
    async with _orbit(_jovian(size=4, next_cost=0)) as screen:
        assert screen.check_action("build_city", ()) is False  # off the footer entirely
        assert not screen.query("#btn-build-city")


async def test_staging_is_not_offered_on_a_ground_world() -> None:
    terra = PlanetDTO(
        planet_id=12, name="Eden", ptype="terrestrial_warm", owner="unowned",
        colonizable=True, claimable=True, owned_by_you=False, colonists=0,
        habitability_cap=100_000, stores=[("Fuel Ore", 0)], allocation=[],
        ship_colonists=0, ship_colonist_capacity=50, landable=True, extractable=False)
    async with _orbit(terra) as screen:
        assert screen.check_action("build_city", ()) is False
        assert not screen.query("#btn-build-city")
        assert screen.query("#stores-table")
