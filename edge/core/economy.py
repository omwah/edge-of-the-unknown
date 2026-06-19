"""The economy: pricing, trade resolution, haggling, banking, stock regen (§8).

Pure functions over the frozen models — no I/O, no clock, no global RNG (any
randomness is drawn from a `random.Random` passed in by the caller, which owns
the seeded generator, §3). Every operation returns *new* frozen entities rather
than mutating in place; the store/service wraps the swap in a transaction (§8
invariant: balances never negative, goods conserved, mutations transactional).

The §8 invariants enforced and property-tested here (§13):
- prices clamped to ``[floor_frac*base, ceiling_frac*base]`` and always > 0;
- negative feedback — buying from a port never lowers, and selling into it never
  raises, that port's quoted price;
- goods conserved across any trade (latinum is *not*: it is minted when a port
  buys from the player and burned when it sells);
- the player's latinum never goes negative.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from enum import Enum

from edge.core.config import EconomyConfig
from edge.core.enums import Commodity, PortMode
from edge.core.models import Player, Port, PortCommodity, Ship


class EconomyError(Exception):
    """An illegal economic action (insufficient funds/goods/stock/holds)."""


# --- pricing ----------------------------------------------------------------


def capacity_for_size(size: int) -> int:
    """Port commodity capacity = size * 1000 (the twclone model, §8)."""
    return size * 1000


def stock_ratio(stock: int, capacity: int) -> float:
    return stock / capacity if capacity else 0.0


def quoted_unit_price(
    line: PortCommodity, *, elasticity: float, floor_frac: float, ceiling_frac: float
) -> int:
    """The §8 stock-ratio price for one commodity line, clamped and positive.

    Port SELLS (player buys):  base - delta * ratio * elasticity.
    Port BUYS  (player sells): base + delta * (1 - ratio) * elasticity.
    Both are non-increasing in stock, which yields the negative-feedback rule:
    a buy (stock down) raises the sell price; a sell (stock up) lowers the buy
    price. The result is clamped to [floor_frac*base, ceiling_frac*base] and to
    a minimum of 1 slip, so prices stay positive and bounded (§8 invariant).
    """
    ratio = stock_ratio(line.stock, line.capacity)
    if line.mode is PortMode.SELL:
        raw = line.base - line.delta * ratio * elasticity
    else:
        raw = line.base + line.delta * (1.0 - ratio) * elasticity
    lo = floor_frac * line.base
    hi = ceiling_frac * line.base
    clamped = min(max(raw, lo), hi)
    return max(1, round(clamped))


def port_unit_price(line: PortCommodity, econ: EconomyConfig) -> int:
    """Quoted price for a line using the economy config's per-commodity tunables."""
    return quoted_unit_price(
        line,
        elasticity=econ.pricing(line.commodity).elasticity,
        floor_frac=econ.floor_frac,
        ceiling_frac=econ.ceiling_frac,
    )


# --- trade resolution -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TradeOutcome:
    """The result of a trade: the new entities + a record of what moved."""

    port: Port
    ship: Ship
    player: Player
    commodity: Commodity
    mode: PortMode  # the port's mode for this commodity
    units: int
    unit_price: int
    total: int  # units * unit_price, in slips


def _with_stock(port: Port, commodity: Commodity, new_stock: int) -> Port:
    lines = tuple(
        replace(c, stock=new_stock) if c.commodity is commodity else c
        for c in port.commodities
    )
    return replace(port, commodities=lines)


def _with_cargo(ship: Ship, commodity: Commodity, new_qty: int) -> Ship:
    cargo = dict(ship.cargo)
    if new_qty > 0:
        cargo[commodity] = new_qty
    else:
        cargo.pop(commodity, None)
    return replace(ship, cargo=cargo)


def execute_trade(
    *,
    port: Port,
    ship: Ship,
    player: Player,
    commodity: Commodity,
    units: int,
    unit_price: int,
) -> TradeOutcome:
    """Move `units` of `commodity` between ship and port at the agreed `unit_price`.

    The direction is the port's mode for that commodity. Raises `EconomyError` if
    the trade would violate an invariant (unaffordable, oversell, over-capacity,
    insufficient holds/stock). Goods are conserved; the player's latinum is minted
    (port buys) or burned (port sells). `Port.latinum` is a soft figure in Phase 1
    (ports never go broke, §8) and is left unchanged here.
    """
    if units <= 0:
        raise EconomyError("trade units must be positive")
    line = port.line(commodity)
    if line is None:
        raise EconomyError(f"port {port.id} does not trade {commodity.value}")

    total = units * unit_price

    if line.mode is PortMode.SELL:  # player buys from the port
        if units > line.stock:
            raise EconomyError("port lacks the stock to sell")
        if units > ship.holds_free:
            raise EconomyError("not enough free holds")
        if total > player.latinum:
            raise EconomyError("insufficient latinum")
        new_port = _with_stock(port, commodity, line.stock - units)
        new_ship = _with_cargo(ship, commodity, ship.cargo.get(commodity, 0) + units)
        new_player = replace(player, latinum=player.latinum - total)  # burned
    else:  # PortMode.BUY — player sells into the port
        held = ship.cargo.get(commodity, 0)
        if units > held:
            raise EconomyError("ship lacks the goods to sell")
        if line.stock + units > line.capacity:
            raise EconomyError("port lacks the capacity to absorb")
        new_port = _with_stock(port, commodity, line.stock + units)
        new_ship = _with_cargo(ship, commodity, held - units)
        new_player = replace(player, latinum=player.latinum + total)  # minted

    return TradeOutcome(
        port=new_port, ship=new_ship, player=new_player, commodity=commodity,
        mode=line.mode, units=units, unit_price=unit_price, total=total,
    )


# --- haggling (one offer; the round counter lives in the session, §8) -------


class HaggleStatus(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INSULTING = "insulting"
    EXHAUSTED = "exhausted"  # the port closed negotiation for the day (§8 max_rejections)


def improvement_fraction(fair: int, counter: int, mode: PortMode) -> float:
    """How much `counter` favors the player beyond `fair`, as a fraction (>= 0).

    For a player buy (port SELLS) a lower counter is better; for a player sell
    (port BUYS) a higher counter is better. Returns 0 when the counter does not
    favor the player over fair.
    """
    if fair <= 0:
        return 0.0
    if mode is PortMode.SELL:  # player buys; wants to pay less than fair
        return max(0.0, (fair - counter) / fair)
    return max(0.0, (counter - fair) / fair)  # player sells; wants more than fair


def haggle_acceptance_probability(
    fair: int, counter: int, mode: PortMode, *, insult_frac: float,
    history_penalty: float, recent_attempts: int,
) -> float | None:
    """Probability the port accepts `counter`, or None if the offer is insulting.

    Falls off linearly with how greedy the counter is (relative to `insult_frac`)
    and with the player's recent haggling history at this port; clamped to [0, 1].
    A counter that does not favor the player over fair is accepted outright (1.0).
    """
    gap = improvement_fraction(fair, counter, mode)
    if gap > insult_frac:
        return None
    base = 1.0 if insult_frac <= 0 else 1.0 - gap / insult_frac
    p = base - history_penalty * max(0, recent_attempts)
    return min(1.0, max(0.0, p))


@dataclass(frozen=True, slots=True)
class HaggleResult:
    status: HaggleStatus
    price: int | None  # agreed price if ACCEPTED; the fair fallback if REJECTED


def resolve_haggle(
    fair: int, counter: int, mode: PortMode, rng: random.Random, *,
    insult_frac: float, history_penalty: float, recent_attempts: int,
) -> HaggleResult:
    """Resolve a single haggle offer with the caller's seeded RNG."""
    p = haggle_acceptance_probability(
        fair, counter, mode, insult_frac=insult_frac,
        history_penalty=history_penalty, recent_attempts=recent_attempts,
    )
    if p is None:
        return HaggleResult(HaggleStatus.INSULTING, None)
    if rng.random() < p:
        return HaggleResult(HaggleStatus.ACCEPTED, counter)
    return HaggleResult(HaggleStatus.REJECTED, fair)  # final price on exhaustion


# --- banking ----------------------------------------------------------------


def deposit(player: Player, amount: int) -> Player:
    """Move latinum on-hand into the bank (no negative on-hand balance)."""
    if amount <= 0:
        raise EconomyError("deposit must be positive")
    if amount > player.latinum:
        raise EconomyError("insufficient latinum to deposit")
    return replace(player, latinum=player.latinum - amount, bank_balance=player.bank_balance + amount)


def withdraw(player: Player, amount: int) -> Player:
    """Move latinum from the bank to on-hand (no negative bank balance)."""
    if amount <= 0:
        raise EconomyError("withdrawal must be positive")
    if amount > player.bank_balance:
        raise EconomyError("insufficient bank balance")
    return replace(player, latinum=player.latinum + amount, bank_balance=player.bank_balance - amount)


def accrue_interest(balance: int, rate_per_day: float, days: float = 1.0) -> int:
    """Compound interest on a bank balance (engine cron applies; math is pure)."""
    factor: float = (1.0 + rate_per_day) ** days
    return round(balance * factor)


# --- stock regeneration (engine econ tick, §8) ------------------------------


def regenerate_stock(stock: int, capacity: int, *, desired_frac: float, regen_frac: float) -> int:
    """Move stock `regen_frac` of the way toward `desired_frac * capacity`."""
    desired = desired_frac * capacity
    moved = stock + regen_frac * (desired - stock)
    return max(0, min(capacity, round(moved)))
