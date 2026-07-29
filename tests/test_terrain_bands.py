"""GW-WP21 — a landable biome's band names must be unique, and every band must be
able to reach its own authored colours.

`BIOME_BANDS` (gameplay, `edge.core.groundwar.terrain`) and `BIOME_COLORS`/
`FEATURES_REGISTRY` (presentation, `edge.art.terrain`) are index-aligned lists, but the
ground map views do not have the index — they receive a *feature name* per cell and call
`feature_colors(ptype, feature)`, which scans the band list for the first match. So two
bands of one biome sharing a name silently collapses them: the later band's colours
become unreachable and two terrains that were authored to look different render
identically. `terrestrial_cold` did exactly that with a shallow and a high `ice` band
until the top one became `glacier`.

Non-landable biomes (jovian, asteroid_belt) may still repeat a name. Nothing projects
them into a ground view — Cloud City interiors use a disjoint feature namespace — and
planet art reads bands positionally via `get_biome_feature`, so a repeat there is
harmless. These tests therefore scope the uniqueness rule to `LANDABLE_BIOMES`, which is
where it actually bites.
"""

from __future__ import annotations

import pytest

from edge.art.terrain import BIOME_COLORS, FEATURES_REGISTRY
from edge.config import load_default_config
from edge.core.groundwar.terrain import BIOME_BANDS, LANDABLE_BIOMES
from edge.tui.screens._ground_shared import feature_colors

CFG = load_default_config()


@pytest.mark.parametrize("ptype", LANDABLE_BIOMES)
def test_a_landable_biome_never_repeats_a_band_name(ptype: str) -> None:
    """The invariant itself. This is the guard that stops the bug returning: adding a
    duplicate band name to a walkable biome fails here rather than quietly costing that
    band its colours somewhere in the TUI."""
    names = [name for _threshold, name in BIOME_BANDS[ptype].bands]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    assert not duplicates, (
        f"{ptype} repeats band name(s) {duplicates}; feature_colors() keys on the name, "
        f"so only the first such band's colours can ever render")


@pytest.mark.parametrize("ptype", LANDABLE_BIOMES)
def test_every_band_resolves_to_its_own_authored_colours(ptype: str) -> None:
    """The property the uniqueness rule exists to protect: walking the bands in order,
    each one's feature name must look up the colour pair authored at *its* index."""
    bands = BIOME_BANDS[ptype].bands
    colors = BIOME_COLORS[ptype]
    assert len(colors) >= len(bands), f"{ptype} has fewer colour pairs than bands"
    for index, (_threshold, name) in enumerate(bands):
        assert feature_colors(ptype, name) == colors[index], (
            f"{ptype} band {index} ({name}) renders in another band's colours")


def test_cold_shelf_ice_and_high_glacier_look_different() -> None:
    """The concrete regression. Before the split, both bands were named `ice` and the
    high band's cyan-on-blue was unreachable — deep glacial ice drew in shallow ice's
    white-on-white."""
    shelf = feature_colors("terrestrial_cold", "ice")
    glacier = feature_colors("terrestrial_cold", "glacier")
    assert shelf != glacier
    assert glacier == ("bright_cyan", "blue")


@pytest.mark.parametrize("ptype", LANDABLE_BIOMES)
def test_every_landable_band_has_gameplay_rules_and_a_glyph(ptype: str) -> None:
    """A new band name is not free: it needs a terrain class (movement/cover/LOS) and at
    least one glyph, or it walks like nothing and draws as `?`."""
    assert CFG.groundwar is not None
    for _threshold, name in BIOME_BANDS[ptype].bands:
        assert name in CFG.groundwar.terrain, f"{name} has no terrain class in config"
        assert FEATURES_REGISTRY.get(name), f"{name} has no glyphs in FEATURES_REGISTRY"


def test_glacier_is_still_barred_as_a_survey_drop_site() -> None:
    """`glacier` was part of `ice` when the shuttle refused to set down on it; splitting
    the band must not quietly open a landing site that was closed."""
    assert CFG.groundwar is not None
    blocked = CFG.groundwar.expedition.landing_blocked_features
    assert "ice" in blocked and "glacier" in blocked
