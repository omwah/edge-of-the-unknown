"""GW-WP19 — one world, one ground: shared survey/assault layout and positional rubble.

The gap this closes (recorded as a known gap in GW-WP12-FU1): a world had two unrelated
grounds. Surveying a world you had just conquered showed different terrain in different
places, and a repeat assault fought a freshly rolled battlefield, because
`generate_survey` and `generate_assault_map` seeded their own noise and scattered their
own towns/cities. `Planet.ground_damage` was a per-*kind* counter for exactly that reason.

The crown-jewel assertions here are the two that could not be written before:
`test_survey_and_assault_of_one_world_share_terrain_and_places` and
`test_surveying_a_conquered_world_shows_the_assaults_rubble`.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.config import load_default_config
from edge.core.enums import Commodity
from edge.core.groundwar import assault as gw_assault
from edge.core.groundwar import settlement as gw_settlement
from edge.core.groundwar import survey as gw_survey
from edge.core.groundwar import world as gw_world
from edge.core.groundwar.models import AssaultOperation, AssaultTrooper
from edge.core.dto import SurveyExpeditionDTO
from edge.core.models import (
    AlienSpecies,
    Game,
    GroundRubble,
    Ownership,
    Planet,
    Player,
    Sector,
    Ship,
    UniverseState,
)
from edge.core.rules import BeginSurvey, ExtractGroundOperation, apply_result, reduce
from edge.server import session

CFG = load_default_config()
GW = CFG.groundwar
assert GW is not None


def _planet(**kw: object) -> Planet:
    base: dict[str, object] = dict(
        id=1, sector_id=1, name="Haven", planet_type="terrestrial_warm",
        population={"vesk": 4_000}, habitability_cap=40_000,
        stores={Commodity.FUEL_ORE: 80}, citadel_level=2, gun_integrity=0,
        garrison_infantry=8, garrison_armor=2,
    )
    base.update(kw)
    return Planet(**base)  # type: ignore[arg-type]


def _state(planet: Planet) -> UniverseState:
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t"))
    state.sectors = {1: Sector(1, 1, (), "Frontier")}
    state.rebuild_adjacency()
    state.planets = {planet.id: planet}
    state.ships = {1: Ship(id=1, type_id="trailblazer", name="S.S.", owner_player_id=1,
                           sector_id=1, holds_total=60, turns_per_warp=1)}
    state.players = {1: Player(id=1, name="you", ship_id=1, latinum=10_000,
                               turns_remaining=250)}
    return state


def _vesk() -> AlienSpecies:
    sc = next(species for species in CFG.roster.species if species.id == "vesk")
    return AlienSpecies(
        id=7, roster_id="vesk", name=sc.name, archetype_id=sc.archetype_id, sector_id=1,
        home_band="Frontier", tech_level=sc.tech_level,
        base_disposition=sc.disposition_center, disposition_center=sc.disposition_center,
        disposition_variance=0.0,
    )


def _places(planet: Planet) -> int:
    return gw_world.place_count(planet, CFG, distance_band="Frontier")


# --- the shared identity -------------------------------------------------------


def test_world_ground_seed_is_derived_stable_and_per_world() -> None:
    """No hashed field: the identity comes off `(Game.seed, planet_id)` (GW-WP19)."""
    assert gw_world.world_ground_seed(1986, 7) == gw_world.world_ground_seed(1986, 7)
    assert gw_world.world_ground_seed(1986, 7) != gw_world.world_ground_seed(1986, 8)
    assert gw_world.world_ground_seed(1986, 7) != gw_world.world_ground_seed(1987, 7)


def test_generate_world_ground_is_deterministic() -> None:
    a = gw_world.generate_world_ground(CFG, seed=99, planet_type="terrestrial_cool", places=3)
    b = gw_world.generate_world_ground(CFG, seed=99, planet_type="terrestrial_cool", places=3)
    assert a == b
    assert len(a.stamps) == 3
    assert [stamp.place.capital for stamp in a.stamps] == [False, False, True]


def test_buildings_are_whole_footprints_with_one_kind_each() -> None:
    """GW-WP27: a building is one rolled object, not a strip of independently-kinded cells.

    The pre-WP27 loop rolled military/civilian per *cell*, so a two-wide block could —
    and, over enough seeds, did — come out half depot, half housing. Rolling once per
    building and placing its whole footprint atomically is the fix; this asserts both
    halves of it hold across a seed sweep: every footprint is internally one kind, no
    two footprints share a cell, and every footprint sits entirely inside its place
    (never straddling the wall or a reserved emplacement slot).
    """
    for seed in range(1, 12):
        ground = gw_world.generate_world_ground(
            CFG, seed=seed, planet_type="terrestrial_warm", places=3)
        for stamp in ground.stamps:
            place = stamp.place
            seen: set[tuple[int, int]] = set()
            sizes_seen: set[tuple[int, int]] = set()
            for x, y, w, h in stamp.buildings:
                cells = {(x + dx, y + dy) for dy in range(h) for dx in range(w)}
                assert cells.isdisjoint(seen), f"seed {seed}: overlapping building footprints"
                seen |= cells
                assert cells.isdisjoint(set(stamp.reserved)), (
                    f"seed {seed}: building overlaps a reserved emplacement slot")
                assert all(place.x0 < cx < place.x1 and place.y0 < cy < place.y1
                          for cx, cy in cells), f"seed {seed}: building crosses the wall line"
                sizes_seen.add((w, h))
            # Each footprint is one atomic (x, y, w, h) tuple in `military` XOR `civilian`
            # — there is no per-cell kind to disagree with itself, so "one kind each" is
            # true by construction. What's worth checking is that sizes actually vary
            # (the whole point of D35), not just 2x2 everywhere.
            if len(stamp.buildings) >= 4:
                assert len(sizes_seen) > 1, f"seed {seed}: every building came out the same size"


def test_survey_and_assault_of_one_world_share_terrain_and_places() -> None:
    """The whole point of the WP: one world, one ground.

    Same seed, same planet type, same place count → the identical biome grid and the
    identical town/city footprints, names, and gate positions.
    """
    seed = gw_world.world_ground_seed(1986, 1)
    planet = _planet()
    places = _places(planet)
    smap = gw_survey.generate_survey(
        CFG, seed=seed, planet_type=planet.planet_type, inhabited=True, sites=(),
        places=places)
    amap = gw_assault.generate_assault_map(
        CFG, seed=seed, planet_type=planet.planet_type, cities=places,
        citadel_level=planet.citadel_level)

    assert (smap.width, smap.height) == (amap.width, amap.height)
    # Terrain matches everywhere the two modes have not built on top of it, and both
    # pave their footprints identically, so the grids are equal outright.
    assert smap.feature == amap.feature
    assert [(t.id, t.name, t.x0, t.y0, t.x1, t.y1) for t in smap.settlements] == \
           [(c.id, c.name, c.x0, c.y0, c.x1, c.y1) for c in amap.cities]
    # Every gate the surveyor can walk through is a `gate` structure on the battlefield.
    assert smap.gates == frozenset(
        (s.x, s.y) for s in amap.structures if s.kind == "gate")
    # Every masonry cell a surveyor cannot cross carries a structure in the assault —
    # every cell of every footprint since GW-WP27, not just each structure's anchor.
    struct_at = {cell for s in amap.structures for cell in s.cells}
    assert smap.blocked <= struct_at


def test_an_uninhabited_world_keeps_its_terrain_but_shows_no_towns() -> None:
    """Places belong to the world's layout; *living* settlements belong to its people."""
    seed = 4242
    peopled = gw_survey.generate_survey(
        CFG, seed=seed, planet_type="barren", inhabited=True, sites=(), places=2)
    empty = gw_survey.generate_survey(
        CFG, seed=seed, planet_type="barren", inhabited=False, sites=(), places=2)
    assert empty.settlements == () and empty.blocked == frozenset()
    assert len(peopled.settlements) == 2
    # Terrain outside the paved footprints is the same world either way. (Bounds are
    # spelled out because `SurveySettlement.inside` is strict — it excludes the wall ring,
    # which *is* paved.)
    outside = [
        (x, y) for y in range(empty.height) for x in range(empty.width)
        if not any(town.x0 <= x <= town.x1 and town.y0 <= y <= town.y1
                   for town in peopled.settlements)
    ]
    assert all(empty.feature[y][x] == peopled.feature[y][x] for x, y in outside)


def test_place_count_survives_conquest_so_the_layout_cannot_re_roll() -> None:
    """`place_count` reads only stable world facts (GW-WP19).

    Ownership and citadel level both change on conquest; if either fed the count, taking
    a world would silently move its towns. They shift the surrender threshold instead.
    """
    planet = _planet()
    before = _places(planet)
    conquered = replace(
        planet, owner=Ownership("player", 1), citadel_level=0, garrison_infantry=0,
        population={})  # even losing every inhabitant must not move the towns
    assert _places(conquered) == before

    # Same citadel level, so only the ownership multiplier differs: a bloc holding
    # holds out to a *lower* Resolve than an unaligned world of identical build.
    hard = gw_assault.derive_difficulty(
        replace(planet, owner=Ownership("alliance", 3)), CFG,
        distance_band="Frontier", species=None)
    soft = gw_assault.derive_difficulty(
        replace(planet, owner=Ownership("none")), CFG,
        distance_band="Frontier", species=None)
    assert hard.citadel_level == soft.citadel_level
    assert hard.surrender_threshold < soft.surrender_threshold


def test_expedition_and_battlefield_must_share_one_grid_size() -> None:
    from pydantic import ValidationError

    from edge.core.config import GroundwarConfig

    assert GW is not None
    data = GW.model_dump()
    data["expedition"]["width"] = GW.battlefield.width + 10
    with pytest.raises(ValidationError, match="must share one grid size"):
        GroundwarConfig.model_validate(data)


# --- positional rubble ---------------------------------------------------------


def _dropped_operation(planet: Planet, *, structure_hp: dict[int, int] | None = None,
                       outcome: str = "retrieval") -> AssaultOperation:
    return AssaultOperation(
        operation_id=17, planet_id=planet.id, sector_id=planet.sector_id,
        planet_type=planet.planet_type, seed=42, started_day=3, resolve=20,
        retrieval_turn=20,
        world_seed=gw_world.world_ground_seed(1986, planet.id),
        cities=_places(planet), citadel_level=planet.citadel_level,
        surrender_threshold=GW.resolve.surrender_threshold if GW else 25,
        reserved_infantry=8, reserved_armor=2, outcome=outcome, dropped=True,
        platoon=(AssaultTrooper(id=100, suit_id="marauder", name="T", x=1, y=1, hp=80,
                                missiles=0, jump_charges=0),),
        structure_hp=structure_hp or {}, initial_strength=1,
    )


def _ship() -> Ship:
    return Ship(id=1, type_id="trailblazer", name="S.S.", owner_player_id=1, sector_id=1,
                holds_total=60, passenger_capacity=20, recruits=1, suits={"marauder": 1})


def test_settlement_records_destroyed_structures_by_position() -> None:
    planet = _planet()
    op = _dropped_operation(planet)
    amap = gw_assault.assault_map_for_state(op, CFG)
    wall = next(s for s in amap.structures if s.kind == "wall")
    settled = gw_settlement.settle_assault(
        planet, _ship(), replace(op, structure_hp={wall.id: 0}),
        player_id=1, corp_id=None, day=5, config=CFG)
    assert GroundRubble(wall.x, wall.y, "wall") in settled.planet.ground_rubble
    assert gw_world.rubble_counts(settled.planet)["wall"] == 1


def test_a_repeat_assault_reopens_the_same_breach() -> None:
    """Positional damage projects exactly (G12-adjacent): the wall that fell is the
    wall that starts at zero, not "the lowest stable id of that kind"."""
    planet = _planet()
    op = _dropped_operation(planet)
    amap = gw_assault.assault_map_for_state(op, CFG)
    wall = next(s for s in amap.structures if s.kind == "wall")
    battered = replace(planet, ground_rubble=(GroundRubble(wall.x, wall.y, "wall"),))

    again = gw_assault.assault_map_for_state(op, CFG)
    assert again.feature == amap.feature  # the same battlefield, not a fresh roll
    hp = gw_assault.persistent_structure_hp(again, gw_world.rubble_at(battered))
    assert hp == {wall.id: 0}


def test_surveying_a_conquered_world_shows_the_assaults_rubble() -> None:
    """The user-visible outcome: walk a world you took and the battle damage is there —
    on the cell it happened, and walkable, because a breach is a way through."""
    planet = _planet()
    seed = gw_world.world_ground_seed(1986, planet.id)
    places = _places(planet)
    amap = gw_assault.generate_assault_map(
        CFG, seed=seed, planet_type=planet.planet_type, cities=places,
        citadel_level=planet.citadel_level)
    wall = next(s for s in amap.structures if s.kind == "wall")

    intact = gw_survey.generate_survey(
        CFG, seed=seed, planet_type=planet.planet_type, inhabited=True, sites=(),
        places=places)
    assert (wall.x, wall.y) in intact.blocked

    ruined = gw_survey.generate_survey(
        CFG, seed=seed, planet_type=planet.planet_type, inhabited=True, sites=(),
        places=places, rubble={(wall.x, wall.y): "wall"})
    assert (wall.x, wall.y) not in ruined.blocked
    assert ruined.rubble[(wall.x, wall.y)] == "wall"
    assert gw_survey._cell_cost(ruined, CFG, wall.x, wall.y) > 0


def test_taking_a_world_then_surveying_it_shows_the_battle_through_the_reducers() -> None:
    """The user's scenario end to end, through commands rather than generators.

    Assault an unaligned inhabited world to surrender → it becomes a protectorate you
    control → `BeginSurvey` on that same world → the projected viewport carries the
    rubble of the structures the assault levelled, on their own cells.
    """
    planet = _planet(owner=Ownership("none"))
    state = _state(planet)
    state.species = {7: _vesk()}

    # Level one wall and one civilian block, then surrender the world.
    op = _dropped_operation(planet, outcome="surrender")
    amap = gw_assault.assault_map_for_state(op, CFG)
    wall = next(s for s in amap.structures if s.kind == "wall")
    civilian = next(s for s in amap.structures if s.kind == "building_civilian")
    state.ships[1] = _ship()
    state.players[1] = replace(
        state.players[1],
        ground_operation=replace(op, structure_hp={wall.id: 0, civilian.id: 0}),
    )
    apply_result(state, reduce(state, 1, ExtractGroundOperation(op.operation_id), CFG))

    settled = state.planets[planet.id]
    assert settled.protectorate_controller == Ownership("player", 1)
    assert settled.owner == Ownership("none")  # D2: the native polity is retained
    ruined = {(entry.x, entry.y): entry.kind for entry in settled.ground_rubble}
    # GW-WP27: a razed building leaves rubble at *every* cell of its footprint, not just
    # its anchor — one HP pool, one ruin, the whole shape of it.
    expected = {(wall.x, wall.y): "wall"}
    expected.update({cell: "building_civilian" for cell in civilian.cells})
    assert ruined == expected

    # Now walk it. The survey must be the same world, carrying that damage.
    apply_result(state, reduce(state, 1, BeginSurvey(planet.id), CFG))
    view = session.ground_operation_view(state, 1, CFG)  # full map, no crop
    assert isinstance(view, SurveyExpeditionDTO)
    cells = {(cell.x, cell.y): cell for cell in view.cells}
    assert cells[(wall.x, wall.y)].rubble == "wall"
    assert cells[(civilian.x, civilian.y)].rubble == "building_civilian"
    # A breach is a way in, not masonry: the projection must not also call it blocked.
    assert not cells[(wall.x, wall.y)].blocked
    # And the town it belonged to is on the survey map, at the assault's own footprint.
    city = next(c for c in amap.cities if c.inside(wall.x, wall.y))
    town = next(t for t in view.settlements if t.settlement_id == city.id)
    assert town.name == city.name


def test_begin_survey_snapshots_the_world_layout_not_a_player_seed() -> None:
    """Two players surveying one world get one world (the per-player `map_seed` is gone)."""
    # An uninhabited world: `Survey` for anyone, so both players can descend on it.
    planet = _planet(population={})
    state = _state(planet)
    state.players[2] = Player(id=2, name="them", ship_id=2, latinum=10_000,
                              turns_remaining=250)
    state.ships[2] = Ship(id=2, type_id="trailblazer", name="S.S. Two", owner_player_id=2,
                          sector_id=1, holds_total=60, turns_per_warp=1)
    for player_id in (1, 2):
        apply_result(state, reduce(state, player_id, BeginSurvey(planet.id), CFG))
    first = state.players[1].ground_operation
    second = state.players[2].ground_operation
    assert first is not None and second is not None
    assert first.world_seed == second.world_seed == gw_world.world_ground_seed(
        state.game.seed, planet.id)
    assert first.operation_id != second.operation_id
