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
class SurfaceSite:
    """A discoverable surface site on a descended planet (UI_MOCKUPS.md §4)."""

    marker: str  # "[1]", "[2]", "[?]" — keyed to the terrain map
    name: str
    rarity: str  # "Rare", "Uncommon", …
    status: str  # "unexplored", "explored → ancient", "hidden"
    payload: list[str] = field(default_factory=list)  # detail lines (markup ok)


@dataclass(frozen=True)
class SurfaceDTO:
    planet: str
    descent_fuel: str  # "n/a" in Phase 1 (movement costs turns, not fuel)
    terrain: list[str]  # top-down ASCII map rows (markup ok)
    sites: list[SurfaceSite] = field(default_factory=list)


@dataclass(frozen=True)
class MapBand:
    """One distance band's column on the galactic map (UI_MOCKUPS.md §10)."""

    title: str  # e.g. "Band 0 · Core"
    rows: list[str]  # rendered content lines (Rich markup allowed)
    lane: str | None = None  # neutral-lane glyph drawn to this band's left, if any


@dataclass(frozen=True)
class MapDTO:
    you_sector: int
    you_band: str
    bands: list[MapBand]


@dataclass(frozen=True)
class Slot:
    """One component slot in a subsystem panel (UI_MOCKUPS.md §8).

    `state` is "filled" | "empty" | "knocked" (knocked-out by combat); a filled
    slot names its `component`, and the structural `keystone` slot is marked.
    """

    state: str
    component: str = ""
    keystone: bool = False


@dataclass(frozen=True)
class Subsystem:
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
    on_hand: list[str]  # carried components, e.g. ["converter x1", "turbine x1"]


@dataclass(frozen=True)
class TradePair:
    """One row of the Computer's pair-trade finder (UI_MOCKUPS.md §9)."""

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


def sample_surface() -> SurfaceDTO:
    """The Terra Nova descent scene from UI_MOCKUPS.md §4."""
    return SurfaceDTO(
        planet="Terra Nova",
        descent_fuel="n/a",
        terrain=[
            "[dim].[/] [green]^[/]    [red]*?[/]       [green]^^[/]",
            "  [green]^^^[/]  [yellow][1][/]     [dim].[/]      [yellow]*[/]",
            "[blue]~~~~~[/]   [green]^[/]     [yellow][2][/]    [green]^^^[/]",
            "  [dim].[/]  [magenta]crashed-ship[/]    [blue]~~~~[/]",
            "    [green]^^[/]     [dim].[/]       [dim].[/]",
        ],
        sites=[
            SurfaceSite(
                "[1]", "Ruined Spire", "Rare", "unexplored",
                payload=["[red]ancient_tech ?[/]", "lore fragment"],
            ),
            SurfaceSite(
                "[2]", "Crashed Ship", "Uncommon", "explored → ancient",
                payload=["ancient drive (claimed)", "salvage cache"],
            ),
            SurfaceSite(
                "[?]", "(hidden)", "?", "hidden",
                payload=["needs a sensor sweep", "sensors Tier II"],
            ),
        ],
    )


def sample_map() -> MapDTO:
    """The banded galactic map from UI_MOCKUPS.md §10.

    Bands run Core → Hub → Frontier → Void, left to right; `lane` glyphs are the
    neutral navigable lanes between alliance home clusters (§5/§10). The current
    sector `(7@)` sits in the Core column, matching `sample_state()`.
    """
    return MapDTO(
        you_sector=7,
        you_band="0 - Core",
        bands=[
            MapBand(
                title="Band 0 · Core",
                rows=[
                    "[dim](3)[/]   [dim](6)[/]",
                    "  \\   /",
                    "[dim](1)[/]─[reverse cyan](7@)[/]",
                    "  /   \\",
                    "[dim](8)[/]   [dim](12)[/]",
                    "",
                    "[magenta]P[/] Sol  [green]o[/] Terra",
                ],
            ),
            MapBand(
                title="Band 1 · Hub",
                lane="~",
                rows=[
                    "[cyan]Concord[/]",
                    "cluster",
                    "",
                    "[dim](21)(22)[/]",
                    "[dim](24)(25)[/]",
                    "",
                    "[green]o[/] [green]o[/]  owned",
                ],
            ),
            MapBand(
                title="Band 2 · Frontier",
                lane="~",
                rows=[
                    "[yellow]*[/] rumor",
                    "",
                    "(40)(41)[red]?[/]",
                    "(43)[red]?[/]  [red]#?[/]",
                    "",
                    "[red]~[/] hazard",
                    "[green]o[/]   [red]#?[/]",
                ],
            ),
            MapBand(
                title="Band 3+ · Void",
                lane="·",
                rows=[
                    "",
                    "[dim]· · · ·[/]",
                    "[dim]unknown[/]",
                    "",
                    "[red]~ ?[/]",
                    "",
                    "[dim]deep void[/]",
                ],
            ),
        ],
    )


def sample_engine_room() -> EngineRoomDTO:
    """The S.S. Wayfarer's engine room from UI_MOCKUPS.md §8.

    Mirrors the sidebar ship: warp 3, shields 82%, combat 4, a knocked-out
    thruster burner (so the integrity line has something to flag), and a couple
    of on-hand parts to install/cannibalise.
    """
    return EngineRoomDTO(
        ship="S.S. Wayfarer",
        efficiency_bonus="+2 all",
        subsystems=[
            Subsystem(
                "SPINDRIVE", "warp 3",
                [
                    Slot("filled", "navigator", keystone=True),
                    Slot("filled", "turbine"),
                    Slot("filled", "accelerator"),
                    Slot("empty"),
                    Slot("empty"),
                ],
            ),
            Subsystem(
                "SCREENS", "shields 82%",
                [
                    Slot("filled", "secondary", keystone=True),
                    Slot("filled", "accelerator"),
                    Slot("empty"),
                    Slot("empty"),
                ],
            ),
            Subsystem(
                "THRUSTERS", "combat spd 4",
                [
                    Slot("filled", "burner", keystone=True),
                    Slot("knocked", "burner"),
                    Slot("empty"),
                    Slot("empty"),
                ],
            ),
            Subsystem(
                "MAIN GUN", "dmg 18 · rate 2",
                [
                    Slot("filled", "accelerator", keystone=True),
                    Slot("filled", "linkage"),
                    Slot("empty"),
                    Slot("empty"),
                    Slot("empty"),
                ],
            ),
        ],
        kits=2,
        on_hand=["converter x1", "turbine x1"],
    )


def sample_computer() -> ComputerDTO:
    """The Computer's pair-trade finder from UI_MOCKUPS.md §9."""
    return ComputerDTO(
        selected="Sol <-> Halaf-2",
        pairs=[
            TradePair("Sol <-> Halaf-2", "Org/Equ", 2, 640, 320),
            TradePair("Sol <-> Mirach", "Fuel/Equ", 3, 810, 270),
            TradePair("Halaf-2 <-> Vega-9", "Org/Fuel", 4, 900, 225),
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
