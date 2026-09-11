"""Guards for the three maintainer-reported composition defects.

`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` -> "Retention scoring counted
against the shrinking admitted set", "Cost-aware rung selection", "Stardock as
its own scale class", and "Ship apparent size and the cost budget" are the
reference sections. Everything here runs against the *real* config-driven
`SceneTuning`/`ArtGeometryCatalog` pair a live game builds, because each defect
only manifested at the shipped WP-SC05 values.

The three claims under test:

1. **A scene is never emptied to improve its own score.** The pass loop's
   retention ladder shrinks `admitted`; scoring rejections against that
   shrinking list made ejection look like an improvement, so a plan holding
   the anchor alone beat a plan holding the anchor and both ships. Scoring is
   now against the fixed full inventory.
2. **A laddered object is never dropped for cost while a cheaper authored rung
   fits where it stands.** Rung selection is cost-aware.
3. **Stardock renders at one of its two richest authored rungs, and ships get
   visibly larger as the canvas does** (`FixedFovPerspective`; the depth-
   layered strategy's scale ceiling is a separate, documented finding).
"""

from __future__ import annotations

import collections
from fractions import Fraction

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from edge.art.geometry_catalog import load_geometry_catalog
from edge.art.scene_tuning import build_continuous_yields, build_scene_tuning
from edge.config import load_config
from edge.core.dto import (
    SectorDTO,
    SectorPlanetDTO,
    SectorPortDTO,
    SectorShipDTO,
    SectorStarbaseDTO,
)
from edge.scene.classify import classify_sector
from edge.scene.geometry import CellBox
from edge.scene.model import ArtMode, ScenePlan, SceneTuning
from edge.scene.project import DepthLayeredAnchorProjection, FixedFovPerspective, ProjectionStrategy
from edge.scene.solve import _select_rung, solve

_CFG = load_config("config/default.yaml")
_PM = _CFG.scene.physical_model
TUNING: SceneTuning = build_scene_tuning(_PM)
CATALOG = load_geometry_catalog(build_continuous_yields(_PM))

STRATEGIES: tuple[ProjectionStrategy, ...] = (FixedFovPerspective(), DepthLayeredAnchorProjection())
SIZES: tuple[tuple[int, int], ...] = ((67, 30), (87, 36), (120, 44), (150, 52))
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


def _port(name: str, *, stardock: bool = False) -> SectorPortDTO:
    return SectorPortDTO(
        port_id=64, name=name, klass="Stardock" if stardock else "Class 1 (SBB)",
        is_stardock=stardock, archetype_id=_ARCHETYPE,
    )


def _base(name: str = "Orbital Platform", planet_id: int | None = None) -> SectorStarbaseDTO:
    return SectorStarbaseDTO(
        starbase_id=4, name=name, owner="yours", operational=True,
        planet_id=planet_id, condition="open", archetype_id=_ARCHETYPE,
    )


_TRAFFIC = [_ship("Vesk Trader", "transport", 2), _ship("Kalt Corvette", "warship", 5)]
_PLANET = [SectorPlanetDTO(planet_id=9101, name="New Hesse", ptype="terrestrial_warm")]


def _solved(sector: SectorDTO, strategy: ProjectionStrategy, w: int, h: int) -> ScenePlan:
    arrangement, _glyphs = classify_sector(sector, TUNING)
    return solve(arrangement, CellBox(0, 0, w, h), TUNING, CATALOG, strategy, trace_prose=True)


def _matrix() -> dict[str, SectorDTO]:
    return {
        "port+ships": _sector(102, ports=[_port("Port Kalso")], ships=_TRAFFIC),
        "stardock+ships": _sector(103, ports=[_port("Stardock", stardock=True)], ships=_TRAFFIC),
        "starbase+ships": _sector(104, starbases=[_base()], ships=_TRAFFIC),
        "planet+ships": _sector(105, planets=_PLANET, ships=_TRAFFIC),
        "planet+port+ships": _sector(
            106, planets=_PLANET, ports=[_port("Port Kalso")], ships=_TRAFFIC
        ),
        "planet+stardock+ships": _sector(
            107, planets=_PLANET, ports=[_port("Stardock", stardock=True)], ships=_TRAFFIC
        ),
        "planet+starbase+ships": _sector(
            108, planets=_PLANET, starbases=[_base(planet_id=9101)], ships=_TRAFFIC
        ),
    }


# ---------------------------------------------------------------------------
# 1. The scene is never emptied to improve its own score.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_the_previously_emptied_scenes_now_keep_their_ships(
    strategy: ProjectionStrategy,
) -> None:
    """The exact regression the maintainer saw: scenes with visible room
    dropping *every* secondary object.

    Before the retention-scoring fix, `planet+port+ships @ 67x30` admitted
    0 of 3 secondary objects and spent 12 of a 250 render-cost budget --
    the port genuinely cannot clear a non-excluded rung at that viewport
    (its parent-relative depth puts it at `dz >= 113` where it needs
    `dz <= 70`), and the pass loop then shed both ships as well, because
    the resulting one-object plan scored *better* than the three-object one.
    """
    for name in ("planet+port+ships", "planet+stardock+ships", "planet+starbase+ships"):
        for w, h in ((67, 30), (87, 36)):
            plan = _solved(_matrix()[name], strategy, w, h)
            ships = sum(
                1 for p in plan.projections if p.accepted and p.key.tag in ("ship", "player")
            )
            assert ships == 2, f"{name} @ {w}x{h} on {strategy.name} kept {ships}/2 ships"


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_no_scene_in_the_matrix_is_emptied_of_every_secondary_object(
    strategy: ProjectionStrategy,
) -> None:
    """Generalises the case above: some object failing must never take the
    whole retention tail with it."""
    for name, sector in _matrix().items():
        for w, h in SIZES:
            arrangement, _ = classify_sector(sector, TUNING)
            anchor = max(
                (o for o in arrangement.objects if o.art_mode is not ArtMode.GLYPH),
                key=lambda o: (o.face.area_su, o.key),
            )
            secondary = {
                o.key for o in arrangement.objects if o.flexible and o.key != anchor.key
            }
            if not secondary:
                continue
            plan = solve(arrangement, CellBox(0, 0, w, h), TUNING, CATALOG, strategy)
            kept = secondary & {p.key for p in plan.projections if p.accepted}
            assert kept, f"{name} @ {w}x{h} on {strategy.name} kept no secondary object"


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_every_retention_reject_names_its_underlying_cause(
    strategy: ProjectionStrategy,
) -> None:
    """Plan §4.20 legibility: "dropped for no discernible reason" must not be
    reproducible from the trace. A `retention_reject` for an object that ever
    failed a hard rule carries that rule id in `Decision.inputs`."""
    seen = False
    # A cramped canvas beside the calibrated ones, because the WP-SC12 parity
    # work admits every object of every `_matrix()` case at every size in
    # `SIZES` — the guard would otherwise pass vacuously on a trace that no
    # longer contains a single `retention_reject`. 40x14 is below the smallest
    # calibrated viewport and forces the fallback ladder to shed.
    for sector in _matrix().values():
        for w, h in (*SIZES, (40, 14)):
            plan = _solved(sector, strategy, w, h)
            hard = {
                d.key for d in plan.trace
                if d.outcome == "reject" and d.rule_id != "retention_reject"
            }
            for decision in plan.trace:
                if decision.rule_id != "retention_reject":
                    continue
                seen = True
                assert decision.reason, "retention_reject carries no prose under trace_prose"
                if decision.key in hard:
                    named = dict(decision.inputs)
                    assert named.get("last_failure"), (
                        f"{decision.key} failed a hard rule but its retention_reject "
                        "names no cause"
                    )
    assert seen, "no retention_reject observed; this guard would be vacuous"


# ---------------------------------------------------------------------------
# 2. Cost never drops an object that had a cheaper authored rung right there.
# ---------------------------------------------------------------------------


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(
    case=st.sampled_from(sorted(_matrix())),
    size=st.sampled_from(SIZES),
    strategy_index=st.integers(min_value=0, max_value=len(STRATEGIES) - 1),
)
def test_a_rejected_object_never_had_an_affordable_rung_at_its_own_size(
    case: str, size: tuple[int, int], strategy_index: int
) -> None:
    """`_select_rung` is cost-aware, so `cost_budget` may only ever refuse an
    object whose *cheapest* allowed rung is already unaffordable -- never one
    whose richest fitting rung was too dear while a cheaper fitting rung sat
    right beside it in the same ladder."""
    strategy = STRATEGIES[strategy_index]
    w, h = size
    plan = _solved(_matrix()[case], strategy, w, h)
    spent = plan.counters.cost_estimated
    arrangement, _ = classify_sector(_matrix()[case], TUNING)
    by_key = {o.key: o for o in arrangement.objects}
    for decision in plan.trace:
        if decision.rule_id != "cost_budget" or decision.key is None:
            continue
        obj = by_key[decision.key]
        if obj.art_mode is not ArtMode.LADDER or obj.ladder_key is None:
            continue
        rungs = CATALOG.rungs(obj.ladder_key)
        floor = TUNING.min_rung_index_from_end_by_scale_class.get(obj.scale_class, 0)
        worst_allowed = max(r.index for r in rungs) - floor
        cheapest = min(r.render_cost for r in rungs if r.index <= worst_allowed)
        assert spent + cheapest > TUNING.cost_budget, (
            f"{decision.key} refused on cost with {TUNING.cost_budget - spent} left "
            f"but its cheapest allowed rung costs {cheapest}"
        )


def test_cost_aware_rung_selection_only_ever_steps_down() -> None:
    """Plan §4.14: a cost correction "may never move it to a higher cost
    class". A `max_cost` can only remove candidates, so the selected rung is
    always the cost-blind pick or something cheaper."""
    arrangement, _ = classify_sector(_matrix()["planet+stardock+ships"], TUNING)
    laddered = [o for o in arrangement.objects if o.art_mode is ArtMode.LADDER]
    assert laddered
    for obj in laddered:
        for width in range(4, 60, 3):
            for height in range(2, 30, 2):
                box = CellBox(0, 0, width, height)
                richest = _select_rung(CATALOG, obj, box, TUNING)
                if richest is None:
                    continue
                for budget in (0, 20, 50, 150, 400):
                    picked = _select_rung(CATALOG, obj, box, TUNING, budget)
                    if picked is None:
                        assert richest.render_cost > budget
                        continue
                    assert picked.render_cost <= budget
                    assert picked.render_cost <= richest.render_cost
                    assert picked.natural.width <= width
                    assert picked.natural.height <= height


# ---------------------------------------------------------------------------
# 3a. Stardock is a headline location and renders like one.
# ---------------------------------------------------------------------------


def _stardock_rungs(plan: ScenePlan, arrangement_keys: dict[object, str]) -> list[int]:
    out: list[int] = []
    for proj in plan.projections:
        if not proj.accepted or proj.rung is None:
            continue
        if arrangement_keys.get(proj.key) == "stardock":
            out.append(proj.rung.index)
    return out


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_stardock_never_renders_below_its_richness_floor(
    strategy: ProjectionStrategy,
) -> None:
    """Stardock has its own `scale_class`, its own face extent, and its own
    `min_rung_index_from_end` floor, so an admitted Stardock is always at one
    of its ladder's richest tiers -- never the mast-only rung an ordinary
    trading post may fall back to."""
    floor = TUNING.min_rung_index_from_end_by_scale_class["stardock"]
    seen = 0
    for name in ("stardock+ships", "planet+stardock+ships"):
        for w, h in SIZES:
            arrangement, _ = classify_sector(_matrix()[name], TUNING)
            kinds = {
                o.key: (o.ladder_key.subtype if o.ladder_key else "")
                for o in arrangement.objects
            }
            plan = solve(arrangement, CellBox(0, 0, w, h), TUNING, CATALOG, strategy)
            for obj in arrangement.objects:
                if kinds[obj.key] != "stardock":
                    continue
                assert obj.scale_class == "stardock"
                n_rungs = len(CATALOG.rungs(obj.ladder_key)) if obj.ladder_key else 0
                for proj in plan.projections:
                    if proj.key != obj.key or not proj.accepted:
                        continue
                    assert proj.rung is not None
                    seen += 1
                    assert proj.rung.index <= n_rungs - 1 - floor, (
                        f"{name} @ {w}x{h} on {strategy.name}: Stardock rung "
                        f"{proj.rung.index} of {n_rungs}"
                    )
    assert seen, "no Stardock admitted anywhere; this guard would be vacuous"


@pytest.mark.parametrize("strategy", STRATEGIES, ids=lambda s: s.name)
def test_stardock_outreads_an_ordinary_port_at_the_same_viewport(
    strategy: ProjectionStrategy,
) -> None:
    """The narrative point of the fix (`AGENTS.md`: Stardock is Core Space's
    flagship): at the same canvas and inventory shape, Stardock's projected
    box is strictly taller than a trading port's."""
    for w, h in SIZES:
        port_plan = _solved(_matrix()["planet+port+ships"], strategy, w, h)
        dock_plan = _solved(_matrix()["planet+stardock+ships"], strategy, w, h)
        port_h = [p.bounds.height for p in port_plan.projections
                  if p.accepted and p.key.tag == "port"]
        dock_h = [p.bounds.height for p in dock_plan.projections
                  if p.accepted and p.key.tag == "port"]
        if not port_h or not dock_h:
            continue
        assert max(dock_h) > max(port_h), (
            f"{w}x{h} on {strategy.name}: stardock {dock_h} not taller than port {port_h}"
        )


def test_stardock_face_area_preserves_the_apparent_scale_hierarchy() -> None:
    """Plan §2.2/§4.4: station > wreck > ship, and every station well below a
    planet/phenomenon anchor -- so a bigger Stardock face must not turn it
    into a scene anchor."""
    extents = TUNING.face_extent_by_scale_class
    area = {k: w * h for k, (w, h) in extents.items()}
    assert area["anchor"] > area["stardock"] > area["orbital"] > area["wreck"] > area["ship"]
    assert area["entity"] > area["stardock"]
    for _kind, (w, h) in TUNING.face_extent_by_kind.items():
        assert w * h > area["stardock"]


# ---------------------------------------------------------------------------
# 3b. Ship apparent size responds to canvas size.
# ---------------------------------------------------------------------------


def test_ship_apparent_size_grows_with_the_canvas_under_perspective() -> None:
    """The maintainer's third complaint: "the composers tend to never use the
    larger sizes for the ships even on large screens".

    Under `FixedFovPerspective` a bigger canvas must actually buy bigger
    ships. Asserted as a monotone comparison of the *mean* admitted ship
    rung richness between the smallest and largest canvases, because any one
    scene's ships are placed at genuinely varied depths by design (§4.13).
    """
    strategy = FixedFovPerspective()
    per_size: dict[int, list[int]] = collections.defaultdict(list)
    for sector in _matrix().values():
        for w, h in SIZES:
            plan = _solved(sector, strategy, w, h)
            for proj in plan.projections:
                if proj.accepted and proj.rung is not None and proj.key.tag in ("ship", "player"):
                    per_size[w].append(proj.bounds.height)
    assert all(per_size[w] for w, _ in SIZES)
    small = Fraction(sum(per_size[67]), len(per_size[67]))
    large = Fraction(sum(per_size[150]), len(per_size[150]))
    assert large > small, f"mean ship box height {small} at 67x30 vs {large} at 150x52"


def test_depth_layered_projection_cannot_magnify_and_this_is_known() -> None:
    """A documented limitation, asserted so it cannot silently change.

    `DepthLayeredAnchorProjection`'s scale is `depth_layer_scale ** layer`
    with `layer = dz // depth_layer_size_su >= 0` and
    `0 < depth_layer_scale < 1`, so scale never exceeds 1 and an object's
    projected box never exceeds its own su face size (times `cell_aspect` on
    width) at *any* viewport. That, not the cost budget, is why ship rung
    richness under that strategy is flat across every canvas -- see the plan's
    "Ship apparent size and the cost budget" section.
    """
    assert 0 < TUNING.depth_layer_scale < 1
    strategy = DepthLayeredAnchorProjection()
    for _sector in _matrix().values():
        for w, h in SIZES:
            plan = _solved(_sector, strategy, w, h)
            scale = strategy.scale_at(plan.camera, CellBox(0, 0, w, h), plan.camera.position.z + 1)
            assert scale is None or scale <= 1
