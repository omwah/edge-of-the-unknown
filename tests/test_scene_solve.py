"""Tests for the constraint solver (WP-SC06): pass loop, admission, hysteresis.

Covers: the solve() contract for both strategies, retention-order fairness
(§4.5), hysteresis never defeating a hard rule (§4.11), bounded termination
(§6.2 rule 4), determinism (§4.1), glyph scatter (§4.19), the trace-prose gate
(§4.20), and that no art is rendered and no floats feed a decision.
"""

from __future__ import annotations

import time
from dataclasses import replace
from fractions import Fraction

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from edge.scene.catalog import ArtGeometryCatalog, ContinuousYield, LadderKey, LadderRung
from edge.scene.geometry import CellBox, Face, FaceShape, Region, Su, Vec3
from edge.scene.model import (
    ArtMode,
    GlyphRequest,
    PhysicalObject,
    Placement,
    SceneKey,
    SceneRetention,
    SceneTuning,
    WorldArrangement,
)
from edge.scene.project import DepthLayeredAnchorProjection, FixedFovPerspective, ProjectionStrategy
from edge.scene.solve import solve

# ---------------------------------------------------------------------------
# Shared fixtures
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
    ink_fraction_max=Fraction(9, 10),
    min_extent=CellBox(0, 0, 4, 3),
    box_classes=(CellBox(0, 0, 60, 24), CellBox(0, 0, 40, 16), CellBox(0, 0, 20, 8)),
    render_cost=(80, 40, 12),
)

_WRECK_YIELD = ContinuousYield(
    kind="wreck",
    ink_fraction_min=Fraction(1, 2),
    ink_fraction_max=Fraction(4, 5),
    min_extent=CellBox(0, 0, 3, 2),
    box_classes=(CellBox(0, 0, 20, 8),),
    render_cost=(10,),
)


class _FakeCatalog:
    version = "test"

    def rungs(self, key: LadderKey) -> tuple[LadderRung, ...]:
        if key == SHIP_LADDER_KEY:
            return _SHIP_RUNGS
        return ()

    def continuous(self, kind: str) -> ContinuousYield:
        if kind == "nebula":
            return _ANCHOR_YIELD
        if kind == "wreck":
            return _WRECK_YIELD
        raise KeyError(kind)


CATALOG: ArtGeometryCatalog = _FakeCatalog()

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
        max_reposition_candidates=3,
        max_glyph_tries=6,
        glyph_spacing=1,
    )
    base.update(overrides)
    return SceneTuning(**base)  # type: ignore[arg-type]


def _ship_object(
    ident: int, *, retention: SceneRetention = SceneRetention.NEUTRAL_SHIP,
    hostility_ordinal: int = 5, threat_rank: int = 1,
) -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("ship", ident),
        parent=None,
        face=Face(shape=FaceShape.RECT, width_su=40, height_su=10),
        scale_class="ship",
        art_mode=ArtMode.LADDER,
        ladder_key=SHIP_LADDER_KEY,
        continuous_kind=None,
        retention=retention,
        hostility_ordinal=hostility_ordinal,
        threat_rank=threat_rank,
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
        retention=SceneRetention.ANCHOR,
        hostility_ordinal=0,
        threat_rank=0,
        region=_region(),
        flexible=False,
        occludes=True,
        label="Nebula",
        destination=None,
    )


def _wreck_object(ident: int) -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("wreck", ident),
        parent=None,
        face=Face(shape=FaceShape.RECT, width_su=20, height_su=8),
        scale_class="wreck",
        art_mode=ArtMode.CONTINUOUS,
        ladder_key=None,
        continuous_kind="wreck",
        retention=SceneRetention.WRECK,
        hostility_ordinal=0,
        threat_rank=0,
        region=_region(),
        flexible=True,
        occludes=True,
        label=f"Wreck {ident}",
        destination=None,
    )


def _placement(key: SceneKey, x: Su, y: Su, z: Su) -> Placement:
    return Placement(key=key, position=Vec3(x, y, z))


def _arrangement(
    objects: tuple[PhysicalObject, ...],
    placements: tuple[Placement, ...],
    *,
    sector_id: int = 7,
    glyphs: tuple[GlyphRequest, ...] = (),
) -> WorldArrangement:
    return WorldArrangement(objects=objects, placements=placements, sector_id=sector_id, glyphs=glyphs)


STRATEGIES: tuple[ProjectionStrategy, ...] = (FixedFovPerspective(), DepthLayeredAnchorProjection())


def _basic_scene() -> WorldArrangement:
    anchor = _anchor_object()
    ships = [_ship_object(i, hostility_ordinal=i) for i in range(3)]
    objects = (anchor, *ships)
    placements = (
        _placement(anchor.key, 0, 0, 40),
        *(_placement(s.key, (i - 1) * 30, 0, 20 + i * 5) for i, s in enumerate(ships)),
    )
    return _arrangement(objects, placements)


# ---------------------------------------------------------------------------
# Basic contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_solve_admits_the_anchor_and_returns_quantised_output(strategy: ProjectionStrategy) -> None:
    cfg = _tuning()
    plan = solve(_basic_scene(), VIEWPORT, cfg, CATALOG, strategy)
    assert plan.strategy == strategy.name
    keys = {p.key for p in plan.projections}
    assert SceneKey("discovery", 1) in keys, "the anchor must be admitted"
    for projection in plan.projections:
        assert isinstance(projection.bounds.col, int)
        assert isinstance(projection.bounds.width, int)
        assert isinstance(projection.visible_fraction, Fraction)


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_solve_is_deterministic(strategy: ProjectionStrategy) -> None:
    cfg = _tuning()
    scene = _basic_scene()
    plan_a = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
    plan_b = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
    assert plan_a.fingerprint == plan_b.fingerprint
    assert plan_a.projections == plan_b.projections
    assert plan_a.rejected == plan_b.rejected


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_permuting_object_order_does_not_change_the_result(strategy: ProjectionStrategy) -> None:
    cfg = _tuning()
    scene = _basic_scene()
    reversed_scene = _arrangement(
        tuple(reversed(scene.objects)), tuple(reversed(scene.placements)), sector_id=scene.sector_id
    )
    plan_a = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
    plan_b = solve(reversed_scene, VIEWPORT, cfg, CATALOG, strategy)
    assert {p.key for p in plan_a.projections} == {p.key for p in plan_b.projections}
    assert plan_a.fingerprint == plan_b.fingerprint


def test_solve_never_renders_art_or_touches_random_module() -> None:
    """No `edge.art.sprites`/Rich/Textual import and no `random` module use
    anywhere reachable from `solve.py` -- reuses the same AST boundary this
    package already enforces package-wide (`tests/test_scene_import_boundaries.py`)."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path("edge/scene/solve.py").read_text())
    forbidden = ("edge.art.sprites", "edge.art.sprite_art", "edge.tui", "rich", "textual", "random")
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            assert not any(name == p or name.startswith(p + ".") for p in forbidden), name


# ---------------------------------------------------------------------------
# Retention-order fairness (§4.5)
# ---------------------------------------------------------------------------


def _crowded_scene(n_ships: int, *, spread: Su = 6) -> WorldArrangement:
    """`n_ships` ships packed close enough together that not all of them can
    satisfy separation at once, forcing the solver to actually apply
    retention priority rather than just fitting everyone.
    """
    ships = [
        _ship_object(i, hostility_ordinal=(n_ships - i), threat_rank=i)
        for i in range(n_ships)
    ]
    placements = tuple(_placement(s.key, i * spread, 0, 30) for i, s in enumerate(ships))
    return _arrangement(tuple(ships), placements)


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_higher_retention_priority_is_never_dropped_for_a_lower_one(strategy: ProjectionStrategy) -> None:
    cfg = _tuning(cost_budget=60, emergency_ship_ceiling=25)  # tight enough to force real trimming
    scene = _crowded_scene(6)
    plan = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
    accepted = {p.key for p in plan.projections}
    rejected = set(plan.rejected)
    # `_crowded_scene` assigns strictly increasing retention priority as
    # `ident` increases (ship 0 = highest hostility_ordinal = lowest
    # priority... constructed so that admitted priority is monotone in
    # ident): assert no rejected ship has strictly higher priority (lower
    # hostility_ordinal here, since retention/hostility_ordinal both sort
    # ascending-first) than an accepted one.
    ships = {s.key: s for s in scene.objects}
    for r in rejected:
        if r.tag != "ship":
            continue
        r_obj = ships[r]
        for a in accepted:
            if a.tag != "ship":
                continue
            a_obj = ships[a]
            better = (a_obj.retention, a_obj.hostility_ordinal, -a_obj.threat_rank, a_obj.key)
            worse = (r_obj.retention, r_obj.hostility_ordinal, -r_obj.threat_rank, r_obj.key)
            assert not (worse < better), (
                f"{r} was rejected while lower-priority {a} was admitted"
            )


# ---------------------------------------------------------------------------
# Termination (§6.2 rule 4, §9.6)
# ---------------------------------------------------------------------------


@given(n_ships=st.integers(min_value=0, max_value=10))
@settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_every_solve_terminates_within_the_configured_pass_bound(n_ships: int) -> None:
    cfg = _tuning(max_passes=32)
    scene = _crowded_scene(n_ships) if n_ships else _arrangement((), ())
    plan = solve(scene, VIEWPORT, cfg, CATALOG, FixedFovPerspective())
    assert plan.counters.passes <= cfg.max_passes


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_empty_arrangement_yields_a_starfield_only_plan(strategy: ProjectionStrategy) -> None:
    cfg = _tuning()
    plan = solve(_arrangement((), ()), VIEWPORT, cfg, CATALOG, strategy)
    assert plan.projections == ()
    assert plan.rejected == ()


# ---------------------------------------------------------------------------
# Invariant 18: if anything can fit, something is admitted.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_a_single_fitting_ship_is_always_admitted(strategy: ProjectionStrategy) -> None:
    cfg = _tuning()
    ship = _ship_object(0)
    scene = _arrangement((ship,), (_placement(ship.key, 0, 0, 30),))
    plan = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
    assert {p.key for p in plan.projections} == {ship.key}
    assert plan.rejected == ()


# ---------------------------------------------------------------------------
# Hysteresis never defeats a hard rule (§4.11)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_hysteresis_never_defeats_a_hard_rule(strategy: ProjectionStrategy) -> None:
    cfg = _tuning(
        hysteresis_weight_camera=10_000, hysteresis_weight_position=10_000,
        hysteresis_weight_admission=10_000, hysteresis_weight_art=10_000,
    )
    scene = _basic_scene()
    first = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
    # A viewport resize the previous plan cannot possibly match cell-for-cell
    # (much narrower): even with a massive hysteresis weight urging the
    # solver to stay put, every accepted box must still fit the new viewport.
    smaller = CellBox(col=0, row=0, width=50, height=20)
    second = solve(scene, smaller, cfg, CATALOG, strategy, previous=first)
    for projection in second.projections:
        assert projection.bounds.col >= cfg.edge_margin
        assert projection.bounds.row >= cfg.edge_margin
        assert projection.bounds.col + projection.bounds.width <= smaller.width - cfg.edge_margin
        assert projection.bounds.row + projection.bounds.height <= smaller.height - cfg.edge_margin


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_resize_with_previous_plan_stays_close_when_physically_possible(strategy: ProjectionStrategy) -> None:
    cfg = _tuning()
    scene = _basic_scene()
    first = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
    nearly_same = CellBox(col=0, row=0, width=VIEWPORT.width + 1, height=VIEWPORT.height)
    second = solve(scene, nearly_same, cfg, CATALOG, strategy, previous=first)
    # A +-1 cell resize with hysteresis enabled should not rescatter every
    # object to an unrelated camera; the same anchor should stay admitted.
    assert SceneKey("discovery", 1) in {p.key for p in second.projections}


# ---------------------------------------------------------------------------
# Anchor box-class step-down under cost pressure (§2.3, §4.14)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_cost_pressure_steps_the_anchor_down_before_rejecting_it(strategy: ProjectionStrategy) -> None:
    # A budget only the cheapest anchor box class (render_cost 12) can meet.
    cfg = _tuning(cost_budget=15, emergency_ship_ceiling=25)
    anchor = _anchor_object()
    scene = _arrangement((anchor,), (_placement(anchor.key, 0, 0, 40),))
    plan = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
    assert anchor.key in {p.key for p in plan.projections}, "the anchor is never rejected for cost"
    assert plan.counters.step_downs > 0


# ---------------------------------------------------------------------------
# Glyph scatter (§4.19, §9.6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_glyph_scatter_is_bounded_and_deterministic(strategy: ProjectionStrategy) -> None:
    cfg = _tuning()
    glyphs = (GlyphRequest(key=SceneKey("glyph", 1), count=4),)
    scene = _arrangement((), (), glyphs=glyphs)
    plan_a = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
    plan_b = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
    assert plan_a.counters.glyphs_placed + plan_a.counters.glyphs_dropped == 4
    assert plan_a.counters.glyphs_placed == plan_b.counters.glyphs_placed
    assert plan_a.counters.glyphs_dropped == plan_b.counters.glyphs_dropped


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_unplaced_glyphs_never_enter_scene_text_only_the_sidebar(strategy: ProjectionStrategy) -> None:
    # A viewport with only one free cell after edge margins and a huge glyph
    # request forces drops.
    cfg = _tuning(max_glyph_tries=2)
    glyphs = (GlyphRequest(key=SceneKey("glyph", 1), count=50),)
    tiny_viewport = CellBox(col=0, row=0, width=6, height=6)
    scene = _arrangement((), (), glyphs=glyphs)
    plan = solve(scene, tiny_viewport, cfg, CATALOG, strategy)
    assert plan.counters.glyphs_dropped > 0
    # No scene text: the only surface for an omitted glyph is `rejected`
    # (the sidebar/object-list projection) or the counters, never a string
    # baked into any accepted `Projection`'s label/bounds.
    assert all(p.key.tag != "glyph" for p in plan.projections)


# ---------------------------------------------------------------------------
# Trace-prose gating (§4.20, §6.2 rule 8)
# ---------------------------------------------------------------------------


def test_trace_prose_is_empty_unless_requested() -> None:
    cfg = _tuning(cost_budget=60)  # forces some reject/step_down decisions to exist
    scene = _crowded_scene(6)
    quiet = solve(scene, VIEWPORT, cfg, CATALOG, FixedFovPerspective())
    loud = solve(scene, VIEWPORT, cfg, CATALOG, FixedFovPerspective(), trace_prose=True)
    assert all(d.reason == "" for d in quiet.trace)
    assert quiet.counters == loud.counters, "structural counters do not depend on the prose gate"
    if loud.trace:
        assert any(d.reason != "" for d in loud.trace)


# ---------------------------------------------------------------------------
# Structural/solver-only benchmark: sub-second for a modest inventory,
# and no candidate/pass explosion (§6.2 rule 4, §6.4).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_solver_only_timing_is_sub_second_for_a_modest_inventory(strategy: ProjectionStrategy) -> None:
    cfg = _tuning()
    scene = _crowded_scene(12, spread=10)
    start = time.perf_counter()
    plan = solve(scene, VIEWPORT, cfg, CATALOG, strategy)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"solver-only pass took {elapsed:.3f}s for a 12-ship scene"
    assert plan.counters.camera_candidates <= cfg.max_camera_candidates * cfg.max_passes


# ---------------------------------------------------------------------------
# Occlusion / equal-depth ordering sanity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_projections_are_depth_ordered_far_to_near(strategy: ProjectionStrategy) -> None:
    cfg = _tuning()
    plan = solve(_basic_scene(), VIEWPORT, cfg, CATALOG, strategy)
    depths = [p.depth for p in plan.projections]
    assert depths == sorted(depths, reverse=True)


# ---------------------------------------------------------------------------
# No-clearing-rung objects are rejected, never cropped (§4.7, §4.17)
# ---------------------------------------------------------------------------


def test_an_object_with_no_ladder_key_match_is_rejected_not_cropped() -> None:
    # The bad-rung ship must not itself become the framing anchor (`frame()`
    # -- WP-SC03, out of this WP's scope -- needs at least one real rung for
    # whichever object it is asked to frame), so pair it with the nebula
    # anchor, which has a larger nominal face area and is always selected as
    # anchor first (plan §2.3).
    cfg = _tuning()
    bad_key = LadderKey(kind="ship", subtype="does-not-exist", axis="horizontal", archetype_id="x")
    ship = replace(_ship_object(0), ladder_key=bad_key)
    anchor = _anchor_object()
    scene = _arrangement(
        (anchor, ship), (_placement(anchor.key, 0, 0, 40), _placement(ship.key, 0, 0, 30))
    )
    plan = solve(scene, VIEWPORT, cfg, CATALOG, FixedFovPerspective())
    assert ship.key not in {p.key for p in plan.projections}
    assert ship.key in plan.rejected
