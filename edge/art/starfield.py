"""Procedural starfield generation."""

import random
from dataclasses import dataclass
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

@dataclass(frozen=True)
class StarfieldParams:
    """Per-subtype knobs turning the noise field into stars.

    threshold  - noise cutoff above which the local density ramp kicks in
    max_fill   - peak star probability in the densest regions
    min_fill   - baseline scatter probability (0.0 == genuine empty voids)
    scale      - noise feature size (smaller == tighter clusters)
    """

    threshold: float
    max_fill: float
    min_fill: float
    scale: float


# Generation parameters per procedural starfield variation.
STARFIELD_PRESETS: dict[str, StarfieldParams] = {
    "standard": StarfieldParams(threshold=-0.5, max_fill=0.15, min_fill=0.02, scale=15.0),
    "dense": StarfieldParams(threshold=-0.8, max_fill=0.25, min_fill=0.05, scale=15.0),
    # genuine empty space between sparse stars
    "sparse": StarfieldParams(threshold=0.0, max_fill=0.05, min_fill=0.0, scale=15.0),
    # tighter clusters with dark voids between them
    "cluster": StarfieldParams(threshold=0.3, max_fill=0.5, min_fill=0.0, scale=10.0),
}

# Available procedural starfield variations
STARFIELD_SUBTYPES = list(STARFIELD_PRESETS)

class StarfieldGenerator:
    """Generates procedural background starfields using noise clustering."""
    
    def __init__(
        self,
        octaves: int = 3,
        star_chars: list[tuple[str, int]] | None = None,
        star_colors: list[tuple[str, int]] | None = None,
    ):
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
        - 'standard': standard starfield
        - 'dense': more stars everywhere
        - 'sparse': very few stars
        - 'cluster': tightly grouped dense star clusters
        """
        noise_seed = rng.randint(0, 2**31 - 1)
        gen = OpenSimplex(seed=noise_seed)

        map_text = Text()

        params = STARFIELD_PRESETS.get(subtype.lower(), STARFIELD_PRESETS["standard"])
        threshold = params.threshold
        fill_rate = params.max_fill
        min_fill = params.min_fill
        scale = params.scale

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
