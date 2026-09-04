"""Reproducible baseline/comparison benchmark for the sector scene (WP-SC04).

`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §6 ("Performance contract") requires a
dependency-free benchmark that (a) replaces the informal 2026-08-31 shipped-composer
numbers in §6.1 with a reproducible measurement over the same scene canvases, (b)
measures real fog-safe `SectorDTO` inventories from the actual bigbang/server code
paths, and (c) runs both `edge/scene/` projection strategies through identical
inventories to report structural comparison data a human uses to pick one strategy
(WP-SC04's "compare and approve" step — this tool never picks; it only measures).

Usage::

    pixi run python -m edge.devtool.scene_benchmark
    pixi run python -m edge.devtool.scene_benchmark --seeds 10 --sectors-per-seed 300
    pixi run python -m edge.devtool.scene_benchmark --json out.json --md out.md

No third-party benchmarking package is used, per plan §6.3 -- only
`time.perf_counter`. Output is one JSON document (machine-readable, for
before/after diffing) plus a concise human-readable Markdown summary.

**Scope note (read before trusting a number here):** `edge/scene/solve.py` (the
constraint solver, WP-SC06) is an unimplemented stub, and no `scene:` calibration
data has shipped yet (WP-SC05: `SceneTuning`/`ContinuousYield` ship with no default
instance by design). So the "replacement" side of this benchmark can only exercise
what has actually landed -- DTO classification (`edge.scene.classify.classify_sector`)
and each strategy's `frame()`/`candidates()`/`project()` -- against a **benchmark-only**
`SceneTuning` and a **benchmark-only synthetic `ContinuousYield`** overlay (ship/port
ladder rungs come from the real checked-in `edge/art/geometry_catalog.json`; continuous
kinds like planets/nebulae have no calibrated data yet, so this tool fabricates
plausible placeholder envelopes purely to exercise the arithmetic, and every report
section built from them is labelled accordingly). There is no admitted/rejected/
painted pipeline, no solve-pass/occlusion/reanchor counters, no sprite-render cache,
and no `ScenePlan` cache to report on -- those fields are explicitly marked ``"n/a
(pending WP-SC06/SC07)"`` in the JSON output rather than fabricated.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from edge.art.geometry_catalog import JsonArtGeometryCatalog, load_default_geometry_catalog
from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core.config import GameConfig, SceneArtConfig
from edge.core.dto import SectorDTO, SectorForceDTO, SectorShipDTO
from edge.core.models import UniverseState
from edge.core.rules import JoinGame, apply_result, reduce
from edge.scene.catalog import ArtGeometryCatalog, ContinuousYield, LadderKey, LadderRung
from edge.scene.classify import classify_sector
from edge.scene.geometry import CellBox, Region, Vec3
from edge.scene.model import PhysicalObject, SceneTuning
from edge.scene.project import (
    DepthLayeredAnchorProjection,
    FixedFovPerspective,
    ProjectionStrategy,
)
from edge.server.session import _sector_dto
from edge.tui.scene_gallery import SIZES, cases
from edge.tui.widgets import _SceneComposer

# The exact canvases named in plan §6.1, so the reproducible numbers below are
# directly comparable to the informal 2026-08-31 figures.
BASELINE_SIZES: tuple[tuple[str, int, int], ...] = SIZES

REPORT_LABEL = "PENDING HUMAN REVIEW / APPROVAL"
"""Stamped into every report section: WP-SC04 measures, it does not approve
(plan §6.4 reserves that decision for the maintainer)."""


# ---------------------------------------------------------------------------
# Small stats helpers (no numpy/statistics-package dependency beyond stdlib)
# ---------------------------------------------------------------------------


def _percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile over `values` (0 <= p <= 100); 0.0 if empty."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = max(0, min(len(ordered) - 1, int(round(p / 100 * (len(ordered) - 1)))))
    return ordered[rank]


@dataclass
class Distribution:
    """median/p95/p99/max over a sample, plus its size."""

    n: int
    median: float
    p95: float
    p99: float
    max: float

    @classmethod
    def of(cls, values: list[float]) -> Distribution:
        if not values:
            return cls(n=0, median=0.0, p95=0.0, p99=0.0, max=0.0)
        return cls(
            n=len(values),
            median=statistics.median(values),
            p95=_percentile(values, 95),
            p99=_percentile(values, 99),
            max=max(values),
        )


def _ms(seconds: float) -> float:
    return round(seconds * 1000, 4)


# ---------------------------------------------------------------------------
# Section 1: reproducible shipped-composer baseline (plan §6.1)
# ---------------------------------------------------------------------------


@dataclass
class ComposerCaseResult:
    case: str
    size: str
    width: int
    height: int
    cold_ms: float
    """First compose of this (case, size) pair -- an uncached run."""
    warm_ms: Distribution
    """4 repeat composes of the same (case, size) pair."""


def benchmark_current_composer(*, repeats: int = 5) -> list[ComposerCaseResult]:
    """Reproduce plan §6.1 over the same case matrix `edge.tui.scene_gallery` uses
    and the same canvases (67x30 through 150x52), cold vs warm split out per
    §6.2 rule 8 / plan fact 1 ("warm revisit cost and cold new-sector/new-size
    cost are different workloads")."""
    cfg = SceneArtConfig()
    results: list[ComposerCaseResult] = []
    for case_name, sector in cases().items():
        for size_label, w, h in BASELINE_SIZES:
            samples: list[float] = []
            for _ in range(repeats):
                composer = _SceneComposer(sector, cfg)
                t0 = time.perf_counter()
                composer.compose(w, h)
                samples.append(time.perf_counter() - t0)
            cold_ms = _ms(samples[0])
            warm = Distribution.of([_ms(s) for s in samples[1:]])
            results.append(ComposerCaseResult(
                case=case_name, size=size_label, width=w, height=h,
                cold_ms=cold_ms, warm_ms=warm))
    return results


# ---------------------------------------------------------------------------
# Section 2: real fog-safe DTO inventories (plan §2.3 grounding, §6.3 bullet 1)
# ---------------------------------------------------------------------------


@dataclass
class DtoInventorySample:
    ships: int
    discoveries: int
    stations: int
    """ports + starbases."""
    wrecks: int
    """discoveries whose kind == "wreck" -- generated wreck visibility, not a
    runtime-combat wreck (those are created during play, not by bigbang)."""


@dataclass
class DtoInventoryReport:
    seeds_sampled: int
    sectors_sampled: int
    ships: Distribution
    discoveries: Distribution
    stations: Distribution
    wrecks: Distribution
    multiplayer_stress: dict[str, float]
    """Synthetic: not generated-universe data -- see docstring on the field's
    producer. Reports ship-inventory-size timing impact only."""


def _enroll(state: UniverseState, config: GameConfig, player_id: int) -> None:
    apply_result(state, reduce(state, player_id, JoinGame(), config))


def measure_dto_inventories(
    *, seeds: int, sectors_per_seed: int, config: GameConfig | None = None,
) -> DtoInventoryReport:
    """Walk real generated universes through the real fog-safe projection
    (`edge.server.session._sector_dto`) -- not synthetic guesses -- to ground
    the "actual fog-safe DTO inventories" claim in plan §2.3."""
    cfg = config or load_default_config()
    ships: list[float] = []
    discoveries: list[float] = []
    stations: list[float] = []
    wrecks: list[float] = []
    sectors_sampled = 0
    for seed in range(seeds):
        state = generate(cfg, seed)
        _enroll(state, cfg, 1)
        player = state.players[1]
        sector_ids = sorted(state.sectors)[:sectors_per_seed]
        for sid in sector_ids:
            sector = state.sectors[sid]
            dto = _sector_dto(state, player, sector, state.core_hops, cfg)
            ships.append(len(dto.ships))
            discoveries.append(len(dto.discoveries))
            stations.append(len(dto.ports) + len(dto.starbases))
            wrecks.append(len([d for d in dto.discoveries if d.kind == "wreck"]))
            sectors_sampled += 1

    # Multiplayer stress: not from generated-universe data (bigbang seeds one
    # player only) -- a labelled synthetic case exercising classify_sector's
    # cost as ship count scales, per plan §6.3's "1, 5, 20, 50-ship synthetic
    # inventories, because the replacement removes the current three-sprite cap."
    stress: dict[str, float] = {}
    for n in (1, 5, 20, 50):
        dto = _synthetic_ship_sector(n)
        t0 = time.perf_counter()
        classify_sector(dto, _benchmark_tuning())
        stress[f"{n}_ships_classify_ms"] = _ms(time.perf_counter() - t0)

    return DtoInventoryReport(
        seeds_sampled=seeds, sectors_sampled=sectors_sampled,
        ships=Distribution.of(ships), discoveries=Distribution.of(discoveries),
        stations=Distribution.of(stations), wrecks=Distribution.of(wrecks),
        multiplayer_stress=stress)


def _synthetic_ship_sector(n_ships: int) -> SectorDTO:
    ships = [
        SectorShipDTO(
            name=f"Bench Ship {i}", role="warship", archetype_id="federation",
            contact_id=i, art_subtype="warship",
            retention_class=("hostile", "neutral", "friendly")[i % 3],
            hostility_ordinal=i, combat_threat_rank=i,
        )
        for i in range(n_ships)
    ]
    return SectorDTO(
        region="Bench", sector_id=1, flavor="a benchmark arrangement",
        beacon=None, band="Frontier", ships=ships,
        force=SectorForceDTO(owner="Bench Fleet", yours=False, fighters=0,
                             mode="offensive", toll=0, armid_mines=0, limpet_mines=0))


# ---------------------------------------------------------------------------
# Section 3: benchmark-only SceneTuning + catalog overlay
# ---------------------------------------------------------------------------


def _bench_region() -> Region:
    return Region(x_min=-200, x_max=200, y_min=-100, y_max=100, z_min=1, z_max=400)


def _benchmark_tuning() -> SceneTuning:
    """A plausible, internally-consistent `SceneTuning` used only to drive this
    benchmark's arithmetic. **Not calibrated** -- WP-SC05 owns the real numbers;
    this tool must not be read as proposing these values for `config/default.yaml`.
    """
    region = _bench_region()
    return SceneTuning(
        face_extent_by_scale_class={
            "entity": (30, 12), "anchor": (80, 40), "belt": (120, 20),
            "orbital": (18, 9), "ship": (36, 8), "wreck": (24, 10),
        },
        region_by_scale_class={cls: region for cls in
                               ("entity", "anchor", "belt", "orbital", "ship", "wreck")},
        target_fraction_by_scale_class={
            "entity": Fraction(1, 4), "anchor": Fraction(1, 2), "belt": Fraction(1, 2),
            "orbital": Fraction(1, 5), "ship": Fraction(1, 6), "wreck": Fraction(1, 6),
        },
        ink_ratio_by_scale_class={
            "entity": Fraction(4, 5), "anchor": Fraction(3, 5), "belt": Fraction(1, 2),
            "orbital": Fraction(9, 10), "ship": Fraction(9, 10), "wreck": Fraction(4, 5),
        },
        structural_mode_thresholds=(
            (150, 52, "wide"), (120, 44, "large"), (87, 36, "standard"), (0, 0, "compact"),
        ),
        fixed_fov_num=1, fixed_fov_den=2,
        cell_aspect=Fraction(2, 1), near_plane_su=1,
        depth_layers=8, depth_layer_size_su=6, depth_layer_scale=Fraction(4, 5),
        camera_height_fraction_min=Fraction(1, 8), camera_height_fraction_max=Fraction(3, 4),
        aim_offsets_su=(0, -2, 2, -4, 4), max_camera_candidates=64,
        hysteresis_weight_camera=1, hysteresis_weight_position=1,
        hysteresis_weight_admission=4, hysteresis_weight_art=1,
        # WP-SC06 solver bounds -- not calibrated, see docstring above.
        max_passes=24, edge_margin=1,
        min_projected_cells_by_scale_class={
            "entity": (4, 2), "anchor": (6, 3), "belt": (6, 2),
            "orbital": (3, 2), "ship": (3, 1), "wreck": (3, 1),
        },
        separation_margin=1,
        min_visible_fraction_by_scale_class={
            "entity": Fraction(1, 1), "anchor": Fraction(1, 1), "belt": Fraction(1, 1),
            "orbital": Fraction(3, 4), "ship": Fraction(3, 4), "wreck": Fraction(3, 4),
        },
        cost_budget=250, emergency_ship_ceiling=40,
        max_reposition_candidates=16, max_glyph_tries=20, glyph_spacing=2,
    )


class _BenchmarkCatalog:
    """`ArtGeometryCatalog` for this benchmark only: real ship/port ladder rungs
    from the checked-in `geometry_catalog.json`, plus a synthetic placeholder
    `ContinuousYield` for any continuous kind the classifier reaches (planets,
    nebula/black_hole/wormhole discoveries, wrecks, the roaming entity) --
    WP-SC05 has not calibrated those yet, so this fabricates a plausible
    envelope purely to exercise the arithmetic. Every report field derived from
    this catalog is labelled as benchmark-only, never as calibrated data.
    """

    def __init__(self, real: JsonArtGeometryCatalog) -> None:
        self._real = real
        self.version = f"{real.version}+bench-synthetic-continuous"
        self._continuous_cache: dict[str, ContinuousYield] = {}
        self._rung_fallback_cache: dict[LadderKey, tuple[LadderRung, ...]] = {}

    def rungs(self, key: LadderKey) -> tuple[LadderRung, ...]:
        real_rungs = self._real.rungs(key)
        if real_rungs:
            return real_rungs
        # No calibrated archetype/subtype match (e.g. a fixture with no real
        # species archetype_id, or a DTO inventory outside the checked-in art
        # sample) -- fall back to a synthetic 3-tier ladder purely so this
        # benchmark's arithmetic has something to chew on. Never presented as
        # calibrated data.
        cached = self._rung_fallback_cache.get(key)
        if cached is not None:
            return cached
        rungs = (
            LadderRung(tier_id="bench-rich", index=0, natural=CellBox(0, 0, 36, 8),
                      ink_min=CellBox(0, 0, 32, 7), ink_max=CellBox(0, 0, 36, 8),
                      ink_count_min=120, ink_count_max=180, render_cost=25),
            LadderRung(tier_id="bench-mid", index=1, natural=CellBox(0, 0, 22, 5),
                      ink_min=CellBox(0, 0, 19, 4), ink_max=CellBox(0, 0, 22, 5),
                      ink_count_min=50, ink_count_max=80, render_cost=12),
            LadderRung(tier_id="bench-thin", index=2, natural=CellBox(0, 0, 10, 3),
                      ink_min=CellBox(0, 0, 8, 2), ink_max=CellBox(0, 0, 10, 3),
                      ink_count_min=10, ink_count_max=18, render_cost=4),
        )
        self._rung_fallback_cache[key] = rungs
        return rungs

    def continuous(self, kind: str) -> ContinuousYield:
        cached = self._continuous_cache.get(kind)
        if cached is not None:
            return cached
        yield_ = ContinuousYield(
            kind=kind,
            ink_fraction_min=Fraction(3, 5), ink_fraction_max=Fraction(9, 10),
            min_extent=CellBox(0, 0, 6, 3),
            box_classes=(CellBox(0, 0, 80, 32), CellBox(0, 0, 50, 20), CellBox(0, 0, 24, 10)),
            render_cost=(90, 45, 15),
        )
        self._continuous_cache[kind] = yield_
        return yield_


def _load_benchmark_catalog() -> ArtGeometryCatalog:
    return _BenchmarkCatalog(load_default_geometry_catalog())


# ---------------------------------------------------------------------------
# Section 4: replacement structural comparison (classify + strategy candidates)
# ---------------------------------------------------------------------------


@dataclass
class StrategyCaseResult:
    strategy: str
    case: str
    size: str
    frame_ms: float
    candidates_ms: float
    candidate_count: int
    distinct_quantised_scene_count: int
    """Distinct full (col, row, width, height) boxes among the candidates --
    plan §6.3's "distinct quantised scene count", scoped to the anchor only
    (no admitted-set/solve exists yet -- see module docstring)."""
    deterministic_ordering: bool
    """Same candidate camera sequence on a repeat run."""


@dataclass
class ReplacementReport:
    classify_ms: Distribution
    """`classify_sector` alone, over the same case matrix as the composer baseline."""
    strategies: list[StrategyCaseResult]
    admitted_rejected_painted: str = "n/a (pending WP-SC06 solver)"
    solve_pass_counters: str = "n/a (pending WP-SC06 solver)"
    sprite_cache_hit_rate: str = "n/a (pending WP-SC07 art resolution)"
    scene_plan_cache: str = "n/a (no ScenePlan cache exists before WP-SC06/SC08)"
    decision_prose_gating: str = "n/a (no Decision trace producer exists before WP-SC06)"


def _pick_anchor(objects: tuple[PhysicalObject, ...]) -> PhysicalObject | None:
    if not objects:
        return None
    return min(objects, key=lambda o: (int(o.retention), o.key.tag, o.key.ident))


def _distinct_scene_count(
    strategy: ProjectionStrategy, anchor: PhysicalObject,
    candidates: list[Any], viewport: CellBox, at: Vec3,
) -> int:
    boxes = set()
    for camera in candidates:
        box = strategy.project(camera, anchor, at, viewport)
        boxes.add((box.col, box.row, box.width, box.height))
    return len(boxes)


def benchmark_replacement(*, repeats: int = 3) -> ReplacementReport:
    """Run `classify_sector` and both strategies' `frame()`/`candidates()` over
    the same case matrix as the composer baseline, under the benchmark-only
    tuning/catalog above. See module docstring for exactly what is and is not
    measurable before WP-SC06/SC07 land.
    """
    tuning = _benchmark_tuning()
    catalog = _load_benchmark_catalog()
    strategies: list[ProjectionStrategy] = [FixedFovPerspective(), DepthLayeredAnchorProjection()]

    classify_times: list[float] = []
    results: list[StrategyCaseResult] = []
    for case_name, sector in cases().items():
        t0 = time.perf_counter()
        arrangement, _glyphs = classify_sector(sector, tuning)
        classify_times.append(time.perf_counter() - t0)
        anchor = _pick_anchor(arrangement.objects)
        if anchor is None:
            continue
        anchor_pos = next(p.position for p in arrangement.placements if p.key == anchor.key)
        for size_label, w, h in BASELINE_SIZES:
            viewport = CellBox(0, 0, w, h)
            for strategy in strategies:
                t0 = time.perf_counter()
                camera = strategy.frame(arrangement, anchor.key, viewport, tuning, catalog)
                frame_ms = _ms(time.perf_counter() - t0)

                t0 = time.perf_counter()
                candidates = list(strategy.candidates(camera, anchor, anchor_pos, viewport, tuning))
                candidates_ms = _ms(time.perf_counter() - t0)

                distinct = _distinct_scene_count(
                    strategy, anchor, candidates, viewport, anchor_pos
                )

                deterministic = True
                for _ in range(repeats - 1):
                    repeat_candidates = list(
                        strategy.candidates(camera, anchor, anchor_pos, viewport, tuning)
                    )
                    if [(c.position, c.aim_x_su) for c in repeat_candidates] != \
                       [(c.position, c.aim_x_su) for c in candidates]:
                        deterministic = False
                        break

                results.append(StrategyCaseResult(
                    strategy=strategy.name, case=case_name, size=size_label,
                    frame_ms=frame_ms, candidates_ms=candidates_ms,
                    candidate_count=len(candidates),
                    distinct_quantised_scene_count=distinct,
                    deterministic_ordering=deterministic))

    return ReplacementReport(classify_ms=Distribution.of([_ms(t) for t in classify_times]),
                             strategies=results)


# ---------------------------------------------------------------------------
# Section 5: decision-prose gating (§6.2 rule 8)
# ---------------------------------------------------------------------------


def benchmark_decision_prose_gating() -> dict[str, str]:
    """Plan §6.2 rule 8 asks the benchmark to show the dev/gallery decision-prose
    switch matters (or doesn't) by timing the same scene with it off vs on. No
    `Decision`-trace producer exists yet (that is WP-SC06's `solve()`), so there
    is nothing to gate today; recorded as explicitly N/A rather than faked.
    """
    return {"gated_off_ms": "n/a (no Decision trace producer before WP-SC06)",
            "gated_on_ms": "n/a (no Decision trace producer before WP-SC06)"}


# ---------------------------------------------------------------------------
# Report assembly + CLI
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkReport:
    label: str
    generated_note: str
    composer_baseline: list[ComposerCaseResult]
    dto_inventories: DtoInventoryReport
    replacement: ReplacementReport
    decision_prose_gating: dict[str, str]


def run_benchmark(*, seeds: int, sectors_per_seed: int, repeats: int) -> BenchmarkReport:
    return BenchmarkReport(
        label=REPORT_LABEL,
        generated_note=(
            "Supersedes the informal 2026-08-31 figures in plan §6.1 with a "
            "reproducible measurement. Strategy comparison numbers use a "
            "benchmark-only SceneTuning/catalog overlay -- see module docstring."
        ),
        composer_baseline=benchmark_current_composer(repeats=repeats),
        dto_inventories=measure_dto_inventories(seeds=seeds, sectors_per_seed=sectors_per_seed),
        replacement=benchmark_replacement(repeats=repeats),
        decision_prose_gating=benchmark_decision_prose_gating(),
    )


def _to_jsonable(obj: Any) -> Any:
    if isinstance(obj, Distribution | ComposerCaseResult | DtoInventoryReport |
                  StrategyCaseResult | ReplacementReport | BenchmarkReport):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    return obj


def render_markdown(report: BenchmarkReport) -> str:
    lines = [
        "# Sector scene benchmark", "",
        f"**{report.label}** -- this document reports measurements only; WP-SC04's "
        "\"approve one production strategy\" decision is a separate, human step. "
        "Do not read any number here as an approval.", "",
        report.generated_note, "",
        "## 1. Current composer baseline (reproduces plan §6.1)", "",
        "| case | size | cold ms | warm median ms | warm p95 ms | warm max ms |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in report.composer_baseline:
        lines.append(f"| {r.case} | {r.size} | {r.cold_ms} | {r.warm_ms.median} | "
                     f"{r.warm_ms.p95} | {r.warm_ms.max} |")

    inv = report.dto_inventories
    lines += [
        "", "## 2. Real fog-safe DTO inventories "
        f"({inv.seeds_sampled} seeds x up to {inv.sectors_sampled} sectors sampled)", "",
        "| field | median | p95 | p99 | max |", "|---|---:|---:|---:|---:|",
        f"| ships | {inv.ships.median} | {inv.ships.p95} | {inv.ships.p99} | {inv.ships.max} |",
        f"| discoveries | {inv.discoveries.median} | {inv.discoveries.p95} | "
        f"{inv.discoveries.p99} | {inv.discoveries.max} |",
        f"| stations (ports+starbases) | {inv.stations.median} | {inv.stations.p95} | "
        f"{inv.stations.p99} | {inv.stations.max} |",
        f"| generated wrecks | {inv.wrecks.median} | {inv.wrecks.p95} | {inv.wrecks.p99} | "
        f"{inv.wrecks.max} |",
        "", "Synthetic multiplayer/N-ship stress (`classify_sector` only, not generated-universe data):",
        "",
    ]
    for k, v in inv.multiplayer_stress.items():
        lines.append(f"- {k}: {v} ms")

    lines += [
        "", "## 3. Replacement strategy comparison (WP-SC03 code, benchmark-only tuning)", "",
        f"`classify_sector` alone: median {report.replacement.classify_ms.median} ms, "
        f"p95 {report.replacement.classify_ms.p95} ms, max {report.replacement.classify_ms.max} ms.",
        "",
        "| strategy | case | size | frame ms | candidates ms | candidate count | "
        "distinct quantised scenes | deterministic |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for s in report.replacement.strategies:
        lines.append(f"| {s.strategy} | {s.case} | {s.size} | {s.frame_ms} | "
                     f"{s.candidates_ms} | {s.candidate_count} | "
                     f"{s.distinct_quantised_scene_count} | {s.deterministic_ordering} |")

    lines += [
        "", "### Fields not measurable before WP-SC06/SC07", "",
        f"- admitted/rejected/painted counts: {report.replacement.admitted_rejected_painted}",
        f"- solve-pass/occlusion/reanchor counters: {report.replacement.solve_pass_counters}",
        f"- sprite-cache hit rate: {report.replacement.sprite_cache_hit_rate}",
        f"- ScenePlan cache: {report.replacement.scene_plan_cache}",
        f"- decision-prose gating: {report.decision_prose_gating['gated_off_ms']} / "
        f"{report.decision_prose_gating['gated_on_ms']}",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--seeds", type=int, default=5, help="generated universes to sample")
    parser.add_argument("--sectors-per-seed", type=int, default=250,
                        help="sectors sampled per generated universe")
    parser.add_argument("--repeats", type=int, default=5,
                        help="repeats per (case, size) for cold/warm split")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the machine-readable report here")
    parser.add_argument("--md", type=Path, default=None,
                        help="write the human-readable summary here")
    args = parser.parse_args(argv)

    report = run_benchmark(seeds=args.seeds, sectors_per_seed=args.sectors_per_seed,
                           repeats=args.repeats)
    payload = _to_jsonable(report)

    if args.json is not None:
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    if args.md is not None:
        args.md.write_text(render_markdown(report))
    if args.json is None and args.md is None:
        print(json.dumps(payload, indent=2))
        print()
        print(render_markdown(report))


if __name__ == "__main__":
    main()
