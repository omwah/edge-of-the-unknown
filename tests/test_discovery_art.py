"""Tests for the procedural discovery sprites (``edge/art/discovery.py``).

Covers the five free-floating sector-space kinds (nebula / black_hole / wormhole /
wreck / entity) — the four planet-surface-site kinds (ruins / artifact / ancient_tech
/ crashed_ship) were retired in GW-WP14, superseded by the GroundWar expedition
field-sketch art (``edge.groundwar.findart``, see ``tests/test_surface_finds.py``).
The guarantees worth pinning: every subtype fills the exact bounding box at any
size, and is seeded-deterministic.
"""

from __future__ import annotations

import random

import pytest

from edge.art.discovery import DISCOVERY_GRAMMAR, DiscoveryGenerator

_GEN = DiscoveryGenerator()
_SUBTYPES = tuple(DISCOVERY_GRAMMAR)
_SIZES = ((20, 10), (12, 6), (40, 14), (17, 9))


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_every_subtype_fills_the_exact_box(subtype: str) -> None:
    for width, height in _SIZES:
        text = _GEN.generate(random.Random(5), subtype, width, height)
        lines = text.plain.split("\n")
        assert len(lines) == height, (subtype, width, height)
        assert all(len(line) == width for line in lines), (subtype, width, height)


@pytest.mark.parametrize("subtype", _SUBTYPES)
def test_generation_is_deterministic(subtype: str) -> None:
    a = _GEN.generate(random.Random(9), subtype, 24, 11, "humanoid_diplomat")
    b = _GEN.generate(random.Random(9), subtype, 24, 11, "humanoid_diplomat")
    assert a.plain == b.plain
    assert a.spans == b.spans
