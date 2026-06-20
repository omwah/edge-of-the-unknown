"""Procedural terrain generation using OpenSimplex noise."""

import random
from opensimplex import OpenSimplex
from rich.text import Text

# FEATURES_REGISTRY maps a generic feature name to a list of its visual representations.
# Format: "feature_name": [("character", relative_frequency_weight), ...]
FEATURES_REGISTRY = {
    "water_deep": [
        ("~", 1),
        ("=", 1),
    ],
    "water_shallow": [
        ("~", 1),
        ("-", 1),
    ],
    "sand": [
        (".", 1),
        (",", 1),
    ],
    "grass": [
        ('"', 1),
        ("'", 1),
    ],
    "forest": [
        ("T", 1),
        ("Y", 1),
        ("t", 1),
    ],
    "mountain": [
        ("^", 1),
        ("A", 1),
    ],
    "snow": [
        ("*", 1),
        ("+", 1),
    ],
    "ice": [
        ("_", 1),
        ("-", 1),
    ],
    "ash": [
        ("_", 1),
        ("-", 1),
        (".", 1),
    ],
    "crater": [
        ("o", 1),
        ("O", 1),
        ("C", 1),
    ],
    "dust": [
        (".", 1),
        ("_", 1),
    ],
    "rock": [
        ("o", 1),
        ("O", 1),
        ("@", 1),
    ],
    "debris": [
        ("*", 1),
        (",", 1),
        (".", 1),
    ],
    "gas_thick": [
        ("=", 1),
        ("#", 1),
    ],
    "gas_thin": [
        ("-", 1),
        ("~", 1),
    ],
    "void": [
        (" ", 1),
    ],
}

# BIOMES_REGISTRY maps a planet subtype to its noise generation parameters and visual bands.
# Format:
#   "subtype_name": {
#       "scale_x": float,  # Noise stretching factor along the X axis
#       "scale_y": float,  # Noise stretching factor along the Y axis
#       "bands": [
#           (noise_threshold_float, "feature_name", "rich_color_string"),
#           ...
#       ]
#   }
BIOMES_REGISTRY = {
    "terrestrial_warm": {
        "scale_x": 15.0, "scale_y": 15.0,
        "bands": [
            (-0.2, "water_deep", "blue"),
            (-0.05, "water_shallow", "cyan"),
            (0.05, "sand", "bright_yellow"),
            (0.3, "grass", "green"),
            (0.6, "forest", "dark_green"),
            (0.8, "mountain", "bright_black"),
            (1.0, "snow", "white"),
        ]
    },
    "terrestrial_cool": {
        "scale_x": 15.0, "scale_y": 15.0,
        "bands": [
            (-0.1, "water_deep", "blue"),
            (0.1, "water_shallow", "cyan"),
            (0.3, "dust", "white"),
            (0.5, "grass", "dark_green"),
            (0.7, "forest", "green"),
            (0.9, "mountain", "white"),
            (1.0, "snow", "bright_white"),
        ]
    },
    "terrestrial_hot": {
        "scale_x": 12.0, "scale_y": 12.0,
        "bands": [
            (-0.2, "water_deep", "red"),
            (0.0, "water_shallow", "bright_red"),
            (0.2, "ash", "dark_gray"),
            (0.5, "dust", "bright_black"),
            (0.8, "mountain", "red"),
            (1.0, "snow", "yellow"),
        ]
    },
    "terrestrial_cold": {
        "scale_x": 18.0, "scale_y": 18.0,
        "bands": [
            (-0.2, "water_shallow", "cyan"),
            (0.1, "ice", "white"),
            (0.4, "snow", "bright_white"),
            (0.7, "mountain", "cyan"),
            (1.0, "ice", "blue"),
        ]
    },
    "jovian": {
        "scale_x": 50.0, "scale_y": 5.0,
        "bands": [
            (-0.4, "gas_thick", "#8B4513"),
            (-0.1, "gas_thin", "#D2691E"),
            (0.2, "water_shallow", "#F4A460"),
            (0.5, "gas_thick", "#FFDEAD"),
            (0.8, "gas_thin", "#D2691E"),
            (1.0, "water_shallow", "#8B4513"),
        ]
    },
    "asteroid_belt": {
        "scale_x": 8.0, "scale_y": 8.0,
        "bands": [
            (-0.3, "void", "black"),
            (0.3, "dust", "bright_black"),
            (0.6, "rock", "gray"),
            (0.8, "rock", "white"),
            (1.0, "debris", "bright_white"),
        ]
    },
    "barren": {
        "scale_x": 15.0, "scale_y": 15.0,
        "bands": [
            (-0.1, "dust", "yellow"),
            (0.2, "rock", "bright_yellow"),
            (0.6, "crater", "red"),
            (1.0, "mountain", "bright_red"),
        ]
    }
}

def get_biome_feature(val: float, biomes: list[tuple[float, str, str]]) -> tuple[str, str]:
    """Return the feature name and color for a given noise value."""
    for threshold, feature_name, color in biomes:
        if val <= threshold:
            return feature_name, color
    return biomes[-1][1], biomes[-1][2]

def resolve_feature_char(rng: random.Random, feature_name: str, features_registry: dict[str, list[tuple[str, int]]]) -> str:
    """Resolve a feature name to a specific character based on frequencies."""
    choices = features_registry.get(feature_name, [("?", 1)])
    chars = [c[0] for c in choices]
    weights = [c[1] for c in choices]
    return rng.choices(chars, weights=weights, k=1)[0]

class TerrainGenerator:
    """Procedural terrain generator using configured noise and biomes."""
    
    def __init__(
        self,
        biomes_registry: dict[str, dict[str, any]] | None = None,
        features_registry: dict[str, list[tuple[str, int]]] | None = None,
        asteroid_noise_scale: float = 12.0,
        asteroid_cluster_threshold: float = 0.1,
        asteroid_max_fill_rate: float = 0.9,
    ):
        self.biomes_registry = biomes_registry or BIOMES_REGISTRY
        self.features_registry = features_registry or FEATURES_REGISTRY
        self.asteroid_noise_scale = asteroid_noise_scale
        self.asteroid_cluster_threshold = asteroid_cluster_threshold
        self.asteroid_max_fill_rate = asteroid_max_fill_rate
        
        # Extract valid debris characters and colors from the registry bands
        belt_bands = self.biomes_registry.get("asteroid_belt", {}).get("bands", [])
        
        chars = []
        colors = []
        for _, feature_name, color in belt_bands:
            if feature_name != "void":
                for char, _ in self.features_registry.get(feature_name, []):
                    if char.strip():
                        chars.append(char)
                if color.strip():
                    colors.append(color)
                    
        self.asteroid_chars = list(dict.fromkeys(chars))
        self.asteroid_colors = list(dict.fromkeys(colors))
        
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
                feature_name, color = get_biome_feature(noise_val, bands)
                char = resolve_feature_char(rng, feature_name, self.features_registry)
                map_text.append(char, style=color)
            if y < height - 1:
                map_text.append("\n")
                
        return map_text
