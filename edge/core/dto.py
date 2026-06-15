"""Public projection shapes — the fog-of-war view the TUI consumes (DESIGN §3).

These are the read-only DTOs that `to_public(context)` will emit at the server
boundary (WP6); the TUI reads *only* these, never the core models. They are
deliberately **structurally identical** to today's `edge/tui/dummy.py` fixtures,
which are the de-facto contract — so when the real service lands, `dummy.py` is
refactored to re-export these and the widget code is untouched (WP8).

Scope: Phase-1 screens only (Game / Port / StarDock-commodities / Computer /
Map). DTOs use primitive types (str modes/names), not core enums — the
projection converts enums to display strings. Phase 2–3 DTOs (surface, engine
room, contact, encounter, messages) stay in `dummy.py` until their engines land.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommodityLine:
    name: str
    mode: str  # "BUY" (port buys from you) | "SELL" (port sells to you)
    stock: int
    capacity: int
    price: int
    base_price: int
    player_qty: int

    @property
    def stock_ratio(self) -> float:
        return self.stock / self.capacity if self.capacity else 0.0

    @property
    def trend(self) -> str:
        if self.price > self.base_price:
            return "^"
        if self.price < self.base_price:
            return "v"
        return "="


@dataclass(frozen=True)
class PortDTO:
    name: str
    klass: str
    sector_id: int
    commodities: list[CommodityLine]


@dataclass(frozen=True)
class WarpDTO:
    sector_id: int
    arrow: str
    label: str | None = None
    explored: bool = True


@dataclass(frozen=True)
class SectorDTO:
    region: str
    sector_id: int
    flavor: str
    beacon: str | None
    ports: list[str] = field(default_factory=list)
    planets: list[str] = field(default_factory=list)
    ships: list[str] = field(default_factory=list)
    warps: list[WarpDTO] = field(default_factory=list)


@dataclass(frozen=True)
class Aspect:
    label: str
    filled: int  # 0..10 for the bar
    note: str


@dataclass(frozen=True)
class Hold:
    label: str
    qty: int
    capacity: int


@dataclass(frozen=True)
class ShipDTO:
    name: str
    klass: str
    aspects: list[Aspect]
    integrity: str
    holds_used: int
    holds_total: int
    holds: list[Hold]
    gun: str
    missiles: int
    kits: int
    latinum: int
    band: str
    region_map: list[str]


@dataclass(frozen=True)
class TradePair:
    pair: str
    goods: str
    dist: int
    profit_rt: int  # round-trip profit
    per_turn: int  # profit per turn (the finder's score)


@dataclass(frozen=True)
class ComputerDTO:
    pairs: list[TradePair]
    selected: str


@dataclass(frozen=True)
class MapBand:
    title: str
    rows: list[str]
    lane: str | None = None  # neutral-lane glyph drawn to this band's left, if any


@dataclass(frozen=True)
class MapDTO:
    you_sector: int
    you_band: str
    bands: list[MapBand]


@dataclass(frozen=True)
class GameState:
    """The game-screen view bundle (the public counterpart of `UniverseState`)."""

    turns: int
    max_turns: int
    ship: ShipDTO
    sector: SectorDTO
