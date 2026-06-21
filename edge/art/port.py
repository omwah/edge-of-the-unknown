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

# Sprites are LEFT/RIGHT symmetric and stack as vertical *bands*, so rather than
# storing whole fixed-size silhouettes we store recombinable PARTS and compose
# them. Each part is authored as its LEFT HALF, *including the centre column*, and
# mirrored to full width at render time (see ``_mirror_row`` / ``_MIRROR``); this
# guarantees symmetry and halves authoring. A subtype's grammar is an ordered
# stack of slots (cap -> repeatable body -> base); the composer picks one part per
# slot and repeats the body to fill the requested height -- so any height in range
# is reachable, and interchangeable parts give per-station variety.
#
# Glyph legend, by shading level (same alphabet as before):
#   '█'            -> bright hull       (lit, sun-facing plating)
#   half/box chars -> mid hull / struts (bevelled edges, arms, panels)
#   '▒' '░'        -> dark hull         (shadowed recesses)
#   'R'            -> red beacon  (rendered as an upper-half block, top light)
#   'Y'            -> yellow glow (rendered as a lower-half block, engine light)
#   ' '            -> empty space
#   any other char -> a facet feature (see _HULL_CHARS): drawn in the archetype
#                     facet colour over a bright-hull background,
#                     e.g. ☉ ° ◇ ◆ ◊ ⁐ ≡ ◇ ◆ ☉
# A part's centre-column glyph (the last char of each left-half row) must be
# self-symmetric (in ``_SELF_SYMMETRIC``) so it reads correctly straddling the
# mirror axis; corner/quadrant/triangle glyphs would seam.


@dataclass(frozen=True)
class Part:
    """A recombinable band fragment, authored as left-half rows (centre column
    included) and mirrored to full width. ``repeatable`` parts may be stacked
    multiple times by the composer to grow a sprite's height."""

    left: tuple[str, ...]
    repeatable: bool = False


@dataclass(frozen=True)
class Slot:
    """One position in a subtype's vertical band stack. The composer picks a
    single part from ``parts`` (seeded), then -- if that part is repeatable --
    emits its rows between ``min_repeat`` and ``max_repeat`` times to fill the box."""

    parts: tuple[Part, ...]
    min_repeat: int = 1
    max_repeat: int = 1


# Per-subtype band grammars, ordered top (cap) -> bottom (base). The FIRST part of
# each slot is the *canonical* one: choosing all canonical parts at the repeat that
# matches the historic height reproduces the original largest silhouette exactly
# (this is "decompose what we had", not "redraw"). The remaining parts are
# interchangeable variants that give repeat ports visible variety.
PORT_GRAMMAR: dict[str, tuple[Slot, ...]] = {
    # The hero. Beacon + shoulders, docking-arm platform, tapering chevron body,
    # engine glow -- the TW2002 StarDock shape.
    "stardock": (
        # Cap: red beacon on a mast, widening to shoulders.
        Slot((
            Part(("       R", "       █", "      ██")),          # canonical
            Part(("       R", "       █", "       █", "      ██")),  # tall mast
            Part(("       R", "      ██")),                        # stubby
        )),
        # Platform: shoulder ridge + docking-arm deck.
        Slot((
            Part(("    ▟███", "╾─▓████◊")),  # canonical: arms + facet
            Part(("    ▟███", "╾─▓█████")),  # plain deck
            Part(("  ▟█████", "▓██████")),   # wide, armless platform
        )),
        # Body: tapering chevron, repeated to lengthen the hull.
        Slot(
            (
                Part(("    ▜██≡", "     ▓██"), repeatable=True),  # canonical: faceted
                Part(("    ▜███", "     ▓██"), repeatable=True),  # plain
                Part(("    ▜██◊", "    ▓███"), repeatable=True),  # alt facet, fuller
            ),
            min_repeat=1,
            max_repeat=5,
        ),
        # Base: final taper to the engine glow.
        Slot((
            Part(("      ▜█", "       Y")),               # canonical
            Part(("     ▜██", "      ▓█", "       Y")),   # longer taper
            Part(("       Y",)),                           # bare glow
        )),
    ),
    # Compact trading module: dish/antenna, boxed core with side solar panels.
    "trading_port": (
        # Cap: antenna dish on a mast, down to the top box edge.
        Slot((
            Part(("     ▴", "     │", "   ┌──")),            # canonical
            Part(("     ▴", "   ┌──")),                       # short mast
            Part(("     ▴", "     │", "     │", "   ┌──")),  # tall mast
        )),
        # Core: solar-panel deck row + plain hull row, repeated to grow the box.
        Slot(
            (
                Part(("▤──┤██", "   │██"), repeatable=True),  # canonical
                Part(("   │██", "   │██"), repeatable=True),  # plain (no panels)
                Part(("▦──┤██", "   │██"), repeatable=True),  # alt-panel
            ),
            min_repeat=1,
            max_repeat=5,
        ),
        # Base: trailing panel deck, bottom box edge, mast, dish.
        Slot((
            Part(("▤──┤██", "   └──", "     │", "     ▾")),  # canonical
            Part(("   └──", "     │", "     ▾")),             # no trailing deck
            Part(("▤──┤██", "   └──", "     ▾")),             # short mast
        )),
    ),
    # Fortified octagonal bastion -- squat, armoured, distinct from the others.
    "starbase": (
        # Cap: top arc widening through the bevel to the full belt.
        Slot((
            Part(("   ▄▄▄", "  ▟███", " ▟████", "▟█████")),            # canonical
            Part(("   ▄▄▄", "  ▟███", "▟█████")),                       # squat
            Part(("    ▄▄", "   ▟██", "  ▟███", " ▟████", "▟█████")),  # tall
        )),
        # Belt: full-width armoured band, repeated to fatten the bastion.
        Slot(
            (
                Part(("██████",), repeatable=True),   # canonical
                Part(("▒█████",), repeatable=True),   # shadow streak
                Part(("██≡███",), repeatable=True),   # facet band
            ),
            min_repeat=1,
            max_repeat=8,
        ),
        # Base: bottom bevel narrowing through the arc.
        Slot((
            Part(("▜█████", " ▜████", "  ▜███", "   ▀▀▀")),            # canonical
            Part(("▜█████", "  ▜███", "   ▀▀▀")),                       # squat
            Part(("▜█████", " ▜████", "  ▜███", "   ▀▀", "    ▀")),    # tall
        )),
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

# Glyphs whose shape is asymmetric and must be swapped when a left-half row is
# mirrored to the right (quadrant blocks, heavy arm stubs, triangles, box edges).
# Listed once as left->right pairs; both directions are seeded into ``_MIRROR``.
_MIRROR_PAIRS = (
    ("▟", "▙"), ("▜", "▛"), ("╾", "╼"),
    ("◢", "◣"), ("◥", "◤"),
    ("┌", "┐"), ("└", "┘"), ("├", "┤"),
)
_MIRROR: dict[str, str] = {}
for _a, _b in _MIRROR_PAIRS:
    _MIRROR[_a] = _b
    _MIRROR[_b] = _a
del _a, _b

# Glyphs that read correctly straddling the mirror axis, so they are legal as a
# part's centre column. Everything self-symmetric: full/half/shade blocks, the
# vertical/horizontal rules, beacon/glow markers, and every facet feature (facets
# are not hull glyphs, so any glyph outside ``_HULL_CHARS`` is treated as one and
# is axis-safe). Asymmetric glyphs in ``_MIRROR`` are excluded.
_SELF_SYMMETRIC = (_HULL_CHARS - frozenset(_MIRROR)) | frozenset(" RY")


def _mirror_row(left: str) -> str:
    """Expand a left-half row (centre column included) to a full symmetric row:
    the centre glyph is emitted once and the body is reflected with each glyph
    swapped to its mirror (``_MIRROR``), self-mirroring glyphs left as-is."""
    if not left:
        return ""
    body, center = left[:-1], left[-1]
    right = "".join(_MIRROR.get(ch, ch) for ch in reversed(body))
    return body + center + right


def _mirror_part(part: "Part") -> tuple[str, ...]:
    """Mirror every left-half row of a part to full width."""
    return tuple(_mirror_row(row) for row in part.left)


def _compose(
    grammar: tuple[Slot, ...], rng: random.Random, target_h: int
) -> list[str]:
    """Compose a full-width sprite grid from a band grammar, seeded by ``rng``.

    One part is chosen per slot (in slot order -- a fixed number of draws,
    independent of ``target_h``, so the downstream window/beacon draw stream is
    stable across sizes). Repeatable parts are then stacked, by pure arithmetic,
    to fill ``target_h`` as closely as possible without overshooting: every
    repeatable starts at ``min_repeat`` and is grown round-robin one block at a
    time while the next block still fits and ``max_repeat`` is not exceeded."""
    chosen = [rng.choice(slot.parts) for slot in grammar]

    # Block heights and starting repeats for the repeatable slots.
    repeats = [slot.min_repeat for slot in grammar]
    total = sum(len(part.left) * r for part, r in zip(chosen, repeats))
    growable = [
        i for i, (slot, part) in enumerate(zip(grammar, chosen)) if part.repeatable
    ]
    # Round-robin fill: keep adding one block to whichever repeatable still fits.
    progressed = True
    while progressed and growable:
        progressed = False
        for i in growable:
            block = len(chosen[i].left)
            if repeats[i] < grammar[i].max_repeat and total + block <= target_h:
                repeats[i] += 1
                total += block
                progressed = True

    rows: list[str] = []
    for part, r in zip(chosen, repeats):
        mirrored = _mirror_part(part)
        for _ in range(r):
            rows.extend(mirrored)
    return rows


class PortGenerator:
    """Generates iconic, deterministic port/starbase sprites by composing
    mirror-symmetric band parts (see ``PORT_GRAMMAR`` / ``_compose``)."""

    def generate(
        self,
        rng: random.Random,
        subtype: str,
        width: int,
        height: int,
        archetype_id: str | None = None,
    ) -> Text:
        """Generate a procedural space port sprite, hued by owner ``archetype_id``."""
        grammar = PORT_GRAMMAR.get(subtype.lower(), PORT_GRAMMAR["trading_port"])
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

        rows = _compose(grammar, rng, height)
        nh = len(rows)
        nw = max((len(row) for row in rows), default=0)
        # Centre the composed art within the requested bounds. When the art is
        # taller than the box, crop symmetrically (``crop_top``) so the body is
        # sacrificed before the iconic cap and base, rather than beheading them.
        pad_top = max(0, (height - nh) // 2)
        crop_top = max(0, (nh - height) // 2)

        map_text = Text()
        for y in range(height):
            src = y - pad_top + crop_top
            if not (0 <= src < nh):
                # Blank padding above/below the art -- a full row of void.
                line = " " * width
            elif nw <= width:
                # Centre the art horizontally within the wider box.
                row = rows[src].center(nw)
                left = (width - nw) // 2
                line = (" " * left) + row + (" " * (width - nw - left))
            else:
                # Box narrower than the art: crop symmetrically.
                row = rows[src].center(nw)
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
