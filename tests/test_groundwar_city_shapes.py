"""GW-WP28 — city silhouettes (D37) and the lockstep guarantee they depend on.

`GroundPlace.inside`, `AssaultCity.inside`, and `SurveySettlement.inside` are three
separate call sites over the same shared geometry. Before this WP they trivially agreed
because they were all the same bbox inequality; a shape system only stays safe if all
three keep answering the same question about the same cell. `shapes.shape_contains` is
the one function all three delegate to — this file is the proof that the delegation
actually holds, plus the structural invariants a generated city must keep regardless of
which family it rolled.
"""

from __future__ import annotations

from edge.config import load_default_config
from edge.core.groundwar import assault as ga
from edge.core.groundwar import shapes as gw_shapes
from edge.core.groundwar import survey as gw_survey
from edge.core.groundwar import world as gw_world

CFG = load_default_config()

_FAMILIES: tuple[tuple[gw_shapes.PlaceShape, int], ...] = (
    ("rect", 0),
    ("chamfered", gw_shapes.chamfer_param(34, 20)),
    ("chamfered", gw_shapes.chamfer_param(46, 26)),
    ("ellipse", 0),
    ("stepped", gw_shapes.stepped_param(0, 34, 20)),
    ("stepped", gw_shapes.stepped_param(1, 34, 20)),
    ("stepped", gw_shapes.stepped_param(2, 34, 20)),
    ("stepped", gw_shapes.stepped_param(3, 34, 20)),
)


def test_ground_place_and_assault_city_agree_on_every_cell() -> None:
    """The lockstep test: walk every bbox cell of every family, in both directions.

    `GroundPlace` and `AssaultCity` are independent dataclasses with independent
    `inside()` implementations that happen to call the same underlying predicate.
    Nothing in the type system enforces that they stay in sync — only a test that
    exercises both against the same geometry does.
    """
    x0, y0, x1, y1 = 10, 10, 43, 29  # a 34x20 town-sized box
    for shape, param in _FAMILIES:
        place = gw_world.GroundPlace(
            id=1, name="Test", x0=x0, y0=y0, x1=x1, y1=y1, shape=shape, shape_param=param)
        city = ga.AssaultCity(
            id=1, name="Test", cx=place.cx, cy=place.cy, x0=x0, y0=y0, x1=x1, y1=y1,
            shape=shape, shape_param=param)
        mismatches = [
            (x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
            if place.inside(x, y) != city.inside(x, y)
        ]
        assert not mismatches, f"{shape}/{param}: GroundPlace/AssaultCity disagree at {mismatches[:5]}"


def test_survey_settlement_strict_interior_is_a_subset_of_the_place() -> None:
    """`SurveySettlement.inside` is deliberately stricter (excludes the wall ring) —
    the lockstep property here is one-directional: every cell it accepts must also be
    a cell `GroundPlace`/`AssaultCity` accept, and it must accept strictly fewer.
    """
    x0, y0, x1, y1 = 10, 10, 43, 29
    for shape, param in _FAMILIES:
        place = gw_world.GroundPlace(
            id=1, name="Test", x0=x0, y0=y0, x1=x1, y1=y1, shape=shape, shape_param=param)
        settlement = gw_survey.SurveySettlement(
            id=1, name="Test", cx=place.cx, cy=place.cy, x0=x0, y0=y0, x1=x1, y1=y1,
            shape=shape, shape_param=param)
        strict_count = 0
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if settlement.inside(x, y):
                    strict_count += 1
                    assert place.inside(x, y), (
                        f"{shape}/{param}: settlement accepted {(x, y)} the place rejects")
        full_count = sum(
            1 for y in range(y0, y1 + 1) for x in range(x0, x1 + 1) if place.inside(x, y))
        assert 0 < strict_count < full_count, f"{shape}/{param}: strict interior didn't shrink"


def test_generated_cities_use_every_family_across_a_seed_sweep() -> None:
    """The weighted roll must actually reach every family, not just the common case."""
    seen: set[str] = set()
    for seed in range(1, 60):
        ground = gw_world.generate_world_ground(
            CFG, seed=seed, planet_type="terrestrial_warm", places=3)
        seen.update(stamp.place.shape for stamp in ground.stamps)
    assert seen == {"rect", "chamfered", "ellipse", "stepped"}


def test_every_gate_sits_on_the_ring_and_the_ring_is_shape_consistent() -> None:
    for seed in range(1, 15):
        ground = gw_world.generate_world_ground(
            CFG, seed=seed, planet_type="terrestrial_warm", places=3)
        for stamp in ground.stamps:
            place = stamp.place
            for gx, gy in stamp.gates:
                assert place.inside(gx, gy), f"seed {seed}: gate off the place's own shape"
            for wx, wy in stamp.perimeter:
                assert place.inside(wx, wy)
                # A perimeter cell must have at least one neighbour outside the shape —
                # otherwise it is an interior cell wrongly classified as wall.
                assert any(
                    not place.inside(wx + dx, wy + dy)
                    for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))
                ), f"seed {seed}: perimeter cell {(wx, wy)} has no outside-facing neighbour"


def test_every_reserved_slots_full_footprint_is_inside_the_shape() -> None:
    for seed in range(1, 15):
        ground = gw_world.generate_world_ground(
            CFG, seed=seed, planet_type="terrestrial_warm", places=3)
        for stamp in ground.stamps:
            place = stamp.place
            for ax, ay in stamp.reserved:
                for dx in range(2):
                    for dy in range(2):
                        assert place.inside(ax + dx, ay + dy), (
                            f"seed {seed}: emplacement slot {(ax, ay)} 2x2 not fully inside")


def test_no_building_footprint_crosses_the_silhouette() -> None:
    for seed in range(1, 15):
        ground = gw_world.generate_world_ground(
            CFG, seed=seed, planet_type="terrestrial_warm", places=3)
        for stamp in ground.stamps:
            place = stamp.place
            for x, y, w, h in stamp.buildings:
                for dx in range(w):
                    for dy in range(h):
                        assert place.inside(x + dx, y + dy), (
                            f"seed {seed}: building at {(x, y)} size {(w, h)} crosses the wall")


def test_survey_and_assault_still_agree_on_a_shaped_world() -> None:
    """The GW-WP19 shared-layout contract, re-checked specifically against a world
    whose places are *not* rectangles — the property this whole WP could break."""
    seed = 4242
    ground = gw_world.generate_world_ground(
        CFG, seed=seed, planet_type="terrestrial_warm", places=3)
    assert any(stamp.place.shape != "rect" for stamp in ground.stamps), (
        "test seed rolled all-rect; pick a different seed to exercise this property")
    smap = gw_survey.generate_survey(
        CFG, seed=seed, planet_type="terrestrial_warm", inhabited=True, sites=(), places=3)
    amap = ga.generate_assault_map(
        CFG, seed=seed, planet_type="terrestrial_warm", cities=3, citadel_level=0)
    assert smap.feature == amap.feature
    struct_at = {cell for s in amap.structures for cell in s.cells}
    assert smap.blocked <= struct_at
