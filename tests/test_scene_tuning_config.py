"""Tests for WP-SC05's shipped scene calibration (`scene.physical_model`).

Covers the calibration gate's closing step
(`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §5): the reviewer-approved values
from `docs/SCENE_CALIBRATION_REVIEW.md` §1-2 are now real, schema-validated
config, and `edge.art.scene_tuning.build_scene_tuning` /
`build_continuous_yields` turn a validated section into a real
`edge.scene.model.SceneTuning` / `ContinuousYield` map with exact `Fraction`
equality (never float-approximate).
"""

from __future__ import annotations

from fractions import Fraction

import pytest
from pydantic import ValidationError

from edge.art.scene_tuning import build_continuous_yields, build_scene_tuning
from edge.config import load_config
from edge.core.config import (
    GameConfig,
    ScenePhysicalModelConfig,
    SceneRegionConfig,
    _default_physical_model,
)
from edge.scene.catalog import ContinuousYield
from edge.scene.geometry import CellBox, Region
from edge.scene.model import SceneTuning

DEFAULT_CONFIG_PATH = "config/default.yaml"


def _cfg() -> GameConfig:
    return load_config(DEFAULT_CONFIG_PATH)


def test_default_yaml_loads_and_validates_physical_model() -> None:
    cfg = _cfg()
    pm = cfg.scene.physical_model
    assert isinstance(pm, ScenePhysicalModelConfig)
    assert pm.cost_budget == 800
    assert pm.max_camera_candidates == 64


def test_default_yaml_matches_schema_default() -> None:
    """`config/default.yaml`'s explicit `physical_model:` block and the
    schema's own `_default_physical_model()` fallback must stay in sync —
    both encode the same reviewer-approved numbers."""

    assert _cfg().scene.physical_model == _default_physical_model()


def test_fraction_fields_are_exact_fractions_not_floats() -> None:
    pm = _cfg().scene.physical_model
    assert pm.target_fraction_by_scale_class["entity"] == Fraction(1, 3)
    assert isinstance(pm.target_fraction_by_scale_class["entity"], Fraction)
    assert pm.cell_aspect == Fraction(2, 1)
    assert pm.depth_layer_scale == Fraction(4, 5)
    assert pm.min_visible_fraction_by_scale_class["orbital"] == Fraction(3, 4)
    assert pm.continuous["nebula"].ink_fraction_min == Fraction(2, 5)
    assert pm.cost_budget_estimate_tolerance == Fraction(1, 10)


def test_physical_model_extra_key_rejected() -> None:
    base = _default_physical_model().model_dump(mode="json")
    base["bogus_field"] = 1
    with pytest.raises(ValidationError):
        ScenePhysicalModelConfig(**base)


def test_physical_model_missing_required_field_rejected() -> None:
    base = _default_physical_model().model_dump(mode="json")
    del base["cost_budget"]
    with pytest.raises(ValidationError):
        ScenePhysicalModelConfig(**base)


def test_physical_model_missing_scale_class_rejected() -> None:
    base = _default_physical_model().model_dump(mode="json")
    del base["region_by_scale_class"]["ship"]
    with pytest.raises(ValidationError):
        ScenePhysicalModelConfig(**base)


def test_scene_region_config_shape() -> None:
    region = SceneRegionConfig(x_min=-1, x_max=1, y_min=-2, y_max=2, z_min=1, z_max=3)
    assert region.x_min == -1
    assert region.z_max == 3


def test_build_scene_tuning_matches_config_exactly() -> None:
    pm = _cfg().scene.physical_model
    tuning = build_scene_tuning(pm)
    assert isinstance(tuning, SceneTuning)

    assert tuning.face_extent_by_scale_class == {
        k: tuple(v) for k, v in pm.face_extent_by_scale_class.items()
    }
    assert tuning.face_extent_by_kind == {
        k: tuple(v) for k, v in pm.face_extent_by_kind.items()
    }
    assert tuning.region_by_scale_class["ship"] == Region(
        x_min=-320, x_max=320, y_min=-160, y_max=160, z_min=300, z_max=819,
    )
    assert tuning.region_by_scale_class["anchor"] == Region(
        x_min=-200, x_max=200, y_min=-100, y_max=100, z_min=600, z_max=699,
    )
    # WP-SC12: a station's orbit is an offset from its parent, distinct from
    # the absolute region it uses when it has no planet.
    assert tuning.orbit_offset_region_by_scale_class["orbital"] == Region(
        x_min=-200, x_max=200, y_min=-100, y_max=100, z_min=-120, z_max=120,
    )
    assert tuning.region_by_scale_class["orbital"] == Region(
        x_min=-200, x_max=200, y_min=-100, y_max=100, z_min=300, z_max=799,
    )
    assert tuning.target_fraction_by_scale_class["entity"] == Fraction(1, 3)
    assert tuning.ink_ratio_by_scale_class["ship"] == Fraction(9, 10)
    assert tuning.structural_mode_thresholds == (
        (120, 44, "wide"), (87, 36, "standard"), (0, 0, "compact"),
    )
    assert (tuning.fixed_fov_num, tuning.fixed_fov_den) == (1, 2)
    assert tuning.cell_aspect == Fraction(2, 1)
    assert tuning.near_plane_su == 1
    assert (tuning.depth_layers, tuning.depth_layer_size_su, tuning.depth_layer_scale) == (
        8, 6, Fraction(4, 5),
    )
    assert (tuning.camera_height_fraction_min, tuning.camera_height_fraction_max) == (
        Fraction(1, 8), Fraction(3, 4),
    )
    assert tuning.aim_offsets_su == (0, -2, 2, -4, 4, -6, 6)
    assert tuning.max_camera_candidates == 64
    assert (tuning.hysteresis_weight_camera, tuning.hysteresis_weight_position,
            tuning.hysteresis_weight_admission, tuning.hysteresis_weight_art) == (1, 1, 4, 1)
    assert tuning.max_passes == 24
    assert tuning.edge_margin == 1
    assert tuning.min_projected_cells_by_scale_class["orbital"] == (11, 7)
    assert tuning.separation_margin == 1
    assert tuning.min_visible_fraction_by_scale_class["entity"] == Fraction(1, 1)
    assert tuning.cost_budget == 800
    assert tuning.emergency_ship_ceiling == 40
    assert tuning.max_reposition_candidates == 16
    assert tuning.max_glyph_tries == 20
    assert tuning.glyph_spacing == 2

    # WP-SC12 station-size parity: the reference body height and the per-kind
    # targets, both lifted from the legacy composer's own scale chain.
    reference = tuning.station_size_reference
    assert reference is not None
    assert (reference.height_fraction, reference.header_rows) == (Fraction(9, 10), 4)
    assert (reference.width_fraction, reference.max_cells, reference.min_cells) == (
        Fraction(11, 20), 40, 4,
    )
    assert set(tuning.station_target_by_scale_class) == {"orbital", "starbase", "stardock"}
    assert tuning.station_target_by_scale_class["orbital"].parent_scale == Fraction(3, 10)
    assert tuning.station_target_by_scale_class["starbase"].parent_scale == Fraction(7, 20)
    assert tuning.station_target_by_scale_class["stardock"].parent_scale == Fraction(3, 5)
    for target in tuning.station_target_by_scale_class.values():
        assert target.lone_scale == Fraction(3, 5)


def test_build_continuous_yields_matches_config_exactly() -> None:
    pm = _cfg().scene.physical_model
    yields = build_continuous_yields(pm)
    assert set(yields) == {
        "planet", "nebula", "black_hole", "wormhole", "wreck", "entity", "belt",
    }
    nebula = yields["nebula"]
    assert isinstance(nebula, ContinuousYield)
    assert nebula.ink_fraction_min == Fraction(2, 5)
    assert nebula.ink_fraction_max == Fraction(9, 10)
    assert nebula.min_extent == CellBox(col=0, row=0, width=10, height=5)
    assert nebula.box_classes == (
        CellBox(col=0, row=0, width=100, height=50),
        CellBox(col=0, row=0, width=64, height=32),
        CellBox(col=0, row=0, width=36, height=18),
    )
    assert nebula.render_cost == (110, 55, 20)

    wreck = yields["wreck"]
    assert wreck.box_classes == (
        CellBox(col=0, row=0, width=24, height=10),
        CellBox(col=0, row=0, width=16, height=7),
    )
    assert wreck.render_cost == (15, 6)


def test_continuous_yield_render_cost_length_must_match_box_classes() -> None:
    base = _default_physical_model().model_dump(mode="json")
    base["continuous"]["planet"]["render_cost"] = [1, 2]  # 3 box_classes, 2 costs
    with pytest.raises(ValidationError):
        ScenePhysicalModelConfig(**base)


def test_legacy_scene_art_config_unaffected() -> None:
    """The pre-existing `SceneArtConfig` fields (legacy `_SceneComposer`) are
    untouched by adding `physical_model` alongside them."""

    cfg = _cfg()
    assert cfg.scene.ship_scale == 0.2
    assert cfg.scene.port_scale == 0.3
