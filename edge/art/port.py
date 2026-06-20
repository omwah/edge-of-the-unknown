"""Procedural Port and Starbase art.

Ports are small, iconic sprites (as little as 3 cells tall), so this module
uses a *compositional / template* approach rather than SDF rasterization: each
port subtype is a set of hand-authored ASCII silhouettes at a few size tiers.
At those resolutions an implicit-surface (SDF) trace has too few samples to read
as anything recognizable, while a hand-drawn silhouette stays crisp and keeps
the BBS/ANSI heritage the project is going for.

The renderer picks the largest tier that fits the requested bounds, centers it,
recolors the shading levels per the owner species' palette, and layers light
seeded variation (navigation-beacon hue, lit windows) on top so repeat ports
differ without losing their iconic shape.

The flagship ``stardock`` silhouette deliberately evokes the classic TradeWars
2002 Federation StarDock: a vertical, left/right-symmetric station with a red
beacon up top, a control tower, a wide platform trailing thin docking arms, a
tapering chevron body, and a yellow engine glow at the bottom.
"""

import random
from dataclasses import dataclass
from rich.text import Text

PORT_SUBTYPES = ["trading_port", "starbase", "stardock"]

# Per-subtype silhouettes, ordered LARGEST tier first. Each tier is a tuple of
# rows (rows are centered to the tier's natural width at render time, so minor
# ragged-edge authoring is tolerated). Glyph legend, by shading level:
#   '█'            -> bright hull       (lit, sun-facing plating)
#   half/box chars -> mid hull / struts (bevelled edges, arms, panels)
#   '▒' '░'        -> dark hull         (shadowed recesses)
#   'R'            -> red beacon  (rendered as an upper-half block, top light)
#   'Y'            -> yellow glow (rendered as a lower-half block, engine light)
#   ' '            -> empty space
PORT_ART: dict[str, tuple[tuple[str, ...], ...]] = {
    # The hero. Vertical, symmetric: beacon, tower, docking-arm platform,
    # tapering chevron body, engine glow -- the TW2002 StarDock shape.
    "stardock": (
        (
            "     R     ",
            "     █     ",
            "    ███    ",
            "╾──█████──╼",
            "   ▓███▓   ",
            "    ▜█▛    ",
            "     Y     ",
        ),
        (
            "   R   ",
            "  ▟█▙  ",
            "╾─███─╼",
            "  ▜█▛  ",
            "   Y   ",
        ),
        (
            " R ",
            "╾█╼",
            " Y ",
        ),
    ),
    # Compact trading module: boxed core, dish/antenna, side solar panels.
    "trading_port": (
        (
            "    ▴    ",
            "  ┌───┐  ",
            "▤─┤███├─▤",
            "  └───┘  ",
            "    ▾    ",
        ),
        (
            " ┌─┐ ",
            "▦│█│▦",
            " └─┘ ",
        ),
        (
            "┌─┐",
            "▦█▦",
            "└─┘",
        ),
    ),
    # Fortified octagonal bastion -- squat, armoured, distinct from the others.
    "starbase": (
        (
            "   ▄▄▄   ",
            "  ▟███▙  ",
            " ▟█████▙ ",
            "█████████",
            " ▜█████▛ ",
            "  ▜███▛  ",
            "   ▀▀▀   ",
        ),
        (
            "  ▄▄▄  ",
            " ▟███▙ ",
            "███████",
            " ▜███▛ ",
            "  ▀▀▀  ",
        ),
        (
            " ◢█◣ ",
            "█████",
            " ◥█◤ ",
        ),
    ),
}

@dataclass(frozen=True)
class PortStyle:
    """Palette for a port hull: three shading levels, the navigation-beacon hue
    pools (a steady hue is drawn per station), and the lit-window hue pool."""

    bright: str
    mid: str
    dark: str
    top: tuple[str, ...]
    bottom: tuple[str, ...]
    window: tuple[str, ...]


# Hull palettes keyed by owner species. 'default' / 'human' read as the grey
# Federation hull of the classic StarDock.
SPECIES_STYLES: dict[str, PortStyle] = {
    "human": PortStyle(
        bright="grey85", mid="grey58", dark="grey35",
        top=("red", "bright_red"),
        bottom=("yellow", "bright_yellow"),
        window=("bright_cyan", "bright_yellow", "grey100"),
    ),
    "zorgon": PortStyle(
        bright="green", mid="dark_green", dark="grey23",
        top=("bright_green", "green"),
        bottom=("bright_yellow", "yellow"),
        window=("bright_green", "bright_yellow"),
    ),
    "arachni": PortStyle(
        bright="grey70", mid="red", dark="dark_red",
        top=("bright_red", "red"),
        bottom=("orange1", "bright_red"),
        window=("bright_red", "orange1"),
    ),
}
# Federation hull as the catch-all style.
SPECIES_STYLES["default"] = SPECIES_STYLES["human"]

# Glyphs that read as bright, lit plating; everything else structural defaults
# to the mid level, and these recesses to the dark level.
_BRIGHT_CHARS = frozenset("█")
_DARK_CHARS = frozenset("▒░")

# Chance a bright hull cell lights up as a window, for a touch of life.
_WINDOW_PROB = 0.05


class PortGenerator:
    """Generates iconic, deterministic port/starbase sprites from templates."""

    def _select_tier(
        self, tiers: tuple[tuple[str, ...], ...], width: int, height: int
    ) -> tuple[tuple[str, ...], int, int]:
        """Return the largest tier that fits ``width`` x ``height`` (plus its
        natural width/height). Falls back to the smallest tier when nothing fits
        so a too-small box still renders a centred, cropped silhouette."""
        for tier in tiers:
            nh = len(tier)
            nw = max((len(row) for row in tier), default=0)
            if nw <= width and nh <= height:
                return tier, nw, nh
        smallest = tiers[-1]
        nh = len(smallest)
        nw = max((len(row) for row in smallest), default=0)
        return smallest, nw, nh

    def generate(
        self,
        rng: random.Random,
        subtype: str,
        width: int,
        height: int,
        owner_species: str | None = None,
    ) -> Text:
        """Generate a procedural space port sprite."""
        tiers = PORT_ART.get(subtype.lower(), PORT_ART["trading_port"])
        species_key = (owner_species or "default").lower()
        style = SPECIES_STYLES.get(species_key, SPECIES_STYLES["default"])

        bright = style.bright
        mid = style.mid
        dark = style.dark
        # Pick this station's beacon hues once, so the lights are steady.
        top_color = rng.choice(style.top)
        bottom_color = rng.choice(style.bottom)
        windows = style.window

        tier, nw, nh = self._select_tier(tiers, width, height)
        # Centre the natural art within the requested bounds.
        pad_top = max(0, (height - nh) // 2)

        map_text = Text()
        for y in range(height):
            src = y - pad_top
            row = tier[src].center(nw) if 0 <= src < nh else ""

            # Centre (or, if the box is narrower than the art, crop) horizontally.
            if nw <= width:
                left = (width - nw) // 2
                line = (" " * left) + row + (" " * (width - nw - left))
            else:
                start = (nw - width) // 2
                line = row[start:start + width].ljust(width)

            for char in line:
                if char == " ":
                    map_text.append(" ")
                elif char == "R":
                    map_text.append("▀", style=top_color)
                elif char == "Y":
                    map_text.append("▄", style=bottom_color)
                elif char in _BRIGHT_CHARS:
                    if rng.random() < _WINDOW_PROB:
                        map_text.append(char, style=rng.choice(windows))
                    else:
                        map_text.append(char, style=bright)
                elif char in _DARK_CHARS:
                    map_text.append(char, style=dark)
                else:
                    map_text.append(char, style=mid)

            if y < height - 1:
                map_text.append("\n")

        return map_text
