"""WP-PR06 — asteroid belts are spatial features, not colony worlds (playtest PT-30).

DESIGN §4.2: a belt may be scanned/mined and may hold open-space finds, but it cannot be
descended onto, colonized, given colony stores/citadels, banked, invaded, or terraformed by
Genesis. These lock down the capability model at the config, core-predicate, generation, and
reducer seams, plus the fog-safe projection the TUI renders from.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.config import load_default_config
from edge.core.economy import EconomyError
from edge.core.enums import Commodity, DiscoveryKind, PayloadKind, RarityTier
from edge.core.models import (
    Discovery,
    DiscoveryPayload,
    Game,
    Ownership,
    Planet,
    Player,
    Sector,
    Ship,
    UniverseState,
)
from edge.core.events import BeltMined
from edge.core.movement import MovementError
from edge.core.planets import (
    belt_mining_yield,
    is_colonizable,
    is_extractable,
    is_landable,
    normalize_belt,
)
from edge.core.rules import Descend, DeployGenesis, Explore, MineBelt, apply_result, reduce
from edge.server.session import planet_view

CFG = load_default_config()


# --- capability predicates ----------------------------------------------------


def test_belt_capabilities() -> None:
    assert not is_landable("asteroid_belt", CFG)
    assert not is_colonizable("asteroid_belt", CFG)
    assert is_extractable("asteroid_belt", CFG)  # equipment mined in orbit


def test_terrestrial_and_barren_stay_landable() -> None:
    assert is_landable("terrestrial_warm", CFG)
    assert is_landable("barren", CFG)  # a rocky dead world still has a surface
    assert is_landable("jovian", CFG)  # unchanged by WP-PR06
    assert not is_extractable("barren", CFG)


def test_belt_removed_from_genesis_eligibility() -> None:
    assert CFG.genesis is not None
    assert "asteroid_belt" not in CFG.genesis.eligible_types


# --- normalize_belt scrub -----------------------------------------------------


def _dirty_belt() -> Planet:
    return Planet(
        id=1, sector_id=1, name="Rubble", planet_type="asteroid_belt",
        owner=Ownership("alliance", 4), colonists=500, habitability_cap=0,
        allocation={Commodity.EQUIPMENT: 1.0}, stores={Commodity.EQUIPMENT: 9000},
        citadel_level=2, treasury=1234, fighters=40, starbase_id=7,
    )


def test_normalize_belt_scrubs_colony_state_and_is_idempotent() -> None:
    clean = normalize_belt(_dirty_belt(), CFG)
    assert not clean.owner.is_owned and clean.colonists == 0
    assert not clean.stores and not clean.allocation
    assert clean.citadel_level == 0 and clean.treasury == 0 and clean.fighters == 0
    assert clean.starbase_id is None
    assert normalize_belt(clean, CFG) == clean  # idempotent — legacy re-read converges


def test_normalize_leaves_landable_worlds_untouched() -> None:
    colony = Planet(id=2, sector_id=1, name="Eden", planet_type="terrestrial_warm",
                    owner=Ownership("player", 1), colonists=1000)
    assert normalize_belt(colony, CFG) is colony


# --- reducer rejections -------------------------------------------------------


def _state_with_belt() -> UniverseState:
    game = Game(id=1, seed=1, config_version=CFG.config_version,
                created_at="1970-01-01T00:00:00Z", core_governing_alliance_id=1)
    state = UniverseState.new(game)
    state.sectors[1] = Sector(id=1, region_id=1, warps_out=(), distance_band="Frontier")
    state.rebuild_adjacency()
    state.planets[1] = Planet(id=1, sector_id=1, name="Rubble", planet_type="asteroid_belt")
    state.ships[1] = Ship(id=1, type_id="trailblazer", name="T", owner_player_id=1,
                          sector_id=1, holds_total=20, hull_current=200, hull_max=200,
                          shields=50, warp_speed=3, combat_speed=3, turns_per_warp=1)
    state.players[1] = Player(id=1, name="T", ship_id=1, latinum=5000, turns_remaining=100)
    return state


def test_descend_rejected_on_belt() -> None:
    state = _state_with_belt()
    with pytest.raises(EconomyError, match="no surface"):
        reduce(state, 1, Descend(planet_id=1), CFG)


def test_explore_rejected_on_belt() -> None:
    state = _state_with_belt()
    with pytest.raises(EconomyError, match="no surface"):
        reduce(state, 1, Explore(planet_id=1), CFG)


def test_genesis_rejected_on_belt() -> None:
    state = _state_with_belt()
    genesis = CFG.genesis
    assert genesis is not None
    ship = state.ships[1]
    state.ships[1] = replace(ship, devices={genesis.device_id: 1})  # torpedo aboard
    with pytest.raises(EconomyError, match="cannot be re-formed by genesis"):
        reduce(state, 1, DeployGenesis(planet_id=1), CFG)


def test_descend_still_works_on_a_terrestrial() -> None:
    state = _state_with_belt()
    state.planets[1] = replace(state.planets[1], planet_type="terrestrial_warm")
    result = reduce(state, 1, Descend(planet_id=1), CFG)  # no raise
    apply_result(state, result)
    assert state.players[1].turns_remaining < 100  # a turn was spent landing


# --- projection capabilities --------------------------------------------------


def test_planet_view_carries_belt_capabilities() -> None:
    state = _state_with_belt()
    view = planet_view(state, 1, 1, CFG)
    assert not view.landable and not view.colonizable and view.extractable
    assert not view.claimable and not view.genesis_eligible
    assert view.mine_yield == CFG.planets.asteroid_mining  # the hand-mining haul is projected


# --- player belt mining (PT-30) ----------------------------------------------


def test_mine_belt_fills_holds_and_spends_a_turn() -> None:
    state = _state_with_belt()
    before = state.players[1].turns_remaining
    result = reduce(state, 1, MineBelt(planet_id=1), CFG)
    apply_result(state, result)
    ship = state.ships[1]
    # holds_total is 20 < the 50-unit yield, so the haul is clamped to free space.
    assert ship.cargo.get(Commodity.EQUIPMENT, 0) == ship.holds_total == 20
    assert state.players[1].turns_remaining == before - CFG.planets.mining_turn_cost
    mined = next(e for e in result.events if isinstance(e, BeltMined))
    assert mined.commodity == "equipment" and mined.amount == 20


def test_mine_belt_clamps_to_free_holds() -> None:
    state = _state_with_belt()
    # Pre-fill 15 of 20 holds → only 5 free, so mining takes exactly 5 more.
    state.ships[1] = replace(state.ships[1], cargo={Commodity.ORGANICS: 15})
    apply_result(state, reduce(state, 1, MineBelt(planet_id=1), CFG))
    ship = state.ships[1]
    assert ship.cargo.get(Commodity.EQUIPMENT, 0) == 5 and ship.holds_free == 0


def test_mine_belt_rejects_full_holds() -> None:
    state = _state_with_belt()
    state.ships[1] = replace(state.ships[1], cargo={Commodity.ORGANICS: 20})  # holds full
    with pytest.raises(EconomyError, match="holds are full"):
        reduce(state, 1, MineBelt(planet_id=1), CFG)


def test_mine_belt_rejects_out_of_turns() -> None:
    state = _state_with_belt()
    state.players[1] = replace(state.players[1], turns_remaining=0)
    with pytest.raises(MovementError, match="out of turns"):
        reduce(state, 1, MineBelt(planet_id=1), CFG)


def test_mine_rejected_on_non_belt() -> None:
    state = _state_with_belt()
    state.planets[1] = replace(state.planets[1], planet_type="terrestrial_warm")
    assert belt_mining_yield("terrestrial_warm", CFG) is None
    with pytest.raises(EconomyError, match="cannot be mined"):
        reduce(state, 1, MineBelt(planet_id=1), CFG)


def test_belt_has_open_space_finds_but_no_surface_sites() -> None:
    """A belt still hosts spatial finds (its sector's discoveries), just not landable sites."""
    state = _state_with_belt()
    state.discoveries[1] = Discovery(
        id=1, kind=DiscoveryKind.WRECK, rarity_tier=RarityTier.RARE,
        sector_id=1, payload=DiscoveryPayload(kind=PayloadKind.LATINUM, latinum=100))
    # A space find (planet_id is None) is unaffected by belt landability.
    assert state.discoveries[1].planet_id is None
