"""Procedural Port and Starbase art.

Ports are small, iconic sprites (as little as 3 cells tall), so this module
uses a *compositional / template* approach rather than SDF rasterization: each
port subtype is a set of hand-authored ASCII silhouettes at a few size tiers.
At those resolutions an implicit-surface (SDF) trace has too few samples to read
as anything recognizable, while a hand-drawn silhouette stays crisp and keeps
the BBS/ANSI heritage the project is going for.

The renderer picks the largest tier that fits the requested bounds, centers it,
recolors the shading levels per the owner's *archetype* palette, and layers light
seeded variation (navigation-beacon hue, lit windows) on top so repeat ports
differ without losing their iconic shape. Palettes key off ``archetype_id``
rather than the species id/name: a roster can rename or reskin a species, but its
archetype (humanoid_diplomat, brain_dome_automaton, ...) is the stable visual
identity, so the hull look stays put across roster edits.

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
#   any other char -> a facet feature (see _HULL_CHARS): drawn in the archetype
#                     facet colour over a bright-hull background, 
#                     e.g. ☉ ° ◇ ◆ ◊ ⁐ ≡ ◇ ◆ ☉
PORT_ART: dict[str, tuple[tuple[str, ...], ...]] = {
    # The hero. Vertical, symmetric: beacon, tower, docking-arm platform,
    # tapering chevron body, engine glow -- the TW2002 StarDock shape.
    "stardock": (
        (
            "       R       ",
            "       █       ",
            "      ███      ",
            "    ▟█████▙    ",
            "╾─▓████◊████▓─╼",
            "    ▜██≡██▛    ",
            "     ▓███▓     ",
            "      ▜█▛      ",
            "       Y       ",
        ),
        (
            "      R      ",
            "      █      ",
            "    ▟███▙    ",
            "╾─▓███████▓─╼",
            "    ▓███▓    ",
            "     ▜█▛     ",
            "      Y      ",
        ),
        (
            "    R    ",
            "   ▟█▙   ",
            "╾▟█████▙╼",
            "   ▜█▛   ",
            "    Y    ",
        ),
        (
            "  R  ",
            "╾███╼",
            "  Y  ",
        ),
    ),
    # Compact trading module: boxed core, dish/antenna, side solar panels.
    "trading_port": (
        (
            "     ▴     ",
            "     │     ",
            "   ┌───┐   ",
            "▤──┤███├──▤",
            "   │███│   ",
            "▤──┤███├──▤",
            "   └───┘   ",
            "     │     ",
            "     ▾     ",
        ),
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
            "   ▄▄▄▄▄   ",
            "  ▟█████▙  ",
            " ▟███████▙ ",
            "▟█████████▙",
            "███████████",
            "▜█████████▛",
            " ▜███████▛ ",
            "  ▜█████▛  ",
            "   ▀▀▀▀▀   ",
        ),
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
    pools (a steady hue is drawn per station), the lit-window hue pool, and the
    ``facet`` colour -- the foreground hue for surface-feature glyphs, drawn over
    a bright-hull background so the feature reads as etched into the plating."""

    bright: str
    mid: str
    dark: str
    top: tuple[str, ...]
    bottom: tuple[str, ...]
    window: tuple[str, ...]
    facet: str


# Hull palettes keyed by ``archetype_id`` (see config/roster_default.yaml). The
# Federation 'humanoid_diplomat' reads as the grey hull of the classic StarDock;
# every other archetype gets a distinct hull/beacon hue family. Unknown archetypes
# fall back to 'default'.
ARCHETYPE_STYLES: dict[str, PortStyle] = {
    # Terran/Centaurian Federation -- grey plating, red/yellow nav lights.
    "humanoid_diplomat": PortStyle(
        bright="grey85", mid="grey58", dark="grey35",
        top=("red", "bright_red"),
        bottom=("yellow", "bright_yellow"),
        window=("bright_cyan", "bright_yellow", "grey100"),
        facet="grey15",
    ),
    # Vesk -- warm fox-folk technologists: amber-khaki hull, cyan windows.
    "canid_technologist": PortStyle(
        bright="khaki1", mid="dark_khaki", dark="grey35",
        top=("orange1", "gold1"),
        bottom=("cyan", "bright_cyan"),
        window=("gold1", "bright_white"),
        facet="dark_orange3",
    ),
    # Selvani -- soft-bodied envoys: aqua/teal organic hull.
    "tentacled_envoy": PortStyle(
        bright="pale_turquoise1", mid="cyan", dark="grey30",
        top=("aquamarine1", "cyan"),
        bottom=("turquoise2", "cyan"),
        window=("pale_turquoise1", "bright_white"),
        facet="dark_cyan",
    ),
    # Helot -- cold brain-dome automata: chrome and electric blue.
    "brain_dome_automaton": PortStyle(
        bright="grey93", mid="grey62", dark="grey30",
        top=("bright_cyan", "cyan"),
        bottom=("dodger_blue1", "bright_cyan"),
        window=("bright_cyan", "grey100"),
        facet="deep_sky_blue4",
    ),
    # Quill -- predatory salvagers: rusted bronze hull, ember lights.
    "ribbon_salvager": PortStyle(
        bright="tan", mid="dark_orange3", dark="grey23",
        top=("orange_red1", "red"),
        bottom=("orange1", "dark_orange"),
        window=("orange1", "red"),
        facet="grey15",
    ),
    # Stryx -- time-dabbling brokers: violet, uncanny.
    "temporal_broker": PortStyle(
        bright="plum1", mid="medium_purple", dark="grey27",
        top=("magenta", "violet"),
        bottom=("blue_violet", "purple"),
        window=("plum1", "bright_white"),
        facet="purple4",
    ),
    # The Concordance -- bodiless arbiter: pale gold, luminous.
    "cosmic_arbiter": PortStyle(
        bright="khaki1", mid="gold3", dark="grey42",
        top=("gold1", "yellow"),
        bottom=("bright_white", "gold1"),
        window=("gold1", "bright_white"),
        facet="dark_goldenrod",
    ),
    # Dignar -- aristocratic mind-mages: royal orchid/purple.
    "telepath_aristocrat": PortStyle(
        bright="orchid", mid="purple", dark="grey27",
        top=("magenta", "bright_magenta"),
        bottom=("violet", "magenta"),
        window=("orchid", "bright_white"),
        facet="purple4",
    ),
    # Cibelline -- engineered aesthetes: rose and pink-gold finery.
    "engineered_aesthete": PortStyle(
        bright="pink1", mid="hot_pink3", dark="grey30",
        top=("gold1", "yellow"),
        bottom=("deep_pink2", "hot_pink"),
        window=("gold1", "pink1"),
        facet="medium_violet_red",
    ),
    # Selvi -- playful imps: bright pinks and magenta.
    "amorous_imp": PortStyle(
        bright="light_pink1", mid="hot_pink", dark="grey30",
        top=("hot_pink", "magenta"),
        bottom=("bright_magenta", "hot_pink"),
        window=("light_pink1", "bright_white"),
        facet="medium_violet_red",
    ),
    # Vennrith -- horned grudge-keepers: iron grey and blood red.
    "horned_grudgekeeper": PortStyle(
        bright="grey66", mid="red3", dark="dark_red",
        top=("red", "bright_red"),
        bottom=("orange3", "red"),
        window=("red", "orange1"),
        facet="grey15",
    ),
    # Thessarch -- psionic overlords: deep indigo authority.
    "psionic_overlord": PortStyle(
        bright="slate_blue1", mid="purple4", dark="grey23",
        top=("blue_violet", "purple"),
        bottom=("dodger_blue1", "blue"),
        window=("slate_blue1", "bright_cyan"),
        facet="grey15",
    ),
    # Thessbrood -- colonial broodmasters: sickly insectoid chartreuse.
    "colonial_broodmaster": PortStyle(
        bright="green_yellow", mid="chartreuse4", dark="grey23",
        top=("green_yellow", "chartreuse1"),
        bottom=("yellow3", "chartreuse3"),
        window=("green_yellow", "bright_yellow"),
        facet="green4",
    ),
    # Dacaran -- winged schemers: cold slate and dark teal.
    "winged_schemer": PortStyle(
        bright="grey62", mid="cadet_blue", dark="grey27",
        top=("dark_cyan", "cyan"),
        bottom=("steel_blue", "cyan"),
        window=("cyan", "grey100"),
        facet="grey15",
    ),
}
# Federation hull as the catch-all style for unknown/unset archetypes.
ARCHETYPE_STYLES["default"] = ARCHETYPE_STYLES["humanoid_diplomat"]

# Hull-glyph shading levels: bright (lit plating), dark (shadowed recesses), and
# -- by exclusion -- mid for every other structural glyph (bevels, struts, arms,
# panels, box edges).
_BRIGHT_CHARS = frozenset("█")
_DARK_CHARS = frozenset("▒░")
_MID_CHARS = frozenset("▟▙▜▛▓▄▀╾╼─◢◣◥◤▴▾│┌┐└┘┤├▤▦")

# The complete, closed set of glyphs the sprites draw as *hull*. A hull cell is
# painted in its shading tone over the black void; ANY other non-space glyph is a
# *facet* -- a surface feature (e.g. ☉ ◘ ◙ ° ◇ ◆ ◊ ▬ ⁐ ≡) drawn in the archetype
# facet colour over a bright-hull background so its negative space blends into
# the surrounding plating. We enumerate the hull set rather than every possible
# facet because the hull alphabet is small and closed, so new feature glyphs just
# work when dropped into a template.
_HULL_CHARS = _BRIGHT_CHARS | _DARK_CHARS | _MID_CHARS

# Background of every hull cell: the black of space.
_VOID_BG = "black"

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
        archetype_id: str | None = None,
    ) -> Text:
        """Generate a procedural space port sprite, hued by owner ``archetype_id``."""
        tiers = PORT_ART.get(subtype.lower(), PORT_ART["trading_port"])
        archetype_key = (archetype_id or "default").lower()
        style = ARCHETYPE_STYLES.get(archetype_key, ARCHETYPE_STYLES["default"])

        bright = style.bright
        mid = style.mid
        dark = style.dark
        facet = style.facet
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
                elif char in _HULL_CHARS:
                    # Hull plating: a shading tone over the black of space.
                    if char in _BRIGHT_CHARS and rng.random() < _WINDOW_PROB:
                        color = rng.choice(windows)
                    elif char in _DARK_CHARS:
                        color = dark
                    elif char in _BRIGHT_CHARS:
                        color = bright
                    else:
                        color = mid
                    map_text.append(char, style=f"{color} on {_VOID_BG}")
                else:
                    # Facet feature: a detail glyph over a patch of bright hull,
                    # so its surrounding negative space matches the plating.
                    map_text.append(char, style=f"{facet} on {bright}")

            if y < height - 1:
                map_text.append("\n")

        return map_text
