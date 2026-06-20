"""Procedural ASCII art generation logic."""

import random
from functools import lru_cache
from rich.text import Text

from edge.art.terrain import TerrainGenerator

_TERRAIN_GEN = TerrainGenerator()

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
    if entity_type in ("terrain", "planet"):
        return _TERRAIN_GEN.generate(rng, subtype, width, height)
    
    # Placeholder for other types (ships, ports, subsystems)
    if width < 2 or height < 2:
        return Text("?")
        
    lines = Text()
    lines.append("+" + "-" * (width - 2) + "+\n")
    for _ in range(height - 2):
        row = "|"
        for _ in range(width - 2):
            char = rng.choice([".", "*", " ", "o", "O", "~", "+", "x"])
            row += char
        row += "|\n"
        lines.append(row)
    lines.append("+" + "-" * (width - 2) + "+")
    
    return lines
