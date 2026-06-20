"""Procedural terrain generation using OpenSimplex noise."""

import random
from opensimplex import OpenSimplex
from rich.text import Text

from edge.art.noise import fractal_noise

# FEATURES_REGISTRY maps a generic feature name to a list of its visual representations.
# Format: "feature_name": [("character", relative_frequency_weight), ...]
# Note: Group the character tuples horizontally (up to 6 per row) to maintain compactness and readability.
FEATURES_REGISTRY = {
    "water_deep": [
        ("≋", 2), ("≈", 1),
    ],
    "water_shallow": [
        ("~", 1), ("∿", 1), ("∽", 1),
    ],
    "sand": [
        ("░", 1), ("▒", 1),
    ],
    "grass": [
        ('ψ', 1), ("ʬ", 2), (" ", 2), 
    ],
    "forest": [
        (" ", 40), ("├", 1), ("┝", 1), ("┞", 1), ("┟", 1), ("┠", 1),
        ("┡", 1), ("┢", 1), ("┣", 1), ("┤", 1), ("┥", 1), ("┦", 1),
        ("┧", 1), ("┨", 1), ("┩", 1), ("┪", 1), ("┫", 1), ("┬", 1),
        ("┭", 1), ("┮", 1), ("┯", 1), ("┰", 1), ("┱", 1), ("┲", 1),
        ("┳", 1), ("┴", 1), ("┵", 1), ("┶", 1), ("┷", 1), ("┸", 1),
        ("┹", 1), ("┺", 1), ("┻", 1), ("┼", 1), ("┽", 1), ("┾", 1),
        ("┿", 1), ("╀", 1), ("╁", 1), ("╂", 1), ("╃", 1), ("╄", 1),
        ("╅", 1), ("╆", 1), ("╇", 1), ("╈", 1), ("╉", 1), ("╊", 1),
        ("╋", 1),
    ],
    "mountain": [
        ("^", 2), ("Λ", 1), (" ", 1),
    ],
    "snow": [
        ("*", 1), ("+", 1),
    ],
    "ice": [
        ("_", 1), ("-", 1),
    ],
    "ash": [
        ("_", 1), ("-", 1), (".", 1),
    ],
    "crater": [
        ("o", 0.5), ("O", 0.5), ("◌", 1), ("⁘", 1), (" ", 5),
    ],
    "dust": [
        (".", 1), ("_", 1),
    ],
    "rock": [
        ("•", 1), ("⬢", 1), ("⛬", 1), (" ", 10),
    ],
    "debris": [
        ("*", 1), ("⸝", 1), ("⹁", 1), (".", 1),
    ],
    "gas_thick": [
        ("≓", 0.05), ("≑", 0.5), ("=", 2), 
    ],
    "gas_thin": [
        ("┄", 2), ("─", 1), ("┈", 2), ("~", 2)
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
#           (noise_threshold_float, "feature_name", "fg_color", "bg_color"),
#           ...
#       ]
#   }
BIOMES_REGISTRY = {
    "terrestrial_warm": {
        "scale_x": 15.0, "scale_y": 15.0,
        "bands": [
            (-0.2, "water_deep", "bright_blue", "blue"),
            (-0.05, "water_shallow", "bright_cyan", "cyan"),
            (0.05, "sand", "yellow", "bright_yellow"),
            (0.3, "grass", "bright_green", "green"),
            (0.6, "forest", "#af5f00", "green"),
            (0.8, "mountain", "white", "bright_black"),
            (1.0, "snow", "bright_white", "white"),
        ]
    },
    "terrestrial_cool": {
        "scale_x": 15.0, "scale_y": 15.0,
        "bands": [
            (-0.1, "water_deep", "bright_blue", "blue"),
            (0.1, "water_shallow", "bright_cyan", "cyan"),
            (0.3, "dust", "bright_white", "white"),
            (0.5, "grass", "green", "dark_green"),
            (0.7, "forest", "bright_green", "green"),
            (0.9, "mountain", "white", "bright_black"),
            (1.0, "snow", "bright_white", "white"),
        ]
    },
    "terrestrial_hot": {
        "scale_x": 12.0, "scale_y": 12.0,
        "bands": [
            (-0.2, "water_deep", "bright_red", "red"),
            (0.0, "water_shallow", "yellow", "bright_red"),
            (0.1, "sand", "yellow", "bright_yellow"),
            (0.2, "ash", "dark_gray", "black"),
            (0.5, "dust", "bright_black", "black"),
            (0.8, "mountain", "bright_red", "bright_black"),
            (1.0, "snow", "yellow", "red"),
        ]
    },
    "terrestrial_cold": {
        "scale_x": 18.0, "scale_y": 18.0,
        "bands": [
            (-0.2, "water_shallow", "cyan", "blue"),
            (0.1, "ice", "bright_white", "white"),
            (0.4, "snow", "bright_white", "cyan"),
            (0.7, "mountain", "white", "cyan"),
            (1.0, "ice", "bright_cyan", "blue"),
        ]
    },
    "jovian": {
        "scale_x": 50.0, "scale_y": 5.0,
        "bands": [
            (-0.4, "gas_thick", "black", "#8B4513"),
            (-0.1, "gas_thin", "black", "#D2691E"),
            (0.2, "gas_thin", "black", "#F4A460"),
            (0.5, "gas_thick", "black", "#FFDEAD"),
            (0.8, "gas_thin", "black", "#D2691E"),
            (1.0, "gas_thick", "black", "#8B4513"),
        ]
    },
    "asteroid_belt": {
        "scale_x": 8.0, "scale_y": 8.0,
        "bands": [
            (-0.3, "void", "black", "black"),
            (0.3, "dust", "bright_black", "black"),
            (0.6, "rock", "gray", "black"),
            (0.8, "rock", "white", "black"),
            (1.0, "debris", "bright_white", "black"),
        ]
    },
    "barren": {
        "scale_x": 15.0, "scale_y": 15.0,
        "bands": [
            (-0.1, "dust", "bright_yellow", "yellow"),
            (0.2, "rock", "yellow", "bright_black"),
            (0.6, "crater", "bright_red", "red"),
            (1.0, "mountain", "white", "bright_red"),
        ]
    }
}

def get_biome_feature(val: float, biomes: list[tuple[float, str, str, str]]) -> tuple[str, str, str]:
    """Return the feature name, fg, and bg color for a given noise value."""
    for threshold, feature_name, fg, bg in biomes:
        if val <= threshold:
            return feature_name, fg, bg
    return biomes[-1][1], biomes[-1][2], biomes[-1][3]

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
        asteroid_min_fill_rate: float = 0.06,
        asteroid_octaves: int = 3,
        use_fg_color: bool = True,
        use_bg_color: bool = True,
    ):
        self.biomes_registry = biomes_registry or BIOMES_REGISTRY
        self.features_registry = features_registry or FEATURES_REGISTRY
        self.asteroid_noise_scale = asteroid_noise_scale
        self.asteroid_cluster_threshold = asteroid_cluster_threshold
        self.asteroid_max_fill_rate = asteroid_max_fill_rate
        self.asteroid_min_fill_rate = asteroid_min_fill_rate
        self.asteroid_octaves = asteroid_octaves
        self.use_fg_color = use_fg_color
        self.use_bg_color = use_bg_color
        
        # Extract valid debris characters and colors from the registry bands
        belt_bands = self.biomes_registry.get("asteroid_belt", {}).get("bands", [])
        
        chars = []
        colors = []
        for _, feature_name, fg, bg in belt_bands:
            if feature_name != "void":
                for char, _ in self.features_registry.get(feature_name, []):
                    if char.strip():
                        chars.append(char)
                if fg.strip() and fg != "black":
                    colors.append(fg)
                    
        self.asteroid_chars = list(dict.fromkeys(chars))
        self.asteroid_colors = list(dict.fromkeys(colors))
        
        # Fallbacks just in case the registry is empty
        if not self.asteroid_chars:
            self.asteroid_chars = ["o", "O", ".", "@"]
        if not self.asteroid_colors:
            self.asteroid_colors = ["gray", "white"]

    def get_grid(
        self, rng: random.Random, subtype: str, width: int, height: int
    ) -> list[list[tuple[str, str, str]]]:
        """Generate a raw procedural grid of (char, fg, bg)."""
        noise_seed = rng.randint(0, 2**31 - 1)
        gen = OpenSimplex(seed=noise_seed)

        if subtype.lower() in ("asteroid_belt", "asteroid"):
            return self._get_asteroid_grid(rng, gen, width, height)
        return self._get_biome_grid(rng, gen, subtype, width, height)

    def _get_asteroid_grid(
        self, rng: random.Random, gen: OpenSimplex, width: int, height: int
    ) -> list[list[tuple[str, str, str]]]:
        """Generate a sparse field of clustered debris for asteroid belts."""
        grid = []
        threshold = self.asteroid_cluster_threshold
        scale_range = 1.0 - threshold
        min_fill = self.asteroid_min_fill_rate
        for y in range(height):
            row = []
            for x in range(width):
                cluster_noise = fractal_noise(
                    gen, x, y, self.asteroid_noise_scale, self.asteroid_octaves
                )
                # Every cell keeps a baseline scatter probability so quiet regions
                # stay speckled rather than collapsing into large black voids.
                if cluster_noise > threshold:
                    density = (cluster_noise - threshold) / scale_range
                    fill_rate = min_fill + density * (self.asteroid_max_fill_rate - min_fill)
                else:
                    fill_rate = min_fill
                if rng.random() < fill_rate:
                    char = rng.choice(self.asteroid_chars)
                    fg = rng.choice(self.asteroid_colors)
                    row.append((char, fg, "black"))
                else:
                    row.append((" ", "black", "black"))
            grid.append(row)
        return grid

    def _get_biome_grid(
        self, rng: random.Random, gen: OpenSimplex, subtype: str, width: int, height: int
    ) -> list[list[tuple[str, str, str]]]:
        """Generate a banded biome surface from layered noise."""
        subtype_key = subtype.lower()
        if subtype_key not in self.biomes_registry:
            raise ValueError(
                f"Unknown terrain subtype '{subtype}'. "
                f"Available subtypes: {list(self.biomes_registry.keys())}"
            )

        biome_config = self.biomes_registry[subtype_key]
        bands = biome_config["bands"]
        sx = biome_config["scale_x"]
        sy = biome_config["scale_y"]

        grid = []
        for y in range(height):
            row = []
            ny = (y / max(1, height - 1)) * 2.0 - 1.0
            pole_dist = abs(ny)

            for x in range(width):
                noise_val = gen.noise2(x / sx, y / sy)

                # Polar ice caps: dramatically boost noise near poles on terrestrial planets
                if "terrestrial" in subtype_key and pole_dist > 0.7:
                    pole_factor = (pole_dist - 0.7) / 0.3
                    noise_val += pole_factor * 1.5

                feature_name, fg, bg = get_biome_feature(noise_val, bands)

                if self.use_fg_color:
                    char = resolve_feature_char(rng, feature_name, self.features_registry)
                    final_fg = fg
                else:
                    char = " "
                    final_fg = ""

                final_bg = bg if self.use_bg_color else ""
                row.append((char, final_fg, final_bg))
            grid.append(row)
        return grid

    def generate(
        self, rng: random.Random, subtype: str, width: int, height: int
    ) -> Text:
        """Generate a procedural terrain map using noise."""
        grid = self.get_grid(rng, subtype, width, height)
        map_text = Text()
        
        for y in range(height):
            for x in range(width):
                char, fg, bg = grid[y][x]
                if bg and bg not in ("black", "default"):
                    style = f"{fg} on {bg}" if fg else f"on {bg}"
                else:
                    style = fg
                map_text.append(char, style=style)
            if y < height - 1:
                map_text.append("\n")
                
        return map_text
