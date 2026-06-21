"""Procedural Ship art.

Ships reuse the compositional band-grammar machinery of ports (see
``edge/art/hull.py``) but along the *other* axis. Where a port is a left/right
symmetric *vertical* stack of bands, a ship is a *horizontal* sequence of
sections -- thrusters at the tail, then spindrive, a repeatable hull backbone,
screens, and the main gun at the nose -- read front-to-back. Ships have **no
symmetry** (neither vertical nor horizontal), so parts are authored as *full*
rows rather than mirrored half-rows, and verticality (a dorsal bridge rising
above the hull line, an offset nacelle) is drawn straight into the row grid.

The five section slots deliberately mirror the four player-tweakable engine-room
subsystems (plus the hull/cargo backbone) so a glance at a ship reads as its
loadout:

  THRUSTERS  -> exhaust plume / engine block at the tail   (Y glow marker)
  SPINDRIVE  -> warp block just ahead of the thrusters
  HULL       -> repeatable cargo/structure backbone (grows the ship's length)
  SCREENS    -> deflector facets near the bow
  MAIN_GUN   -> spinal barrel tapering to a muzzle at the nose

Grammars are authored facing **nose-right** (canonical). Requesting
``facing="left"`` flips the finished grid with ``hull.flip_row`` -- a glyph-aware
reflection that swaps asymmetric glyphs (``▟▙``, ``▶◀``, ``╾╼``, ...) -- so the
same ship can point either way without re-authoring. The flip is a deterministic
post-transform that consumes no rng, so the two facings are the identical ship.

A role maps to an ordered tuple of grammar *tiers*, tallest first; the composer
picks the tallest tier whose authored height fits the box, so big boxes get the
detailed silhouette and tiny (3-row) boxes get a dedicated compact one. The
length grows by tiling the repeatable HULL slot to fill the requested width.
"""

import random
from rich.text import Text

from edge.art.hull import (
    Part,
    Slot,
    compose_horizontal,
    flip_row,
    render_grid,
    select_grammar,
    style_for,
)

SHIP_SUBTYPES = ["transport", "fighter", "warship", "capital_warship"]


# Per-role horizontal band grammars, authored facing nose-RIGHT. Each role maps
# to grammar *tiers* ordered tallest-first; ``_select_grammar`` picks the tallest
# tier whose row-height fits the box (so a 3-row box gets the compact tier). Within
# a tier every part has the same number of rows (the tier height) and every row of
# a part the same width, so the sections tile and abut cleanly. The FIRST part of
# each slot is the canonical one; the rest add seeded variety (dorsal towers,
# nacelles, facet panels). Slots run tail (left) -> nose (right).
SHIP_GRAMMAR: dict[str, tuple[tuple[Slot, ...], ...]] = {
    # Sleek courier/scout: short, light, a single thin backbone.
    "fighter": (
        # --- full detail (height 4) ---
        (
            # Thrusters: twin exhaust glow.
            Slot((
                Part(("  ", "Y▙", "Y▛", "  ")),
                Part(("  ", "Y▓", "Y▓", "  ")),
            )),
            # Spindrive: compact warp wedge with a dorsal fin.
            Slot((
                Part((" ▴", "▓█", "▓█", "  ")),
                Part(("  ", "▓█", "▓█", "  ")),
            )),
            # Hull: thin fuselage, repeated to stretch the fighter.
            Slot(
                (
                    Part(("   ", "▟▓█", "▜▓█", "   "), repeatable=True),  # canonical
                    Part((" ▴ ", "─▓█", "─▓█", "   "), repeatable=True),  # dorsal fin
                    Part(("   ", "─▓█", "─▓█", " ▾ "), repeatable=True),  # ventral fin
                ),
                min_repeat=1,
                max_repeat=6,
            ),
            # Screens: cockpit canopy with a nav light + deflector facet.
            Slot((
                Part((" R", "◇▓", "██", "  ")),
                Part(("  ", "◇▓", "██", "  ")),
            )),
            # Main gun: short spinal barrel to a muzzle at the nose.
            Slot((
                Part(("   ", "─▓▶", "─▓╼", "   ")),
                Part(("   ", "▟▓▶", "▜██", "   ")),
            )),
        ),
        # --- compact (height 3): glow / hull band(s) / muzzle ---
        (
            Slot((Part(("  ", "Y█", "  ")),)),
            Slot(
                (
                    Part(("  ", "██", "  "), repeatable=True),
                    Part((" ▴", "██", "  "), repeatable=True),
                ),
                min_repeat=1,
                max_repeat=8,
            ),
            Slot((Part(("  ", "█▶", "  ")),)),
        ),
    ),
    # Boxy freighter: a fat container backbone between drive and a token gun.
    "transport": (
        # --- full detail (height 5) ---
        (
            # Thrusters: broad engine block + glow.
            Slot((
                Part(("   ", " ▟▓", "Y█▓", " ▜▓", "   ")),
                Part(("   ", "Y▟▓", "Y█▓", "Y▜▓", "   ")),
            )),
            # Spindrive: warp block with a dorsal heat-fin facet.
            Slot((
                Part((" ≡ ", "▓██", "▓█▓", "▓██", "   ")),
                Part(("   ", "▓██", "▓█▓", "▓██", "   ")),
            )),
            # Hull: container bays, repeated to lengthen the freighter.
            Slot(
                (
                    Part(("    ", "┌──┐", "│▦▦│", "└──┘", "    "), repeatable=True),
                    Part((" ▄▄ ", "┌──┐", "│▤▤│", "└──┘", "    "), repeatable=True),
                    Part(("    ", "┌──┐", "│≡≡│", "└──┘", " ▀▀ "), repeatable=True),
                ),
                min_repeat=1,
                max_repeat=8,
            ),
            # Screens: a slim deflector + bridge nav light.
            Slot((
                Part((" R", "◇▓", "██", "◇▓", "  ")),
                Part(("  ", "◇▓", "██", "◇▓", "  ")),
            )),
            # Main gun: a stubby nose turret.
            Slot((
                Part(("   ", "▓█▙", "▓█▶", "▓█▛", "   ")),
                Part(("   ", "▓██", "▓█▶", "▓██", "   ")),
            )),
        ),
        # --- compact (height 3): glow / container band(s) / nose ---
        (
            Slot((Part(("  ", "Y█", "  ")),)),
            Slot(
                (
                    Part(("   ", "▟█▙", "   "), repeatable=True),
                    Part(("   ", "███", "   "), repeatable=True),
                ),
                min_repeat=1,
                max_repeat=10,
            ),
            Slot((Part(("  ", "█▶", "  ")),)),
        ),
    ),
    # Lean warship: a prominent spinal gun and a faceted deflector prow.
    "warship": (
        # --- full detail (height 5) ---
        (
            # Thrusters: raked engine block with glow.
            Slot((
                Part(("   ", "▟▓▓", "Y██", "▜▓▓", "   ")),
                Part(("   ", " ▟▓", "Y██", " ▜▓", "   ")),
            )),
            # Spindrive: warp core with a dorsal facet.
            Slot((
                Part((" ≡ ", "▓█▓", "███", "▓█▓", "   ")),
                Part(("   ", "▓█▓", "███", "▓█▓", "   ")),
            )),
            # Hull: armoured backbone; dorsal bridge / ventral pod variants.
            Slot(
                (
                    Part(("    ", "◢██◣", "█▒▒█", "◥██◤", "    "), repeatable=True),
                    Part((" ▟▙ ", "◢██◣", "█▒▒█", "◥██◤", "    "), repeatable=True),
                    Part(("    ", "◢██◣", "█◇◇█", "◥██◤", " ▜▛ "), repeatable=True),
                ),
                min_repeat=1,
                max_repeat=8,
            ),
            # Screens: layered deflector facets + nav light.
            Slot((
                Part((" R ", "◇▓▓", "◇██", "◇▓▓", "   ")),
                Part(("   ", "◇▓▓", "███", "◇▓▓", "   ")),
            )),
            # Main gun: long spinal barrel tapering to a nose muzzle.
            Slot((
                Part(("    ", "─▓▙ ", "─▓█▶", "─▓▛ ", "    ")),
                Part(("    ", "─██▙", "─██▶", "─██▛", "    ")),
            )),
        ),
        # --- compact (height 3): glow / hull band(s) / spinal muzzle ---
        (
            Slot((Part(("  ", "Y█", "  ")),)),
            Slot(
                (
                    Part(("  ", "██", "  "), repeatable=True),
                    Part((" ▴", "██", "  "), repeatable=True),
                ),
                min_repeat=1,
                max_repeat=10,
            ),
            Slot((Part(("   ", "██▶", "   ")),)),
        ),
    ),
    # Capital warship: tall, blocky, a towering superstructure and heavy prow.
    "capital_warship": (
        # --- full detail (height 7) ---
        (
            # Thrusters: bank of engines with glow.
            Slot((
                Part(("    ", " ▟▓▓", "Y█▓▓", "Y██▓", "Y█▓▓", " ▜▓▓", "    ")),
                Part(("    ", "Y▟▓▓", "Y█▓▓", "Y██▓", "Y█▓▓", "Y▜▓▓", "    ")),
            )),
            # Spindrive: heavy warp block with dorsal heat-sink facet.
            Slot((
                Part((" ≡≡ ", "▓██▓", "████", "█▒▒█", "████", "▓██▓", "    ")),
                Part(("    ", "▓██▓", "████", "█▒▒█", "████", "▓██▓", "    ")),
            )),
            # Hull: superstructure backbone -- dorsal towers & ventral hangars.
            Slot(
                (
                    Part((" ▟▓▙ ", "┌───┐", "│▒░▒│", "│▒░▒│", "└───┘", "▓███▓", "     "),
                         repeatable=True),  # canonical: dorsal tower
                    Part(("  R  ", "┌───┐", "│▒░▒│", "│▒░▒│", "└───┘", "▓███▓", "     "),
                         repeatable=True),  # sensor mast w/ nav light
                    Part(("     ", "┌───┐", "│▒◊▒│", "│▒░▒│", "└───┘", "▓███▓", " ▜▓▛ "),
                         repeatable=True),  # ventral hangar
                ),
                min_repeat=1,
                max_repeat=7,
            ),
            # Screens: stacked deflector facets across the prow.
            Slot((
                Part((" R ", "◇▓▓", "◇██", "███", "◇██", "◇▓▓", "   ")),
                Part(("   ", "◇▓▓", "███", "███", "███", "◇▓▓", "   ")),
            )),
            # Main gun: massive spinal lance to a nose muzzle.
            Slot((
                Part(("      ", "─██─▙ ", "─█▓─█▙", "─██─▓▶", "─█▓─█▛", "─██─▛ ", "      ")),
                Part(("      ", "─██─█▙", "─██─▓▓", "─██─▓▶", "─██─▓▓", "─██─█▛", "      ")),
            )),
        ),
        # --- compact (height 3): glow / hull band(s) / heavy muzzle ---
        (
            Slot((Part((" █", "Y█", " █")),)),
            Slot(
                (
                    Part(("██", "██", "██"), repeatable=True),
                    Part(("▀█", "██", "▄█"), repeatable=True),
                ),
                min_repeat=1,
                max_repeat=12,
            ),
            Slot((Part(("   ", "██▶", "   ")),)),
        ),
    ),
}


def _tier_height(grammar: tuple[Slot, ...]) -> int:
    """The authored row-height of a ship grammar tier (all parts share it)."""
    return max(len(part.left) for slot in grammar for part in slot.parts)


def _select_grammar(
    tiers: tuple[tuple[Slot, ...], ...], height: int
) -> tuple[Slot, ...]:
    """Pick the tallest tier whose authored height fits ``height``; falls back to
    the compact tier so a tiny box still renders a legible ship."""
    return select_grammar(tiers, height, _tier_height)


class ShipGenerator:
    """Generates iconic, deterministic ship sprites by composing asymmetric
    horizontal sections (see ``SHIP_GRAMMAR`` / ``compose_horizontal``), optionally
    flipped to face either way."""

    def generate(
        self,
        rng: random.Random,
        subtype: str,
        width: int,
        height: int,
        archetype_id: str | None = None,
        facing: str = "right",
    ) -> Text:
        """Generate a procedural ship sprite, hued by owner ``archetype_id`` and
        pointed ``facing`` 'right' (canonical) or 'left'."""
        tiers = SHIP_GRAMMAR.get(subtype.lower(), SHIP_GRAMMAR["fighter"])
        grammar = _select_grammar(tiers, height)
        style = style_for(archetype_id)

        # Pick this ship's running-light / engine-glow hues once, so they're steady.
        top_color = rng.choice(style.top)
        bottom_color = rng.choice(style.bottom)

        rows = compose_horizontal(grammar, rng, width)
        if facing.lower() == "left":
            rows = [flip_row(row) for row in rows]

        return render_grid(rows, style, top_color, bottom_color, rng, width, height)
