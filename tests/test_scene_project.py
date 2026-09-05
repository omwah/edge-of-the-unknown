"""Tests for the projection strategies (WP-SC03).

Covers: exact `Fraction`/`int` arithmetic (no float feeding a decision), the
`frame()`/`project()`/`candidates()`/`structural_mode()` contracts, both
strategies compared under identical inventories (calibration-contract style,
structural comparison only -- visual approval is WP-SC04's), deterministic
candidate ordering, and that projection never imports or calls into sprite
rendering.
"""

from __future__ import annotations

from fractions import Fraction

from edge.scene.catalog import ArtGeometryCatalog, ContinuousYield, LadderKey, LadderRung
from edge.scene.geometry import CellBox, Face, FaceShape, Region, Vec3
from edge.scene.model import (
    ArtMode,
    Camera,
    PhysicalObject,
    Placement,
    SceneKey,
    SceneRetention,
    SceneTuning,
    WorldArrangement,
)
from edge.scene.project import (
    DepthLayeredAnchorProjection,
    FixedFovPerspective,
    NearPlaneViolation,
    hysteresis_delta,
    round_half_even,
    structural_mode,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SHIP_LADDER_KEY = LadderKey(kind="ship", subtype="warship", axis="horizontal", archetype_id="federation")

_SHIP_RUNGS = (
    LadderRung(
        tier_id="rich", index=0, natural=CellBox(0, 0, 40, 10),
        ink_min=CellBox(0, 0, 36, 9), ink_max=CellBox(0, 0, 40, 10),
        ink_count_min=200, ink_count_max=260, render_cost=30,
    ),
    LadderRung(
        tier_id="mid", index=1, natural=CellBox(0, 0, 24, 6),
        ink_min=CellBox(0, 0, 21, 5), ink_max=CellBox(0, 0, 24, 6),
        ink_count_min=90, ink_count_max=120, render_cost=14,
    ),
    LadderRung(
        tier_id="thin", index=2, natural=CellBox(0, 0, 10, 3),
        ink_min=CellBox(0, 0, 8, 2), ink_max=CellBox(0, 0, 10, 3),
        ink_count_min=15, ink_count_max=22, render_cost=4,
    ),
)

_ANCHOR_YIELD = ContinuousYield(
    kind="nebula",
    ink_fraction_min=Fraction(3, 5),
    ink_fraction_max=Fraction(9, 10),
    min_extent=CellBox(0, 0, 6, 3),
    box_classes=(CellBox(0, 0, 60, 24), CellBox(0, 0, 40, 16), CellBox(0, 0, 20, 8)),
    render_cost=(80, 40, 12),
)


class _FakeCatalog:
    version = "test"

    def rungs(self, key: LadderKey) -> tuple[LadderRung, ...]:
        assert key == SHIP_LADDER_KEY
        return _SHIP_RUNGS

    def continuous(self, kind: str) -> ContinuousYield:
        assert kind == "nebula"
        return _ANCHOR_YIELD


CATALOG: ArtGeometryCatalog = _FakeCatalog()


def _region() -> Region:
    return Region(x_min=-100, x_max=100, y_min=-100, y_max=100, z_min=1, z_max=200)


def _ship_object(ident: int) -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("ship", ident),
        parent=None,
        face=Face(shape=FaceShape.RECT, width_su=40, height_su=10),
        scale_class="ship",
        art_mode=ArtMode.LADDER,
        ladder_key=SHIP_LADDER_KEY,
        continuous_kind=None,
        archetype_id=None,
        retention=SceneRetention.NEUTRAL_SHIP,
        hostility_ordinal=5,
        threat_rank=1,
        region=_region(),
        flexible=True,
        occludes=True,
        label="Ship",
        destination=None,
    )


def _anchor_object() -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("discovery", 1),
        parent=None,
        face=Face(shape=FaceShape.ELLIPSE, width_su=60, height_su=30),
        scale_class="anchor",
        art_mode=ArtMode.CONTINUOUS,
        ladder_key=None,
        continuous_kind="nebula",
        archetype_id=None,
        retention=SceneRetention.ANCHOR,
        hostility_ordinal=0,
        threat_rank=0,
        region=_region(),
        flexible=False,
        occludes=True,
        label="Nebula",
        destination=None,
    )


def _tuning(**overrides: object) -> SceneTuning:
    base: dict[str, object] = dict(
        face_extent_by_scale_class={"ship": (40, 10), "anchor": (60, 30)},
        face_extent_by_kind={},
        region_by_scale_class={"ship": _region(), "anchor": _region()},
        target_fraction_by_scale_class={"ship": Fraction(1, 6), "anchor": Fraction(1, 3)},
        ink_ratio_by_scale_class={"ship": Fraction(9, 10), "anchor": Fraction(3, 5)},
        structural_mode_thresholds=((150, 52, "wide"), (100, 40, "standard"), (0, 0, "compact")),
        fixed_fov_num=1,
        fixed_fov_den=2,
        cell_aspect=Fraction(2, 1),
        near_plane_su=1,
        depth_layers=8,
        depth_layer_size_su=4,
        depth_layer_scale=Fraction(4, 5),
        camera_height_fraction_min=Fraction(1, 8),
        camera_height_fraction_max=Fraction(3, 4),
        aim_offsets_su=(0, -1, 1, -2, 2),
        max_camera_candidates=12,
        hysteresis_weight_camera=1,
        hysteresis_weight_position=1,
        hysteresis_weight_admission=4,
        hysteresis_weight_art=1,
        max_passes=64,
        edge_margin=1,
        min_projected_cells_by_scale_class={"ship": (3, 1), "anchor": (4, 3)},
        min_rung_index_from_end_by_scale_class={},
        separation_margin=1,
        min_visible_fraction_by_scale_class={"ship": Fraction(1, 2), "anchor": Fraction(1, 3)},
        cost_budget=1000,
        emergency_ship_ceiling=50,
        max_reposition_candidates=4,
        max_glyph_tries=8,
        glyph_spacing=1,
    )
    base.update(overrides)
    return SceneTuning(**base)  # type: ignore[arg-type]


VIEWPORT = CellBox(col=0, row=0, width=120, height=40)


def _arrangement(anchor_z: int, ship_z: int) -> WorldArrangement:
    anchor = _anchor_object()
    ship = _ship_object(1)
    return WorldArrangement(
        objects=(anchor, ship),
        placements=(
            Placement(key=anchor.key, position=Vec3(0, 0, anchor_z)),
            Placement(key=ship.key, position=Vec3(5, 0, ship_z)),
        ),
    )


# ---------------------------------------------------------------------------
# round_half_even / structural_mode
# ---------------------------------------------------------------------------


def test_round_half_even_ties_to_even() -> None:
    assert round_half_even(Fraction(1, 2)) == 0
    assert round_half_even(Fraction(3, 2)) == 2
    assert round_half_even(Fraction(5, 2)) == 2
    assert round_half_even(Fraction(-1, 2)) == 0


def test_structural_mode_first_match_wins_most_permissive_first() -> None:
    cfg = _tuning()
    assert structural_mode(CellBox(0, 0, 150, 52), cfg) == "wide"
    assert structural_mode(CellBox(0, 0, 149, 52), cfg) == "standard"
    assert structural_mode(CellBox(0, 0, 100, 40), cfg) == "standard"
    assert structural_mode(CellBox(0, 0, 10, 10), cfg) == "compact"


def test_structural_mode_raises_without_a_catch_all_threshold() -> None:
    cfg = _tuning(structural_mode_thresholds=((150, 52, "wide"),))
    try:
        structural_mode(CellBox(0, 0, 10, 10), cfg)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for a viewport no threshold matches")


# ---------------------------------------------------------------------------
# frame() / project() per strategy
# ---------------------------------------------------------------------------

STRATEGIES = (FixedFovPerspective(), DepthLayeredAnchorProjection())


def test_frame_hits_target_fraction_for_a_continuous_anchor() -> None:
    cfg = _tuning()
    arrangement = _arrangement(anchor_z=40, ship_z=20)
    anchor = _anchor_object()
    for strategy in STRATEGIES:
        camera = strategy.frame(arrangement, anchor.key, VIEWPORT, cfg, CATALOG)
        box = strategy.project(camera, anchor, Vec3(0, 0, 40), VIEWPORT)
        target_h = round_half_even(cfg.target_fraction_by_scale_class["anchor"] * VIEWPORT.height)
        ink_h = round_half_even(Fraction(box.height) * _ANCHOR_YIELD.ink_fraction_min)
        # Estimated ink height should land at (or very near, after integer
        # rounding both directions) the target fraction of the viewport --
        # never wildly off, and never computed via a float comparison.
        assert abs(ink_h - target_h) <= 1, (strategy.name, ink_h, target_h)


def test_frame_snaps_a_laddered_anchor_to_a_real_rung() -> None:
    cfg = _tuning()
    ship = _ship_object(1)
    arrangement = WorldArrangement(
        objects=(ship,),
        placements=(Placement(key=ship.key, position=Vec3(0, 0, 30)),),
    )
    natural_heights = {r.natural.height for r in _SHIP_RUNGS}
    for strategy in STRATEGIES:
        camera = strategy.frame(arrangement, ship.key, VIEWPORT, cfg, CATALOG)
        box = strategy.project(camera, ship, Vec3(0, 0, 30), VIEWPORT)
        # The projected box height should equal one of the authored rungs'
        # natural heights (the anchor "never sits between rungs", plan §9.5),
        # allowing +-1 for the final rounding step in project() itself.
        assert any(abs(box.height - h) <= 1 for h in natural_heights), (
            strategy.name, box.height, natural_heights,
        )


def test_project_uses_exact_fraction_arithmetic_and_floor_for_position() -> None:
    cfg = _tuning()
    ship = _ship_object(1)
    camera = Camera(
        position=Vec3(0, 0, 0),
        aim_x_su=0,
        aim_y_su=0,
        fov_num=1,
        fov_den=2,
        near_plane_su=1,
        cell_aspect=Fraction(2, 1),
        depth_layer_size_su=cfg.depth_layer_size_su,
        depth_layer_scale=cfg.depth_layer_scale,
    )
    strategy = FixedFovPerspective()
    box = strategy.project(camera, ship, Vec3(3, 1, 20), VIEWPORT)
    dz = Fraction(20)
    scale = Fraction(VIEWPORT.height * camera.fov_den, camera.fov_num) / dz
    expected_h = round_half_even(Fraction(ship.face.height_su) * scale)
    expected_w = round_half_even(Fraction(ship.face.width_su) * scale * camera.cell_aspect)
    assert box.height == max(1, expected_h)
    assert box.width == max(1, expected_w)


def test_project_rejects_an_object_at_or_behind_near_plane() -> None:
    cfg = _tuning()
    ship = _ship_object(1)
    camera = Camera(
        position=Vec3(0, 0, 0),
        aim_x_su=0,
        aim_y_su=0,
        fov_num=1,
        fov_den=2,
        near_plane_su=5,
        cell_aspect=Fraction(2, 1),
        depth_layer_size_su=cfg.depth_layer_size_su,
        depth_layer_scale=cfg.depth_layer_scale,
    )
    for strategy in STRATEGIES:
        try:
            strategy.project(camera, ship, Vec3(0, 0, 3), VIEWPORT)
        except NearPlaneViolation:
            pass
        else:
            raise AssertionError(f"{strategy.name} accepted an object behind near_plane_su")


# ---------------------------------------------------------------------------
# candidates(): ordering and determinism
# ---------------------------------------------------------------------------


def test_candidates_ordering_is_deterministic_and_bounded() -> None:
    cfg = _tuning()
    ship = _ship_object(1)
    for strategy in STRATEGIES:
        camera = Camera(
            position=Vec3(0, 0, -30),
            aim_x_su=0,
            aim_y_su=0,
            fov_num=cfg.fixed_fov_num,
            fov_den=cfg.fixed_fov_den,
            near_plane_su=cfg.near_plane_su,
            cell_aspect=cfg.cell_aspect,
            depth_layer_size_su=cfg.depth_layer_size_su,
            depth_layer_scale=cfg.depth_layer_scale,
        )
        run_a = list(strategy.candidates(camera, ship, Vec3(0, 0, 0), VIEWPORT, cfg))
        run_b = list(strategy.candidates(camera, ship, Vec3(0, 0, 0), VIEWPORT, cfg))
        assert run_a == run_b, f"{strategy.name} candidate ordering is not deterministic"
        assert len(run_a) <= cfg.max_camera_candidates
        assert run_a, f"{strategy.name} produced no candidates"


def test_candidates_never_exceeds_configured_cap() -> None:
    cfg = _tuning(max_camera_candidates=3)
    ship = _ship_object(1)
    for strategy in STRATEGIES:
        camera = Camera(
            position=Vec3(0, 0, -30),
            aim_x_su=0,
            aim_y_su=0,
            fov_num=cfg.fixed_fov_num,
            fov_den=cfg.fixed_fov_den,
            near_plane_su=cfg.near_plane_su,
            cell_aspect=cfg.cell_aspect,
            depth_layer_size_su=cfg.depth_layer_size_su,
            depth_layer_scale=cfg.depth_layer_scale,
        )
        assert len(list(strategy.candidates(camera, ship, Vec3(0, 0, 0), VIEWPORT, cfg))) <= 3


def test_candidates_at_nonzero_anchor_z_vary_height_and_track_frame() -> None:
    """Regression for the bug where `candidates()` dropped the anchor's
    actual world z-position and silently assumed su z=0 -- for a laddered
    anchor placed far from the origin (like the real port+ships gallery
    case at z~340), that made every swept height floor to the camera's
    near-plane depth and every projected box collapse to `max(1, ...)`
    regardless of the swept target height, and made the nearest-to-current
    candidate land nowhere near `frame()`'s own framing.

    With the fix, `candidates()` receives `anchor_pos` and uses
    `anchor_pos.z - dz_su` (matching `frame()`'s own convention), so swept
    heights produce genuinely different projected box heights, and the
    candidate nearest the framed height roughly reproduces `frame()`'s own
    projected height for the same anchor/viewport.
    """
    cfg = _tuning()
    ship = _ship_object(1)
    anchor_pos = Vec3(0, 0, 340)
    arrangement = WorldArrangement(
        objects=(ship,),
        placements=(Placement(key=ship.key, position=anchor_pos),),
    )
    for strategy in STRATEGIES:
        framed_camera = strategy.frame(arrangement, ship.key, VIEWPORT, cfg, CATALOG)
        framed_box = strategy.project(framed_camera, ship, anchor_pos, VIEWPORT)

        candidates = list(
            strategy.candidates(framed_camera, ship, anchor_pos, VIEWPORT, cfg)
        )
        assert candidates, f"{strategy.name} produced no candidates"

        heights = set()
        for camera in candidates:
            # A candidate camera must still see the anchor as being at its
            # real z -- i.e. anchor_pos.z - camera.position.z is a sane,
            # positive depth, not (pre-fix) a huge or nonsensical one.
            dz = anchor_pos.z - camera.position.z
            assert 0 < dz < anchor_pos.z, (
                strategy.name, dz, camera.position, anchor_pos,
            )
            box = strategy.project(camera, ship, anchor_pos, VIEWPORT)
            heights.add(box.height)

        # The swept heights must produce more than one distinct projected
        # box height -- pre-fix, every candidate's dz was wildly wrong (and
        # roughly constant across the sweep relative to the true anchor
        # depth), collapsing every box to the height floor.
        assert len(heights) > 1, (strategy.name, heights)

        # Among the swept candidates, at least one should land close to
        # frame()'s own projected height for this anchor/viewport -- pre-fix,
        # every candidate was off by hundreds of su of depth, so none did.
        closest_gap = min(
            abs(strategy.project(camera, ship, anchor_pos, VIEWPORT).height - framed_box.height)
            for camera in candidates
        )
        assert closest_gap <= 2, (strategy.name, closest_gap, framed_box.height)


# ---------------------------------------------------------------------------
# Calibration-contract style comparison: both strategies on identical input
# ---------------------------------------------------------------------------


def test_both_strategies_project_the_same_inventory_to_admissible_boxes() -> None:
    cfg = _tuning()
    arrangement = _arrangement(anchor_z=40, ship_z=90)
    anchor = _anchor_object()
    ship = _ship_object(1)
    for strategy in STRATEGIES:
        camera = strategy.frame(arrangement, anchor.key, VIEWPORT, cfg, CATALOG)
        anchor_box = strategy.project(camera, anchor, Vec3(0, 0, 40), VIEWPORT)
        ship_box = strategy.project(camera, ship, Vec3(5, 0, 90), VIEWPORT)
        # Structural comparison only (plan calibration-contract style, not
        # visual approval -- WP-SC04's job): both boxes are non-degenerate
        # integer cell rectangles, and the nearer ship at equal-or-lesser
        # depth than the anchor projects to at least as tall a box only when
        # actually nearer -- here it is farther, so just sanity-check shape.
        assert anchor_box.width >= 1 and anchor_box.height >= 1
        assert ship_box.width >= 1 and ship_box.height >= 1


def test_preliminary_equal_depth_ordering_never_compares_unequal_depths() -> None:
    """Plan §4 invariant 8 / WP-SC03 verification: at equal depth, ordering
    by nominal face area is well defined; this test only asserts the
    catalogue-ink-metadata comparison is meaningful at equal depth, without
    invoking any depth-unequal comparison (that ordering is WP-SC06's).
    """
    anchor = _anchor_object()
    ship = _ship_object(1)
    # Equal-depth comparison uses face.area_su, never rendered ink -- both
    # objects here sit at the same z, so only their nominal face areas may
    # be compared.
    assert anchor.face.area_su != ship.face.area_su
    ordered = sorted((anchor, ship), key=lambda o: (-o.face.area_su, o.key))
    assert ordered[0] is anchor


# ---------------------------------------------------------------------------
# hysteresis_delta()
# ---------------------------------------------------------------------------


def test_hysteresis_delta_is_zero_with_no_previous_plan() -> None:
    cfg = _tuning()
    assert (
        hysteresis_delta(
            anchor_height_now=10,
            anchor_height_prev=None,
            admitted_now=frozenset({SceneKey("ship", 1)}),
            admitted_prev=None,
            position_deltas=(3, 4),
            art_deltas=(1,),
            cfg=cfg,
        )
        == 0
    )


def test_hysteresis_delta_sums_weighted_integer_terms() -> None:
    cfg = _tuning(
        hysteresis_weight_camera=2,
        hysteresis_weight_position=3,
        hysteresis_weight_admission=5,
        hysteresis_weight_art=7,
    )
    now = frozenset({SceneKey("ship", 1), SceneKey("ship", 2)})
    prev = frozenset({SceneKey("ship", 1)})
    delta = hysteresis_delta(
        anchor_height_now=12,
        anchor_height_prev=10,
        admitted_now=now,
        admitted_prev=prev,
        position_deltas=(2, 3),
        art_deltas=(1, 1),
        cfg=cfg,
    )
    expected = 2 * abs(12 - 10) + 3 * (2 + 3) + 5 * len(now ^ prev) + 7 * (1 + 1)
    assert delta == expected
    assert isinstance(delta, int)


# ---------------------------------------------------------------------------
# No sprite art generation during projection
# ---------------------------------------------------------------------------


def test_projection_module_imports_no_sprite_rendering() -> None:
    import ast
    from pathlib import Path

    source = Path(__file__).parents[1] / "edge" / "scene" / "project.py"
    tree = ast.parse(source.read_text(), filename=str(source))
    forbidden = ("edge.art.sprites", "edge.art.sprite_art", "rich", "textual")
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            assert not any(
                name == prefix or name.startswith(prefix + ".") for prefix in forbidden
            ), f"edge/scene/project.py imports {name!r}"
