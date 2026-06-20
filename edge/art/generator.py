"""Procedural ASCII art generation logic."""

import random

def generate_sprite(
    entity_type: str,
    subtype: str,
    seed: int,
    width: int,
    height: int,
    owner_species: str | None = None
) -> str:
    """Generate a procedural ASCII sprite based on parameters.
    
    Args:
        entity_type: "planet", "terrain", "ship", or "port"
        subtype: The specific role or type (e.g., "terrestrial_warm", "fighter")
        seed: The deterministic seed derived from game_seed and entity_id
        width: The target width in characters
        height: The target height in lines
        owner_species: Optional species name for stylistic variations
        
    Returns:
        A multiline string representing the generated ASCII art.
    """
    # Derive a local PRNG from the input parameters to ensure determinism
    rng_seed = f"{seed}|{entity_type}|{subtype}"
    if owner_species:
        rng_seed += f"|{owner_species}"
    rng = random.Random(rng_seed)
    
    # TODO: Implement the actual compositional/noise/SDF algorithms based on type
    # For now, return a basic structural placeholder to verify the CLI works
    
    if width < 2 or height < 2:
        return "?"
        
    lines = []
    lines.append("+" + "-" * (width - 2) + "+")
    for _ in range(height - 2):
        row = "|"
        for _ in range(width - 2):
            char = rng.choice([".", "*", " ", "o", "O", "~", "+", "x"])
            row += char
        row += "|"
        lines.append(row)
    lines.append("+" + "-" * (width - 2) + "+")
    
    return "\n".join(lines)
