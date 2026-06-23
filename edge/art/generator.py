"""Procedural ASCII art generation logic."""

import random
from functools import lru_cache
from rich.text import Text

from edge.art.hull import ARCHETYPE_STYLES
from edge.art.terrain import TerrainGenerator
from edge.art.planet import PlanetGenerator
from edge.art.starfield import StarfieldGenerator, STARFIELD_SUBTYPES
from edge.art.port import PortGenerator, PORT_SUBTYPES
from edge.art.ship import ShipGenerator, SHIP_SUBTYPES
from edge.art.discovery import DiscoveryGenerator, DISCOVERY_GRAMMAR

_TERRAIN_GEN = TerrainGenerator(use_fg_color=True, use_bg_color=True)
_PLANET_TERRAIN_GEN = TerrainGenerator(use_fg_color=False, use_bg_color=True)
_PLANET_GEN = PlanetGenerator(terrain_gen=_PLANET_TERRAIN_GEN)
_STARFIELD_GEN = StarfieldGenerator()
_PORT_GEN = PortGenerator()
_SHIP_GEN = ShipGenerator()
_DISCOVERY_GEN = DiscoveryGenerator()


def available_subtypes(entity_type: str) -> list[str]:
    """Return the known subtypes for an entity type.

    Lets callers (e.g. the CLI) enumerate and loop over every subtype themselves;
    ``generate_sprite`` always renders exactly one concrete subtype.
    """
    if entity_type in ("terrain", "planet"):
        return list(_TERRAIN_GEN.biomes_registry.keys())
    if entity_type == "starfield":
        return list(STARFIELD_SUBTYPES)
    if entity_type == "port":
        return list(PORT_SUBTYPES)
    if entity_type == "ship":
        return list(SHIP_SUBTYPES)
    if entity_type == "discovery":
        return list(DISCOVERY_GRAMMAR.keys())
    return []


def available_archetypes() -> list[str]:
    """Return the archetype ids that have a defined art palette.

    Lets the CLI enumerate and loop over every archetype style (``--archetype-id
    all``). The 'default' fallback alias is omitted so it doesn't render as a
    duplicate of the archetype it points at.
    """
    return [a for a in ARCHETYPE_STYLES if a != "default"]


@lru_cache(maxsize=128)
def generate_sprite(
    entity_type: str,
    subtype: str,
    seed: int,
    width: int,
    height: int,
    archetype_id: str | None = None,
    facing: str = "right",
) -> Text:
    """Generate a procedural ASCII sprite based on parameters.

    Args:
        entity_type: "planet", "terrain", "ship", "port", or "discovery"
        subtype: The specific role or type (e.g., "terrestrial_warm", "fighter")
        seed: The deterministic seed derived from game_seed and entity_id
        width: The target width in characters
        height: The target height in lines
        archetype_id: Optional owner archetype id for stylistic variations
            (stable across species renames, unlike a species id/name)
        facing: For ships, "right" (canonical) or "left" -- the same ship flipped
            to point either way. Ignored by the other entity types.

    Returns:
        A rich Text object representing the generated ASCII art.
    """
    # Derive a local PRNG from the input parameters to ensure determinism.
    # ``facing`` is deliberately omitted from the seed: left/right are the same
    # ship, just flipped, so they must share one composition.
    rng_seed = f"{seed}|{entity_type}|{subtype}"
    if archetype_id:
        rng_seed += f"|{archetype_id}"
    rng = random.Random(rng_seed)

    # Route to specific generation algorithms based on entity type
    if entity_type == "terrain":
        return _TERRAIN_GEN.generate(rng, subtype, width, height)

    if entity_type == "planet":
        return _PLANET_GEN.generate(rng, subtype, width, height)

    if entity_type == "starfield":
        return _STARFIELD_GEN.generate(rng, subtype, width, height)

    if entity_type == "port":
        return _PORT_GEN.generate(rng, subtype, width, height, archetype_id)

    if entity_type == "ship":
        return _SHIP_GEN.generate(rng, subtype, width, height, archetype_id, facing)

    if entity_type == "discovery":
        return _DISCOVERY_GEN.generate(rng, subtype, width, height, archetype_id)

    raise ValueError(f"Unknown entity type '{entity_type}'.")
