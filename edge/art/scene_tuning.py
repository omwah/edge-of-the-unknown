"""Builds `edge.scene.model.SceneTuning` from validated `scene.physical_model`
config (WP-SC05).

`edge/scene/` never reads config files itself (`edge/scene/model.py`'s
`SceneTuning` docstring, AGENTS.md's `edge/scene` layering note); this is the
art/TUI seam that does — the same pattern `edge/art/geometry_catalog.py`
established for the injected `ArtGeometryCatalog` (WP-SC02). A caller (the
eventual WP-SC08/SC09 TUI wiring, or a test) passes a validated
`edge.core.config.ScenePhysicalModelConfig` in and gets back a real, frozen
`SceneTuning` plus the per-kind `ContinuousYield` envelopes that
`edge.art.geometry_catalog.JsonArtGeometryCatalog` needs for its `continuous()`
lookups.

Not wired into any running composer by this commit — see `SceneTuning`'s own
docstring and `docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §5's closing
instruction.
"""

from __future__ import annotations

from edge.core.config import ScenePhysicalModelConfig, SceneRegionConfig
from edge.scene.catalog import ContinuousYield
from edge.scene.geometry import CellBox, Region
from edge.scene.model import SceneTuning


def _region(cfg: SceneRegionConfig) -> Region:
    return Region(
        x_min=cfg.x_min, x_max=cfg.x_max,
        y_min=cfg.y_min, y_max=cfg.y_max,
        z_min=cfg.z_min, z_max=cfg.z_max,
    )


def _cell_box(extent: tuple[int, int]) -> CellBox:
    width, height = extent
    return CellBox(col=0, row=0, width=width, height=height)


def build_scene_tuning(cfg: ScenePhysicalModelConfig) -> SceneTuning:
    """Construct the frozen `SceneTuning` bundle from validated config.

    A near-mechanical field-for-field copy — `ScenePhysicalModelConfig`'s
    field names mirror `SceneTuning`'s exactly (see that config class's
    docstring) — plus the two shape conversions config can express but the
    pure `edge.scene` dataclasses cannot import: `SceneRegionConfig` ->
    `Region`, and the config's plain `(num, den)`-free `Fraction`s pass
    straight through unchanged.
    """

    return SceneTuning(
        face_extent_by_scale_class=dict(cfg.face_extent_by_scale_class),
        face_extent_by_kind=dict(cfg.face_extent_by_kind),
        region_by_scale_class={
            scale_class: _region(region)
            for scale_class, region in cfg.region_by_scale_class.items()
        },
        target_fraction_by_scale_class=dict(cfg.target_fraction_by_scale_class),
        ink_ratio_by_scale_class=dict(cfg.ink_ratio_by_scale_class),
        structural_mode_thresholds=cfg.structural_mode_thresholds,
        fixed_fov_num=cfg.fixed_fov_num,
        fixed_fov_den=cfg.fixed_fov_den,
        cell_aspect=cfg.cell_aspect,
        near_plane_su=cfg.near_plane_su,
        depth_layers=cfg.depth_layers,
        depth_layer_size_su=cfg.depth_layer_size_su,
        depth_layer_scale=cfg.depth_layer_scale,
        camera_height_fraction_min=cfg.camera_height_fraction_min,
        camera_height_fraction_max=cfg.camera_height_fraction_max,
        aim_offsets_su=cfg.aim_offsets_su,
        max_camera_candidates=cfg.max_camera_candidates,
        hysteresis_weight_camera=cfg.hysteresis_weight_camera,
        hysteresis_weight_position=cfg.hysteresis_weight_position,
        hysteresis_weight_admission=cfg.hysteresis_weight_admission,
        hysteresis_weight_art=cfg.hysteresis_weight_art,
        max_passes=cfg.max_passes,
        edge_margin=cfg.edge_margin,
        min_projected_cells_by_scale_class=dict(cfg.min_projected_cells_by_scale_class),
        separation_margin=cfg.separation_margin,
        min_visible_fraction_by_scale_class=dict(cfg.min_visible_fraction_by_scale_class),
        cost_budget=cfg.cost_budget,
        emergency_ship_ceiling=cfg.emergency_ship_ceiling,
        max_reposition_candidates=cfg.max_reposition_candidates,
        max_glyph_tries=cfg.max_glyph_tries,
        glyph_spacing=cfg.glyph_spacing,
    )


def build_continuous_yields(cfg: ScenePhysicalModelConfig) -> dict[str, ContinuousYield]:
    """Construct the per-kind `ContinuousYield` envelopes (calibration §2)
    that `edge.scene.catalog.ArtGeometryCatalog.continuous()` looks up by
    `PhysicalObject.continuous_kind` category bucket."""

    return {
        kind: ContinuousYield(
            kind=kind,
            ink_fraction_min=envelope.ink_fraction_min,
            ink_fraction_max=envelope.ink_fraction_max,
            min_extent=_cell_box(envelope.min_extent),
            box_classes=tuple(_cell_box(box) for box in envelope.box_classes),
            render_cost=envelope.render_cost,
        )
        for kind, envelope in cfg.continuous.items()
    }
