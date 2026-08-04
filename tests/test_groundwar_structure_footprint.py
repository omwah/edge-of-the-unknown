"""GW-WP25 — a structure occupies a footprint, not a cell.

Every footprint the shipped generator produces is still 1x1: this WP is the model
change alone, and its acceptance criterion was that the whole ground-war suite stays
green *without a single expected value or snapshot being touched*. That criterion is
what makes the machinery below untested by anything else — none of the shipped maps
exercise a `w > 1` structure yet, so the footprint paths would ship dark and only fail
once GW-WP27 turned them on, at which point the failure would look like a generation
bug rather than a plumbing one.

So these tests build multi-cell structures by hand and assert the four properties the
rest of the system will lean on: the index covers every cell, the anchor is not
privileged, line of sight does not block on the target's own body, and a levelled
building leaves a building-shaped ruin.
"""

from __future__ import annotations

from dataclasses import replace
from random import Random

from edge.config import load_default_config
from edge.core.groundwar import assault as ga
from edge.core.groundwar.models import AssaultOperation

CFG = load_default_config()
GW = CFG.groundwar
assert GW is not None


def _map(*, seed: int = 42, cities: int = 2, citadel_level: int = 0) -> ga.AssaultMap:
    return ga.generate_assault_map(
        CFG, seed=seed, planet_type="terrestrial_warm", cities=cities,
        citadel_level=citadel_level)


def _op(amap: ga.AssaultMap) -> AssaultOperation:
    return AssaultOperation(
        operation_id=1, planet_id=1, sector_id=1, planet_type="terrestrial_warm", seed=42,
        started_day=1, resolve=GW.resolve.start, retrieval_turn=20,
        cities=len(amap.cities), citadel_level=0,
        surrender_threshold=GW.resolve.surrender_threshold,
        reserved_infantry=0, reserved_armor=0,
    )


# --- the footprint itself ----------------------------------------------------


def test_a_1x1_structure_is_its_own_anchor() -> None:
    """The defaults must reproduce the pre-WP25 record exactly.

    This is the load-bearing property of the whole staging plan: everything shipped
    today is 1x1, so if the defaults drifted the "no expected value changed" gate
    would have been passing for the wrong reason.
    """
    s = ga.AssaultStructure(id=1, kind="wall", x=7, y=3, city_id=1, hp_max=200)
    assert (s.w, s.h) == (1, 1)
    assert s.cells == ((7, 3),)
    assert (s.ox, s.oy) == (7, 3)
    assert s.covers(7, 3)
    assert not s.covers(8, 3)


def test_footprint_cells_and_firing_origin() -> None:
    s = ga.AssaultStructure(id=1, kind="building_military", x=10, y=5, city_id=1,
                            hp_max=110, w=4, h=2, origin_dx=1, origin_dy=1)
    assert len(s.cells) == 8
    assert set(s.cells) == {(x, y) for x in range(10, 14) for y in range(5, 7)}
    assert (s.ox, s.oy) == (11, 6)
    assert s.covers(13, 6)
    assert not s.covers(14, 6)
    assert not s.covers(10, 7)


def test_map_index_covers_every_cell_of_every_structure_exactly_once() -> None:
    """`struct_at` is the single index the rest of the system reads through.

    A cell claimed by two structures would make `structure_at` order-dependent, and a
    cell claimed by none would make part of a building intangible — you could walk
    through it and could not shoot it.
    """
    amap = _map()
    seen: dict[tuple[int, int], int] = {}
    for s in amap.structures:
        for cell in s.cells:
            assert cell not in seen, f"{cell} claimed by structures {seen[cell]} and {s.id}"
            seen[cell] = s.id
    assert {c: s.id for c, s in amap.struct_at.items()} == seen
    for cell, s in amap.struct_at.items():
        assert amap.structure_at(*cell) is s


def test_cloud_city_map_indexes_its_footprints_too() -> None:
    """The station branch builds its own index; it must satisfy the same contract."""
    amap = ga.generate_cloud_city_assault_map(CFG, seed=7, cloud_city_size=2, citadel_level=0)
    for s in amap.structures:
        for cell in s.cells:
            assert amap.structure_at(*cell) is s


# --- line of sight through one's own body ------------------------------------


def _battle_with(amap: ga.AssaultMap, op: AssaultOperation) -> ga._Battle:
    return ga._battle_for(op, amap, CFG, Random(1))


def _clear_strip(amap: ga.AssaultMap, battle: ga._Battle, length: int = 10) -> tuple[int, int]:
    """A run of open ground with nothing on it and nothing in it that blocks sight.

    Terrain matters as much as structures here: `_line_of_sight` also stops on any
    feature with `blocks_los`, and a strip picked only for being structure-free lands
    in forest often enough that the test fails for a reason it is not about.
    """
    for y in range(3, amap.height - 3):
        for x in range(3, amap.width - length - 3):
            cells = [(x + i, y) for i in range(-2, length)]
            if any(c in battle.struct_at for c in cells):
                continue
            terrain = (GW.terrain.get(amap.feature[cy][cx]) for cx, cy in cells)
            if any(t is not None and t.blocks_los for t in terrain):
                continue
            return x, y
    raise AssertionError("no clear strip on this map")


def _slab(battle: ga._Battle, sid: int, x: int, y: int, w: int) -> ga._Structure:
    slab = ga._Structure(id=sid, kind="building_military", x=x, y=y, city_id=1,
                         hp=110, hp_max=110, w=w, h=1)
    battle.structures[slab.id] = slab
    for cell in slab.cells:
        battle.struct_at[cell] = slab.id
    return slab


def test_line_of_sight_is_not_blocked_by_the_targets_own_footprint() -> None:
    """The sharpest break a footprint causes, and the reason the exemption is by id.

    Endpoint-only exclusion was correct while a structure was one cell — the target's
    only cell *was* the endpoint. Give it a body and a shot at its far face crosses its
    near face, which is neither endpoint, so the target blocks the shot at itself and
    becomes unkillable from that side.
    """
    amap = _map(cities=1)
    op = _op(amap)
    battle = _battle_with(amap, op)

    # A 4x1 slab lying east-west, with clear ground either side of it.
    x0, y = _clear_strip(amap, battle)
    slab = _slab(battle, 90_001, x0, y, 4)

    shooter = (x0 - 2, y)
    near_face, far_face = (x0, y), (x0 + 3, y)
    assert ga._line_of_sight(battle, *shooter, *near_face)
    assert ga._line_of_sight(battle, *shooter, *far_face), (
        "the slab's near cells must not block a shot at the slab itself")

    # ...but it still blocks something standing behind it.
    behind = (x0 + 5, y)
    assert not ga._line_of_sight(battle, *shooter, *behind)

    # ...and once it is rubble it blocks nothing at all.
    slab.hp = 0
    assert ga._line_of_sight(battle, *shooter, *behind)


def test_a_trooper_can_shoot_out_of_the_rubble_it_stands_in() -> None:
    """The same exemption from the other end: the *shooter's* cell is exempt too."""
    amap = _map(cities=1)
    op = _op(amap)
    battle = _battle_with(amap, op)
    x0, y = _clear_strip(amap, battle)
    _slab(battle, 90_002, x0, y, 4)
    # Standing on the slab's west cell, shooting east past its own remaining body.
    assert ga._line_of_sight(battle, x0, y, x0 + 5, y)


# --- the rubble round trip ---------------------------------------------------


def test_a_levelled_structure_is_recognised_from_any_of_its_cells() -> None:
    """`persistent_structure_hp` reads world rubble back onto a fresh map.

    Rubble is stored per cell because that is the granularity a survey walks, but a
    structure has one HP pool — so any one cell being rubble means the whole thing is
    down. Anchoring the lookup would resurrect a razed building whose anchor happened
    not to be the cell recorded.
    """
    amap = _map()
    target = next(s for s in amap.structures if s.kind == "wall")
    for cell in target.cells:
        assert ga.persistent_structure_hp(amap, {cell: target.kind}) == {target.id: 0}
    assert ga.persistent_structure_hp(amap, {}) == {}


def test_settlement_records_rubble_at_every_cell_of_a_levelled_structure() -> None:
    """The write side of the same round trip (`settlement._destroyed`)."""
    from edge.core.groundwar import settlement as gs

    amap = _map()
    target = next(s for s in amap.structures if s.kind == "building_civilian")
    op = _op(amap)
    op = replace(op, structure_hp={target.id: 0})
    destroyed = gs._destroyed(op, amap)
    assert set(target.cells) <= set(destroyed)
    assert all(destroyed[cell] == target.kind for cell in target.cells)
    # ...and it round-trips back to the same structure.
    assert ga.persistent_structure_hp(amap, destroyed) == {target.id: 0}
