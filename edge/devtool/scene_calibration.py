"""Calibration review tool for the sector scene physical model (WP-SC05).

`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §5 ("Calibration gate: no unapproved
numerical defaults") lists every numeric value the replacement scene composer
needs before it can ship. WP-SC04 already picked no production strategy (both
`FixedFovPerspective` and `DepthLayeredAnchorProjection` remain live pending that
approval — see `docs/SCENE_BENCHMARK_BASELINE.md` §0), so this tool drives the
*real* production `edge.scene.classify.classify_sector` and *both* strategies
against a matrix of representative sectors and a set of **proposed** — not
shipped — numeric values, and renders a review sheet a human goes through
bullet-by-bullet.

**This tool never writes to `config/default.yaml`.** `SceneArtConfig` forbids
unknown keys (WP-SC02), so the new `scene:` values stay out of shipped config
until a human approves them here and a later commit adds them with schema
validation. Every number below is a *proposal* for review, not a default.

Usage::

    pixi run python -m edge.devtool.scene_calibration
    pixi run python -m edge.devtool.scene_calibration --json out.json --md out.md

**Scope note (read before trusting a number here):** `edge/scene/solve.py`
(the constraint solver, WP-SC06) has since landed with a real
admission/rejection loop, anchor box-class step-down, occlusion pass, and
glyph scatter -- but this tool was written, and its matrix traced, against
only classification (WP-SC02) and each strategy's own
`frame()`/`candidates()`/`project()` (WP-SC03); it does not call `solve()`
itself. So every per-object row below is this tool's own `frame()`/`project()`
walk against the proposed tuning, not the real solver's admission decision:
`decision` labels every non-anchor object `would-accept (pending WP-SC06 hard
rules)` or `would-reject: <reason>` from a near-plane check alone, never a
real separation/occlusion/cost verdict, and every occlusion-shaped field
(visible fraction) is an explicit hand-rolled placeholder rather than
`solve()` output. Wiring this tool through the real `solve()` -- now that it
exists -- to report actual admission/rejection/occlusion/cost-spend is called
out as follow-up work in this report's open-questions section rather than
attempted in this pass, so nothing here is silently presented as more than
what it is: a classification + framing review, not a full solve review.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from edge.art.geometry_catalog import JsonArtGeometryCatalog, load_default_geometry_catalog
from edge.core.dto import (
    SectorAnomalyDTO,
    SectorDTO,
    SectorPlanetDTO,
    SectorShipDTO,
)
from edge.scene.catalog import ArtGeometryCatalog, ContinuousYield, LadderKey, LadderRung
from edge.scene.classify import classify_sector
from edge.scene.geometry import CellBox, Region
from edge.scene.model import PhysicalObject, SceneTuning
from edge.scene.project import (
    DepthLayeredAnchorProjection,
    FixedFovPerspective,
    ProjectionStrategy,
    hysteresis_delta,
)
from edge.tui.scene_gallery import SIZES, _base, _find, _port, _sector, cases as gallery_cases

REPORT_LABEL = "PENDING HUMAN REVIEW / APPROVAL"
"""Stamped throughout the output. This tool proposes; it does not approve
(plan §5: "none becomes a shipped default without review")."""

# The canvas set the WP-SC04 benchmark already froze (plan §6.1); reused here
# so the calibration cells and the benchmark numbers describe the same scenes.
CALIBRATION_SIZES: tuple[tuple[str, int, int], ...] = SIZES


# ---------------------------------------------------------------------------
# Section 1: proposed SceneTuning + ContinuousYield values, with rationale
# ---------------------------------------------------------------------------


@dataclass
class ProposedValue:
    """One §5 line item: a proposed number/choice plus why, for human review."""

    field: str
    proposal: str
    rationale: str


def _proposed_region() -> Region:
    # Scene units carry no fixed real-world scale (plan §9.1): this box only
    # needs to be large enough that every scale class's placement freedom
    # comfortably fits without objects colliding by construction.
    return Region(x_min=-200, x_max=200, y_min=-100, y_max=100, z_min=1, z_max=400)


def proposed_tuning() -> tuple[SceneTuning, list[ProposedValue]]:
    """The tool's proposed `SceneTuning`, paired with the reviewable rationale
    for each field it sets. Nothing here is a shipped default (plan §5)."""

    region = _proposed_region()
    notes: list[ProposedValue] = []

    # Nominal face areas (plan §2.2's apparent-scale hierarchy, exaggerated
    # display scale rather than literal km — see the open question in §5 of
    # this report about the single shared "anchor" bucket covering the
    # planet/nebula/black_hole/wormhole scale class).
    face_extent_by_scale_class = {
        "entity": (34, 14),      # area 476 — the foreground subject; largest of all
        "anchor": (60, 30),      # area 1800 — shared planet/discovery bucket
        "belt": (90, 16),        # area 1440 — wide flat permeable field
        "orbital": (14, 7),      # area 98 — station; below anchor, above wreck/ship
        "wreck": (16, 6),        # area 96 — "slightly larger than ships" (plan §2.2)
        "ship": (12, 5),         # area 60
    }
    notes.append(ProposedValue(
        "face_extent_by_scale_class",
        repr(face_extent_by_scale_class),
        "Preserves plan §2.2's ordering (entity > anchor > belt > orbital > "
        "wreck > ship) as bounding-box area (plan §9.1). Numbers are display "
        "scene units, not literal kilometres — the composer already exaggerates "
        "controlled ratios to stay legible at terminal resolution (plan §2.3). "
        "`\"anchor\"` here is now only the fallback bucket a planet uses (and "
        "any anchor-scale kind with no `face_extent_by_kind` override) — see "
        "`face_extent_by_kind` below for the per-kind nebula/black_hole/"
        "wormhole distinction plan §2.2 asks for."))

    # Per-kind override (WP-SC02 model addition: `SceneTuning.face_extent_by_kind`,
    # `edge/scene/classify.py` `_face`). `classify_sector` looks this up first by
    # `PhysicalObject.continuous_kind`, falling back to `face_extent_by_scale_class`
    # ("anchor") for any kind not listed here -- a plain planet keeps using the
    # "anchor" bucket unchanged. Areas below express plan §2.2's apparent-scale
    # hierarchy: nebula/black_hole visual system ≫ wormhole > planet, all as
    # bounding-box width*height (plan §9.1), and all ≫ the "anchor" fallback
    # (1800) a bare planet uses, since these are hierarchy-topping phenomena.
    face_extent_by_kind = {
        "nebula": (110, 60),      # area 6600 — the largest phenomenon: a diffuse field
        "black_hole": (100, 60),  # area 6000 — comparable to nebula, slightly tighter
        "wormhole": (76, 40),     # area 3040 — clearly bigger than a bare planet (1800),
                                   # clearly smaller than nebula/black_hole
    }
    notes.append(ProposedValue(
        "face_extent_by_kind",
        repr(face_extent_by_kind),
        "Resolves the OPEN QUESTION this review previously flagged: "
        "`classify_sector` looked up face extent by `scale_class` alone, so a "
        "planet and every anchor-scale discovery (nebula/black_hole/wormhole) "
        "shared the single \"anchor\" bucket and could not express \"wormhole "
        "slightly larger than planet\" or \"nebula ≫ wormhole\" as a face-area "
        "distinction (only the FaceShape -- ellipse vs circle -- differed). "
        "`SceneTuning` now carries `face_extent_by_kind`, keyed by "
        "`continuous_kind`, which `_face()` consults before falling back to "
        "`face_extent_by_scale_class[\"anchor\"]`; §2.1 still guarantees a "
        "planet and an anchor-scale discovery never coexist in one sector, so "
        "this is purely a display-size distinction, never an occlusion "
        "concern. Ordering: nebula (6600) ≈ black_hole (6000) ≫ wormhole "
        "(3040) > planet/anchor-fallback (1800), matching plan §2.2's stated "
        "hierarchy."))

    region = _proposed_region()
    wide_region = Region(x_min=-320, x_max=320, y_min=-160, y_max=160, z_min=1, z_max=520)
    region_by_scale_class = {
        cls: (wide_region if cls in ("ship", "wreck") else region)
        for cls in ("entity", "anchor", "belt", "orbital", "wreck", "ship")
    }
    notes.append(ProposedValue(
        "region_by_scale_class",
        f"ship/wreck: {wide_region!r}; every other class: {region!r}",
        "Resolves the OPEN QUESTION this review previously flagged: a single "
        "shared region for every scale class did not differentiate ship/wreck "
        "placement freedom from station orbital freedom by size, though "
        "`SceneTuning.region_by_scale_class`'s type (`Mapping[str, Region]`) "
        "was already per-scale-class-capable -- this was purely a proposed-"
        "value gap, not a model gap. Per plan §2.5 (\"[ships] receive wider "
        "placement regions/depth ranges than stations\"), ship/wreck now get a "
        "noticeably wider box on every axis (x/y span +60%, z span +30%) than "
        "the shared region every other class (entity/anchor/belt/orbital) "
        "keeps -- orbital placement stays tied to its parent planet's own "
        "narrower placement per the field's docstring, so it should not widen "
        "independently of the anchor it orbits."))

    target_fraction_by_scale_class = {
        "entity": Fraction(1, 3), "anchor": Fraction(1, 2), "belt": Fraction(1, 2),
        "orbital": Fraction(1, 5), "wreck": Fraction(1, 8), "ship": Fraction(1, 8),
    }
    notes.append(ProposedValue(
        "target_fraction_by_scale_class",
        repr({k: str(v) for k, v in target_fraction_by_scale_class.items()}),
        "The Entity frames tighter than a planet/phenomenon (1/3 vs 1/2 of "
        "viewport height) so it reads as a close subject rather than a "
        "backdrop; ships/wrecks are rarely the anchor (only when nothing else "
        "is present) so their fraction is small and mostly theoretical."))

    ink_ratio_by_scale_class = {
        "entity": Fraction(4, 5), "anchor": Fraction(3, 5), "belt": Fraction(1, 3),
        "orbital": Fraction(9, 10), "wreck": Fraction(4, 5), "ship": Fraction(9, 10),
    }
    notes.append(ProposedValue(
        "ink_ratio_by_scale_class",
        repr({k: str(v) for k, v in ink_ratio_by_scale_class.items()}),
        "Seed ratio `frame()` uses before a laddered anchor snaps to its own "
        "rung's exact ratio (plan §9.5). Ships/stations are dense authored art "
        "(little padding, 9/10); planets/nebulae fade toward the edge "
        "(3/5); belts are the sparsest (1/3, permeable field, plan §2.5)."))

    structural_mode_thresholds = (
        (120, 44, "wide"), (87, 36, "standard"), (0, 0, "compact"),
    )
    notes.append(ProposedValue(
        "structural_mode_thresholds",
        repr(structural_mode_thresholds),
        "Plan §9.1 names exactly three modes (wide/standard/compact); the "
        "thresholds reuse the WP-SC04 benchmark canvas breakpoints (87x36, "
        "120x44) so mode selection lines up with the sizes already measured, "
        "collapsing the benchmark's four labels to the plan's three names."))

    fixed_fov_num, fixed_fov_den = 1, 2
    notes.append(ProposedValue(
        "fixed_fov_num / fixed_fov_den",
        f"{fixed_fov_num}/{fixed_fov_den}",
        "A gentle half-angle (visible height per depth unit) keeps distant "
        "admitted objects legible instead of shrinking sharply toward the "
        "frame edges; matches the value the WP-SC04 benchmark already "
        "exercised for continuity between the two review passes."))

    cell_aspect = Fraction(2, 1)
    notes.append(ProposedValue(
        "cell_aspect", str(cell_aspect),
        "Matches the shipped composer's existing `width = 2 * height` disc "
        "rule (`docs/SECTOR_SCENE_COMPOSITION.md`), so cutover does not "
        "silently change the terminal's visual proportions."))

    near_plane_su = 1
    notes.append(ProposedValue("near_plane_su", str(near_plane_su),
                                "Smallest workable positive depth; effectively "
                                "\"do not let anything sit on the camera plane.\""))

    depth_layers, depth_layer_size_su, depth_layer_scale = 8, 6, Fraction(4, 5)
    notes.append(ProposedValue(
        "depth_layers / depth_layer_size_su / depth_layer_scale",
        f"{depth_layers} / {depth_layer_size_su} / {depth_layer_scale}",
        "8 layers give `DepthLayeredAnchorProjection` enough depth resolution "
        "to distinguish near/mid/far traffic without an unbounded search "
        "space; a 4/5 per-layer scale gives roughly a 20% size step between "
        "adjacent layers, which is visually distinguishable at terminal "
        "resolution without ships snapping between wildly different sizes."))

    camera_height_fraction_min = Fraction(1, 8)
    camera_height_fraction_max = Fraction(3, 4)
    notes.append(ProposedValue(
        "camera_height_fraction_min / _max", f"{camera_height_fraction_min} / "
        f"{camera_height_fraction_max}",
        "Bounds the framing-height sweep `candidates()` explores (plan §9.6): "
        "never frame an anchor smaller than 1/8 of the viewport (illegible) "
        "or larger than 3/4 (crowds out everything else)."))

    aim_offsets_su = (0, -2, 2, -4, 4, -6, 6)
    notes.append(ProposedValue(
        "aim_offsets_su", repr(aim_offsets_su),
        "Centre-out, symmetric, bounded horizontal reframe search — enough "
        "range to dodge a collision without the candidate search degenerating "
        "into a full raster scan (plan §6.2 rule 4)."))

    max_camera_candidates = 64
    notes.append(ProposedValue(
        "max_camera_candidates", str(max_camera_candidates),
        "Hard cap on `candidates()` output; keeps the bounded search bounded "
        "in the literal sense plan §6.2 rule 4 requires. 64 = the height "
        "sweep (roughly a dozen distinct rung/cell heights in practice) times "
        "the 7 aim offsets above, rounded up for headroom."))

    hysteresis_weight_camera = 1
    hysteresis_weight_position = 1
    hysteresis_weight_admission = 4
    hysteresis_weight_art = 1
    notes.append(ProposedValue(
        "hysteresis weights (camera/position/admission/art)",
        f"{hysteresis_weight_camera}/{hysteresis_weight_position}/"
        f"{hysteresis_weight_admission}/{hysteresis_weight_art}",
        "Admission changes (an object popping in/out) are the most visually "
        "jarring resize artifact, so that term is weighted 4x the others; "
        "camera/position/art-size churn are weighted equally as comparatively "
        "minor wobble."))

    # -- WP-SC06 solver bounds (landed after this tool's first pass; the
    # numbers below replace what used to be `extended_proposals()` guesses
    # for these same concepts now that `SceneTuning` has real fields for
    # them). Rationale mirrors the WP-SC06 field docstrings in
    # `edge/scene/model.py`.
    max_passes = 24
    notes.append(ProposedValue(
        "max_passes", str(max_passes),
        "Hard bound on the whole solve pass loop (plan §9.6, §6.2 rule 4): "
        "covers a handful of reposition attempts, at most one reanchor, and "
        "a few box-class step-downs before the loop must terminate."))

    edge_margin = 1
    notes.append(ProposedValue("edge_margin", str(edge_margin),
                                "One cell of clearance from every viewport edge "
                                "(plan §2.4: \"retain separation and edge margins "
                                "rather than eliminate every void cell\")."))

    min_projected_cells_by_scale_class = {
        "entity": (4, 2), "anchor": (6, 3), "belt": (6, 2),
        "orbital": (3, 2), "ship": (3, 1), "wreck": (3, 1),
    }
    notes.append(ProposedValue(
        "min_projected_cells_by_scale_class", repr(min_projected_cells_by_scale_class),
        "Below these cell dimensions an object reads as noise rather than "
        "its own shape; stations/ships need at least 2-3 cells on their "
        "short axis to read as a rectangle rather than a dot."))

    min_rung_index_from_end_by_scale_class = {"orbital": 1}
    notes.append(ProposedValue(
        "min_rung_index_from_end_by_scale_class", repr(min_rung_index_from_end_by_scale_class),
        "Minimum-richness floor: never select the worst 1 rung of a "
        "port/starbase/stardock's 4-rung ladder (maintainer feedback that "
        "composers were shrinking to the worst tier, which the "
        "min_projected_cells floor above does not prevent since it is "
        "smaller than every ladder's smallest rung). `ship` is deliberately "
        "excluded: measurement showed the same floor on ships collapses "
        "DepthLayeredAnchorProjection admission from ~99% to ~3% via its "
        "coarse per-layer depth-scale step -- a depth-layer-granularity fix "
        "is needed first."))

    separation_margin = 1
    notes.append(ProposedValue("separation_margin", str(separation_margin),
                                "Matches edge_margin: one blank cell of clearance "
                                "between distinct accepted objects' ink-max boxes "
                                "(plan §9.6 attempt rule 4)."))

    min_visible_fraction_by_scale_class = {
        "entity": Fraction(1, 1), "anchor": Fraction(1, 1), "belt": Fraction(1, 1),
        "orbital": Fraction(3, 4), "ship": Fraction(3, 4), "wreck": Fraction(3, 4),
    }
    notes.append(ProposedValue(
        "min_visible_fraction_by_scale_class",
        repr({k: str(v) for k, v in min_visible_fraction_by_scale_class.items()}),
        "The Entity and the framing anchor (planet/belt/discovery) are never "
        "partially occluded by construction in every case this tool traced, "
        "so their floor is 1 (fully visible or rejected); wrecks/ships/"
        "stations may be legitimately partly hidden behind a nearer object "
        "but must stay at least 3/4 visible to remain readable (plan §2.5)."))

    cost_budget = 250
    notes.append(ProposedValue(
        "cost_budget", str(cost_budget),
        "Same scale as the catalogue's measured `render_cost` units (plan "
        "§9.4): the checked-in ship/port rungs measure in the tens, and the "
        "nebula's richest proposed box class above costs 110 -- this budget "
        "comfortably covers one rich anchor plus a handful of laddered "
        "ships, and is deliberately tight enough that the cost-pressure "
        "illustration below actually engages."))

    emergency_ship_ceiling = 40
    notes.append(ProposedValue(
        "emergency_ship_ceiling", str(emergency_ship_ceiling),
        "Protects against estimator/pathological-input failure (plan §2.3) "
        "well above any generated-universe DTO inventory the WP-SC04 "
        "benchmark measured, but comfortably below the 50-ship synthetic "
        "stress case (plan §6.3) so that case still exercises the ceiling."))

    max_reposition_candidates = 16
    notes.append(ProposedValue(
        "max_reposition_candidates", str(max_reposition_candidates),
        "Bounded reposition search (plan §9.6 step 1) -- enough positions "
        "inside a flexible object's region to usually dodge a collision "
        "without an unbounded scan."))

    max_glyph_tries = 20
    glyph_spacing = 2
    notes.append(ProposedValue(
        "max_glyph_tries / glyph_spacing", f"{max_glyph_tries} / {glyph_spacing}",
        "Plan §9.6's glyph scatter: 20 free-cell attempts per fighter/mine "
        "glyph before giving up to the sidebar, spaced 2 cells apart so a "
        "fighter garrison doesn't read as one solid block."))

    tuning = SceneTuning(
        face_extent_by_scale_class=face_extent_by_scale_class,
        face_extent_by_kind=face_extent_by_kind,
        region_by_scale_class=region_by_scale_class,
        target_fraction_by_scale_class=target_fraction_by_scale_class,
        ink_ratio_by_scale_class=ink_ratio_by_scale_class,
        structural_mode_thresholds=structural_mode_thresholds,
        fixed_fov_num=fixed_fov_num, fixed_fov_den=fixed_fov_den,
        cell_aspect=cell_aspect, near_plane_su=near_plane_su,
        depth_layers=depth_layers, depth_layer_size_su=depth_layer_size_su,
        depth_layer_scale=depth_layer_scale,
        camera_height_fraction_min=camera_height_fraction_min,
        camera_height_fraction_max=camera_height_fraction_max,
        aim_offsets_su=aim_offsets_su, max_camera_candidates=max_camera_candidates,
        hysteresis_weight_camera=hysteresis_weight_camera,
        hysteresis_weight_position=hysteresis_weight_position,
        hysteresis_weight_admission=hysteresis_weight_admission,
        hysteresis_weight_art=hysteresis_weight_art,
        max_passes=max_passes, edge_margin=edge_margin,
        min_projected_cells_by_scale_class=min_projected_cells_by_scale_class,
        min_rung_index_from_end_by_scale_class=min_rung_index_from_end_by_scale_class,
        separation_margin=separation_margin,
        min_visible_fraction_by_scale_class=min_visible_fraction_by_scale_class,
        cost_budget=cost_budget, emergency_ship_ceiling=emergency_ship_ceiling,
        max_reposition_candidates=max_reposition_candidates,
        max_glyph_tries=max_glyph_tries, glyph_spacing=glyph_spacing,
    )
    return tuning, notes


_CONTINUOUS_PROPOSALS: dict[str, ContinuousYield] = {}


def _continuous_category(kind: str) -> str:
    """Map a `continuous_kind` (a planet's `ptype`, a discovery `kind`, or
    "entity") onto one of the small set of proposal buckets below. Not every
    `ptype` gets its own bespoke envelope yet — see the open question this
    raises in the report."""

    if kind == "asteroid_belt":
        return "belt"
    if kind in ("nebula", "black_hole", "wormhole"):
        return kind
    if kind == "wreck":
        return "wreck"
    if kind == "entity":
        return "entity"
    return "planet"  # every other ptype (terrestrial_*, jovian, barren)


def proposed_continuous_yields() -> tuple[dict[str, ContinuousYield], list[ProposedValue]]:
    """Proposed `ContinuousYield` envelopes, one per category bucket (plan §5
    "per-key ink envelopes ... continuous per-kind yields")."""

    notes: list[ProposedValue] = []

    def _yield(kind: str, *, ink_min: Fraction, ink_max: Fraction,
               min_extent: tuple[int, int], boxes: tuple[tuple[int, int], ...],
               costs: tuple[int, ...], rationale: str) -> ContinuousYield:
        y = ContinuousYield(
            kind=kind, ink_fraction_min=ink_min, ink_fraction_max=ink_max,
            min_extent=CellBox(0, 0, *min_extent),
            box_classes=tuple(CellBox(0, 0, w, h) for w, h in boxes),
            render_cost=costs,
        )
        notes.append(ProposedValue(
            f"continuous[{kind}]",
            f"ink_fraction=[{ink_min},{ink_max}] min_extent={min_extent} "
            f"box_classes={boxes} render_cost={costs}",
            rationale))
        return y

    proposals = {
        "planet": _yield(
            "planet", ink_min=Fraction(3, 5), ink_max=Fraction(9, 10),
            min_extent=(6, 3), boxes=((80, 40), (50, 25), (28, 14)),
            costs=(70, 35, 12),
            rationale="A disc render fills most of its request box (60-90%); "
            "three box classes give the anchor step-down ladder (plan §2.3) "
            "room to shrink twice before hitting the legibility floor."),
        "nebula": _yield(
            "nebula", ink_min=Fraction(2, 5), ink_max=Fraction(9, 10),
            min_extent=(10, 5), boxes=((100, 50), (64, 32), (36, 18)),
            costs=(110, 55, 20),
            rationale="Cloud phenomena are diffuse (lower ink-fraction floor "
            "than a solid disc) but can be dense at full detail; the largest "
            "of these boxes is the plan §6.1 cost-dominant case, hence the "
            "highest render_cost in this proposal set — this is the anchor "
            "the cost-pressure illustration below exercises."),
        "black_hole": _yield(
            "black_hole", ink_min=Fraction(1, 2), ink_max=Fraction(9, 10),
            min_extent=(8, 4), boxes=((90, 45), (58, 29), (32, 16)),
            costs=(100, 50, 18),
            rationale="Accretion-disc/lensing system, plan §2.1: the visible "
            "phenomenon (not just the event horizon) supplies physical scale, "
            "so its envelope is sized close to the nebula's."),
        "wormhole": _yield(
            "wormhole", ink_min=Fraction(1, 2), ink_max=Fraction(4, 5),
            min_extent=(6, 3), boxes=((50, 25), (32, 16), (18, 9)),
            costs=(40, 20, 8),
            rationale="\"Slightly larger than a planet\" (plan §2.2): smaller "
            "top box class than the planet/nebula/black_hole entries above, "
            "not a separate scale_class (see the face-area open question)."),
        "wreck": _yield(
            "wreck", ink_min=Fraction(1, 2), ink_max=Fraction(4, 5),
            min_extent=(5, 2), boxes=((24, 10), (16, 7)),
            costs=(15, 6),
            rationale="Wrecks are not laddered (they are `ArtMode.CONTINUOUS` "
            "in `classify.py`) so they get their own small envelope; two box "
            "classes are enough since a wreck never anchors a crowded scene."),
        "entity": _yield(
            "entity", ink_min=Fraction(3, 5), ink_max=Fraction(9, 10),
            min_extent=(8, 4), boxes=((40, 16), (26, 10)),
            costs=(35, 14),
            rationale="The Entity is unique per sector and never rejected for "
            "cost (plan §2.3 invariant), so its ladder only needs enough room "
            "for the anchor step-down machinery to have somewhere to go."),
        "belt": _yield(
            "belt", ink_min=Fraction(1, 5), ink_max=Fraction(1, 2),
            min_extent=(12, 3), boxes=((120, 20), (80, 14)),
            costs=(30, 12),
            rationale="Permeable field (plan §2.5): low ink fraction is "
            "expected and correct, not a rendering failure — the field is "
            "mostly negative space with traffic and stations painted through "
            "it."),
    }
    return proposals, notes


class _ProposedCatalog:
    """`ArtGeometryCatalog` for this review pass only: real ship/port ladder
    rungs from the checked-in `edge/art/geometry_catalog.json`, plus this
    tool's proposed `ContinuousYield` per category bucket (see
    `_continuous_category`). Never a source of shipped defaults."""

    def __init__(self, real: JsonArtGeometryCatalog,
                 continuous: dict[str, ContinuousYield]) -> None:
        self._real = real
        self._continuous = continuous
        self._rung_fallback_cache: dict[LadderKey, tuple[LadderRung, ...]] = {}
        self.version = f"{real.version}+wp-sc05-proposed-continuous"

    def rungs(self, key: LadderKey) -> tuple[LadderRung, ...]:
        real_rungs = self._real.rungs(key)
        if real_rungs:
            return real_rungs
        # No exact (subtype, archetype) match in the checked-in catalogue --
        # every calibration-case fixture below leaves archetype_id blank, and
        # the real catalogue is keyed by real roster archetype ids (WP-SC02
        # §9.4). Fall back to a synthetic 3-tier ladder purely so this cell's
        # arithmetic has something to chew on, exactly as the WP-SC04
        # benchmark does for the same reason -- never presented as
        # calibrated art geometry.
        cached = self._rung_fallback_cache.get(key)
        if cached is not None:
            return cached
        rungs = (
            LadderRung(tier_id="proposed-rich", index=0, natural=CellBox(0, 0, 30, 7),
                      ink_min=CellBox(0, 0, 26, 6), ink_max=CellBox(0, 0, 30, 7),
                      ink_count_min=100, ink_count_max=150, render_cost=22),
            LadderRung(tier_id="proposed-mid", index=1, natural=CellBox(0, 0, 18, 5),
                      ink_min=CellBox(0, 0, 15, 4), ink_max=CellBox(0, 0, 18, 5),
                      ink_count_min=40, ink_count_max=65, render_cost=10),
            LadderRung(tier_id="proposed-thin", index=2, natural=CellBox(0, 0, 9, 3),
                      ink_min=CellBox(0, 0, 7, 2), ink_max=CellBox(0, 0, 9, 3),
                      ink_count_min=8, ink_count_max=14, render_cost=3),
        )
        self._rung_fallback_cache[key] = rungs
        return rungs

    def continuous(self, kind: str) -> ContinuousYield:
        return self._continuous[_continuous_category(kind)]


def _load_proposed_catalog(continuous: dict[str, ContinuousYield]) -> ArtGeometryCatalog:
    return _ProposedCatalog(load_default_geometry_catalog(), continuous)


# ---------------------------------------------------------------------------
# Section 2: the required matrix cells (plan WP-SC05 bullet 2)
# ---------------------------------------------------------------------------


def _entity(contact_id: int = 900, *, contactable: bool = True) -> SectorAnomalyDTO:
    return SectorAnomalyDTO(label="a presence just beyond sensor range",
                             contact_id=contact_id, contactable=contactable)


def _hostility_ships() -> list[SectorShipDTO]:
    """Explicit hostile/neutral/friendly ships with distinct ordinals, for the
    retention-ordering matrix cell (plan §2.3, §4.6)."""

    return [
        SectorShipDTO(name="Vesk Raider", role="warship", contact_id=1,
                       retention_class="hostile", hostility_ordinal=0, combat_threat_rank=1),
        SectorShipDTO(name="Vesk Marauder", role="warship", contact_id=2,
                       retention_class="hostile", hostility_ordinal=1, combat_threat_rank=0),
        SectorShipDTO(name="Kalt Trader", role="transport", contact_id=3,
                       retention_class="neutral", hostility_ordinal=2, combat_threat_rank=2),
        SectorShipDTO(name="Aki Envoy", role="transport", contact_id=4,
                       retention_class="friendly", hostility_ordinal=3, combat_threat_rank=3),
        SectorShipDTO(name="Aki Escort", role="fighter", contact_id=5,
                       retention_class="friendly", hostility_ordinal=4, combat_threat_rank=1),
    ]


def calibration_cases() -> dict[str, SectorDTO]:
    """The required matrix cells (WP-SC05 implementation bullet 2), reusing
    `edge.tui.scene_gallery`'s existing case-building helpers where a cell is
    already covered there, and adding the cells that gallery does not build:
    Entity, a sensor-gated generated wreck, explicit hostility ordering, and
    stacked runtime wrecks alongside a planet."""

    planet = [SectorPlanetDTO(planet_id=9401, name="Corvenne", ptype="terrestrial_warm")]
    cases = dict(gallery_cases())  # reuse: port/stardock/starbase/planet/discovery/belt cells

    cases["entity+planet"] = _sector(
        901, planets=planet, anomaly=_entity())
    cases["entity+planet+hostile-ship"] = _sector(
        902, planets=planet, anomaly=_entity(),
        ships=[SectorShipDTO(name="Vesk Hunter", role="warship", contact_id=11,
                              retention_class="hostile", hostility_ordinal=0,
                              combat_threat_rank=0)])
    cases["discovery:wreck (generated, sensor-gated)"] = _sector(
        903, discoveries=[_find("wreck", "the Silent Hulk", collected=False)])
    cases["planet+port+runtime-wrecks"] = _sector(
        904, planets=planet, ports=[_port("Port Corvenne")],
        discoveries=[_find("wreck", "Marauder VII"), _find("wreck", "Kalt Drifter")])
    cases["planet+starbase(arbitrary-orbit)"] = _sector(
        905, planets=planet, starbases=[_base("Farside Watch", planet_id=None)])
    cases["hostility-ordering"] = _sector(906, ships=_hostility_ships())
    cases["cost-pressure(nebula-anchor)"] = _sector(
        907, discoveries=[_find("nebula", "the Cindered Veil")])
    return cases


# ---------------------------------------------------------------------------
# Section 3: per-cell trace (face/ink/camera/projection/cost/decision)
# ---------------------------------------------------------------------------


@dataclass
class ObjectTrace:
    key: str
    kind: str
    scale_class: str
    art_mode: str
    face_width_su: int
    face_height_su: int
    face_area_su: int
    parent: str | None
    projected_box: dict[str, int]
    depth_su: int
    art_choice: str
    ink_est_width: int
    ink_est_height: int
    render_cost: int
    visible_fraction_note: str
    decision: str


@dataclass
class CaseStrategyTrace:
    case: str
    size: str
    width: int
    height: int
    strategy: str
    camera_position: tuple[int, int, int]
    camera_aim_x: int
    candidate_count: int
    distinct_quantised_scenes: int
    anchor_key: str
    objects: tuple[ObjectTrace, ...]


def _cell_box_dict(box: CellBox) -> dict[str, int]:
    return {"col": box.col, "row": box.row, "width": box.width, "height": box.height}


def _pick_anchor(objects: tuple[PhysicalObject, ...]) -> PhysicalObject | None:
    if not objects:
        return None
    return min(objects, key=lambda o: (int(o.retention), o.key.tag, o.key.ident))


def _art_choice_and_cost(
    obj: PhysicalObject, box: CellBox, catalog: ArtGeometryCatalog,
) -> tuple[str, CellBox, int]:
    """Illustrative rung/box-class match for reporting: the nearest catalogue
    entry at or below the strategy's actual projected height. This mirrors
    (but does not duplicate) `project.py`'s private rung-snapping used inside
    `frame()` — it exists here purely to label the trace, not to make an
    admission decision (WP-SC06's job)."""

    if obj.ladder_key is not None:
        rungs = catalog.rungs(obj.ladder_key)
        if not rungs:
            return "no clearing rung (would reject, plan §4.7/§4.18)", CellBox(0, 0, 0, 0), 0
        below = [r for r in rungs if r.natural.height <= box.height]
        rung = (max(below, key=lambda r: (r.natural.height, -r.index)) if below
                else min(rungs, key=lambda r: (r.natural.height, r.index)))
        return f"rung {rung.tier_id!r} (index {rung.index})", rung.ink_min, rung.render_cost
    if obj.continuous_kind is not None:
        yield_ = catalog.continuous(obj.continuous_kind)
        below_boxes = [
            (i, b) for i, b in enumerate(yield_.box_classes) if b.height <= box.height
        ]
        idx, chosen_box = (
            min(below_boxes, key=lambda ib: ib[1].height * ib[1].width)
            if below_boxes else (len(yield_.box_classes) - 1, yield_.box_classes[-1])
        )
        ink_w = max(1, round(chosen_box.width * yield_.ink_fraction_min))
        ink_h = max(1, round(chosen_box.height * yield_.ink_fraction_min))
        return (f"box class {idx} ({chosen_box.width}x{chosen_box.height})",
                CellBox(0, 0, ink_w, ink_h), yield_.render_cost[idx])
    return "glyph (post-solve scatter, not a retained object)", CellBox(0, 0, 1, 1), 0


def trace_case(
    case_name: str, sector: SectorDTO, size_label: str, w: int, h: int,
    strategy: ProjectionStrategy, tuning: SceneTuning, catalog: ArtGeometryCatalog,
) -> CaseStrategyTrace | None:
    arrangement, _glyphs = classify_sector(sector, tuning)
    anchor = _pick_anchor(arrangement.objects)
    if anchor is None:
        return None
    viewport = CellBox(0, 0, w, h)
    anchor_pos = next(p.position for p in arrangement.placements if p.key == anchor.key)
    camera = strategy.frame(arrangement, anchor.key, viewport, tuning, catalog)
    candidates = list(strategy.candidates(camera, anchor, anchor_pos, viewport, tuning))
    boxes: set[tuple[int, int, int, int]] = set()
    for cam in candidates:
        try:
            b = strategy.project(cam, anchor, anchor_pos, viewport)
        except ValueError:
            continue
        boxes.add((b.col, b.row, b.width, b.height))

    positions = {p.key: p.position for p in arrangement.placements}
    # Retention order (plan §2.3 / §9.6's admission sort key), so a cell like
    # "hostility-ordering" reads top-to-bottom in the order a real solve
    # would consider objects, not alphabetically by generated identity.
    ordered_objects = sorted(
        arrangement.objects,
        key=lambda o: (int(o.retention), o.hostility_ordinal, -o.threat_rank, o.key),
    )
    traces: list[ObjectTrace] = []
    for obj in ordered_objects:
        pos = positions[obj.key]
        try:
            box = strategy.project(camera, obj, pos, viewport)
            decision = "anchor" if obj.key == anchor.key else "would-accept (pending WP-SC06 hard rules)"
        except ValueError as exc:
            box = CellBox(0, 0, 0, 0)
            decision = f"would-reject: {exc}"
        art_choice, ink_est, cost = _art_choice_and_cost(obj, box, catalog)
        traces.append(ObjectTrace(
            key=f"{obj.key.tag}:{obj.key.ident}", kind=obj.key.tag,
            scale_class=obj.scale_class, art_mode=obj.art_mode.value,
            face_width_su=obj.face.width_su, face_height_su=obj.face.height_su,
            face_area_su=obj.face.area_su,
            parent=(f"{obj.parent.tag}:{obj.parent.ident}" if obj.parent else None),
            projected_box=_cell_box_dict(box), depth_su=pos.z, art_choice=art_choice,
            ink_est_width=ink_est.width, ink_est_height=ink_est.height, render_cost=cost,
            visible_fraction_note="1 (assumed unoccluded; real occlusion is n/a pending "
                                   "WP-SC06 solver)",
            decision=decision,
        ))
    return CaseStrategyTrace(
        case=case_name, size=size_label, width=w, height=h, strategy=strategy.name,
        camera_position=(camera.position.x, camera.position.y, camera.position.z),
        camera_aim_x=camera.aim_x_su, candidate_count=len(candidates),
        distinct_quantised_scenes=len(boxes),
        anchor_key=f"{anchor.key.tag}:{anchor.key.ident}", objects=tuple(traces))


# ---------------------------------------------------------------------------
# Section 4: illustrative solver-adjacent computations (clearly labelled)
# ---------------------------------------------------------------------------


@dataclass
class CostPressureIllustration:
    """Plan WP-SC05 bullet 5: "a cost-pressure cell that exercises the anchor
    box-class step-down and shows the resulting framing is acceptable."
    Illustrative only — WP-SC06 owns the real step-down loop (plan §9.6)."""

    case: str
    anchor_kind: str
    box_class_sequence: list[dict[str, object]]
    proposed_cost_budget: int
    chosen_box_class_index: int
    note: str


def illustrate_cost_pressure(
    tuning: SceneTuning, catalog: ArtGeometryCatalog, cost_budget: int,
) -> CostPressureIllustration:
    case_name = "cost-pressure(nebula-anchor)"
    sector = calibration_cases()[case_name]
    arrangement, _glyphs = classify_sector(sector, tuning)
    anchor = _pick_anchor(arrangement.objects)
    assert anchor is not None and anchor.continuous_kind is not None
    yield_ = catalog.continuous(anchor.continuous_kind)
    sequence: list[dict[str, object]] = [
        {"box_class_index": i, "box": f"{b.width}x{b.height}", "render_cost": c,
         "fits_budget": c <= cost_budget}
        for i, (b, c) in enumerate(zip(yield_.box_classes, yield_.render_cost, strict=True))
    ]
    chosen = next((s for s in sequence if s["fits_budget"]), sequence[-1])
    chosen_index = chosen["box_class_index"]
    assert isinstance(chosen_index, int)
    return CostPressureIllustration(
        case=case_name, anchor_kind=anchor.continuous_kind, box_class_sequence=sequence,
        proposed_cost_budget=cost_budget, chosen_box_class_index=chosen_index,
        note="Illustrative manual walk of the anchor's box_classes ladder "
             "(descending) against the proposed cost budget, stopping at the "
             "first class whose render_cost fits — exactly the order plan "
             "§2.3/§4.14 describe for the real step-down loop, which "
             "WP-SC06's solver performs automatically and never below the "
             "class's configured minimum ink extent (never illustrated here "
             "as rejecting the anchor).")


@dataclass
class FailedAnchorIllustration:
    case: str
    size: str
    width: int
    height: int
    anchor_kind: str
    min_extent: dict[str, int]
    smallest_available: dict[str, int]
    would_fit: bool
    note: str


def illustrate_failed_anchor(
    tuning: SceneTuning, catalog: ArtGeometryCatalog,
) -> FailedAnchorIllustration:
    """A viewport small enough that even the anchor cannot clear its minimum
    ink extent — the sidebar-only outcome plan §4.17/§4.18 describes.
    Illustrative: no solver exists to actually reject the scene, so this
    checks the same "can fit" bar (§4.18) by hand against the proposed
    envelope."""

    w, h = 12, 6
    case_name = "planet+ships"
    sector = calibration_cases()[case_name]
    arrangement, _glyphs = classify_sector(sector, tuning)
    anchor = _pick_anchor(arrangement.objects)
    assert anchor is not None and anchor.continuous_kind is not None
    yield_ = catalog.continuous(anchor.continuous_kind)
    smallest = yield_.box_classes[-1]
    would_fit = smallest.height <= h and smallest.width <= w
    return FailedAnchorIllustration(
        case=case_name, size=f"{w}x{h}", width=w, height=h,
        anchor_kind=anchor.continuous_kind,
        min_extent={"width": yield_.min_extent.width, "height": yield_.min_extent.height},
        smallest_available={"width": smallest.width, "height": smallest.height},
        would_fit=would_fit,
        note="Illustrative floor check only (plan §4.18's \"can fit\" bar): "
             "at this viewport the anchor's smallest configured box class "
             f"({smallest.width}x{smallest.height}) "
             + ("still clears the viewport, so this proposed viewport is not "
                "actually a failed-anchor case — pick a smaller one to "
                "exercise sidebar-only output, or treat this as evidence the "
                "proposed box_classes floor is too permissive."
                if would_fit else
                "does not clear the viewport, so a real WP-SC06 solver would "
                "reject every object to the sidebar and render starfield "
                "only (plan §4.17), never a cropped or partial anchor."))


@dataclass
class ResizeStabilityIllustration:
    case: str
    strategy: str
    size_a: str
    size_b: str
    anchor_height_a: int
    anchor_height_b: int
    hysteresis_delta_terms: int
    note: str


def illustrate_resize_stability(
    tuning: SceneTuning, catalog: ArtGeometryCatalog, strategy: ProjectionStrategy,
) -> ResizeStabilityIllustration:
    case_name = "planet+port+ships"
    sector = gallery_cases()[case_name]
    arrangement, _glyphs = classify_sector(sector, tuning)
    anchor = _pick_anchor(arrangement.objects)
    assert anchor is not None
    anchor_pos = next(p.position for p in arrangement.placements if p.key == anchor.key)

    vp_a, vp_b = CellBox(0, 0, 87, 36), CellBox(0, 0, 88, 36)
    cam_a = strategy.frame(arrangement, anchor.key, vp_a, tuning, catalog)
    cam_b = strategy.frame(arrangement, anchor.key, vp_b, tuning, catalog)
    box_a = strategy.project(cam_a, anchor, anchor_pos, vp_a)
    box_b = strategy.project(cam_b, anchor, anchor_pos, vp_b)

    delta = hysteresis_delta(
        anchor_height_now=box_b.height, anchor_height_prev=box_a.height,
        admitted_now=frozenset({o.key for o in arrangement.objects}),
        admitted_prev=frozenset({o.key for o in arrangement.objects}),
        position_deltas=(abs(box_b.col - box_a.col), abs(box_b.row - box_a.row)),
        art_deltas=(abs(box_b.width - box_a.width), abs(box_b.height - box_a.height)),
        cfg=tuning,
    )
    return ResizeStabilityIllustration(
        case=case_name, strategy=strategy.name, size_a="87x36", size_b="88x36",
        anchor_height_a=box_a.height, anchor_height_b=box_b.height,
        hysteresis_delta_terms=delta,
        note="A ±1-column resize with an unchanged admission set (WP-SC06's "
             "own reposition/admission solve is what actually varies the "
             "admitted set — this illustration holds it fixed) should produce "
             "a small hysteresis delta; the actual acceptance threshold for "
             "\"small\" is a WP-SC06/solver-tuning decision, not fixed here.")


# ---------------------------------------------------------------------------
# Section 5: absolute/extended proposals that don't live on SceneTuning yet
# ---------------------------------------------------------------------------


def extended_proposals() -> list[ProposedValue]:
    """§5 values that still are not `SceneTuning` fields (the solver-bound
    numbers WP-SC06 needed -- cost budget, emergency ceiling, margins,
    minimum visible fraction, and the bounded-search counts -- now live as
    real `SceneTuning` fields and are proposed in `proposed_tuning()`
    instead). What remains here is genuinely not wired to any dataclass
    field yet: the budget's estimate-side *tolerance* (a solver behaviour,
    not a `SceneTuning` value), the soft depth-variation objective strength,
    the default label mode (a `UISettings` field, not `SceneTuning`), and
    the absolute/solver-only latency budgets from plan §6.4."""

    return [
        ProposedValue("render cost budget estimate-side tolerance", "10%",
                      "Plan §4.14: the budget binds the *estimate* side within "
                      "this tolerance; the bounded actual-ink validation "
                      "correction (§6.2 rule 2) may shrink or reject but "
                      "never raise a box's cost class."),
        ProposedValue("ship-depth/rung-variation objective strength", "weight 2 (soft)",
                      "Plan §4.13: prefer arrangements where admitted ships "
                      "don't all project to the same apparent size, but only "
                      "as a tiebreaker after every hard rule and the primary "
                      "hysteresis/admission-count comparison (plan §9.6's "
                      "lexicographic tuple) — a low, clearly-soft weight."),
        ProposedValue("default global label mode (`scene_labels`)", "\"hover_hint\"",
                      "Keeps the art scene visually uncluttered by default "
                      "while remaining fully accessible via mouse hover and "
                      "keyboard focus (plan §2.6); a player who wants "
                      "always-on names can switch to `labeled` in Options."),
        ProposedValue(
            "absolute latency budgets (warm/cold/resize/phenomenon p95)",
            "warm 50ms, cold 200ms, resize 80ms, nebula/black_hole 400ms",
            "Set from the WP-SC04 reproducible baseline's own cached-median "
            "ranges (`docs/SCENE_BENCHMARK_BASELINE.md`): comfortably above "
            "the measured cached medians so the physical model has headroom "
            "for its own bounded search, while still well under the "
            "informal uncached figures the plan's §6.1 baseline records for "
            "large nebula scenes (\"1-4 seconds\")."),
        ProposedValue(
            "solver-only latency and candidate-count budget",
            "solver time <= 30ms warm, <= max_camera_candidates * "
            "max_reposition_candidates candidate-projections per solve",
            "A generous fraction of the total warm budget above, leaving "
            "most of the 50ms for sprite generation/cell conversion/paint "
            "(plan §6.4's total-time-vs-solver-time split); the candidate "
            "cap is the product of the two bounded searches above, which is "
            "the worst case the solve loop's pass budget can spend before it "
            "must fall back to rejection."),
    ]


# ---------------------------------------------------------------------------
# Report assembly + CLI
# ---------------------------------------------------------------------------


@dataclass
class CalibrationReport:
    label: str
    generated_note: str
    catalog_version: str
    tuning_proposals: list[ProposedValue] = field(default_factory=list)
    continuous_proposals: list[ProposedValue] = field(default_factory=list)
    extended_proposals: list[ProposedValue] = field(default_factory=list)
    matrix: list[CaseStrategyTrace] = field(default_factory=list)
    cost_pressure: CostPressureIllustration | None = None
    failed_anchor: FailedAnchorIllustration | None = None
    resize_stability: list[ResizeStabilityIllustration] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


def run_calibration(*, sizes: tuple[tuple[str, int, int], ...] = CALIBRATION_SIZES,
                     cost_budget: int | None = None) -> CalibrationReport:
    """`cost_budget` overrides the proposed `SceneTuning.cost_budget` only for
    the cost-pressure illustration below (e.g. to show a *tighter* budget
    engaging the step-down ladder harder than the tuning proposal's own
    value); it defaults to the proposed tuning's own `cost_budget` field."""

    tuning, tuning_notes = proposed_tuning()
    continuous, continuous_notes = proposed_continuous_yields()
    catalog = _load_proposed_catalog(continuous)
    effective_cost_budget = tuning.cost_budget if cost_budget is None else cost_budget
    strategies: list[ProjectionStrategy] = [FixedFovPerspective(), DepthLayeredAnchorProjection()]

    matrix: list[CaseStrategyTrace] = []
    for case_name, sector in calibration_cases().items():
        for size_label, w, h in sizes:
            for strategy in strategies:
                try:
                    trace = trace_case(case_name, sector, size_label, w, h,
                                        strategy, tuning, catalog)
                except ValueError:
                    trace = None
                if trace is not None:
                    matrix.append(trace)

    resize_stability = [
        illustrate_resize_stability(tuning, catalog, strategy) for strategy in strategies
    ]

    open_questions = [
        "RESOLVED: the single shared `\"anchor\"` face_extent bucket for "
        "planet and every generated discovery kind could not express "
        "per-kind face-area differences (nebula ≫ wormhole > planet, plan "
        "§2.2). `SceneTuning` now carries `face_extent_by_kind` (a WP-SC02 "
        "model addition), and `classify_sector` looks it up by "
        "`continuous_kind` before falling back to `face_extent_by_scale_class`"
        " — see the face_extent_by_kind proposal above for the numbers.",
        "RESOLVED: `region_by_scale_class`'s type was already per-scale-class "
        "(`Mapping[str, Region]`); this proposal previously handed every "
        "class the same shared box, so ships/wrecks did not yet get the "
        "*wider* placement freedom plan §2.5 asks for relative to stations. "
        "The proposal above now gives ship/wreck a distinct, wider region "
        "(x/y span +60%, z span +30%) than entity/anchor/belt/orbital — a "
        "calibration-value fix only, no model.py change was needed.",
        "\"Arbitrary station orbit, including the near or far side\" (plan "
        "§2.5) is not yet distinguishable from any other flexible "
        "placement: `classify_sector`'s stable-hash offset picks one point "
        "in the shared orbital region without a near/far concept. The "
        "`planet+starbase(arbitrary-orbit)` matrix cell above only proves "
        "the station parents correctly to its planet; it does not exercise "
        "near/far placement, which likely needs its own region shape or "
        "reposition-search concept beyond what `edge/scene/solve.py` "
        "(WP-SC06) implements today.",
        "This tool's per-object `visible_fraction_note` is a hand-computed "
        "illustration ('1, assumed unoccluded'), not a call into the real "
        "WP-SC06 occlusion pass (`edge/scene/solve.py` now implements one) "
        "-- wiring the trace through the actual `solve()` output, rather "
        "than this tool's own `frame()`/`project()`-only walk, would give a "
        "real occlusion-based figure and is worth doing in a follow-up pass "
        "of this tool now that WP-SC06 has landed.",
    ]

    return CalibrationReport(
        label=REPORT_LABEL,
        generated_note=(
            "WP-SC05 calibration review sheet: proposed numeric values plus a "
            "traced matrix run through the real edge.scene classifier and "
            "both edge.scene.project strategies. Nothing here is a shipped "
            "default -- see the field-by-field rationale below for what a "
            "reviewer should accept, reject, or adjust."
        ),
        catalog_version=catalog.version,
        tuning_proposals=tuning_notes, continuous_proposals=continuous_notes,
        extended_proposals=extended_proposals(),
        matrix=matrix,
        cost_pressure=illustrate_cost_pressure(tuning, catalog, effective_cost_budget),
        failed_anchor=illustrate_failed_anchor(tuning, catalog),
        resize_stability=resize_stability,
        open_questions=open_questions,
    )


def _to_jsonable(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_to_jsonable(v) for v in obj]
    return obj


def render_markdown(report: CalibrationReport) -> str:
    lines = [
        "# Sector scene calibration review (WP-SC05)", "",
        f"**{report.label}** -- every value below is a proposal for the "
        "maintainer to accept, reject, or adjust per plan §5. Nothing here "
        "has been written to `config/default.yaml`.", "",
        report.generated_note, "", f"Geometry catalogue: `{report.catalog_version}`", "",
        "## 1. Proposed SceneTuning values (plan §5 bullets, framing/camera/hysteresis)",
        "",
    ]
    for p in report.tuning_proposals:
        lines += [f"### `{p.field}`", "", f"Proposed: `{p.proposal}`", "", p.rationale, ""]

    lines += ["## 2. Proposed continuous-kind ink/cost envelopes", ""]
    for p in report.continuous_proposals:
        lines += [f"### `{p.field}`", "", f"Proposed: `{p.proposal}`", "", p.rationale, ""]

    lines += ["## 3. Extended proposals (budgets, margins, mode -- not yet "
              "SceneTuning fields; see rationale)", ""]
    for p in report.extended_proposals:
        lines += [f"### {p.field}", "", f"Proposed: `{p.proposal}`", "", p.rationale, ""]

    lines += ["## 4. Matrix cells: production classifier + both strategies", "",
              "Every cell below ran through the real `edge.scene.classify.classify_sector` "
              "and the named `edge.scene.project` strategy. `decision` for the anchor is "
              "always `\"anchor\"`; every other object is labelled "
              "`would-accept (pending WP-SC06 hard rules)` or `would-reject: <reason>` -- "
              "neither is a real admission decision, since the solver does not exist yet.",
              ""]
    for t in report.matrix:
        lines += [
            f"### {t.case} @ {t.size} -- {t.strategy}", "",
            f"camera position `{t.camera_position}`, aim_x `{t.camera_aim_x}`, "
            f"{t.candidate_count} candidates ({t.distinct_quantised_scenes} distinct "
            "quantised scenes), anchor `" + t.anchor_key + "`", "",
            "| object | kind | scale_class | art_mode | face(w,h,area) | parent | "
            "projected box | depth | art choice | ink_est | cost | decision |",
            "|---|---|---|---|---|---|---|---:|---|---|---:|---|",
        ]
        for o in t.objects:
            box = o.projected_box
            lines.append(
                f"| {o.key} | {o.kind} | {o.scale_class} | {o.art_mode} | "
                f"({o.face_width_su},{o.face_height_su},{o.face_area_su}) | "
                f"{o.parent or '-'} | "
                f"({box['col']},{box['row']},{box['width']}x{box['height']}) | "
                f"{o.depth_su} | {o.art_choice} | "
                f"{o.ink_est_width}x{o.ink_est_height} | {o.render_cost} | {o.decision} |")
        lines.append("")

    if report.cost_pressure is not None:
        cp = report.cost_pressure
        lines += [
            "## 5. Cost-pressure illustration (anchor box-class step-down)", "",
            f"Case `{cp.case}`, anchor kind `{cp.anchor_kind}`, proposed budget "
            f"{cp.proposed_cost_budget}. {cp.note}", "",
            "| box class | box | render_cost | fits budget |", "|---:|---|---:|---|",
        ]
        for s in cp.box_class_sequence:
            lines.append(f"| {s['box_class_index']} | {s['box']} | {s['render_cost']} | "
                         f"{s['fits_budget']} |")
        lines += ["", f"Chosen box class under this illustration: "
                  f"{cp.chosen_box_class_index}.", ""]

    if report.failed_anchor is not None:
        fa = report.failed_anchor
        lines += [
            "## 6. Failed-anchor sidebar illustration", "",
            f"Case `{fa.case}` at `{fa.size}` ({fa.width}x{fa.height}), anchor kind "
            f"`{fa.anchor_kind}`. min_extent={fa.min_extent}, "
            f"smallest_available={fa.smallest_available}, would_fit={fa.would_fit}.",
            "", fa.note, "",
        ]

    lines += ["## 7. Resize-stability illustration (±1 column, fixed admission set)", ""]
    for rs in report.resize_stability:
        lines += [
            f"- `{rs.case}` / {rs.strategy}: anchor height {rs.anchor_height_a} "
            f"({rs.size_a}) -> {rs.anchor_height_b} ({rs.size_b}), hysteresis delta "
            f"{rs.hysteresis_delta_terms}. {rs.note}",
        ]
    lines.append("")

    lines += ["## 8. Open questions for the reviewer", ""]
    for q in report.open_questions:
        lines.append(f"- {q}")
    lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("--cost-budget", type=int, default=None,
                        help="override the proposed SceneTuning.cost_budget for the "
                             "cost-pressure illustration only (default: use the "
                             "proposed tuning's own cost_budget)")
    parser.add_argument("--json", type=Path, default=None,
                        help="write the machine-readable report here")
    parser.add_argument("--md", type=Path, default=None,
                        help="write the human-readable review sheet here")
    args = parser.parse_args(argv)

    report = run_calibration(cost_budget=args.cost_budget)
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
