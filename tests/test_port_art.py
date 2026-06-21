"""Tests for the recombinable, mirror-symmetric port-sprite composer
(``edge/art/port.py``). The art is built from left-half band parts mirrored to
full width and stacked to fill the requested height, so the guarantees worth
pinning are: symmetry, the mirror map's correctness, centre-column legality,
seeded determinism (stable across sizes), height fitting, and that the canonical
part selection still reproduces the original silhouettes."""

from __future__ import annotations

import random

import pytest

from edge.art.port import (
    PORT_GRAMMAR,
    PORT_SUBTYPES,
    PortGenerator,
    _compose,
    _MIRROR,
    _mirror_part,
    _mirror_row,
    _SELF_SYMMETRIC,
)

_GEN = PortGenerator()
_SUBTYPES = ("stardock", "trading_port", "starbase")


def _mirror_line(line: str) -> str:
    """A whole rendered line, reflected: reversed with each glyph swapped to its
    mirror. A symmetric silhouette equals its own mirror."""
    return "".join(_MIRROR.get(ch, ch) for ch in reversed(line))


# --- mirror map ------------------------------------------------------------


def test_mirror_map_is_an_involution() -> None:
    for glyph, image in _MIRROR.items():
        assert _MIRROR[image] == glyph  # swapping twice is identity
        assert image in _MIRROR  # every image is itself a key


def test_self_symmetric_and_mirror_sets_are_disjoint() -> None:
    assert _SELF_SYMMETRIC.isdisjoint(_MIRROR)


def test_mirror_row_reproduces_known_rows() -> None:
    assert _mirror_row("    ▟███") == "    ▟█████▙    "
    assert _mirror_row("╾─▓████◊") == "╾─▓████◊████▓─╼"
    assert _mirror_row("       R") == "       R       "
    assert _mirror_row("") == ""


# --- part authoring --------------------------------------------------------


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_centre_columns_are_axis_legal(subtype: str) -> None:
    """Every part row's centre column (its last char) must read correctly on the
    mirror axis -- i.e. it must not be an asymmetric glyph that flips, or it would
    seam. Self-symmetric hull glyphs, spaces, beacons, and facets are all fine."""
    for slot in PORT_GRAMMAR[subtype]:
        for part in slot.parts:
            for row in part.left:
                assert row, "part rows must be non-empty (need a centre column)"
                assert row[-1] not in _MIRROR, (subtype, row)
                if row[-1] in _SELF_SYMMETRIC:
                    continue  # explicitly-enumerated axis-safe hull glyph
                # Otherwise it must be a facet (a non-hull decorative glyph),
                # which is a single cell on the axis and mirrors to itself.


def test_grammar_covers_the_public_subtypes() -> None:
    for subtype in PORT_SUBTYPES:
        assert subtype in PORT_GRAMMAR


# --- composition: symmetry & determinism -----------------------------------


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_composed_rows_are_symmetric(subtype: str) -> None:
    grammar = PORT_GRAMMAR[subtype]
    for seed in range(40):
        for height in (5, 9, 14, 20, 33):
            rows = _compose(grammar, random.Random(seed), height)
            for row in rows:
                assert row == _mirror_line(row), (subtype, seed, row)


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_painted_silhouette_is_symmetric(subtype: str) -> None:
    """End-to-end: the rendered sprite's silhouette (ignoring how it is centred
    in the box) reads the same mirrored. R/Y beacons paint to ▀/▄, both
    self-symmetric, so the property survives painting."""
    for seed in range(25):
        text = _GEN.generate(random.Random(seed), subtype, 30, 18)
        for line in text.plain.split("\n"):
            silhouette = line.strip(" ")
            assert silhouette == _mirror_line(silhouette), (subtype, seed, line)


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_generation_is_deterministic(subtype: str) -> None:
    a = _GEN.generate(random.Random(3), subtype, 24, 16, "ribbon_salvager")
    b = _GEN.generate(random.Random(3), subtype, 24, 16, "ribbon_salvager")
    assert a.plain == b.plain
    assert a.spans == b.spans


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_compose_consumes_fixed_draws_regardless_of_height(subtype: str) -> None:
    """The composer makes exactly one draw per slot, independent of target
    height, so the downstream beacon/window draw stream is identical across
    sizes -- two sprites of different heights share the same seeded details."""
    grammar = PORT_GRAMMAR[subtype]
    short = random.Random(11)
    _compose(grammar, short, 6)
    tall = random.Random(11)
    _compose(grammar, tall, 40)
    assert short.random() == tall.random()


# --- composition: height fitting -------------------------------------------


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_height_grows_monotonically_and_respects_bounds(subtype: str) -> None:
    grammar = PORT_GRAMMAR[subtype]
    # The minimum stack for this seed's chosen parts (target 0 forces min repeats).
    min_stack = len(_compose(grammar, random.Random(0), 0))
    prev = 0
    for height in range(3, 41):
        rows = _compose(grammar, random.Random(0), height)
        nh = len(rows)
        # Never overshoot unless even the minimum stack is taller than the box.
        assert nh <= height or nh == min_stack
        # Taller boxes never yield a shorter sprite (same seed → same parts).
        assert nh >= prev
        prev = nh
    # By height 40 the repeatable body has grown beyond the minimum.
    assert prev > min_stack


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_generate_fills_exact_box(subtype: str) -> None:
    for height in (3, 12, 25):
        for width in (9, 20, 40):
            text = _GEN.generate(random.Random(2), subtype, width, height)
            lines = text.plain.split("\n")
            assert len(lines) == height
            assert all(len(line) == width for line in lines)


# --- decompose, don't redraw -----------------------------------------------

# The original largest StarDock silhouette (pre-refactor PORT_ART tier 0).
_CANONICAL_STARDOCK = (
    "       R       ",
    "       █       ",
    "      ███      ",
    "    ▟█████▙    ",
    "╾─▓████◊████▓─╼",
    "    ▜██≡██▛    ",
    "     ▓███▓     ",
    "      ▜█▛      ",
    "       Y       ",
)


def test_canonical_selection_reproduces_original_stardock() -> None:
    """Choosing the first (canonical) part of every slot, with the body at its
    minimum repeat, must rebuild the exact historic StarDock art."""
    rows: list[str] = []
    for slot in PORT_GRAMMAR["stardock"]:
        rows.extend(_mirror_part(slot.parts[0]))
    assert tuple(rows) == _CANONICAL_STARDOCK
