"""WP40 — starbases: set-piece assault, planetary defense, repair, claim (§4.2, §10).

Covers the pure defense helpers (`core.starbases`, `core.aliens.base_owner_hostile`), the
`roll_base_defense` engagement, and the AssaultStarbase / RepairStarbase / ClaimStarbase
reducers plus razing consequences.
"""

from __future__ import annotations

import random
from dataclasses import replace

import pytest

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core import aliens, encounters
from edge.core.economy import EconomyError
from edge.core.combat import CombatError
from edge.core.engine_room import build_layouts
from edge.core.enums import Component, ComponentTier, Subsystem
from edge.core.events import StarbaseClaimed, StarbaseRazed, StarbaseRepaired
from edge.core.models import (
    EncounterFoe,
    Game,
    InstalledComponent,
    Ownership,
    Planet,
    Player,
    Sector,
    Ship,
    Starbase,
    SubsystemState,
    UniverseState,
)
from edge.core.rules import (
    AssaultStarbase,
    ClaimStarbase,
    CombatAction,
    JoinGame,
    RepairStarbase,
    Warp,
    apply_result,
    reduce,
)
from edge.core.starbases import assault_foe, component_integrity, is_operational

CFG = load_default_config()
SMALL = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(
    update={"sector_count": 400, "start_sector": 1})})


def _base_subsystems(*, operational: bool) -> dict[Subsystem, SubsystemState]:
    layouts = build_layouts(CFG.starbase.subsystems)
    if not operational:
        reactor = layouts[Subsystem.FUSION_REACTOR]
        slots = list(reactor.slots)
        slots[reactor.keystone_index] = None  # strip the keystone → derelict
        layouts[Subsystem.FUSION_REACTOR] = replace(reactor, slots=tuple(slots))
    return layouts


def _base(bid: int, sector_id: int, planet_id: int, owner: Ownership, *,
          operational: bool = True) -> Starbase:
    return Starbase(id=bid, sector_id=sector_id, planet_id=planet_id, ship_class_id="orbital_platform",
                    owner=owner, subsystems=_base_subsystems(operational=operational))


# --- pure helpers -----------------------------------------------------------


def test_is_operational_and_integrity() -> None:
    live = _base(1, 1, 1, Ownership("alliance", 2), operational=True)
    dead = _base(1, 1, 1, Ownership("none"), operational=False)
    assert is_operational(live) and not is_operational(dead)
    assert component_integrity(live) > component_integrity(dead)


def test_assault_foe_scales_with_integrity() -> None:
    live = _base(1, 1, 1, Ownership("alliance", 2), operational=True)
    dead = _base(1, 1, 1, Ownership("none"), operational=False)
    strong, weak = assault_foe(live, CFG), assault_foe(dead, CFG)
    assert strong.hull > weak.hull  # more surviving components → a tougher emplacement
    assert strong.firing_arc == "all_round" and strong.combat_speed == 0


def test_base_owner_hostile_keys_on_standing() -> None:
    state = _mini_state()
    base = _base(1, 2, 1, Ownership("alliance", 2))
    player = state.players[1]
    assert aliens.base_owner_hostile(state, base, player) is False  # neutral standing
    hostile = replace(player, alliance_standing={2: -1.0})
    assert aliens.base_owner_hostile(state, base, hostile) is True
    # An unowned base never engages.
    assert aliens.base_owner_hostile(state, _base(1, 2, 1, Ownership("none")), hostile) is False


# --- state builders ---------------------------------------------------------


def _mini_state() -> UniverseState:
    game = Game(id=1, seed=1, config_version=CFG.config_version,
                created_at="1970-01-01T00:00:00Z", core_governing_alliance_id=1)
    state = UniverseState.new(game)
    state.sectors[1] = Sector(id=1, region_id=1, warps_out=(2,), distance_band="Frontier")
    state.sectors[2] = Sector(id=2, region_id=1, warps_out=(1,), distance_band="Frontier")
    state.rebuild_adjacency()
    state.planets[1] = Planet(id=1, sector_id=2, name="P", planet_type="barren",
                              owner=Ownership("alliance", 2), starbase_id=1)
    state.ships[1] = Ship(id=1, type_id="trailblazer", name="T", owner_player_id=1,
                          sector_id=1, holds_total=20, hull_current=200, hull_max=200,
                          shields=100, warp_speed=3, combat_speed=3, turns_per_warp=1)
    state.players[1] = Player(id=1, name="T", ship_id=1, latinum=5000, turns_remaining=100)
    return state


# --- base defense engagement ------------------------------------------------


def test_roll_base_defense_engages_hostile_owner() -> None:
    state = _mini_state()
    state.starbases[1] = _base(1, 2, 1, Ownership("alliance", 2))
    state.players[1] = replace(state.players[1], alliance_standing={2: -1.0})
    enc = encounters.roll_base_defense(
        state, state.players[1], state.ships[1], 2, CFG)
    assert enc is not None and enc.starbase_id == 1 and enc.species_id == 0
    # A neutral-standing player is left alone.
    assert encounters.roll_base_defense(state, _mini_state().players[1], state.ships[1], 2, CFG) is None


def test_base_defense_fires_through_warp() -> None:
    state = _mini_state()
    state.starbases[1] = _base(1, 2, 1, Ownership("alliance", 2))
    state.players[1] = replace(state.players[1], alliance_standing={2: -1.0})
    apply_result(state, reduce(state, 1, Warp(to_sector=2), CFG))
    assert state.players[1].active_encounter is not None
    assert state.players[1].active_encounter.starbase_id == 1


# --- assault reducer + razing -----------------------------------------------


def _generated():
    state = generate(SMALL, 3)
    apply_result(state, reduce(state, 1, JoinGame(name="T"), SMALL))
    return state


def _weak_foe() -> EncounterFoe:
    return EncounterFoe(ship_class_id="orbital_platform", name="Platform", hull=1, hull_max=400,
                        shields=0, damage=1, firing_arc="all_round", combat_speed=0, defense=0)


def test_assault_rejects_derelict() -> None:
    state = _generated()
    ship = state.ships[state.players[1].ship_id]
    state.starbases[99] = _base(99, ship.sector_id, 1, Ownership("none"), operational=False)
    with pytest.raises(CombatError, match="derelict"):
        reduce(state, 1, AssaultStarbase(starbase_id=99), SMALL)


def test_assault_victory_razes_base_and_frees_world() -> None:
    state = _generated()
    ship = state.ships[state.players[1].ship_id]
    # An operational, alliance-owned base + its world, in the player's sector.
    state.planets[500] = Planet(id=500, sector_id=ship.sector_id, name="Holt",
                                planet_type="barren", owner=Ownership("alliance", 2), starbase_id=77)
    state.starbases[77] = _base(77, ship.sector_id, 500, Ownership("alliance", 2))
    # Begin the assault, then hand it a single near-dead foe so one round wins.
    apply_result(state, reduce(state, 1, AssaultStarbase(starbase_id=77), SMALL))
    enc = state.players[1].active_encounter
    assert enc is not None and enc.starbase_id == 77
    state.players[1] = replace(state.players[1], active_encounter=replace(enc, foes=(_weak_foe(),)))
    before_lat = state.players[1].latinum
    result = reduce(state, 1, CombatAction(action="fight"), SMALL)
    apply_result(state, result)
    player = state.players[1]
    assert player.active_encounter is None
    assert not is_operational(state.starbases[77])          # razed → derelict
    assert not state.starbases[77].owner.is_owned            # ownership stripped
    assert not state.planets[500].owner.is_owned             # world freed/claimable
    assert player.alliance_standing[2] == -1.0               # owner bloc soured
    # Bounty (+ any wreck salvage) is paid; experience is credited for the razing.
    assert player.latinum >= before_lat + CFG.starbase.raze_bounty
    assert player.experience >= CFG.starbase.raze_experience
    razed = next(e for e in result.events if isinstance(e, StarbaseRazed))
    assert razed.bounty == CFG.starbase.raze_bounty and razed.former_owner_ref == 2


# --- repair + claim ---------------------------------------------------------


def test_repair_refills_reactor_and_claim_takes_it() -> None:
    state = _generated()
    ship = state.ships[state.players[1].ship_id]
    base = _base(88, ship.sector_id, 1, Ownership("none"), operational=False)
    state.starbases[88] = base
    assert not is_operational(base)
    # Give the player a loose converter to refill the reactor keystone.
    ks = base.subsystems[Subsystem.FUSION_REACTOR].keystone_index
    state.ships[ship.id] = replace(ship, components={(Component.CONVERTER, ComponentTier.I): 1})
    result = reduce(state, 1, RepairStarbase(
        88, Subsystem.FUSION_REACTOR, ks, Component.CONVERTER, ComponentTier.I), SMALL)
    apply_result(state, result)
    assert is_operational(state.starbases[88])               # reactor back online
    assert state.ships[ship.id].components.get((Component.CONVERTER, ComponentTier.I), 0) == 0
    assert any(isinstance(e, StarbaseRepaired) for e in result.events)
    # Now claim the operational, unowned base.
    before = state.players[1].latinum
    result = reduce(state, 1, ClaimStarbase(starbase_id=88), SMALL)
    apply_result(state, result)
    assert state.starbases[88].owner == Ownership("player", 1)
    assert state.players[1].latinum == before - CFG.starbase.claim_cost
    assert any(isinstance(e, StarbaseClaimed) for e in result.events)


def test_claim_rejects_derelict() -> None:
    state = _generated()
    ship = state.ships[state.players[1].ship_id]
    state.starbases[88] = _base(88, ship.sector_id, 1, Ownership("none"), operational=False)
    with pytest.raises(EconomyError, match="repair"):
        reduce(state, 1, ClaimStarbase(starbase_id=88), SMALL)
