"""Dev preview for the SectorScene arrival composition (WP-PR2-05 prototype).

Renders representative sector compositions straight to the terminal — no game,
no app — so layout/scale decisions can be judged quickly at every tier:

    python -m edge.tui.scene_preview                    # all cases, all tiers
    python -m edge.tui.scene_preview --case belt        # one case
    python -m edge.tui.scene_preview --size 87x36       # one size
    python -m edge.tui.scene_preview --list             # case names

Sizes default to the space the scene actually gets per tier: compact 80×20
(where today the object list replaces the scene — rendered here to judge
whether the arrival view could someday take over), standard 67×30 (100×34
screen minus sidebar/ticker/footer), wide 87×36 (120×40 likewise).

Dev-only, never imported by runtime screens.
"""

from __future__ import annotations

import argparse

from rich.console import Console
from rich.rule import Rule

from edge.core.config import SceneArtConfig
from edge.core.dto import (
    SectorAnomalyDTO,
    SectorDiscovery,
    SectorDTO,
    SectorForceDTO,
    SectorPlanetDTO,
    SectorPortDTO,
    SectorShipDTO,
    SectorStarbaseDTO,
)
from edge.tui.widgets import _SceneComposer

# (label, width, height) — the canvas the scene gets at each responsive tier.
SIZES: tuple[tuple[str, int, int], ...] = (
    ("compact 80×24 screen → 80×20 scene", 80, 20),
    ("standard 100×34 screen → 67×30 scene", 67, 30),
    ("wide 120×40 screen → 87×36 scene", 87, 36),
)


def _cases() -> dict[str, SectorDTO]:
    """Hand-built sectors covering every composition the scene can take."""
    return {
        # The everyday arrival: world + port + traffic, foreign fighters on patrol.
        "colony": SectorDTO(
            region="Verdant Reach", sector_id=412, display_id=412, band="Frontier",
            flavor="warm winds over green terraces", beacon=None,
            planets=[SectorPlanetDTO(planet_id=9101, name="New Hesse",
                                     ptype="terrestrial_warm")],
            ports=[SectorPortDTO(port_id=31, name="Port Kalso", klass="Class 2 (BSB)",
                                 is_stardock=False, archetype_id=None)],
            ships=[
                SectorShipDTO(name="Vesk Trader", role="transport",
                              archetype_id=None, contact_id=2),
                SectorShipDTO(name="Kalt Corvette", role="warship",
                              archetype_id=None, contact_id=5),
            ],
            force=SectorForceDTO(owner="Vesk Combine", yours=False, fighters=120,
                                 mode="toll", toll=50, armid_mines=0, limpet_mines=0),
        ),
        # An orbital starbase takes the port slot; your own mines seed the lanes.
        "starbase": SectorDTO(
            region="Hub Approaches", sector_id=77, display_id=77, band="Hub",
            flavor="traffic control chatter on every channel", beacon="Toll lane — keep formation",
            planets=[SectorPlanetDTO(planet_id=88, name="Meridian", ptype="terrestrial_cool")],
            ports=[SectorPortDTO(port_id=7, name="Meridian Exchange", klass="Class 4 (BBS)",
                                 is_stardock=False)],
            starbases=[SectorStarbaseDTO(starbase_id=4, name="Orbital Platform",
                                         owner="yours", operational=True, planet_id=88,
                                         condition="open")],
            ships=[SectorShipDTO(name="Aki Longhauler", role="transport", contact_id=3)],
            force=SectorForceDTO(owner="yours", yours=True, fighters=60, mode="defensive",
                                 toll=0, armid_mines=12, limpet_mines=4),
        ),
        # A half-worked asteroid belt — the contrast case (rocks vs. stars).
        "belt": SectorDTO(
            region="Cinder Drift", sector_id=5310, display_id=5310, band="Void",
            flavor="rock dust hisses across the hull", beacon=None,
            planets=[SectorPlanetDTO(planet_id=531, name="Cinder Drift Field",
                                     ptype="asteroid_belt",
                                     ore_reserve=1400, ore_reserve_max=2600)],
            ships=[SectorShipDTO(name="Rok Prospector", role="transport", contact_id=9)],
        ),
        # A staged gas giant flying its Cloud City (scale-capped on the disc).
        "jovian": SectorDTO(
            region="Amber Deeps", sector_id=2204, display_id=2204, band="Expanse",
            flavor="storm bands the size of moons", beacon=None,
            planets=[SectorPlanetDTO(planet_id=220, name="Heliodor", ptype="jovian",
                                     cloud_city_size=3)],
        ),
        # Post-combat: a named wreck shares the sector with a planet (the PT-44
        # wreck slot), traffic overflows the sprite cap, the Entity drifts through.
        "wreck": SectorDTO(
            region="Contested Marches", sector_id=1893, display_id=1893, band="Frontier",
            flavor="debris pings off the forward screens", beacon=None,
            planets=[SectorPlanetDTO(planet_id=189, name="Redoubt", ptype="barren")],
            discoveries=[SectorDiscovery(discovery_id=61,
                                         label="Wreckage of the Vesk Marauder VII",
                                         kind="wreck", rarity="Uncommon", salvageable=True,
                                         name="Vesk Marauder VII")],
            ships=[
                SectorShipDTO(name="Kalt Lance", role="warship", contact_id=5),
                SectorShipDTO(name="Kalt Pike", role="fighter", contact_id=5),
                SectorShipDTO(name="Aki Witness", role="transport", contact_id=3),
                SectorShipDTO(name="Drifting Pilgrim", role="transport", contact_id=11),
            ],
            anomaly=SectorAnomalyDTO(label="something vast passes beneath sensor thresholds",
                                     contact_id=99, contactable=False),
            force=SectorForceDTO(owner="Kalt Ascendancy", yours=False, fighters=200,
                                 mode="offensive", toll=0, armid_mines=0, limpet_mines=0),
        ),
        # No planet: a nebula fills the sky as the scene's primary body.
        "nebula": SectorDTO(
            region="the Rose Veil", sector_id=3117, display_id=3117, band="Deep",
            flavor="the void glows rose and gold", beacon=None,
            discoveries=[SectorDiscovery(discovery_id=22, label="the Rose Veil",
                                         kind="nebula", rarity="Rare", salvageable=True,
                                         name="the Rose Veil")],
            ships=[SectorShipDTO(name="Dust Skimmer", role="transport", contact_id=4)],
        ),
        # No planet: a wormhole is the scene's primary body.
        "wormhole": SectorDTO(
            region="the Hollow", sector_id=9414, display_id=9414, band="Void",
            flavor="space folds wrong here", beacon=None,
            discoveries=[SectorDiscovery(discovery_id=14, label="the Hollow Gate",
                                         kind="wormhole", rarity="Rare", salvageable=False,
                                         name="the Hollow Gate", collected=True,
                                         warp_to=9415)],
            ships=[SectorShipDTO(name="Silent Cartographer", role="transport",
                                 contact_id=7)],
        ),
        # Nothing but a lone port — the station is the primary body.
        "port-only": SectorDTO(
            region="Waystation Verge", sector_id=640, display_id=640, band="Expanse",
            flavor="a single docking light blinks in the dark", beacon=None,
            ports=[SectorPortDTO(port_id=64, name="Verge Depot", klass="Class 1 (SBB)",
                                 is_stardock=False)],
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--case", help="render only this case (see --list)")
    parser.add_argument("--size", help="render only WxH, e.g. 87x36")
    parser.add_argument("--list", action="store_true", help="list case names and exit")
    args = parser.parse_args()

    cases = _cases()
    if args.list:
        print("\n".join(cases))
        return
    if args.case:
        cases = {args.case: cases[args.case]}
    sizes = SIZES
    if args.size:
        sw, _, shh = args.size.partition("x")
        sizes = ((args.size, int(sw), int(shh)),)

    console = Console()
    cfg = SceneArtConfig()
    for name, sector in cases.items():
        for label, w, h in sizes:
            console.print(Rule(f"{name} — {label}"))
            console.print(_SceneComposer(sector, cfg).compose(w, h))
            console.print()


if __name__ == "__main__":
    main()
