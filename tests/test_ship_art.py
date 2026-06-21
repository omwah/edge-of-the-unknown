"""Tests for the horizontal, asymmetric ship-sprite composer
(``edge/art/ship.py``). Unlike ports, ships have no symmetry: parts are authored
as full rows and composed left-to-right (tail -> nose) to fill the requested
width, and a whole ship is flipped (``hull.flip_row``) to face the other way.
The guarantees worth pinning are: well-formed grammars (uniform part widths /
tier heights), seeded determinism stable across sizes, width fitting, exact box
filling, the facing-flip being a clean glyph-aware reflection, and that ships are
genuinely asymmetric (we did not accidentally inherit the port mirror)."""

from __future__ import annotations

import random

import pytest

from edge.art.hull import GLYPH_FLIP, compose_horizontal, flip_row
from edge.art.ship import (
    SHIP_GRAMMAR,
    SHIP_SUBTYPES,
    ShipGenerator,
    _select_grammar,
    _tier_height,
)

_GEN = ShipGenerator()
_SUBTYPES = tuple(SHIP_SUBTYPES)

# Asymmetric glyphs whose left<->right mirror is a *different* glyph: if a ship
# part uses one of these it must be in GLYPH_FLIP, or facing-left would corrupt it.
_ASYMMETRIC = frozenset("▟▙▜▛╾╼◢◣◥◤▶◀►◄╱╲┌┐└┘├┤▌▐▖▗▘▝")


def _all_glyphs() -> set[str]:
    return {
        ch
        for tiers in SHIP_GRAMMAR.values()
        for grammar in tiers
        for slot in grammar
        for part in slot.parts
        for row in part.left
        for ch in row
    }


# --- grammar well-formedness -----------------------------------------------


def test_grammar_covers_the_public_subtypes() -> None:
    for subtype in SHIP_SUBTYPES:
        assert subtype in SHIP_GRAMMAR


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_parts_have_uniform_widths_and_tier_heights(subtype: str) -> None:
    """Horizontal tiling/abutment only works if every row of a part is the same
    width and every part in a tier is the same height (the tier height)."""
    for grammar in SHIP_GRAMMAR[subtype]:
        height = _tier_height(grammar)
        for slot in grammar:
            for part in slot.parts:
                assert len(part.left) == height, (subtype, part.left)
                widths = {len(row) for row in part.left}
                assert len(widths) == 1, (subtype, part.left)


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_tiers_are_ordered_tallest_first_and_reach_three_rows(subtype: str) -> None:
    tiers = SHIP_GRAMMAR[subtype]
    heights = [_tier_height(g) for g in tiers]
    assert heights == sorted(heights, reverse=True), (subtype, heights)
    assert heights[-1] <= 3, "the compact tier must fit a 3-row box"


# --- facing flip & glyph table ---------------------------------------------


def test_glyph_flip_is_an_involution() -> None:
    for glyph, image in GLYPH_FLIP.items():
        assert GLYPH_FLIP[image] == glyph  # swapping twice is identity
        assert image in GLYPH_FLIP


def test_flip_row_is_an_involution() -> None:
    for row in ("██▶", " ▟█", "Y███▙", "◇██≡", "    "):
        assert flip_row(flip_row(row)) == row


def test_every_asymmetric_glyph_used_is_flippable() -> None:
    """Any asymmetric glyph a ship draws must have a mirror twin in GLYPH_FLIP,
    or pointing the ship left would leave a glyph facing the wrong way."""
    used_asymmetric = _all_glyphs() & _ASYMMETRIC
    assert used_asymmetric <= set(GLYPH_FLIP), used_asymmetric - set(GLYPH_FLIP)


# --- determinism & composition ---------------------------------------------


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_generation_is_deterministic(subtype: str) -> None:
    a = _GEN.generate(random.Random(3), subtype, 30, 7, "ribbon_salvager")
    b = _GEN.generate(random.Random(3), subtype, 30, 7, "ribbon_salvager")
    assert a.plain == b.plain
    assert a.spans == b.spans


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_compose_consumes_fixed_draws_regardless_of_width(subtype: str) -> None:
    """One draw per slot, independent of target width, so the downstream
    light/window draw stream is identical across sizes."""
    grammar = SHIP_GRAMMAR[subtype][0]  # the full-detail tier
    narrow = random.Random(11)
    compose_horizontal(grammar, narrow, 12)
    wide = random.Random(11)
    compose_horizontal(grammar, wide, 80)
    assert narrow.random() == wide.random()


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_width_grows_monotonically_and_respects_bounds(subtype: str) -> None:
    grammar = SHIP_GRAMMAR[subtype][0]
    prev = 0
    for width in range(8, 80):
        rows = compose_horizontal(grammar, random.Random(0), width)
        nw = max(len(r) for r in rows)
        min_w = max(len(r) for r in compose_horizontal(grammar, random.Random(0), 0))
        assert nw <= width or nw == min_w  # never overshoot unless minimum is wider
        assert nw >= prev  # wider boxes never yield a shorter ship
        prev = nw


# --- rendering --------------------------------------------------------------


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_generate_fills_exact_box(subtype: str) -> None:
    for height in (3, 6, 12):
        for width in (12, 24, 48):
            text = _GEN.generate(random.Random(2), subtype, width, height)
            lines = text.plain.split("\n")
            assert len(lines) == height
            assert all(len(line) == width for line in lines)


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_facing_left_is_the_glyph_flip_of_facing_right(subtype: str) -> None:
    """Same seed, opposite facing: each line's silhouette (stripped of the
    centring padding) must be the glyph-aware reflection of the other."""
    right = _GEN.generate(random.Random(7), subtype, 40, 7, "humanoid_diplomat")
    left = _GEN.generate(random.Random(7), subtype, 40, 7, "humanoid_diplomat", "left")
    for r_line, l_line in zip(right.plain.split("\n"), left.plain.split("\n")):
        assert l_line.strip(" ") == flip_row(r_line.strip(" ")), (subtype, r_line)


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_ships_are_not_left_right_symmetric(subtype: str) -> None:
    """A ship is asymmetric (tail != nose), so its silhouette must differ from its
    own mirror -- guards against accidentally inheriting the port mirror trick."""
    text = _GEN.generate(random.Random(1), subtype, 40, 7)
    silhouette = [ln.strip(" ") for ln in text.plain.split("\n") if ln.strip()]
    mirrored = [flip_row(ln) for ln in silhouette]
    assert silhouette != mirrored, subtype


# --- compact tier (tiny boxes) ---------------------------------------------


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_compact_tier_renders_legibly_in_a_three_row_box(subtype: str) -> None:
    tiers = SHIP_GRAMMAR[subtype]
    assert _select_grammar(tiers, 3) is tiers[-1]
    for seed in range(15):
        text = _GEN.generate(random.Random(seed), subtype, 18, 3)
        lines = text.plain.split("\n")
        assert len(lines) == 3
        assert all(len(line) == 18 for line in lines)
        assert any(line.strip() for line in lines)  # not a blank box
