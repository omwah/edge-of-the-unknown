"""The constraint solver: bounded search, admission, and hysteresis.

Plan §9.6 is the pass-loop/attempt/comparison reference; plan §4 is the
acceptance contract and wins wherever this module and §9.6 disagree. The
deviations §9.6's original pseudocode no longer describes are enumerated in
the plan's "Joint secondary-object placement (post-WP-SC09 redesign)" section
-- above all, that flexible objects are placed *inside* `_attempt`, jointly
and in retention order, against the exact candidate camera being evaluated,
rather than independently and camera-blind before the search.

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
from functools import lru_cache
from fractions import Fraction
from typing import Literal

from edge.scene.catalog import ArtGeometryCatalog, LadderRung
from edge.scene.geometry import CellBox, Region, Vec3
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


def _select_rung(
    catalog: ArtGeometryCatalog,
    obj: PhysicalObject,
    bounds: CellBox,
    cfg: SceneTuning,
    max_cost: int | None = None,
) -> LadderRung | None:
    """Plan §4.7/§9.6 attempt rule 3 (laddered): the richest complete authored
    rung whose natural box fits inside the projected box. Never the shipped
    `fit_box` clamp -- an object with no clearing rung returns `None` and is
    rejected, never cropped.

    The `min_rung_index_from_end_by_scale_class` floor (minimum-richness fix)
    excludes the worst `N` rung indices of this object's ladder from
    consideration entirely -- not just from the ranking, but from what
    "clears" means -- so an object that can only ever fit one of the excluded
    rungs is rejected outright rather than shown at a degraded tier. `index`
    ascends from 0 (richest); the worst `N` are the top `N` index values
    actually present in *this* ladder, so the exclusion scales correctly even
    though port/starbase/stardock ladders have 4 rungs and ship ladders have
    3.

    `max_cost`, when given, additionally excludes rungs the caller cannot
    afford out of the remaining `cost_budget` (plan §4.14). It is a
    *selection* input, not a post-hoc veto, because the two differ: picking
    the richest fitting rung first and then refusing it on cost drops an
    object that had a perfectly good cheaper authored tier available at the
    very same position. That was a real, measured defect -- e.g.
    `port+ships @ 120x44` under `FixedFovPerspective` rejected its warship
    with `cost_budget` while the whole scene had spent 85 of 250, because
    every sampled depth projected a box big enough for a rung-0 hull
    (`render_cost` 350-436) and the rung-2 hull (34) that also fit was never
    considered. Callers reasoning about pure geometry (`_z_ok_near_and_size`
    and so `_feasible_z_interval`) pass `None` and stay cost-blind, which
    keeps the feasible-z band a property of the camera and the ladder alone.
    """
    if obj.ladder_key is None:
        return None
    all_rungs = catalog.rungs(obj.ladder_key)
    if not all_rungs:
        return None
    exclude_from_end = cfg.min_rung_index_from_end_by_scale_class.get(obj.scale_class, 0)
    max_index = max(r.index for r in all_rungs)
    allowed = [r for r in all_rungs if r.index <= max_index - exclude_from_end]
    fits = [
        r for r in allowed if r.natural.width <= bounds.width and r.natural.height <= bounds.height
    ]
    if max_cost is not None:
        fits = [r for r in fits if r.render_cost <= max_cost]
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
    positions: dict[SceneKey, Vec3] = field(default_factory=dict)
    """The position each object was actually *placed* at under this candidate
    camera. Joint placement (see `_attempt`) makes this per-attempt state, not
    solver-wide state: two candidate cameras frame different volumes and so
    reach different placements for the same object."""
    bounds: dict[SceneKey, CellBox] = field(default_factory=dict)
    rung: dict[SceneKey, LadderRung | None] = field(default_factory=dict)
    box_class: dict[SceneKey, int | None] = field(default_factory=dict)
    visible_fraction: dict[SceneKey, Fraction] = field(default_factory=dict)
    accepted: set[SceneKey] = field(default_factory=set)
    min_violations: int = 0
    occlusion_comparisons: int = 0
    placement_evaluations: int = 0
    cost_estimated: int = 0
    min_separation_slack: int = _LARGE_SLACK
    decisions: list[Decision] = field(default_factory=list)

    def hard_ok(self, admitted_count: int) -> bool:
        return len(self.accepted) == admitted_count


@dataclass(frozen=True, slots=True)
class _PlacedObject:
    """One object already committed inside a joint-placement attempt: what a
    later, lower-priority object must place itself around."""

    obj: PhysicalObject
    position: Vec3
    bounds: CellBox
    rung: LadderRung | None
    ink_min: CellBox
    ink_max_inflated: CellBox


# Structural search bounds for joint placement. Plan §6.2 rule 4 admits
# "explicit configured **or code-level** maxima"; these are search *structure*
# (how finely the free-space scan samples the frame), not calibrated visual
# tuning, so they live here rather than becoming unapproved `scene:` values.
_SLOT_COLS = 7
"""Columns in the deterministic screen-space free-slot lattice."""
_SLOT_ROWS = 5
"""Rows in that lattice."""
_DEPTH_STRATA = 4
"""Depths sampled from a flexible object's feasible z-band, per camera."""


_Outcome = Literal["accept", "move", "reject", "step_down", "reanchor"]


def _decision(
    rule_id: str,
    key: SceneKey | None,
    outcome: _Outcome,
    *,
    trace_prose: bool,
    reason: str = "",
    inputs: tuple[tuple[str, int | str], ...] = (),
) -> Decision:
    return Decision(
        rule_id=rule_id,
        key=key,
        outcome=outcome,
        inputs=inputs,
        reason=reason if trace_prose else "",
    )


def _absolute_region(
    obj: PhysicalObject, positions: dict[SceneKey, Vec3], cfg: SceneTuning
) -> Region:
    """Where `obj` may be placed, in absolute scene units.

    An object with a placed parent uses
    `SceneTuning.orbit_offset_region_by_scale_class` — a genuine offset box —
    re-based onto the parent's own position; everything else uses its
    absolute `obj.region` unchanged. Parents are placed before children
    because the retention order (`ANCHOR` < `ORBITAL`) already visits them
    first, and a parent that has not been placed at all falls back to the
    absolute region, exactly as `classify_sector` does.

    Before WP-SC12 there was only one region and it was *both*: the shipped
    `orbital`/`stardock` value was the absolute anchor box (`z 1..400`) while
    `region_by_scale_class`'s docstring described it as a parent offset, so a
    parented station was always at least 1 su behind its planet and up to 400
    behind. With the anchor framed to fill the viewport the camera sits close,
    so that put every parented station far past the depth at which any
    authored rung still clears — the `no_feasible_depth` rejection that lost
    the port in every `planet+port+…` cell of the gallery matrix. A class with
    no orbit-offset entry keeps the old behaviour exactly.
    """
    parent = obj.parent
    parented = parent is not None and parent in positions
    region = obj.region
    if parented and obj.scale_class in cfg.orbit_offset_region_by_scale_class:
        region = cfg.orbit_offset_region_by_scale_class[obj.scale_class]
    ox = oy = oz = 0
    if parented:
        assert parent is not None
        origin = positions[parent]
        ox, oy, oz = origin.x, origin.y, origin.z
    return Region(
        x_min=region.x_min + ox,
        x_max=region.x_max + ox,
        y_min=region.y_min + oy,
        y_max=region.y_max + oy,
        z_min=region.z_min + oz,
        z_max=region.z_max + oz,
    )


def _su_for_screen(
    strategy: ProjectionStrategy,
    camera: Camera,
    viewport: CellBox,
    z: int,
    want_col: int,
    want_row: int,
    box: CellBox,
) -> tuple[int, int] | None:
    """Run `project()`'s position algebra backwards: the integer su `(x, y)`
    that puts a `box`-sized object's top-left corner at `(want_col, want_row)`
    at depth `z`.

    `project()` computes, for both strategies,

        col = floor(vw/2 + (x - camx - aimx) * scale * cell_aspect - w/2)
        row = floor(vh/2 - (y - camy - aimy) * scale       - h/2)

    so given the strategy's exact `scale_at()` `Fraction` this inverts to an
    exact rational and floors once (plan §9.1: `floor` for positions). The
    result is an *estimate* only in the sense that the two floors do not
    commute perfectly -- the caller always re-`project()`s and re-checks every
    hard rule, so a one-cell drift costs a candidate, never correctness.
    """
    scale = strategy.scale_at(camera, viewport, z)
    if scale is None or scale <= 0:
        return None
    x_denom = scale * camera.cell_aspect
    if x_denom <= 0:
        return None
    cx = Fraction(want_col) - Fraction(viewport.width, 2) + Fraction(box.width, 2)
    cy = Fraction(viewport.height, 2) - Fraction(want_row) - Fraction(box.height, 2)
    x = camera.position.x + camera.aim_x_su + math.floor(cx / x_denom)
    y = camera.position.y + camera.aim_y_su + math.floor(cy / scale)
    return x, y


def _slot_lattice(viewport: CellBox, margin: int, box: CellBox) -> tuple[tuple[int, int], ...]:
    """The deterministic screen-space free-slot lattice a flexible object of
    projected size `box` may be placed on: `_SLOT_COLS * _SLOT_ROWS` top-left
    positions spread evenly across the margin-clipped viewport.

    Searching in *screen* space rather than su space is the point: separation,
    edge margin, and occlusion are all screen-space constraints, so a lattice
    here samples exactly the quantity the hard rules measure, and a slot can be
    rejected against already-placed boxes by integer rectangle arithmetic
    before any projection work happens.
    """
    col_lo = margin
    col_hi = viewport.width - margin - box.width
    row_lo = margin
    row_hi = viewport.height - margin - box.height
    if col_hi < col_lo or row_hi < row_lo:
        return ()
    def _spread(lo: int, hi: int, count: int) -> list[int]:
        if count <= 1 or hi == lo:
            return [lo + (hi - lo) // 2]
        return [lo + ((hi - lo) * i) // (count - 1) for i in range(count)]
    cols = _spread(col_lo, col_hi, _SLOT_COLS)
    rows = _spread(row_lo, row_hi, _SLOT_ROWS)
    return tuple((c, r) for r in rows for c in cols)


@lru_cache(maxsize=4096)
def _shuffled(key: SceneKey, salt: str, count: int) -> tuple[int, ...]:
    """A deterministic, key-dependent permutation of `range(count)`.

    Not randomness and not game RNG: a stable sort on a content hash, exactly
    like `_hash_index`. It exists to keep plan §2.5's "wide region" design
    intent real -- two ships in the same sector, and the same ship across
    different sectors/viewports, try the frame's depths and free slots in
    *different* orders, so admitted traffic spreads over the whole feasible
    volume instead of funnelling into whichever slot happens to be first.

    Cached because joint placement asks for the same permutation once per
    (object, depth) per camera candidate; the cache is a pure memo of a pure
    function, so it changes no result.
    """
    return tuple(
        sorted(
            range(count),
            key=lambda i: (_hash_index(f"{key.tag}:{key.ident}|{salt}|{i}", 1 << 32), i),
        )
    )


def _depth_strata(key: SceneKey, z_lo: int, z_hi: int, preferred: tuple[int, ...]) -> tuple[int, ...]:
    """Up to `_DEPTH_STRATA` depths sampled from a feasible z-band `[z_lo,
    z_hi]`, **nearest first**, with any `preferred` depths that fall inside
    the band tried ahead of them.

    `preferred` carries only the object's depth in the previous plan, when
    there is one -- plan §4.11's "minimize ... placement ... change after all
    hard rules are satisfied", expressed as candidate order rather than as a
    score term, so it can never overturn a hard rule or a retention decision.

    Two deliberate changes from the joint-placement redesign's first version,
    both aimed at the maintainer's "composers never use the larger sizes for
    the ships even on large screens" report (see the plan's "Ship apparent
    size" section):

    * the object's **classified base depth is no longer tried first**. For a
      flexible object that draw is a viewport-independent hash over the whole
      nominal region (plan §9.3) with no relationship to what the camera can
      show; it won whenever it happened to land in the feasible band, which
      pinned ship size to a coin flip. Its x/y counterparts were already
      unused for flexible objects (the screen-space slot lattice supersedes
      them), so this is the last vestige of the blind draw.
    * the sampled depths are ordered **near to far** instead of by a content
      hash. `z_lo` is the nearest depth the frame can contain, so a
      near-first walk takes the largest apparent size -- and therefore the
      richest authored rung -- the frame and the already-placed objects
      allow, falling back outward only when a nearer depth is actually
      refused.

    This does not flatten depth variation (plan §4.13, §2.5): placement runs
    in retention order against committed neighbours, so the first ship takes
    the near band and every later one is pushed outward by separation.
    Measured across the gallery matrix, admitted ships still reach 54
    distinct depths and box heights from 4 to 20 cells under
    `FixedFovPerspective`, and mean ship box height now *rises* with the
    canvas (6.3 / 7.1 / 8.4 / 9.1 cells at 67x30 / 87x36 / 120x44 / 150x52)
    where before it was flat at 5.0-5.4. Screen *position* variety is
    unaffected -- the slot lattice is still walked in `_shuffled` order.
    """
    if z_hi < z_lo:
        return ()
    span = z_hi - z_lo
    sampled = tuple(z_lo + (span * (2 * i + 1)) // (2 * _DEPTH_STRATA) for i in range(_DEPTH_STRATA))
    out: list[int] = []
    for z in preferred:
        if z_lo <= z <= z_hi and z not in out:
            out.append(z)
    for z in sampled:
        if z not in out:
            out.append(z)
    return tuple(out)


def _separation_exempt(
    obj: PhysicalObject, other: PhysicalObject, anchor_key: SceneKey, cfg: SceneTuning
) -> bool:
    """True for the one pair the separation margin must not apply to: a
    station and the scene anchor (WP-SC12).

    Separation exists so two objects do not read as a single mass (plan §2.4).
    A station beside the body it serves is the one case where the opposite is
    true: the arrival view's whole idiom is that the station hovers *at* the
    world, and the legacy composer says so explicitly — `_paint_station`
    berths it at the primary body's lower limb "overlapping the disc's
    bounding box a little so it reads as *at* the world", and never consults
    the occupancy map at all.

    Requiring a clear gap instead pushed the station out to whatever depth
    left room beside the body, which is a smaller authored rung than legacy
    draws, and on a canvas the body mostly fills there was no such depth. The
    exemption is narrow: only this pair, only the separation *margin*.
    Occlusion still applies in full — the anchor must still stay above
    `min_visible_fraction_by_scale_class["anchor"]`, so the station may sit
    against the body but never bury it.
    """
    if not cfg.station_target_by_scale_class:
        return False
    if obj.key == anchor_key:
        return other.scale_class in cfg.station_target_by_scale_class
    if other.key == anchor_key:
        return obj.scale_class in cfg.station_target_by_scale_class
    return False


def _projected_height_at(
    obj: PhysicalObject,
    z: int,
    camera: Camera,
    viewport: CellBox,
    strategy: ProjectionStrategy,
) -> int | None:
    """`obj`'s projected box height at depth `z`, placed at the camera's aim
    point (the same best-case-xy convention `_z_ok_near_and_size` uses), or
    `None` when `z` violates the near plane."""
    at = Vec3(camera.position.x + camera.aim_x_su, camera.position.y + camera.aim_y_su, z)
    try:
        return strategy.project(camera, obj, at, viewport).height
    except NearPlaneViolation:
        return None


def _depth_for_target_height(
    obj: PhysicalObject,
    target_h: int,
    camera: Camera,
    viewport: CellBox,
    strategy: ProjectionStrategy,
    z_lo: int,
    z_hi: int,
) -> int:
    """The depth in `[z_lo, z_hi]` whose projected height is closest to
    `target_h` (station-size parity, plan §9.6 "Station size parity").

    Projected height is non-increasing in `z` for both strategies (see
    `_z_ok_near_and_size`), so this is one bounded binary search —
    `O(log(z_hi - z_lo))` `project()` calls, never a scan (§6.2 rule 4) — for
    the largest `z` still projecting at least `target_h`, then an exact
    integer comparison of that `z` against `z + 1` to pick the nearer of the
    two heights straddling the target.

    Ties go to the farther depth — the *smaller* apparent size —
    deterministically. With a strategy whose depth is quantised the two
    straddling heights are often exactly equidistant from the target, and the
    legacy composer clamps a station's height rather than letting it grow, so
    the conservative direction is down: `DepthLayeredAnchorProjection` at
    120x44 can put a parented port at 12 cells or at 10 against a target of
    11, and 10 is the tier legacy draws while 12 is one richer.

    `[z_lo, z_hi]` is always the already-proven feasible band, so every depth
    considered here clears the near plane and the caller re-runs every hard
    rule on the result regardless.
    """
    def height(z: int) -> int:
        got = _projected_height_at(obj, z, camera, viewport, strategy)
        return got if got is not None else 0

    if z_hi <= z_lo:
        return z_lo
    if height(z_lo) <= target_h:
        return z_lo
    if height(z_hi) >= target_h:
        return z_hi
    lo, hi = z_lo, z_hi  # height(lo) > target_h >= ... > height(hi)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if height(mid) >= target_h:
            lo = mid
        else:
            hi = mid
    # `lo` is at or above the target, `hi` the first below it: keep whichever
    # is closer, ties to `hi` (the farther depth, the smaller size).
    return lo if (height(lo) - target_h) < (target_h - height(hi)) else hi


_NO_RUNG = 1 << 20
"""Sentinel rung index for a depth at which nothing authored clears, so it
sorts behind every real rung without a special case."""


def _target_rung_index(
    obj: PhysicalObject, target_h: int, catalog: ArtGeometryCatalog, cfg: SceneTuning
) -> int | None:
    """The authored rung a `target_h`-cell-tall request resolves to.

    The sprite library picks a tier from the requested **height** alone
    (`edge/art/sprites.py::fit_box`), which is why the legacy composer's
    `station_dimensions` height is enough to say which tier it draws; this
    reads the same choice off the catalogue. `None` for a non-laddered object
    or an empty ladder.
    """
    if obj.ladder_key is None:
        return None
    rungs = catalog.rungs(obj.ladder_key)
    if not rungs:
        return None
    exclude_from_end = cfg.min_rung_index_from_end_by_scale_class.get(obj.scale_class, 0)
    max_index = max(r.index for r in rungs)
    allowed = [r for r in rungs if r.index <= max_index - exclude_from_end]
    if not allowed:
        return None
    fits = [r for r in allowed if r.natural.height <= target_h]
    if fits:
        return max(fits, key=lambda r: (r.natural.height, -r.index)).index
    return max(r.index for r in allowed)


def _by_closest_size(
    obj: PhysicalObject,
    depths: tuple[int, ...],
    target_h: int,
    target_rung: int | None,
    camera: Camera,
    viewport: CellBox,
    cfg: SceneTuning,
    catalog: ArtGeometryCatalog,
    strategy: ProjectionStrategy,
) -> tuple[int, ...]:
    """`depths` reordered so the depth rendering the target *size* comes first.

    The authored rung is the primary key, because the rung is the size
    decision — projected height only chooses between tiers, and two depths a
    cell apart in projected height can be a whole tier apart or identical.
    `DepthLayeredAnchorProjection` shows why the distinction matters: its
    depth is quantised, so at 120x44 a parented starbase can project 14 cells
    or 11 against a target of 13. Ranking on height alone takes 14 (off by 1)
    and draws rung 0; ranking on rung takes 11, which is the rung 13 resolves
    to and the tier the legacy composer draws.

    Projected height breaks a rung tie, and the farther depth (the smaller
    apparent size) breaks that. Integer comparisons only, so the ordering is
    platform-stable (§4.1).
    """
    def key(z: int) -> tuple[int, int, int]:
        height = _projected_height_at(obj, z, camera, viewport, strategy)
        if height is None:
            return (_NO_RUNG, _NO_RUNG, -z)
        rung_gap = 0
        if target_rung is not None:
            at = Vec3(
                camera.position.x + camera.aim_x_su, camera.position.y + camera.aim_y_su, z
            )
            try:
                bounds = strategy.project(camera, obj, at, viewport)
            except NearPlaneViolation:
                return (_NO_RUNG, _NO_RUNG, -z)
            rung = _select_rung(catalog, obj, bounds, cfg)
            rung_gap = _NO_RUNG if rung is None else abs(rung.index - target_rung)
        return (rung_gap, abs(height - target_h), -z)

    return tuple(sorted(depths, key=key))


def _station_target_height(
    obj: PhysicalObject, viewport: CellBox, cfg: SceneTuning, *, parented: bool
) -> int | None:
    """`obj`'s target projected ink height, or `None` when its scale class
    declares none (every non-station class today)."""
    target = cfg.station_target_by_scale_class.get(obj.scale_class)
    if target is None or cfg.station_size_reference is None:
        return None
    return target.target_height(viewport, cfg.station_size_reference, parented=parented)



def _prefer_clear_of_anchor(
    order: tuple[int, ...],
    slots: tuple[tuple[int, int], ...],
    box: CellBox,
    obj: PhysicalObject,
    placed: list[_PlacedObject],
    anchor_key: SceneKey,
    cfg: SceneTuning,
) -> tuple[int, ...]:
    """`order` partitioned into slots that clear the anchor's ink and slots
    that do not, each keeping its original relative order.

    Only ever reorders, so it cannot change what is admissible — every slot in
    `order` is still tried, and the caller's bounded budget is unchanged. It
    exists solely so `_separation_exempt`'s allowance (a station may touch the
    body it orbits) does not become a preference for sitting on top of it.
    """
    if not cfg.station_target_by_scale_class:
        return order
    if obj.scale_class not in cfg.station_target_by_scale_class:
        return order
    anchor = next((p for p in placed if p.obj.key == anchor_key), None)
    if anchor is None:
        return order
    clear: list[int] = []
    over: list[int] = []
    for index in order:
        col, row = slots[index]
        probe = CellBox(col, row, box.width, box.height)
        (over if _rect_gap(probe, anchor.ink_max_inflated) < 0 else clear).append(index)
    return tuple((*clear, *over))


def _evaluate_placement(
    obj: PhysicalObject,
    pos: Vec3,
    camera: Camera,
    viewport: CellBox,
    cfg: SceneTuning,
    catalog: ArtGeometryCatalog,
    strategy: ProjectionStrategy,
    placed: list[_PlacedObject],
    anchor_key: SceneKey,
    anchor_box_class: int | None,
    remaining_cost: int,
    result: _Attempt,
) -> tuple[_PlacedObject | None, str]:
    """Every hard rule of plan §9.6's `attempt`, for one object at one
    position, against the objects already committed in this attempt.

    Rules run in the plan's cheapest-and-most-rejecting-first order:
    near-plane, containment/edge margin, minimum projected size, ladder rung /
    continuous minimum ink extent, pairwise separation, then depth occlusion.
    Returns `(placement, "")` on success or `(None, rule_id)` on the first
    rule that refuses it.
    """
    try:
        bounds = strategy.project(camera, obj, pos, viewport)
    except NearPlaneViolation:
        return None, "near_plane"
    if not _contained(bounds, viewport, cfg.edge_margin):
        return None, "edge_margin"
    min_w, min_h = cfg.min_projected_cells_by_scale_class[obj.scale_class]
    if bounds.width < min_w or bounds.height < min_h:
        return None, "min_projected_size"

    rung: LadderRung | None = None
    if obj.art_mode is ArtMode.LADDER:
        # Cost-aware from the start (plan §4.14): the richest rung that both
        # fits *and* is affordable out of what retention order has left. See
        # `_select_rung`'s `max_cost` note for why picking richest-then-vetoing
        # dropped objects that had a cheaper authored tier right there.
        rung = _select_rung(catalog, obj, bounds, cfg, remaining_cost)
        if rung is None:
            # Distinguish the two causes in the trace: a purely geometric
            # "nothing authored fits here" is a different fact for a reviewer
            # than "something fits but the budget is spent" (plan §4.20).
            return None, (
                "no_clearing_rung"
                if _select_rung(catalog, obj, bounds, cfg) is None
                else "cost_budget"
            )
    else:
        assert obj.continuous_kind is not None
        yield_ = catalog.continuous(obj.continuous_kind)
        probe = _ink_box(obj, bounds, None, catalog, side="min")
        if probe.width < yield_.min_extent.width or probe.height < yield_.min_extent.height:
            return None, "min_ink_extent"

    ink_min = _ink_box(obj, bounds, rung, catalog, side="min")
    ink_max_inflated = _inflate(
        _ink_box(obj, bounds, rung, catalog, side="max"), cfg.separation_margin
    )

    slack = _LARGE_SLACK
    if obj.occludes:
        for other in placed:
            if not other.obj.occludes:
                continue
            if _separation_exempt(obj, other.obj, anchor_key, cfg):
                continue
            gap = _rect_gap(ink_max_inflated, other.ink_max_inflated)
            if gap < 0:
                return None, "separation"
            slack = min(slack, gap)

    # Occlusion by depth: the *farther* object of a pair must stay above its
    # class's minimum visible fraction. A new object can only ever lose here,
    # never unseat an already-committed one -- placement runs in retention
    # order, so everything already committed outranks it (plan §4.5).
    own_visible = Fraction(1)
    # Visible fractions this placement would impose on already-committed
    # objects, applied only if the placement is committed -- a candidate that
    # is refused below must leave no trace on the attempt (plan §4.1: nothing
    # the solver decides may depend on which candidates were tried).
    imposed: list[tuple[SceneKey, Fraction]] = []
    if obj.occludes:
        for other in placed:
            if not other.obj.occludes:
                continue
            if pos.z == other.position.z:
                continue
            result.occlusion_comparisons += 1
            if pos.z > other.position.z:
                near_box, far_ink, far_class = other.ink_max_inflated, ink_min, obj.scale_class
            else:
                near_box, far_ink, far_class = ink_max_inflated, other.ink_min, other.obj.scale_class
            area = far_ink.width * far_ink.height
            if area <= 0:
                continue
            visible = Fraction(area - _overlap_area(near_box, far_ink), area)
            if visible < cfg.min_visible_fraction_by_scale_class[far_class]:
                return None, "min_visible_fraction"
            if pos.z > other.position.z:
                own_visible = min(own_visible, visible)
            else:
                imposed.append((other.obj.key, visible))

    box_class = anchor_box_class if (obj.key == anchor_key and rung is None) else None
    # Cost is a hard rule like any other (plan §4.14). A laddered object has
    # already been *selected* within budget above, so this only ever binds a
    # continuous one, whose box class is fixed by the anchor step-down ladder
    # rather than chosen here -- for that one there is no cheaper alternative
    # at this position, so refusing the candidate is the whole remedy.
    cost = (
        rung.render_cost if rung is not None
        else catalog.continuous(str(obj.continuous_kind)).render_cost[box_class or 0]
    )
    if cost > remaining_cost:
        return None, "cost_budget"

    if slack < result.min_separation_slack:
        result.min_separation_slack = slack
    result.bounds[obj.key] = bounds
    result.rung[obj.key] = rung
    result.box_class[obj.key] = box_class
    result.visible_fraction[obj.key] = own_visible
    for other_key, fraction in imposed:
        result.visible_fraction[other_key] = min(result.visible_fraction[other_key], fraction)
    result.positions[obj.key] = pos
    return _PlacedObject(
        obj=obj, position=pos, bounds=bounds, rung=rung, ink_min=ink_min,
        ink_max_inflated=ink_max_inflated,
    ), ""


def _attempt(
    camera: Camera,
    admitted: list[PhysicalObject],
    base_positions: dict[SceneKey, Vec3],
    viewport: CellBox,
    cfg: SceneTuning,
    catalog: ArtGeometryCatalog,
    strategy: ProjectionStrategy,
    anchor_key: SceneKey,
    anchor_box_class: int | None,
    previous_depths: dict[SceneKey, int],
    z_memo: dict[tuple[SceneKey, int, int, int], tuple[int, int] | None],
    *,
    trace_prose: bool,
) -> _Attempt:
    """Place *and* admit every currently-admitted object under one candidate
    camera (the WP-SC09 joint-placement redesign; see the plan's
    "Joint secondary-object placement" section).

    The pre-redesign `_attempt` projected fixed, camera-blind placements and
    could only report which of them happened to survive; whether a ship was
    placed somewhere the accepted camera could show it was decided *outside*
    the candidate loop, against a different (merely framed) camera. Here,
    placement is part of the candidate's own evaluation:

    * objects are visited in retention-priority order -- the exact
      `(retention, hostility_ordinal, -threat_rank, key)` order `solve` sorts
      `admitted` into -- so a higher-priority object always chooses its
      position before, and independently of, every lower-priority one
      (plan §4.5/§4.6);
    * an inflexible object has exactly one candidate position, its classified
      one, so anchors/planets/the Entity are unmoved (plan §2.4/§4.3);
    * a flexible object searches its own feasible volume *against this
      camera*: the z-band `_feasible_z_interval` proves workable, then, at
      each sampled depth, a screen-space lattice of free slots that clears
      every already-committed object's inflated ink box.

    This is a deterministic **greedy** joint search, not an exhaustive one: it
    never backtracks to move a higher-priority object so a lower-priority one
    can fit. That is the bounded-work tradeoff plan §6.2 rule 4 requires --
    an exhaustive joint search over `n` objects and `k` positions is `k**n` --
    and it is also the only ordering that cannot violate §4.5, since the
    object that "wins" a contested slot is always the higher-priority one.
    `_attempt` never mutates `admitted` or `base_positions`.
    """
    result = _Attempt(camera=camera)
    placed: list[_PlacedObject] = []
    cost = 0
    ship_count = 0

    for obj in admitted:
        base = base_positions[obj.key]
        reason = "no_feasible_placement"
        committed: _PlacedObject | None = None

        # Plan §4.14: "Cost is spent in retention order." Spending it *here*,
        # as the greedy walk reaches each object, is what makes that literal --
        # the pre-redesign `_attempt` summed the whole scene and, on overflow,
        # cleared the entire admitted set, so a 50-ship inventory produced an
        # empty plan instead of the affordable high-priority prefix (and, with
        # `max_passes` far below the number of ships to shed, the pass loop's
        # reject ladder could never converge on one either -- a §4.18
        # violation). The cheapest authored rung / box class bounds an object's
        # cost from below, so an object that cannot be afforded even at its
        # cheapest is refused before any placement search is spent on it.
        floor_cost = _cheapest_cost(obj, catalog, cfg)
        is_ship = obj.key.tag in ("ship", "player")
        if is_ship and ship_count + 1 > cfg.emergency_ship_ceiling:
            result.min_violations += 1
            result.positions.setdefault(obj.key, base)
            result.decisions.append(
                _decision(
                    "emergency_ship_ceiling", obj.key, "reject", trace_prose=trace_prose,
                    reason="emergency ship ceiling reached",
                )
            )
            continue
        if cost + floor_cost > cfg.cost_budget:
            result.min_violations += 1
            result.positions.setdefault(obj.key, base)
            result.decisions.append(
                _decision(
                    "cost_budget", obj.key, "reject", trace_prose=trace_prose,
                    reason="render-cost budget exhausted in retention order",
                )
            )
            continue

        if not obj.flexible:
            result.placement_evaluations += 1
            committed, why = _evaluate_placement(
                obj, base, camera, viewport, cfg, catalog, strategy, placed,
                anchor_key, anchor_box_class, cfg.cost_budget - cost, result,
            )
            if committed is None:
                reason = why
        else:
            region = _absolute_region(obj, result.positions, cfg)
            x_min, x_max = region.x_min, region.x_max
            y_min, y_max = region.y_min, region.y_max
            z_min, z_max = region.z_min, region.z_max
            # One bounded binary-search pair per (object, camera), memoised
            # across the pass loop because `candidates()` re-yields the same
            # camera set on every pass. The memo is a pure function of its key
            # -- object, camera depth, and aim -- so it changes no result.
            memo_key = (obj.key, camera.position.z, camera.aim_x_su, camera.aim_y_su)
            if memo_key in z_memo:
                z_band = z_memo[memo_key]
            else:
                z_band = _feasible_z_interval(
                    camera, obj, viewport, cfg, catalog, strategy, z_min, z_max
                )
                z_memo[memo_key] = z_band
            if z_band is None:
                # `_feasible_z_interval` evaluates the depth-dependent rules at
                # the camera's own aim point, which is the most permissive xy
                # there is: a box too large to be contained when centred cannot
                # be contained anywhere, and the minimum-size/rung/ink-extent
                # rules do not depend on xy at all. An empty band therefore
                # means *no* placement of this object can pass under this
                # camera, so the slot scan below is skipped outright rather
                # than spending its budget proving it. (The pre-redesign
                # reposition fallback fell back to the full region here; it had
                # to, because it drew a single blind sample and a fallback was
                # its only alternative to giving up. Joint placement gets the
                # same object a fresh chance under every other camera
                # candidate, so the honest early reject is strictly better than
                # a sample that cannot pass.)
                result.min_violations += 1
                result.positions.setdefault(obj.key, base)
                result.decisions.append(
                    _decision(
                        "no_feasible_depth", obj.key, "reject", trace_prose=trace_prose,
                        reason="no depth in this object's region clears the hard rules "
                               "under this camera",
                    )
                )
                continue
            z_lo, z_hi = z_band
            # Only the previous plan's depth (resize hysteresis, §4.11). The
            # classified `base.z` is deliberately *not* preferred here -- see
            # `_depth_strata`.
            preferred: list[int] = []
            # Station-size parity (plan §9.6 "Station size parity"): a scale
            # class with a declared target projected height puts the depth
            # achieving that height first, ahead of the previous plan's depth
            # and the near-to-far strata. Both are candidate *ordering* only —
            # every candidate still goes through the identical
            # `_evaluate_placement`, so this can no more overturn a hard rule
            # than §4.11's hysteresis ordering can.
            target_h = _station_target_height(
                obj, viewport, cfg,
                parented=obj.parent is not None and obj.parent in result.positions,
            )
            if target_h is not None:
                preferred.append(
                    _depth_for_target_height(
                        obj, target_h, camera, viewport, strategy, z_lo, z_hi
                    )
                )
            prev_z = previous_depths.get(obj.key)
            if prev_z is not None and prev_z not in preferred:
                preferred.append(prev_z)
            budget = cfg.max_reposition_candidates
            strata = _depth_strata(obj.key, z_lo, z_hi, tuple(preferred))
            if target_h is not None:
                # Order the whole bounded candidate list by how close each
                # depth lands to the target *size*, so a refused first choice
                # falls back to the next-closest size rather than to the
                # nearest (and therefore largest) depth left.
                strata = _by_closest_size(
                    obj, strata, target_h,
                    _target_rung_index(obj, target_h, catalog, cfg),
                    camera, viewport, cfg, catalog, strategy,
                )
            for z in strata:
                if committed is not None or budget <= 0:
                    break
                extent = strategy.visible_xy_extent(camera, viewport, z, obj.face, cfg)
                xy = intersect_region_xy(region, extent)
                bounds_probe: CellBox | None = None
                try:
                    bounds_probe = strategy.project(
                        camera, obj,
                        Vec3(camera.position.x + camera.aim_x_su, camera.position.y + camera.aim_y_su, z),
                        viewport,
                    )
                except NearPlaneViolation:
                    continue
                slots = _slot_lattice(viewport, cfg.edge_margin, bounds_probe)
                if not slots:
                    continue
                order = _shuffled(obj.key, f"slot|{z}", len(slots))
                # The separation exemption (`_separation_exempt`) lets a
                # station *touch* the scene anchor; it should not make one
                # settle on the anchor's face when there is clear sky. Slots
                # that clear the anchor's ink outright are tried first, in the
                # unchanged `_shuffled` order, and the overlapping ones only
                # after -- so a crowded scene still admits the station (which
                # is what the exemption is for) while an uncrowded one berths
                # it beside the body, the way the legacy composer does. This is
                # candidate ordering only; nothing is newly refused, and the
                # partition is an integer rectangle test (§4.1).
                order = _prefer_clear_of_anchor(
                    order, slots, bounds_probe, obj, placed, anchor_key, cfg
                )
                for index in order:
                    if budget <= 0:
                        break
                    col, row = slots[index]
                    probe = _inflate(
                        CellBox(col, row, bounds_probe.width, bounds_probe.height),
                        cfg.separation_margin,
                    )
                    if obj.occludes and any(
                        p.obj.occludes
                        and not _separation_exempt(obj, p.obj, anchor_key, cfg)
                        and _rect_gap(probe, p.ink_max_inflated) < 0
                        for p in placed
                    ):
                        continue
                    su = _su_for_screen(strategy, camera, viewport, z, col, row, bounds_probe)
                    if su is None:
                        continue
                    x = min(max(su[0], x_min), x_max)
                    y = min(max(su[1], y_min), y_max)
                    if xy is not None:
                        x = min(max(x, xy[0]), xy[1])
                        y = min(max(y, xy[2]), xy[3])
                    budget -= 1
                    result.placement_evaluations += 1
                    candidate, why = _evaluate_placement(
                        obj, Vec3(x, y, z), camera, viewport, cfg, catalog, strategy, placed,
                        anchor_key, anchor_box_class, cfg.cost_budget - cost, result,
                    )
                    if candidate is not None:
                        committed = candidate
                        break
                    reason = why

        if committed is None:
            result.min_violations += 1
            result.positions.setdefault(obj.key, base)
            result.decisions.append(
                _decision(reason, obj.key, "reject", trace_prose=trace_prose, reason=reason)
            )
            continue

        cost += _actual_cost(committed, catalog, result.box_class[obj.key])
        ship_count += is_ship
        placed.append(committed)
        result.accepted.add(obj.key)

    result.cost_estimated = cost
    return result


def _cheapest_cost(obj: PhysicalObject, catalog: ArtGeometryCatalog, cfg: SceneTuning) -> int:
    """The least this object could possibly cost to render: its cheapest
    authored rung, or its cheapest continuous box class (plan §4.14 -- ladder
    costs assume no monotonicity by rung, so this is a `min`, not the last
    entry).

    Excludes the same worst-`N` rung indices `_select_rung` refuses to select
    (minimum-richness fix), so the floor's cost estimate stays a true lower
    bound on what this object could actually be rendered at."""
    if obj.art_mode is ArtMode.LADDER:
        assert obj.ladder_key is not None
        rungs = catalog.rungs(obj.ladder_key)
        if not rungs:
            return 0
        exclude_from_end = cfg.min_rung_index_from_end_by_scale_class.get(obj.scale_class, 0)
        max_index = max(r.index for r in rungs)
        allowed = [r for r in rungs if r.index <= max_index - exclude_from_end]
        return min((r.render_cost for r in allowed), default=0)
    assert obj.continuous_kind is not None
    return min(catalog.continuous(obj.continuous_kind).render_cost, default=0)


def _actual_cost(
    entry: _PlacedObject, catalog: ArtGeometryCatalog, box_class: int | None
) -> int:
    if entry.rung is not None:
        return entry.rung.render_cost
    assert entry.obj.continuous_kind is not None
    return catalog.continuous(entry.obj.continuous_kind).render_cost[box_class or 0]



def _rejected_by_retention(
    attempt: _Attempt, inventory: list[PhysicalObject]
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

    `inventory` is the solve's **full**, never-shrunk admitted list, not the
    pass's current one -- see `solve`'s `inventory` local and the plan's
    "Retention scoring counted against the shrinking admitted set" section.
    An object the fallback ladder has already ejected is still counted as
    rejected here, because from the *viewer's* point of view it is: it is
    absent from the scene either way. Scoring against the pass-local list
    instead made ejection itself improve the score -- a pass that had shed
    everything but the anchor reported zero rejections and so beat an
    earlier pass that placed the anchor and both ships but missed one
    station, which is the same §4.5 inversion this tuple exists to prevent,
    reached from the opposite direction.
    """
    counts = [0] * len(SceneRetention)
    for obj in inventory:
        if obj.key not in attempt.accepted:
            counts[int(obj.retention)] += 1
    return tuple(counts)


def _z_ok_near_and_size(
    z: int,
    camera: Camera,
    obj: PhysicalObject,
    viewport: CellBox,
    cfg: SceneTuning,
    catalog: ArtGeometryCatalog,
    strategy: ProjectionStrategy,
) -> tuple[bool, bool]:
    """Evaluate `obj` at depth `z`, placed at the camera's own aim point (the
    same best-case-xy convention `_visible_xy_extent_from_scale` already uses
    for the xy half of this fix), against every depth-dependent hard rule
    `_attempt()` applies: near-plane, edge-margin/containment ("too big"),
    `min_projected_size`, and (ladder) `no_clearing_rung` / (continuous)
    `min_ink_extent` ("too small").

    Returns `(not_too_big, not_too_small)`. Both are independently monotonic
    in `z` for either strategy -- `scale(z)` is non-increasing in `z` for
    both `FixedFovPerspective`'s continuous divide-by-depth and
    `DepthLayeredAnchorProjection`'s step function, so a farther z can never
    project a *larger* box than a nearer one -- which is what lets
    `_feasible_z_interval` binary-search each bound independently instead of
    needing a closed-form inversion per strategy.
    """
    at = Vec3(camera.position.x + camera.aim_x_su, camera.position.y + camera.aim_y_su, z)
    try:
        bounds = strategy.project(camera, obj, at, viewport)
    except NearPlaneViolation:
        return False, False
    not_too_big = _contained(bounds, viewport, cfg.edge_margin)
    min_w, min_h = cfg.min_projected_cells_by_scale_class[obj.scale_class]
    not_too_small = bounds.width >= min_w and bounds.height >= min_h
    if not_too_small:
        if obj.art_mode is ArtMode.LADDER:
            not_too_small = _select_rung(catalog, obj, bounds, cfg) is not None
        else:
            assert obj.continuous_kind is not None
            yield_ = catalog.continuous(obj.continuous_kind)
            ink_min_box = _ink_box(obj, bounds, None, catalog, side="min")
            not_too_small = (
                ink_min_box.width >= yield_.min_extent.width
                and ink_min_box.height >= yield_.min_extent.height
            )
    return not_too_big, not_too_small


def _feasible_z_interval(
    camera: Camera,
    obj: PhysicalObject,
    viewport: CellBox,
    cfg: SceneTuning,
    catalog: ArtGeometryCatalog,
    strategy: ProjectionStrategy,
    z_min: int,
    z_max: int,
) -> tuple[int, int] | None:
    """The z-subinterval of `[z_min, z_max]` (an object's own region depth
    bounds) where `obj` clears every depth-dependent hard rule -- the same
    "invert the forward math to find the exact feasible band" technique the
    xy fix applies to `visible_xy_extent`, extended to z (plan §9.6
    frustum-aware reposition, z half).

    Rather than deriving a closed-form inversion of `scale(z)` per strategy
    (`FixedFovPerspective`'s `Fraction` divide vs.
    `DepthLayeredAnchorProjection`'s discrete per-layer power -- two
    different formulas, and for a laddered object a further per-rung
    natural-size threshold on top), this reuses `strategy.project()` and the
    exact same `_contained`/`_select_rung`/`_ink_box` functions `_attempt()`
    itself calls as an oracle, and finds each bound by bounded binary search
    (`O(log(z_max - z_min))` `project()` calls, never an open-ended scan --
    plan §6.2 rule 4). This is possible, and exact, because
    `_z_ok_near_and_size`'s two indicators are each monotonic in z: the
    "too big" (near-plane/edge-margin) failure can only happen for z too
    close to the camera, and the "too small" (min-size/no-clearing-rung/
    min-ink-extent) failure can only happen for z too far -- so a laddered
    object's discrete rung ladder does not need a union over rungs here:
    since every rung's natural box only ever changes the *threshold* size at
    which "too small" flips (never the direction), the set of feasible rungs
    collapses to a single contiguous z-band exactly like the continuous
    case, with the smallest authored rung's natural size setting the far
    edge.

    Returns `None` when no z in `[z_min, z_max]` clears every rule (the
    feasible band is empty, or `z_min > z_max`) -- the caller falls back to
    the untouched full region z-range in that case, exactly the pre-fix
    behaviour, so this can only ever help, never newly reject a placement.
    """
    if z_min > z_max:
        return None
    # Near-plane clamp: `_z_ok_near_and_size` reports `(False, False)` for any
    # z that violates the near-plane check (`dz <= 0` or `z < near_plane_su`),
    # which is a *third*, independent failure mode, not "too small" -- z near
    # `z_min` is frequently *behind* the camera for a wide region (a ship's
    # region commonly starts at world z=0/1 while the framed camera sits far
    # forward of the anchor), so treating that `False` as "too small at the
    # near end" would corrupt the monotonic assumption the two searches below
    # depend on. Restricting both searches to the sub-range that already
    # clears the near-plane check removes the confound before it can bite.
    z_valid_min = max(z_min, camera.near_plane_su, camera.position.z + 1)
    if z_valid_min > z_max:
        return None

    lo_big, lo_small = _z_ok_near_and_size(z_valid_min, camera, obj, viewport, cfg, catalog, strategy)
    hi_big, hi_small = _z_ok_near_and_size(z_max, camera, obj, viewport, cfg, catalog, strategy)

    if lo_big:
        z_lo = z_valid_min
    elif not hi_big:
        return None
    else:
        lo, hi = z_valid_min, z_max
        while hi - lo > 1:
            mid = (lo + hi) // 2
            mid_big, _ = _z_ok_near_and_size(mid, camera, obj, viewport, cfg, catalog, strategy)
            if mid_big:
                hi = mid
            else:
                lo = mid
        z_lo = hi

    if hi_small:
        z_hi = z_max
    elif not lo_small:
        return None
    else:
        lo, hi = z_valid_min, z_max
        while hi - lo > 1:
            mid = (lo + hi) // 2
            _, mid_small = _z_ok_near_and_size(mid, camera, obj, viewport, cfg, catalog, strategy)
            if mid_small:
                lo = mid
            else:
                hi = mid
        z_hi = lo

    if z_lo > z_hi:
        return None
    return (z_lo, z_hi)


def _score(
    attempt: _Attempt,
    inventory: list[PhysicalObject],
    anchor_key: SceneKey,
    target_height: int,
    previous: ScenePlan | None,
    cfg: SceneTuning,
) -> tuple[tuple[int, ...], int, int, int, int, int, str]:
    """Plan §9.6 `better_of`'s lexicographic tuple, all ascending-better --
    with the retention-priority guard (`_rejected_by_retention`) prepended
    ahead of the raw accepted-count term (see that function's docstring).

    `inventory` is the solve's full, never-shrunk admitted list so that both
    of the first two terms measure the same fixed denominator across every
    pass; comparing attempts drawn from differently-sized admitted sets is
    what the pass loop does by construction.
    """
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
        _rejected_by_retention(attempt, inventory),
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
    # The full inventory, fixed for the whole solve. `admitted` shrinks as the
    # fallback ladder ejects objects; `inventory` never does, so `_score`'s
    # retention term measures every attempt against the same denominator
    # (see `_rejected_by_retention`).
    inventory = list(admitted)

    if not admitted:
        base_camera = _base_starfield_camera(cfg)
        plan = _starfield_plan(viewport, mode, strategy.name, base_camera)
        return _with_glyph_trace(plan, arrangement, viewport, cfg)

    trace: list[Decision] = []
    counters = {
        "camera_candidates": 0, "reposition_candidates": 0, "passes": 0, "reanchors": 0,
        "step_downs": 0, "occlusion_comparisons": 0,
    }
    # Plan §4.11: the only placement state carried across a resize is the
    # previous plan's per-object depth, used purely as the first entry of a
    # flexible object's own deterministic candidate order (`_depth_strata`).
    # It cannot overturn a hard rule -- every candidate, preferred or not, goes
    # through the identical `_evaluate_placement` -- and it never reaches the
    # comparison tuple, where hysteresis stays the low-priority term §4.11
    # specifies.
    previous_depths: dict[SceneKey, int] = (
        {p.key: p.depth for p in previous.projections if p.accepted} if previous is not None else {}
    )
    z_memo: dict[tuple[SceneKey, int, int, int], tuple[int, int] | None] = {}
    last_failure: dict[SceneKey, str] = {}

    best: _Attempt | None = None
    best_score: tuple[tuple[int, ...], int, int, int, int, int, str] | None = None
    best_admitted: list[PhysicalObject] | None = None

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
                anchor.key, anchor_box_class, previous_depths, z_memo, trace_prose=trace_prose,
            )
            counters["occlusion_comparisons"] += attempt.occlusion_comparisons
            counters["reposition_candidates"] += attempt.placement_evaluations
            # Plan §4.20 legibility: remember why each object last failed a
            # hard rule under *some* camera, so a later `retention_reject`
            # (which by construction happens in a pass where the object is
            # no longer in `admitted`, and so carries no hard-rule decision
            # of its own) can still name the underlying cause instead of
            # reporting only "lowest retention priority".
            for decision in attempt.decisions:
                if decision.key is not None and decision.outcome == "reject":
                    last_failure[decision.key] = decision.rule_id
            score = _score(attempt, inventory, anchor.key, target_h, previous, cfg_current)
            if best_score is None or score < best_score:
                best = attempt
                best_score = score
                best_admitted = admitted
            if attempt.hard_ok(len(admitted)):
                found_hard_ok = True
                break
        if found_hard_ok:
            assert best is not None and best_admitted is not None
            return _finish(
                best, best_admitted, all_objects, viewport, mode, strategy.name, catalog,
                counters, trace, arrangement, cfg, trace_prose=trace_prose,
            )

        # Fallback ladder, in order: anchor box-class step-down -> retention
        # reject. The pre-redesign ladder had a third, first rung -- move one
        # flexible object per pass, against the pass's *framed* camera, and
        # re-run the whole camera sweep. Joint placement subsumes it: every
        # flexible object now chooses its position inside `_attempt`, against
        # the exact candidate camera being judged, so there is nothing left for
        # a separate blind reposition step to do and passes are no longer spent
        # on it. `SolveCounters.reposition_candidates` therefore now reports
        # the placement candidates joint placement actually evaluated (see the
        # plan's "Joint secondary-object placement" section).
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
            cause = last_failure.get(drop.key, "")
            trace.append(
                _decision(
                    "retention_reject", drop.key, "reject", trace_prose=trace_prose,
                    reason=(
                        "lowest retention priority; last hard-rule failure was "
                        f"{cause}" if cause else
                        "lowest retention priority; this object cleared every hard "
                        "rule but the scene as a whole did not"
                    ),
                    inputs=(("last_failure", cause),) if cause else (),
                )
            )
            continue

        break

    if best is None or best_admitted is None:
        base_camera = _base_starfield_camera(cfg)
        plan = _starfield_plan(viewport, mode, strategy.name, base_camera)
        return _with_glyph_trace(plan, arrangement, viewport, cfg)

    return _finish(
        best, best_admitted, all_objects, viewport, mode, strategy.name, catalog,
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
    works from a possibly-shrunk `admitted` list, so this rebuilds the minimal
    view `frame()` needs without mutating the caller's original arrangement.
    `placements` is the classifier's immutable base map -- joint placement
    keeps its per-candidate positions on the `_Attempt`, never here.
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
                depth=attempt.positions[obj.key].z,
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
