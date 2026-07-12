"""Procedural Port and Starbase art.

Ports are small, iconic sprites (as little as 3 cells tall), so this module
uses a *compositional / template* approach rather than SDF rasterization: each
port subtype is a set of hand-authored ASCII silhouettes at a few size tiers.
At those resolutions an implicit-surface (SDF) trace has too few samples to read
as anything recognizable, while a hand-drawn silhouette stays crisp and keeps
the BBS/ANSI heritage the project is going for.

Ports are LEFT/RIGHT symmetric and stack as vertical *bands*, so rather than
storing whole fixed-size silhouettes we store recombinable PARTS and compose
them. Each part is authored as its LEFT HALF, *including the centre column*, and
mirrored to full width at render time (see ``_mirror_row`` / ``_MIRROR``); this
guarantees symmetry and halves authoring. A subtype's grammar is an ordered
stack of slots (cap -> repeatable body -> base); the composer picks one part per
slot and repeats the body to fill the requested height.

The shared hull machinery -- the part/slot grammar types, the glyph-flip table,
the shading alphabet, the archetype palettes, and the painter -- lives in
``edge/art/hull.py`` and is reused by the (horizontal, asymmetric) ship generator.
This module owns only what is port-specific: the per-subtype grammars and the
mirror-symmetry that ships do not have.

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

Glyph legend, by shading level (see ``edge/art/hull.py``):
  '█'            -> bright hull       (lit, sun-facing plating)
  half/box chars -> mid hull / struts (bevelled edges, arms, panels)
  '▒' '░'        -> dark hull         (shadowed recesses)
  'R'            -> red beacon  (rendered as an upper-half block, top light)
  'Y'            -> yellow glow (rendered as a lower-half block, engine light)
  ' '            -> empty space
  any other char -> a facet feature: drawn in the archetype facet colour over a
                    bright-hull background, e.g. ☉ ° ◇ ◆ ◊ ⁐ ≡
A part's centre-column glyph (the last char of each left-half row) must be
self-symmetric (in ``_SELF_SYMMETRIC``) so it reads correctly straddling the
mirror axis; corner/quadrant/triangle glyphs would seam.
"""

import random
from rich.text import Text

from edge.art.hull import (
    GLYPH_FLIP,
    HULL_CHARS,
    HullStyle,
    Part,
    Slot,
    render_grid,
    select_grammar,
    style_for,
)

# Public alias: the old name for the hull palette type, kept for callers/tests.
PortStyle = HullStyle

# The mirror map and the closed hull alphabet come from the shared module; ports
# expose ``_MIRROR`` / ``_SELF_SYMMETRIC`` under their historic names.
_MIRROR = GLYPH_FLIP

PORT_SUBTYPES = ["trading_port", "starbase", "stardock"]

# Glyphs that read correctly straddling the mirror axis, so they are legal as a
# part's centre column. Everything self-symmetric: full/half/shade blocks, the
# vertical/horizontal rules, beacon/glow markers, and every facet feature (facets
# are not hull glyphs, so any glyph outside ``HULL_CHARS`` is treated as one and
# is axis-safe). Asymmetric glyphs in ``_MIRROR`` are excluded.
_SELF_SYMMETRIC = (HULL_CHARS - frozenset(_MIRROR)) | frozenset(" RY")


# Per-subtype band grammars. Each subtype maps to an ordered tuple of grammar
# *tiers*, largest-floor first; ``_select_grammar`` picks the richest tier whose
# minimum stack fits the requested height (so big boxes get the detailed art and
# tiny boxes get a legible compact silhouette -- the platform/octagon don't shrink
# to a few rows gracefully, so the small regime needs its own parts).
#
# Within a tier the slots run top (cap) -> bottom (base). The FIRST part of each
# slot is the *canonical* one: choosing all canonical parts at the repeat that
# matches the historic height reproduces the original largest silhouette exactly
# (this is "decompose what we had", not "redraw"). The remaining parts are
# interchangeable variants that give repeat ports visible variety.
PORT_GRAMMAR: dict[str | tuple[str, str], tuple[tuple[Slot, ...], ...]] = {
    # The hero. Beacon + shoulders, docking-arm platform, tapering chevron body,
    # engine glow -- the TW2002 StarDock shape.
    "stardock": (
        # --- full detail (floor 7) ---
        (
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
        # --- compact (floor 3, fills 3-6): beacon / hull band(s) / glow ---
        (
            Slot((Part(("    R",)),)),  # beacon
            Slot(
                (
                    Part(("╾▟███",), repeatable=True),  # canonical: arm band
                    Part(("╾████",), repeatable=True),  # plain arm band
                    Part(("  ███",), repeatable=True),  # bare hull band
                ),
                min_repeat=1,
                max_repeat=4,
            ),
            Slot((Part(("    Y",)),)),  # engine glow
        ),
    ),
    # Compact trading module: dish/antenna, boxed core with side solar panels.
    "trading_port": (
        # --- full detail (floor 7) ---
        (
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
        # --- compact (floor 3, fills 3-6): top edge / core band(s) / bottom edge ---
        (
            Slot((Part(("  ┌─",)),)),  # top box edge
            Slot(
                (
                    Part(("▦│█",), repeatable=True),  # canonical: panelled core
                    Part(("  │█",), repeatable=True),  # plain core
                    Part(("▤─█",), repeatable=True),  # deck-panel core
                ),
                min_repeat=1,
                max_repeat=4,
            ),
            Slot((Part(("  └─",)),)),  # bottom box edge
        ),
    ),
    # Fortified octagonal bastion -- squat, armoured, distinct from the others.
    "starbase": (
        # --- full detail (floor 7) ---
        (
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
        # --- compact (floor 3, fills 3-6): point cap / belt(s) / point base ---
        (
            Slot((Part((" ◢█",)),)),  # pointed cap
            Slot(
                (
                    Part(("███",), repeatable=True),  # canonical: full belt
                    Part(("▒██",), repeatable=True),  # shadow streak
                    Part(("█≡█",), repeatable=True),  # facet belt
                ),
                min_repeat=1,
                max_repeat=4,
            ),
            Slot((Part((" ◥█",)),)),  # pointed base
        ),
    ),
}

# Archetype-specific procedural silhouettes derived from the generated exterior
# reference sheets in images/ui/{ports,starbases}/source. They intentionally keep
# the existing mirrored band-composer: raster art guides the shape language, while
# the runtime icon remains crisp deterministic BBS cell art.
PORT_GRAMMAR.update({
    ("trading_port", "humanoid_diplomat"): ((
        Slot((Part(("     R", "    ▟█")),)),
        Slot((Part(("╾─▟███", "  ▟███"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("  ▜███", "     Y")),)),
    ),),
    ("starbase", "humanoid_diplomat"): ((
        Slot((Part(("     R", "    ▟█", "  ▟███")),)),
        Slot((Part(("╾─████", " ▟█◇██"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part((" ▜████", "   ▜██", "     Y")),)),
    ),),
    ("trading_port", "tentacled_envoy"): ((
        Slot((Part(("     ◆", "   ▟██")),)),
        Slot((Part(("╾▟█◇██", " ▟████"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("  ▜███", "    ◇")),)),
    ),),
    ("starbase", "tentacled_envoy"): ((
        Slot((Part(("     ◆", "   ▟██", " ▟█◇██")),)),
        Slot((Part(("▟█████", "██◇███"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("▜█████", "  ▜███", "    ◇")),)),
    ),),
    ("trading_port", "brain_dome_automaton"): ((
        Slot((Part(("     R", "   ▟██")),)),
        Slot((Part(("╾█████", "▒█≡███"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part((" ▜████", "     Y")),)),
    ),),
    ("starbase", "brain_dome_automaton"): ((
        Slot((Part(("    ▄▄", "  ▟███", "▟█████")),)),
        Slot((Part(("██████", "▒█≡███"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part(("▜█████", "  ▜███", "    ▀▀")),)),
    ),),
    ("trading_port", "engineered_aesthete"): ((
        Slot((Part(("    ▴", "   ▟██")),)),
        Slot((Part(("▦─┤███", "▒█◊███"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("╾─▜███", "    ▾")),)),
    ),),
    ("starbase", "engineered_aesthete"): ((
        Slot((Part(("    ▴", "  ▟███", "╾█████")),)),
        Slot((Part(("▒█◊███", "██≡███"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part(("╾▜████", "  ▜███", "    ▾")),)),
    ),),
    ("trading_port", "telepath_aristocrat"): ((
        Slot((Part(("     ◇", "    ◢█")),)),
        Slot((Part(("  ◢█◆█", "╾─████"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("  ◥█◇█", "     ◇")),)),
    ),),
    ("starbase", "telepath_aristocrat"): ((
        Slot((Part(("     ◆", "    ◢█", "  ◢█◇█")),)),
        Slot((Part(("◢██◆██", "██████"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("◥██◇██", "   ◥██", "     ◇")),)),
    ),),
    ("trading_port", "temporal_broker"): ((
        Slot((Part(("     ◊", "    ▟█")),)),
        Slot((Part(("  ▟█◊█", "╾─▒███"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("   ▜██", "     Y")),)),
    ),),
    ("starbase", "temporal_broker"): ((
        Slot((Part(("     ◊", "    ▟█", "   ▟██")),)),
        Slot((Part((" ▟█◊██", "╾─████"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part(("  ▜███", "    ▜█", "     Y")),)),
    ),),
    ("trading_port", "amorous_imp"): ((
        Slot((Part(("    ♥", "  ◢██")),)),
        Slot((Part(("╾◢█♥██", " ▜████"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("  ◥███", "    ♦")),)),
    ),),
    ("starbase", "amorous_imp"): ((
        Slot((Part(("    ♥", "  ◢██", "◢██♥██")),)),
        Slot((Part(("██████", "▒█♥███"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part(("◥█████", "  ◥███", "    ♦")),)),
    ),),
    ("trading_port", "canid_technologist"): ((
        Slot((Part(("   ▴ ▴", "   ▟██")),)),
        Slot((Part(("╾─┤███", "  █◇██"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("  ▜███", "    ▾")),)),
    ),),
    ("starbase", "canid_technologist"): ((
        Slot((Part(("   ▴ ▴", "  ▟███", "╾█████")),)),
        Slot((Part(("██◇███", "██████"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part(("╾▜████", "  ▜███", "    ▾")),)),
    ),),
    ("trading_port", "colonial_broodmaster"): ((
        Slot((Part(("   ◢◆█", " ◢████")),)),
        Slot((Part(("◢█◆███", "██◇███"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("◥█████", "   ◥◆█")),)),
    ),),
    ("starbase", "colonial_broodmaster"): ((
        Slot((Part(("   ◢◆█", " ◢████", "◢██◇██")),)),
        Slot((Part(("█◆██◆█", "██████"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part(("◥█████", " ◥████", "   ◥◆█")),)),
    ),),
    ("trading_port", "cosmic_arbiter"): ((
        Slot((Part(("   ╭─╮", "   │◆│")),)),
        Slot((Part(("╾─┤◇██", "  │███"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("   │◆│", "   ╰─╯")),)),
    ),),
    ("starbase", "cosmic_arbiter"): ((
        Slot((Part(("   ╭─╮", "  ╭┤◆│", "╾─┤◇██")),)),
        Slot((Part(("  │███", "╾─┤◆██"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part(("╾─┤◇██", "  ╰┤◆│", "   ╰─╯")),)),
    ),),
    ("trading_port", "horned_grudgekeeper"): ((
        Slot((Part(("◢    ◣", " ◢███")),)),
        Slot((Part(("╾█████", "▒█≡███"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part((" ◥████", "◥    ◤")),)),
    ),),
    ("starbase", "horned_grudgekeeper"): ((
        Slot((Part(("◢    ◣", " ◢███", "◢█████")),)),
        Slot((Part(("█≡████", "██████"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part(("◥█████", " ◥████", "◥    ◤")),)),
    ),),
    ("trading_port", "psionic_overlord"): ((
        Slot((Part(("  ╭──╮", "    ◆")),)),
        Slot((Part(("  ▟█◇█", "╾─████"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part(("   ▜██", "  ╰──╯")),)),
    ),),
    ("starbase", "psionic_overlord"): ((
        Slot((Part(("  ╭──╮", "    ◆", "  ▟█◇█")),)),
        Slot((Part(("╾─████", " ▟█◆██"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part(("  ▜███", "    ◇", "  ╰──╯")),)),
    ),),
    ("trading_port", "ribbon_salvager"): ((
        Slot((Part(("╭─╮  ▴", " ╰─▟█")),)),
        Slot((Part(("╾─▒███", " ╭┤███"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part((" ╰─▜██", "╰─╯  ▾")),)),
    ),),
    ("starbase", "ribbon_salvager"): ((
        Slot((Part(("╭─╮  ▴", " ╰─▟█", "╾─████")),)),
        Slot((Part(("╭┤▒███", "╰─████"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part(("╾─▜███", " ╭─▜█", "╰─╯  ▾")),)),
    ),),
    ("trading_port", "winged_schemer"): ((
        Slot((Part(("   ▴██", " ◢████")),)),
        Slot((Part(("╾◢█◊██", "╾─████"), repeatable=True),), min_repeat=1, max_repeat=4),
        Slot((Part((" ◥████", "   ▾██")),)),
    ),),
    ("starbase", "winged_schemer"): ((
        Slot((Part(("   ▴██", " ◢████", "╾◢█◊██")),)),
        Slot((Part(("╾─████", "██◇███"), repeatable=True),), min_repeat=1, max_repeat=5),
        Slot((Part(("╾◥████", " ◥████", "   ▾██")),)),
    ),),
})


def _mirror_row(left: str) -> str:
    """Expand a left-half row (centre column included) to a full symmetric row:
    the centre glyph is emitted once and the body is reflected with each glyph
    swapped to its mirror (``_MIRROR``), self-mirroring glyphs left as-is."""
    if not left:
        return ""
    body, center = left[:-1], left[-1]
    right = "".join(_MIRROR.get(ch, ch) for ch in reversed(body))
    return body + center + right


def _mirror_part(part: Part) -> tuple[str, ...]:
    """Mirror every left-half row of a part to full width."""
    return tuple(_mirror_row(row) for row in part.left)


def _grammar_floor(grammar: tuple[Slot, ...]) -> int:
    """The shortest height this grammar can compose: the smallest part in each
    slot at its minimum repeat. A grammar can never produce fewer rows than this."""
    return sum(
        min(len(part.left) for part in slot.parts) * slot.min_repeat
        for slot in grammar
    )


def _select_grammar(
    tiers: tuple[tuple[Slot, ...], ...], height: int
) -> tuple[Slot, ...]:
    """Pick the richest grammar tier (listed largest-floor first) whose minimum
    stack still fits ``height``; falls back to the compact tier for tiny boxes."""
    return select_grammar(tiers, height, _grammar_floor)


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
        subtype = subtype.lower()
        tiers = PORT_GRAMMAR.get(
            (subtype, archetype_id or ""),
            PORT_GRAMMAR.get(subtype, PORT_GRAMMAR["trading_port"]),
        )
        grammar = _select_grammar(tiers, height)
        style = style_for(archetype_id)

        # Pick this station's beacon hues once, so the lights are steady.
        top_color = rng.choice(style.top)
        bottom_color = rng.choice(style.bottom)

        rows = _compose(grammar, rng, height)
        return render_grid(rows, style, top_color, bottom_color, rng, width, height)
