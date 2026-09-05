"""Joint secondary-object placement (the post-WP-SC09 solver redesign).

`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` -> "Joint secondary-object
placement (post-WP-SC09 redesign)" is the reference; plan §4 is the acceptance
contract. These tests exercise the redesign against the *real*
config-driven `SceneTuning`/`ArtGeometryCatalog` pair a live game builds, not
invented calibration numbers, because the failure the redesign fixes only
showed up at the shipped WP-SC05 values.

Covered here:

* admission actually works for ordinary inventories (the headline metric);
* every admitted object still clears every hard rule -- rejections were not
  traded for incorrect admissions;
* determinism, including DTO container permutation and repeat solves;
* retention priority is never violated by the greedy joint order (§4.5/§4.6);
* the search stays bounded and counted under 20/50-ship stress (§6.2 rule 4);
* plan §2.5's "wide region" intent survives: ships still reach genuinely
  varied depths and screen positions across sectors and viewports.
"""

from __future__ import annotations

import random
import time
from fractions import Fraction

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from edge.art.geometry_catalog import load_geometry_catalog
from edge.art.scene_tuning import build_continuous_yields, build_scene_tuning
from edge.config import load_config
from edge.core.dto import (
    SectorDiscovery,
    SectorDTO,
    SectorPlanetDTO,
    SectorPortDTO,
    SectorShipDTO,
    SectorStarbaseDTO,
)
from edge.scene.classify import classify_sector
from edge.scene.geometry import CellBox
from edge.scene.model import ArtMode, PhysicalObject, ScenePlan, SceneTuning
from edge.scene.project import DepthLayeredAnchorProjection, FixedFovPerspective, ProjectionStrategy
from edge.scene.solve import (
    _attempt,
    _contained,
    _ink_box,
    _inflate,
    _overlap_area,
    _rect_gap,
    _select_rung,
    solve,
)

_CFG = load_config("config/default.yaml")
_PM = _CFG.scene.physical_model
TUNING: SceneTuning = build_scene_tuning(_PM)
CATALOG = load_geometry_catalog(build_continuous_yields(_PM))

STRATEGIES: tuple[ProjectionStrategy, ...] = (FixedFovPerspective(), DepthLayeredAnchorProjection())

# The scene canvases plan §6.1/§6.3 already measure against.
SIZES: tuple[tuple[int, int], ...] = ((67, 30), (87, 36), (120, 44), (150, 52))

# Every ship/port/starbase subtype in the shipped catalogue carries this
# archetype, so a fixture using it exercises real authored rungs.
_ARCHETYPE = "humanoid_diplomat"


def _ship(name: str, role: str, cid: int) -> SectorShipDTO:
    return SectorShipDTO(name=name, role=role, archetype_id=_ARCHETYPE, contact_id=cid)


def _sector(sid: int, **kw: object) -> SectorDTO:
    base: dict[str, object] = dict(
        region="Test", sector_id=sid, display_id=sid, band="Frontier",
        flavor="a test arrangement", beacon=None,
    )
    base.update(kw)
    return SectorDTO(**base)  # type: ignore[arg-type]


_TRAFFIC = [_ship("Vesk Trader", "transport", 2), _ship("Kalt Corvette", "warship", 5)]
_PLANET = [SectorPlanetDTO(planet_id=9101, name="New Hesse", ptype="terrestrial_warm")]


def _port(name: str = "Verge Depot", *, stardock: bool = False) -> SectorPortDTO:
    return SectorPortDTO(
        port_id=64, name=name, klass="Stardock" if stardock else "Class 1 (SBB)",
        is_stardock=stardock, archetype_id=_ARCHETYPE,
    )


def _base(name: str = "Orbital Platform", planet_id: int | None = None) -> SectorStarbaseDTO:
    return SectorStarbaseDTO(
        starbase_id=4, name=name, owner="yours", operational=True,
        planet_id=planet_id, condition="open", archetype_id=_ARCHETYPE,
    )


def _find(kind: str, name: str) -> SectorDiscovery:
    return SectorDiscovery(
        discovery_id=22, label=name, kind=kind, rarity="Rare", salvageable=True,
        name=name, collected=True,
    )


def matrix() -> dict[str, SectorDTO]:
    """A composition matrix mirroring the dev gallery's, kept here so the
    admission metric is asserted in CI rather than only in a dev tool."""
    return {
        "empty+ships": _sector(101, ships=_TRAFFIC),
        "port+ships": _sector(102, ports=[_port("Port Kalso")], ships=_TRAFFIC),
        "starbase+ships": _sector(104, starbases=[_base()], ships=_TRAFFIC),
        "planet+ships": _sector(105, planets=_PLANET, ships=_TRAFFIC),
        "planet+port+ships": _sector(
            106, planets=_PLANET, ports=[_port("Port Kalso")], ships=_TRAFFIC
        ),
        "planet+starbase+ships": _sector(
            108, planets=_PLANET, starbases=[_base(planet_id=9101)], ships=_TRAFFIC
        ),
        "wormhole+port+ships": _sector(
            109, discoveries=[_find("wormhole", "the Hollow Gate")],
            ports=[_port("Gate Depot")], ships=_TRAFFIC,
        ),
        "nebula+port+ships": _sector(
            111, discoveries=[_find("nebula", "the Rose Veil")],
            ports=[_port("Veil Depot")], ships=_TRAFFIC,
        ),
        "wreck+ships": _sector(
            112, discoveries=[_find("wreck", "Vesk Marauder VII")], ships=_TRAFFIC
        ),
        "belt+port+ships": _sector(
            114,
            planets=[SectorPlanetDTO(planet_id=531, name="Cinder Drift", ptype="asteroid_belt")],
            ports=[_port("Drift Depot")], ships=_TRAFFIC,
        ),
    }


def _solved(sector: SectorDTO, strategy: ProjectionStrategy, w: int, h: int) -> tuple[ScenePlan, list[PhysicalObject]]:
    arrangement, _glyphs = classify_sector(sector, TUNING)
    plan = solve(arrangement, CellBox(0, 0, w, h), TUNING, CATALOG, strategy)
    objects = [o for o in arrangement.objects if o.art_mode is not ArtMode.GLYPH]
    return plan, objects


def _secondary(objects: list[PhysicalObject]) -> list[PhysicalObject]:
    """Non-anchor flexible objects -- ships, wrecks, and orbital stations: the
    population the pre-redesign solver rejected almost entirely."""
    if not objects:
        return []
    anchor = max(objects, key=lambda o: (o.face.area_su, o.key))
    return [o for o in objects if o.flexible and o.key != anchor.key]


# ---------------------------------------------------------------------------
# The headline metric: secondary objects actually get admitted.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_secondary_objects_are_admitted_across_the_matrix(strategy: ProjectionStrategy) -> None:
    """Before the joint-placement redesign this rate was 26.2% / 33.1% -- a
    port with two ships lost both ships, every time -- against roughly 93% for
    the legacy `_SceneComposer` on the same inventories.

    The minimum-richness floor (`min_rung_index_from_end_by_scale_class`,
    `orbital: 1`) legitimately lowers this: an orbital object that can only
    ever reach its ladder's worst rung is now rejected outright rather than
    shown degraded, and -- since a rejected/repositioned orbital changes
    which camera the joint solve scores best -- ship/wreck admission shifts
    too even though no rung floor applies to them. Measured on this module's
    matrix after the fix: ~77% (`fixed_fov_perspective`) / ~84%
    (`depth_layered_anchor`), down from ~95%/~99%
    (`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md`'s minimum-richness section
    has the full real-gallery-matrix before/after). The floor below is
    dropped to stay well under that, so ordinary calibration drift does not
    make it flaky, while still failing loudly if independent, camera-blind
    placement ever comes back.
    """
    total = admitted = 0
    for sector in matrix().values():
        for w, h in SIZES:
            plan, objects = _solved(sector, strategy, w, h)
            accepted = {p.key for p in plan.projections if p.accepted}
            for obj in _secondary(objects):
                total += 1
                admitted += obj.key in accepted
    assert total > 0
    rate = Fraction(admitted, total)
    assert rate >= Fraction(70, 100), f"{admitted}/{total} secondary objects admitted"


# ---------------------------------------------------------------------------
# ...and they are admitted *correctly*: every hard rule still holds.
# ---------------------------------------------------------------------------


def _assert_hard_rules(plan: ScenePlan, objects: list[PhysicalObject], viewport: CellBox) -> None:
    by_key = {o.key: o for o in objects}
    accepted = [p for p in plan.projections if p.accepted]
    ink_max: dict[object, CellBox] = {}
    for proj in accepted:
        obj = by_key[proj.key]
        # Near plane (plan §9.2) and edge margin / containment (attempt rule 1).
        assert proj.depth > plan.camera.position.z
        assert proj.depth >= plan.camera.near_plane_su
        assert _contained(proj.bounds, viewport, TUNING.edge_margin), proj
        # Minimum projected size (attempt rule 2).
        min_w, min_h = TUNING.min_projected_cells_by_scale_class[obj.scale_class]
        assert proj.bounds.width >= min_w and proj.bounds.height >= min_h
        # A complete authored rung, never `fit_box`'s crop (attempt rule 3, §4.7).
        if obj.art_mode is ArtMode.LADDER:
            assert proj.rung is not None
            assert proj.rung == _select_rung(CATALOG, obj, proj.bounds, TUNING)
            assert proj.rung.natural.width <= proj.bounds.width
            assert proj.rung.natural.height <= proj.bounds.height
        else:
            assert obj.continuous_kind is not None
            floor = CATALOG.continuous(obj.continuous_kind).min_extent
            assert proj.ink_est.width >= floor.width and proj.ink_est.height >= floor.height
        ink_max[proj.key] = _inflate(
            _ink_box(obj, proj.bounds, proj.rung, CATALOG, side="max"), TUNING.separation_margin
        )
    for i, a in enumerate(accepted):
        if not by_key[a.key].occludes:
            continue
        for b in accepted[i + 1 :]:
            if not by_key[b.key].occludes:
                continue
            # Separation (attempt rule 4).
            assert _rect_gap(ink_max[a.key], ink_max[b.key]) >= 0, (a.key, b.key)
            # Occlusion: the farther object stays above its visibility floor
            # (attempt rule 5). Separation already forbids ink overlap between
            # occluding pairs, so this is a belt-and-braces re-derivation from
            # the published plan rather than a restatement of the same check.
            if a.depth == b.depth:
                continue
            near, far = (a, b) if a.depth < b.depth else (b, a)
            area = far.ink_est.width * far.ink_est.height
            if area <= 0:
                continue
            visible = Fraction(area - _overlap_area(ink_max[near.key], far.ink_est), area)
            assert visible >= TUNING.min_visible_fraction_by_scale_class[by_key[far.key].scale_class]


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_every_admitted_object_clears_every_hard_rule(strategy: ProjectionStrategy) -> None:
    for sector in matrix().values():
        for w, h in SIZES:
            plan, objects = _solved(sector, strategy, w, h)
            _assert_hard_rules(plan, objects, CellBox(0, 0, w, h))


# ---------------------------------------------------------------------------
# Determinism (§4.1): placement is now camera-dependent, so it is newly
# capable of nondeterminism -- assert it is not.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_repeat_solves_are_byte_identical(strategy: ProjectionStrategy) -> None:
    for sector in matrix().values():
        for w, h in SIZES:
            first, _ = _solved(sector, strategy, w, h)
            second, _ = _solved(sector, strategy, w, h)
            assert first.fingerprint == second.fingerprint
            assert [(p.key, p.bounds, p.depth, p.rung) for p in first.projections] == [
                (p.key, p.bounds, p.depth, p.rung) for p in second.projections
            ]
            assert first.rejected == second.rejected


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_permuting_dto_containers_does_not_change_the_plan(strategy: ProjectionStrategy) -> None:
    rng = random.Random(20260904)
    sector = matrix()["planet+port+ships"]
    baseline, _ = _solved(sector, strategy, 120, 44)
    for _ in range(4):
        shuffled = list(sector.ships)
        rng.shuffle(shuffled)
        permuted = _sector(
            sector.sector_id, planets=list(sector.planets), ports=list(sector.ports),
            ships=shuffled, starbases=list(sector.starbases),
            discoveries=list(sector.discoveries),
        )
        plan, _ = _solved(permuted, strategy, 120, 44)
        assert plan.fingerprint == baseline.fingerprint


@settings(deadline=None, max_examples=20, suppress_health_check=[HealthCheck.too_slow])
@given(
    width=st.integers(min_value=40, max_value=150),
    height=st.integers(min_value=20, max_value=52),
    ships=st.integers(min_value=0, max_value=5),
)
def test_solve_is_deterministic_for_arbitrary_viewports(width: int, height: int, ships: int) -> None:
    sector = _sector(
        777, planets=_PLANET,
        ships=[_ship(f"Hull {i}", "warship", i) for i in range(ships)],
    )
    a, _ = _solved(sector, FixedFovPerspective(), width, height)
    b, _ = _solved(sector, FixedFovPerspective(), width, height)
    assert a.fingerprint == b.fingerprint


# ---------------------------------------------------------------------------
# Retention priority (§4.5/§4.6) under joint placement.
# ---------------------------------------------------------------------------


def _admissibility_class(obj: PhysicalObject) -> tuple[object, ...]:
    """What plan §4.5's "of the same admissibility class" means concretely:
    two objects are interchangeable when nothing but their retention key
    distinguishes what the solver can do with them.

    Objects that differ here are *not* comparable under §4.5 -- a belt anchor
    that is too wide for a 67-column frame, or a station on a different
    ladder, is refused by geometry, not by consideration order.
    """
    return (
        obj.scale_class, obj.art_mode, obj.ladder_key, obj.continuous_kind,
        obj.face, obj.region, obj.flexible, obj.occludes, obj.parent,
    )


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_greedy_placement_never_inverts_retention(strategy: ProjectionStrategy) -> None:
    """Placement runs in `(retention, hostility_ordinal, -threat_rank, key)`
    order, so within one admissibility class a rejected object can never be
    outranked by an admitted one (plan §4.5/§4.6).
    """
    for sector in matrix().values():
        for w, h in SIZES:
            plan, objects = _solved(sector, strategy, w, h)
            accepted = {p.key for p in plan.projections if p.accepted}
            for obj in objects:
                if obj.key in accepted:
                    continue
                peers = [
                    o for o in objects
                    if o.key in accepted and _admissibility_class(o) == _admissibility_class(obj)
                ]
                for peer in peers:
                    assert (obj.retention, obj.hostility_ordinal, -obj.threat_rank, obj.key) > (
                        peer.retention, peer.hostility_ordinal, -peer.threat_rank, peer.key
                    ), (
                        f"{obj.key} (tier {obj.retention}) rejected while the "
                        f"lower-priority, interchangeable {peer.key} "
                        f"(tier {peer.retention}) was admitted"
                    )


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_a_crowd_of_ships_is_thinned_from_the_friendly_end(strategy: ProjectionStrategy) -> None:
    """Overload a small viewport with more ships than can fit and check the
    survivors are the more hostile ones (§4.6), not whichever the greedy scan
    happened to reach first."""
    ships = [_ship(f"Hull {i}", "warship", i) for i in range(12)]
    for index, ship in enumerate(ships):
        ships[index] = SectorShipDTO(
            name=ship.name, role=ship.role, archetype_id=_ARCHETYPE, contact_id=ship.contact_id,
            retention_class="hostile" if index < 4 else "friendly",
            hostility_ordinal=index,
        )
    sector = _sector(303, planets=_PLANET, ships=ships)
    plan, objects = _solved(sector, strategy, 67, 30)
    accepted = {p.key for p in plan.projections if p.accepted}
    admitted_tiers = {o.retention for o in objects if o.key in accepted and o.key.tag == "ship"}
    rejected_tiers = {o.retention for o in objects if o.key not in accepted and o.key.tag == "ship"}
    if admitted_tiers and rejected_tiers:
        assert max(admitted_tiers) <= min(rejected_tiers)


# ---------------------------------------------------------------------------
# Bounded, counted search (§6.2 rule 4) -- including the 20/50-ship stress
# inventories of plan §6.3.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("count", [20, 50])
@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_stress_inventories_stay_bounded_and_counted(count: int, strategy: ProjectionStrategy) -> None:
    sector = _sector(
        404, planets=_PLANET, ships=[_ship(f"Hull {i}", "warship", i) for i in range(count)]
    )
    start = time.perf_counter()
    plan, objects = _solved(sector, strategy, 150, 52)
    elapsed = time.perf_counter() - start
    counters = plan.counters
    assert counters.passes <= TUNING.max_passes
    assert counters.camera_candidates <= TUNING.max_camera_candidates * TUNING.max_passes
    ceiling = (
        counters.camera_candidates * (len(objects) + 1) * max(TUNING.max_reposition_candidates, 1)
    )
    assert counters.reposition_candidates <= ceiling
    assert elapsed < 15.0, f"{count}-ship solve took {elapsed:.1f}s"
    _assert_hard_rules(plan, objects, CellBox(0, 0, 150, 52))
    # Plan §4.18: a starfield-only plan is valid only when nothing can fit; a
    # busy sector must not produce one.
    assert any(p.accepted for p in plan.projections)
    # Plan §4.14: admission never exceeds the budget or the emergency ceiling.
    assert plan.counters.cost_estimated <= TUNING.cost_budget
    ships = sum(
        1 for p in plan.projections if p.accepted and p.key.tag in ("ship", "player")
    )
    assert ships <= TUNING.emergency_ship_ceiling


# ---------------------------------------------------------------------------
# Plan §2.5's "wide region" intent: the redesign must not buy admission by
# funnelling every ship into one narrow band.
# ---------------------------------------------------------------------------


def test_admitted_ships_reach_varied_depths_and_positions() -> None:
    """Variety is asserted *across* sectors and viewports, not within one
    scene: within-scene spread is §4.13's soft objective and competes with
    hysteresis, while the design intent this guards is that a ship's wide
    region stays genuinely reachable."""
    for strategy in STRATEGIES:
        depths: set[int] = set()
        heights: set[int] = set()
        columns: set[int] = set()
        rows: set[int] = set()
        for sector in matrix().values():
            for w, h in SIZES:
                plan, objects = _solved(sector, strategy, w, h)
                ships = {o.key for o in objects if o.key.tag in ("ship", "player")}
                for proj in plan.projections:
                    if proj.accepted and proj.key in ships:
                        depths.add(proj.depth)
                        heights.add(proj.bounds.height)
                        columns.add(proj.bounds.col)
                        rows.add(proj.bounds.row)
        assert len(depths) >= 8, f"{strategy.name}: ships funnelled to depths {sorted(depths)}"
        # Projected *height* variety is coarser than depth variety by
        # construction: `DepthLayeredAnchorProjection` quantises depth into a
        # handful of layers and a ship's face is only 5su tall, so adjacent
        # layers routinely round to the same cell height. The design intent
        # guarded here is that the wide region stays *reachable*, which the
        # depth/column/row spreads below carry.
        assert len(heights) >= 2, f"{strategy.name}: ships funnelled to heights {sorted(heights)}"
        assert len(columns) >= 8, f"{strategy.name}: ships funnelled to columns {sorted(columns)}"
        assert len(rows) >= 5, f"{strategy.name}: ships funnelled to rows {sorted(rows)}"


# ---------------------------------------------------------------------------
# The one scoring term joint placement newly assembles incrementally.
# ---------------------------------------------------------------------------


def test_min_separation_slack_describes_only_the_committed_set() -> None:
    """`min_separation_slack` is the fifth term of `_score`'s lexicographic
    candidate-ordering tuple (plan §9.6), and joint placement now builds it
    during a greedy walk rather than from a finished projection list. That
    makes it the one place per-candidate scratch state could leak into an
    ordering decision and break §4.1, so pin it: the value must equal the
    minimum pairwise gap over exactly the objects that were *committed*,
    unaffected by the candidates tried and discarded along the way.
    """
    sector = matrix()["planet+port+ships"]
    strategy = FixedFovPerspective()
    arrangement, _ = classify_sector(sector, TUNING)
    viewport = CellBox(0, 0, 120, 44)
    admitted = [o for o in arrangement.objects if o.art_mode is not ArtMode.GLYPH]
    admitted.sort(key=lambda o: (o.retention, o.hostility_ordinal, -o.threat_rank, o.key))
    base = {p.key: p.position for p in arrangement.placements}
    anchor = max(admitted, key=lambda o: (o.face.area_su, o.key))
    camera = strategy.frame(arrangement, anchor.key, viewport, TUNING, CATALOG)
    attempt = _attempt(
        camera, admitted, base, viewport, TUNING, CATALOG, strategy,
        anchor.key, 0, {}, {}, trace_prose=False,
    )
    by_key = {o.key: o for o in admitted}
    boxes = {
        key: _inflate(
            _ink_box(by_key[key], attempt.bounds[key], attempt.rung[key], CATALOG, side="max"),
            TUNING.separation_margin,
        )
        for key in attempt.accepted
        if by_key[key].occludes
    }
    keys = sorted(boxes)
    gaps = [
        _rect_gap(boxes[a], boxes[b])
        for i, a in enumerate(keys)
        for b in keys[i + 1 :]
    ]
    expected = min(gaps) if gaps else attempt.min_separation_slack
    assert attempt.min_separation_slack == expected
    # ...and it is a pure function of the inputs, not of evaluation history.
    again = _attempt(
        camera, admitted, base, viewport, TUNING, CATALOG, strategy,
        anchor.key, 0, {}, {}, trace_prose=False,
    )
    assert again.min_separation_slack == attempt.min_separation_slack


# ---------------------------------------------------------------------------
# No float ever reaches a decision (§4.1).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_quantised_output_carries_no_floats(strategy: ProjectionStrategy) -> None:
    for sector in matrix().values():
        plan, _ = _solved(sector, strategy, 120, 44)
        for proj in plan.projections:
            for value in (
                proj.bounds.col, proj.bounds.row, proj.bounds.width, proj.bounds.height, proj.depth
            ):
                assert isinstance(value, int) and not isinstance(value, bool)
            assert isinstance(proj.visible_fraction, Fraction)
