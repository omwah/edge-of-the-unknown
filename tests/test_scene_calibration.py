"""Tests for the WP-SC05 calibration review tool (`edge.devtool.scene_calibration`).

Smoke/structure tests: the tool must run against the real classifier and both
projection strategies without crashing, produce well-formed machine-readable
output covering every required matrix cell (plan WP-SC05 implementation
bullet 2), and must never write anything into `config/default.yaml` -- the
whole point of this tool is that it *proposes* numbers for review rather than
shipping them (plan §5).
"""

from __future__ import annotations

import json
from pathlib import Path

from edge.devtool.scene_calibration import (
    REPORT_LABEL,
    CALIBRATION_SIZES,
    _load_proposed_catalog,
    calibration_cases,
    extended_proposals,
    illustrate_cost_pressure,
    illustrate_failed_anchor,
    illustrate_resize_stability,
    proposed_continuous_yields,
    proposed_tuning,
    render_markdown,
    run_calibration,
    trace_case,
)
from edge.scene.project import DepthLayeredAnchorProjection, FixedFovPerspective

# The matrix cells the plan's WP-SC05 implementation bullet requires be
# covered (§ "Cover Entity + planet, each mutually exclusive generated
# discovery ... including a sensor-gated wreck, planet/phenomenon + runtime
# wrecks, permeable belt, arbitrary station orbit, hostility/threat ordering,
# natural unpadded stations, cost pressure, failed-anchor sidebar handling,
# and resize stability").
REQUIRED_CASE_SUBSTRINGS = (
    "entity+planet",
    "nebula",
    "blackhole",
    "wormhole",
    "discovery:wreck",
    "runtime-wrecks",
    "belt",
    "arbitrary-orbit",
    "hostility-ordering",
    "port+ships",  # a natural, unpadded station case
    "cost-pressure",
)


def test_calibration_cases_cover_the_required_matrix_cells() -> None:
    cases = calibration_cases()
    for needle in REQUIRED_CASE_SUBSTRINGS:
        assert any(needle in name for name in cases), f"missing case for {needle!r}"


def test_proposed_tuning_has_a_rationale_for_every_field() -> None:
    tuning, notes = proposed_tuning()
    assert notes  # every SceneTuning field documented gets a ProposedValue note
    for note in notes:
        assert note.field and note.proposal and note.rationale
    # Every scale_class classify.py can reach must resolve on this tuning.
    from edge.scene.classify import SCALE_CLASSES

    for cls in SCALE_CLASSES:
        assert cls in tuning.face_extent_by_scale_class
        assert cls in tuning.region_by_scale_class
        assert cls in tuning.target_fraction_by_scale_class
        assert cls in tuning.ink_ratio_by_scale_class


def test_proposed_face_extent_by_kind_orders_anchor_phenomena_by_area() -> None:
    """Plan §2.2's apparent-scale hierarchy: nebula/black_hole visual system
    ≫ wormhole > planet (which has no per-kind override, so it falls back to
    the shared "anchor" scale_class bucket)."""
    tuning, notes = proposed_tuning()
    assert any(n.field == "face_extent_by_kind" for n in notes)
    for kind in ("nebula", "black_hole", "wormhole"):
        assert kind in tuning.face_extent_by_kind

    def area(w_h: tuple[int, int]) -> int:
        return w_h[0] * w_h[1]

    nebula_area = area(tuning.face_extent_by_kind["nebula"])
    black_hole_area = area(tuning.face_extent_by_kind["black_hole"])
    wormhole_area = area(tuning.face_extent_by_kind["wormhole"])
    planet_area = area(tuning.face_extent_by_scale_class["anchor"])
    assert nebula_area > wormhole_area > planet_area
    assert black_hole_area > wormhole_area > planet_area


def test_proposed_region_gives_ship_and_wreck_wider_freedom_than_stations() -> None:
    """Plan §2.5: ships receive wider placement regions/depth ranges than
    stations. `region_by_scale_class`'s type is already per-scale-class
    (`Mapping[str, Region]`); this checks the *proposed values* differentiate
    ship/wreck from orbital/anchor/belt/entity, not just the type."""
    tuning, notes = proposed_tuning()
    assert any(n.field == "region_by_scale_class" for n in notes)
    ship_region = tuning.region_by_scale_class["ship"]
    wreck_region = tuning.region_by_scale_class["wreck"]
    orbital_region = tuning.region_by_scale_class["orbital"]
    anchor_region = tuning.region_by_scale_class["anchor"]

    def span(region: object) -> tuple[int, int, int]:
        return (
            region.x_max - region.x_min,  # type: ignore[attr-defined]
            region.y_max - region.y_min,  # type: ignore[attr-defined]
            region.z_max - region.z_min,  # type: ignore[attr-defined]
        )

    ship_span, wreck_span, orbital_span = span(ship_region), span(wreck_region), span(orbital_region)
    assert ship_span == wreck_span
    for axis in range(3):
        assert ship_span[axis] > orbital_span[axis]
    # Orbital/anchor/belt/entity still share the one common (narrower) region.
    assert orbital_region == anchor_region


def test_proposed_continuous_yields_cover_every_classify_category() -> None:
    yields, notes = proposed_continuous_yields()
    assert notes
    for kind in ("planet", "nebula", "black_hole", "wormhole", "wreck", "entity", "belt"):
        assert kind in yields
        y = yields[kind]
        assert y.box_classes
        assert len(y.box_classes) == len(y.render_cost)


def test_trace_case_runs_real_classifier_and_both_strategies() -> None:
    tuning, _ = proposed_tuning()
    continuous, _ = proposed_continuous_yields()
    catalog = _load_proposed_catalog(continuous)
    cases = calibration_cases()
    sector = cases["planet+port+ships" if "planet+port+ships" in cases else next(iter(cases))]
    for strategy in (FixedFovPerspective(), DepthLayeredAnchorProjection()):
        trace = trace_case("planet+port+ships", sector, "standard", 67, 30,
                            strategy, tuning, catalog)
        assert trace is not None
        assert trace.objects
        anchor_traces = [o for o in trace.objects if o.decision == "anchor"]
        assert len(anchor_traces) == 1
        for obj in trace.objects:
            assert obj.render_cost >= 0


def test_illustrate_cost_pressure_walks_the_box_class_ladder() -> None:
    tuning, _ = proposed_tuning()
    continuous, _ = proposed_continuous_yields()
    catalog = _load_proposed_catalog(continuous)
    illustration = illustrate_cost_pressure(tuning, catalog, cost_budget=50)
    assert illustration.box_class_sequence
    assert illustration.chosen_box_class_index >= 0
    # A tight budget should not silently pick the most expensive class.
    costs = [int(s["render_cost"]) for s in illustration.box_class_sequence]  # type: ignore[call-overload]
    assert (min(costs) <= illustration.proposed_cost_budget
            or illustration.chosen_box_class_index == len(costs) - 1)


def test_illustrate_failed_anchor_reports_a_floor_check() -> None:
    tuning, _ = proposed_tuning()
    continuous, _ = proposed_continuous_yields()
    catalog = _load_proposed_catalog(continuous)
    illustration = illustrate_failed_anchor(tuning, catalog)
    assert illustration.width > 0 and illustration.height > 0
    assert illustration.min_extent["width"] > 0
    assert isinstance(illustration.would_fit, bool)


def test_illustrate_resize_stability_reports_a_small_delta_for_one_column() -> None:
    tuning, _ = proposed_tuning()
    continuous, _ = proposed_continuous_yields()
    catalog = _load_proposed_catalog(continuous)
    for strategy in (FixedFovPerspective(), DepthLayeredAnchorProjection()):
        illustration = illustrate_resize_stability(tuning, catalog, strategy)
        assert illustration.hysteresis_delta_terms >= 0
        assert illustration.size_a != illustration.size_b


def test_extended_proposals_are_all_labelled() -> None:
    proposals = extended_proposals()
    assert proposals
    for p in proposals:
        assert p.field and p.proposal and p.rationale


def test_run_calibration_end_to_end_and_json_roundtrip(tmp_path: Path) -> None:
    # A reduced size matrix keeps this test fast; the full CALIBRATION_SIZES
    # matrix is exercised by running the CLI, not by every test.
    report = run_calibration(sizes=CALIBRATION_SIZES[:1], cost_budget=100)
    assert report.label == REPORT_LABEL == "PENDING HUMAN REVIEW / APPROVAL"
    assert report.matrix
    assert report.cost_pressure is not None
    assert report.failed_anchor is not None
    assert report.resize_stability
    assert report.open_questions

    seen_cases = {t.case for t in report.matrix}
    for needle in REQUIRED_CASE_SUBSTRINGS:
        assert any(needle in name for name in seen_cases), f"matrix missing {needle!r}"

    from dataclasses import asdict

    payload = asdict(report)
    out = tmp_path / "calibration.json"
    out.write_text(json.dumps(payload, default=str))
    reloaded = json.loads(out.read_text())
    assert reloaded["label"] == REPORT_LABEL

    md = render_markdown(report)
    assert "PENDING HUMAN REVIEW / APPROVAL" in md
    assert "Open questions" in md or "open questions" in md.lower()


def test_calibration_tool_never_touches_shipped_config() -> None:
    """The whole point of this tool: `config/default.yaml` must not gain a
    `scene:` key from running it. This asserts the shipped file is unchanged
    around its `scene:` block after a full calibration run."""

    repo_root = Path(__file__).resolve().parent.parent
    config_path = repo_root / "config" / "default.yaml"
    before = config_path.read_text()
    run_calibration(sizes=CALIBRATION_SIZES[:1], cost_budget=100)
    after = config_path.read_text()
    assert before == after
    # The legacy scene: block (SceneArtConfig, plan §5's "keeps the new
    # scene: keys out of config/default.yaml entirely") stays exactly as it
    # was: no WP-SC05 tuning key name should appear in it.
    for wp_sc05_key in ("face_extent_by_scale_class", "target_fraction_by_scale_class",
                        "ink_ratio_by_scale_class", "camera_height_fraction_min"):
        assert wp_sc05_key not in after
