"""Procedural planet generation using Signed Distance Fields."""

import random
import math
from rich.text import Text
from edge.art.terrain import TerrainGenerator

def get_outline_char(dx: float, dy: float) -> str:
    """Return an appropriate box drawing character for the planet's circular outline."""
    angle = math.degrees(math.atan2(dy, dx)) % 360
    if 337.5 <= angle or angle < 22.5: return "│" 
    if 22.5 <= angle < 67.5: return "╯" 
    if 67.5 <= angle < 112.5: return "─" 
    if 112.5 <= angle < 157.5: return "╰" 
    if 157.5 <= angle < 202.5: return "│" 
    if 202.5 <= angle < 247.5: return "╭" 
    if 247.5 <= angle < 292.5: return "─" 
    if 292.5 <= angle < 337.5: return "╮" 
    return " "

class PlanetGenerator:
    """Procedural planet generator using SDF masks over terrain fills."""
    
    def __init__(self, terrain_gen: TerrainGenerator):
        self.terrain_gen = terrain_gen
        
    @property
    def biomes_registry(self) -> dict:
        """Expose the terrain's biome registry for iteration in CLI."""
        return self.terrain_gen.biomes_registry

    def generate(self, rng: random.Random, subtype: str, width: int, height: int) -> Text:
        """Generate a procedural planet wrapped in a circular SDF."""
        grid = self.terrain_gen.get_grid(rng, subtype, width, height)
        map_text = Text()
        
        center_x = (width - 1) / 2.0
        center_y = (height - 1) / 2.0
        radius_x = width / 2.0
        radius_y = height / 2.0
        
        # Inner fill distance squared (leaves a narrow band for the outline)
        # Using 0.85 means roughly the outer ~10% of the radius is outline.
        fill_dist_sq = 0.85
        
        is_asteroid = subtype.lower() in ("asteroid_belt", "asteroid")

        for y in range(height):
            for x in range(width):
                dx = (x - center_x) / radius_x
                dy = (y - center_y) / radius_y
                dist_sq = dx*dx + dy*dy
                
                if is_asteroid:
                    # Pass through directly without border or spherical mask
                    char, fg, bg = grid[y][x]
                    map_text.append(char, style=fg)
                else:
                    if dist_sq > 1.0:
                        map_text.append(" ", style="black")
                    elif dist_sq > fill_dist_sq:
                        # Draw outline
                        char = get_outline_char(dx, dy)
                        map_text.append(char, style="bright_white")
                    else:
                        # Draw inner terrain fill
                        char, fg, bg = grid[y][x]
                        if bg and bg not in ("black", "default"):
                            style = f"{fg} on {bg}" if fg else f"on {bg}"
                        else:
                            style = fg
                        map_text.append(char, style=style)
                        
            if y < height - 1:
                map_text.append("\n")
                
        return map_text
