"""Tests for the procedural discovery sprites (``edge/art/discovery.py``).

The four *surface-site* subtypes (ruins / artifact / ancient_tech / crashed_ship)
draw a full planet scene — alien-dusk sky over textured ground with the structure
overlaid — by assembling ``rich.Text`` directly rather than through the hull
``render_grid`` path. The guarantees worth pinning are the same contract the other
sprites honour: every subtype fills the exact bounding box at any size, is seeded-
deterministic (and varies with the seed), and the archetype-tint path is exercised
for both an applied archetype and none.
"""

from __future__ import annotations

import random

import pytest

from edge.art.discovery import DISCOVERY_GRAMMAR, DiscoveryGenerator

_GEN = DiscoveryGenerator()
_SUBTYPES = tuple(DISCOVERY_GRAMMAR)
# The new ground/sky surface scenes, kept apart so they can be asserted on directly.
_SURFACE = ("ruins", "artifact", "ancient_tech", "crashed_ship")
_SIZES = ((20, 10), (12, 6), (40, 14), (17, 9))


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_every_subtype_fills_the_exact_box(subtype: str) -> None:
    for width, height in _SIZES:
        text = _GEN.generate(random.Random(5), subtype, width, height)
        lines = text.plain.split("\n")
        assert len(lines) == height, (subtype, width, height)
        assert all(len(line) == width for line in lines), (subtype, width, height)


@pytest.mark.parametrize("subtype", _SURFACE)
def test_surface_scene_is_not_blank(subtype: str) -> None:
    """A surface scene is painted edge to edge (sky/ground backgrounds + a
    structure), so it must carry visible content, not an empty box."""
    text = _GEN.generate(random.Random(3), subtype, 20, 10)
    assert any(line.strip() for line in text.plain.split("\n"))
    assert len(text.spans) > 0  # colour was applied


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_generation_is_deterministic(subtype: str) -> None:
    a = _GEN.generate(random.Random(9), subtype, 24, 11, "humanoid_diplomat")
    b = _GEN.generate(random.Random(9), subtype, 24, 11, "humanoid_diplomat")
    assert a.plain == b.plain
    assert a.spans == b.spans


@pytest.mark.parametrize("subtype", _SURFACE)
def test_different_seeds_differ(subtype: str) -> None:
    a = _GEN.generate(random.Random(1), subtype, 24, 11)
    b = _GEN.generate(random.Random(2), subtype, 24, 11)
    assert a.plain != b.plain or a.spans != b.spans


@pytest.mark.parametrize("subtype", _SURFACE)
@pytest.mark.parametrize("archetype", [None, "humanoid_diplomat", "tentacled_envoy"])
def test_archetype_tint_path_renders(subtype: str, archetype: str | None) -> None:
    """Both the fixed-fallback accent (no archetype) and the archetype-tinted
    accent must render a well-formed box without raising."""
    text = _GEN.generate(random.Random(4), subtype, 20, 10, archetype)
    lines = text.plain.split("\n")
    assert len(lines) == 10
    assert all(len(line) == 20 for line in lines)


@pytest.mark.parametrize("subtype", _SURFACE)
def test_tiny_boxes_do_not_crash(subtype: str) -> None:
    for width, height in ((4, 1), (5, 2), (8, 3)):
        text = _GEN.generate(random.Random(0), subtype, width, height)
        lines = text.plain.split("\n")
        assert len(lines) == height
        assert all(len(line) == width for line in lines)
