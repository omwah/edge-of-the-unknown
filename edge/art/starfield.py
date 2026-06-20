"""Procedural starfield generation."""

import random
from rich.text import Text
from opensimplex import OpenSimplex

from edge.art.noise import fractal_noise

# Default weighted stars. Format is a list of tuples:
# (character_string, relative_probability_weight)
# A higher weight means the character is more likely to be chosen.
DEFAULT_STAR_CHARS = [
    (".", 50),
    ("·", 30),
    ("*", 10),
    ("+", 5),
    ("✦", 2),
    ("✧", 2),
]

# Default weighted colors for the stars. Format is a list of tuples:
# (rich_style_string, relative_probability_weight)
# A higher weight means the color is more likely to be chosen.
DEFAULT_STAR_COLORS = [
    ("dim white", 60),
    ("white", 30),
    ("bright_white", 10),
    ("bright_black", 10), # distant stars
    ("bright_cyan", 2), # occasional blue giant
    ("bright_yellow", 2), # occasional yellow star
]

# Available procedural starfield variations
STARFIELD_SUBTYPES = [
    "default",
    "dense",
    "sparse",
    "cluster",
]

class StarfieldGenerator:
    """Generates procedural background starfields using noise clustering."""
    
    def __init__(
        self,
        noise_scale: float = 15.0,
        cluster_threshold: float = -0.5,
        max_fill_rate: float = 0.15,
        min_fill_rate: float = 0.02,
        octaves: int = 3,
        star_chars: list[tuple[str, int]] | None = None,
        star_colors: list[tuple[str, int]] | None = None,
    ):
        self.noise_scale = noise_scale
        self.cluster_threshold = cluster_threshold
        self.max_fill_rate = max_fill_rate
        self.min_fill_rate = min_fill_rate
        self.octaves = octaves

        # Default weighted stars: mostly tiny dots, rarely larger stars
        self.star_chars = star_chars or DEFAULT_STAR_CHARS
        
        # Default weighted colors: mostly dim, occasionally bright
        self.star_colors = star_colors or DEFAULT_STAR_COLORS

    def _pick_weighted(self, rng: random.Random, choices: list[tuple[str, int]]) -> str:
        total = sum(weight for _, weight in choices)
        r = rng.randint(0, total - 1)
        current = 0
        for item, weight in choices:
            current += weight
            if r < current:
                return item
        return choices[-1][0]

    def generate(self, rng: random.Random, subtype: str, width: int, height: int) -> Text:
        """Generate a procedural starfield.
        
        Supported subtypes:
        - 'default': standard starfield
        - 'dense': more stars everywhere
        - 'sparse': very few stars
        - 'cluster': tightly grouped dense star clusters
        """
        noise_seed = rng.randint(0, 2**31 - 1)
        gen = OpenSimplex(seed=noise_seed)
        
        map_text = Text()
        
        # Adjust parameters based on subtype
        threshold = self.cluster_threshold
        fill_rate = self.max_fill_rate
        min_fill = self.min_fill_rate
        scale = self.noise_scale

        st = subtype.lower()
        if st == "dense":
            threshold = -0.8
            fill_rate = 0.25
            min_fill = 0.05
        elif st == "sparse":
            threshold = 0.0
            fill_rate = 0.05
            min_fill = 0.0  # genuine empty space between sparse stars
        elif st == "cluster":
            threshold = 0.3
            fill_rate = 0.5
            scale = 10.0 # tighter clusters
            min_fill = 0.0  # dark voids between tight clusters are the point

        scale_range = 1.0 - threshold

        for y in range(height):
            for x in range(width):
                # Fractal (multi-octave) noise breaks up the large smooth low
                # regions that otherwise read as big connected black voids.
                cluster_noise = fractal_noise(gen, x, y, scale, self.octaves)

                # Above the cluster threshold the local density ramps the fill
                # rate up; elsewhere a baseline keeps quiet regions speckled
                # rather than collapsing into empty bands.
                if cluster_noise > threshold:
                    density = (cluster_noise - threshold) / scale_range
                    cell_fill = min_fill + density * (fill_rate - min_fill)
                else:
                    cell_fill = min_fill

                if rng.random() < cell_fill:
                    char = self._pick_weighted(rng, self.star_chars)
                    fg = self._pick_weighted(rng, self.star_colors)
                    map_text.append(char, style=fg)
                else:
                    map_text.append(" ")

            if y < height - 1:
                map_text.append("\n")

        return map_text
