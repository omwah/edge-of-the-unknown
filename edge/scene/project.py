"""Projection strategies with injected parameters (plan §9.3, §9.5, WP-SC03).

Two concrete `ProjectionStrategy` implementations are compared behind one
typed interface, neither privileged: `FixedFovPerspective` (true divide-by-
depth perspective) and `DepthLayeredAnchorProjection` (discrete depth layers,
no per-object divide). WP-SC04 runs both through the calibration gallery and
picks a production strategy; the loser is deleted then, not now.

Everything that feeds a decision -- scale, position, size -- is
`fractions.Fraction` or `int`. `float` never appears in this module. Cell
rounding is `floor` for positions and round-half-even for extents, applied to
a `Fraction`, per plan §9.1 "Exact arithmetic" and §4 invariant 1.

Scope note (WP-SC03 vs WP-SC06): `candidates()` here explores only camera
framing height/aim variations for a single anchor -- it does not run the hard
constraint checks (separation, occlusion-rejection, cost budget) from plan
§9.6, because none of the state those checks need (a full projected plan,
retained-object set, previous-plan admission) exists until the solver
(`edge/scene/solve.py`) is implemented in WP-SC06. `hysteresis_delta()` below
is the same scoping: it computes the deterministic integer terms of plan
§9.6's hysteresis metric from values a caller already has in hand, but does
not itself walk a `ScenePlan` -- that wiring is WP-SC06's.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import replace
from fractions import Fraction
from typing import Protocol

from edge.scene.catalog import ArtGeometryCatalog, LadderRung
from edge.scene.geometry import CellBox, Face, Region, Su, Vec3
from edge.scene.model import (
    ArtMode,
    Camera,
    PhysicalObject,
    SceneKey,
    SceneTuning,
    WorldArrangement,
)


def round_half_even(value: Fraction) -> int:
    """Round a `Fraction` to the nearest `int`, ties to even (plan §9.1).

    `Fraction` has no built-in round-half-even; `round()` on a `Fraction`
    already implements banker's rounding in Python, so this is a thin,
    explicitly-named wrapper documenting that the choice is deliberate,
    not a "whatever `round()` happens to do" accident.
    """
    result = round(value)
    assert isinstance(result, int)
    return result


def structural_mode(viewport: CellBox, cfg: SceneTuning) -> str:
    """Select the hybrid structural mode from the drawable scene viewport
    (plan §9.1): first `(min_cols, min_rows, mode)` threshold both dimensions
    clear wins, most permissive (most demanding) first.
    """
    for min_cols, min_rows, mode in cfg.structural_mode_thresholds:
        if viewport.width >= min_cols and viewport.height >= min_rows:
            return mode
    raise ValueError(
        f"no structural_mode_thresholds entry matches viewport {viewport!r}; "
        "cfg.structural_mode_thresholds must include a catch-all floor entry"
    )


class ProjectionStrategy(Protocol):
    """One camera/projection algorithm, compared under identical inputs."""

    name: str

    def frame(
        self,
        arrangement: WorldArrangement,
        anchor: SceneKey,
        viewport: CellBox,
        cfg: SceneTuning,
        catalog: ArtGeometryCatalog,
    ) -> Camera: ...

    def candidates(
        self,
        camera: Camera,
        anchor: PhysicalObject,
        anchor_pos: Vec3,
        viewport: CellBox,
        cfg: SceneTuning,
    ) -> Iterator[Camera]: ...

    def project(
        self,
        camera: Camera,
        obj: PhysicalObject,
        at: Vec3,
        viewport: CellBox,
    ) -> CellBox: ...

    def visible_xy_extent(
        self,
        camera: Camera,
        viewport: CellBox,
        z: Su,
        face: Face,
        cfg: SceneTuning,
    ) -> tuple[Su, Su, Su, Su] | None: ...

    def scale_at(self, camera: Camera, viewport: CellBox, z: Su) -> Fraction | None: ...


class NearPlaneViolation(ValueError):
    """A camera placed an object at or behind `camera.near_plane_su`.

    Plan §9.2: "a candidate camera that would place any admitted object at
    `z <= near_plane_su` is rejected before projection, never clamped." A
    correct `frame()`/`candidates()` never yields such a camera for an
    object it means to place; this is a programming-invariant guard, not a
    normal control-flow rejection path.
    """


def _find_object(arrangement: WorldArrangement, key: SceneKey) -> PhysicalObject:
    for obj in arrangement.objects:
        if obj.key == key:
            return obj
    raise KeyError(f"no PhysicalObject for {key!r} in this WorldArrangement")


def _find_position(arrangement: WorldArrangement, key: SceneKey) -> Vec3:
    for placement in arrangement.placements:
        if placement.key == key:
            return placement.position
    raise KeyError(f"no Placement for {key!r} in this WorldArrangement")


def _nearest_rung_at_or_below(rungs: tuple[LadderRung, ...], want_h: int) -> LadderRung:
    """Plan §9.5 `frame()`: "`want_h` is ... snapped to the nearest rung at or
    below it". Falls back to the smallest available rung if every rung's
    natural height exceeds `want_h` -- the anchor still gets a camera; the
    solver's step-down/reject machinery (WP-SC06) is what may ultimately
    refuse the scene, not `frame()`.
    """
    below = [r for r in rungs if r.natural.height <= want_h]
    if below:
        return max(below, key=lambda r: (r.natural.height, -r.index))
    return min(rungs, key=lambda r: (r.natural.height, r.index))


def _target_natural_height(
    obj: PhysicalObject, cfg: SceneTuning, catalog: ArtGeometryCatalog, target_h: int
) -> tuple[int, LadderRung | None]:
    """Plan §9.5 `frame()`'s middle step: turn a target *ink* height (cells)
    into a target *natural/request-box* height (cells), snapping a laddered
    anchor to a real rung. Returns `(final_h, rung_or_none)`.
    """
    if obj.art_mode is ArtMode.LADDER:
        if obj.ladder_key is None:
            raise ValueError(f"{obj.key!r} is ArtMode.LADDER with no ladder_key")
        rungs = catalog.rungs(obj.ladder_key)
        if not rungs:
            raise ValueError(f"catalog has no rungs for {obj.ladder_key!r}")
        seed_ratio = cfg.ink_ratio_by_scale_class[obj.scale_class]
        seed_want_h = math.ceil(Fraction(target_h) / seed_ratio)
        rung = _nearest_rung_at_or_below(rungs, seed_want_h)
        # Re-derive against the chosen rung's own exact ink ratio, per §9.5:
        # "the camera re-derived from that rung, so the anchor never sits
        # between rungs."
        exact_ratio = Fraction(rung.ink_min.height, rung.natural.height)
        final_want_h = math.ceil(Fraction(target_h) / exact_ratio)
        rung = _nearest_rung_at_or_below(rungs, final_want_h)
        return rung.natural.height, rung
    if obj.continuous_kind is None:
        raise ValueError(f"{obj.key!r} is ArtMode.CONTINUOUS with no continuous_kind")
    yield_ = catalog.continuous(obj.continuous_kind)
    want_h = math.ceil(Fraction(target_h) / yield_.ink_fraction_min)
    return want_h, None


def _base_camera(cfg: SceneTuning, *, fov_num: int, fov_den: int) -> Camera:
    return Camera(
        position=Vec3(0, 0, 0),
        aim_x_su=0,
        aim_y_su=0,
        fov_num=fov_num,
        fov_den=fov_den,
        near_plane_su=cfg.near_plane_su,
        cell_aspect=cfg.cell_aspect,
        depth_layer_size_su=cfg.depth_layer_size_su,
        depth_layer_scale=cfg.depth_layer_scale,
    )


def _height_sweep(viewport: CellBox, cfg: SceneTuning, current_h: int) -> tuple[int, ...]:
    """The bounded, deterministic set of target anchor-ink heights (cells)
    `candidates()` explores, nearest-to-`current_h` first (plan §9.6's
    "nearest-to-current first", scoped down to WP-SC03's framing-only sweep).
    """
    h_hi = round_half_even(cfg.camera_height_fraction_max * viewport.height)
    h_lo = round_half_even(cfg.camera_height_fraction_min * viewport.height)
    if h_lo > h_hi:
        h_lo, h_hi = h_hi, h_lo
    h_lo = max(h_lo, 1)
    heights = list(range(h_lo, h_hi + 1))
    heights.sort(key=lambda h: (abs(h - current_h), h))
    return tuple(heights)


def _visible_xy_extent_from_scale(
    camera: Camera,
    viewport: CellBox,
    face: Face,
    cfg: SceneTuning,
    scale: Fraction,
) -> tuple[Su, Su, Su, Su] | None:
    """Invert `project()`'s own forward formulas (plan §9.6's frustum-aware
    reposition fix) to find the su-space (x_min, x_max, y_min, y_max) box
    that a `face`-sized object, placed anywhere inside it at the depth this
    `scale` was computed for, projects fully inside `viewport` with
    `cfg.edge_margin` clearance on every side -- exactly the same
    containment test `_contained()` (`edge/scene/solve.py`) applies after
    the fact, computed here in advance instead of by trial placement.

    Both `ProjectionStrategy` implementations share this: only their scale
    formula differs (a `Fraction` divide by depth vs. a discrete per-layer
    power), and both already reduce to one exact `scale` `Fraction` by the
    time `project()` computes `w_cells`/`h_cells`/`cx`/`cy` -- this function
    starts from that same `scale` and runs the position algebra in reverse.

    Returns `None` when `scale <= 0` (no visibility at this depth, mirroring
    `NearPlaneViolation`) or when the face is too large to fit inside the
    margin-clipped viewport at this depth at all (an empty extent) -- the
    caller falls back to the object's full nominal region in that case,
    exactly as if this helper did not exist, so it can only ever help, never
    newly reject a placement `_attempt()` would otherwise have allowed.

    Deterministic, exact-`Fraction`/`int` only (plan §4.1): the two `- 1`
    terms below are an integer safety margin absorbing `project()`'s own
    `floor()` rounding at the edges, not a tuned or approximated value, so a
    `(x, y)` drawn from inside the returned box is *conservatively*
    guaranteed to clear `_contained()`, never merely likely to.
    """
    if scale <= 0:
        return None
    w_cells = round_half_even(Fraction(face.width_su) * scale * camera.cell_aspect)
    h_cells = round_half_even(Fraction(face.height_su) * scale)
    cx_max = Fraction(viewport.width, 2) - cfg.edge_margin - Fraction(w_cells, 2) - 1
    cy_max = Fraction(viewport.height, 2) - cfg.edge_margin - Fraction(h_cells, 2) - 1
    if cx_max < 0 or cy_max < 0:
        return None
    x_denom = scale * camera.cell_aspect
    x_half_su = math.floor(cx_max / x_denom) if x_denom > 0 else 0
    y_half_su = math.floor(cy_max / scale)
    if x_half_su < 0 or y_half_su < 0:
        return None
    cx0 = camera.position.x + camera.aim_x_su
    cy0 = camera.position.y + camera.aim_y_su
    return (cx0 - x_half_su, cx0 + x_half_su, cy0 - y_half_su, cy0 + y_half_su)


class FixedFovPerspective:
    """True perspective: scale is an exact `Fraction` divide by depth
    (plan §9.5).
    """

    name = "fixed_fov_perspective"

    def frame(
        self,
        arrangement: WorldArrangement,
        anchor: SceneKey,
        viewport: CellBox,
        cfg: SceneTuning,
        catalog: ArtGeometryCatalog,
    ) -> Camera:
        obj = _find_object(arrangement, anchor)
        anchor_pos = _find_position(arrangement, anchor)
        target_h = round_half_even(
            cfg.target_fraction_by_scale_class[obj.scale_class] * viewport.height
        )
        final_h, _rung = _target_natural_height(obj, cfg, catalog, target_h)
        camera = _base_camera(cfg, fov_num=cfg.fixed_fov_num, fov_den=cfg.fixed_fov_den)
        # Solve dz from project()'s h_cells = face.height_su * scale,
        # scale = (viewport.height * fov_den) / (fov_num * dz), for
        # h_cells == final_h exactly:
        #   dz = (viewport.height * fov_den * face.height_su) / (fov_num * final_h)
        dz = (
            Fraction(viewport.height * camera.fov_den, camera.fov_num)
            * Fraction(obj.face.height_su, final_h)
        )
        dz_su = max(math.floor(dz), cfg.near_plane_su + 1)
        return replace(camera, position=Vec3(anchor_pos.x, anchor_pos.y, anchor_pos.z - dz_su))

    def candidates(
        self,
        camera: Camera,
        anchor: PhysicalObject,
        anchor_pos: Vec3,
        viewport: CellBox,
        cfg: SceneTuning,
    ) -> Iterator[Camera]:
        # "Current" height: what the anchor projects to at the input camera's
        # own depth (its z-distance from the camera plane, per the anchor's
        # actual world z-position -- `frame()`'s own convention, plan §9.5),
        # so the sweep can order candidates nearest-to-current first (§9.6).
        current_dz = Fraction(anchor_pos.z - camera.position.z)
        current_h = (
            round_half_even(
                Fraction(anchor.face.height_su)
                * (Fraction(viewport.height * camera.fov_den, camera.fov_num) / current_dz)
            )
            if current_dz > 0
            else 0
        )
        count = 0
        seen: set[tuple[int, int]] = set()
        # Candidate #0 is the framed camera itself (plan §9.6: "nearest-to-
        # current first" -- "current" being the camera `frame()` just solved
        # for this anchor). It was previously dropped: the sweep only ever
        # yielded heights inside `[camera_height_fraction_min,
        # camera_height_fraction_max] * viewport.height`, and for a
        # *continuous* anchor `frame()`'s own solved height is
        # `target_fraction / ink_ratio * viewport.height`, which the approved
        # WP-SC05 numbers put *outside* that window (planet: 1/2 / 3/5 = 5/6 >
        # 3/4). The framed camera was therefore unreachable for every
        # planet/nebula/black-hole/wormhole scene, and every candidate the
        # solver could see was strictly farther away than the one framing
        # chose -- which shrank secondary ships below `min_projected_size` /
        # every authored rung. Yielding it first costs one candidate from the
        # same bounded budget and retunes no approved value.
        for cam0 in (camera,):
            seen.add((anchor_pos.z - cam0.position.z, cam0.aim_x_su))
            yield cam0
            count += 1
        # Aim offsets outside, framing heights inside (WP-SC12). The height
        # sweep is the *coarse* axis — it is what decides whether the anchor
        # fits the viewport at all — while an aim offset is a few cells of
        # lateral nudge. Running heights in the inner loop spent
        # `max_camera_candidates` on `len(aim_offsets_su)` copies of the same
        # handful of heights nearest the framed one: with 64 candidates and 7
        # offsets only ~9 of the 34 available heights at 150x52 were ever
        # reached. A wide, low-ink-fraction anchor frames far outside that
        # window — an asteroid belt's own framed height is 45 cells against a
        # sweep that tops out at 39, so every reachable candidate projected it
        # 350 cells wide and it failed `edge_margin` in every `belt+…` scene.
        # Same bound, same "nearest-to-current first" order within an offset.
        for dx in cfg.aim_offsets_su:
            aim_x_su = camera.aim_x_su + dx
            for h in _height_sweep(viewport, cfg, current_h):
                dz = Fraction(viewport.height * camera.fov_den, camera.fov_num) * Fraction(
                    anchor.face.height_su, h
                )
                dz_su = max(math.floor(dz), cfg.near_plane_su + 1)
                # §6.2 rule 4: distinct swept heights can floor to the same integer
                # depth, and a laddered anchor's finite rung count collapses many
                # heights onto the same rendered box outright -- both leave `project()`
                # producing byte-identical output for two different swept heights. A
                # candidate whose (depth, aim) pair was already yielded is guaranteed
                # to reproject to the same quantised scene, so it is dropped here
                # rather than spent from `max_camera_candidates`'s bounded budget.
                key = (dz_su, aim_x_su)
                if key in seen:
                    continue
                seen.add(key)
                if count >= cfg.max_camera_candidates:
                    return
                yield replace(
                    camera,
                    position=Vec3(camera.position.x, camera.position.y, anchor_pos.z - dz_su),
                    aim_x_su=aim_x_su,
                )
                count += 1

    def project(
        self,
        camera: Camera,
        obj: PhysicalObject,
        at: Vec3,
        viewport: CellBox,
    ) -> CellBox:
        dz = Fraction(at.z - camera.position.z)
        if dz <= 0 or at.z < camera.near_plane_su:
            raise NearPlaneViolation(
                f"{obj.key!r} at z={at.z} is at/behind near_plane_su={camera.near_plane_su}"
            )
        scale = Fraction(viewport.height * camera.fov_den, camera.fov_num) / dz
        h_cells = round_half_even(Fraction(obj.face.height_su) * scale)
        w_cells = round_half_even(Fraction(obj.face.width_su) * scale * camera.cell_aspect)
        cx = Fraction(at.x - camera.position.x - camera.aim_x_su) * scale * camera.cell_aspect
        cy = Fraction(at.y - camera.position.y - camera.aim_y_su) * scale
        col = math.floor(Fraction(viewport.width, 2) + cx - Fraction(w_cells, 2))
        row = math.floor(Fraction(viewport.height, 2) - cy - Fraction(h_cells, 2))
        return CellBox(col, row, max(1, w_cells), max(1, h_cells))

    def visible_xy_extent(
        self,
        camera: Camera,
        viewport: CellBox,
        z: Su,
        face: Face,
        cfg: SceneTuning,
    ) -> tuple[Su, Su, Su, Su] | None:
        scale = self.scale_at(camera, viewport, z)
        if scale is None:
            return None
        return _visible_xy_extent_from_scale(camera, viewport, face, cfg, scale)

    def scale_at(self, camera: Camera, viewport: CellBox, z: Su) -> Fraction | None:
        """The exact su-to-cell scale factor `project()` uses at depth `z`, or
        `None` when `z` violates the near plane (plan §9.2).

        Exposed so the solver can run `project()`'s position algebra
        *backwards* -- turn a wanted screen cell into the su position that
        lands an object there -- without duplicating either strategy's scale
        formula (see `edge/scene/solve.py::_su_for_screen`).
        """
        dz = Fraction(z - camera.position.z)
        if dz <= 0 or z < camera.near_plane_su:
            return None
        return Fraction(viewport.height * camera.fov_den, camera.fov_num) / dz


class DepthLayeredAnchorProjection:
    """Depth quantised into `cfg.depth_layers` discrete layers, each with an
    exact `Fraction` scale factor relative to the camera's own layer. No
    per-object divide -- "cheaper, flatter arithmetic" than true perspective
    (plan §9.5), the reason WP-SC04's strategy comparison exists at all.
    """

    name = "depth_layered_anchor"

    def frame(
        self,
        arrangement: WorldArrangement,
        anchor: SceneKey,
        viewport: CellBox,
        cfg: SceneTuning,
        catalog: ArtGeometryCatalog,
    ) -> Camera:
        obj = _find_object(arrangement, anchor)
        anchor_pos = _find_position(arrangement, anchor)
        target_h = round_half_even(
            cfg.target_fraction_by_scale_class[obj.scale_class] * viewport.height
        )
        final_h, _rung = _target_natural_height(obj, cfg, catalog, target_h)
        camera = _base_camera(cfg, fov_num=1, fov_den=1)
        # Search the bounded layer-index range for the layer whose exact
        # scale puts the anchor's projected height closest to final_h,
        # ties broken toward the nearer (smaller) layer -- an integer/
        # Fraction comparison only, per §4 invariant 1.
        best_layer = 0
        best_gap: Fraction | None = None
        for layer in range(cfg.depth_layers):
            scale = cfg.depth_layer_scale**layer
            projected = Fraction(obj.face.height_su) * scale
            gap = abs(projected - final_h)
            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_layer = layer
        dz_su = best_layer * cfg.depth_layer_size_su + 1
        return replace(camera, position=Vec3(anchor_pos.x, anchor_pos.y, anchor_pos.z - dz_su))

    def candidates(
        self,
        camera: Camera,
        anchor: PhysicalObject,
        anchor_pos: Vec3,
        viewport: CellBox,
        cfg: SceneTuning,
    ) -> Iterator[Camera]:
        current_layer = 0
        count = 0
        seen: set[tuple[int, int]] = set()
        # Candidate #0 is the framed camera itself, for the same reason as
        # `FixedFovPerspective.candidates()` above (plan §9.6 "nearest-to-
        # current first"): `frame()` picks the layer whose exact scale puts
        # the anchor closest to its calibrated target height, and the layer
        # sweep below -- which always restarts from layer 0 -- has no reason
        # to visit that layer before exhausting nearer ones.
        for cam0 in (camera,):
            seen.add((anchor_pos.z - cam0.position.z, cam0.aim_x_su))
            yield cam0
            count += 1
        layers = sorted(range(cfg.depth_layers), key=lambda layer: (abs(layer - current_layer), layer))
        # Aim offsets outside, depth layers inside, mirroring
        # `FixedFovPerspective.candidates()` above so the two strategies spend
        # the same bounded budget the same way (WP-SC12). With only
        # `depth_layers` = 8 layers against a 64-candidate cap this changes
        # nothing reachable here; it is kept identical so a future cap or
        # layer-count change cannot make the two diverge silently.
        for dx in cfg.aim_offsets_su:
            aim_x_su = camera.aim_x_su + dx
            for layer in layers:
                dz_su = layer * cfg.depth_layer_size_su + 1
                # §6.2 rule 4, mirroring `FixedFovPerspective.candidates()` above:
                # each layer's depth is distinct by construction, but a repeated
                # (depth, aim) pair still cannot happen here except by a future
                # `cfg` change, so this dedup is a cheap, always-correct guard
                # rather than dead code -- it does not, by itself, catch a laddered
                # anchor whose finite rung count makes two *different* depths render
                # the same box; that needs the catalog `candidates()` does not
                # receive, and stays WP-SC06's job (see module docstring).
                key = (dz_su, aim_x_su)
                if key in seen:
                    continue
                seen.add(key)
                if count >= cfg.max_camera_candidates:
                    return
                yield replace(
                    camera,
                    position=Vec3(camera.position.x, camera.position.y, anchor_pos.z - dz_su),
                    aim_x_su=aim_x_su,
                )
                count += 1

    def project(
        self,
        camera: Camera,
        obj: PhysicalObject,
        at: Vec3,
        viewport: CellBox,
    ) -> CellBox:
        dz = at.z - camera.position.z
        if dz <= 0 or at.z < camera.near_plane_su:
            raise NearPlaneViolation(
                f"{obj.key!r} at z={at.z} is at/behind near_plane_su={camera.near_plane_su}"
            )
        layer_index = dz // camera.depth_layer_size_su
        scale = camera.depth_layer_scale**layer_index
        h_cells = round_half_even(Fraction(obj.face.height_su) * scale)
        w_cells = round_half_even(Fraction(obj.face.width_su) * scale * camera.cell_aspect)
        cx = Fraction(at.x - camera.position.x - camera.aim_x_su) * scale * camera.cell_aspect
        cy = Fraction(at.y - camera.position.y - camera.aim_y_su) * scale
        col = math.floor(Fraction(viewport.width, 2) + cx - Fraction(w_cells, 2))
        row = math.floor(Fraction(viewport.height, 2) - cy - Fraction(h_cells, 2))
        return CellBox(col, row, max(1, w_cells), max(1, h_cells))

    def visible_xy_extent(
        self,
        camera: Camera,
        viewport: CellBox,
        z: Su,
        face: Face,
        cfg: SceneTuning,
    ) -> tuple[Su, Su, Su, Su] | None:
        scale = self.scale_at(camera, viewport, z)
        if scale is None:
            return None
        return _visible_xy_extent_from_scale(camera, viewport, face, cfg, scale)

    def scale_at(self, camera: Camera, viewport: CellBox, z: Su) -> Fraction | None:
        """This strategy's discrete per-layer scale at depth `z` (see
        `FixedFovPerspective.scale_at` for why the protocol carries it)."""
        dz = z - camera.position.z
        if dz <= 0 or z < camera.near_plane_su:
            return None
        layer_index = dz // camera.depth_layer_size_su
        scale: Fraction = camera.depth_layer_scale**layer_index
        return scale


def intersect_region_xy(
    region: Region, extent: tuple[Su, Su, Su, Su] | None
) -> tuple[Su, Su, Su, Su] | None:
    """Clamp `region`'s x/y bounds to a `visible_xy_extent()` result.

    Returns `None` when there is no overlap (or `extent` is `None`, meaning
    "no visibility estimate at this depth" -- the caller falls back to
    `region`'s own bounds unchanged in that case), so a caller never has to
    special-case "no camera yet" separately from "camera exists but this
    object's region does not reach where it can see".
    """
    if extent is None:
        return None
    x_min, x_max, y_min, y_max = extent
    ix_min = max(region.x_min, x_min)
    ix_max = min(region.x_max, x_max)
    iy_min = max(region.y_min, y_min)
    iy_max = min(region.y_max, y_max)
    if ix_min > ix_max or iy_min > iy_max:
        return None
    return (ix_min, ix_max, iy_min, iy_max)


def hysteresis_delta(
    *,
    anchor_height_now: int,
    anchor_height_prev: int | None,
    admitted_now: frozenset[SceneKey],
    admitted_prev: frozenset[SceneKey] | None,
    position_deltas: tuple[int, ...],
    art_deltas: tuple[int, ...],
    cfg: SceneTuning,
) -> int:
    """Plan §9.6's deterministic previous-plan hysteresis metric, exposed as
    a standalone integer computation (WP-SC03's "expose deterministic
    hysteresis terms, all weights injected and unset until calibration").

    `0` whenever there is no previous plan, matching §9.6: "`0` when
    `previous is None`". Wiring this against a real `ScenePlan`'s admitted
    set and per-object position/art deltas is WP-SC06's job -- this function
    only owns the arithmetic, taking the already-computed per-term inputs a
    caller supplies.
    """
    if anchor_height_prev is None or admitted_prev is None:
        return 0
    term_cam = cfg.hysteresis_weight_camera * abs(anchor_height_now - anchor_height_prev)
    term_pos = cfg.hysteresis_weight_position * sum(position_deltas)
    term_adm = cfg.hysteresis_weight_admission * len(admitted_now ^ admitted_prev)
    term_art = cfg.hysteresis_weight_art * sum(art_deltas)
    return term_cam + term_pos + term_adm + term_art
