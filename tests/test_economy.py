"""WP2 — property-based economy invariants (DESIGN §8, §13).

Hypothesis covers the §8 invariants over arbitrary inputs: prices clamped and
positive, price monotonic in stock, the negative-feedback rule, goods conserved
across trades, and the player's latinum never going negative. Plus example-based
checks for haggling, banking, and stock regen.
"""

from __future__ import annotations

import math
import random

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from edge.core.economy import (
    EconomyError,
    HaggleStatus,
    accrue_interest,
    deposit,
    execute_trade,
    haggle_acceptance_probability,
    port_unit_price,
    quoted_unit_price,
    regenerate_stock,
    resolve_haggle,
    withdraw,
)
from edge.core.enums import Commodity, PortClass, PortMode
from edge.core.models import Player, Port, PortCommodity, Ship

# --- strategies -------------------------------------------------------------

bases = st.floats(min_value=1.0, max_value=1000.0)
deltas = st.floats(min_value=0.0, max_value=1000.0)
elasticities = st.floats(min_value=0.0, max_value=5.0)
fracs_floor = st.floats(min_value=0.0, max_value=0.9)
fracs_ceiling = st.floats(min_value=1.0, max_value=4.0)
capacities = st.integers(min_value=1, max_value=4_000_000)
modes = st.sampled_from([PortMode.BUY, PortMode.SELL])


def _line(mode: PortMode, stock: int, capacity: int, base: float, delta: float) -> PortCommodity:
    return PortCommodity(Commodity.FUEL_ORE, mode, stock, capacity, base, delta)


# --- pricing invariants -----------------------------------------------------


@given(
    mode=modes, capacity=capacities, base=bases, delta=deltas, elasticity=elasticities,
    floor_frac=fracs_floor, ceiling_frac=fracs_ceiling, data=st.data(),
)
def test_price_is_clamped_and_positive(
    mode: PortMode, capacity: int, base: float, delta: float, elasticity: float,
    floor_frac: float, ceiling_frac: float, data: st.DataObject,
) -> None:
    stock = data.draw(st.integers(min_value=0, max_value=capacity))
    price = quoted_unit_price(
        _line(mode, stock, capacity, base, delta),
        elasticity=elasticity, floor_frac=floor_frac, ceiling_frac=ceiling_frac,
    )
    assert price >= 1  # always positive
    assert price <= math.ceil(ceiling_frac * base)  # never above the ceiling


@given(
    mode=modes, capacity=capacities, base=bases, delta=deltas, elasticity=elasticities,
    data=st.data(),
)
def test_price_non_increasing_in_stock(
    mode: PortMode, capacity: int, base: float, delta: float, elasticity: float,
    data: st.DataObject,
) -> None:
    lo = data.draw(st.integers(min_value=0, max_value=capacity))
    hi = data.draw(st.integers(min_value=lo, max_value=capacity))
    kw = dict(elasticity=elasticity, floor_frac=0.25, ceiling_frac=2.0)
    p_lo = quoted_unit_price(_line(mode, lo, capacity, base, delta), **kw)
    p_hi = quoted_unit_price(_line(mode, hi, capacity, base, delta), **kw)
    assert p_lo >= p_hi  # more stock never costs more


@given(capacity=capacities, base=bases, delta=deltas, elasticity=elasticities, data=st.data())
def test_negative_feedback_rule(
    capacity: int, base: float, delta: float, elasticity: float, data: st.DataObject,
) -> None:
    stock = data.draw(st.integers(min_value=1, max_value=capacity - 1)) if capacity > 1 else 1
    assume(0 < stock < capacity)
    kw = dict(elasticity=elasticity, floor_frac=0.25, ceiling_frac=2.0)
    # Buying from a port lowers its stock -> its SELL price must not drop.
    sell_before = quoted_unit_price(_line(PortMode.SELL, stock, capacity, base, delta), **kw)
    sell_after = quoted_unit_price(_line(PortMode.SELL, stock - 1, capacity, base, delta), **kw)
    assert sell_after >= sell_before
    # Selling into a port raises its stock -> its BUY price must not rise.
    buy_before = quoted_unit_price(_line(PortMode.BUY, stock, capacity, base, delta), **kw)
    buy_after = quoted_unit_price(_line(PortMode.BUY, stock + 1, capacity, base, delta), **kw)
    assert buy_after <= buy_before


# --- trade resolution invariants --------------------------------------------


def _port(mode: PortMode, stock: int, capacity: int = 1000) -> Port:
    return Port(
        id=1, sector_id=3, name="Test", klass=PortClass.CLASS_1, size=capacity // 1000 or 1,
        commodities=(_line(mode, stock, capacity, 11, 5),),
    )


def _ship(cargo: int = 0, holds: int = 60) -> Ship:
    c = {Commodity.FUEL_ORE: cargo} if cargo else {}
    return Ship(id=1, type_id="t", name="s", owner_player_id=1, sector_id=3, holds_total=holds, cargo=c)


def _player(latinum: int = 10_000) -> Player:
    return Player(id=1, name="you", ship_id=1, latinum=latinum)


# deadline disabled: a 40-step pure-arithmetic loop is timing-irrelevant to the
# invariant under test, but coverage instrumentation can push a single example
# past hypothesis's 200ms per-example deadline (a spurious failure).
@settings(deadline=None)
@given(actions=st.lists(st.tuples(st.booleans(), st.integers(1, 30)), max_size=40))
def test_goods_conserved_and_balance_non_negative_over_sequence(
    actions: list[tuple[bool, int]],
) -> None:
    capacity = 1000
    # A class-1 port BUYS fuel ore; flip a copy to SELL for the buy side.
    sell_port = _port(PortMode.SELL, stock=500, capacity=capacity)
    buy_port = _port(PortMode.BUY, stock=500, capacity=capacity)
    ship = _ship(cargo=100, holds=400)
    player = _player(50_000)

    for is_buy, units in actions:
        port = sell_port if is_buy else buy_port
        line = port.commodities[0]
        total_goods = line.stock + ship.cargo.get(Commodity.FUEL_ORE, 0)
        price = port_unit_price(line, _default_econ())
        try:
            out = execute_trade(
                port=port, ship=ship, player=player,
                commodity=Commodity.FUEL_ORE, units=units, unit_price=price,
            )
        except EconomyError:
            continue  # rejected trades leave state untouched
        # Goods conserved across the transfer.
        after = out.port.commodities[0].stock + out.ship.cargo.get(Commodity.FUEL_ORE, 0)
        assert after == total_goods
        assert out.player.latinum >= 0  # never negative
        assert 0 <= out.port.commodities[0].stock <= capacity
        assert out.ship.holds_used <= out.ship.holds_total
        ship, player = out.ship, out.player
        if is_buy:
            sell_port = out.port
        else:
            buy_port = out.port


def test_trade_rejects_unaffordable_and_overspend() -> None:
    port = _port(PortMode.SELL, stock=100)
    ship = _ship(holds=60)
    poor = _player(latinum=5)  # can't afford even 1 unit at ~11/unit
    with pytest.raises(EconomyError):
        execute_trade(port=port, ship=ship, player=poor,
                      commodity=Commodity.FUEL_ORE, units=1, unit_price=11)


def _default_econ() -> object:  # tiny shim so the property test reads cleanly
    from edge.config import load_default_config

    return load_default_config().economy


# --- haggling ---------------------------------------------------------------


def test_haggle_insult_aborts() -> None:
    # Offering 50% under fair on a buy exceeds the 0.30 insult threshold.
    p = haggle_acceptance_probability(
        fair=100, counter=50, mode=PortMode.SELL,
        insult_frac=0.30, history_penalty=0.0, recent_attempts=0,
    )
    assert p is None


def test_haggle_fair_or_better_for_port_always_accepts() -> None:
    p = haggle_acceptance_probability(
        fair=100, counter=100, mode=PortMode.SELL,
        insult_frac=0.30, history_penalty=0.0, recent_attempts=0,
    )
    assert p == 1.0


@given(
    fair=st.integers(1, 1000), counter=st.integers(0, 2000), mode=modes,
    insult=st.floats(0.01, 0.5), pen=st.floats(0.0, 0.3), attempts=st.integers(0, 10),
)
def test_haggle_probability_in_unit_interval(
    fair: int, counter: int, mode: PortMode, insult: float, pen: float, attempts: int,
) -> None:
    p = haggle_acceptance_probability(
        fair, counter, mode, insult_frac=insult, history_penalty=pen, recent_attempts=attempts,
    )
    assert p is None or 0.0 <= p <= 1.0


def test_resolve_haggle_is_deterministic_per_seed() -> None:
    kw = dict(insult_frac=0.30, history_penalty=0.0, recent_attempts=0)
    a = resolve_haggle(100, 80, PortMode.SELL, random.Random(7), **kw)
    b = resolve_haggle(100, 80, PortMode.SELL, random.Random(7), **kw)
    assert a == b
    assert a.status in {HaggleStatus.ACCEPTED, HaggleStatus.REJECTED}


# --- banking & regen --------------------------------------------------------


def test_deposit_withdraw_conserve_total_and_reject_overdraw() -> None:
    p = _player(latinum=1_000)
    p2 = deposit(p, 600)
    assert (p2.latinum, p2.bank_balance) == (400, 600)
    assert p2.latinum + p2.bank_balance == 1_000
    p3 = withdraw(p2, 600)
    assert (p3.latinum, p3.bank_balance) == (1_000, 0)
    with pytest.raises(EconomyError):
        withdraw(p3, 1)  # empty bank


def test_interest_grows_balance() -> None:
    assert accrue_interest(10_000, 0.005) == 10_050
    assert accrue_interest(0, 0.005) == 0


def test_banking_error_paths() -> None:
    p = _player(latinum=100)
    for bad in (deposit, withdraw):
        with pytest.raises(EconomyError):
            bad(p, 0)  # non-positive
    with pytest.raises(EconomyError):
        deposit(p, 1_000)  # more than on hand
    with pytest.raises(EconomyError):
        withdraw(p, 1)  # empty bank


def test_resolve_haggle_insult_aborts() -> None:
    r = resolve_haggle(
        100, 40, PortMode.SELL, random.Random(0),
        insult_frac=0.30, history_penalty=0.0, recent_attempts=0,
    )
    assert r.status is HaggleStatus.INSULTING and r.price is None


def test_trade_rejects_oversell_and_over_capacity() -> None:
    buy_port = _port(PortMode.BUY, stock=995, capacity=1000)  # near full
    ship = _ship(cargo=2, holds=60)
    player = _player(1_000)
    # Selling more than held.
    with pytest.raises(EconomyError):
        execute_trade(port=buy_port, ship=ship, player=player,
                      commodity=Commodity.FUEL_ORE, units=50, unit_price=11)
    # Selling more than the port can absorb (stock would exceed capacity).
    full_ship = _ship(cargo=100, holds=200)
    with pytest.raises(EconomyError):
        execute_trade(port=buy_port, ship=full_ship, player=player,
                      commodity=Commodity.FUEL_ORE, units=20, unit_price=11)


def test_trade_rejects_nonpositive_units() -> None:
    with pytest.raises(EconomyError):
        execute_trade(port=_port(PortMode.SELL, 100), ship=_ship(), player=_player(),
                      commodity=Commodity.FUEL_ORE, units=0, unit_price=11)


@given(stock=st.integers(0, 1000), data=st.data())
def test_regen_moves_toward_desired_and_stays_in_bounds(
    stock: int, data: st.DataObject,
) -> None:
    new = regenerate_stock(stock, 1000, desired_frac=0.5, regen_frac=0.05)
    assert 0 <= new <= 1000
    desired = 500
    # The new stock is no further from desired than the old (moves toward it).
    assert abs(new - desired) <= abs(stock - desired)


# --- WP43: NPC-trader goods conservation ------------------------------------


def _npc_state(port: Port, sp: object) -> object:
    """A minimal universe holding one port + one merchant, for `npc.plan_trade`."""
    from edge.core.models import Game, UniverseState

    state = UniverseState.new(Game(1, 1, 1, "t"))
    state.ports = {port.id: port}
    state.species = {sp.id: sp}  # type: ignore[attr-defined]
    return state


@given(
    sell_stock=st.integers(0, 1000), sell_base=st.floats(1.0, 50.0), sell_delta=st.floats(0.0, 50.0),
    buy_stock=st.integers(0, 1000), buy_base=st.floats(1.0, 50.0), buy_delta=st.floats(0.0, 50.0),
    cash=st.integers(0, 100_000), held=st.integers(0, 500),
)
@settings(max_examples=300)
def test_npc_trade_conserves_goods(
    sell_stock: int, sell_base: float, sell_delta: float,
    buy_stock: int, buy_base: float, buy_delta: float, cash: int, held: int,
) -> None:
    """An NPC trade moves goods between port and merchant without minting or losing any —
    the §8 conservation invariant, now for the WP43 trader path (`core.npc.plan_trade`)."""
    from edge.config import load_default_config
    from edge.core import npc
    from edge.core.models import AlienSpecies

    config = load_default_config()
    port = Port(id=1, sector_id=2, name="Mkt", klass=PortClass.CLASS_1, size=1, commodities=(
        PortCommodity(Commodity.FUEL_ORE, PortMode.SELL, sell_stock, 1000, sell_base, sell_delta),
        PortCommodity(Commodity.ORGANICS, PortMode.BUY, buy_stock, 1000, buy_base, buy_delta),
    ))
    sp = AlienSpecies(
        id=1, roster_id="selvani", name="S", archetype_id="a", sector_id=2,
        home_band="Frontier", tech_level=5, base_disposition=0.5,
        disposition_center=0.5, disposition_variance=0.05,
        cash=cash, cargo={Commodity.ORGANICS: held} if held else {})
    state = _npc_state(port, sp)

    trade = npc.plan_trade(state, sp, config)  # type: ignore[arg-type]
    if trade is None:
        return
    old_line = port.line(trade.commodity)
    new_line = trade.port.line(trade.commodity)
    assert old_line is not None and new_line is not None
    old_qty = sp.cargo.get(trade.commodity, 0)
    new_qty = trade.species.cargo.get(trade.commodity, 0)
    # Goods conserved: what leaves the port enters the hold (and vice versa).
    assert old_line.stock + old_qty == new_line.stock + new_qty
    # Invariants: purse never negative; port stock stays within its capacity.
    assert trade.species.cash >= 0
    assert 0 <= new_line.stock <= new_line.capacity
    assert trade.units > 0
