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


# Every `*_id` below is the *internal* sector id (the click/message payload and
# key); the parallel `display_id` is the band-monotone spatial id the player sees
# (DESIGN §5.1). The TUI renders `display_id` and acts on `sector_id`.


@dataclass(frozen=True)
class PortDTO:
    name: str
    klass: str
    sector_id: int
    commodities: list[CommodityLine]
    display_id: int = 0  # spatial id of the port's sector (§5.1)


@dataclass(frozen=True)
class WarpDTO:
    sector_id: int
    arrow: str  # gravity glyph relative to the Core: "<<" closer / ">>" deeper / "--" level
    label: str | None = None
    kind: str = "explored"  # "explored" | "unexplored" | "backtrack" — drives colour
    display_id: int = 0  # spatial id rendered on the warp button (§5.1)

    @property
    def explored(self) -> bool:
        return self.kind != "unexplored"


@dataclass(frozen=True)
class NeighborDTO:
    """One adjacent sector for the sidebar quick-reference (a clickable warp).

    `name`/`band` and content `codes` are filled only for sectors the player has
    explored; an unexplored neighbour reads as `[id] —` with no codes. `name`
    embeds the spatial `display_id`; `sector_id` stays internal for the warp action.
    """

    sector_id: int
    name: str  # "[10604] Halaf Verge" (explored) | "[10604] —" (unexplored)
    band: str  # "Frontier" (explored) | "?" (unexplored)
    explored: bool
    codes: list[str] = field(default_factory=list)  # short content tokens, explored only
    display_id: int = 0  # spatial id shown in `name` (§5.1)


@dataclass(frozen=True)
class SectorDTO:
    region: str
    sector_id: int
    flavor: str
    beacon: str | None
    band: str = ""  # distance-band name, e.g. "Frontier" (for the "[id] Region (Band)" title)
    ports: list[str] = field(default_factory=list)
    planets: list[str] = field(default_factory=list)
    ships: list[str] = field(default_factory=list)
    warps: list[WarpDTO] = field(default_factory=list)
    display_id: int = 0  # spatial id shown in the sector title (§5.1)


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
    neighbors: list[NeighborDTO]


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
    you_display: int = 0  # spatial id of the player's sector (§5.1)


@dataclass(frozen=True)
class LogEntry:
    """One line in the messages/event log (UI_MOCKUPS.md §11, DESIGN §12)."""

    when: str  # short label, e.g. "" or "start"; markup-free
    text: str  # markup ok


@dataclass(frozen=True)
class MessagesDTO:
    """The messages & log view, projected from the durable event_log (§12)."""

    events: list[LogEntry]


@dataclass(frozen=True)
class Slot:
    """One component slot in a subsystem panel (UI_MOCKUPS.md §8, DESIGN §4.1).

    `state` is "filled" | "empty" | "knocked" (knocked-out by combat — Phase 3);
    a filled slot names its `component`, and the structural `keystone` slot is marked.
    """

    state: str
    component: str = ""
    keystone: bool = False


@dataclass(frozen=True)
class Subsystem:
    """One subsystem panel: its derived aspect and its slot grid (§4.1)."""

    name: str  # "SPINDRIVE", "THRUSTERS", "SCREENS", "MAIN GUN"
    derived: str  # the aspect this subsystem drives, e.g. "warp 3"
    slots: list[Slot]


@dataclass(frozen=True)
class EngineRoomDTO:
    """The player ship's slotted subsystems (UI_MOCKUPS.md §8, DESIGN §4.1)."""

    ship: str
    efficiency_bonus: str  # spindrive global combat buff, e.g. "+2 all"
    subsystems: list[Subsystem]
    kits: int
    on_hand: list[str]  # loose carried components, e.g. ["converter (I) x1"]


@dataclass(frozen=True)
class HardwareItem:
    """One row in the StarDock hardware emporium (UI_MOCKUPS.md §5, DESIGN §8)."""

    component: str
    tier: str
    price: int  # latinum
    affordable: bool


@dataclass(frozen=True)
class ShipyardItem:
    """One buyable hull in the StarDock shipyard, with a stat line (§8, §11)."""

    class_id: str
    name: str
    role: str
    price: int
    net_price: int  # price after the current hull's trade-in credit
    holds: int
    shields: int
    warp: int
    combat: int
    affordable: bool
    owned: bool  # the hull the player currently flies


@dataclass(frozen=True)
class StarDockDTO:
    """The StarDock services catalog (hardware + shipyard), fog-of-war scoped (§3)."""

    sector_display: int
    latinum: int
    hardware: list[HardwareItem]
    shipyard: list[ShipyardItem]


@dataclass(frozen=True)
class GameState:
    """The game-screen view bundle (the public counterpart of `UniverseState`)."""

    turns: int
    max_turns: int
    ship: ShipDTO
    sector: SectorDTO
