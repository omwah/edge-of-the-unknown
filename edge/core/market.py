"""The order-book market: order generation, settlement, residual drifts (§8, WP46).

Phase 5 replaces the flat 5% stock regen with twclone's order-book model, made
normative in DESIGN §8: each economy tick every port posts at most one order
per commodity per side against its own desired-stock gap, and a daily
settlement matches those orders across ports, physically moving goods and
latinum between them. This module is the book as *pure math* — no I/O, no RNG,
no state wiring (H10): the WP47 crons/reducers call in with snapshots and
apply the returned deltas transactionally.

Determinism contract (H10). Every function here is a pure function of its
arguments: order generation walks ports in ascending id order, settlement
sorts both sides of the book canonically (price-time priority degenerates to
price-then-port-id, since all orders in a cycle are simultaneous) and works
commodities in `Commodity` definition order, and no call consults a clock or
an RNG. Two calls with equal inputs return equal outputs — the market rides
the `(seed, command log)` replay rail untouched.

Conservation contract (H10/§13). `match_orders` asserts its own invariant
before returning: per commodity the stock deltas sum to zero, and the latinum
deltas sum to zero — settlement moves value between ports, never mints or
burns it. The invariant lives in the module it guards, so the book cannot be
wired into state without it holding.

Why the residual drifts exist. A closed order book starves: ports converge on
their desired stocks, the dead band silences the book, and trade halts. Two
deliberate, port-local, deterministic residuals keep a gentle external
gradient alive for the market (and the player) to arbitrage:

- `hinterland_drift` — the legacy regen at a much smaller fraction (default
  0.01 vs the old 0.05), each port's off-map hinterland producing and
  consuming a trickle of goods;
- `liquidity_drip` — a daily top-up of each port's purse toward a configured
  floor, the §8 faucet that keeps player *selling* viable everywhere: a broke
  port partially fills (WP47) but never deadlocks forever.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Literal

from edge.core.config import EconomyConfig
from edge.core.economy import port_unit_price, regenerate_stock
from edge.core.enums import Commodity, PortClass
from edge.core.models import Port, PortCommodity, UniverseState

Side = Literal["buy", "sell"]


@dataclass(frozen=True, slots=True)
class PortOrder:
    """One open order: a port's standing offer to buy or sell one commodity.

    At most one order exists per `(port, commodity, side)`: `generate_orders`
    *replaces* a port's book each cycle rather than appending, so the whole
    book is bounded by 3 commodities × 2 sides × n_ports and stale orders
    cannot accumulate (§8 idempotence).
    """

    port_id: int
    commodity: Commodity
    side: Side
    qty: int  # units still wanted/offered; always > 0 in a generated book
    limit: int  # per-unit limit in slips: max bid (buy) / min ask (sell); >= 1


@dataclass(frozen=True, slots=True)
class MatchFill:
    """One settled match — the event-log record of goods and latinum moving."""

    commodity: Commodity
    buyer_port_id: int
    seller_port_id: int
    qty: int
    unit_price: int  # the integer midpoint of the crossed limits (§8)

    @property
    def total(self) -> int:
        """Latinum moved buyer → seller, in slips."""
        return self.qty * self.unit_price


@dataclass(frozen=True, slots=True)
class Settlement:
    """The outcome of one daily settlement: what to apply to the ports (WP47).

    `stock_deltas` is port id → commodity → signed units; `latinum_deltas` is
    port id → signed slips. Both are already conservation-checked (per
    commodity the stock deltas sum to zero; the latinum deltas sum to zero),
    so the applying reducer only swaps snapshots — it re-verifies nothing.
    """

    fills: tuple[MatchFill, ...]
    stock_deltas: Mapping[int, Mapping[Commodity, int]]
    latinum_deltas: Mapping[int, int]


def desired_stock_frac(port: Port, econ: EconomyConfig) -> float:
    """The port's desired-stock ratio — its §8 price pivot.

    Stardock idles near-full (a reliable supplier); standard ports pivot at
    half capacity. The same ratios the legacy regen used (twclone's model),
    lifted here so the order book and the hinterland drift share one pivot.
    """
    return (
        econ.desired_stock_frac_stardock
        if port.klass is PortClass.STARDOCK
        else econ.desired_stock_frac_standard
    )


def generate_orders(
    state: UniverseState, econ: EconomyConfig
) -> dict[int, tuple[PortOrder, ...]]:
    """Post every port's open orders from `state.ports` (see `orders_from_ports`)."""
    return orders_from_ports(state.ports, econ)


def orders_from_ports(
    ports: Mapping[int, Port], econ: EconomyConfig
) -> dict[int, tuple[PortOrder, ...]]:
    """Post every port's open orders from its desired-stock gaps (§8).

    For each commodity line, with ``desired = desired_frac × capacity`` and
    ``band = market.order_band``:

    - ``stock < desired × (1 − band)`` — a **BUY** for the full gap
      ``desired − stock`` at the port's own quoted §8 price at current stock
      (the port bids its current fair price), clamped so ``qty × limit``
      never exceeds the port's purse: a port never bids money it does not
      hold. (Each line is clamped against the whole purse — three lines may
      overcommit it in aggregate; settlement enforces the *running* purse per
      fill, so the clamp here is a bound on intent, not the spend.)
    - ``stock > desired × (1 + band)`` — a **SELL** for the excess above the
      band edge at the quoted ask. The asymmetry with the BUY side is §8's:
      buys restore the pivot exactly, sells shed only what lies beyond
      tolerance — a port keeps a working buffer rather than selling down to
      the knife-edge of its own shortage trigger.
    - inside the dead band — no order: equilibrium is silent, so repeated
      generation at rest churns nothing.

    Pure and RNG-free; ports are walked in ascending id order. The result is
    a *total replacement* for the previous book — regeneration is idempotent
    and the book stays bounded (H10). Ports with no orders are omitted.
    """
    band = econ.market.order_band
    book: dict[int, tuple[PortOrder, ...]] = {}
    for port_id in sorted(ports):
        port = ports[port_id]
        frac = desired_stock_frac(port, econ)
        orders: list[PortOrder] = []
        for line in port.commodities:
            desired = frac * line.capacity
            quote = port_unit_price(line, econ)  # the §8 price at current stock
            if line.stock < desired * (1.0 - band):
                gap = round(desired) - line.stock
                qty = min(gap, port.latinum // quote)  # purse clamp (never bid unheld money)
                if qty > 0:
                    orders.append(PortOrder(port.id, line.commodity, "buy", qty, quote))
            elif line.stock > desired * (1.0 + band):
                excess = line.stock - round(desired * (1.0 + band))
                if excess > 0:
                    orders.append(PortOrder(port.id, line.commodity, "sell", excess, quote))
        if orders:
            book[port_id] = tuple(orders)
    return book


def match_orders(
    orders: Mapping[int, tuple[PortOrder, ...]],
    ports: Mapping[int, Port],
    econ: EconomyConfig,
) -> Settlement:
    """Match the book and return the conserving inter-port settlement (§8).

    Per commodity (in `Commodity` definition order — canonical, so dict
    ordering of the inputs cannot matter): BUYs sort by limit descending then
    port id ascending, SELLs by limit ascending then port id ascending, and
    the fronts match greedily while ``buy.limit >= sell.limit``. Each match
    fills ``min(buy qty, sell qty, buyer purse // price, seller stock, buyer
    capacity headroom)`` at ``settle_price`` — today always the integer
    midpoint ``(buy.limit + sell.limit) // 2``, which the crossing condition
    pins inside ``[sell.limit, buy.limit]`` (so it is always >= 1).

    Purses, stocks, and headrooms are tracked *live* across the whole
    settlement — a port that spends its purse buying fuel ore has less to bid
    on equipment, and a seller's earnings are spendable within the same
    settlement (commodity order makes that deterministic). An order the
    running constraints have squeezed to a zero fill is dropped and the walk
    continues, so one broke port never blocks the rest of the book.

    Tolerated degenerate inputs (property tests feed arbitrary books): orders
    with non-positive qty or limit are ignored, an order naming a commodity
    its port has no line for can never fill (headroom/stock resolve to 0),
    and a self-match (same port both sides) nets to zero deltas — all safe,
    none produced by `generate_orders`.

    Asserts its own H10 invariant before returning: per commodity the stock
    deltas sum to zero, the latinum deltas sum to zero, and no running purse
    ever went negative.
    """
    # `settle_price` is a named policy knob so a future rule (e.g. pay-the-ask)
    # is a config value, not a rewrite; "midpoint" is the only policy today.
    assert econ.market.settle_price == "midpoint"

    purses: dict[int, int] = {pid: p.latinum for pid, p in ports.items()}
    stocks: dict[tuple[int, Commodity], int] = {
        (pid, line.commodity): line.stock
        for pid, p in ports.items()
        for line in p.commodities
    }
    capacities: dict[tuple[int, Commodity], int] = {
        (pid, line.commodity): line.capacity
        for pid, p in ports.items()
        for line in p.commodities
    }

    fills: list[MatchFill] = []
    flat = [o for port_orders in orders.values() for o in port_orders]
    for commodity in Commodity:
        buys = sorted(
            (o for o in flat if o.commodity is commodity and o.side == "buy" and o.qty > 0 and o.limit > 0),
            key=lambda o: (-o.limit, o.port_id),
        )
        sells = sorted(
            (o for o in flat if o.commodity is commodity and o.side == "sell" and o.qty > 0 and o.limit > 0),
            key=lambda o: (o.limit, o.port_id),
        )
        # Remaining quantity per front order; orders pop when exhausted or squeezed.
        buy_rem = [o.qty for o in buys]
        sell_rem = [o.qty for o in sells]
        b = s = 0
        while b < len(buys) and s < len(sells) and buys[b].limit >= sells[s].limit:
            buy, sell = buys[b], sells[s]
            price = (buy.limit + sell.limit) // 2
            headroom = capacities.get((buy.port_id, commodity), 0) - stocks.get(
                (buy.port_id, commodity), 0
            )
            fill = min(
                buy_rem[b],
                sell_rem[s],
                purses[buy.port_id] // price,
                stocks.get((sell.port_id, commodity), 0),
                headroom,
            )
            if fill <= 0:
                # Squeezed to nothing: drop whichever side's running constraint
                # binds (buyer purse/headroom, else seller stock) and move on.
                if purses[buy.port_id] // price <= 0 or headroom <= 0:
                    b += 1
                else:
                    s += 1
                continue
            fills.append(MatchFill(commodity, buy.port_id, sell.port_id, fill, price))
            buy_rem[b] -= fill
            sell_rem[s] -= fill
            purses[buy.port_id] -= fill * price
            purses[sell.port_id] += fill * price
            stocks[buy.port_id, commodity] = stocks.get((buy.port_id, commodity), 0) + fill
            stocks[sell.port_id, commodity] -= fill
            if buy_rem[b] == 0:
                b += 1
            if sell_rem[s] == 0:
                s += 1

    # Fold the fills into the per-port delta maps the WP47 reducer applies.
    stock_deltas: dict[int, dict[Commodity, int]] = {}
    latinum_deltas: dict[int, int] = {}
    for fill_rec in fills:
        for pid, sign in ((fill_rec.buyer_port_id, +1), (fill_rec.seller_port_id, -1)):
            per_port = stock_deltas.setdefault(pid, {})
            per_port[fill_rec.commodity] = per_port.get(fill_rec.commodity, 0) + sign * fill_rec.qty
        latinum_deltas[fill_rec.buyer_port_id] = (
            latinum_deltas.get(fill_rec.buyer_port_id, 0) - fill_rec.total
        )
        latinum_deltas[fill_rec.seller_port_id] = (
            latinum_deltas.get(fill_rec.seller_port_id, 0) + fill_rec.total
        )

    # The H10 conservation invariant, enforced where the numbers are made.
    for commodity in Commodity:
        assert sum(d.get(commodity, 0) for d in stock_deltas.values()) == 0
    assert sum(latinum_deltas.values()) == 0
    assert all(p >= 0 for p in purses.values())

    return Settlement(
        fills=tuple(fills), stock_deltas=stock_deltas, latinum_deltas=latinum_deltas
    )


def clear_filled(
    orders: Mapping[int, tuple[PortOrder, ...]], settlement: Settlement
) -> dict[int, tuple[PortOrder, ...]]:
    """The residual book after a settlement: each order's filled quantity removed (§8, WP47).

    Sums the fills against each `(port, commodity, side)` order and subtracts them;
    an order filled to zero is dropped, and a port left with no open orders is omitted.
    Pure and deterministic — the next economy tick replaces the book wholesale anyway,
    but between a settlement and that regeneration the book must reflect what already
    traded so a projection (WP48) never shows a filled order as still open.
    """
    filled: dict[tuple[int, Commodity, Side], int] = {}
    for fill in settlement.fills:
        filled[fill.buyer_port_id, fill.commodity, "buy"] = (
            filled.get((fill.buyer_port_id, fill.commodity, "buy"), 0) + fill.qty
        )
        filled[fill.seller_port_id, fill.commodity, "sell"] = (
            filled.get((fill.seller_port_id, fill.commodity, "sell"), 0) + fill.qty
        )
    residual: dict[int, tuple[PortOrder, ...]] = {}
    for port_id in sorted(orders):
        kept: list[PortOrder] = []
        for order in orders[port_id]:
            done = filled.get((order.port_id, order.commodity, order.side), 0)
            remaining = order.qty - done
            if remaining > 0:
                kept.append(replace(order, qty=remaining))
        if kept:
            residual[port_id] = tuple(kept)
    return residual


def hinterland_drift(
    line: PortCommodity, econ: EconomyConfig, *, desired_frac: float
) -> int:
    """New stock after the off-map hinterland's residual trickle (§8).

    The legacy `regenerate_stock` at `market.hinterland_frac` (default 0.01
    vs the old 0.05): each port's unseen hinterland produces toward shortages
    and consumes surpluses a little each tick. Without it a closed book
    starves — every port converges on its pivot and trade halts; with it the
    market keeps a gentle external gradient to arbitrage. `desired_frac` is
    the caller's `desired_stock_frac(port, econ)` (a line does not know its
    port's class).
    """
    return regenerate_stock(
        line.stock,
        line.capacity,
        desired_frac=desired_frac,
        regen_frac=econ.market.hinterland_frac,
    )


def liquidity_drip(port: Port, econ: EconomyConfig) -> int:
    """The daily purse top-up in slips toward the liquidity floor; 0 at/above it.

    The floor is ``size × market.min_purse_per_size``; each day the purse
    closes ``market.drip_frac`` of the gap (rounded, but always >= 1 slip
    while below the floor so small gaps cannot stall, and capped at the gap
    so the drip never overshoots the floor). This is the §8 standing faucet:
    it keeps player selling viable everywhere without refilling a genuinely
    drained market instantly — an arbitrageur can still empty a purse faster
    than it refills (H10's no-deadlock, not no-scarcity, guarantee).
    """
    gap = port.size * econ.market.min_purse_per_size - port.latinum
    if gap <= 0:
        return 0
    return min(gap, max(1, round(econ.market.drip_frac * gap)))
