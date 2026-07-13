"""Shared machinery for compositional *hull* sprites -- ports and ships.

Both ports and ships are small, iconic ASCII sprites built by composing
hand-authored, recombinable PARTS into a glyph grid that is then recoloured by
the owner's *archetype* palette. This module factors out everything the two
generators share so each only has to own its grammar and its composition axis:

* ``Part`` / ``Slot`` -- the band-grammar dataclasses.
* ``GLYPH_FLIP`` -- the left<->right glyph-swap table. Ports use it to mirror a
  left-half band to full width; ships use it to flip a whole hull so it can face
  either way.
* Shading sets + ``HullStyle`` / ``ARCHETYPE_STYLES`` -- the closed hull glyph
  alphabet and the per-archetype colour palettes (keyed on ``archetype_id`` so a
  roster rename/reskin keeps the look).
* ``render_grid`` -- the painter: centre a finished glyph grid in the requested
  box and paint hull shading / beacon / glow / windows / facet features.
* ``select_grammar`` / ``compose_horizontal`` -- generic composition helpers.

Ports compose along the *height* axis with horizontal mirror symmetry (see
``edge/art/port.py``); ships compose along the *width* axis (front -> back) with
no symmetry, flipped for facing (see ``edge/art/ship.py``).

Glyph legend, by shading level:
  '█'            -> bright hull       (lit, sun-facing plating)
  half/box chars -> mid hull / struts (bevelled edges, arms, panels)
  '▒' '░'        -> dark hull         (shadowed recesses)
  'R'            -> red beacon  (rendered as an upper-half block, top light)
  'Y'            -> yellow glow (rendered as a lower-half block, engine light)
  ' '            -> empty space
  any other char -> a facet feature (see ``HULL_CHARS``): drawn in the archetype
                    facet colour over a bright-hull background, e.g. ☉ ° ◇ ◆ ◊ ⁐ ≡
"""

import random
from collections.abc import Callable
from dataclasses import dataclass
from rich.text import Text


@dataclass(frozen=True)
class Part:
    """A recombinable sprite fragment, authored as ``cells`` rows and composed to
    fit the requested bounds. For ports the rows are a *left half* (centre column
    included) mirrored to full width; for ships they are *full* rows (no symmetry).
    ``repeatable`` parts may be tiled multiple times by the composer to grow the
    sprite along its composition axis (height for ports, width for ships).

    The field is named ``left`` for backward compatibility with the port composer,
    which authors left-half bands; read it as "the authored rows" everywhere."""

    left: tuple[str, ...]
    repeatable: bool = False


@dataclass(frozen=True)
class Slot:
    """One position in a subtype's band stack. The composer picks a single part
    from ``parts`` (seeded), then -- if that part is repeatable -- tiles it between
    ``min_repeat`` and ``max_repeat`` times to fill the box."""

    parts: tuple[Part, ...]
    min_repeat: int = 1
    max_repeat: int = 1


# Glyphs whose shape is asymmetric and must be swapped when reflected left<->right
# (quadrant blocks, heavy arm stubs, triangles, box edges, muzzle arrows). Listed
# once as left->right pairs; both directions are seeded into ``GLYPH_FLIP``.
GLYPH_FLIP_PAIRS = (
    ("▟", "▙"), ("▜", "▛"), ("╾", "╼"),
    ("◢", "◣"), ("◥", "◤"),
    ("┌", "┐"), ("└", "┘"), ("├", "┤"),
    ("▶", "◀"), ("►", "◄"), ("╱", "╲"),
)
GLYPH_FLIP: dict[str, str] = {}
for _a, _b in GLYPH_FLIP_PAIRS:
    GLYPH_FLIP[_a] = _b
    GLYPH_FLIP[_b] = _a
del _a, _b

# Hull-glyph shading levels: bright (lit plating), dark (shadowed recesses), and
# -- by exclusion -- mid for every other structural glyph (bevels, struts, arms,
# panels, box edges).
BRIGHT_CHARS = frozenset("█")
DARK_CHARS = frozenset("▒░")
MID_CHARS = frozenset("▟▙▜▛▓▄▀╾╼─◢◣◥◤▴▾│┌┐└┘┤├▤▦═║╱╲")

# The complete, closed set of glyphs the sprites draw as *hull*. A hull cell is
# painted in its shading tone over the black void; ANY other non-space glyph is a
# *facet* -- a surface feature (e.g. ☉ ◘ ◙ ° ◇ ◆ ◊ ▬ ⁐ ≡) drawn in the archetype
# facet colour over a bright-hull background so its negative space blends into
# the surrounding plating. We enumerate the hull set rather than every possible
# facet because the hull alphabet is small and closed, so new feature glyphs just
# work when dropped into a template.
HULL_CHARS = BRIGHT_CHARS | DARK_CHARS | MID_CHARS

# Background of every hull cell: the black of space.
VOID_BG = "black"

# Chance a bright hull cell lights up as a window, for a touch of life.
WINDOW_PROB = 0.05


@dataclass(frozen=True)
class HullStyle:
    """Palette for a hull: three shading levels, the navigation-beacon hue pools
    (a steady hue is drawn per sprite), the lit-window hue pool, and the ``facet``
    colour -- the foreground hue for surface-feature glyphs, drawn over a
    bright-hull background so the feature reads as etched into the plating."""

    bright: str
    mid: str
    dark: str
    top: tuple[str, ...]
    bottom: tuple[str, ...]
    window: tuple[str, ...]
    facet: str


# Hull palettes keyed by ``archetype_id`` (see config/alien_roster_default.yaml). The
# Federation 'humanoid_diplomat' reads as the grey hull of the classic Stardock;
# every other archetype gets a distinct hull/beacon hue family. Unknown archetypes
# fall back to 'default'. Ports and ships share these palettes.
ARCHETYPE_STYLES: dict[str, HullStyle] = {
    # Terran/Centaurian Federation -- grey plating, red/yellow nav lights.
    "humanoid_diplomat": HullStyle(
        bright="grey85", mid="grey58", dark="grey35",
        top=("red", "bright_red"),
        bottom=("yellow", "bright_yellow"),
        window=("bright_cyan", "bright_yellow", "grey100"),
        facet="grey15",
    ),
    # Vesk -- warm fox-folk technologists: amber-khaki hull, cyan windows.
    "canid_technologist": HullStyle(
        bright="khaki1", mid="dark_khaki", dark="grey35",
        top=("orange1", "gold1"),
        bottom=("cyan", "bright_cyan"),
        window=("gold1", "bright_white"),
        facet="dark_orange3",
    ),
    # Selvani -- soft-bodied envoys: aqua/teal organic hull.
    "tentacled_envoy": HullStyle(
        bright="pale_turquoise1", mid="cyan", dark="grey30",
        top=("aquamarine1", "cyan"),
        bottom=("turquoise2", "cyan"),
        window=("pale_turquoise1", "bright_white"),
        facet="dark_cyan",
    ),
    # Helot -- cold brain-dome automata: chrome and electric blue.
    "brain_dome_automaton": HullStyle(
        bright="grey93", mid="grey62", dark="grey30",
        top=("bright_cyan", "cyan"),
        bottom=("dodger_blue1", "bright_cyan"),
        window=("bright_cyan", "grey100"),
        facet="deep_sky_blue4",
    ),
    # Quill -- predatory salvagers: rusted bronze hull, ember lights.
    "ribbon_salvager": HullStyle(
        bright="tan", mid="dark_orange3", dark="grey23",
        top=("orange_red1", "red"),
        bottom=("orange1", "dark_orange"),
        window=("orange1", "red"),
        facet="grey15",
    ),
    # Stryx -- time-dabbling brokers: violet, uncanny.
    "temporal_broker": HullStyle(
        bright="plum1", mid="medium_purple", dark="grey27",
        top=("magenta", "violet"),
        bottom=("blue_violet", "purple"),
        window=("plum1", "bright_white"),
        facet="purple4",
    ),
    # The Concordance -- bodiless arbiter: pale gold, luminous.
    "cosmic_arbiter": HullStyle(
        bright="khaki1", mid="gold3", dark="grey42",
        top=("gold1", "yellow"),
        bottom=("bright_white", "gold1"),
        window=("gold1", "bright_white"),
        facet="dark_goldenrod",
    ),
    # Dignar -- aristocratic mind-mages: royal orchid/purple.
    "telepath_aristocrat": HullStyle(
        bright="orchid", mid="purple", dark="grey27",
        top=("magenta", "bright_magenta"),
        bottom=("violet", "magenta"),
        window=("orchid", "bright_white"),
        facet="purple4",
    ),
    # Cibelline -- engineered aesthetes: rose and pink-gold finery.
    "engineered_aesthete": HullStyle(
        bright="pink1", mid="hot_pink3", dark="grey30",
        top=("gold1", "yellow"),
        bottom=("deep_pink2", "hot_pink"),
        window=("gold1", "pink1"),
        facet="medium_violet_red",
    ),
    # Selvi -- playful imps: bright pinks and magenta.
    "amorous_imp": HullStyle(
        bright="light_pink1", mid="hot_pink", dark="grey30",
        top=("hot_pink", "magenta"),
        bottom=("bright_magenta", "hot_pink"),
        window=("light_pink1", "bright_white"),
        facet="medium_violet_red",
    ),
    # Vennrith -- horned grudge-keepers: iron grey and blood red.
    "horned_grudgekeeper": HullStyle(
        bright="grey66", mid="red3", dark="dark_red",
        top=("red", "bright_red"),
        bottom=("orange3", "red"),
        window=("red", "orange1"),
        facet="grey15",
    ),
    # Thessarch -- psionic overlords: deep indigo authority.
    "psionic_overlord": HullStyle(
        bright="slate_blue1", mid="purple4", dark="grey23",
        top=("blue_violet", "purple"),
        bottom=("dodger_blue1", "blue"),
        window=("slate_blue1", "bright_cyan"),
        facet="grey15",
    ),
    # Thessbrood -- colonial broodmasters: sickly insectoid chartreuse.
    "colonial_broodmaster": HullStyle(
        bright="green_yellow", mid="chartreuse4", dark="grey23",
        top=("green_yellow", "chartreuse1"),
        bottom=("yellow3", "chartreuse3"),
        window=("green_yellow", "bright_yellow"),
        facet="green4",
    ),
    # Dacaran -- winged schemers: cold slate and dark teal.
    "winged_schemer": HullStyle(
        bright="grey62", mid="cadet_blue", dark="grey27",
        top=("dark_cyan", "cyan"),
        bottom=("steel_blue", "cyan"),
        window=("cyan", "grey100"),
        facet="grey15",
    ),
}
# Federation hull as the catch-all style for unknown/unset archetypes.
ARCHETYPE_STYLES["default"] = ARCHETYPE_STYLES["humanoid_diplomat"]


def style_for(archetype_id: str | None) -> HullStyle:
    """Resolve an ``archetype_id`` to its palette, falling back to Federation grey."""
    key = (archetype_id or "default").lower()
    return ARCHETYPE_STYLES.get(key, ARCHETYPE_STYLES["default"])


def flip_row(row: str) -> str:
    """Reflect a full row left<->right: reverse it and swap each asymmetric glyph
    to its mirror (``GLYPH_FLIP``); self-symmetric glyphs pass through. Used to
    point a ship the other way -- and applying it twice is the identity."""
    return "".join(GLYPH_FLIP.get(ch, ch) for ch in reversed(row))


def select_grammar(
    tiers: tuple[tuple[Slot, ...], ...],
    budget: int,
    floor: Callable[[tuple[Slot, ...]], int],
) -> tuple[Slot, ...]:
    """Pick the richest grammar tier (listed largest-floor first) whose minimum
    footprint -- measured by ``floor`` -- still fits ``budget``. Falls back to the
    smallest (compact) tier so a tiny box renders a legible silhouette rather than
    a cropped detailed one."""
    for grammar in tiers:
        if floor(grammar) <= budget:
            return grammar
    return tiers[-1]


def compose_horizontal(
    grammar: tuple[Slot, ...], rng: random.Random, target_w: int
) -> list[str]:
    """Compose a sprite grid by laying parts left-to-right to fill ``target_w``.

    One part is chosen per slot (a fixed number of draws, independent of
    ``target_w``, so the downstream window/beacon draw stream is stable across
    sizes). Repeatable parts are then tiled, by pure arithmetic, to fill the width
    as closely as possible without overshooting: each repeatable starts at
    ``min_repeat`` and is grown round-robin one block at a time while the next
    block still fits and ``max_repeat`` is not exceeded.

    Every part in a tier must have the same number of rows (the tier height) and
    every row of a part the same width, so the columns tile and join cleanly."""
    chosen = [rng.choice(slot.parts) for slot in grammar]
    widths = [len(part.left[0]) for part in chosen]
    repeats = [slot.min_repeat for slot in grammar]
    total = sum(w * r for w, r in zip(widths, repeats))
    growable = [
        i for i, (slot, part) in enumerate(zip(grammar, chosen)) if part.repeatable
    ]
    # Round-robin fill: keep adding one block to whichever repeatable still fits.
    progressed = True
    while progressed and growable:
        progressed = False
        for i in growable:
            if repeats[i] < grammar[i].max_repeat and total + widths[i] <= target_w:
                repeats[i] += 1
                total += widths[i]
                progressed = True

    height = len(chosen[0].left)
    rows: list[str] = []
    for r in range(height):
        line = "".join(
            part.left[r] * rep for part, rep in zip(chosen, repeats)
        )
        rows.append(line)
    return rows


def render_grid(
    rows: list[str],
    style: HullStyle,
    top_color: str,
    bottom_color: str,
    rng: random.Random,
    width: int,
    height: int,
) -> Text:
    """Paint a finished glyph grid into a ``width`` x ``height`` ``rich.Text``.

    The grid is centred within the box; when it is larger than the box it is
    cropped symmetrically so the iconic extremities survive before the middle.
    Hull glyphs paint in their shading tone over the void, ``R``/``Y`` markers
    paint as the upper/lower half-block beacon/glow in the chosen hues, a few
    bright cells light up as windows, and any other glyph is a facet feature
    drawn over a patch of bright hull."""
    bright = style.bright
    mid = style.mid
    dark = style.dark
    facet = style.facet
    windows = style.window

    nh = len(rows)
    nw = max((len(row) for row in rows), default=0)
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
            elif char in HULL_CHARS:
                # Hull plating: a shading tone over the black of space.
                if char in BRIGHT_CHARS and rng.random() < WINDOW_PROB:
                    color = rng.choice(windows)
                elif char in DARK_CHARS:
                    color = dark
                elif char in BRIGHT_CHARS:
                    color = bright
                else:
                    color = mid
                map_text.append(char, style=f"{color} on {VOID_BG}")
            else:
                # Facet feature: a detail glyph over a patch of bright hull,
                # so its surrounding negative space matches the plating.
                map_text.append(char, style=f"{facet} on {bright}")

        if y < height - 1:
            map_text.append("\n")

    return map_text
