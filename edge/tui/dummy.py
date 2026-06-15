"""Hard-coded dummy DTOs for the throwaway TUI skeleton.

These stand in for the `to_public(context)` fog-of-war DTOs the real
`edge.server` will emit (DESIGN.md §3). The TUI reads *only* these shapes, so
when the real service lands the skeleton swaps its data source without touching
widget code. Nothing here is authoritative game logic — it exists to make the
screens render against realistic shapes.
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
class PlanetDTO:
    name: str
    ptype: str
    owner: str
    starbase: str | None = None


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
class GameState:
    turns: int
    max_turns: int
    ship: ShipDTO
    sector: SectorDTO


def sample_state() -> GameState:
    """The Sector-7 scene from UI_MOCKUPS.md §1."""
    ship = ShipDTO(
        name="S.S. Wayfarer",
        klass="Trailblazer",
        aspects=[
            Aspect("Shields", 8, "82%"),
            Aspect("Warp", 3, "3"),
            Aspect("Combat", 4, "4"),
            Aspect("Cloak", 0, "off"),
            Aspect("Sensors", 6, "Tier II"),
        ],
        integrity="all nominal",
        holds_used=40,
        holds_total=60,
        holds=[Hold("Fuel", 20, 60), Hold("Org", 12, 60), Hold("Equ", 8, 60)],
        gun="online",
        missiles=3,
        kits=2,
        latinum=14_250,
        band="0 - Core",
        # The mini-map is the current sector's neighbourhood, so the sectors drawn
        # adjacent to (7) must be exactly its warp targets below (1,3,6,8,12). In the
        # real game both this and the warp list are projected from the one warp graph
        # via to_public(); here they're hand-synced.
        region_map=[
            " (3) (6)",
            "   \\ /",
            "(1)-(7)",
            "   / \\",
            " (8) (12)",
        ],
    )
    sector = SectorDTO(
        region="CORE SPACE",
        sector_id=7,
        flavor="the lanes hum with traffic",
        beacon='"Welcome to Sol"',
        ports=["Stardock - Class 0"],
        planets=["Terra Nova  terrestrial, warm"],
        ships=["Kestrel  free trader", "Cabal Marauder", "Verdani escort"],
        warps=[
            WarpDTO(1, "<"),
            WarpDTO(3, "/", "Sol"),
            WarpDTO(6, ">"),
            WarpDTO(8, "?", explored=False),
            WarpDTO(12, "?", explored=False),
        ],
    )
    return GameState(turns=287, max_turns=300, ship=ship, sector=sector)


def sample_port() -> PortDTO:
    """The Sol Exchange trade screen from UI_MOCKUPS.md §2 (a plain port)."""
    return PortDTO(
        name="Sol Exchange",
        klass="Class 4 (BBS)",
        sector_id=3,
        commodities=[
            CommodityLine("Fuel Ore", "BUY", 410, 1000, 13, 11, 20),
            CommodityLine("Organics", "SELL", 220, 1000, 6, 5, 12),
            CommodityLine("Equipment", "BUY", 580, 1000, 14, 15, 8),
        ],
    )


def sample_stardock_port() -> PortDTO:
    """The StarDock's own commodities counter (its Commodities tab, §5).

    A StarDock sells all three goods (Class 0), so every line is a SELL.
    """
    return PortDTO(
        name="Sol StarDock",
        klass="Class 0 (StarDock)",
        sector_id=7,
        commodities=[
            CommodityLine("Fuel Ore", "SELL", 880, 1000, 12, 11, 20),
            CommodityLine("Organics", "SELL", 760, 1000, 6, 5, 12),
            CommodityLine("Equipment", "SELL", 820, 1000, 15, 15, 8),
        ],
    )
