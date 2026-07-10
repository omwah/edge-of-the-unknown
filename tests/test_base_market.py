"""WP78 — base-hosted markets (DESIGN §4.2).

A port sharing its sector with an orbital starbase is *base-hosted*: the base is the
sector's trading post. These tests pin the access gate (dark while derelict, closed to
the owner's enemies, indifferent otherwise), the owner's commission on outsider trades
(paid from the port purse, never to yourself, clamped non-negative), and the big-bang
guarantee that every starbase sector holds a market port.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core.economy import EconomyError
from edge.core.engine_room import build_layouts
from edge.core.enums import Commodity, PortClass, PortMode, Subsystem
from edge.core.events import BaseCommission
from edge.core.models import (
    Corporation,
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
from edge.core.rules import Dock, Trade, apply_result, reduce

CONFIG = load_default_config()
CUT_FRAC = CONFIG.starbase.services.trade_cut_frac  # type: ignore[union-attr]


def _base(sector_id: int, owner: Ownership, *, operational: bool = True) -> Starbase:
    assert CONFIG.starbase is not None
    subs = build_layouts(CONFIG.starbase.subsystems)
    base = Starbase(id=1, sector_id=sector_id, planet_id=1,
                    ship_class_id="orbital_platform", owner=owner, subsystems=subs)
    if not operational:  # strip the reactor keystone → derelict
        reactor = base.subsystems[Subsystem.FUSION_REACTOR]
        slots = list(reactor.slots)
        slots[reactor.keystone_index] = None
        base = replace(base, subsystems={
            **base.subsystems, Subsystem.FUSION_REACTOR: replace(reactor, slots=tuple(slots))})
    return base


def _world(*, base_owner: Ownership, operational: bool = True) -> UniverseState:
    """Sector 2 holds a base-hosted port (SELL fuel ore); the player sits there."""
    game = Game(id=1, seed=1, config_version=CONFIG.config_version, created_at="t")
    state = UniverseState.new(game)
    state.sectors = {
        1: Sector(1, 1, (2,), "Hub"),
        2: Sector(2, 1, (1,), "Hub"),
    }
    state.rebuild_adjacency()
    state.ports = {
        1: Port(id=1, sector_id=2, name="Foothold Market", klass=PortClass.CLASS_2, size=2,
                commodities=(PortCommodity(Commodity.FUEL_ORE, PortMode.SELL, 500, 1000, 11, 5),),
                latinum=5_000),
    }
    state.starbases = {1: _base(2, base_owner, operational=operational)}
    state.planets = {1: Planet(1, 2, "Foothold", "barren", starbase_id=1)}
    state.ships = {
        1: Ship(id=1, type_id="trailblazer", name="Landlord", owner_player_id=1,
                sector_id=2, holds_total=60, turns_per_warp=1),
        2: Ship(id=2, type_id="trailblazer", name="Visitor", owner_player_id=2,
                sector_id=2, holds_total=60, turns_per_warp=1),
    }
    state.players = {
        1: Player(id=1, name="landlord", ship_id=1, latinum=100_000, turns_remaining=250),
        2: Player(id=2, name="visitor", ship_id=2, latinum=100_000, turns_remaining=250),
    }
    return state


# --- the access gate ----------------------------------------------------------


def test_derelict_base_market_is_dark() -> None:
    state = _world(base_owner=Ownership("none"), operational=False)
    with pytest.raises(EconomyError, match="dark"):
        reduce(state, 2, Trade(Commodity.FUEL_ORE, 5), CONFIG)
    with pytest.raises(EconomyError, match="dark"):
        reduce(state, 2, Dock(), CONFIG)


def test_hostile_owner_refuses_trade() -> None:
    state = _world(base_owner=Ownership("alliance", 7))
    state.players[2] = replace(state.players[2], alliance_standing={7: -1.0})
    with pytest.raises(EconomyError, match="refuses"):
        reduce(state, 2, Trade(Commodity.FUEL_ORE, 5), CONFIG)


def test_tolerated_player_trades_normally() -> None:
    # Neutral standing with the owning bloc: the market is open; no commission is
    # taken for an alliance host (the cut is a player/corp landlord's rent).
    state = _world(base_owner=Ownership("alliance", 7))
    res = reduce(state, 2, Trade(Commodity.FUEL_ORE, 5), CONFIG)
    apply_result(state, res)
    assert state.ships[2].cargo.get(Commodity.FUEL_ORE) == 5
    assert not [e for e in res.events if isinstance(e, BaseCommission)]


def test_unowned_operational_base_market_is_open() -> None:
    state = _world(base_owner=Ownership("none"))
    apply_result(state, reduce(state, 2, Trade(Commodity.FUEL_ORE, 5), CONFIG))
    assert state.ships[2].cargo.get(Commodity.FUEL_ORE) == 5


# --- the owner's cut ----------------------------------------------------------


def test_outsider_trade_pays_the_player_owner_from_the_purse() -> None:
    state = _world(base_owner=Ownership("player", 1))
    res = reduce(state, 2, Trade(Commodity.FUEL_ORE, 10), CONFIG)
    apply_result(state, res)
    cuts = [e for e in res.events if isinstance(e, BaseCommission)]
    assert len(cuts) == 1
    cut = cuts[0]
    total = next(e.total for e in res.events if type(e).__name__ == "Traded")
    assert cut.amount == round(total * CUT_FRAC)
    assert cut.owner_kind == "player" and cut.owner_ref == 1
    # Paid out of the port's purse into the landlord's bank — latinum conserved.
    assert state.players[1].bank_balance == cut.amount
    assert state.ports[1].latinum == 5_000 + total - cut.amount


def test_no_commission_on_the_owners_own_trades() -> None:
    state = _world(base_owner=Ownership("player", 1))
    res = reduce(state, 1, Trade(Commodity.FUEL_ORE, 10), CONFIG)
    apply_result(state, res)
    assert not [e for e in res.events if isinstance(e, BaseCommission)]
    assert state.players[1].bank_balance == 0


def test_corp_host_taxes_outsiders_but_not_members() -> None:
    state = _world(base_owner=Ownership("corp", 1))
    state.corporations = {1: Corporation(id=1, name="EotU", tag="EU", ceo_player_id=1,
                                         member_player_ids=frozenset({1}))}
    # A member trades free.
    member = reduce(state, 1, Trade(Commodity.FUEL_ORE, 5), CONFIG)
    assert not [e for e in member.events if isinstance(e, BaseCommission)]
    # An outsider pays the corp bank.
    res = reduce(state, 2, Trade(Commodity.FUEL_ORE, 10), CONFIG)
    apply_result(state, res)
    cuts = [e for e in res.events if isinstance(e, BaseCommission)]
    assert len(cuts) == 1 and cuts[0].owner_kind == "corp"
    assert state.corporations[1].bank_balance == cuts[0].amount


def test_commission_clamps_to_the_purse() -> None:
    # A near-empty purse cannot go negative: the cut clamps to what remains.
    state = _world(base_owner=Ownership("player", 1))
    state.ports[1] = replace(state.ports[1], latinum=0)
    res = reduce(state, 2, Trade(Commodity.FUEL_ORE, 10), CONFIG)
    apply_result(state, res)
    total = next(e.total for e in res.events if type(e).__name__ == "Traded")
    cuts = [e for e in res.events if isinstance(e, BaseCommission)]
    # The purse held only this trade's proceeds; the cut still fits inside them.
    assert cuts and cuts[0].amount <= total
    assert state.ports[1].latinum >= 0


# --- the big-bang guarantee ---------------------------------------------------


@pytest.mark.parametrize("seed", [3, 17, 99])
def test_every_starbase_sector_hosts_a_market(seed: int) -> None:
    state = generate(CONFIG, seed)
    assert state.starbases, "expected at least one starbase in a default universe"
    with_port = {p.sector_id for p in state.ports.values()}
    for base in state.starbases.values():
        assert base.sector_id in with_port
