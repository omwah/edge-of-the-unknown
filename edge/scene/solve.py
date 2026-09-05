"""The constraint solver: bounded search, admission, and hysteresis.

Plan §9.6 is the literal pass-loop/attempt/comparison reference; plan §4 is
the acceptance contract and wins wherever this module and §9.6 disagree.

Everything here is integer or `fractions.Fraction`; no accepted/rejected
decision, ordering, or rounding ever consumes a `float` (plan §4.1). No art is
rendered or imported here (§6.2 rule 1) -- only catalogue-supplied face
geometry and ink envelopes. No game RNG and no game-state mutation: glyph
scatter uses a small local hash-based deterministic picker (see
`_hash_index` below), never `random.Random` or anything seeded from game
state, matching the package-wide "no `random` module" boundary that
`tests/test_scene_import_boundaries.py` already enforces on every module in
this package.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Literal

from edge.scene.catalog import ArtGeometryCatalog, LadderRung
from edge.scene.geometry import CellBox, Vec3
from edge.scene.model import (
    ArtMode,
    Camera,
    Decision,
    GlyphRequest,
    PhysicalObject,
    Placement,
    Projection,
    SceneKey,
    ScenePlan,
    SceneRetention,
    SceneTuning,
    SolveCounters,
    WorldArrangement,
)
from edge.scene.project import (
    NearPlaneViolation,
    ProjectionStrategy,
    hysteresis_delta,
    intersect_region_xy,
    structural_mode,
)

# ---------------------------------------------------------------------------
# Deterministic, non-random hashing (never `random.Random`, never game RNG).
# ---------------------------------------------------------------------------


def _hash_index(key: str, modulus: int) -> int:
    """A deterministic, seed-free index in `[0, modulus)` from `key`.

    Mirrors `edge.scene.classify._stable_int`'s reasoning (Python's salted
    `hash()` would make output non-reproducible across runs); reimplemented
    locally so `solve.py` does not depend on a private classifier helper.
    """
    if modulus <= 0:
        return 0
    digest = hashlib.blake2b(key.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % modulus


def _fingerprint(camera: Camera, entries: tuple[tuple[str, int, int, int, int, int], ...]) -> str:
    """A stable hash of quantised output, used only as the final tie-break in
    `better_of` (plan §9.6: "stable final tie-break, never iteration order")
    and as `ScenePlan.fingerprint` (plan §9.1's "quantised output").
    """
    parts = [
        f"{camera.position.x},{camera.position.y},{camera.position.z}",
        f"{camera.aim_x_su},{camera.aim_y_su}",
    ]
    for tag, ident, col, row, width, height in entries:
        parts.append(f"{tag}:{ident}:{col},{row},{width}x{height}")
    return hashlib.blake2b("|".join(parts).encode(), digest_size=16).hexdigest()


# ---------------------------------------------------------------------------
# Geometry helpers (integer-only rectangle arithmetic).
# ---------------------------------------------------------------------------


def _contained(bounds: CellBox, viewport: CellBox, margin: int) -> bool:
    return (
        bounds.col >= margin
        and bounds.row >= margin
        and bounds.col + bounds.width <= viewport.width - margin
        and bounds.row + bounds.height <= viewport.height - margin
    )


def _select_rung(catalog: ArtGeometryCatalog, obj: PhysicalObject, bounds: CellBox) -> LadderRung | None:
    """Plan §4.7/§9.6 attempt rule 3 (laddered): the richest complete authored
    rung whose natural box fits inside the projected box. Never the shipped
    `fit_box` clamp -- an object with no clearing rung returns `None` and is
    rejected, never cropped.
    """
    if obj.ladder_key is None:
        return None
    fits = [
        r
        for r in catalog.rungs(obj.ladder_key)
        if r.natural.width <= bounds.width and r.natural.height <= bounds.height
    ]
    if not fits:
        return None
    return max(fits, key=lambda r: (r.natural.height, r.natural.width, -r.index))


def _ink_box(
    obj: PhysicalObject,
    bounds: CellBox,
    rung: LadderRung | None,
    catalog: ArtGeometryCatalog,
    *,
    side: str,
) -> CellBox:
    """The ink envelope on the declared side (plan §2.5): `"min"` for
    visibility/minimum-extent floors, `"max"` for separation/occlusion
    clearance. Centred within `bounds`, since ink is a sub-region of the
    request box.
    """
    if obj.art_mode is ArtMode.LADDER:
        assert rung is not None
        base = rung.ink_min if side == "min" else rung.ink_max
        width, height = base.width, base.height
    else:
        assert obj.continuous_kind is not None
        yield_ = catalog.continuous(obj.continuous_kind)
        frac = yield_.ink_fraction_min if side == "min" else yield_.ink_fraction_max
        if side == "min":
            width = math.floor(Fraction(bounds.width) * frac)
            height = math.floor(Fraction(bounds.height) * frac)
        else:
            width = math.ceil(Fraction(bounds.width) * frac)
            height = math.ceil(Fraction(bounds.height) * frac)
        width = max(width, 0)
        height = max(height, 0)
    col = bounds.col + (bounds.width - width) // 2
    row = bounds.row + (bounds.height - height) // 2
    return CellBox(col, row, width, height)


def _inflate(box: CellBox, margin: int) -> CellBox:
    return CellBox(box.col - margin, box.row - margin, box.width + 2 * margin, box.height + 2 * margin)


def _rect_gap(a: CellBox, b: CellBox) -> int:
    """Signed separation between two rectangles: positive is clear space,
    negative (or zero) means overlap. Used both as the pairwise separation
    hard-rule test and as the `min_separation_slack` comparison term.
    """
    dx = max(a.col - (b.col + b.width), b.col - (a.col + a.width))
    dy = max(a.row - (b.row + b.height), b.row - (a.row + a.height))
    if dx < 0 and dy < 0:
        # Overlapping on both axes: report how deeply, as a negative slack.
        return -min(-dx, -dy)
    return max(dx, dy)


def _overlap_area(a: CellBox, b: CellBox) -> int:
    left = max(a.col, b.col)
    right = min(a.col + a.width, b.col + b.width)
    top = max(a.row, b.row)
    bottom = min(a.row + a.height, b.row + b.height)
    if right <= left or bottom <= top:
        return 0
    return (right - left) * (bottom - top)


# ---------------------------------------------------------------------------
# One camera candidate's evaluation.
# ---------------------------------------------------------------------------

_LARGE_SLACK = 1 << 30
"""Sentinel `min_separation_slack` reported when there are no occluding pairs
to compare -- deliberately "as good as it gets", never read back as a float.
"""


@dataclass
class _Attempt:
    camera: Camera
    bounds: dict[SceneKey, CellBox] = field(default_factory=dict)
    rung: dict[SceneKey, LadderRung | None] = field(default_factory=dict)
    box_class: dict[SceneKey, int | None] = field(default_factory=dict)
    visible_fraction: dict[SceneKey, Fraction] = field(default_factory=dict)
    accepted: set[SceneKey] = field(default_factory=set)
    min_violations: int = 0
    occlusion_comparisons: int = 0
    cost_estimated: int = 0
    min_separation_slack: int = _LARGE_SLACK
    decisions: list[Decision] = field(default_factory=list)

    def hard_ok(self, admitted_count: int) -> bool:
        return len(self.accepted) == admitted_count


_Outcome = Literal["accept", "move", "reject", "step_down", "reanchor"]


def _decision(
    rule_id: str, key: SceneKey | None, outcome: _Outcome, *, trace_prose: bool, reason: str = ""
) -> Decision:
    return Decision(
        rule_id=rule_id,
        key=key,
        outcome=outcome,
        inputs=(),
        reason=reason if trace_prose else "",
    )


def _attempt(
    camera: Camera,
    admitted: list[PhysicalObject],
    placements: dict[SceneKey, Vec3],
    viewport: CellBox,
    cfg: SceneTuning,
    catalog: ArtGeometryCatalog,
    strategy: ProjectionStrategy,
    anchor_key: SceneKey,
    anchor_box_class: int | None,
    *,
    trace_prose: bool,
) -> _Attempt:
    """Project every currently-admitted object under one candidate camera and
    check the hard rules of plan §9.6 in cheapest-and-most-rejecting-first
    order. Returns which objects survived; the caller (`solve`) decides what
    to do about the rest -- `_attempt` never mutates `admitted`.
    """
    result = _Attempt(camera=camera)
    surviving: list[PhysicalObject] = []

    for obj in admitted:
        pos = placements[obj.key]
        try:
            bounds = strategy.project(camera, obj, pos, viewport)
        except NearPlaneViolation:
            result.min_violations += 1
            result.decisions.append(
                _decision("near_plane", obj.key, "reject", trace_prose=trace_prose, reason="behind near plane")
            )
            continue
        if not _contained(bounds, viewport, cfg.edge_margin):
            result.min_violations += 1
            result.decisions.append(
                _decision("edge_margin", obj.key, "reject", trace_prose=trace_prose, reason="outside viewport")
            )
            continue
        min_w, min_h = cfg.min_projected_cells_by_scale_class[obj.scale_class]
        if bounds.width < min_w or bounds.height < min_h:
            result.min_violations += 1
            result.decisions.append(
                _decision(
                    "min_projected_size", obj.key, "reject", trace_prose=trace_prose, reason="too small to read"
                )
            )
            continue

        rung: LadderRung | None = None
        box_class: int | None = None
        if obj.art_mode is ArtMode.LADDER:
            rung = _select_rung(catalog, obj, bounds)
            if rung is None:
                result.min_violations += 1
                result.decisions.append(
                    _decision(
                        "no_clearing_rung", obj.key, "reject", trace_prose=trace_prose,
                        reason="no authored rung fits; never cropped",
                    )
                )
                continue
        else:
            assert obj.continuous_kind is not None
            yield_ = catalog.continuous(obj.continuous_kind)
            ink_min_box = _ink_box(obj, bounds, None, catalog, side="min")
            if ink_min_box.width < yield_.min_extent.width or ink_min_box.height < yield_.min_extent.height:
                result.min_violations += 1
                result.decisions.append(
                    _decision(
                        "min_ink_extent", obj.key, "reject", trace_prose=trace_prose,
                        reason="below minimum continuous ink extent",
                    )
                )
                continue
            if obj.key == anchor_key:
                box_class = anchor_box_class

        result.bounds[obj.key] = bounds
        result.rung[obj.key] = rung
        result.box_class[obj.key] = box_class
        result.visible_fraction[obj.key] = Fraction(1)
        result.accepted.add(obj.key)
        surviving.append(obj)

    # Rule 4: separation. `surviving` is already in retention-priority order,
    # so on overlap the later (lower-priority) object of the pair loses.
    min_slack = _LARGE_SLACK
    for i, a in enumerate(surviving):
        if a.key not in result.accepted or not a.occludes:
            continue
        ink_a = _inflate(_ink_box(a, result.bounds[a.key], result.rung[a.key], catalog, side="max"), cfg.separation_margin)
        for b in surviving[i + 1 :]:
            if b.key not in result.accepted or not b.occludes:
                continue
            ink_b = _inflate(
                _ink_box(b, result.bounds[b.key], result.rung[b.key], catalog, side="max"), cfg.separation_margin
            )
            gap = _rect_gap(ink_a, ink_b)
            min_slack = min(min_slack, gap)
            if gap < 0:
                result.accepted.discard(b.key)
                result.decisions.append(
                    _decision("separation", b.key, "reject", trace_prose=trace_prose, reason="too close to " + str(a.key))
                )

    # Rule 5: occlusion by depth. Nearer (smaller z; equal-z ties broken by
    # larger face area first, per §4.8/§9.6) checked against farther.
    ordered = sorted(
        (o for o in surviving if o.key in result.accepted),
        key=lambda o: (placements[o.key].z, -o.face.area_su, o.key),
    )
    for i, nearer in enumerate(ordered):
        if nearer.key not in result.accepted or not nearer.occludes:
            continue
        occluder = _ink_box(
            nearer, result.bounds[nearer.key], result.rung[nearer.key], catalog, side="max"
        )
        for farther in ordered[i + 1 :]:
            if farther.key not in result.accepted or not farther.occludes:
                continue
            if placements[farther.key].z <= placements[nearer.key].z:
                continue  # strictly farther only; equal depth handled by the sort above
            farther_ink = _ink_box(
                farther, result.bounds[farther.key], result.rung[farther.key], catalog, side="min"
            )
            result.occlusion_comparisons += 1
            area = farther_ink.width * farther_ink.height
            if area <= 0:
                continue
            overlap = _overlap_area(occluder, farther_ink)
            visible = Fraction(area - overlap, area)
            result.visible_fraction[farther.key] = min(result.visible_fraction[farther.key], visible)
            threshold = cfg.min_visible_fraction_by_scale_class[farther.scale_class]
            if visible < threshold:
                result.accepted.discard(farther.key)
                result.decisions.append(
                    _decision(
                        "min_visible_fraction", farther.key, "reject", trace_prose=trace_prose,
                        reason="occluded below minimum visible fraction",
                    )
                )

    # Rule 7: cumulative cost and emergency ship ceiling.
    cost = 0
    ship_count = 0
    for obj in surviving:
        if obj.key not in result.accepted:
            continue
        if obj.art_mode is ArtMode.LADDER:
            rung_obj = result.rung[obj.key]
            assert rung_obj is not None
            cost += rung_obj.render_cost
        else:
            assert obj.continuous_kind is not None
            yield_ = catalog.continuous(obj.continuous_kind)
            idx = result.box_class[obj.key] or 0
            cost += yield_.render_cost[idx]
        if obj.key.tag in ("ship", "player"):
            ship_count += 1
    result.cost_estimated = cost
    if cost > cfg.cost_budget or ship_count > cfg.emergency_ship_ceiling:
        # A cost/ceiling violation fails the whole candidate (plan §4.14) --
        # unlike separation/occlusion, this is not attributable to one object,
        # so it does not discard anyone here; it only clears `hard_ok`. The
        # outer pass loop's step-down/reject fallbacks are what actually act
        # on it.
        result.accepted.clear()

    result.min_separation_slack = min_slack
    return result


def _rejected_by_retention(
    attempt: _Attempt, admitted: list[PhysicalObject]
) -> tuple[int, ...]:
    """How many objects of each `SceneRetention` tier this attempt rejected,
    indexed by tier value ascending (plan §4.5: "higher retention priority is
    never dropped for a lower one").

    Comparing two attempts' full accepted *count* alone (as a bare
    `-len(attempt.accepted)`) is exactly the hierarchy violation §4.5
    forbids: across the solver's own pass loop, a later pass's `admitted`
    superset can differ from an earlier pass's (retention-priority ejection
    shrinks it monotonically, per this module's fallback ladder), so a
    "more objects accepted" attempt from one pass can otherwise outscore a
    "the one object retention actually protects is accepted" attempt from
    another -- silently dropping the anchor itself in favour of several
    lower-priority ships if ships alone happen to fit more easily than the
    full scene (the frustum-aware reposition fix directly increases how
    often ships *do* fit, which is exactly what surfaced this). Comparing
    the two attempts tier-by-tier, most-protected tier first, makes any
    rejection at a higher tier strictly worse than any number of
    lower-tier gains, regardless of total count.
    """
    counts = [0] * len(SceneRetention)
    for obj in admitted:
        if obj.key not in attempt.accepted:
            counts[int(obj.retention)] += 1
    return tuple(counts)


def _score(
    attempt: _Attempt,
    admitted: list[PhysicalObject],
    anchor_key: SceneKey,
    target_height: int,
    previous: ScenePlan | None,
    cfg: SceneTuning,
) -> tuple[tuple[int, ...], int, int, int, int, int, str]:
    """Plan §9.6 `better_of`'s lexicographic tuple, all ascending-better --
    with the retention-priority guard (`_rejected_by_retention`) prepended
    ahead of the raw accepted-count term (see that function's docstring)."""
    anchor_bounds = attempt.bounds.get(anchor_key)
    anchor_height = anchor_bounds.height if anchor_bounds is not None else 0
    min_slack = attempt.min_separation_slack
    entries = tuple(
        sorted(
            (key.tag, key.ident, box.col, box.row, box.width, box.height)
            for key, box in attempt.bounds.items()
            if key in attempt.accepted
        )
    )
    fingerprint = _fingerprint(attempt.camera, entries)
    hysteresis = _hysteresis(attempt, anchor_key, anchor_height, previous, cfg)
    return (
        _rejected_by_retention(attempt, admitted),
        -len(attempt.accepted),
        attempt.min_violations,
        abs(anchor_height - target_height),
        -min_slack,
        hysteresis,
        fingerprint,
    )


def _hysteresis(
    attempt: _Attempt,
    anchor_key: SceneKey,
    anchor_height_now: int,
    previous: ScenePlan | None,
    cfg: SceneTuning,
) -> int:
    if previous is None:
        return 0
    prev_by_key = {p.key: p for p in previous.projections if p.accepted}
    anchor_prev = prev_by_key.get(anchor_key)
    anchor_height_prev = anchor_prev.bounds.height if anchor_prev is not None else None
    admitted_now = frozenset(attempt.accepted)
    admitted_prev = frozenset(prev_by_key.keys())
    position_deltas: list[int] = []
    art_deltas: list[int] = []
    for key in admitted_now & admitted_prev:
        now_box = attempt.bounds[key]
        prev_box = prev_by_key[key].bounds
        position_deltas.append(abs(now_box.col - prev_box.col) + abs(now_box.row - prev_box.row))
        art_deltas.append(abs(now_box.width - prev_box.width) + abs(now_box.height - prev_box.height))
    return hysteresis_delta(
        anchor_height_now=anchor_height_now,
        anchor_height_prev=anchor_height_prev,
        admitted_now=admitted_now,
        admitted_prev=admitted_prev,
        position_deltas=tuple(position_deltas),
        art_deltas=tuple(art_deltas),
        cfg=cfg,
    )


# ---------------------------------------------------------------------------
# Glyph scatter (plan §4.19, §9.6). Runs after the solve, never affects it.
# ---------------------------------------------------------------------------


def _scatter_glyphs(
    sector_id: int,
    glyphs: tuple[GlyphRequest, ...],
    viewport: CellBox,
    covered: list[CellBox],
    cfg: SceneTuning,
) -> tuple[int, int, tuple[SceneKey, ...]]:
    if viewport.width <= 0 or viewport.height <= 0:
        return 0, sum(g.count for g in glyphs), tuple(sorted(g.key for g in glyphs))

    def _is_covered(col: int, row: int) -> bool:
        return any(
            box.col <= col < box.col + box.width and box.row <= row < box.row + box.height for box in covered
        )

    placed_cells: list[tuple[int, int]] = []
    placed = 0
    dropped = 0
    dropped_keys: list[SceneKey] = []
    for glyph in sorted(glyphs, key=lambda g: g.key):
        any_dropped = False
        for mark in range(glyph.count):
            found = False
            for attempt_no in range(cfg.max_glyph_tries):
                seed = f"{sector_id}|glyphs|{viewport.width}x{viewport.height}|{glyph.key.tag}:{glyph.key.ident}|{mark}|{attempt_no}"
                idx = _hash_index(seed, viewport.width * viewport.height)
                col = viewport.col + idx % viewport.width
                row = viewport.row + idx // viewport.width
                if _is_covered(col, row):
                    continue
                if any(
                    abs(col - pc) + abs(row - pr) < cfg.glyph_spacing for pc, pr in placed_cells
                ):
                    continue
                placed_cells.append((col, row))
                placed += 1
                found = True
                break
            if not found:
                dropped += 1
                any_dropped = True
        if any_dropped:
            dropped_keys.append(glyph.key)
    return placed, dropped, tuple(dropped_keys)


# ---------------------------------------------------------------------------
# The pass loop.
# ---------------------------------------------------------------------------


def _starfield_plan(viewport: CellBox, mode: str, strategy_name: str, camera: Camera) -> ScenePlan:
    return ScenePlan(
        viewport=viewport,
        mode=mode,
        strategy=strategy_name,
        camera=camera,
        projections=(),
        rejected=(),
        fingerprint=_fingerprint(camera, ()),
        counters=SolveCounters(
            camera_candidates=0, reposition_candidates=0, passes=0, reanchors=0, step_downs=0,
            occlusion_comparisons=0, validation_corrections=0, glyphs_placed=0, glyphs_dropped=0,
            cost_estimated=0, cost_actual=0,
        ),
        trace=(),
    )


def solve(
    arrangement: WorldArrangement,
    viewport: CellBox,
    cfg: SceneTuning,
    catalog: ArtGeometryCatalog,
    strategy: ProjectionStrategy,
    previous: ScenePlan | None = None,
    *,
    trace_prose: bool = False,
) -> ScenePlan:
    mode = structural_mode(viewport, cfg)
    all_objects = {o.key: o for o in arrangement.objects}
    placements: dict[SceneKey, Vec3] = {p.key: p.position for p in arrangement.placements}
    admitted = [o for o in arrangement.objects if o.art_mode is not ArtMode.GLYPH]
    admitted.sort(key=lambda o: (o.retention, o.hostility_ordinal, -o.threat_rank, o.key))

    if not admitted:
        base_camera = _base_starfield_camera(cfg)
        plan = _starfield_plan(viewport, mode, strategy.name, base_camera)
        return _with_glyph_trace(plan, arrangement, viewport, cfg)

    trace: list[Decision] = []
    counters = {
        "camera_candidates": 0, "reposition_candidates": 0, "passes": 0, "reanchors": 0,
        "step_downs": 0, "occlusion_comparisons": 0,
    }
    reposition_attempts: dict[SceneKey, int] = {}

    best: _Attempt | None = None
    best_score: tuple[tuple[int, ...], int, int, int, int, int, str] | None = None
    best_anchor_key: SceneKey | None = None

    current_anchor_key: SceneKey | None = None
    step_index = 0
    cfg_current = cfg

    for _pass in range(cfg.max_passes):
        counters["passes"] += 1
        anchor = max(admitted, key=lambda o: (o.face.area_su, o.key))
        if anchor.key != current_anchor_key:
            if current_anchor_key is not None:
                counters["reanchors"] += 1
                trace.append(_decision("reanchor", anchor.key, "reanchor", trace_prose=trace_prose))
            current_anchor_key = anchor.key
            step_index = 0
            cfg_current = cfg

        anchor_box_class = step_index if anchor.art_mode is ArtMode.CONTINUOUS else None
        target_h = _round_half_even(
            cfg_current.target_fraction_by_scale_class[anchor.scale_class] * viewport.height
        )

        camera = strategy.frame(
            _as_world_arrangement(admitted, placements, arrangement),
            anchor.key,
            viewport,
            cfg_current,
            catalog,
        )
        anchor_pos = placements[anchor.key]
        found_hard_ok = False
        for cand_camera in strategy.candidates(camera, anchor, anchor_pos, viewport, cfg_current):
            counters["camera_candidates"] += 1
            attempt = _attempt(
                cand_camera, admitted, placements, viewport, cfg_current, catalog, strategy,
                anchor.key, anchor_box_class, trace_prose=trace_prose,
            )
            counters["occlusion_comparisons"] += attempt.occlusion_comparisons
            score = _score(attempt, admitted, anchor.key, target_h, previous, cfg_current)
            if best_score is None or score < best_score:
                best = attempt
                best_score = score
                best_anchor_key = anchor.key
            if attempt.hard_ok(len(admitted)):
                found_hard_ok = True
                break
        if found_hard_ok:
            assert best is not None and best_anchor_key is not None
            return _finish(
                best, admitted, all_objects, placements, viewport, mode, strategy.name, catalog,
                counters, trace, arrangement, cfg, trace_prose=trace_prose,
            )

        # Fallback ladder, in order: reposition -> anchor step-down -> reject.
        flexible_candidates = [
            o for o in reversed(admitted)
            if o.flexible and reposition_attempts.get(o.key, 0) < cfg.max_reposition_candidates
        ]
        if flexible_candidates:
            target = flexible_candidates[0]
            attempt_no = reposition_attempts.get(target.key, 0)
            reposition_attempts[target.key] = attempt_no + 1
            counters["reposition_candidates"] += 1
            region = target.region
            offset_key = f"{target.key.tag}:{target.key.ident}|reposition|{attempt_no}"
            new_z = region.z_min + _hash_index(offset_key + "|z", region.z_max - region.z_min + 1)
            # Frustum-aware reposition (docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md
            # §2.5/§9.6 fix): `target.region` is deliberately wide -- ships/wrecks
            # receive placement freedom far beyond a station's -- but only the
            # slice of it a camera the solver would actually place can show is
            # ever worth sampling. Intersecting with `strategy.visible_xy_extent()`
            # at this attempt's depth turns "resample the whole region and hope"
            # into "resample the part of the region that can possibly pass
            # `_contained()`", without narrowing the region itself or spending any
            # extra bounded-search budget -- this replaces one hash draw with
            # another, it does not add a loop. `camera` here is the current pass's
            # *framed* camera (fixed once per anchor/step, before the per-candidate
            # height/aim sweep) -- an estimate, not the eventual winning candidate,
            # so a `None`/empty intersection (near-plane failure, or a face too
            # large to fit at this depth) falls back to the untouched full region,
            # exactly WP-SC06's original behaviour for this object.
            extent = strategy.visible_xy_extent(camera, viewport, new_z, target.face, cfg_current)
            xy = intersect_region_xy(region, extent)
            x_min, x_max, y_min, y_max = xy if xy is not None else (
                region.x_min, region.x_max, region.y_min, region.y_max
            )
            new_pos = Vec3(
                x_min + _hash_index(offset_key + "|x", x_max - x_min + 1),
                y_min + _hash_index(offset_key + "|y", y_max - y_min + 1),
                new_z,
            )
            placements[target.key] = new_pos
            trace.append(_decision("reposition", target.key, "move", trace_prose=trace_prose))
            continue

        yield_max_index = None
        anchor_continuous_kind = anchor.continuous_kind
        if anchor.art_mode is ArtMode.CONTINUOUS and anchor_continuous_kind is not None:
            yield_ = catalog.continuous(anchor_continuous_kind)
            yield_max_index = len(yield_.box_classes) - 1
        if yield_max_index is not None and anchor_continuous_kind is not None and step_index < yield_max_index:
            step_index += 1
            new_fraction = Fraction(
                catalog.continuous(anchor_continuous_kind).box_classes[step_index].height, viewport.height
            )
            cfg_current = replace(
                cfg_current,
                target_fraction_by_scale_class={
                    **cfg_current.target_fraction_by_scale_class, anchor.scale_class: new_fraction
                },
            )
            counters["step_downs"] += 1
            trace.append(_decision("step_down", anchor.key, "step_down", trace_prose=trace_prose))
            continue

        if admitted and admitted[-1].key != anchor.key:
            drop = admitted[-1]
            admitted = admitted[:-1]
            trace.append(_decision("retention_reject", drop.key, "reject", trace_prose=trace_prose, reason="lowest retention priority"))
            continue

        break

    if best is None or best_anchor_key is None:
        base_camera = _base_starfield_camera(cfg)
        plan = _starfield_plan(viewport, mode, strategy.name, base_camera)
        return _with_glyph_trace(plan, arrangement, viewport, cfg)

    return _finish(
        best, admitted, all_objects, placements, viewport, mode, strategy.name, catalog,
        counters, trace, arrangement, cfg, trace_prose=trace_prose,
    )


def _round_half_even(value: Fraction) -> int:
    result = round(value)
    assert isinstance(result, int)
    return result


def _base_starfield_camera(cfg: SceneTuning) -> Camera:
    return Camera(
        position=Vec3(0, 0, 0), aim_x_su=0, aim_y_su=0,
        fov_num=cfg.fixed_fov_num, fov_den=cfg.fixed_fov_den,
        near_plane_su=cfg.near_plane_su, cell_aspect=cfg.cell_aspect,
        depth_layer_size_su=cfg.depth_layer_size_su, depth_layer_scale=cfg.depth_layer_scale,
    )


def _as_world_arrangement(
    admitted: list[PhysicalObject], placements: dict[SceneKey, Vec3], arrangement: WorldArrangement
) -> WorldArrangement:
    """`ProjectionStrategy.frame()` takes a `WorldArrangement`; the solver
    works from a possibly-shrunk `admitted` list and a possibly-repositioned
    `placements` map, so this rebuilds the minimal view `frame()` needs
    without mutating the caller's original arrangement.
    """
    objs = tuple(admitted)
    plc = tuple(Placement(key=o.key, position=placements[o.key]) for o in admitted)
    return replace(arrangement, objects=objs, placements=plc)


def _with_glyph_trace(plan: ScenePlan, arrangement: WorldArrangement, viewport: CellBox, cfg: SceneTuning) -> ScenePlan:
    placed, dropped, dropped_keys = _scatter_glyphs(arrangement.sector_id, arrangement.glyphs, viewport, [], cfg)
    return replace(
        plan,
        rejected=tuple(sorted({*plan.rejected, *dropped_keys})),
        counters=replace(plan.counters, glyphs_placed=placed, glyphs_dropped=dropped),
    )


def _finish(
    attempt: _Attempt,
    admitted: list[PhysicalObject],
    all_objects: dict[SceneKey, PhysicalObject],
    placements: dict[SceneKey, Vec3],
    viewport: CellBox,
    mode: str,
    strategy_name: str,
    catalog: ArtGeometryCatalog,
    counters: dict[str, int],
    trace: list[Decision],
    arrangement: WorldArrangement,
    cfg: SceneTuning,
    *,
    trace_prose: bool = False,
) -> ScenePlan:
    # Plan invariant 20: the winning attempt's own per-object hard-rule
    # rejection `Decision`s (near_plane/edge_margin/min_projected_size/
    # no_clearing_rung/min_ink_extent/separation/min_visible_fraction --
    # `_attempt()`'s `result.decisions`) were only ever discarded here, so
    # even `trace_prose=True` reported reanchor/reposition/step_down/
    # retention_reject events but never *why* a specific object failed inside
    # the accepted candidate camera. Every other rule appends to `trace`
    # unconditionally (only each `Decision`'s own `reason` text is gated on
    # `trace_prose`, via `_decision()`), so these are merged in the same way
    # here for consistency, in candidate-evaluation order (they were recorded
    # in that order by `_attempt()`).
    trace.extend(attempt.decisions)
    projections: list[Projection] = []
    accepted_boxes: list[CellBox] = []
    for obj in admitted:
        if obj.key not in attempt.accepted:
            continue
        bounds = attempt.bounds[obj.key]
        rung = attempt.rung[obj.key]
        box_class = attempt.box_class[obj.key]
        ink_est = _ink_box(obj, bounds, rung, catalog, side="min")
        accepted_boxes.append(ink_est)
        projections.append(
            Projection(
                key=obj.key,
                bounds=bounds,
                depth=placements[obj.key].z,
                rung=rung,
                box_class=box_class,
                ink_est=ink_est,
                ink_actual=None,
                visible_fraction=attempt.visible_fraction.get(obj.key, Fraction(1)),
                label_bounds=None,
                accepted=True,
            )
        )
        trace.append(_decision("accept", obj.key, "accept", trace_prose=trace_prose))

    # Depth-ordered far to near; equal-depth ties keep scale-class/face-area
    # ordering (plan §4.4/§4.8) via `-face.area_su`, final tie-break by key.
    projections.sort(
        key=lambda p: (-p.depth, -all_objects[p.key].face.area_su, p.key),
    )

    accepted_keys = {p.key for p in projections}
    all_keys = {o.key for o in arrangement.objects if o.art_mode is not ArtMode.GLYPH}
    rejected = tuple(sorted(all_keys - accepted_keys))

    entries = tuple(
        sorted((p.key.tag, p.key.ident, p.bounds.col, p.bounds.row, p.bounds.width, p.bounds.height) for p in projections)
    )
    fingerprint = _fingerprint(attempt.camera, entries)

    glyphs_placed, glyphs_dropped, dropped_glyph_keys = _scatter_glyphs(
        arrangement.sector_id, arrangement.glyphs, viewport, accepted_boxes, cfg
    )

    plan = ScenePlan(
        viewport=viewport,
        mode=mode,
        strategy=strategy_name,
        camera=attempt.camera,
        projections=tuple(projections),
        rejected=tuple(sorted({*rejected, *dropped_glyph_keys})),
        fingerprint=fingerprint,
        counters=SolveCounters(
            camera_candidates=counters["camera_candidates"],
            reposition_candidates=counters["reposition_candidates"],
            passes=counters["passes"],
            reanchors=counters["reanchors"],
            step_downs=counters["step_downs"],
            occlusion_comparisons=counters["occlusion_comparisons"],
            validation_corrections=0,
            glyphs_placed=glyphs_placed,
            glyphs_dropped=glyphs_dropped,
            cost_estimated=attempt.cost_estimated,
            cost_actual=attempt.cost_estimated,
        ),
        trace=tuple(trace),
    )
    return plan
