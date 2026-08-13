"""Procedural ASCII art generation logic."""

import random
from functools import lru_cache
from rich.text import Text

from edge.art.terrain import TerrainGenerator
from edge.art.planet import PlanetGenerator
from edge.art.starfield import StarfieldGenerator, STARFIELD_SUBTYPES
from edge.art.sprites import SPRITES, fit_box, pad_to
from edge.art.discovery import DiscoveryGenerator, DISCOVERY_GRAMMAR
from edge.art.static import StaticGenerator, STATIC_SUBTYPES

_TERRAIN_GEN = TerrainGenerator(use_fg_color=True, use_bg_color=True)
_PLANET_TERRAIN_GEN = TerrainGenerator(use_fg_color=False, use_bg_color=True)
_PLANET_GEN = PlanetGenerator(terrain_gen=_PLANET_TERRAIN_GEN)
_STARFIELD_GEN = StarfieldGenerator()
_DISCOVERY_GEN = DiscoveryGenerator()
_STATIC_GEN = StaticGenerator()


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
        return list(SPRITES.available_subtypes("port"))
    if entity_type == "ship":
        return list(SPRITES.available_subtypes("ship"))
    if entity_type == "discovery":
        return list(DISCOVERY_GRAMMAR.keys())
    if entity_type == "static":
        return list(STATIC_SUBTYPES)
    return []


def available_archetypes() -> list[str]:
    """Return the archetype ids that have a defined art palette."""
    return sorted(SPRITES.palettes.archetypes)


@lru_cache(maxsize=128)
def generate_sprite(
    entity_type: str,
    subtype: str,
    seed: int,
    width: int,
    height: int,
    archetype_id: str | None = None,
    facing: str = "right",
    depletion: float = 0.0,
    cloud_city: int = 0,
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
        depletion: For an asteroid-belt planet, the 0..1 fraction of its ore already
            mined out -- rocks thin as the field empties (PT-52). Ignored elsewhere.
        cloud_city: For a jovian planet, the size of the Cloud City built there (PT-54);
            0 is bare clouds. Bigger cities are bigger structures. Ignored elsewhere.

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
        return _PLANET_GEN.generate(rng, subtype, width, height, depletion, cloud_city)

    if entity_type == "starfield":
        return _STARFIELD_GEN.generate(rng, subtype, width, height)

    # Ships and stations are tiered YAML art: the requested box is a *bound*, and
    # `fit_box` resolves it to the richest tier that fits inside it. Asking for
    # the box directly would let the library centre-crop a too-wide tier and
    # return the middle of the hull band (see `fit_box`), so Edge pads the tier's
    # natural render into the requested box itself.
    if entity_type == "port":
        fw, fh = fit_box("port", subtype, max_width=width, max_height=height,
                         archetype_id=archetype_id)
        return pad_to(
            SPRITES.generate_port(
                subtype, seed, min(fw, width), min(fh, height), archetype_id),
            width, height)

    if entity_type == "ship":
        fw, fh = fit_box("ship", subtype, max_width=width, max_height=height,
                         archetype_id=archetype_id, facing=facing)
        return pad_to(
            SPRITES.generate_ship(
                subtype, seed, min(fw, width), min(fh, height), archetype_id, facing),
            width, height)

    if entity_type == "discovery":
        return _DISCOVERY_GEN.generate(rng, subtype, width, height, archetype_id)

    if entity_type == "static":
        return _STATIC_GEN.generate(rng, subtype, width, height)

    raise ValueError(f"Unknown entity type '{entity_type}'.")
