"""Tests for the WP-SC04 benchmark tool (`edge.devtool.scene_benchmark`).

These are smoke/structure tests, not performance assertions -- CI must not
depend on fragile wall-clock thresholds (plan §6.2 "CI tests should assert
structural counts and bounds, not fragile wall-clock thresholds"). They check
the tool runs against small inputs, produces well-formed machine-readable
output, and does not crash on edge inventories (an empty sector, and the
1/5/20/50-synthetic-ship stress cases).
"""

from __future__ import annotations

import json
from pathlib import Path

from edge.core.dto import SectorDTO
from edge.devtool.scene_benchmark import (
    Distribution,
    _benchmark_tuning,
    _load_benchmark_catalog,
    _synthetic_ship_sector,
    _to_jsonable,
    benchmark_current_composer,
    benchmark_decision_prose_gating,
    benchmark_replacement,
    measure_dto_inventories,
    render_markdown,
    run_benchmark,
)
from edge.scene.classify import classify_sector


def test_distribution_of_empty() -> None:
    d = Distribution.of([])
    assert d.n == 0
    assert d.median == 0.0 and d.max == 0.0


def test_distribution_of_values() -> None:
    d = Distribution.of([1.0, 2.0, 3.0, 4.0, 5.0])
    assert d.n == 5
    assert d.median == 3.0
    assert d.max == 5.0
    assert d.p95 <= d.max


def test_benchmark_current_composer_runs_and_reports_both_workloads() -> None:
    results = benchmark_current_composer(repeats=2)
    assert results  # non-empty: every (case, size) pair produced a sample
    for r in results:
        assert r.cold_ms >= 0
        assert r.warm_ms.n == 1  # repeats=2 -> 1 warm sample
        assert r.width > 0 and r.height > 0


def test_measure_dto_inventories_uses_real_bigbang_and_server_projection() -> None:
    report = measure_dto_inventories(seeds=1, sectors_per_seed=20)
    assert report.seeds_sampled == 1
    assert report.sectors_sampled == 20
    assert report.ships.n == 20
    assert report.discoveries.n == 20
    assert report.stations.n == 20
    assert report.wrecks.n == 20
    # Synthetic multiplayer/N-ship stress is present for every requested size.
    for n in (1, 5, 20, 50):
        assert f"{n}_ships_classify_ms" in report.multiplayer_stress
        assert report.multiplayer_stress[f"{n}_ships_classify_ms"] >= 0


def test_synthetic_ship_sector_classifies_at_every_stress_size() -> None:
    tuning = _benchmark_tuning()
    for n in (0, 1, 5, 20, 50):
        dto = _synthetic_ship_sector(n)
        arrangement, glyphs = classify_sector(dto, tuning)
        assert len(arrangement.objects) == n
        assert glyphs == ()  # no force block with fighters/mines


def test_empty_sector_does_not_crash_classification_or_strategies() -> None:
    """An edge inventory: a sector with nothing in it at all."""
    empty = SectorDTO(region="Bench", sector_id=1, flavor="empty", beacon=None)
    tuning = _benchmark_tuning()
    arrangement, glyphs = classify_sector(empty, tuning)
    assert arrangement.objects == ()
    assert glyphs == ()


def test_benchmark_replacement_runs_both_strategies_deterministically() -> None:
    report = benchmark_replacement(repeats=2)
    assert report.classify_ms.n > 0
    assert report.strategies  # every case with a viable anchor produced rows
    strategy_names = {s.strategy for s in report.strategies}
    assert strategy_names == {"fixed_fov_perspective", "depth_layered_anchor"}
    for s in report.strategies:
        assert s.candidate_count >= s.distinct_quantised_scene_count >= 0
        assert s.deterministic_ordering is True


def test_benchmark_catalog_falls_back_for_unmatched_archetypes() -> None:
    """A ladder key with no real calibrated match (e.g. archetype_id="") must
    still get usable rungs, not raise -- the benchmark cannot depend on every
    fixture happening to name a species the checked-in art catalogue covers.
    """
    from edge.scene.catalog import LadderKey

    catalog = _load_benchmark_catalog()
    key = LadderKey(kind="ship", subtype="transport", axis="horizontal", archetype_id="")
    rungs = catalog.rungs(key)
    assert rungs
    # continuous() must also never raise for a benchmark-reached kind.
    yield_ = catalog.continuous("some_unseen_kind")
    assert yield_.kind == "some_unseen_kind"


def test_decision_prose_gating_is_explicitly_labelled_not_faked() -> None:
    gating = benchmark_decision_prose_gating()
    assert "n/a" in gating["gated_off_ms"]
    assert "n/a" in gating["gated_on_ms"]


def test_run_benchmark_end_to_end_and_json_roundtrip(tmp_path: Path) -> None:
    report = run_benchmark(seeds=1, sectors_per_seed=10, repeats=2)
    assert report.label == "PENDING HUMAN REVIEW / APPROVAL"
    payload = _to_jsonable(report)
    out = tmp_path / "bench.json"
    out.write_text(json.dumps(payload))
    reloaded = json.loads(out.read_text())
    assert reloaded["label"] == "PENDING HUMAN REVIEW / APPROVAL"
    assert reloaded["composer_baseline"]
    assert reloaded["dto_inventories"]["ships"]["n"] == 10

    md = render_markdown(report)
    assert "PENDING HUMAN REVIEW / APPROVAL" in md
    assert "distinct quantised scenes" in md
