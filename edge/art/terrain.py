"""Procedural terrain generation using OpenSimplex noise."""

import random
from opensimplex import OpenSimplex
from rich.text import Text

BIOMES_REGISTRY = {
    "terrestrial_warm": {
        "scale_x": 15.0, "scale_y": 15.0,
        "bands": [
            (-0.2, "~", "blue"),          # Deep Water
            (-0.05, "~", "cyan"),         # Shallow Water
            (0.05, ".", "bright_yellow"), # Sand
            (0.3, '"', "green"),          # Grass/Plains
            (0.6, "T", "dark_green"),     # Forest
            (0.8, "^", "bright_black"),   # Mountains
            (1.0, "*", "white"),          # Snow Peaks
        ]
    },
    "terrestrial_cool": {
        "scale_x": 15.0, "scale_y": 15.0,
        "bands": [
            (-0.1, "~", "blue"),
            (0.1, "~", "cyan"),
            (0.3, ".", "white"),         # Frost
            (0.5, '"', "dark_green"),    # Hardy grass
            (0.7, "T", "green"),         # Pine forest
            (0.9, "^", "white"),         # Snow mountains
            (1.0, "*", "bright_white"),  # Glaciers
        ]
    },
    "terrestrial_hot": {
        "scale_x": 12.0, "scale_y": 12.0,
        "bands": [
            (-0.2, "~", "red"),           # Lava
            (0.0, "~", "bright_red"),     # Shallow lava
            (0.2, "_", "dark_gray"),      # Ash
            (0.5, ".", "bright_black"),   # Charred rock
            (0.8, "^", "red"),            # Volcanoes
            (1.0, "*", "yellow"),         # Fire peaks
        ]
    },
    "terrestrial_cold": {
        "scale_x": 18.0, "scale_y": 18.0,
        "bands": [
            (-0.2, "~", "cyan"),          # Freezing water
            (0.1, "_", "white"),          # Ice sheets
            (0.4, ".", "bright_white"),   # Deep snow
            (0.7, "^", "cyan"),           # Ice crags
            (1.0, "*", "blue"),           # Blue ice
        ]
    },
    "jovian": {
        "scale_x": 50.0, "scale_y": 5.0,  # Highly stretched horizontally for gas bands
        "bands": [
            (-0.4, "=", "#8B4513"),       # Saddle Brown
            (-0.1, "-", "#D2691E"),       # Chocolate
            (0.2, "~", "#F4A460"),        # Sandy Brown
            (0.5, "=", "#FFDEAD"),        # Navajo White
            (0.8, "-", "#D2691E"),
            (1.0, "~", "#8B4513"),
        ]
    },
    "asteroid_belt": {
        "scale_x": 8.0, "scale_y": 8.0,   # High frequency for scattered rubble
        "bands": [
            (-0.3, " ", "black"),         # Void
            (0.3, ".", "bright_black"),   # Dust
            (0.6, "o", "gray"),           # Small rocks
            (0.8, "O", "white"),          # Asteroids
            (1.0, "@", "bright_white"),   # Dense clusters
        ]
    },
    "barren": {
        "scale_x": 15.0, "scale_y": 15.0,
        "bands": [
            (-0.1, "_", "yellow"),        # Dust plains
            (0.2, ".", "bright_yellow"),  # Rocks
            (0.6, "o", "red"),            # Craters
            (1.0, "^", "bright_red"),     # High ridges
        ]
    }
}

def get_biome(val: float, biomes: list[tuple[float, str, str]]) -> tuple[str, str]:
    """Return the character and color for a given noise value."""
    for threshold, char, color in biomes:
        if val <= threshold:
            return char, color
    return biomes[-1][1], biomes[-1][2]


class TerrainGenerator:
    """Procedural terrain generator using configured noise and biomes."""
    
    def __init__(
        self,
        biomes_registry: dict[str, dict[str, any]] | None = None,
        asteroid_noise_scale: float = 12.0,
        asteroid_cluster_threshold: float = 0.1,
        asteroid_max_fill_rate: float = 0.9,
    ):
        self.biomes_registry = biomes_registry or BIOMES_REGISTRY
        self.asteroid_noise_scale = asteroid_noise_scale
        self.asteroid_cluster_threshold = asteroid_cluster_threshold
        self.asteroid_max_fill_rate = asteroid_max_fill_rate
        
        # Extract valid debris characters and colors from the registry bands
        belt_bands = self.biomes_registry.get("asteroid_belt", {}).get("bands", [])
        self.asteroid_chars = [char for _, char, _ in belt_bands if char.strip()]
        self.asteroid_colors = list(dict.fromkeys(color for _, char, color in belt_bands if char.strip()))
        
        # Fallbacks just in case the registry is empty
        if not self.asteroid_chars:
            self.asteroid_chars = ["o", "O", ".", "@"]
        if not self.asteroid_colors:
            self.asteroid_colors = ["gray", "white"]

    def _generate_asteroid_belt(
        self, rng: random.Random, gen: OpenSimplex, width: int, height: int
    ) -> Text:
        """Helper to generate sparse debris fields for asteroid belts."""
        map_text = Text()
        threshold = self.asteroid_cluster_threshold
        scale_range = 1.0 - threshold

        for y in range(height):
            for x in range(width):
                cluster_noise = gen.noise2(x / self.asteroid_noise_scale, y / self.asteroid_noise_scale)
                if cluster_noise > threshold:
                    density = (cluster_noise - threshold) / scale_range
                    if rng.random() < density * self.asteroid_max_fill_rate:
                        char = rng.choice(self.asteroid_chars)
                        color = rng.choice(self.asteroid_colors)
                        map_text.append(char, style=color)
                    else:
                        map_text.append(" ", style="black")
                else:
                    map_text.append(" ", style="black")
            if y < height - 1:
                map_text.append("\n")
        return map_text

    def generate(
        self, rng: random.Random, subtype: str, width: int, height: int
    ) -> Text:
        """Generate a procedural terrain map using noise."""
        noise_seed = rng.randint(0, 2**31 - 1)
        gen = OpenSimplex(seed=noise_seed)
        
        if subtype.lower() == "asteroid_belt" or subtype.lower() == "asteroid":
            return self._generate_asteroid_belt(rng, gen, width, height)
            
        biome_config = self.biomes_registry.get(subtype.lower(), self.biomes_registry["barren"])
        bands = biome_config["bands"]
        sx = biome_config["scale_x"]
        sy = biome_config["scale_y"]

        map_text = Text()
        
        for y in range(height):
            for x in range(width):
                noise_val = gen.noise2(x / sx, y / sy)
                char, color = get_biome(noise_val, bands)
                map_text.append(char, style=color)
            if y < height - 1:
                map_text.append("\n")
                
        return map_text
