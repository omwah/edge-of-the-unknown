"""GW-WP20 — the protectorate/annexation player surface (GW-WP12-FU1's second gap).

`AnnexProtectorate` and the D13 administration rights have been in core since GW-WP11,
but nothing projected or offered them: `PlanetDTO` carried no protectorate fields and no
screen could annex, read the controller's share, or see the D14 gate.

Two halves are covered here. **Projection** proves `planet_view` reports what the reducer
would do — the same `annex_ready` sentence, the share ledger a load actually draws from,
and nothing about another controller's share. **Presentation** proves the orbit screen and
the transfer workbench act on that projection rather than on the sovereign-ownership
assumptions they were written under: a protectorate's treasury buttons are gone (banking
is sovereign-only), its stores table separates the two ledgers, and the workbench clamps
loads to the share instead of the inhabitants' stores.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest

from edge.config import load_default_config
from edge.core.dto import PlanetDTO
from edge.core.economy import EconomyError
from edge.core.enums import Commodity
from edge.core.models import (
    Game,
    Ownership,
    Planet,
    Player,
    Sector,
    Ship,
    UniverseState,
)
from edge.core.rules import AnnexProtectorate, apply_result, reduce
from edge.server import session
from edge.tui.app import EdgeApp
from edge.tui.saves import clear_slot
from edge.tui.screens.planet import PlanetScreen
from edge.tui.screens.transfer import TransferWorkbenchScreen

CFG = load_default_config()
SETTLE = CFG.groundwar.settlement  # type: ignore[union-attr]
MIN_DAYS = SETTLE.protectorate_min_days
RESOLVE_GATE = SETTLE.annex_resolve_threshold


# --- state helpers -----------------------------------------------------------


def _state(planet: Planet, *, day: int = 100) -> UniverseState:
    """A one-sector universe holding `planet`, with player 1 in orbit over it."""
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t", day_number=day))
    state.sectors = {1: Sector(1, 1, (), "Frontier")}
    state.rebuild_adjacency()
    state.planets = {planet.id: planet}
    state.ships = {1: Ship(id=1, type_id="trailblazer", name="S.S.", owner_player_id=1,
                           sector_id=1, holds_total=60, turns_per_warp=1)}
    state.players = {1: Player(id=1, name="you", ship_id=1, latinum=10_000,
                               turns_remaining=250)}
    return state


def _protectorate(*, controller: int = 1, since: int = 0, resolve: int = RESOLVE_GATE,
                  share: dict[Commodity, int] | None = None) -> Planet:
    """An unaligned inhabited world under protectorate control (D2's exact shape).

    `owner` stays `none` — the native polity is retained — while the controller is
    recorded separately. That mutual exclusion is what lets the DTO derive "sovereign"
    as `owned_by_you and not protectorate`.
    """
    return Planet(
        id=1, sector_id=1, name="Kesh", planet_type="terrestrial_warm",
        habitability_cap=100_000, population={"vesk": 40_000},
        owner=Ownership("none"),
        protectorate_controller=Ownership("player", controller),
        protectorate_since=since,
        protectorate_stores=share if share is not None else {Commodity.FUEL_ORE: 120},
        stores={Commodity.FUEL_ORE: 9_000, Commodity.EQUIPMENT: 500},
        ground_resolve=resolve,
    )


# --- projection: what the controller is told ---------------------------------


def test_a_protectorate_projects_its_control_age_and_share() -> None:
    state = _state(_protectorate(since=90), day=100)
    view = session.planet_view(state, 1, 1, CFG)
    assert view.protectorate and view.protectorate_yours
    assert view.owner == "protectorate (yours)"
    assert view.protectorate_days == 10
    assert view.protectorate_share_pct == round(SETTLE.protectorate_production_share * 100)
    assert dict(view.protectorate_stores)["Fuel Ore"] == 120
    # The inhabitants' own stores stay theirs and stay visible — two ledgers, not one.
    assert dict(view.stores)["Fuel Ore"] == 9_000


def test_another_powers_protectorate_leaks_no_share_ledger() -> None:
    """A world someone else administers reads as held, but its books are not yours."""
    state = _state(_protectorate(controller=2, since=0))
    view = session.planet_view(state, 1, 1, CFG)
    assert view.protectorate and not view.protectorate_yours
    assert view.owner == "protectorate"
    assert view.protectorate_stores == []
    assert view.protectorate_days == 0 and view.protectorate_share_pct == 0
    assert not view.can_annex


def test_an_ordinary_world_is_not_a_protectorate() -> None:
    plain = Planet(id=1, sector_id=1, name="Eden", planet_type="terrestrial_warm",
                   habitability_cap=100_000, owner=Ownership("player", 1))
    view = session.planet_view(_state(plain), 1, 1, CFG)
    assert not view.protectorate and not view.protectorate_yours
    assert view.can_annex is False and view.annex_blocker == ""


# --- projection/reducer lockstep on the D14 gate -----------------------------


@pytest.mark.parametrize("since,resolve,expect", [
    (100, RESOLVE_GATE, "days"),                 # held zero days — the age gate
    (0, RESOLVE_GATE - 1, "Resolve"),            # battered — the recovery gate
])
def test_a_barred_annex_names_the_reducers_own_reason(
        since: int, resolve: int, expect: str) -> None:
    """The greyed line and the refusal are one sentence, not two paraphrases."""
    state = _state(_protectorate(since=since, resolve=resolve), day=100)
    view = session.planet_view(state, 1, 1, CFG)
    assert not view.can_annex
    assert expect in view.annex_blocker
    with pytest.raises(EconomyError) as exc:
        reduce(state, 1, AnnexProtectorate(planet_id=1), CFG)
    assert str(exc.value) == view.annex_blocker


def test_a_ready_protectorate_annexes_and_merges_its_share() -> None:
    state = _state(_protectorate(since=100 - MIN_DAYS, resolve=RESOLVE_GATE), day=100)
    view = session.planet_view(state, 1, 1, CFG)
    assert view.can_annex and view.annex_blocker == ""

    apply_result(state, reduce(state, 1, AnnexProtectorate(planet_id=1), CFG))
    planet = state.planets[1]
    assert planet.owner == Ownership("player", 1)
    assert not planet.protectorate_controller.is_owned
    # The controller's share becomes ordinary stores — nothing is minted or dropped (G8).
    assert planet.stores[Commodity.FUEL_ORE] == 9_000 + 120
    assert not planet.protectorate_stores

    after = session.planet_view(state, 1, 1, CFG)
    assert not after.protectorate and not after.can_annex
    assert after.owner == "you"


def test_annexing_from_another_sector_is_barred_in_both_places() -> None:
    """`planet_view` must not offer what `_annex_protectorate`'s in-sector gate refuses."""
    state = _state(_protectorate(since=100 - MIN_DAYS), day=100)
    state.sectors[2] = Sector(2, 1, (), "Frontier")
    state.rebuild_adjacency()
    state.ships[1] = replace(state.ships[1], sector_id=2)
    view = session.planet_view(state, 1, 1, CFG)
    assert not view.can_annex and "orbit" in view.annex_blocker
    with pytest.raises(EconomyError):
        reduce(state, 1, AnnexProtectorate(planet_id=1), CFG)


# --- the orbit screen ---------------------------------------------------------


def _dto(**kw: object) -> PlanetDTO:
    base: dict[str, object] = dict(
        planet_id=1, name="Kesh", ptype="terrestrial_warm", owner="protectorate (yours)",
        colonizable=True, claimable=False, owned_by_you=True, colonists=40_000,
        habitability_cap=100_000,
        stores=[("Fuel Ore", 9_000), ("Organics", 0), ("Equipment", 500)],
        allocation=[("Fuel Ore", 50), ("Organics", 25), ("Equipment", 25)],
        ship_colonists=0, ship_colonist_capacity=100, species="Vesk",
        protectorate=True, protectorate_yours=True, protectorate_days=MIN_DAYS,
        protectorate_share_pct=10,
        protectorate_stores=[("Fuel Ore", 120), ("Organics", 0), ("Equipment", 5)],
        ground_resolve=RESOLVE_GATE, annex_resolve_threshold=RESOLVE_GATE,
        can_annex=True, citadel_level=1, treasury=5_000,
    )
    base.update(kw)
    return PlanetDTO(**base)  # type: ignore[arg-type]


@asynccontextmanager
async def _orbit(planet: PlanetDTO,
                 size: tuple[int, int] = (100, 34)) -> AsyncIterator[PlanetScreen]:
    app = EdgeApp()
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        app.push_screen(PlanetScreen(planet))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, PlanetScreen)
        yield screen


def _text(screen: PlanetScreen) -> str:
    from textual.widgets import Static
    return " ".join(str(w.render()) for w in screen.query(Static))


@pytest.mark.parametrize("tier", [(80, 24), (100, 34), (160, 48)])
async def test_a_ready_protectorate_offers_annex_at_every_tier(
        tier: tuple[int, int]) -> None:
    async with _orbit(_dto(), tier) as screen:
        assert screen.query("#btn-annex")
        assert screen.check_action("annex", ()) is True


async def test_a_barred_annex_greys_the_button_and_says_why() -> None:
    blocker = f"protectorate must stand for {MIN_DAYS} days (1 elapsed)"
    async with _orbit(_dto(protectorate_days=1, can_annex=False,
                           annex_blocker=blocker)) as screen:
        assert not screen.query("#btn-annex")  # no button to press into a refusal
        assert blocker in _text(screen)
        # The key stays live: pressing it explains rather than doing nothing silently.
        assert screen.check_action("annex", ()) is True


async def test_annex_is_off_the_footer_on_a_world_that_is_not_your_protectorate() -> None:
    async with _orbit(_dto(protectorate=False, protectorate_yours=False,
                           protectorate_stores=[], can_annex=False,
                           owner="you")) as screen:
        assert screen.check_action("annex", ()) is False
        assert not screen.query("#btn-annex")


async def test_a_protectorate_separates_the_two_ledgers_and_hides_banking() -> None:
    """D13: their stores and treasury stay theirs; only the share is yours to draw."""
    async with _orbit(_dto()) as screen:
        table = screen.query_one("#stores-table")
        headers = [str(c.label) for c in table.columns.values()]  # type: ignore[attr-defined]
        assert headers == ["Commodity", "Their stores", "Your share", "Aboard"]
        # Banking is sovereign-only (`rules._planet_bank`), so the buttons must be gone.
        assert not screen.query("#btn-cit-dep")
        assert not screen.query("#btn-cit-wd")


async def test_an_owned_world_keeps_its_original_stores_table_and_banking() -> None:
    async with _orbit(_dto(protectorate=False, protectorate_yours=False,
                           protectorate_stores=[], can_annex=False,
                           owner="you")) as screen:
        table = screen.query_one("#stores-table")
        headers = [str(c.label) for c in table.columns.values()]  # type: ignore[attr-defined]
        assert headers == ["Commodity", "In stores", "Aboard"]
        assert screen.query("#btn-cit-dep") and screen.query("#btn-cit-wd")


# --- the transfer workbench ---------------------------------------------------


async def test_the_workbench_loads_from_the_share_not_the_colonys_stores() -> None:
    """The bug this WP closes: `_transfer_cargo` draws a controller's cargo from
    `protectorate_stores`, but the workbench showed and clamped against `stores` — so a
    9,000-unit colony offered a load the reducer would cut to 120."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        clear_slot()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        state = svc.state
        ship = state.ships[state.players[1].ship_id]
        pid = (max(state.planets) + 1) if state.planets else 1
        # A share deliberately smaller than the free holds, so the row's ceiling can only
        # have come from the share ledger — clamping to `stores` would leave it at the
        # holds instead, which is exactly the disagreement this WP removes.
        share = {Commodity.FUEL_ORE: 30}
        state.planets[pid] = replace(_protectorate(since=0, share=share), id=pid,
                                     sector_id=ship.sector_id)
        assert state.ships[ship.id].holds_free > 30
        app.push_screen(TransferWorkbenchScreen(svc, 1, pid))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, TransferWorkbenchScreen)

        # The row reads the share, and the stepper cannot be typed past it.
        row = screen.query_one("#stepper-fuel_ore")
        assert row.maximum == 30  # type: ignore[attr-defined]
        assert "your share 30" in _row_text(screen)

        # Loading everything offered moves exactly the share, leaving the natives' stores.
        screen._set_amount("fuel_ore", 30)  # type: ignore[attr-defined]
        screen._do_row("fuel_ore", to_planet=False)  # type: ignore[attr-defined]
        await pilot.pause()
        planet = svc.state.planets[pid]
        assert planet.protectorate_stores.get(Commodity.FUEL_ORE, 0) == 0
        assert planet.stores[Commodity.FUEL_ORE] == 9_000  # untouched — not yours to take
        assert svc.state.ships[ship.id].cargo.get(Commodity.FUEL_ORE, 0) >= 30


def _row_text(screen: TransferWorkbenchScreen) -> str:
    from textual.widgets import Static
    return " ".join(str(w.render()) for w in screen.query(Static))
