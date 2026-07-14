"""Partial-fighter invasion (PT-53 / WP-PR2-14).

`InvadePlanet` has always taken an amount; the planet screen committed the whole wing, so a
failed assault cost every fighter aboard. The screen now opens an `AmountPrompt` (the quantity
sibling of `ConfirmScreen`) defaulting to all, clamped to `1..ship_fighters`.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from edge.core.dto import PlanetDTO
from edge.core.rules import InvadePlanet
from textual.widgets import Input

from edge.tui.amount_stepper import AmountStepper
from edge.tui.app import EdgeApp
from edge.tui.screens.amount import AmountPrompt
from edge.tui.screens.planet import PlanetScreen

HOSTILE_WORLD = PlanetDTO(
    planet_id=7, name="Karsk", ptype="terrestrial_cool", owner="Thessarch",
    colonizable=True, claimable=False, owned_by_you=False, colonists=40_000,
    habitability_cap=100_000, stores=[], allocation=[], ship_colonists=0,
    ship_colonist_capacity=100, can_invade=True, fighters=250, ship_fighters=400,
)


class RecordingPlanetService:
    def __init__(self) -> None:
        self.applied: list[object] = []

    def planet_view(self, player_id: int, planet_id: int) -> PlanetDTO:
        return HOSTILE_WORLD

    def game_view(self, player_id: int) -> SimpleNamespace:
        return SimpleNamespace(ship=SimpleNamespace(holds=[]))  # the stores panel reads holds

    def apply(self, player_id: int, command: object) -> tuple[object, ...]:
        self.applied.append(command)
        return ()


async def _open_invade(app: EdgeApp, service: RecordingPlanetService) -> None:
    app.push_screen(PlanetScreen(HOSTILE_WORLD, service, 1))  # type: ignore[arg-type]


async def test_invade_prompts_for_an_amount_and_commits_only_that_many() -> None:
    service = RecordingPlanetService()
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await _open_invade(app, service)
        await pilot.pause()

        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, AmountPrompt)

        # Defaults to the whole wing — the common case stays one keystroke away.
        stepper = app.screen.query_one(AmountStepper)
        assert stepper.amount == HOSTILE_WORLD.ship_fighters

        stepper.set_amount(120)  # hold a reserve back
        await pilot.click("#amount-commit")
        await pilot.pause()
        assert service.applied == [InvadePlanet(7, 120)]


async def test_the_prompt_clamps_to_the_fighters_aboard() -> None:
    service = RecordingPlanetService()
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await _open_invade(app, service)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        stepper = app.screen.query_one(AmountStepper)

        stepper.set_amount(10_000)  # more than you carry
        assert stepper.amount == HOSTILE_WORLD.ship_fighters
        stepper.set_amount(0)  # …and a landing of nobody is not a landing
        await pilot.click("#amount-commit")
        await pilot.pause()
        assert service.applied == [InvadePlanet(7, 1)]


async def test_all_key_refills_the_wing() -> None:
    service = RecordingPlanetService()
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await _open_invade(app, service)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        app.screen.query_one(AmountStepper).set_amount(5)
        await pilot.press("a")  # [A] all
        await pilot.pause()
        assert app.screen.query_one(AmountStepper).amount == HOSTILE_WORLD.ship_fighters


async def test_cancelling_the_prompt_lands_nobody() -> None:
    service = RecordingPlanetService()
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await _open_invade(app, service)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, PlanetScreen)
        assert service.applied == []


async def test_a_blocked_invasion_never_reaches_the_prompt() -> None:
    """The `can_invade` / `invade_blocker` gating still bars the attempt (regression)."""
    service = RecordingPlanetService()
    barred = dataclasses.replace(
        HOSTILE_WORLD, can_invade=False, invade_blocker="its shields are up")
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        app.push_screen(PlanetScreen(barred, service, 1))  # type: ignore[arg-type]
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, PlanetScreen)  # no prompt
        assert service.applied == []


async def test_a_stray_enter_lands_nobody() -> None:
    """An invasion is destructive, so the prompt opens on Cancel (the ConfirmScreen rule)."""
    service = RecordingPlanetService()
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await _open_invade(app, service)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        assert app.screen.focused is not None
        assert app.screen.focused.id == "amount-cancel"

        await pilot.press("enter")  # a stray Enter after the hotkey presses Cancel
        await pilot.pause()
        assert isinstance(app.screen, PlanetScreen)
        assert service.applied == []


async def test_enter_in_the_amount_field_commits_that_amount() -> None:
    """Typing a number and pressing Enter is unambiguous intent — it does not cancel."""
    service = RecordingPlanetService()
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await _open_invade(app, service)
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        field = app.screen.query_one(AmountStepper).query_one(Input)
        field.focus()
        await pilot.pause()
        field.value = "60"
        await pilot.press("enter")
        await pilot.pause()
        assert service.applied == [InvadePlanet(7, 60)]
