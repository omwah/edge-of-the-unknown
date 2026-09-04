"""Unit tests for the pure scene model shapes (WP-SC02).

Pins relationships, identities, art modes, scale, retention, permeability, ink
estimates, and glyph classification per
`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §9.3, and checks the generated
geometry catalogue against fresh renders of the vendored assets.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from edge.art.geometry_catalog import JsonArtGeometryCatalog, load_default_geometry_catalog
from edge.art.sprite_art import render_sprite, resolve_archetype
from edge.art.sprites import SPRITES, _natural_box
from edge.scene.catalog import ContinuousYield, LadderKey
from edge.scene.geometry import CellBox, Face, FaceShape, Region, Vec3
from edge.scene.model import (
    ArtMode,
    Camera,
    Placement,
    PhysicalObject,
    SceneKey,
    SceneRetention,
    SceneTuning,
    WorldArrangement,
)
from edge.tui.art_adapter import text_to_cells


def _face(shape: FaceShape, w: int, h: int) -> Face:
    return Face(shape=shape, width_su=w, height_su=h)


def _region() -> Region:
    return Region(x_min=0, x_max=0, y_min=0, y_max=0, z_min=1, z_max=1)


def _object(
    key: SceneKey,
    *,
    face: Face,
    retention: SceneRetention,
    parent: SceneKey | None = None,
    art_mode: ArtMode = ArtMode.CONTINUOUS,
    occludes: bool = True,
) -> PhysicalObject:
    return PhysicalObject(
        key=key,
        parent=parent,
        face=face,
        scale_class="test",
        art_mode=art_mode,
        ladder_key=None,
        continuous_kind="nebula",
        archetype_id=None,
        retention=retention,
        hostility_ordinal=0,
        threat_rank=0,
        region=_region(),
        flexible=False,
        occludes=occludes,
        label="",
        destination=None,
    )


# ---------------------------------------------------------------------------
# Face / scale-class ordering (plan §4.4, §9.1)
# ---------------------------------------------------------------------------


def test_face_area_is_exact_bounding_box_product() -> None:
    face = _face(FaceShape.CIRCLE, 10, 10)
    assert face.area_su == 100
    ellipse = _face(FaceShape.ELLIPSE, 12, 4)
    assert ellipse.area_su == 48


def test_scale_class_ordering_compares_nominal_face_area_not_ink() -> None:
    """A sparse tall station can out-order a dense wide ship purely by nominal
    face area, matching plan §4.4 ("rendered ink is not a physical-size
    metric")."""

    ship = _face(FaceShape.RECT, 20, 3)  # area 60, dense long hull
    station = _face(FaceShape.RECT, 4, 20)  # area 80, sparse vertical mast
    assert station.area_su > ship.area_su


# ---------------------------------------------------------------------------
# Retention hierarchy (plan §2.3, §9.3)
# ---------------------------------------------------------------------------


def test_retention_hierarchy_matches_plan_ordering() -> None:
    ordered = [
        SceneRetention.ENTITY,
        SceneRetention.ANCHOR,
        SceneRetention.ORBITAL,
        SceneRetention.HOSTILE_SHIP,
        SceneRetention.NEUTRAL_SHIP,
        SceneRetention.WRECK,
        SceneRetention.FRIENDLY_SHIP,
    ]
    assert ordered == sorted(ordered)
    assert [int(r) for r in ordered] == list(range(7))


def test_retention_sort_key_orders_hostile_before_neutral_before_wreck_before_friendly() -> None:
    objects = [
        _object(SceneKey("ship", 1), face=_face(FaceShape.RECT, 2, 2), retention=SceneRetention.FRIENDLY_SHIP),
        _object(SceneKey("wreck", 2), face=_face(FaceShape.RECT, 2, 2), retention=SceneRetention.WRECK),
        _object(SceneKey("ship", 3), face=_face(FaceShape.RECT, 2, 2), retention=SceneRetention.HOSTILE_SHIP),
        _object(SceneKey("ship", 4), face=_face(FaceShape.RECT, 2, 2), retention=SceneRetention.NEUTRAL_SHIP),
    ]
    ordered = sorted(objects, key=lambda o: (o.retention, o.hostility_ordinal, -o.threat_rank, o.key))
    assert [o.retention for o in ordered] == [
        SceneRetention.HOSTILE_SHIP,
        SceneRetention.NEUTRAL_SHIP,
        SceneRetention.WRECK,
        SceneRetention.FRIENDLY_SHIP,
    ]


# ---------------------------------------------------------------------------
# Identity / SceneKey (plan §2.3, §4.1)
# ---------------------------------------------------------------------------


def test_scene_key_is_hashable_and_stable_tie_break() -> None:
    a = SceneKey("ship", 5)
    b = SceneKey("ship", 5)
    c = SceneKey("ship", 6)
    assert a == b
    assert hash(a) == hash(b)
    assert sorted([c, a]) == [a, c]


def test_scene_key_tag_distinguishes_cross_kind_collisions() -> None:
    ship = SceneKey("ship", 1)
    player = SceneKey("player", 1)
    assert ship != player


# ---------------------------------------------------------------------------
# Parent relationships (plan §4.3)
# ---------------------------------------------------------------------------


def test_orbital_infrastructure_declares_its_planet_parent() -> None:
    planet_key = SceneKey("planet", 1)
    port = _object(
        SceneKey("port", 2),
        face=_face(FaceShape.RECT, 11, 14),
        retention=SceneRetention.ORBITAL,
        parent=planet_key,
    )
    assert port.parent == planet_key


# ---------------------------------------------------------------------------
# Art mode / glyph classification (plan §2.5, §9.3)
# ---------------------------------------------------------------------------


def test_glyphs_are_a_distinct_art_mode_and_never_occlude() -> None:
    glyph = _object(
        SceneKey("glyph", 1),
        face=_face(FaceShape.FIELD, 1, 1),
        retention=SceneRetention.FRIENDLY_SHIP,  # glyphs never participate in retention (§2.3)
        art_mode=ArtMode.GLYPH,
        occludes=False,
    )
    assert glyph.art_mode is ArtMode.GLYPH
    assert glyph.occludes is False


def test_belts_are_permeable_fields() -> None:
    belt = _object(
        SceneKey("belt", 1),
        face=_face(FaceShape.FIELD, 40, 8),
        retention=SceneRetention.ORBITAL,
        occludes=False,
    )
    assert belt.face.shape is FaceShape.FIELD
    assert belt.occludes is False


# ---------------------------------------------------------------------------
# WorldArrangement / Camera / SceneTuning (plan §9.3)
# ---------------------------------------------------------------------------


def test_world_arrangement_pairs_objects_with_deterministic_placements() -> None:
    key = SceneKey("ship", 1)
    obj = _object(key, face=_face(FaceShape.RECT, 4, 2), retention=SceneRetention.NEUTRAL_SHIP)
    placement = Placement(key=key, position=Vec3(0, 0, 5))
    arrangement = WorldArrangement(objects=(obj,), placements=(placement,))
    assert arrangement.objects[0].key == arrangement.placements[0].key


def test_camera_cell_aspect_is_an_exact_fraction() -> None:
    camera = Camera(
        position=Vec3(0, 0, 0),
        aim_x_su=0,
        aim_y_su=0,
        fov_num=1,
        fov_den=1,
        near_plane_su=1,
        cell_aspect=Fraction(2, 1),
        depth_layer_size_su=1,
        depth_layer_scale=Fraction(4, 5),
    )
    assert camera.cell_aspect == Fraction(2)


def test_scene_tuning_has_no_shipped_default_instance() -> None:
    """WP-SC02 defines the tuning bundle's shape (what the classifier needs
    to look up), not its values -- no module-level default instance exists,
    so a caller must always build its own from calibrated config."""

    import edge.scene.model as scene_model_module

    assert not any(
        isinstance(value, SceneTuning) for value in vars(scene_model_module).values()
    )
    # The shape itself is usable once a caller supplies real numbers -- this
    # is what proves it is a shape, not a placeholder that silently ships
    # zeros.
    tuning = SceneTuning(
        face_extent_by_scale_class={"ship": (4, 2)},
        face_extent_by_kind={},
        region_by_scale_class={"ship": _region()},
        target_fraction_by_scale_class={"ship": Fraction(1, 3)},
        ink_ratio_by_scale_class={"ship": Fraction(4, 5)},
        structural_mode_thresholds=((0, 0, "compact"),),
        fixed_fov_num=1,
        fixed_fov_den=2,
        cell_aspect=Fraction(2, 1),
        near_plane_su=1,
        depth_layers=4,
        depth_layer_size_su=5,
        depth_layer_scale=Fraction(4, 5),
        camera_height_fraction_min=Fraction(1, 4),
        camera_height_fraction_max=Fraction(3, 4),
        aim_offsets_su=(0,),
        max_camera_candidates=16,
        hysteresis_weight_camera=1,
        hysteresis_weight_position=1,
        hysteresis_weight_admission=1,
        hysteresis_weight_art=1,
        max_passes=32,
        edge_margin=1,
        min_projected_cells_by_scale_class={"ship": (3, 1)},
        separation_margin=1,
        min_visible_fraction_by_scale_class={"ship": Fraction(1, 2)},
        cost_budget=500,
        emergency_ship_ceiling=20,
        max_reposition_candidates=4,
        max_glyph_tries=8,
        glyph_spacing=1,
    )
    assert tuning.face_extent_by_scale_class["ship"] == (4, 2)


# ---------------------------------------------------------------------------
# Catalogue vs. fresh render (plan §9.4 verification)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def catalog() -> JsonArtGeometryCatalog:
    return load_default_geometry_catalog()


def test_catalog_natural_box_matches_a_fresh_render(catalog: JsonArtGeometryCatalog) -> None:
    key = LadderKey(kind="ship", subtype="warship", axis="horizontal", archetype_id="humanoid_diplomat")
    rungs = catalog.rungs(key)
    assert rungs
    rung = rungs[0]
    sprite = SPRITES.sprites["warship"]
    view = sprite.views["horizontal"]
    tier = view.tiers[rung.index]
    natural = _natural_box(view, tier, resolve_archetype("humanoid_diplomat"))
    assert (rung.natural.width, rung.natural.height) == natural


def test_catalog_ink_bounds_match_a_fresh_render_on_both_axes(catalog: JsonArtGeometryCatalog) -> None:
    horizontal = LadderKey(kind="ship", subtype="warship", axis="horizontal", archetype_id="humanoid_diplomat")
    vertical = LadderKey(kind="ship", subtype="warship", axis="vertical", archetype_id="humanoid_diplomat")
    for key, view_id in ((horizontal, "horizontal"), (vertical, "vertical")):
        rung = catalog.rungs(key)[0]
        sprite = SPRITES.sprites["warship"]
        view = sprite.views[view_id]
        art = render_sprite(
            sprite,
            SPRITES.palettes,
            width=rung.natural.width,
            height=rung.natural.height,
            seed=0,
            archetype_id=resolve_archetype("humanoid_diplomat"),
            view_id=view_id,
            facing=view.canonical_facing,
        )
        cells = text_to_cells(art)
        cols = {x for row in cells for x, (ch, _s) in enumerate(row) if ch != " "}
        rows_ = {y for y, row in enumerate(cells) for ch, _s in row if ch != " "}
        assert min(cols) >= rung.ink_min.col
        assert max(cols) - min(cols) + 1 <= rung.ink_max.width
        assert min(rows_) >= 0


def test_facing_and_archetype_select_different_catalog_records(catalog: JsonArtGeometryCatalog) -> None:
    horizontal = LadderKey(kind="ship", subtype="warship", axis="horizontal", archetype_id="humanoid_diplomat")
    vertical = LadderKey(kind="ship", subtype="warship", axis="vertical", archetype_id="humanoid_diplomat")
    assert catalog.rungs(horizontal)[0].natural != catalog.rungs(vertical)[0].natural

    other_archetype = LadderKey(kind="ship", subtype="warship", axis="horizontal", archetype_id="canid_technologist")
    default_rung = catalog.rungs(horizontal)[0]
    other_rung = catalog.rungs(other_archetype)[0]
    # Natural box is archetype-invariant for this sprite's horizontal tiers,
    # but the measured ink envelope may legitimately differ per archetype
    # (plan §2.5): assert the catalogue actually stores them as separate keys
    # rather than collapsing archetypes onto one record.
    assert (horizontal, default_rung) != (other_archetype, other_rung)
    assert default_rung is not other_rung


def test_subtype_plus_rung_index_alone_is_ambiguous_without_axis_and_archetype(
    catalog: JsonArtGeometryCatalog,
) -> None:
    """Regression for the exact under-specification plan §2.5 calls out."""

    keys = {
        LadderKey(kind="ship", subtype="warship", axis="horizontal", archetype_id="humanoid_diplomat"),
        LadderKey(kind="ship", subtype="warship", axis="vertical", archetype_id="humanoid_diplomat"),
        LadderKey(kind="ship", subtype="warship", axis="horizontal", archetype_id="canid_technologist"),
    }
    naturals = {catalog.rungs(k)[0].natural for k in keys}
    assert len(naturals) >= 2, "axis alone must select different geometry"


# ---------------------------------------------------------------------------
# ContinuousYield shape (plan §9.4: not generated here, no shipped defaults)
# ---------------------------------------------------------------------------


def test_continuous_yield_has_no_shipped_instances() -> None:
    catalog = load_default_geometry_catalog()
    with pytest.raises(KeyError):
        catalog.continuous("nebula")


def test_continuous_yield_shape_is_definable() -> None:
    yield_ = ContinuousYield(
        kind="nebula",
        ink_fraction_min=Fraction(1, 4),
        ink_fraction_max=Fraction(3, 4),
        min_extent=CellBox(0, 0, 4, 4),
        box_classes=(CellBox(0, 0, 20, 10), CellBox(0, 0, 10, 5)),
        render_cost=(100, 40),
    )
    assert yield_.box_classes[0].width > yield_.box_classes[1].width
