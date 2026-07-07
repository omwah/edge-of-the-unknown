"""WP46 — order-book market core invariants (DESIGN §8, §13).

Hypothesis covers the H10 contracts over arbitrary books: settlement conserves
goods and latinum exactly, no fill exceeds purse/stock/capacity, the midpoint
price sits inside the crossed limits, and both generation and matching are
deterministic under dict-ordering permutations (the canonical sorts proven).
Example-based checks pin the dead band, the purse clamp, and the drips.
"""

from __future__ import annotations

import random
from dataclasses import replace

from hypothesis import given, settings
from hypothesis import strategies as st

from edge.core.config import EconomyConfig
from edge.core.enums import Commodity, PortClass, PortMode
from edge.core.market import (
    PortOrder,
    Settlement,
    clear_filled,
    desired_stock_frac,
    generate_orders,
    hinterland_drift,
    liquidity_drip,
    match_orders,
)
from edge.core.models import Game, Port, PortCommodity, UniverseState

ECON = EconomyConfig()

# --- fixtures ----------------------------------------------------------------


def _port(
    pid: int,
    *,
    size: int = 1,
    latinum: int = 10_000,
    stocks: dict[Commodity, int] | None = None,
    klass: PortClass = PortClass.CLASS_1,
) -> Port:
    capacity = size * 1000
    lines = tuple(
        PortCommodity(c, PortMode.SELL, (stocks or {}).get(c, capacity // 2), capacity, 11, 5)
        for c in Commodity
    )
    return Port(
        id=pid, sector_id=pid, name=f"P{pid}", klass=klass, size=size,
        commodities=lines, latinum=latinum,
    )


def _state(ports: dict[int, Port]) -> UniverseState:
    state = UniverseState.new(Game(1, 1, 1, "t"))
    state.ports = ports
    return state


# --- hypothesis strategies ----------------------------------------------------


@st.composite
def books(draw: st.DrawFn) -> tuple[dict[int, Port], dict[int, tuple[PortOrder, ...]]]:
    """Arbitrary ports plus an arbitrary (book-shaped) set of open orders.

    Shape matches `generate_orders`' contract — at most one order per
    (port, commodity, side) — but quantities, limits, purses, and stocks are
    unconstrained, so matching must survive books generation would never post.
    """
    n_ports = draw(st.integers(min_value=2, max_value=6))
    ports: dict[int, Port] = {}
    orders: dict[int, tuple[PortOrder, ...]] = {}
    for pid in range(1, n_ports + 1):
        size = draw(st.integers(min_value=1, max_value=5))
        capacity = size * 1000
        stocks = {c: draw(st.integers(min_value=0, max_value=capacity)) for c in Commodity}
        ports[pid] = _port(
            pid, size=size, latinum=draw(st.integers(min_value=0, max_value=50_000)),
            stocks=stocks,
        )
        port_orders: list[PortOrder] = []
        for commodity in Commodity:
            for side in ("buy", "sell"):
                if draw(st.booleans()):
                    port_orders.append(PortOrder(
                        pid, commodity, side,  # type: ignore[arg-type]
                        qty=draw(st.integers(min_value=1, max_value=capacity)),
                        limit=draw(st.integers(min_value=1, max_value=40)),
                    ))
        if port_orders:
            orders[pid] = tuple(port_orders)
    return ports, orders


# --- settlement invariants (H10/§13) ------------------------------------------


def _apply(ports: dict[int, Port], settlement: Settlement) -> dict[int, Port]:
    """Apply the settlement deltas the way the WP47 reducer will."""
    out: dict[int, Port] = {}
    for pid, port in ports.items():
        per_port = settlement.stock_deltas.get(pid, {})
        lines = tuple(
            replace(line, stock=line.stock + per_port.get(line.commodity, 0))
            for line in port.commodities
        )
        out[pid] = replace(
            port, commodities=lines,
            latinum=port.latinum + settlement.latinum_deltas.get(pid, 0),
        )
    return out


@settings(deadline=None)
@given(book=books())
def test_settlement_conserves_goods_and_latinum(
    book: tuple[dict[int, Port], dict[int, tuple[PortOrder, ...]]],
) -> None:
    ports, orders = book
    settlement = match_orders(orders, ports, ECON)
    for commodity in Commodity:
        assert sum(d.get(commodity, 0) for d in settlement.stock_deltas.values()) == 0
    assert sum(settlement.latinum_deltas.values()) == 0
    # Totals across all ports are unchanged after applying the deltas.
    after = _apply(ports, settlement)
    for commodity in Commodity:
        before_total = sum(p.line(commodity).stock for p in ports.values())  # type: ignore[union-attr]
        after_total = sum(p.line(commodity).stock for p in after.values())  # type: ignore[union-attr]
        assert before_total == after_total
    assert sum(p.latinum for p in ports.values()) == sum(p.latinum for p in after.values())


@settings(deadline=None)
@given(book=books())
def test_no_fill_exceeds_purse_stock_or_capacity(
    book: tuple[dict[int, Port], dict[int, tuple[PortOrder, ...]]],
) -> None:
    ports, orders = book
    after = _apply(ports, match_orders(orders, ports, ECON))
    for port in after.values():
        assert port.latinum >= 0  # no purse overdrawn
        for line in port.commodities:
            assert 0 <= line.stock <= line.capacity  # no oversell, no overflow


@settings(deadline=None)
@given(book=books())
def test_fill_price_is_midpoint_within_crossed_limits(
    book: tuple[dict[int, Port], dict[int, tuple[PortOrder, ...]]],
) -> None:
    ports, orders = book

    def order_of(pid: int, commodity: Commodity, side: str) -> PortOrder:
        (order,) = [
            o for o in orders.get(pid, ()) if o.commodity is commodity and o.side == side
        ]
        return order

    settlement = match_orders(orders, ports, ECON)
    for fill in settlement.fills:
        buy = order_of(fill.buyer_port_id, fill.commodity, "buy")
        sell = order_of(fill.seller_port_id, fill.commodity, "sell")
        assert sell.limit <= fill.unit_price <= buy.limit
        assert fill.unit_price == (buy.limit + sell.limit) // 2
        assert fill.qty >= 1 and fill.unit_price >= 1


@settings(deadline=None)
@given(book=books())
def test_no_order_overfills_its_quantity(
    book: tuple[dict[int, Port], dict[int, tuple[PortOrder, ...]]],
) -> None:
    ports, orders = book
    settlement = match_orders(orders, ports, ECON)
    filled: dict[tuple[int, Commodity, str], int] = {}
    for fill in settlement.fills:
        filled[fill.buyer_port_id, fill.commodity, "buy"] = (
            filled.get((fill.buyer_port_id, fill.commodity, "buy"), 0) + fill.qty
        )
        filled[fill.seller_port_id, fill.commodity, "sell"] = (
            filled.get((fill.seller_port_id, fill.commodity, "sell"), 0) + fill.qty
        )
    for port_orders in orders.values():
        for order in port_orders:
            assert filled.get((order.port_id, order.commodity, order.side), 0) <= order.qty


@settings(deadline=None)
@given(book=books(), seed=st.integers(min_value=0, max_value=2**16))
def test_matching_is_deterministic_under_dict_permutation(
    book: tuple[dict[int, Port], dict[int, tuple[PortOrder, ...]]], seed: int,
) -> None:
    ports, orders = book
    baseline = match_orders(orders, ports, ECON)
    shuffler = random.Random(seed)
    port_keys = list(ports)
    order_keys = list(orders)
    shuffler.shuffle(port_keys)
    shuffler.shuffle(order_keys)
    permuted = match_orders(
        {k: orders[k] for k in order_keys}, {k: ports[k] for k in port_keys}, ECON
    )
    assert permuted == baseline


# --- order generation (§8) -----------------------------------------------------


def test_generation_is_rng_free_and_idempotent() -> None:
    state = _state({
        1: _port(1, stocks={c: 100 for c in Commodity}),  # deep shortage -> buys
        2: _port(2, stocks={c: 900 for c in Commodity}),  # deep surplus -> sells
    })
    first = generate_orders(state, ECON)
    state.rng.random()  # perturb the shared RNG: generation must not consult it
    second = generate_orders(state, ECON)
    assert first == second
    assert all(o.qty > 0 and o.limit >= 1 for os in first.values() for o in os)
    assert {o.side for os in first.values() for o in os if o.port_id == 1} == {"buy"}
    assert {o.side for os in first.values() for o in os if o.port_id == 2} == {"sell"}


def test_generation_is_deterministic_under_dict_permutation() -> None:
    ports = {pid: _port(pid, stocks={c: 100 * pid for c in Commodity}) for pid in (1, 2, 3)}
    forward = generate_orders(_state(dict(sorted(ports.items()))), ECON)
    backward = generate_orders(_state(dict(sorted(ports.items(), reverse=True))), ECON)
    assert forward == backward


def test_dead_band_suppresses_equilibrium_churn() -> None:
    # capacity 1000, desired 500, band 0.10: silence on [450, 550].
    for stock in (450, 500, 540, 550):
        state = _state({1: _port(1, stocks={c: stock for c in Commodity})})
        assert generate_orders(state, ECON) == {}, f"stock {stock} should post nothing"


def test_buy_covers_the_full_gap_and_sell_sheds_the_band_excess() -> None:
    state = _state({
        1: _port(1, stocks={Commodity.FUEL_ORE: 440, Commodity.ORGANICS: 570,
                            Commodity.EQUIPMENT: 500}),
    })
    (orders,) = generate_orders(state, ECON).values()
    by_commodity = {o.commodity: o for o in orders}
    buy = by_commodity[Commodity.FUEL_ORE]
    assert (buy.side, buy.qty) == ("buy", 60)  # the full gap to desired (500 - 440)
    sell = by_commodity[Commodity.ORGANICS]
    assert (sell.side, sell.qty) == ("sell", 20)  # excess above the band edge (570 - 550)
    assert Commodity.EQUIPMENT not in by_commodity  # at the pivot: silent


def test_buy_is_clamped_to_the_purse_and_a_broke_port_posts_no_buy() -> None:
    stocks = {Commodity.FUEL_ORE: 100, Commodity.ORGANICS: 500, Commodity.EQUIPMENT: 500}
    rich = generate_orders(_state({1: _port(1, latinum=10_000, stocks=stocks)}), ECON)
    (order,) = rich[1]
    assert order.qty == 400  # the full gap, affordable
    poor_purse = order.limit * 7  # can afford exactly 7 units at its own quote
    poor = generate_orders(_state({1: _port(1, latinum=poor_purse, stocks=stocks)}), ECON)
    (clamped,) = poor[1]
    assert clamped.qty == 7 and clamped.qty * clamped.limit <= poor_purse
    broke = generate_orders(_state({1: _port(1, latinum=0, stocks=stocks)}), ECON)
    assert broke == {}  # a port never bids money it does not hold


def test_stardock_pivots_near_full() -> None:
    dock = _port(1, klass=PortClass.STARDOCK, stocks={c: 500 for c in Commodity})
    assert desired_stock_frac(dock, ECON) == ECON.desired_stock_frac_stardock
    orders = generate_orders(_state({1: dock}), ECON)
    # Half-full is a deep shortage against StarDock's 90% pivot: it buys.
    assert {o.side for o in orders[1]} == {"buy"}


def test_settlement_moves_goods_from_surplus_to_shortage() -> None:
    ports = {
        1: _port(1, stocks={c: 100 for c in Commodity}),  # shortage: bids high (low stock)
        2: _port(2, stocks={c: 900 for c in Commodity}),  # surplus: asks low (high stock)
    }
    orders = generate_orders(_state(ports), ECON)
    settlement = match_orders(orders, ports, ECON)
    assert settlement.fills, "a crossed book must trade"
    for fill in settlement.fills:
        assert (fill.buyer_port_id, fill.seller_port_id) == (1, 2)
    after = _apply(ports, settlement)
    assert after[1].line(Commodity.FUEL_ORE).stock > 100  # type: ignore[union-attr]
    assert after[2].line(Commodity.FUEL_ORE).stock < 900  # type: ignore[union-attr]
    assert after[1].latinum < ports[1].latinum  # the buyer paid
    assert after[2].latinum > ports[2].latinum  # the seller earned


# --- residual drifts -----------------------------------------------------------


def test_hinterland_drift_is_gentler_than_legacy_regen() -> None:
    port = _port(1, stocks={c: 100 for c in Commodity})
    line = port.commodities[0]
    frac = desired_stock_frac(port, ECON)
    drifted = hinterland_drift(line, ECON, desired_frac=frac)
    assert line.stock < drifted <= round(frac * line.capacity)  # moves toward the pivot
    # 1% of the 400-unit gap vs the legacy 5%: the residual is deliberately small.
    assert drifted - line.stock == round(ECON.market.hinterland_frac * 400)


def test_liquidity_drip_converges_to_the_floor_without_overshoot() -> None:
    floor = 2 * ECON.market.min_purse_per_size
    purse = 0
    for _ in range(1000):
        drip = liquidity_drip(_port(1, size=2, latinum=purse), ECON)
        if purse >= floor:
            assert drip == 0
            break
        assert drip >= 1  # always progresses while below the floor
        purse += drip
        assert purse <= floor  # never overshoots
    assert purse == floor  # and actually gets there


@given(purse=st.integers(min_value=0, max_value=10_000), size=st.integers(min_value=1, max_value=10))
def test_liquidity_drip_never_overshoots(purse: int, size: int) -> None:
    drip = liquidity_drip(_port(1, size=size, latinum=purse), ECON)
    floor = size * ECON.market.min_purse_per_size
    assert drip >= 0
    assert purse + drip <= max(purse, floor)


# --- clearing filled orders (WP47) --------------------------------------------


def test_clear_filled_subtracts_fills_and_drops_exhausted_orders() -> None:
    ports = {
        1: _port(1, stocks={c: 100 for c in Commodity}),  # shortage: buys
        2: _port(2, stocks={c: 900 for c in Commodity}),  # surplus: sells
    }
    orders = generate_orders(_state(ports), ECON)
    settlement = match_orders(orders, ports, ECON)
    assert settlement.fills
    residual = clear_filled(orders, settlement)
    # Every residual order's remaining qty equals its original minus what filled.
    filled: dict[tuple[int, Commodity, str], int] = {}
    for f in settlement.fills:
        filled[f.buyer_port_id, f.commodity, "buy"] = filled.get((f.buyer_port_id, f.commodity, "buy"), 0) + f.qty
        filled[f.seller_port_id, f.commodity, "sell"] = filled.get((f.seller_port_id, f.commodity, "sell"), 0) + f.qty
    for os in orders.values():
        for o in os:
            remaining = o.qty - filled.get((o.port_id, o.commodity, o.side), 0)
            kept = [r for r in residual.get(o.port_id, ()) if r.commodity is o.commodity and r.side == o.side]
            if remaining > 0:
                assert kept and kept[0].qty == remaining
            else:
                assert not kept  # fully filled ⇒ dropped


def test_clear_filled_is_a_noop_without_fills() -> None:
    ports = {1: _port(1, stocks={c: 500 for c in Commodity})}  # at pivot: no orders
    orders = generate_orders(_state(ports), ECON)
    settlement = match_orders(orders, ports, ECON)
    assert clear_filled(orders, settlement) == orders
