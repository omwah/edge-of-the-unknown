"""Immutable event facts — the durable rail (DESIGN §3, §12).

Reducers in `core.rules` return events describing what happened; the store
appends them to the `event_log` (assigning the monotonic id/tick) and the engine
tick loop consumes the same log. Events carry only their semantic payload — no
ids/timestamps, which the store layer assigns. Replaying the command log against
a fixed seed reproduces the same events (the save-integrity / golden-master rail).
"""

from __future__ import annotations

from dataclasses import dataclass

from edge.core.enums import Commodity, PortMode


@dataclass(frozen=True)
class Event:
    """Base class for all event facts."""


@dataclass(frozen=True)
class Warped(Event):
    player_id: int
    from_sector: int
    to_sector: int
    turn_cost: int


@dataclass(frozen=True)
class Docked(Event):
    player_id: int
    sector_id: int
    port_id: int


@dataclass(frozen=True)
class Traded(Event):
    player_id: int
    port_id: int
    commodity: Commodity
    mode: PortMode  # the port's mode for this commodity
    units: int
    unit_price: int
    total: int


@dataclass(frozen=True)
class Haggled(Event):
    player_id: int
    port_id: int
    commodity: Commodity
    status: str  # HaggleStatus value
    price: int | None


@dataclass(frozen=True)
class Banked(Event):
    player_id: int
    kind: str  # "deposit" | "withdraw" | "interest"
    amount: int
    balance: int  # resulting bank balance


@dataclass(frozen=True)
class Upgraded(Event):
    player_id: int
    aspect: str
    cost: int


@dataclass(frozen=True)
class TurnsReset(Event):
    player_id: int
    turns: int


@dataclass(frozen=True)
class StockRegenerated(Event):
    port_id: int
    commodity: Commodity
    new_stock: int
