"""The immutable scene model (plan §9.3).

Field names here are binding. Every dataclass is frozen/slotted and every
collection is a tuple, so a `WorldArrangement` or `ScenePlan` is safe to pass
around, cache, and compare by value without defensive copies.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from fractions import Fraction
from types import MappingProxyType
from typing import Literal

from edge.scene.catalog import LadderKey, LadderRung
from edge.scene.geometry import CellBox, Face, Region, Su, Vec3


class SceneRetention(IntEnum):
    """Gameplay retention priority (plan §2.3). Lower value is retained first."""

    ENTITY = 0
    ANCHOR = 1
    ORBITAL = 2
    HOSTILE_SHIP = 3
    NEUTRAL_SHIP = 4
    WRECK = 5
    FRIENDLY_SHIP = 6


class ArtMode(StrEnum):
    """How an accepted object's art is resolved (plan §2.4, §9.7)."""

    LADDER = "ladder"
    CONTINUOUS = "continuous"
    GLYPH = "glyph"


@dataclass(frozen=True, slots=True, order=True)
class SceneKey:
    """Tagged stable presentation identity; the final deterministic tie-break
    (plan §2.3, §4.1). Orderable so it can serve directly as the last element
    of a lexicographic candidate-comparison tuple (plan §9.6)."""

    tag: Literal[
        "ship", "player", "planet", "port", "starbase", "discovery",
        "wreck", "entity", "belt", "glyph",
    ]
    ident: int


@dataclass(frozen=True, slots=True)
class PhysicalObject:
    """One classified scene inventory entry, before placement or projection."""

    key: SceneKey
    parent: SceneKey | None
    face: Face
    scale_class: str
    """Config-named class; ordering is by `face.area_su` (plan §4.4)."""
    art_mode: ArtMode
    ladder_key: LadderKey | None
    continuous_kind: str | None
    archetype_id: str | None
    """Owner/species palette for procedural art (plan §9.7 gap fix). This is the real
    DTO-level ownership signal when one exists (a port/starbase/ship's own
    `archetype_id`, or an owned planet's `SectorPlanetDTO.archetype_id`) and `None`
    otherwise -- a discovery/wreck/entity carries no ownership/species association at
    the DTO level today, so this is `None` for those, not a fabricated value. For
    `ArtMode.LADDER` this is *not* the same string as `ladder_key.archetype_id`: the
    ladder key always carries a real archetype (substituting
    `SceneTuning.fallback_archetype_id` when the DTO has none, so the geometry
    catalogue -- which has no `archetype_id=""` rungs -- still has a match), while this
    field stays the true `None` for "no owner" so callers reading it for
    ownership/display purposes are never handed a fabricated one."""
    retention: SceneRetention
    hostility_ordinal: int
    """0 = most hostile; opaque, from the fog-safe DTO (WP-SC01)."""
    threat_rank: int
    region: Region
    flexible: bool
    occludes: bool
    """`False` for permeable fields such as asteroid belts (plan §2.5)."""
    label: str
    destination: str | None
    """Interaction route; never read by the solver."""


@dataclass(frozen=True, slots=True)
class Placement:
    key: SceneKey
    position: Vec3


@dataclass(frozen=True, slots=True)
class WorldArrangement:
    """Viewport-independent identities, parents, allowed regions, and initial
    deterministic positions; a solve records any viewport-driven flexible move."""

    objects: tuple[PhysicalObject, ...]
    placements: tuple[Placement, ...]
    sector_id: int = 0
    """Internal sector id this arrangement was classified from (WP-SC06 addition).

    `edge/scene/solve.py` needs a stable, fog-safe-adjacent identity to seed
    its local glyph-scatter RNG (plan §9.6) without touching game RNG or a
    private DTO field; `classify_sector` fills this from `SectorDTO.sector_id`.
    Defaulted so existing fixtures that build a `WorldArrangement` directly
    (WP-SC02/SC03 tests) keep working unchanged.
    """
    glyphs: tuple[GlyphRequest, ...] = ()
    """Free-cell-consumer presence marks (fighters/mines) classified alongside
    this arrangement (plan §2.5, §9.6). `classify_sector` still also returns
    these as a separate tuple for its existing WP-SC02 callers; carrying them
    here too lets `solve()` (whose plan-fixed §9.3 signature takes only an
    `arrangement`) reach them for the post-solve glyph scatter without a
    signature change. Defaulted for the same fixture-compatibility reason as
    `sector_id`.
    """


@dataclass(frozen=True, slots=True)
class Camera:
    position: Vec3
    aim_x_su: Su
    aim_y_su: Su
    fov_num: int
    """Fixed FOV as an exact ratio; strategy-specific.

    `FixedFovPerspective` (`edge/scene/project.py`) uses this as the real FOV
    ratio consumed by `project()`. `DepthLayeredAnchorProjection` does not
    read it for scale -- its scale comes from `depth_layer_scale` below -- and
    sets it to an unused placeholder.
    """
    fov_den: int
    near_plane_su: Su
    cell_aspect: Fraction
    depth_layer_size_su: Su
    """Depth-layered strategy only (plan §9.5): the su span of one depth
    layer. `FixedFovPerspective` sets it to an arbitrary positive placeholder
    since the field is required on this shared dataclass."""
    depth_layer_scale: Fraction
    """Depth-layered strategy only: the exact per-layer multiplicative scale
    factor (`scale(layer) = depth_layer_scale ** layer_index`).
    `FixedFovPerspective` sets it to an arbitrary placeholder."""


@dataclass(frozen=True, slots=True)
class Projection:
    key: SceneKey
    bounds: CellBox
    """Request/container box, integer cells."""
    depth: Su
    rung: LadderRung | None
    box_class: int | None
    """Index into `ContinuousYield.box_classes`."""
    ink_est: CellBox
    """Estimated ink bounds (envelope side per the constraint that reads it)."""
    ink_actual: CellBox | None
    """Filled after art resolution (WP-SC07)."""
    visible_fraction: Fraction
    label_bounds: CellBox | None
    accepted: bool


@dataclass(frozen=True, slots=True)
class Decision:
    rule_id: str
    """Stable, e.g. ``"min_visible_fraction"``."""
    key: SceneKey | None
    outcome: Literal["accept", "move", "reject", "step_down", "reanchor"]
    inputs: tuple[tuple[str, int | str], ...]
    reason: str
    """``""`` unless the dev/gallery switch is on (plan §4.20)."""


@dataclass(frozen=True, slots=True)
class SolveCounters:
    """Always-recorded structural counts (plan §4.20, §6.2 rule 8)."""

    camera_candidates: int
    reposition_candidates: int
    passes: int
    reanchors: int
    step_downs: int
    occlusion_comparisons: int
    validation_corrections: int
    glyphs_placed: int
    glyphs_dropped: int
    cost_estimated: int
    cost_actual: int


@dataclass(frozen=True, slots=True)
class ScenePlan:
    viewport: CellBox
    mode: str
    strategy: str
    camera: Camera
    projections: tuple[Projection, ...]
    """Depth-ordered, far to near."""
    rejected: tuple[SceneKey, ...]
    fingerprint: str
    """Hash of the quantised output only."""
    counters: SolveCounters
    trace: tuple[Decision, ...]


_EMPTY_REGIONS: Mapping[str, Region] = MappingProxyType({})
_EMPTY_TARGETS: Mapping[str, "StationTarget"] = MappingProxyType({})
"""Shared immutable empties, so `SceneTuning`'s optional WP-SC12 mappings can
default without a mutable class attribute on a frozen slotted dataclass."""


@dataclass(frozen=True, slots=True)
class StationSizeReference:
    """The scene's reference body height in cells — the head of the station
    scale chain (plan §9.6 "Station size parity").

    `reference_body_height()` below is the whole of it: a viewport-only
    function, injected coefficient by coefficient, that the solver uses to
    resolve a parented station's target projected height. It is deliberately
    *not* the physical model's own projected anchor height: the anchor is
    bound by the no-crop invariants (§4.7/§4.17) to what fits whole inside the
    viewport, which on a narrow canvas is smaller than the legacy composer's
    deliberately-cropped disc, and keying station size to it would propagate
    that difference into every station.
    """

    height_fraction: Fraction
    header_rows: int
    width_fraction: Fraction
    max_cells: int
    min_cells: int

    def reference_body_height(self, viewport: CellBox) -> int:
        """The reference body height for `viewport`, in cells.

        Exact `int`/`Fraction` only (plan §4.1): `math.floor` on a `Fraction`,
        never a float, and the result feeds an accept/reject decision.
        `floor` (not round-half-even) because the two legacy terms this
        reproduces are `int(body_h * 0.9)` and `int(w * 0.55)`, both
        truncating.
        """
        by_height = math.floor(
            self.height_fraction * max(viewport.height - self.header_rows, 0)
        )
        by_width = math.floor(self.width_fraction * viewport.width)
        return max(self.min_cells, min(self.max_cells, by_height, by_width))


@dataclass(frozen=True, slots=True)
class StationTarget:
    """One station scale class's target projected ink height (plan §4.13).

    `parent_scale` applies when the station orbits a planet (its
    `PhysicalObject.parent` is set); `lone_scale` applies to the header-less
    viewport height when it does not. Both are clamped to
    `[min_cells, max_cells]`.
    """

    parent_scale: Fraction
    lone_scale: Fraction
    min_cells: int
    max_cells: int

    def target_height(
        self, viewport: CellBox, reference: StationSizeReference, *, parented: bool
    ) -> int:
        """The target projected ink height in cells, clamped.

        The two roundings mirror `SceneArtConfig.station_dimensions`'s own two
        branches exactly: `round(primary_height * scale)` when parented (so
        round-half-even, which is what Python's `round` does), and
        `int(body_height * 0.6)` when not (so truncating).
        """
        if parented:
            exact = Fraction(reference.reference_body_height(viewport)) * self.parent_scale
            cells = round(exact)
            assert isinstance(cells, int)
        else:
            cells = math.floor(
                Fraction(max(viewport.height - reference.header_rows, 0)) * self.lone_scale
            )
        return max(self.min_cells, min(self.max_cells, cells))


@dataclass(frozen=True, slots=True)
class SceneTuning:
    """The injected, frozen bundle of every §5 calibrated value.

    Constructed at the TUI seam from validated `scene:` config;
    `edge/scene/` never reads a config file and never supplies a default for
    one of its fields. No instance of this type ships with this commit — a
    caller (production code or a test) must always build its own, and
    `config/default.yaml` names no `scene:` values yet — so declaring these
    fields does not ship a default; only WP-SC05's calibration gate does that.

    The two maps below are what the classifier (`edge/scene/classify.py`)
    needs to turn a fog-safe DTO into a `PhysicalObject`/`Placement` without
    inventing a number itself: every face extent and placement region is a
    lookup by `PhysicalObject.scale_class`, never a literal in classifier
    code. `scale_class` values are plan-fixed strings (`"entity"`, `"anchor"`,
    `"belt"`, `"stardock"`, `"orbital"`, `"ship"`, `"wreck"`), not free-form config keys —
    see `edge.scene.classify.SCALE_CLASSES`.
    """

    face_extent_by_scale_class: Mapping[str, tuple[Su, Su]]
    """`(width_su, height_su)` per `scale_class` — the only numbers the
    classifier needs to build a `Face`; the shape (circle/ellipse/rect/field)
    is a categorical choice already fixed by plan §2.5, not a tuned number."""

    face_extent_by_kind: Mapping[str, tuple[Su, Su]]
    """`(width_su, height_su)` per `PhysicalObject.continuous_kind`, overriding
    `face_extent_by_scale_class` for kinds that need apparent-scale distinction
    within a shared `scale_class` (plan §2.2: nebula/black_hole visual system
    ≫ wormhole > planet, all classed "anchor"). `edge.scene.classify._face`
    looks this up first by `continuous_kind`; a kind with no entry here falls
    back to `face_extent_by_scale_class[scale_class]` unchanged, so an empty
    mapping reproduces the old scale_class-only behaviour exactly. Keyed by
    the same kind strings already used for `PhysicalObject.continuous_kind`
    (planet `ptype` values and `SectorDiscovery.kind` values, e.g. "nebula",
    "black_hole", "wormhole"); need not cover every kind."""

    region_by_scale_class: Mapping[str, Region]
    """The allowed placement region/depth range per `scale_class`. For the two
    station classes, `"orbital"` and `"stardock"`, this is interpreted as an
    offset from the parent planet's own placement, matching plan §2.5 ("their
    nominal face area and allowed orbital placement derive from that planet");
    for every other class it is an absolute scene-unit region. In practice the
    distinction is carried by `PhysicalObject.parent` rather than by the class
    name — `edge.scene.solve._absolute_region` re-adds the parent origin for
    any object that has one — so a station with no planet in its sector falls
    back to an absolute region without a special case."""

    target_fraction_by_scale_class: Mapping[str, Fraction]
    """Plan §9.5 `frame()`: the anchor's target projected-ink-height fraction
    of `viewport.height`, keyed by the anchor's `scale_class`."""

    ink_ratio_by_scale_class: Mapping[str, Fraction]
    """Plan §9.5 `frame()`'s first-pass ink/natural height ratio used to turn
    a target ink height into a target natural (request-box) height, keyed by
    `scale_class`. For a laddered anchor this is only the seed for picking a
    candidate rung -- the rung actually chosen supplies its own exact
    `ink_min.height / natural.height` for the final camera solve."""

    structural_mode_thresholds: tuple[tuple[int, int, str], ...]
    """Plan §9.1 "Structural mode": an ordered `(min_cols, min_rows, mode)`
    list, first match wins, most permissive (most demanding) first."""

    fixed_fov_num: int
    """`FixedFovPerspective`'s calibrated FOV ratio numerator (plan §9.5)."""

    fixed_fov_den: int

    cell_aspect: Fraction
    """Shared terminal cell aspect (plan §9.1), injected once here so both
    strategies' `frame()` can build a `Camera` without inventing a number."""

    near_plane_su: Su
    """Shared hard near-plane constraint (plan §9.2), injected once here."""

    depth_layers: int
    """`DepthLayeredAnchorProjection`'s layer count, bounding the layer-index
    search `frame()` performs when solving camera placement (plan §9.5)."""

    depth_layer_size_su: Su
    """`DepthLayeredAnchorProjection`'s su span of one depth layer."""

    depth_layer_scale: Fraction
    """`DepthLayeredAnchorProjection`'s exact per-layer scale factor."""

    camera_height_fraction_min: Fraction
    """`candidates()`'s framing-height sweep lower bound, as a fraction of
    `viewport.height` (plan §9.6's `anchor_target_min`, scoped to WP-SC03's
    simpler framing-only candidate exploration)."""

    camera_height_fraction_max: Fraction
    """`candidates()`'s framing-height sweep upper bound."""

    aim_offsets_su: tuple[Su, ...]
    """`candidates()`'s bounded, centre-out aim offsets to explore, in the
    order to try them."""

    max_camera_candidates: int
    """Hard cap on the number of cameras `candidates()` yields."""

    hysteresis_weight_camera: int
    """Plan §9.6 hysteresis metric weights (WP-SC03 exposes the deterministic
    per-term computation; the full previous-plan wiring is WP-SC06's)."""

    hysteresis_weight_position: int
    hysteresis_weight_admission: int
    hysteresis_weight_art: int

    # -- WP-SC06 additions: the solver's own bounds/thresholds (plan §9.6, §4). --
    # `edge/scene/` still never supplies a default for any of these; they are
    # only declared here so a caller (production seam or test fixture) has
    # somewhere typed to inject the WP-SC05 calibration values into once
    # approved.

    max_passes: int
    """Hard bound on the whole solve pass loop (plan §9.6, §6.2 rule 4)."""

    edge_margin: int
    """Cells of required clearance from every viewport edge (attempt rule 1)."""

    min_projected_cells_by_scale_class: Mapping[str, tuple[int, int]]
    """`(min_width, min_height)` cells an accepted projection must clear,
    keyed by `PhysicalObject.scale_class` (attempt rule 2)."""

    min_rung_index_from_end_by_scale_class: Mapping[str, int]
    """Minimum-richness floor (maintainer feedback: composers were shrinking
    ports/stardocks/starbases and never using ships' larger tiers): the
    number of worst (highest-`LadderRung.index`) rungs of a laddered object's
    ladder that `_select_rung` must never select, keyed by `scale_class`. A
    value of `1` means "never the single worst rung"; a scale class absent
    from this mapping (or a continuous/non-laddered object) is unaffected.
    This is a genuine exclusion on what counts as "clears" at a given
    projected size, not a post-hoc filter -- an object that can only ever fit
    an excluded rung is rejected outright (plan's "no cropping / no degraded
    compromise" philosophy), never shown at a worse tier than this floor
    allows."""

    separation_margin: int
    """Cells by which accepted ink-max boxes are inflated before the pairwise
    overlap check (attempt rule 4); `occludes=False` objects are skipped."""

    min_visible_fraction_by_scale_class: Mapping[str, Fraction]
    """The minimum visible fraction the farther object of an occluding pair
    must clear, keyed by the farther object's `scale_class` (attempt rule 5)."""

    cost_budget: int
    """Cumulative estimated render-cost ceiling for one solve (attempt rule 7,
    plan §4.14)."""

    emergency_ship_ceiling: int
    """Hard cap on admitted ship count, independent of `cost_budget`, guarding
    against estimator/pathological-input failure (plan §2.3, attempt rule 7)."""

    max_reposition_candidates: int
    """Per-object bound on how many deterministic reposition offsets the
    solver will try for one flexible object across the whole solve (plan
    §6.2 rule 4)."""

    max_glyph_tries: int
    """Per-glyph bound on free-cell placement attempts (plan §9.6, §4.19)."""

    glyph_spacing: int
    """Minimum cell distance a newly placed glyph must keep from every
    already-placed glyph (plan §9.6)."""

    fallback_archetype_id: str
    """The archetype id `edge.scene.classify` substitutes for a port/starbase/ship
    with no `archetype_id` of its own (reachable in real play — e.g. a port in a
    sector no alliance controls) when building its `LadderKey`. Must match the
    injected `ArtGeometryCatalog`'s own no-archetype fallback (the art seam
    generates catalogue rungs for `SPRITES.palettes.fallback_archetype`, never for
    an empty string) or the classifier hands the solver a key the catalogue has no
    rungs for at all, which `edge.scene.project.frame()` cannot recover from when
    that object is the anchor."""

    # -- WP-SC12 additions: station-size parity (plan §9.6 "Station size
    # parity"). Defaulted so every existing fixture that builds a
    # `SceneTuning` by hand keeps working: with no station target declared,
    # a station's depth search is the unchanged near-to-far walk.

    orbit_offset_region_by_scale_class: Mapping[str, Region] = _EMPTY_REGIONS
    """Where an object with a `parent` may sit **relative to that parent**,
    per `scale_class`. `region_by_scale_class` above stays the absolute
    region, used for the same class when the object has no parent.

    Splitting the two is what makes the parent-relative reading of a station
    region real. `region_by_scale_class`'s docstring has always described a
    station's region as an offset from its planet, but the shipped value was
    the *absolute* anchor box (`z 1..400`) — so a parented station was always
    at least 1 su behind its planet and up to 400 behind, never near enough to
    the camera to clear a usable authored rung. A class absent from this
    mapping falls back to `region_by_scale_class` for both cases, exactly the
    pre-WP-SC12 behaviour."""

    station_size_reference: StationSizeReference | None = None
    """The reference body height a parented station's target scales off."""

    station_target_by_scale_class: Mapping[str, StationTarget] = _EMPTY_TARGETS
    """Per-`scale_class` target projected ink height. A class named here has
    its bounded depth candidates *ordered by closeness to that target*
    (plan §4.13's "soft objective expressed in projected height") instead of
    walked near-to-far; a class absent from it is unaffected."""


@dataclass(frozen=True, slots=True)
class GlyphRequest:
    """A free-cell-consumer presence mark: a fighter garrison or mine field.

    Plan §2.5, §9.6: fighters and mines never become retained
    `PhysicalObject`s and never compete in the retention solve. They are a
    separate classification output the post-solve scatter step (WP-SC06)
    consumes to place `count` one-cell glyphs into free projected cells.
    """

    key: SceneKey
    count: int
