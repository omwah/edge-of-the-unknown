"""Legacy-vs-physical-model scene parity measurement (WP-SC12).

The acceptance bar for replacing the legacy `_SceneComposer`
(`edge/tui/widgets.py`) is stated in
`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §9.6's "Station size parity"
section and reduces to two claims, both measured here over the full
`edge.tui.scene_gallery.cases()` x `SIZES` matrix, for both projection
strategies:

**Admission parity.** Every object the legacy composer actually *paints* for
a given sector DTO and canvas is also painted by the new pipeline. Legacy has
no admission solver: it paints the primary body, the one station
(`_paint_station` draws the first starbase, else the first port), each
discovery, and up to `SceneArtConfig.max_ships_shown` ships, degrading an
object that finds no free sky to a text row (`_SceneComposer._deferred`).
A text row is *not* painted art, so it is not part of the parity target --
this harness reads the composer's own `sprite_rects`, which records exactly
what was drawn.

**Station size parity.** A painted port/Stardock/starbase lands on the same
**authored ladder rung** the legacy composer selects. The rung, not the
ink-cropped cell box, is the size decision: the sprite library picks a tier
from the requested *height* alone and then ink-crops it, and the crop varies
with the render seed (legacy seeds a port from `sector_id`, the physical
model from `port_id`), so two renders of the same tier can differ by a cell
or two in either axis. Both the rung and the cell box are reported, so a
reader can see the residual crop delta as well as the tier match.

Deliberately *not* parity targets, because the goal names stations:

* the primary body's own size -- §4.7/§4.17 forbid cropping, and a 60x30 su
  anchor face at `cell_aspect` 2 projects `w = 4h`, so the largest whole
  anchor a viewport can hold is `(width - 2*edge_margin)/4` cells, below the
  legacy composer's deliberately-cropped disc on a narrow canvas;
* ship size -- legacy sizes traffic by band index off its own scale chain,
  which is a different mechanism, not a smaller/larger version of this one.
  Ships are held to admission parity only.

Usage::

    pixi run python -m edge.devtool.scene_parity
    pixi run python -m edge.devtool.scene_parity --json parity.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from edge.art.geometry_catalog import load_geometry_catalog
from edge.art.scene_paint import resolve_scene
from edge.art.scene_tuning import build_continuous_yields, build_scene_tuning
from edge.config import load_config
from edge.core.config import SceneArtConfig
from edge.core.dto import SectorDTO
from edge.scene.catalog import ArtGeometryCatalog, LadderKey
from edge.scene.classify import classify_sector
from edge.scene.geometry import CellBox
from edge.scene.model import PhysicalObject, SceneTuning
from edge.scene.project import DepthLayeredAnchorProjection, FixedFovPerspective, ProjectionStrategy
from edge.scene.solve import solve
from edge.tui.scene_gallery import SIZES, cases
from edge.tui.widgets import _SceneComposer, primary_body_height

STRATEGIES: tuple[ProjectionStrategy, ...] = (
    FixedFovPerspective(),
    DepthLayeredAnchorProjection(),
)

STATION_KINDS: tuple[str, ...] = ("port", "stardock", "starbase")

_LADDER_SUBTYPE = {"port": "trading_port", "stardock": "stardock", "starbase": "starbase"}
"""Legacy `sprite_rects` station kind -> `LadderKey.subtype`, matching
`edge.scene.classify._port_ladder_subtype` / `_starbase_object`."""

_SLOT = {"port": "station", "stardock": "station", "starbase": "station",
         "planet": "body", "belt": "body"}
"""Legacy `sprite_rects` kinds that map onto one *singleton* parity slot.
Legacy draws exactly one primary body and exactly one station, whichever kind
each turns out to be, and the physical model tags them `planet`/`port`/
`starbase`; comparing by slot rather than by tag is what lets a Stardock
(legacy tag `stardock`, model tag `port`) and a belt (legacy tag `belt`,
model tag `planet`) join up."""


@dataclass(frozen=True, slots=True)
class Painted:
    """One object a composer actually drew."""

    slot: str
    """`"body"`, `"station"`, `"discovery"`, `"wreck"`, or `"ship:<name>"`."""
    kind: str
    width: int
    height: int
    rung: int | None
    """Authored ladder rung index, for a station; `None` otherwise."""


@dataclass
class CellResult:
    """One (case, canvas, strategy) cell of the parity matrix."""

    case: str
    width: int
    height: int
    strategy: str
    legacy: tuple[Painted, ...] = ()
    physical: tuple[Painted, ...] = ()
    missing: tuple[str, ...] = ()
    """Slots legacy painted that the physical model did not."""
    extra: tuple[str, ...] = ()
    """Slots the physical model painted that legacy did not (never a failure;
    admitting more than legacy is the stated direction of travel)."""
    size_mismatch: tuple[tuple[str, int | None, int | None], ...] = ()
    """`(slot, legacy_rung, physical_rung)` for every station whose rung
    differs."""

    @property
    def scene_id(self) -> str:
        return f"{self.case}@{self.width}x{self.height}!{self.strategy}"

    @property
    def admission_ok(self) -> bool:
        return not self.missing

    @property
    def size_ok(self) -> bool:
        return not self.size_mismatch


# ---------------------------------------------------------------------------
# Legacy side.
# ---------------------------------------------------------------------------


def legacy_station_rung(
    catalog: ArtGeometryCatalog, kind: str, archetype_id: str, target_height: int
) -> int | None:
    """The authored rung the legacy composer's requested box resolves to.

    The sprite library selects a tier from the requested **height** alone
    (`edge/art/sprites.py::fit_box`'s own docstring), so the rung is the
    richest one whose natural height fits the request, falling back to the
    worst when none does. Verified against the real renderer across
    `height` 3..17 for all three station subtypes: the drawn ink box is a
    step function of the requested height whose steps land exactly on these
    rung boundaries.
    """
    rungs = catalog.rungs(
        LadderKey(kind="port", subtype=_LADDER_SUBTYPE[kind], axis="vertical",
                  archetype_id=archetype_id)
    )
    if not rungs:
        return None
    fits = [r for r in rungs if r.natural.height <= target_height]
    if fits:
        return max(fits, key=lambda r: (r.natural.height, -r.index)).index
    return max(r.index for r in rungs)


def measure_legacy(
    sector: SectorDTO, cfg: SceneArtConfig, catalog: ArtGeometryCatalog, w: int, h: int
) -> tuple[Painted, ...]:
    """What the legacy `_SceneComposer` actually painted, by parity slot."""
    composer = _SceneComposer(sector, cfg)
    composer.compose(w, h)

    # Legacy's own station target, taken from the same inputs `_paint_station`
    # is handed: `body_height` is the header-less body budget, and
    # `primary_height` is the *rendered* primary body's height — read straight
    # off the rect the composer just placed, and passed only when that body is
    # a planet or belt. Reading the rect rather than recomputing
    # `primary_body_height` keeps the belt case exact (a belt skips the
    # ship-sky trim) and absorbs any bottom-edge clipping.
    hdr = 4 if not sector.beacon else 5
    body_h = h - hdr
    primary_height: int | None = None
    if sector.planets:
        primary_height = next(
            (y1 - y0 for kind, _x0, y0, _x1, y1 in composer.sprite_rects
             if kind in ("planet", "belt")),
            primary_body_height(cfg, w, body_h),
        )

    # Ships are recorded by name so admission parity compares the *same*
    # vessels, not just a count. Legacy paints `sec.ships[:max_ships_shown]`
    # minus whatever `_paint_ships` deferred to a text row -- and it appends to
    # `sprite_rects` in **reverse** DTO order, because `_paint_ships` places
    # nearest-first (`for i in reversed(range(n))`). Reversing here is what
    # pairs each recorded rect with the vessel that actually drew it; without
    # it the name set still matched (so admission parity was right) but every
    # per-ship size was attached to the wrong hull.
    shown = [s.name for s in sector.ships[: cfg.max_ships_shown]]
    deferred = "\n".join(text for text, _dest, _ref in composer._deferred)
    painted_ships = [name for name in shown if name not in deferred]
    ship_iter = iter(reversed(painted_ships))

    out: list[Painted] = []
    for kind, x0, y0, x1, y1 in composer.sprite_rects:
        cw, ch = x1 - x0, y1 - y0
        rung: int | None = None
        if kind in STATION_KINDS:
            target_w, target_h = cfg.station_dimensions(
                kind, primary_height=primary_height, body_height=body_h  # type: ignore[arg-type]
            )
            del target_w
            rung = legacy_station_rung(catalog, kind, _archetype_of(sector, kind), target_h)
        if kind == "ship":
            # No `'?'` default: a count mismatch between `sprite_rects` and the
            # deferral list is a harness bug, and a `ship:?` slot would quietly
            # *match* a `ship:?` on the other side instead of failing.
            slot = f"ship:{next(ship_iter)}"
        else:
            slot = _SLOT.get(kind, kind)
            if slot == "discovery":
                # Legacy can paint two finds (a primary phenomenon and a
                # secondary wreck) and tags both "discovery"; the model tags
                # a wreck separately. Distinguish by the DTO.
                slot = "discovery"
        out.append(Painted(slot=slot, kind=kind, width=cw, height=ch, rung=rung))
    # Legacy paints its discoveries in a fixed order (primary find, then the
    # secondary wreck); disambiguate repeated "discovery" slots by index so a
    # two-find scene compares element-wise.
    assert next(ship_iter, None) is None, (
        f"legacy painted fewer ship rects than names it kept for {sector.sector_id}"
    )
    seen: Counter[str] = Counter()
    numbered: list[Painted] = []
    for entry in out:
        if entry.slot == "discovery":
            seen["discovery"] += 1
            n = seen["discovery"]
            numbered.append(
                Painted(slot=f"discovery#{n}", kind=entry.kind, width=entry.width,
                        height=entry.height, rung=entry.rung))
        else:
            numbered.append(entry)
    return tuple(numbered)


def _archetype_of(sector: SectorDTO, kind: str) -> str:
    if kind == "starbase" and sector.starbases:
        return sector.starbases[0].archetype_id or ""
    if sector.ports:
        return sector.ports[0].archetype_id or ""
    return ""


# ---------------------------------------------------------------------------
# Physical-model side.
# ---------------------------------------------------------------------------


def measure_physical(
    sector: SectorDTO,
    strategy: ProjectionStrategy,
    tuning: SceneTuning,
    catalog: ArtGeometryCatalog,
    w: int,
    h: int,
) -> tuple[Painted, ...]:
    """What the new pipeline actually painted, by the same parity slots.

    Reads `edge.art.scene_paint.resolve_scene`'s output, not the solver's
    `ScenePlan`: the paint stage runs its own bounded validation correction
    and occlusion re-check, so an object can be admitted by the solve and
    still not reach the screen. The goal is about what is *shown*.
    """
    arrangement, _glyphs = classify_sector(sector, tuning)
    plan = solve(arrangement, CellBox(0, 0, w, h), tuning, catalog, strategy)
    paint = resolve_scene(plan, arrangement, catalog, tuning)
    objects: dict[object, PhysicalObject] = {o.key: o for o in arrangement.objects}
    projections = {p.key: p for p in plan.projections}

    finds = 0
    out: list[Painted] = []
    for obj in paint.painted:
        physical = objects[obj.key]
        tag = obj.key.tag
        box = obj.scene_box
        rung: int | None = None
        if tag == "planet":
            slot = "body"
        elif tag in ("port", "starbase"):
            slot = "station"
            projection = projections.get(obj.key)
            rung = projection.rung.index if projection is not None and projection.rung else None
        elif tag == "discovery":
            finds += 1
            slot = f"discovery#{finds}"
        elif tag == "wreck":
            finds += 1
            slot = f"discovery#{finds}"
        else:
            slot = f"ship:{physical.label}"
        out.append(Painted(slot=slot, kind=tag, width=box.width, height=box.height, rung=rung))
    return tuple(out)


# ---------------------------------------------------------------------------
# The matrix.
# ---------------------------------------------------------------------------


def build_pipeline() -> tuple[SceneTuning, ArtGeometryCatalog]:
    """The real, shipped `scene.physical_model` calibration -- never invented
    numbers (plan §5)."""
    physical_model = load_config("config/default.yaml").scene.physical_model
    return build_scene_tuning(physical_model), load_geometry_catalog(
        build_continuous_yields(physical_model)
    )


def run_matrix(
    *,
    tuning: SceneTuning | None = None,
    catalog: ArtGeometryCatalog | None = None,
    art_cfg: SceneArtConfig | None = None,
) -> list[CellResult]:
    """Every `cases()` x `SIZES` x strategy cell, measured on both sides."""
    if tuning is None or catalog is None:
        tuning, catalog = build_pipeline()
    cfg = art_cfg if art_cfg is not None else SceneArtConfig()

    results: list[CellResult] = []
    for case, sector in cases().items():
        for _label, w, h in SIZES:
            legacy = measure_legacy(sector, cfg, catalog, w, h)
            for strategy in STRATEGIES:
                physical = measure_physical(sector, strategy, tuning, catalog, w, h)
                results.append(_compare(case, w, h, strategy.name, legacy, physical))
    return results


def _compare(
    case: str, w: int, h: int, strategy: str,
    legacy: tuple[Painted, ...], physical: tuple[Painted, ...],
) -> CellResult:
    legacy_by_slot = {entry.slot: entry for entry in legacy}
    physical_by_slot = {entry.slot: entry for entry in physical}
    missing = tuple(sorted(set(legacy_by_slot) - set(physical_by_slot)))
    extra = tuple(sorted(set(physical_by_slot) - set(legacy_by_slot)))
    mismatch: list[tuple[str, int | None, int | None]] = []
    for slot, legacy_entry in sorted(legacy_by_slot.items()):
        if slot != "station":
            continue
        physical_entry = physical_by_slot.get(slot)
        if physical_entry is None:
            continue  # already reported as an admission miss
        if legacy_entry.rung != physical_entry.rung:
            mismatch.append((slot, legacy_entry.rung, physical_entry.rung))
    return CellResult(
        case=case, width=w, height=h, strategy=strategy,
        legacy=legacy, physical=physical,
        missing=missing, extra=extra, size_mismatch=tuple(mismatch),
    )


# ---------------------------------------------------------------------------
# Reporting.
# ---------------------------------------------------------------------------


@dataclass
class Summary:
    cells: int = 0
    admission_ok: int = 0
    size_ok: int = 0
    legacy_objects: int = 0
    matched_objects: int = 0
    stations: int = 0
    stations_same_rung: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def admission_rate(self) -> float:
        return self.matched_objects / self.legacy_objects if self.legacy_objects else 1.0


def summarize(results: list[CellResult], strategy: str | None = None) -> Summary:
    summary = Summary()
    for cell in results:
        if strategy is not None and cell.strategy != strategy:
            continue
        summary.cells += 1
        summary.admission_ok += cell.admission_ok
        summary.size_ok += cell.size_ok
        summary.legacy_objects += len(cell.legacy)
        summary.matched_objects += len(cell.legacy) - len(cell.missing)
        stations = [e for e in cell.legacy if e.slot == "station"]
        summary.stations += len(stations)
        summary.stations_same_rung += len(stations) - len(cell.size_mismatch) - sum(
            1 for e in stations if e.slot in cell.missing
        )
        if cell.missing:
            summary.failures.append(f"{cell.scene_id}: missing {list(cell.missing)}")
        for slot, legacy_rung, physical_rung in cell.size_mismatch:
            summary.failures.append(
                f"{cell.scene_id}: {slot} rung {physical_rung} != legacy {legacy_rung}"
            )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, help="write the full matrix here")
    parser.add_argument("--verbose", action="store_true", help="list every cell")
    args = parser.parse_args()

    results = run_matrix()
    for strategy in (s.name for s in STRATEGIES):
        summary = summarize(results, strategy)
        print(f"\n=== {strategy}")
        print(f"  cells                    {summary.cells}")
        print(f"  admission-parity cells   {summary.admission_ok}/{summary.cells}")
        print(f"  station-size cells       {summary.size_ok}/{summary.cells}")
        print(f"  legacy objects matched   {summary.matched_objects}/{summary.legacy_objects}"
              f"  ({100 * summary.admission_rate:.1f}%)")
        print(f"  stations on legacy rung  {summary.stations_same_rung}/{summary.stations}")
        for failure in summary.failures:
            print(f"    FAIL {failure}")

    if args.verbose:
        for cell in results:
            print(f"\n{cell.scene_id}")
            print(f"  LEG {[(e.slot, e.width, e.height, e.rung) for e in cell.legacy]}")
            print(f"  NEW {[(e.slot, e.width, e.height, e.rung) for e in cell.physical]}")

    if args.json:
        args.json.write_text(
            json.dumps(
                [
                    {
                        "scene": cell.scene_id,
                        "legacy": [asdict(e) for e in cell.legacy],
                        "physical": [asdict(e) for e in cell.physical],
                        "missing": list(cell.missing),
                        "extra": list(cell.extra),
                        "size_mismatch": [list(m) for m in cell.size_mismatch],
                    }
                    for cell in results
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
