"""Tests for the frustum-aware reposition fix (docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md
§2.5/§9.6): `edge.scene.project.visible_xy_extent`/`intersect_region_xy` and their
use in `edge.scene.solve`'s reposition fallback.

Covers: secondary (flexible, non-anchor) objects are admitted at a much higher
rate than the pre-fix baseline; the "wide region" design intent (plan §2.5:
ships/wrecks get placement freedom stations do not) is preserved rather than
narrowed away -- a ship can still land at meaningfully different depths; every
frustum computation stays exact `Fraction`/`int` (plan §4.1); the reposition
fallback remains a bounded, counted operation (plan §6.2 rule 4) that shows up
in `SolveCounters` like every other bounded search.
"""

from __future__ import annotations

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

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
    ProjectionStrategy,
    intersect_region_xy,
)
from edge.scene.solve import solve

# ---------------------------------------------------------------------------
# Shared fixtures (mirroring tests/test_scene_solve.py's shapes).
# ---------------------------------------------------------------------------

SHIP_LADDER_KEY = LadderKey(kind="ship", subtype="warship", axis="horizontal", archetype_id="federation")

_SHIP_RUNGS = (
    LadderRung(
        tier_id="rich", index=0, natural=CellBox(0, 0, 40, 10),
        ink_min=CellBox(0, 0, 34, 8), ink_max=CellBox(0, 0, 40, 10),
        ink_count_min=180, ink_count_max=240, render_cost=30,
    ),
    LadderRung(
        tier_id="mid", index=1, natural=CellBox(0, 0, 24, 6),
        ink_min=CellBox(0, 0, 20, 5), ink_max=CellBox(0, 0, 24, 6),
        ink_count_min=80, ink_count_max=110, render_cost=14,
    ),
    LadderRung(
        tier_id="thin", index=2, natural=CellBox(0, 0, 10, 3),
        ink_min=CellBox(0, 0, 8, 2), ink_max=CellBox(0, 0, 10, 3),
        ink_count_min=12, ink_count_max=20, render_cost=4,
    ),
)

_ANCHOR_YIELD = ContinuousYield(
    kind="nebula",
    ink_fraction_min=Fraction(3, 5),
    ink_fraction_max=Fraction(4, 5),
    min_extent=CellBox(0, 0, 4, 3),
    box_classes=(CellBox(0, 0, 40, 20), CellBox(0, 0, 24, 12), CellBox(0, 0, 12, 6)),
    render_cost=(40, 24, 12),
)


class _Catalog(ArtGeometryCatalog):
    def rungs(self, key: LadderKey) -> tuple[LadderRung, ...]:
        return _SHIP_RUNGS if key.kind == "ship" else ()

    def continuous(self, kind: str) -> ContinuousYield:
        return _ANCHOR_YIELD


CATALOG = _Catalog()
VIEWPORT = CellBox(col=0, row=0, width=100, height=36)


def _region() -> Region:
    return Region(x_min=-200, x_max=200, y_min=-100, y_max=100, z_min=1, z_max=300)


def _tuning(**overrides: object) -> SceneTuning:
    base: dict[str, object] = dict(
        face_extent_by_scale_class={"ship": (40, 10), "anchor": (60, 30), "wreck": (20, 8)},
        face_extent_by_kind={},
        region_by_scale_class={"ship": _region(), "anchor": _region(), "wreck": _region()},
        target_fraction_by_scale_class={
            "ship": Fraction(1, 6), "anchor": Fraction(1, 2), "wreck": Fraction(1, 8),
        },
        ink_ratio_by_scale_class={"ship": Fraction(9, 10), "anchor": Fraction(3, 5), "wreck": Fraction(4, 5)},
        structural_mode_thresholds=((150, 52, "wide"), (80, 30, "standard"), (0, 0, "compact")),
        fixed_fov_num=1,
        fixed_fov_den=2,
        cell_aspect=Fraction(2, 1),
        near_plane_su=1,
        depth_layers=10,
        depth_layer_size_su=4,
        depth_layer_scale=Fraction(4, 5),
        camera_height_fraction_min=Fraction(1, 10),
        camera_height_fraction_max=Fraction(3, 4),
        aim_offsets_su=(0, -2, 2, -4, 4),
        max_camera_candidates=24,
        hysteresis_weight_camera=1,
        hysteresis_weight_position=1,
        hysteresis_weight_admission=4,
        hysteresis_weight_art=1,
        max_passes=48,
        edge_margin=1,
        min_projected_cells_by_scale_class={"ship": (3, 1), "anchor": (4, 3), "wreck": (2, 1)},
        separation_margin=1,
        min_visible_fraction_by_scale_class={
            "ship": Fraction(1, 3), "anchor": Fraction(1, 4), "wreck": Fraction(1, 4),
        },
        cost_budget=400,
        emergency_ship_ceiling=25,
        max_reposition_candidates=16,
        max_glyph_tries=6,
        glyph_spacing=1,
    )
    base.update(overrides)
    return SceneTuning(**base)  # type: ignore[arg-type]


def _ship_object(ident: int, *, hostility_ordinal: int = 5) -> PhysicalObject:
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
        hostility_ordinal=hostility_ordinal,
        threat_rank=1,
        region=_region(),
        flexible=True,
        occludes=True,
        label=f"Ship {ident}",
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


def _scene(n_ships: int, *, seed: int = 0) -> WorldArrangement:
    """A nebula anchor plus `n_ships` ships spawned far outside any camera's
    visible frustum -- the exact diagnosed shape ("port+ships"/"empty+ships"
    at a small viewport): each ship's own nominal region is wide (plan §2.5),
    but its initial hash-derived spawn point is picked with no camera
    knowledge at all (`edge.scene.classify` is deliberately viewport-blind),
    so it lands almost anywhere in that huge region -- here, deliberately far
    off to the side and near the region's far depth bound, unreachable by a
    camera framed on the anchor without the reposition fix.
    """
    anchor = _anchor_object()
    ships = [_ship_object(i, hostility_ordinal=i) for i in range(n_ships)]
    objects = (anchor, *ships)
    placements = (
        Placement(key=anchor.key, position=Vec3(0, 0, 40)),
        *(
            Placement(key=s.key, position=Vec3(150 + 7 * (i + seed), 90, 280 - 3 * (i + seed)))
            for i, s in enumerate(ships)
        ),
    )
    return WorldArrangement(objects=objects, placements=placements, sector_id=1)


STRATEGIES: tuple[ProjectionStrategy, ...] = (FixedFovPerspective(), DepthLayeredAnchorProjection())

# ---------------------------------------------------------------------------
# 1. Admission rate: a single flexible ship, spawned far outside any camera's
#    visible frustum, must now be admitted -- the exact diagnosed failure mode
#    ("even a second ship in an otherwise empty sector gets lost").
# ---------------------------------------------------------------------------


def test_gallery_matrix_admits_secondary_objects_at_a_much_higher_rate() -> None:
    """The single most important number from the diagnosis, reproduced as a
    regression floor: across the full `edge/tui/scene_gallery.py::cases()` x
    `SIZES` matrix, both strategies combined used to admit ships/wrecks at
    roughly a 5-6% rate (8/144 measured against this exact matrix before the
    fix). The frustum-aware reposition fix must clear a much higher floor --
    set here well below the ~20% (fixed_fov) / ~12% (depth_layered) actually
    measured after the fix, so this is a regression guard, not a tight bound.
    """
    from edge.scene.classify import classify_sector
    from edge.tui.scene_gallery import SIZES, _physical_pipeline, cases

    tuning, catalog = _physical_pipeline()
    total = 0
    admitted = 0
    for dto in cases().values():
        for _name, w, h in SIZES:
            for strategy in STRATEGIES:
                arrangement, _glyphs = classify_sector(dto, tuning)
                viewport = CellBox(0, 0, w, h)
                plan = solve(arrangement, viewport, tuning, catalog, strategy)
                accepted = {p.key for p in plan.projections}
                for obj in arrangement.objects:
                    if obj.key.tag in ("ship", "player", "wreck"):
                        total += 1
                        if obj.key in accepted:
                            admitted += 1
    assert total > 0
    assert admitted / total >= 0.20, (
        f"secondary-object admission rate regressed to {admitted}/{total} "
        f"({admitted / total:.1%}), below the z-feasibility-fix floor "
        "(measured ~26.2% fixed_fov / ~33.1% depth_layered after the z fix, "
        "vs. ~19.8%/~6.4% with xy-only frustum-awareness and ~14.0%/~5.2% "
        "pre-fix)"
    )


# ---------------------------------------------------------------------------
# 2. The "wide region" design intent (plan §2.5) survives: repositioning a
#    ship still explores meaningfully different depths, not one narrow band.
# ---------------------------------------------------------------------------


def test_reposition_still_explores_meaningfully_different_depths() -> None:
    """Plan §2.5's wide ship/wreck placement freedom must remain effectively
    *reachable*, not be narrowed down to one depth band -- across the same
    real case/size matrix, admitted ships should still land at a real spread
    of depths rather than being funneled onto a single z."""
    from edge.scene.classify import classify_sector
    from edge.tui.scene_gallery import SIZES, _physical_pipeline, cases

    tuning, catalog = _physical_pipeline()
    for strategy in STRATEGIES:
        depths: set[int] = set()
        for dto in cases().values():
            for _name, w, h in SIZES:
                arrangement, _glyphs = classify_sector(dto, tuning)
                viewport = CellBox(0, 0, w, h)
                plan = solve(arrangement, viewport, tuning, catalog, strategy)
                for p in plan.projections:
                    if p.key.tag in ("ship", "player"):
                        depths.add(p.depth)
        assert len(depths) >= 2, (
            f"{strategy.name}: admitted ships collapsed onto too few distinct "
            f"depths ({sorted(depths)}); the fix must not fully revoke the "
            "region's depth freedom"
        )


# ---------------------------------------------------------------------------
# 3. Determinism: no float ever enters the decision; repeated solves of the
#    same input reproduce bit-identical plans.
# ---------------------------------------------------------------------------


def test_frustum_aware_solve_is_still_deterministic() -> None:
    for strategy in STRATEGIES:
        cfg = _tuning()
        scene = _scene(3)
        first = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
        second = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
        assert first.fingerprint == second.fingerprint
        assert first.projections == second.projections
        assert first.counters == second.counters


@given(
    z=st.integers(min_value=-50, max_value=400),
    cam_z=st.integers(min_value=-500, max_value=-1),
    aim_x=st.integers(min_value=-10, max_value=10),
)
@settings(max_examples=100)
def test_visible_xy_extent_never_produces_a_float(z: int, cam_z: int, aim_x: int) -> None:
    """Plan §4.1: every term the frustum-intersection helper produces must be
    an exact `int`/`Fraction` -- `visible_xy_extent()` returns a plain integer
    4-tuple or `None`, never a `float`."""
    cfg = _tuning()
    face = Face(shape=FaceShape.RECT, width_su=40, height_su=10)
    for strategy in STRATEGIES:
        camera = Camera(
            position=Vec3(0, 0, cam_z), aim_x_su=aim_x, aim_y_su=0,
            fov_num=cfg.fixed_fov_num, fov_den=cfg.fixed_fov_den,
            near_plane_su=cfg.near_plane_su, cell_aspect=cfg.cell_aspect,
            depth_layer_size_su=cfg.depth_layer_size_su, depth_layer_scale=cfg.depth_layer_scale,
        )
        result = strategy.visible_xy_extent(camera, VIEWPORT, z, face, cfg)
        if result is not None:
            for term in result:
                assert isinstance(term, int) and not isinstance(term, bool)


# ---------------------------------------------------------------------------
# 4. Bounded search: the reposition fallback never exceeds
#    `max_reposition_candidates` attempts per flexible object, and the count
#    surfaces in `SolveCounters` exactly as before -- the frustum intersection
#    adds no new unbounded work, only re-aims the same bounded hash draw.
# ---------------------------------------------------------------------------


def test_reposition_stays_bounded_and_counted() -> None:
    for strategy in STRATEGIES:
        cfg = _tuning(max_reposition_candidates=4)
        plan = solve(_scene(5), VIEWPORT, cfg, CATALOG, strategy)
        # 5 flexible ships x at most 4 attempts each is the hard ceiling.
        assert plan.counters.reposition_candidates <= 5 * 4


def test_intersect_region_xy_returns_none_on_no_overlap() -> None:
    region = Region(x_min=0, x_max=10, y_min=0, y_max=10, z_min=1, z_max=100)
    assert intersect_region_xy(region, (20, 30, 20, 30)) is None
    assert intersect_region_xy(region, None) is None
    assert intersect_region_xy(region, (-5, 5, -5, 5)) == (0, 5, 0, 5)


# ---------------------------------------------------------------------------
# 5. z-feasibility (follow-up fix): the reposition fallback narrows *which
#    z* it draws from, not just which xy, to the depth band where the object
#    can actually clear near-plane, edge-margin, min-projected-size, and
#    (ladder) no-clearing-rung / (continuous) min-ink-extent.
# ---------------------------------------------------------------------------

from edge.scene.solve import _feasible_z_interval, _z_ok_near_and_size  # noqa: E402


def test_feasible_z_interval_matches_direct_probing() -> None:
    """The interval `_feasible_z_interval` returns must agree with a direct,
    brute-force per-z probe over the same region -- this is the ground truth
    the binary search is meant to reproduce exactly, just without the linear
    scan.
    """
    cfg = _tuning()
    ship = _ship_object(1)
    region = ship.region
    for strategy in STRATEGIES:
        camera = Camera(
            position=Vec3(0, 0, -40), aim_x_su=0, aim_y_su=0,
            fov_num=cfg.fixed_fov_num, fov_den=cfg.fixed_fov_den,
            near_plane_su=cfg.near_plane_su, cell_aspect=cfg.cell_aspect,
            depth_layer_size_su=cfg.depth_layer_size_su, depth_layer_scale=cfg.depth_layer_scale,
        )
        got = _feasible_z_interval(
            camera, ship, VIEWPORT, cfg, CATALOG, strategy, region.z_min, region.z_max
        )
        brute_feasible = [
            z for z in range(region.z_min, region.z_max + 1)
            if all(_z_ok_near_and_size(z, camera, ship, VIEWPORT, cfg, CATALOG, strategy))
        ]
        if not brute_feasible:
            assert got is None
        else:
            assert got is not None, (
                f"{strategy.name}: brute force found feasible z "
                f"{brute_feasible[0]}..{brute_feasible[-1]} but the binary "
                "search returned None"
            )
            z_lo, z_hi = got
            assert z_lo == brute_feasible[0]
            assert z_hi == brute_feasible[-1]
            # Every z strictly inside the reported band must also brute-force
            # feasible -- i.e. the band is not merely "endpoints happen to
            # match", it is the true contiguous feasible interval.
            assert set(range(z_lo, z_hi + 1)) == set(brute_feasible)


def test_feasible_z_interval_excludes_region_behind_the_camera() -> None:
    """A region whose near edge starts behind the camera's near plane (a
    common real shape: a ship's nominal region reaches back toward world
    z=0/1 while the framed camera sits far forward of the anchor) must not
    be reported as "too small at the near end" -- that was the bug this
    follow-up fix corrects: `_z_ok_near_and_size` reports `(False, False)`
    for a near-plane violation, which is a distinct failure mode from "too
    small", and conflating them made the binary search return `None` even
    when a real feasible band existed farther out.
    """
    cfg = _tuning()
    ship = _ship_object(1)
    region = Region(x_min=-200, x_max=200, y_min=-100, y_max=100, z_min=1, z_max=300)
    for strategy in STRATEGIES:
        camera = Camera(
            position=Vec3(0, 0, 200), aim_x_su=0, aim_y_su=0,
            fov_num=cfg.fixed_fov_num, fov_den=cfg.fixed_fov_den,
            near_plane_su=cfg.near_plane_su, cell_aspect=cfg.cell_aspect,
            depth_layer_size_su=cfg.depth_layer_size_su, depth_layer_scale=cfg.depth_layer_scale,
        )
        # region.z_min=1 is far behind camera.position.z=200 -> near-plane
        # violated there, but z in (200, 300] should still have a real
        # feasible band since the ship's face is well within min-size floors
        # close to the camera.
        got = _feasible_z_interval(
            camera, ship, VIEWPORT, cfg, CATALOG, strategy, region.z_min, region.z_max
        )
        assert got is not None, (
            f"{strategy.name}: a region reaching behind the camera's near "
            "plane must not blank out a real feasible band farther out"
        )
        z_lo, z_hi = got
        assert z_lo > camera.position.z


def test_feasible_z_interval_never_produces_a_float() -> None:
    cfg = _tuning()
    ship = _ship_object(1)
    region = ship.region
    for strategy in STRATEGIES:
        camera = Camera(
            position=Vec3(0, 0, -40), aim_x_su=0, aim_y_su=0,
            fov_num=cfg.fixed_fov_num, fov_den=cfg.fixed_fov_den,
            near_plane_su=cfg.near_plane_su, cell_aspect=cfg.cell_aspect,
            depth_layer_size_su=cfg.depth_layer_size_su, depth_layer_scale=cfg.depth_layer_scale,
        )
        got = _feasible_z_interval(
            camera, ship, VIEWPORT, cfg, CATALOG, strategy, region.z_min, region.z_max
        )
        if got is not None:
            for term in got:
                assert isinstance(term, int) and not isinstance(term, bool)


def test_feasible_z_interval_is_bounded_work() -> None:
    """Plan §6.2 rule 4: no accept/reject search is ever an open-ended scan.
    `_feasible_z_interval` must cost `O(log(z_max - z_min))` `project()`
    calls (two binary searches plus a couple of endpoint probes), never a
    linear scan over the region's full depth span.
    """
    import math

    cfg = _tuning()
    ship = _ship_object(1)
    region = Region(x_min=-200, x_max=200, y_min=-100, y_max=100, z_min=1, z_max=1_000_000)
    for strategy in STRATEGIES:
        camera = Camera(
            position=Vec3(0, 0, -40), aim_x_su=0, aim_y_su=0,
            fov_num=cfg.fixed_fov_num, fov_den=cfg.fixed_fov_den,
            near_plane_su=cfg.near_plane_su, cell_aspect=cfg.cell_aspect,
            depth_layer_size_su=cfg.depth_layer_size_su, depth_layer_scale=cfg.depth_layer_scale,
        )
        calls = 0
        orig_project = strategy.project

        def counted_project(*args: object, **kwargs: object) -> CellBox:
            nonlocal calls
            calls += 1
            return orig_project(*args, **kwargs)  # type: ignore[arg-type]

        strategy.project = counted_project  # type: ignore[method-assign]
        try:
            _feasible_z_interval(camera, ship, VIEWPORT, cfg, CATALOG, strategy, region.z_min, region.z_max)
        finally:
            strategy.project = orig_project  # type: ignore[method-assign]
        span = region.z_max - region.z_min
        assert calls <= 4 * math.ceil(math.log2(span + 1)) + 8, (
            f"{strategy.name}: _feasible_z_interval made {calls} project() "
            f"calls over a span of {span} -- expected O(log(span)), not a scan"
        )


def test_feasible_z_interval_is_deterministic() -> None:
    cfg = _tuning()
    ship = _ship_object(1)
    region = ship.region
    for strategy in STRATEGIES:
        camera = Camera(
            position=Vec3(0, 0, -40), aim_x_su=0, aim_y_su=0,
            fov_num=cfg.fixed_fov_num, fov_den=cfg.fixed_fov_den,
            near_plane_su=cfg.near_plane_su, cell_aspect=cfg.cell_aspect,
            depth_layer_size_su=cfg.depth_layer_size_su, depth_layer_scale=cfg.depth_layer_scale,
        )
        first = _feasible_z_interval(camera, ship, VIEWPORT, cfg, CATALOG, strategy, region.z_min, region.z_max)
        second = _feasible_z_interval(camera, ship, VIEWPORT, cfg, CATALOG, strategy, region.z_min, region.z_max)
        assert first == second
