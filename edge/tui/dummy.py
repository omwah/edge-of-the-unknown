"""Hard-coded dummy DTOs for the throwaway TUI skeleton.

These stand in for the `to_public(context)` fog-of-war DTOs the real
`edge.server` will emit (DESIGN.md §3). The TUI reads *only* these shapes, so
when the real service lands the skeleton swaps its data source without touching
widget code. Nothing here is authoritative game logic — it exists to make the
screens render against realistic shapes.
"""

from __future__ import annotations

from dataclasses import dataclass

# The Phase-1 public DTO shapes now live canonically in `edge.core.dto` (the
# service's `to_public` output); they are re-exported here so existing TUI
# imports keep working unchanged (the WP8 DTO-contract unification). The Phase
# 2-3 DTOs below stay defined locally until their engines land.
from edge.core import dto
from edge.core.dto import (
    Aspect,
    CommodityLine,
    ComputerDTO,
    EngineRoomDTO,
    GameState,
    Hold,
    LocalMapDTO,
    LogEntry,
    MessagesDTO,
    PlanetDTO,
    PortDTO,
    SectorDTO,
    SectorPlanetDTO,
    SectorPortDTO,
    SectorShipDTO,
    ShipDTO,
    Slot,
    Subsystem,
    SurfaceDTO,
    SurfaceSite,
    TradePair,
    WarpDTO,
)


def sample_planet() -> PlanetDTO:
    """The Terra Nova orbit scene (UI_MOCKUPS.md §3) for the screenshot harness."""
    return PlanetDTO(
        planet_id=1, name="Terra Nova", ptype="terrestrial_warm", owner="Federation",
        colonizable=True, claimable=False, owned_by_you=False, colonists=1_240_000,
        habitability_cap=2_000_000, stores=[("Fuel Ore", 8_200), ("Organics", 31_400),
                                            ("Equipment", 5_100)],
        allocation=[("Fuel Ore", 20), ("Organics", 60), ("Equipment", 20)],
        ship_colonists=0, ship_colonist_capacity=100, starbase="operational",
    )


@dataclass(frozen=True)
class EnemyShip:
    """One hostile in an encounter group (UI_MOCKUPS.md §7)."""

    name: str
    hull_filled: int  # 0..10 for the hull bar
    hull_pct: int


@dataclass(frozen=True)
class EncounterDTO:
    """A hostile encounter: greeting-or-fight/flee (UI_MOCKUPS.md §7, DESIGN §10)."""

    title: str  # "Kessrin Raider pack (x3)"
    opener: str  # "they SHOOT FIRST"
    disposition_filled: int  # 0..5 for the effective-disposition bar
    band: str  # "hostile"
    detection: str  # "they spotted you"
    taunt: str  # dialogue-pack taunt line
    enemies: list[EnemyShip]
    arc_hint: str  # firing-arc tip, e.g. "arc: ahead/spinal → strafe it"
    shields_filled: int
    shields_pct: int
    hull_filled: int
    hull_pct: int
    combat_line: str  # "Combat spd 4 (-2 intcpt)"
    integrity_flag: str  # knocked-out-component flag, e.g. "thrusters: 1 burner out"
    round_no: int
    flee_chance: int  # %
    flee_floor: int  # % — the config escape-chance floor (clamp)




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
        colonists=25,
        colonist_capacity=100,
    )
    sector = SectorDTO(
        region="CORE SPACE",
        sector_id=7,
        flavor="the lanes hum with traffic",
        beacon='"Welcome to Sol"',
        band="Core",
        ports=[SectorPortDTO(0, "Stardock", "StarDock", True)],
        planets=[SectorPlanetDTO(7, "Terra Nova", "terrestrial_warm")],
        ships=[
            SectorShipDTO("Kestrel  free trader", "transport"),
            SectorShipDTO("Cabal Marauder", "fighter"),
            SectorShipDTO("Verdani escort", "warship"),
        ],
        warps=[
            WarpDTO(1, "<<", "Sol Core", display_id=1, band="Hub", codes=["S"]),
            WarpDTO(3, "--", "Sol Core", display_id=3, band="Hub", codes=["P", "@"]),
            WarpDTO(6, "--", "Vega Reach", display_id=6, band="Hub"),
            WarpDTO(8, ">>", kind="unexplored", display_id=8, band="?"),
            WarpDTO(12, ">>", kind="unexplored", display_id=12, band="?"),
        ],
        display_id=7,
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
        display_id=3,
    )


def sample_surface() -> SurfaceDTO:
    """The Terra Nova descent scene from UI_MOCKUPS.md §4.

    Terrain is produced by the live `edge.server.terrain` generator so the
    screenshot harness shows exactly the procedural art the service emits.
    """
    from edge.server import terrain as terrain_art

    sites = [
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
    ]
    return SurfaceDTO(
        planet="Terra Nova",
        descent_fuel="n/a",
        terrain=terrain_art.render_terrain(
            "terrestrial_warm", sites, seed=1986, planet_id=1,
        ),
        sites=sites,
        terrain_blurb=terrain_art.blurb_for("terrestrial_warm"),
        ptype="terrestrial_warm",
    )


def sample_map() -> LocalMapDTO:
    """The local sector ego-graph from UI_MOCKUPS.md §10.

    A node-and-edge graph centered on the current sector `(7@)` in gravity columns
    (toward-Core left, deeper right), matching `sample_state()`. Rows are baked
    Rich-markup; an unexplored neighbour shows its id faintly (contents fogged).
    """
    return LocalMapDTO(
        you_sector=7,
        you_display=7,
        you_band="Hub",
        rows=[
            "                [cyan](6)[/] ──╮",
            "[cyan](1)[/] ─────[reverse bold cyan](7@)[/]──┤",
            "                [green](12)[/] ─╯──[dim](21)[/]",
        ],
        legend=(
            "[reverse bold cyan]@[/] you   [bold yellow]*[/] route   ─ warp   "
            "[magenta]P[/]/[magenta]S[/] port   [green]@[/] planet   [dim](n)[/] unexplored"
        ),
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


def sample_contact() -> dto.ContactDTO:
    """A sample alien contact for the screenshot harness (UI_MOCKUPS.md §6).

    A friendly-band envoy: the dialogue is persona-voiced and the verb menu is derived
    from params — treaty/fight are greyed (Phase-2 / non-reachable), with reasons.
    """
    return dto.ContactDTO(
        species="Vesk", persona="serial_formal", alliance="unaligned",
        standing="friendly", band="friendly", disposition_filled=4,
        base_disposition=0.85, attitude=0.06, effective=0.91,
        opener="Greetings, Trailblazer. I am Veska VK-7 of the Vesk. We are at your service.",
        verbs=[
            dto.ContactVerbDTO("ask", "Ask about…", False, "no other species met yet",
                               kind="say", context="dossier_other", needs_subject=True),
            dto.ContactVerbDTO("trade", "Buy tech"),
            dto.ContactVerbDTO("barter", "Barter artifact"),
            dto.ContactVerbDTO("treaty", "Treaty", False, "treaties open in a later phase"),
            dto.ContactVerbDTO("fight", "Attack", False, "they are friendly"),
            dto.ContactVerbDTO("farewell", "Farewell", kind="say", context="farewell"),
        ],
        offers=[
            dto.TechOfferDTO(0, "navigator (I)", "I", "latinum", 1800, "", True),
            dto.TechOfferDTO(1, "radiator (II)", "II", "latinum", 7000, "", False, "insufficient latinum"),
            dto.TechOfferDTO(2, "sensors +1", "III", "barter", 0, "1 Tier-III artifact", False,
                             "need a Tier-III artifact"),
        ],
        dossier=[
            "The Selvani? We know them. Beware those whose minds are unkind, Trailblazer.",
        ],
    )


def sample_encounter() -> EncounterDTO:
    """The Kessrin Raider pack from UI_MOCKUPS.md §7.

    A hostile-band group that opens with violence (they detected the player's
    drive-glow); the flee chance is shown clamped to the config floor (§10).
    """
    return EncounterDTO(
        title="Kessrin Raider pack (x3)",
        opener="they SHOOT FIRST",
        disposition_filled=1,  # █░░░░ — deep in the hostile band
        band="hostile",
        detection="they spotted you",
        taunt='"Sol-meat. Your drive-glow led us right to you."',
        enemies=[
            EnemyShip("Raider", 7, 70),
            EnemyShip("Raider", 10, 99),
            EnemyShip("Skiff", 4, 40),
        ],
        arc_hint="arc: ahead/spinal → strafe it",
        shields_filled=4,
        shields_pct=38,
        hull_filled=7,
        hull_pct=74,
        combat_line="Combat spd 4 (-2 intcpt)",
        integrity_flag="thrusters: 1 burner out",
        round_no=3,
        flee_chance=31,
        flee_floor=10,
    )


def sample_messages() -> MessagesDTO:
    """The messages & log from UI_MOCKUPS.md §11 (the durable event_log, §12)."""
    return MessagesDTO(
        events=[
            LogEntry("day 4 · 09:12", "Stardock: interest accrued [green]+71 slips[/]"),
            LogEntry("day 4 · 08:50", "Kessrin raid reported near Band-2 boundary"),
            LogEntry(
                "day 4 · 08:31",
                "[magenta]*[/] Discovery logged: Crashed Ship (Uncommon)",
            ),
            LogEntry("day 3 · 22:04", 'Concord envoy: "Our drives await you, trader."'),
            LogEntry("day 3 · 21:10", "Trade: sold 20 Fuel Ore @ 14 → [green]+280 slips[/]"),
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
        display_id=7,
    )
