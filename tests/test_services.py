"""WP53 — the ServicePoint resolver and forward-base services (DESIGN §4.1, §4.2).

The resolver decides *which provider serves the ship's sector and at what fee*, so the
dock-service reducers run one code path against two providers (StarDock, player base).
These tests pin the resolver truth table, the fee/tier gating at a base, and that
StarDock behaviour is byte-identical (fee_frac 1.0) after the refactor.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.config import load_default_config
from edge.core.economy import EconomyError
from edge.core.engine_room import build_layouts
from edge.core.enums import Commodity, Component, ComponentTier, PortClass, PortMode, Subsystem
from edge.core.models import (
    Game,
    Ownership,
    Planet,
    Player,
    Port,
    PortCommodity,
    Sector,
    Ship,
    Starbase,
    UniverseState,
)
from edge.core.rules import BuyComponent, BuyMissiles, Deposit, apply_result, reduce
from edge.core.services import BANKING, COMPONENTS, MUNITIONS, REPAIR, service_point
from edge.server import session

CONFIG = load_default_config()


def _operational_base(sector_id: int, owner: Ownership) -> Starbase:
    """A fully-slotted (operational) orbital base owned by `owner` in `sector_id`."""
    assert CONFIG.starbase is not None
    subs = build_layouts(CONFIG.starbase.subsystems)
    return Starbase(id=1, sector_id=sector_id, planet_id=1,
                    ship_class_id="orbital_platform", owner=owner, subsystems=subs)


def _world(*, base_owner: Ownership, base_operational: bool = True) -> UniverseState:
    """Sectors 1(StarDock) <-> 2(base) <-> 3(empty); player at sector 2 with a base."""
    game = Game(id=1, seed=1, config_version=CONFIG.config_version, created_at="t")
    state = UniverseState.new(game)
    state.sectors = {
        1: Sector(1, 1, (2,), "Hub"),
        2: Sector(2, 1, (1, 3), "Hub"),
        3: Sector(3, 1, (2,), "Hub"),
    }
    state.rebuild_adjacency()
    state.ports = {
        1: Port(id=1, sector_id=1, name="StarDock", klass=PortClass.STARDOCK, size=1,
                commodities=(PortCommodity(Commodity.FUEL_ORE, PortMode.SELL, 500, 1000, 11, 5),)),
    }
    base = _operational_base(2, base_owner)
    if not base_operational:  # strip the reactor keystone → derelict
        reactor = base.subsystems[Subsystem.FUSION_REACTOR]
        slots = list(reactor.slots)
        slots[reactor.keystone_index] = None
        base = replace(base, subsystems={**base.subsystems,
                                         Subsystem.FUSION_REACTOR: replace(reactor, slots=tuple(slots))})
    state.starbases = {1: base}
    state.planets = {1: Planet(1, 2, "Foothold", "barren", starbase_id=1)}
    state.ships = {1: Ship(id=1, type_id="trailblazer", name="S.S.", owner_player_id=1,
                           sector_id=2, holds_total=60, turns_per_warp=1, shields=80)}
    state.players = {1: Player(id=1, name="you", ship_id=1, latinum=100_000, turns_remaining=250)}
    return state


def _sp(state: UniverseState):
    return service_point(state, state.players[1], state.ships[1], CONFIG)


def test_resolver_returns_player_base_for_an_owned_operational_base() -> None:
    state = _world(base_owner=Ownership("player", 1))
    sp = _sp(state)
    assert sp is not None and sp.kind == "player_base" and sp.ref == 1
    assert sp.services == {REPAIR, COMPONENTS, MUNITIONS, BANKING}
    assert sp.fee_frac == CONFIG.starbase.services.fee_frac  # type: ignore[union-attr]


def test_resolver_ignores_a_derelict_or_rival_base() -> None:
    # Derelict (not operational): no service point.
    assert _sp(_world(base_owner=Ownership("player", 1), base_operational=False)) is None
    # Owned by an alliance, not the player: no service point.
    assert _sp(_world(base_owner=Ownership("alliance", 2))) is None
    # Unowned: no service point.
    assert _sp(_world(base_owner=Ownership("none"))) is None


def test_resolver_prefers_stardock_and_charges_no_markup() -> None:
    state = _world(base_owner=Ownership("player", 1))
    state.ships[1] = replace(state.ships[1], sector_id=1)  # move to the StarDock sector
    sp = _sp(state)
    assert sp is not None and sp.kind == "stardock" and sp.fee_frac == 1.0


def test_resolver_none_in_an_empty_sector() -> None:
    state = _world(base_owner=Ownership("player", 1))
    state.ships[1] = replace(state.ships[1], sector_id=3)
    assert _sp(state) is None


def test_buy_component_at_base_applies_markup_and_tier_cap() -> None:
    state = _world(base_owner=Ownership("player", 1))
    econ = CONFIG.economy
    tier_i_price = econ.component_price(ComponentTier.I)
    assert tier_i_price is not None
    before = state.players[1].latinum
    res = reduce(state, 1, BuyComponent(Component.ACCELERATOR, ComponentTier.I), CONFIG)
    apply_result(state, res)
    spent = before - state.players[1].latinum
    assert spent == round(tier_i_price * CONFIG.starbase.services.fee_frac)  # type: ignore[union-attr]
    # Tier III is barter-only everywhere; a base also refuses tiers outside its stock list.
    with pytest.raises(EconomyError):
        reduce(state, 1, BuyComponent(Component.ACCELERATOR, ComponentTier.III), CONFIG)


def test_munitions_gated_by_the_service_point() -> None:
    # In an empty sector, munitions resupply is rejected (no provider).
    empty = _world(base_owner=Ownership("player", 1))
    empty.ships[1] = replace(empty.ships[1], sector_id=3)
    with pytest.raises(EconomyError):
        reduce(empty, 1, BuyMissiles(count=1), CONFIG)
    # At the player base, resupply succeeds at the frontier markup.
    at_base = _world(base_owner=Ownership("player", 1))
    before = at_base.players[1].latinum
    apply_result(at_base, reduce(at_base, 1, BuyMissiles(count=1), CONFIG))
    spent = before - at_base.players[1].latinum
    assert spent == round(CONFIG.combat.missile_price * CONFIG.starbase.services.fee_frac)  # type: ignore[union-attr]


def test_banking_stays_ungated_but_is_a_listed_base_service() -> None:
    # Banking is reachable anywhere (the plan's "rejection conditions only widen" rule),
    # yet still advertised as a service at a player base.
    empty = _world(base_owner=Ownership("player", 1))
    empty.ships[1] = replace(empty.ships[1], sector_id=3)
    apply_result(empty, reduce(empty, 1, Deposit(amount=1000), CONFIG))
    assert empty.players[1].bank_balance == 1000
    at_base = _world(base_owner=Ownership("player", 1))
    sp = _sp(at_base)
    assert sp is not None and BANKING in sp.services


def test_starbase_view_matches_resolver() -> None:
    state = _world(base_owner=Ownership("player", 1))
    view = session.starbase_view(state, 1, 1, CONFIG)
    assert view.standing == "yours"
    assert set(view.services) == {REPAIR, COMPONENTS, MUNITIONS, BANKING}
    # Only stocked tiers appear, at the markup.
    tiers = {item.tier for item in view.hardware}
    assert tiers <= set(CONFIG.starbase.services.component_stock_tiers)  # type: ignore[union-attr]


def test_starbase_view_gates_services_and_station_by_standing() -> None:
    # A derelict: station ops (salvage + keystone-first repair slots), no services.
    derelict = _world(base_owner=Ownership("none"), base_operational=False)
    view = session.starbase_view(derelict, 1, 1, CONFIG)
    assert view.standing == "derelict" and not view.operational
    assert view.salvage and view.empty_slots and view.empty_slots[0][2]  # keystone first
    assert not view.services and not view.hardware
    assert not view.market_open  # no port in the fixture sector → closed with a notice
    # An alliance base at neutral standing: open, but no station ops or services.
    friendly = _world(base_owner=Ownership("alliance", 2))
    view = session.starbase_view(friendly, 1, 1, CONFIG)
    assert view.standing == "open"
    assert not view.salvage and not view.empty_slots and not view.services
    assert view.assaultable  # razing a bloc's base stays the coin of diplomacy
