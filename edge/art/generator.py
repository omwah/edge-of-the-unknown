"""Procedural ASCII art generation logic."""

import random
from functools import lru_cache
from rich.text import Text

from edge.art.terrain import TerrainGenerator
from edge.art.planet import PlanetGenerator
from edge.art.starfield import StarfieldGenerator, STARFIELD_SUBTYPES

_TERRAIN_GEN = TerrainGenerator(use_fg_color=True, use_bg_color=True)
_PLANET_TERRAIN_GEN = TerrainGenerator(use_fg_color=False, use_bg_color=True)
_PLANET_GEN = PlanetGenerator(terrain_gen=_PLANET_TERRAIN_GEN)
_STARFIELD_GEN = StarfieldGenerator()


def available_subtypes(entity_type: str) -> list[str]:
    """Return the known subtypes for an entity type.

    Lets callers (e.g. the CLI) enumerate and loop over every subtype themselves;
    ``generate_sprite`` always renders exactly one concrete subtype.
    """
    if entity_type in ("terrain", "planet"):
        return list(_TERRAIN_GEN.biomes_registry.keys())
    if entity_type == "starfield":
        return list(STARFIELD_SUBTYPES)
    return []


@lru_cache(maxsize=128)
def generate_sprite(
    entity_type: str,
    subtype: str,
    seed: int,
    width: int,
    height: int,
    owner_species: str | None = None
) -> Text:
    """Generate a procedural ASCII sprite based on parameters.
    
    Args:
        entity_type: "planet", "terrain", "ship", or "port"
        subtype: The specific role or type (e.g., "terrestrial_warm", "fighter")
        seed: The deterministic seed derived from game_seed and entity_id
        width: The target width in characters
        height: The target height in lines
        owner_species: Optional species name for stylistic variations
        
    Returns:
        A rich Text object representing the generated ASCII art.
    """
    # Derive a local PRNG from the input parameters to ensure determinism
    rng_seed = f"{seed}|{entity_type}|{subtype}"
    if owner_species:
        rng_seed += f"|{owner_species}"
    rng = random.Random(rng_seed)
    
    # Route to specific generation algorithms based on entity type
    if entity_type == "terrain":
        return _TERRAIN_GEN.generate(rng, subtype, width, height)

    if entity_type == "planet":
        return _PLANET_GEN.generate(rng, subtype, width, height)

    if entity_type == "starfield":
        return _STARFIELD_GEN.generate(rng, subtype, width, height)

    raise ValueError(f"Unknown entity type '{entity_type}'.")
