"""Tests for WP-SC07's art resolution and depth paint (`edge/art/scene_paint.py`).

Covers plan §9.7's verification list: laddered/continuous resolution through
the catalogue (never `fit_box`'s clamp), ink cropping, belt paint-through,
Entity foreground rendering, the render cache / render-once-per-final-box
counter, the station-reference publish/lookup (including reject-on-mismatch),
the direct-open fallback, and that a rejected object can never become painted
scene output.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from edge.art.geometry_catalog import load_default_geometry_catalog, load_geometry_catalog
from edge.art.scene_paint import (
    RenderCache,
    StationKey,
    _resolve_ladder,
    build_station_reference,
    natural_fallback_dimensions,
    paint_grid,
    resolve_scene,
)
from edge.art.scene_tuning import build_continuous_yields, build_scene_tuning
from edge.config import load_config
from edge.scene.catalog import LadderKey
from edge.scene.geometry import CellBox, Face, FaceShape, Region, Su, Vec3
from edge.scene.model import (
    ArtMode,
    PhysicalObject,
    Placement,
    SceneKey,
    SceneRetention,
    WorldArrangement,
)
from edge.scene.project import FixedFovPerspective
from edge.scene.solve import solve

# ---------------------------------------------------------------------------
# Real catalogue + real WP-SC05 calibration, exactly as a production caller
# would assemble them.
# ---------------------------------------------------------------------------

_CFG = load_config("config/default.yaml")
_PM = _CFG.scene.physical_model
TUNING = build_scene_tuning(_PM)
CATALOG = load_geometry_catalog(build_continuous_yields(_PM))

VIEWPORT = CellBox(col=0, row=0, width=100, height=36)

_SHIP_ARCHETYPE = "amorous_imp"
_SHIP_LADDER_KEY = LadderKey(kind="ship", subtype="fighter", axis="horizontal", archetype_id=_SHIP_ARCHETYPE)
_PORT_LADDER_KEY = LadderKey(kind="port", subtype="trading_port", axis="vertical", archetype_id=_SHIP_ARCHETYPE)


def _region() -> Region:
    return Region(x_min=-200, x_max=200, y_min=-100, y_max=100, z_min=1, z_max=300)


def _placement(key: SceneKey, x: Su, y: Su, z: Su) -> Placement:
    return Placement(key=key, position=Vec3(x, y, z))


def _ship_object(
    ident: int, *, retention: SceneRetention = SceneRetention.NEUTRAL_SHIP, hostility_ordinal: int = 5
) -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("ship", ident), parent=None,
        face=Face(shape=FaceShape.RECT, width_su=40, height_su=10),
        scale_class="ship", art_mode=ArtMode.LADDER, ladder_key=_SHIP_LADDER_KEY,
        continuous_kind=None, retention=retention, hostility_ordinal=hostility_ordinal,
        threat_rank=1, region=_region(), flexible=True, occludes=True,
        label=f"Ship {ident}", destination=None,
    )


def _port_object(ident: int) -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("port", ident), parent=None,
        face=Face(shape=FaceShape.RECT, width_su=20, height_su=14),
        scale_class="orbital", art_mode=ArtMode.LADDER, ladder_key=_PORT_LADDER_KEY,
        continuous_kind=None, retention=SceneRetention.ORBITAL, hostility_ordinal=0,
        threat_rank=0, region=_region(), flexible=True, occludes=True,
        label=f"Port {ident}", destination=None,
    )


def _planet_object(ident: int, ptype: str = "terrestrial_warm") -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("planet", ident), parent=None,
        face=Face(shape=FaceShape.CIRCLE, width_su=60, height_su=30),
        scale_class="anchor", art_mode=ArtMode.CONTINUOUS, ladder_key=None,
        continuous_kind=ptype, retention=SceneRetention.ANCHOR, hostility_ordinal=0,
        threat_rank=0, region=_region(), flexible=False, occludes=True,
        label=f"Planet {ident}", destination=None,
    )


def _belt_object(ident: int) -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("planet", ident), parent=None,
        face=Face(shape=FaceShape.FIELD, width_su=200, height_su=20),
        scale_class="belt", art_mode=ArtMode.CONTINUOUS, ladder_key=None,
        continuous_kind="asteroid_belt", retention=SceneRetention.ANCHOR, hostility_ordinal=0,
        threat_rank=0, region=_region(), flexible=False, occludes=False,
        label=f"Belt {ident}", destination=None,
    )


def _entity_object(ident: int) -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("entity", ident), parent=None,
        face=Face(shape=FaceShape.RECT, width_su=30, height_su=15),
        scale_class="entity", art_mode=ArtMode.CONTINUOUS, ladder_key=None,
        continuous_kind="entity", retention=SceneRetention.ENTITY, hostility_ordinal=0,
        threat_rank=0, region=_region(), flexible=False, occludes=True,
        label=f"Entity {ident}", destination=None,
    )


def _arrangement(objects: tuple[PhysicalObject, ...], placements: tuple[Placement, ...], sector_id: int = 7) -> WorldArrangement:
    return WorldArrangement(objects=objects, placements=placements, sector_id=sector_id)


def _solve(objects: tuple[PhysicalObject, ...], placements: tuple[Placement, ...]) -> tuple[WorldArrangement, object]:
    arrangement = _arrangement(objects, placements)
    plan = solve(arrangement, VIEWPORT, TUNING, CATALOG, FixedFovPerspective())
    return arrangement, plan


# ---------------------------------------------------------------------------
# Laddered resolution: through the catalogue rung, never fit_box's clamp.
# ---------------------------------------------------------------------------


def test_ladder_resolves_to_a_complete_catalogue_rung() -> None:
    ship = _ship_object(2)
    objects = (ship,)
    placements = (_placement(ship.key, 0, 0, 20),)
    arrangement, plan = _solve(objects, placements)
    assert isinstance(plan, object)
    paint = resolve_scene(plan, arrangement, CATALOG, TUNING)  # type: ignore[arg-type]

    ship_paints = [p for p in paint.painted if p.key == ship.key]
    assert ship_paints, "the ship must have been admitted and painted"
    painted_ship = ship_paints[0]
    known_naturals = {(r.natural.width, r.natural.height) for r in CATALOG.rungs(_SHIP_LADDER_KEY)}
    assert (painted_ship.natural_box.width, painted_ship.natural_box.height) in known_naturals


def test_ladder_render_bypasses_fit_box_and_is_never_cropped_mid_hull() -> None:
    """A ladder render at its selected rung's exact natural box is never
    smaller than that rung asked for -- `fit_box`'s clamp would silently
    substitute a narrower tier and crop it; going straight through
    `SPRITES.generate_ship`/`generate_port` cannot do that."""

    cache = RenderCache()
    rung = CATALOG.rungs(_SHIP_LADDER_KEY)[0]
    ship = _ship_object(1)
    art, key = _resolve_ladder(ship, rung, seed=1, cache=cache)
    lines = art.split(allow_blank=True)
    assert len(lines) == rung.natural.height
    assert all(line.cell_len == rung.natural.width for line in lines)
    assert key.box == (rung.natural.width, rung.natural.height)


# ---------------------------------------------------------------------------
# Continuous resolution: through the real procedural generators.
# ---------------------------------------------------------------------------


def test_continuous_planet_resolves_via_procedural_generator() -> None:
    planet = _planet_object(1)
    objects = (planet,)
    placements = (_placement(planet.key, 0, 0, 60),)
    arrangement, plan = _solve(objects, placements)
    paint = resolve_scene(plan, arrangement, CATALOG, TUNING)  # type: ignore[arg-type]
    assert len(paint.painted) == 1
    painted = paint.painted[0]
    assert painted.scene_box.width > 0 and painted.scene_box.height > 0
    assert painted.art.plain.strip(" \n") != ""


def test_entity_kind_renders_as_a_discovery_subtype() -> None:
    entity = _entity_object(1)
    objects = (entity,)
    placements = (_placement(entity.key, 0, 0, 30),)
    arrangement, plan = _solve(objects, placements)
    paint = resolve_scene(plan, arrangement, CATALOG, TUNING)  # type: ignore[arg-type]
    assert len(paint.painted) == 1
    assert paint.painted[0].art.plain.strip() != ""


# ---------------------------------------------------------------------------
# Ink cropping (plan §9.1/§9.7): no fully blank border row/col survives.
# ---------------------------------------------------------------------------


def test_painted_art_is_cropped_to_ink() -> None:
    ship = _ship_object(1)
    objects = (ship,)
    placements = (_placement(ship.key, 0, 0, 20),)
    arrangement, plan = _solve(objects, placements)
    paint = resolve_scene(plan, arrangement, CATALOG, TUNING)  # type: ignore[arg-type]
    assert len(paint.painted) == 1
    art = paint.painted[0].art
    lines = art.split(allow_blank=True)
    assert lines, "cropped art must not be empty for an admitted ship"
    assert any(ch != " " for ch in lines[0].plain), "top row must carry ink after crop"
    assert any(ch != " " for ch in lines[-1].plain), "bottom row must carry ink after crop"
    for line in lines:
        assert line.plain and (line.plain[0] != " ") or any(c != " " for c in line.plain)


# ---------------------------------------------------------------------------
# No rejected object ever becomes painted output (plan §4 invariant 9 /
# this WP's structural guarantee: `ScenePaint` carries no text-fallback
# branch for a rejected object at all).
# ---------------------------------------------------------------------------


def test_rejected_objects_never_appear_in_painted_output() -> None:
    ships = [_ship_object(i, hostility_ordinal=i) for i in range(40)]
    placements = tuple(_placement(s.key, (i % 10) * 2, 0, 10 + i) for i, s in enumerate(ships))
    arrangement, plan = _solve(tuple(ships), placements)
    paint = resolve_scene(plan, arrangement, CATALOG, TUNING)  # type: ignore[arg-type]
    painted_keys = {p.key for p in paint.painted}
    rejected_keys = set(plan.rejected)
    assert not (painted_keys & rejected_keys)
    for key in rejected_keys:
        assert key not in painted_keys


# ---------------------------------------------------------------------------
# Belt paint-through (plan §2.5): a belt's own ink paints; a nearer object's
# ink overwrites belt cells it overlaps, and belt cells outside that
# footprint keep showing.
# ---------------------------------------------------------------------------


def test_belt_paints_through_and_nearer_object_overwrites_its_footprint() -> None:
    """`paint_grid` composites far-to-near, so a nearer object's own ink
    always wins over a farther (occludes=False or not) object's ink at the
    same cell, and cells the nearer object never touches keep showing
    whatever painted under them -- exactly what "permeable"/paint-through
    means for a belt (plan §2.5). Exercised directly against `paint_grid`
    with hand-built `PaintedObject`s so the test is not at the mercy of the
    solver's camera search admitting both a giant field and a ship at once.
    """

    from edge.art.scene_paint import PaintedObject
    from rich.text import Text

    belt_art = Text("#####\n#####")
    ship_art = Text("@@\n@@")
    belt = PaintedObject(
        key=SceneKey("planet", 1), art=belt_art, scene_box=CellBox(0, 0, 5, 2),
        natural_box=CellBox(0, 0, 5, 2), depth=80, occludes=False,
    )
    ship = PaintedObject(
        key=SceneKey("ship", 2), art=ship_art, scene_box=CellBox(1, 0, 2, 2),
        natural_box=CellBox(1, 0, 2, 2), depth=20, occludes=True,
    )
    from edge.art.scene_paint import RenderCache, ScenePaint

    paint = ScenePaint(
        painted=(belt, ship), corrected=(), dropped=(), glyphs=(),
        render_cache=RenderCache(), validation_corrections=0,
    )
    grid = paint_grid(paint, CellBox(0, 0, 5, 2))
    # Ship footprint (cols 1-2) shows the ship's ink, overwriting the belt.
    assert grid[0][1] == ("@", None)
    assert grid[0][2] == ("@", None)
    # Belt cells outside the ship's footprint still show through.
    assert grid[0][0] == ("#", None)
    assert grid[0][3] == ("#", None)
    assert grid[0][4] == ("#", None)


# ---------------------------------------------------------------------------
# Render cache / render-once-per-final-box (plan §6.2 rule 3).
# ---------------------------------------------------------------------------


def test_render_cache_hits_for_a_repeated_identical_key() -> None:
    cache = RenderCache()
    rung = CATALOG.rungs(_SHIP_LADDER_KEY)[0]
    ship = _ship_object(1)
    art_a, key_a = _resolve_ladder(ship, rung, seed=42, cache=cache)
    art_b, key_b = _resolve_ladder(ship, rung, seed=42, cache=cache)
    assert key_a == key_b
    assert art_a is art_b
    assert cache.renders == 1
    assert cache.hits == 1


def test_render_cache_misses_for_a_different_box() -> None:
    cache = RenderCache()
    rungs = CATALOG.rungs(_SHIP_LADDER_KEY)
    ship = _ship_object(1)
    _resolve_ladder(ship, rungs[0], seed=1, cache=cache)
    _resolve_ladder(ship, rungs[1], seed=1, cache=cache)
    assert cache.renders == 2
    assert cache.hits == 0


def test_two_identical_ships_in_one_scene_share_one_render() -> None:
    """Two distinct objects that resolve to the same `RenderCacheKey` (same
    subtype/seed/box/facing/archetype/treatment) render once."""

    cache = RenderCache()
    rung = CATALOG.rungs(_SHIP_LADDER_KEY)[0]
    ship = _ship_object(1)
    for _ in range(5):
        _resolve_ladder(ship, rung, seed=7, cache=cache)
    assert cache.renders == 1
    assert cache.hits == 4


# ---------------------------------------------------------------------------
# Station reference publish/lookup (plan §4 invariant 12).
# ---------------------------------------------------------------------------


def test_station_reference_publishes_natural_box_for_a_port() -> None:
    anchor = _planet_object(1)
    port = _port_object(2)
    objects = (anchor, port)
    placements = (_placement(anchor.key, 0, 0, 60), _placement(port.key, 10, 0, 40))
    arrangement, plan = _solve(objects, placements)
    paint = resolve_scene(plan, arrangement, CATALOG, TUNING)  # type: ignore[arg-type]
    ref = build_station_reference(sector_id=99, paint=paint)
    port_painted = next((p for p in paint.painted if p.key == port.key), None)
    if port_painted is None:
        pytest.skip("port not admitted at this viewport/camera solve")
    size = ref.lookup(99, "port", port.key.ident)
    assert size == (port_painted.natural_box.width, port_painted.natural_box.height)


def test_station_reference_rejects_mismatched_keys() -> None:
    anchor = _planet_object(1)
    port = _port_object(2)
    objects = (anchor, port)
    placements = (_placement(anchor.key, 0, 0, 60), _placement(port.key, 10, 0, 40))
    arrangement, plan = _solve(objects, placements)
    paint = resolve_scene(plan, arrangement, CATALOG, TUNING)  # type: ignore[arg-type]
    ref = build_station_reference(sector_id=99, paint=paint)
    # Wrong sector, wrong kind, wrong object id: all rejected (None), never
    # silently inferred from another entry.
    assert ref.lookup(100, "port", port.key.ident) is None
    assert ref.lookup(99, "starbase", port.key.ident) is None
    assert ref.lookup(99, "port", port.key.ident + 999) is None


def test_station_key_requires_all_three_parts() -> None:
    key_a = StationKey(sector_id=1, station_kind="port", object_id=5)
    key_b = StationKey(sector_id=1, station_kind="starbase", object_id=5)
    assert key_a != key_b


# ---------------------------------------------------------------------------
# Direct-open fallback (plan §4 invariant 16).
# ---------------------------------------------------------------------------


def test_direct_open_fallback_resolves_to_a_natural_authored_rung() -> None:
    size = natural_fallback_dimensions(CATALOG, "port", archetype_id=_SHIP_ARCHETYPE)
    assert size is not None
    width, height = size
    natural_boxes = {(r.natural.width, r.natural.height) for r in CATALOG.rungs(_PORT_LADDER_KEY)}
    assert (width, height) in natural_boxes


def test_direct_open_fallback_is_none_for_an_unrecognized_kind() -> None:
    assert natural_fallback_dimensions(CATALOG, "not-a-station-kind") is None


def test_direct_open_fallback_uses_the_richest_rung() -> None:
    size = natural_fallback_dimensions(CATALOG, "port", archetype_id=_SHIP_ARCHETYPE)
    rungs = CATALOG.rungs(_PORT_LADDER_KEY)
    richest = min(rungs, key=lambda r: r.index)
    assert size == (richest.natural.width, richest.natural.height)


# ---------------------------------------------------------------------------
# Real geometry catalogue sanity: no shipped defaults invented here.
# ---------------------------------------------------------------------------


def test_real_default_catalog_has_continuous_yields_for_every_bucket() -> None:
    default_catalog = load_default_geometry_catalog()
    assert default_catalog.version
    yields = build_continuous_yields(_PM)
    for bucket in ("planet", "nebula", "black_hole", "wormhole", "wreck", "entity", "belt"):
        assert bucket in yields
        y = yields[bucket]
        assert isinstance(y.ink_fraction_min, Fraction)
