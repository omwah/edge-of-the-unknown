"""WP-PR2-15 — Cloud Cities on gas giants (playtest PT-54).

DESIGN §4.2: a jovian has no ground. It holds no stores and no colonists until a staging
area is built — paid from the ship's *hold*, since there are nowhere any stores to draw on —
and once built, the city berths `size × cloud_city_berths` people. These lock the capability
seam down at the config, core-predicate, generation, reducer, and projection layers.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.config import load_default_config
from edge.core.economy import EconomyError
from edge.core.enums import Commodity
from edge.core.events import CloudCityBuilt
from edge.core.models import (
    UNOWNED,
    Game,
    Ownership,
    Planet,
    Player,
    Sector,
    Ship,
    UniverseState,
)
from edge.core.planets import (
    cloud_city_blocker,
    cloud_city_next_cost,
    colonist_blocker,
    colonist_capacity,
    is_cloud_city_world,
    produce,
    retype_planet,
    store_blocker,
)
from edge.core.rules import (
    BuildStagingArea,
    Colonize,
    SettleColonists,
    TransferCargo,
    apply_result,
    reduce,
)
from edge.server.session import planet_view

CFG = load_default_config()
STAGE = CFG.planets.cloud_city_stage_cost
BERTHS = CFG.planets.cloud_city_berths


def _state(*, size: int = 0, equipment: int = 500, colonists: int = 0) -> UniverseState:
    """A player in orbit over a gas giant, with equipment and people aboard."""
    game = Game(id=1, seed=1, config_version=CFG.config_version,
                created_at="1970-01-01T00:00:00Z", core_governing_alliance_id=1)
    state = UniverseState.new(game)
    state.sectors[1] = Sector(id=1, region_id=1, warps_out=(), distance_band="Frontier")
    state.rebuild_adjacency()
    state.planets[1] = Planet(
        id=1, sector_id=1, name="Bespin", planet_type="jovian", cloud_city_size=size,
        owner=Ownership("player", 1) if size else UNOWNED,
    )
    state.ships[1] = Ship(id=1, type_id="trailblazer", name="T", owner_player_id=1,
                          sector_id=1, holds_total=500, hull_current=200, hull_max=200,
                          shields=50, warp_speed=3, combat_speed=3, turns_per_warp=1,
                          cargo={Commodity.EQUIPMENT: equipment}, colonists=colonists,
                          colonist_capacity=100_000)
    state.players[1] = Player(id=1, name="T", ship_id=1, latinum=5000, turns_remaining=100)
    return state


# --- the capability seam ------------------------------------------------------


def test_a_gas_giant_holds_nobody_and_nothing_until_it_is_staged() -> None:
    bare = _state().planets[1]
    assert is_cloud_city_world("jovian", CFG) and not is_cloud_city_world("barren", CFG)
    assert colonist_capacity(bare, CFG) == 0
    assert "staging area" in colonist_blocker(bare, CFG)
    assert "staging area" in store_blocker(bare, CFG)


def test_capacity_scales_with_city_size() -> None:
    for size in (1, 2, 3):
        planet = _state(size=size).planets[1]
        assert colonist_capacity(planet, CFG) == size * BERTHS
        assert colonist_blocker(planet, CFG) == "" and store_blocker(planet, CFG) == ""


def test_a_ground_world_is_unchanged_by_the_seam() -> None:
    terra = Planet(id=2, sector_id=1, name="Terra", planet_type="terrestrial_warm",
                   habitability_cap=100_000)
    assert colonist_capacity(terra, CFG) == 100_000
    assert store_blocker(terra, CFG) == "" and colonist_blocker(terra, CFG) == ""


def test_next_size_costs_more_than_the_last_and_stops_at_the_ceiling() -> None:
    assert cloud_city_next_cost(_state().planets[1], CFG) == STAGE
    assert cloud_city_next_cost(_state(size=2).planets[1], CFG) == STAGE * 3
    maxed = _state(size=CFG.planets.cloud_city_max_size).planets[1]
    assert cloud_city_next_cost(maxed, CFG) == 0
    assert "built out" in cloud_city_blocker(maxed, 10_000, True, CFG)


def test_the_first_city_fits_one_hold_load_of_the_starting_hull() -> None:
    """The staging cost is a *one-haul* cost — the bootstrap must be reachable (§4.2)."""
    assert STAGE <= CFG.ship.holds_total
    assert STAGE <= CFG.planets.asteroid_mining * 1  # one belt haul also does it


# --- the build ----------------------------------------------------------------


def test_building_consumes_the_haul_claims_the_world_and_opens_stores() -> None:
    state = _state()
    result = reduce(state, 1, BuildStagingArea(1), CFG)
    apply_result(state, result)
    planet, ship = state.planets[1], state.ships[1]
    assert result.events == (CloudCityBuilt(1, 1, 1, STAGE),)
    assert planet.cloud_city_size == 1
    assert planet.owner == Ownership("player", 1)  # the first build claims it
    assert ship.cargo[Commodity.EQUIPMENT] == 500 - STAGE
    assert planet.allocation  # an even production split, as Colonize gives
    assert colonist_capacity(planet, CFG) == BERTHS
    # Stores work now — the gate is gone.
    apply_result(state, reduce(state, 1, TransferCargo(1, Commodity.EQUIPMENT, 30, True), CFG))
    assert state.planets[1].stores[Commodity.EQUIPMENT] == 30


def test_growing_the_city_costs_more_and_berths_more() -> None:
    state = _state(size=1)
    apply_result(state, reduce(state, 1, BuildStagingArea(1), CFG))
    assert state.planets[1].cloud_city_size == 2
    assert state.ships[1].cargo[Commodity.EQUIPMENT] == 500 - STAGE * 2
    assert colonist_capacity(state.planets[1], CFG) == 2 * BERTHS


def test_building_without_the_cargo_is_refused_with_the_projected_reason() -> None:
    state = _state(equipment=STAGE - 1)
    with pytest.raises(EconomyError, match=f"need {STAGE} equipment aboard"):
        reduce(state, 1, BuildStagingArea(1), CFG)
    view = planet_view(state, 1, 1, CFG)
    assert view.cloud_city_blocker == f"need {STAGE} equipment aboard to build (have {STAGE - 1})"


def test_a_rival_world_cannot_be_built_on_and_a_ground_world_carries_no_city() -> None:
    state = _state()
    state.planets[1] = replace(state.planets[1], owner=Ownership("alliance", 2))
    with pytest.raises(EconomyError, match="that world is claimed"):
        reduce(state, 1, BuildStagingArea(1), CFG)
    state.planets[1] = replace(state.planets[1], planet_type="barren", owner=Ownership("none", None))
    with pytest.raises(EconomyError, match="cannot carry a cloud city"):
        reduce(state, 1, BuildStagingArea(1), CFG)


def test_a_built_out_city_cannot_grow() -> None:
    state = _state(size=CFG.planets.cloud_city_max_size, equipment=100_000)
    with pytest.raises(EconomyError, match="built out"):
        reduce(state, 1, BuildStagingArea(1), CFG)


# --- what the gate refuses before the build ------------------------------------


def test_stores_and_colonists_are_refused_on_an_unstaged_gas_giant() -> None:
    state = _state(colonists=50)
    with pytest.raises(EconomyError, match="no ground"):
        reduce(state, 1, Colonize(1, 50), CFG)
    # Owned but (impossibly) unstaged: both remaining doors are shut too.
    state.planets[1] = replace(state.planets[1], owner=Ownership("player", 1))
    with pytest.raises(EconomyError, match="no ground"):
        reduce(state, 1, SettleColonists(1, 50), CFG)
    with pytest.raises(EconomyError, match="nothing can be stored"):
        reduce(state, 1, TransferCargo(1, Commodity.EQUIPMENT, 10, True), CFG)


def test_settling_fills_the_city_and_then_says_it_is_full() -> None:
    state = _state(size=1, colonists=BERTHS + 100)
    apply_result(state, reduce(state, 1, SettleColonists(1, BERTHS + 100), CFG))
    assert state.planets[1].colonists == BERTHS  # clamped to the city's berths
    assert state.ships[1].colonists == 100       # the rest stayed aboard
    with pytest.raises(EconomyError, match="build it larger"):
        reduce(state, 1, SettleColonists(1, 100), CFG)


# --- production ---------------------------------------------------------------


def test_the_scoop_runs_with_or_without_a_city_and_people_produce_on_top() -> None:
    bare = replace(_state().planets[1], owner=Ownership("player", 1))
    assert produce(bare, CFG).stores[Commodity.FUEL_ORE] == CFG.planets.jovian_scoop

    peopled = replace(_state(size=2).planets[1], colonists=4_000,
                      allocation={Commodity.FUEL_ORE: 1.0},
                      stores={Commodity.ORGANICS: 10_000})
    after = produce(peopled, CFG)
    assert after.stores[Commodity.FUEL_ORE] > CFG.planets.jovian_scoop  # scoop + colonist output
    assert after.colonists > peopled.colonists  # fed (imported organics), so it grows


def test_a_city_starves_without_imported_food() -> None:
    """The jovian yield profile has no Organics — a sky city eats what it is brought (§4.2)."""
    hungry = replace(_state(size=1).planets[1], colonists=4_000,
                     allocation={Commodity.FUEL_ORE: 1.0})
    assert produce(hungry, CFG).colonists < 4_000


# --- generation, genesis, and the projection ----------------------------------


def test_an_alliance_gas_giant_is_generated_with_a_city() -> None:
    from edge.bigbang.generator import generate

    state = generate(CFG, 4)
    jovians = [p for p in state.planets.values() if p.planet_type == "jovian"]
    assert jovians, "seed 4 generated no gas giants to check"
    for planet in jovians:
        expected = CFG.planets.cloud_city_npc_size if planet.owner.is_owned else 0
        assert planet.cloud_city_size == expected


def test_genesis_reforming_a_gas_giant_clears_its_city() -> None:
    reformed = retype_planet(_state(size=3).planets[1], "terrestrial_warm", CFG)
    assert reformed.cloud_city_size == 0
    assert colonist_capacity(reformed, CFG) == reformed.habitability_cap


def test_the_orbit_projection_carries_the_city_and_its_affordance() -> None:
    unstaged = planet_view(_state(), 1, 1, CFG)
    assert unstaged.cloud_city and unstaged.cloud_city_size == 0
    assert not unstaged.colonizable and unstaged.habitability_cap == 0
    assert unstaged.cloud_city_next_cost == STAGE and unstaged.cloud_city_blocker == ""
    assert unstaged.ship_equipment == 500

    state = _state(size=2)
    staged = planet_view(state, 1, 1, CFG)
    assert staged.colonizable and staged.habitability_cap == 2 * BERTHS
    assert staged.cloud_city_size == 2
    assert staged.cloud_city_max_size == CFG.planets.cloud_city_max_size


def test_the_sector_scene_sees_the_city() -> None:
    """The scene paints the floating city from the same fact the orbit view reads."""
    from edge.server.session import game_view

    from helpers import generate_with_player

    state = generate_with_player(CFG, 4)
    jovian = next(p for p in state.planets.values()
                  if p.planet_type == "jovian" and p.owner.is_owned)
    player = state.players[1]
    state.ships[player.ship_id] = replace(state.ships[player.ship_id], sector_id=jovian.sector_id)
    state.players[1] = replace(player, sector_id=jovian.sector_id)
    scene = game_view(state, 1, CFG).sector
    city = next(p for p in scene.planets if p.planet_id == jovian.id)
    assert city.cloud_city_size == CFG.planets.cloud_city_npc_size
