"""Procedural terrain generation using OpenSimplex noise.

The *gameplay* band layout (which feature name sits in which noise band, and the
per-planet noise scale) is owned by the pure core seam
`edge.core.groundwar.terrain.BIOME_BANDS`; this module holds only the styling —
per-band colours (`BIOME_COLORS`) and per-feature glyphs (`FEATURES_REGISTRY`) —
and reconstructs the historical `BIOMES_REGISTRY` by zipping the two together, so
band structure has a single source of truth and `edge.core` never imports
`edge.art` (GW-WP02)."""

import colorsys
import random
from opensimplex import OpenSimplex
from rich.color import Color
from rich.text import Text

from edge.art.noise import fractal_noise
from edge.core.groundwar.terrain import BIOME_BANDS

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
    # terrestrial_cold's top band (GW-WP21) — heavier glyphs than flat shelf `ice`, so
    # the two ice bands now separate by weight as well as by their authored colours.
    "glacier": [
        ("=", 2), ("≡", 1),
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
    # Asteroid-belt features carry heavier ink than the generic dust/rock/debris
    # sets: a belt floats over the same black the starfield lives in, so thin
    # glyphs (`.` `•` `*`) read as more stars. Solid geometric chips keep the
    # field unmistakably *rock* (playtest note, 2026-07-17).
    "belt_dust": [
        ("·", 2), ("∙", 1), (" ", 2),
    ],
    "belt_rock": [
        ("●", 3), ("◆", 2), ("⬢", 1), (" ", 3),
    ],
    "belt_debris": [
        ("▪", 2), ("◦", 1), ("*", 1),
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

# BIOME_COLORS maps a planet subtype to its per-band (fg, bg) colour pair,
# index-aligned to `edge.core.groundwar.terrain.BIOME_BANDS[subtype].bands` (the
# gameplay band structure). The historical `BIOMES_REGISTRY` — a subtype -> {
# "scale_x", "scale_y", "bands": [(threshold, feature_name, fg, bg), ...] } map —
# is reconstructed from the two below so band structure has one authority in core
# while colours stay here in the art layer (GW-WP02).
BIOME_COLORS: dict[str, list[tuple[str, str]]] = {
    "terrestrial_warm": [
        ("bright_blue", "blue"), ("bright_cyan", "cyan"), ("yellow", "bright_yellow"),
        ("bright_green", "green"), ("#af5f00", "green"), ("white", "bright_black"),
    ],
    "terrestrial_cool": [
        ("bright_blue", "blue"), ("bright_cyan", "cyan"), ("bright_white", "white"),
        ("green", "dark_green"), ("bright_green", "green"), ("white", "bright_black"),
        ("bright_white", "white"),
    ],
    "terrestrial_hot": [
        ("bright_red", "red"), ("yellow", "bright_red"), ("yellow", "bright_yellow"),
        ("grey35", "black"), ("bright_black", "black"), ("bright_red", "bright_black"),
        ("yellow", "red"),
    ],
    "terrestrial_cold": [
        ("cyan", "blue"), ("bright_white", "white"), ("bright_white", "cyan"),
        ("white", "cyan"), ("bright_cyan", "blue"),
    ],
    "jovian": [
        ("black", "#8B4513"), ("black", "#D2691E"), ("black", "#F4A460"),
        ("black", "#FFDEAD"), ("black", "#D2691E"), ("black", "#8B4513"),
    ],
    # Warm mineral tones (not the starfield's cool white/grey) so the field
    # separates from the stars by colour as well as by glyph weight.
    "asteroid_belt": [
        ("black", "black"), ("grey62", "black"), ("tan", "black"),
        ("orange3", "black"), ("sandy_brown", "black"),
    ],
    "barren": [
        ("bright_yellow", "yellow"), ("yellow", "bright_black"), ("bright_red", "red"),
        ("white", "bright_red"),
    ],
}

BIOMES_REGISTRY = {
    subtype: {
        "scale_x": layout.scale_x,
        "scale_y": layout.scale_y,
        "bands": [
            (threshold, feature_name, fg, bg)
            for (threshold, feature_name), (fg, bg) in zip(layout.bands, BIOME_COLORS[subtype])
        ],
    }
    for subtype, layout in BIOME_BANDS.items()
}

# Some biome bands authored a foreground glyph colour that sits too close to its
# background to read (e.g. `green` on `dark_green`). `readable_fg` measures the
# perceived-luminance gap and, only when a band falls below `_CONTRAST_TRIGGER`,
# nudges the foreground to a hue-preserving lighter/darker variant just past
# `_CONTRAST_TARGET`. Enforcing the "fg must read against bg" convention in code
# keeps every biome and roster legible without per-band colour tables.
#
# The trigger was 0.20 through GW-WP20, which left six landable bands sitting in the
# 0.20-0.26 gap — legible enough to pass the threshold, still muddy to read. GW-WP21
# measured the alternatives (0.20 / 0.26 / 0.35) side by side against the same noise
# seed and settled on 0.26: it catches those six (mountain rock reads noticeably
# harder against its grey) without 0.35's habit of restyling bands that were fine.
# Raising it further is not free — `BIOME_COLORS` is shared with the orbital
# planet-art screens, so every world in the game restyles with it.
_CONTRAST_TRIGGER = 0.26  # correct a band only when its fg/bg gap is below this
_CONTRAST_TARGET = 0.35   # push the adjusted fg at least this far from the bg


def _luminance(rgb: tuple[float, float, float]) -> float:
    """Rec.601 perceived luminance of an (r, g, b) triple in 0..1."""
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def readable_fg(fg: str, bg: str) -> str:
    """`fg` unchanged if it reads against `bg`, else a hue-preserving variant
    (lighter over a dark bg, darker over a light one) with enough contrast."""
    try:
        f = Color.parse(fg).get_truecolor()
        b = Color.parse(bg).get_truecolor()
    except Exception:  # unknown colour name — leave it to the terminal
        return fg
    frgb = (f.red / 255, f.green / 255, f.blue / 255)
    bg_lum = _luminance((b.red / 255, b.green / 255, b.blue / 255))
    if abs(_luminance(frgb) - bg_lum) >= _CONTRAST_TRIGGER:
        return fg
    h, ell, s = colorsys.rgb_to_hls(*frgb)
    direction = 1.0 if bg_lum < 0.5 else -1.0  # move away from the background
    best = frgb
    for step in range(1, 21):
        new_l = min(1.0, max(0.0, ell + direction * step * 0.05))
        best = colorsys.hls_to_rgb(h, new_l, s)
        if abs(_luminance(best) - bg_lum) >= _CONTRAST_TARGET:
            break
        if new_l in (0.0, 1.0):  # ran out of lightness room in this direction
            break
    r, g, bl = (round(c * 255) for c in best)
    return f"#{r:02x}{g:02x}{bl:02x}"


def get_biome_feature(val: float, biomes: list[tuple[float, str, str, str]]) -> tuple[str, str, str]:
    """Return the feature name, and a legible fg/bg colour pair, for a noise value."""
    for threshold, feature_name, fg, bg in biomes:
        if val <= threshold:
            return feature_name, readable_fg(fg, bg), bg
    return biomes[-1][1], readable_fg(biomes[-1][2], biomes[-1][3]), biomes[-1][3]

def resolve_feature_char(rng: random.Random, feature_name: str, features_registry: dict[str, list[tuple[str, int]]]) -> str:
    """Resolve a feature name to a specific character based on frequencies."""
    choices = features_registry.get(feature_name, [("?", 1)])
    chars = [c[0] for c in choices]
    weights = [c[1] for c in choices]
    return rng.choices(chars, weights=weights, k=1)[0]


def style_grid(
    rng: random.Random, noise_seed: int, planet_type: str, width: int, height: int
) -> list[list[tuple[str, str, str]]]:
    """A styled (char, fg, bg) backdrop aligned cell-for-cell with the core grid.

    Seeded from the same `noise_seed` and using the same band thresholds as
    `edge.core.groundwar.terrain.generate_feature_grid`, so every cell resolves to
    the same feature name the gameplay grid records — this only adds the glyph and
    colour the core seam deliberately omits. `rng` drives glyph selection only.
    """
    biome = BIOMES_REGISTRY[planet_type]
    bands = biome["bands"]
    sx, sy = biome["scale_x"], biome["scale_y"]
    gen = OpenSimplex(seed=noise_seed)
    grid: list[list[tuple[str, str, str]]] = []
    for y in range(height):
        row: list[tuple[str, str, str]] = []
        for x in range(width):
            val = gen.noise2(x / sx, y / sy)
            name, fg, bg = get_biome_feature(val, bands)
            row.append((resolve_feature_char(rng, name, FEATURES_REGISTRY), fg, bg))
        grid.append(row)
    return grid

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
        for _, feature_name, fg, _bg in belt_bands:
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
            self.asteroid_colors = ["grey50", "white"]

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
            for x in range(width):
                noise_val = gen.noise2(x / sx, y / sy)

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
