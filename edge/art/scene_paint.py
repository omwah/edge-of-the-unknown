"""Art resolution and depth paint (WP-SC07, plan §9.7).

This is the art/TUI seam that turns a `ScenePlan`'s *accepted* `Projection`s
into real rendered art: `edge/scene/` never imports `edge.art.sprites`, Rich,
or does I/O (AGENTS.md's `edge/scene` layering note; plan §6.2 rule 1 — "no
art is rendered ... only catalogue-supplied face geometry and ink
envelopes"), so this module lives beside `edge/art/geometry_catalog.py` and
`edge/art/scene_tuning.py` and consumes their output plus `edge.scene`'s pure
types. It does not wire into any running TUI composer (that is WP-SC09/SC10)
-- it is a standalone, testable paint function over a `ScenePlan`.

Two art paths (plan §9.7's "Implementation" bullet 1):

* **Laddered kinds (ship/port)** render a complete authored rung selected
  *by the catalogue* -- never through `edge.art.sprites.fit_box`'s
  smallest-tier clamp. `_resolve_ladder` calls
  `edge.art.sprites.SPRITES.generate_ship`/`generate_port` directly with the
  rung's own `natural` box, bypassing `edge.art.generator.generate_sprite`'s
  ship/port branch entirely (that branch calls `fit_box` itself). An object
  with no clearing rung is never seen here -- the solver already rejected it
  (plan §4 invariant 7).
* **Continuous kinds (planet/belt/discovery/entity)** render through
  `edge.art.generator.generate_sprite`'s real, already-shipped procedural
  generators (`PlanetGenerator`, `DiscoveryGenerator`) -- these are genuine,
  calibrated-adjacent renderers, not a placeholder. `PhysicalObject.archetype_id`
  (plan §9.7 gap fix) now carries the real DTO-level owner/species palette when
  one exists and is threaded through to `generate_sprite` here, so an owned
  planet renders owner-tinted. The signal is genuinely absent for the other
  continuous kinds today -- `SectorDiscovery` (nebula/black_hole/wormhole/wreck)
  and the generated Entity carry no owning-species association at the DTO
  level -- so `archetype_id` is `None` for those, a principled absence rather
  than something invented or hidden.

The composition-local render cache (`RenderCache`) and the render-once-per-
final-box counter (`RenderCache.renders`/`.hits`) implement plan §6.2 rule 3.
`resolve_scene` resolves every accepted `Projection`, crops to ink, and runs
the one bounded actual-ink validation correction (§6.2 rule 2, §9.7).
`paint_grid` composites the depth-ordered result into a flat per-cell grid,
with belt paint-through and post-paint glyph scatter (§2.5, §4.19).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import math

from rich.style import Style
from rich.text import Text

from edge.art.generator import generate_sprite
from edge.art.sprites import SPRITES
from edge.scene.catalog import ArtGeometryCatalog, LadderKey, LadderRung
from edge.scene.geometry import CellBox
from edge.scene.model import (
    ArtMode,
    PhysicalObject,
    Projection,
    SceneKey,
    SceneRetention,
    SceneTuning,
    ScenePlan,
    WorldArrangement,
)

Cell = tuple[str, Style | None]
"""One painted terminal cell: a character and its (possibly absent) style.
`None` style marks a transparent cell -- background/starfield shows through,
matching the existing `_SceneComposer` convention this module deliberately
mirrors without importing it (`edge/tui/widgets.py` stays untouched by this
WP)."""


# ---------------------------------------------------------------------------
# Render cache key (plan §6.2 rule 3).
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RenderCacheKey:
    """`(entity_type, subtype, seed, box, facing, archetype, treatment)`,
    exactly as plan §6.2 rule 3 specifies. `box` is `(width, height)`."""

    entity_type: str
    subtype: str
    seed: int
    box: tuple[int, int]
    facing: str
    archetype: str
    treatment: str


# ---------------------------------------------------------------------------
# Flatten / ink bbox (plan §9.1's ink-cell definition: char != " ").
# ---------------------------------------------------------------------------


def _lines(art: Text) -> list[Text]:
    return list(art.split(allow_blank=True))


def _ink_bbox(art: Text) -> CellBox:
    """The `char != " "` bounding box (plan §9.1/§9.7), local to `art`."""

    lines = _lines(art)
    min_col = min_row = None
    max_col = max_row = -1
    for row, line in enumerate(lines):
        plain = line.plain
        for col, ch in enumerate(plain):
            if ch == " ":
                continue
            if min_col is None or col < min_col:
                min_col = col
            if min_row is None or row < min_row:
                min_row = row
            if col > max_col:
                max_col = col
            if row > max_row:
                max_row = row
    if min_col is None or min_row is None:
        return CellBox(0, 0, 0, 0)
    return CellBox(min_col, min_row, max_col - min_col + 1, max_row - min_row + 1)


def _crop_to_ink(art: Text) -> tuple[Text, CellBox]:
    """`art` cropped to its ink bbox, and that bbox (local to `art`)."""

    bbox = _ink_bbox(art)
    if bbox.width <= 0 or bbox.height <= 0:
        return Text(), bbox
    lines = _lines(art)
    cropped = Text("\n").join(
        line[bbox.col : bbox.col + bbox.width] for line in lines[bbox.row : bbox.row + bbox.height]
    )
    return cropped, bbox


def _to_cells(art: Text) -> list[list[Cell]]:
    """Flatten a cropped sprite into `(char, style)` rows. A space keeps
    `None` style so it composites as transparent (matches the ink-cell
    definition and the existing `_SceneComposer._crop`/`_paint` convention)."""

    rows: list[list[Cell]] = []
    for line in _lines(art):
        spans = sorted(line.spans, key=lambda s: s.start)
        row: list[Cell] = []
        plain = line.plain
        for i, ch in enumerate(plain):
            style: Style | None = None
            for span in spans:
                if span.start <= i < span.end:
                    resolved = span.style
                    style = resolved if isinstance(resolved, Style) else Style.parse(str(resolved))
                    break
            row.append((ch, style if ch != " " else None))
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Art mode -> (entity_type, subtype) for the continuous renderers.
# ---------------------------------------------------------------------------


def _continuous_entity_subtype(obj: PhysicalObject) -> tuple[str, str]:
    """The `edge.art.generator.generate_sprite` `(entity_type, subtype)` for
    one `ArtMode.CONTINUOUS` object, from its `SceneKey.tag`/`continuous_kind`
    (plan §2.1/§2.2/§2.5's closed continuous-kind set; `classify.py` is the
    only other place this vocabulary is enumerated)."""

    assert obj.continuous_kind is not None
    if obj.key.tag == "planet":
        return "planet", obj.continuous_kind
    return "discovery", obj.continuous_kind


def _treatment(obj: PhysicalObject) -> str:
    """Styling treatment for a rendered object, mirroring the existing
    `_SceneComposer._sprite_cells` convention (`"derelict"` dim, `"hostile"`
    inverse-red) without importing `edge/tui/widgets.py`."""

    if obj.retention is SceneRetention.WRECK:
        return "derelict"
    if obj.retention is SceneRetention.HOSTILE_SHIP:
        return "hostile"
    return ""


def _apply_treatment(art: Text, treatment: str) -> Text:
    styled = art.copy()
    if treatment == "derelict":
        styled.stylize("dim")
    elif treatment == "hostile":
        styled.stylize("on dark_red")
    return styled


# ---------------------------------------------------------------------------
# Composition-local render cache (plan §6.2 rule 3).
# ---------------------------------------------------------------------------


@dataclass
class RenderCache:
    """One composition's render cache: at most one uncached render per
    distinct `RenderCacheKey`. `renders` counts unique (miss) renders;
    `hits` counts served-from-cache lookups -- together these are the
    render-once-per-final-box assertion surface for tests."""

    _store: dict[RenderCacheKey, Text] = field(default_factory=dict)
    renders: int = 0
    hits: int = 0

    def get(self, key: RenderCacheKey, build: Callable[[], Text]) -> Text:
        cached = self._store.get(key)
        if cached is not None:
            self.hits += 1
            return cached
        art = build()
        self._store[key] = art
        self.renders += 1
        return art


# ---------------------------------------------------------------------------
# Resolving one projection to raw (untreated, uncropped-to-final) art.
# ---------------------------------------------------------------------------

_FACING = "right"
"""Ships have no facing signal on `PhysicalObject`/`Projection` yet (plan §9.3
fixes no such field); every ladder render uses the library's canonical facing.
A real per-ship facing is future work, not invented here."""


def _resolve_ladder(
    obj: PhysicalObject, rung: LadderRung, seed: int, cache: RenderCache
) -> tuple[Text, RenderCacheKey]:
    ladder_key = obj.ladder_key
    assert ladder_key is not None
    box = (rung.natural.width, rung.natural.height)
    treatment = _treatment(obj)
    archetype = ladder_key.archetype_id or ""
    kind = ladder_key.kind
    subtype = ladder_key.subtype
    key = RenderCacheKey(
        entity_type=kind,
        subtype=subtype,
        seed=seed,
        box=box,
        facing=_FACING if kind == "ship" else "",
        archetype=archetype,
        treatment=treatment,
    )

    def _build() -> Text:
        archetype_id = archetype or None
        if kind == "ship":
            raw = SPRITES.generate_ship(subtype, seed, box[0], box[1], archetype_id, _FACING)
        else:
            raw = SPRITES.generate_port(subtype, seed, box[0], box[1], archetype_id)
        return _apply_treatment(raw, treatment)

    return cache.get(key, _build), key


def _resolve_continuous(
    obj: PhysicalObject, box: tuple[int, int], seed: int, cache: RenderCache
) -> tuple[Text, RenderCacheKey]:
    entity_type, subtype = _continuous_entity_subtype(obj)
    treatment = _treatment(obj)
    archetype = obj.archetype_id or ""
    key = RenderCacheKey(
        entity_type=entity_type, subtype=subtype, seed=seed, box=box,
        facing="", archetype=archetype, treatment=treatment,
    )

    def _build() -> Text:
        raw = generate_sprite(entity_type, subtype, seed, box[0], box[1], obj.archetype_id)
        return _apply_treatment(raw, treatment)

    return cache.get(key, _build), key


# ---------------------------------------------------------------------------
# The actual-ink envelope used to validate a resolved render (plan §6.2 rule
# 2): the same conservative "max" side the solver used for separation
# clearance, so a correction check is judged against the guarantee the solve
# already made -- not against `Projection.ink_est`, which plan §9.6/solve.py
# fills from the *min* side (a floor, used for glyph clearance, not a ceiling
# a render can "exceed"). Reimplemented locally (not imported from
# `edge.scene.solve`, whose helpers are private) because it is the same tiny,
# pure formula `edge.scene.solve._ink_box` uses.
# ---------------------------------------------------------------------------


def _max_ink_envelope(
    obj: PhysicalObject, bounds: CellBox, rung: LadderRung | None, catalog: ArtGeometryCatalog
) -> CellBox:
    if obj.art_mode is ArtMode.LADDER:
        assert rung is not None
        width, height = rung.ink_max.width, rung.ink_max.height
    else:
        assert obj.continuous_kind is not None
        yield_ = catalog.continuous(obj.continuous_kind)
        width = math.ceil(Fraction(bounds.width) * yield_.ink_fraction_max)
        height = math.ceil(Fraction(bounds.height) * yield_.ink_fraction_max)
    col = bounds.col + (bounds.width - width) // 2
    row = bounds.row + (bounds.height - height) // 2
    return CellBox(col, row, max(width, 0), max(height, 0))


def _rect_gap(a: CellBox, b: CellBox) -> int:
    dx = max(a.col - (b.col + b.width), b.col - (a.col + a.width))
    dy = max(a.row - (b.row + b.height), b.row - (a.row + a.height))
    if dx < 0 and dy < 0:
        return -min(-dx, -dy)
    return max(dx, dy)


def _inflate(box: CellBox, margin: int) -> CellBox:
    return CellBox(box.col - margin, box.row - margin, box.width + 2 * margin, box.height + 2 * margin)


def _overlap_area(a: CellBox, b: CellBox) -> int:
    left, right = max(a.col, b.col), min(a.col + a.width, b.col + b.width)
    top, bottom = max(a.row, b.row), min(a.row + a.height, b.row + b.height)
    if right <= left or bottom <= top:
        return 0
    return (right - left) * (bottom - top)


# ---------------------------------------------------------------------------
# Painted output.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PaintedObject:
    key: SceneKey
    art: Text
    """Cropped to actual ink."""
    scene_box: CellBox
    """The ink box in scene (viewport) coordinates -- `art`'s placement."""
    natural_box: CellBox
    """The selected rung's/box-class's own natural `(width, height)`, in
    scene coordinates -- the *container* `art` was rendered into, before
    ink-cropping. This -- never the cropped `scene_box` -- is what
    `build_station_reference` publishes (plan §4 invariant 12/§9.7: "the
    *rung's* box, never a padded container")."""
    depth: int
    occludes: bool


@dataclass(frozen=True, slots=True)
class GlyphPaint:
    key: SceneKey
    col: int
    row: int
    glyph: str = "·"


@dataclass(frozen=True, slots=True)
class ScenePaint:
    """The final structurally-safe paint output: only accepted, successfully
    resolved objects appear here (plan §4 invariant 9 / this WP's assertion --
    a rejected object can never become scene text; there is no text-fallback
    branch for one in this type at all). Depth-ordered far to near, matching
    `ScenePlan.projections`."""

    painted: tuple[PaintedObject, ...]
    corrected: tuple[Projection, ...]
    """Projections whose `ink_actual` differs from their solved `bounds`/
    `ink_est` after the bounded validation correction (plan §9.7's `ink_actual`
    population)."""
    dropped: tuple[SceneKey, ...]
    """Objects the bounded correction rejected (shrink still failed)."""
    glyphs: tuple[GlyphPaint, ...]
    render_cache: RenderCache
    validation_corrections: int


def _render_seed(obj: PhysicalObject, sector_id: int) -> int:
    """The render seed for one object, matching the legacy composer's choice.

    Within one authored rung the seed still selects a *variant*, and variants
    differ in ink extent — a Stardock's 15x15 tier ink-crops to 15x14 at one
    seed and 13x12 at another. Legacy seeds a port render from the sector id
    (`_SceneComposer._paint_station`) and a starbase from `starbase_id`; the
    latter already equals `obj.key.ident`, so only the port needed aligning
    for the two composers to draw the identical sprite at the identical size
    (WP-SC12). Everything else keeps its own stable identity."""

    if obj.key.tag == "port":
        return sector_id
    return obj.key.ident


def _resolve_and_render(
    obj: PhysicalObject,
    projection: Projection,
    catalog: ArtGeometryCatalog,
    cache: RenderCache,
    sector_id: int,
) -> tuple[Text, CellBox, LadderRung | None]:
    """Render `projection` at its currently-selected size and return
    `(art, container_bounds, rung)`. `container_bounds` may differ from
    `projection.bounds` after a shrink."""

    seed = _render_seed(obj, sector_id)
    if obj.art_mode is ArtMode.LADDER:
        assert projection.rung is not None
        art, _ = _resolve_ladder(obj, projection.rung, seed, cache)
        container = CellBox(
            projection.bounds.col + (projection.bounds.width - projection.rung.natural.width) // 2,
            projection.bounds.row + (projection.bounds.height - projection.rung.natural.height) // 2,
            projection.rung.natural.width,
            projection.rung.natural.height,
        )
        return art, container, projection.rung
    assert obj.continuous_kind is not None
    catalog_yield = catalog.continuous(obj.continuous_kind)
    if projection.box_class is not None:
        box = catalog_yield.box_classes[projection.box_class]
        width, height = min(box.width, projection.bounds.width), min(box.height, projection.bounds.height)
    else:
        width, height = projection.bounds.width, projection.bounds.height
    art, _ = _resolve_continuous(obj, (max(width, 1), max(height, 1)), seed, cache)
    container = CellBox(
        projection.bounds.col + (projection.bounds.width - width) // 2,
        projection.bounds.row + (projection.bounds.height - height) // 2,
        width,
        height,
    )
    return art, container, None


def _shrink(
    obj: PhysicalObject, projection: Projection, catalog: ArtGeometryCatalog
) -> Projection | None:
    """One step down the ladder/box-class list, or `None` if there is
    nowhere left to shrink to (the caller then rejects the object). Never
    raises the cost class, never restarts the camera search (plan §6.2 rule
    2) -- this only ever narrows `bounds`/`rung`/`box_class` in place."""

    if obj.art_mode is ArtMode.LADDER:
        assert projection.rung is not None
        ladder_key = obj.ladder_key
        rungs = catalog.rungs(ladder_key) if ladder_key is not None else ()
        lower = [r for r in rungs if r.index > projection.rung.index]
        if not lower:
            return None
        next_rung = min(lower, key=lambda r: r.index)
        return Projection(
            key=projection.key, bounds=projection.bounds, depth=projection.depth,
            rung=next_rung, box_class=projection.box_class, ink_est=projection.ink_est,
            ink_actual=projection.ink_actual, visible_fraction=projection.visible_fraction,
            label_bounds=projection.label_bounds, accepted=projection.accepted,
        )
    assert obj.continuous_kind is not None
    catalog_yield = catalog.continuous(obj.continuous_kind)
    current = projection.box_class if projection.box_class is not None else 0
    if current + 1 >= len(catalog_yield.box_classes):
        return None
    return Projection(
        key=projection.key, bounds=projection.bounds, depth=projection.depth,
        rung=projection.rung, box_class=current + 1, ink_est=projection.ink_est,
        ink_actual=projection.ink_actual, visible_fraction=projection.visible_fraction,
        label_bounds=projection.label_bounds, accepted=projection.accepted,
    )


def resolve_scene(
    plan: ScenePlan,
    arrangement: WorldArrangement,
    catalog: ArtGeometryCatalog,
    tuning: SceneTuning,
) -> ScenePaint:
    """Resolve every accepted `Projection` in `plan` to real art, apply the
    one bounded actual-ink validation correction per object (plan §6.2 rule
    2, §9.7), and depth-order the survivors far to near for paint.

    `tuning` supplies `separation_margin` and `min_visible_fraction_by_scale_class`
    for the correction's re-check -- the same config-driven numbers the
    solver itself used (no new tunable is invented here).
    """

    objects = {o.key: o for o in arrangement.objects}
    cache = RenderCache()
    validation_corrections = 0
    corrected: list[Projection] = []
    dropped: list[SceneKey] = []

    # Pass 1: render every accepted projection at its solved size.
    resolved: dict[SceneKey, tuple[Text, CellBox, CellBox, Projection]] = {}
    for projection in plan.projections:
        obj = objects[projection.key]
        art, container, rung = _resolve_and_render(
            obj, projection, catalog, cache, arrangement.sector_id)
        cropped, local_bbox = _crop_to_ink(art)
        scene_ink = CellBox(
            container.col + local_bbox.col, container.row + local_bbox.row,
            local_bbox.width, local_bbox.height,
        )
        resolved[projection.key] = (cropped, scene_ink, container, projection)

    # Pass 2: bounded correction. Objects nearer first, matching the solve's
    # own "later/less-priority loses" convention when two boxes conflict.
    order = sorted(resolved, key=lambda k: (-objects[k].face.area_su, k))
    live_projection: dict[SceneKey, Projection] = {k: p for k, (_, _, _, p) in resolved.items()}
    live_ink: dict[SceneKey, CellBox] = {k: ink for k, (_, ink, _, _) in resolved.items()}
    live_art: dict[SceneKey, Text] = {k: art for k, (art, _, _, _) in resolved.items()}
    live_natural: dict[SceneKey, CellBox] = {k: box for k, (_, _, box, _) in resolved.items()}

    for key in order:
        obj = objects[key]
        projection = live_projection[key]
        # Judge the render against the box it was *rendered into*, not the
        # solver's request box. For a continuous object with a box class those
        # differ (`_resolve_and_render` clips the class box to `bounds`), so
        # comparing a 28x14 render's ink against 90% of a 56x14 request mixed
        # two different boxes and fired the correction spuriously.
        max_env = _max_ink_envelope(obj, live_natural[key], projection.rung, catalog)
        actual = live_ink[key]
        exceeds = actual.width > max_env.width or actual.height > max_env.height
        if not exceeds:
            continue
        validation_corrections += 1
        current = projection
        while True:
            shrunk = _shrink(obj, current, catalog)
            if shrunk is None:
                dropped.append(key)
                del live_projection[key]
                del live_ink[key]
                del live_art[key]
                del live_natural[key]
                break
            art, container, _ = _resolve_and_render(
                obj, shrunk, catalog, cache, arrangement.sector_id)
            cropped, local_bbox = _crop_to_ink(art)
            scene_ink = CellBox(
                container.col + local_bbox.col, container.row + local_bbox.row,
                local_bbox.width, local_bbox.height,
            )
            new_max_env = _max_ink_envelope(obj, container, shrunk.rung, catalog)
            if scene_ink.width <= new_max_env.width and scene_ink.height <= new_max_env.height:
                live_projection[key] = shrunk
                live_ink[key] = scene_ink
                live_art[key] = cropped
                live_natural[key] = container
                corrected.append(
                    Projection(
                        key=shrunk.key, bounds=shrunk.bounds, depth=shrunk.depth,
                        rung=shrunk.rung, box_class=shrunk.box_class, ink_est=shrunk.ink_est,
                        ink_actual=scene_ink, visible_fraction=shrunk.visible_fraction,
                        label_bounds=shrunk.label_bounds, accepted=shrunk.accepted,
                    )
                )
                break
            current = shrunk

    # Re-check separation/occlusion with the (possibly corrected) actual ink,
    # nearer-first so a nearer object's occlusion of a farther one is judged
    # with both sides' real boxes. A conflict drops the **lower-retention**
    # side -- never raises anyone's cost class, never reopens the camera
    # search.
    #
    # Dropping by depth alone (which this did before WP-SC12) states a
    # different rule from the solver's, and a strictly worse one: the solver
    # visits objects in retention order and refuses the *later, lower-priority*
    # candidate, never unseating a committed one (plan §4.5). Here the farther
    # object is very often the anchor -- `min_visible_fraction["anchor"]` is
    # `1`, so a single overlapping cell was enough -- and the scene lost its
    # planet to two ships. `planet+port+ships @ 67x30` under
    # `FixedFovPerspective` produced exactly that: a plan that admitted the
    # planet and both ships painted the ships alone.
    remaining = sorted(live_ink, key=lambda k: (live_projection[k].depth, -objects[k].face.area_su, k))
    for i, key in enumerate(remaining):
        obj = objects[key]
        if key not in live_ink or not obj.occludes:
            continue
        for other_key in remaining[i + 1 :]:
            other = objects[other_key]
            if key not in live_ink:
                break
            if other_key not in live_ink or not other.occludes:
                continue
            if live_projection[other_key].depth <= live_projection[key].depth:
                continue
            near_box = _inflate(live_ink[key], tuning.separation_margin)
            far_box = _inflate(live_ink[other_key], tuning.separation_margin)
            if _rect_gap(near_box, far_box) >= 0:
                continue
            area = live_ink[other_key].width * live_ink[other_key].height
            overlap = _overlap_area(live_ink[key], live_ink[other_key])
            visible = Fraction(max(area - overlap, 0), area) if area > 0 else Fraction(1)
            threshold = tuning.min_visible_fraction_by_scale_class.get(other.scale_class, Fraction(0))
            if visible >= threshold:
                continue
            # Lower retention loses; ties (same tier) fall back to the
            # farther object, the pre-WP-SC12 behaviour, and finally to the
            # key so the choice is never container-order dependent (§4.8).
            loser = max(
                (key, other_key),
                key=lambda k: (int(objects[k].retention), live_projection[k].depth, k),
            )
            dropped.append(loser)
            del live_ink[loser]
            del live_projection[loser]
            del live_art[loser]
            del live_natural[loser]

    painted = [
        PaintedObject(key=key, art=live_art[key], scene_box=live_ink[key],
                      natural_box=live_natural[key],
                      depth=live_projection[key].depth, occludes=objects[key].occludes)
        for key in remaining
        if key in live_ink
    ]
    painted.sort(key=lambda p: (-p.depth, -objects[p.key].face.area_su, p.key))

    covered = [p.scene_box for p in painted]
    glyphs = _scatter_glyphs(arrangement, plan.viewport, covered, tuning)

    return ScenePaint(
        painted=tuple(painted),
        corrected=tuple(corrected),
        dropped=tuple(sorted(set(dropped))),
        glyphs=glyphs,
        render_cache=cache,
        validation_corrections=validation_corrections,
    )


# ---------------------------------------------------------------------------
# Post-paint glyph scatter (plan §4.19, §9.6): re-run against the *actual*
# painted ink boxes, since real art may be smaller/larger than the estimate
# `edge.scene.solve` scattered against. The placed *count* is authoritative
# from `ScenePlan.counters` already; this only decides *where* to draw each
# already-decided glyph. Deterministic, seed-free (never `random.Random`,
# never game RNG) -- mirrors `edge.scene.solve._scatter_glyphs`'s hashing.
# ---------------------------------------------------------------------------


def _hash_index(key: str, modulus: int) -> int:
    if modulus <= 0:
        return 0
    digest = hashlib.blake2b(key.encode(), digest_size=8).digest()
    return int.from_bytes(digest, "big") % modulus


def _scatter_glyphs(
    arrangement: WorldArrangement, viewport: CellBox, covered: list[CellBox], cfg: SceneTuning
) -> tuple[GlyphPaint, ...]:
    if viewport.width <= 0 or viewport.height <= 0:
        return ()

    def _is_covered(col: int, row: int) -> bool:
        return any(box.col <= col < box.col + box.width and box.row <= row < box.row + box.height for box in covered)

    placed_cells: list[tuple[int, int]] = []
    out: list[GlyphPaint] = []
    for glyph in sorted(arrangement.glyphs, key=lambda g: g.key):
        for mark in range(glyph.count):
            for attempt_no in range(cfg.max_glyph_tries):
                seed = (
                    f"{arrangement.sector_id}|glyphs|{viewport.width}x{viewport.height}"
                    f"|{glyph.key.tag}:{glyph.key.ident}|{mark}|{attempt_no}"
                )
                idx = _hash_index(seed, viewport.width * viewport.height)
                col = viewport.col + idx % viewport.width
                row = viewport.row + idx // viewport.width
                if _is_covered(col, row):
                    continue
                if any(abs(col - pc) + abs(row - pr) < cfg.glyph_spacing for pc, pr in placed_cells):
                    continue
                placed_cells.append((col, row))
                out.append(GlyphPaint(key=glyph.key, col=col, row=row))
                break
    return tuple(out)


# ---------------------------------------------------------------------------
# Depth-ordered compositing into a flat cell grid (plan §9.7's last bullet:
# "paint(ink) into the cell grid, spaces transparent"; belt paint-through and
# post-sprite glyph scatter, plan §2.5/§4.19).
# ---------------------------------------------------------------------------


def paint_grid(paint: ScenePaint, viewport: CellBox) -> list[list[Cell]]:
    """Composite `paint.painted` (already depth-ordered far to near) and
    `paint.glyphs` into one `viewport.height` x `viewport.width` cell grid.

    A `occludes=False` object (a belt) still paints its own ink, but a
    *later* (nearer) object painted on top of it overwrites only the cells it
    actually inks -- belt cells outside that footprint keep showing through,
    which is what "permeable"/paint-through means for a field object (plan
    §2.5). Glyphs are scattered after every sprite paints, per plan §9.6/§9.7.
    """

    grid: list[list[Cell]] = [[(" ", None) for _ in range(viewport.width)] for _ in range(viewport.height)]
    for obj in paint.painted:
        rows = _to_cells(obj.art)
        for r, row in enumerate(rows):
            y = obj.scene_box.row + r - viewport.row
            if not 0 <= y < viewport.height:
                continue
            for c, (ch, style) in enumerate(row):
                if ch == " ":
                    continue
                x = obj.scene_box.col + c - viewport.col
                if 0 <= x < viewport.width:
                    grid[y][x] = (ch, style)
    for glyph in paint.glyphs:
        y, x = glyph.row - viewport.row, glyph.col - viewport.col
        if 0 <= y < viewport.height and 0 <= x < viewport.width:
            grid[y][x] = (glyph.glyph, None)
    return grid


# ---------------------------------------------------------------------------
# The docked-header station reference (plan §4 invariant 12): an immutable
# `(sector_id, station_kind, object_id) -> natural (width, height)` mapping,
# published for every rendered port/starbase in one `resolve_scene()` call.
# `station_kind` here is `SceneKey.tag` ("port"/"starbase"); WP-SC01's
# `StarbaseDTO.sector_id`/`PortDTO.sector_id` is what a caller supplies as
# `sector_id`. Port and starbase id namespaces may overlap, so all three key
# parts are required -- `lookup` returns `None` (never a stale/mismatched
# size) for a key that was not published with an exact match on all three.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StationKey:
    sector_id: int
    station_kind: str
    object_id: int


@dataclass(frozen=True, slots=True)
class StationReference:
    """Immutable publish/lookup for docked-header natural dimensions.

    Not wired into `edge/tui/station_art.py` by this WP -- that migration is
    WP-SC10's job (plan's WP-SC07 "Implementation" bullet: "Publish an
    immutable mapping ... Reject exact-key mismatches"). This type is the
    seam that migration will consume.
    """

    entries: tuple[tuple[StationKey, tuple[int, int]], ...]

    def lookup(self, sector_id: int, station_kind: str, object_id: int) -> tuple[int, int] | None:
        wanted = StationKey(sector_id, station_kind, object_id)
        for key, size in self.entries:
            if key == wanted:
                return size
        return None


def build_station_reference(sector_id: int, paint: ScenePaint) -> StationReference:
    """Publish the natural `(width, height)` -- the selected rung's own
    `natural` box, never the ink-cropped `scene_box` and never a padded
    container -- for every painted port/starbase (`SceneKey.tag`)."""

    entries = tuple(
        (StationKey(sector_id, obj.key.tag, obj.key.ident), (obj.natural_box.width, obj.natural_box.height))
        for obj in paint.painted
        if obj.key.tag in ("port", "starbase")
    )
    return StationReference(entries)


# ---------------------------------------------------------------------------
# Direct-open docked-screen fallback (plan §4 invariant 16, WP-SC07
# Implementation bullet 7): a docked screen opened with no preceding sector
# render (so no `StationReference` entry exists for it yet) resolves to a
# natural authored rung from the catalogue -- never `SceneArtConfig`'s padded
# `station_size().max_width/max_height` bounds, which is what
# `edge/tui/station_art.py::station_icon_dimensions` currently falls back to.
# This is an additive helper only: wiring it into `station_icon_dimensions`
# itself is left to WP-SC10 (plan: "keep this change minimal/additive since
# full consumer migration is WP-SC10, not this WP").
# ---------------------------------------------------------------------------

_STATION_LADDER_SUBTYPE = {"port": "trading_port", "stardock": "stardock", "starbase": "starbase"}
"""`station_icon_dimensions`'s `kind` vocabulary -> `LadderKey.subtype`,
matching `edge.scene.classify._port_ladder_subtype`/`_starbase_object`."""


def natural_fallback_dimensions(
    catalog: ArtGeometryCatalog, station_kind: str, archetype_id: str | None = None
) -> tuple[int, int] | None:
    """The richest complete authored rung's natural `(width, height)` for a
    direct-open docked screen, or `None` if the catalogue has no rung for
    this `(subtype, archetype_id)` at all (the caller then has nothing
    authored to fall back to, and must pick its own last resort)."""

    subtype = _STATION_LADDER_SUBTYPE.get(station_kind)
    if subtype is None:
        return None
    key = LadderKey(kind="port", subtype=subtype, axis="vertical", archetype_id=archetype_id or "")
    rungs = catalog.rungs(key)
    if not rungs:
        return None
    richest = min(rungs, key=lambda r: r.index)
    return richest.natural.width, richest.natural.height


__all__ = [
    "Cell",
    "GlyphPaint",
    "PaintedObject",
    "RenderCache",
    "RenderCacheKey",
    "ScenePaint",
    "StationKey",
    "StationReference",
    "build_station_reference",
    "natural_fallback_dimensions",
    "paint_grid",
    "resolve_scene",
]
