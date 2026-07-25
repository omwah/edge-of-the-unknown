"""GW-WP17 regression — every ground-operation render glyph must be single-width.

`edge.tui.screens._ground_shared.CroppedMapView` (survey + assault) lays the map out on
a fixed per-cell grid: one glyph, one terminal column. A double-width glyph (`rich.cells
.cell_len` == 2 — `⚡`/`⌘`-style symbols are common offenders) desyncs that assumption one
column per occurrence, which cascades through the rest of that row and misaligns
whatever sits to its right — the sidebar's own border, in the live screens. This is
exactly how GW-WP17 shipped a broken Cloud City tour sidebar: `edge.art.interior`'s
`engineering`/`electrical` glyph pools picked `⚌`/`⚡`, both width 2.

Two checks: the two *registries* (biome + interior glyph-pool dicts) are swept
programmatically, so a future glyph addition to either is caught automatically. The
*hardcoded* marker glyphs scattered across the survey/assault screens and
`edge/groundwar/widgets.py` have no shared registry to sweep — this is a point-in-time
inventory of the current set, run once to confirm the reported bug's fix is complete.
"""

from __future__ import annotations

from rich.cells import cell_len

from edge.art.interior import (
    DOOR_GLYPH,
    FEATURES_REGISTRY as INTERIOR_FEATURES_REGISTRY,
    LIFT_GLYPH,
    OBJECTIVE_GLYPH,
    WALL_GLYPHS,
)
from edge.art.terrain import FEATURES_REGISTRY as BIOME_FEATURES_REGISTRY
from edge.groundwar.widgets import RUBBLE_ART, STRUCTURE_ART

# The hardcoded per-cell/sidebar markers in ground_expedition.py, ground_assault.py, and
# _ground_shared.py that aren't drawn from either glyph-pool registry above.
_HARDCODED_MARKER_GLYPHS = (
    "Ѫ",  # _EXPLORER
    "✦", "◌", "∴", "▒", "█", "⌂", "◉",  # ground_expedition.py _cell overlays
    "░", "◇", "═", "⚠",  # ground_expedition.py _status sidebar
    "▲", "▼", "✓", "▶",  # ground_assault.py troopers/landing/confirm markers
    "╱", "▲", "╲",  # _ground_shared.py landing_frames animation
)


def test_biome_glyph_registry_is_single_width() -> None:
    for feature, choices in BIOME_FEATURES_REGISTRY.items():
        for glyph, _weight in choices:
            assert cell_len(glyph) == 1, f"biome {feature!r} glyph {glyph!r} is not single-width"


def test_interior_glyph_registry_is_single_width() -> None:
    for feature, choices in INTERIOR_FEATURES_REGISTRY.items():
        for glyph, _weight in choices:
            assert cell_len(glyph) == 1, f"interior {feature!r} glyph {glyph!r} is not single-width"
    for glyph in (DOOR_GLYPH, LIFT_GLYPH, OBJECTIVE_GLYPH, *WALL_GLYPHS):
        assert cell_len(glyph) == 1, f"{glyph!r} is not single-width"


def test_structure_art_glyphs_are_single_width() -> None:
    for kind, (glyph, _fg, _bg) in STRUCTURE_ART.items():
        assert cell_len(glyph) == 1, f"structure {kind!r} glyph {glyph!r} is not single-width"
    assert cell_len(RUBBLE_ART[0]) == 1


def test_hardcoded_marker_glyphs_are_single_width() -> None:
    for glyph in _HARDCODED_MARKER_GLYPHS:
        assert cell_len(glyph) == 1, f"{glyph!r} is not single-width"
