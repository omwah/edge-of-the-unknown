"""WP41 — sector fighters, mines, beacons, black-hole hazards (§10).

Covers the pure territory helpers (`core.territory`), the buy/deploy reducers, and the
movement-entry effects: mine damage, the fighter engage-or-retreat (retreat costs a
fighter), and the black-hole gravity toll.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core import territory
from edge.core.economy import EconomyError
from edge.core.enums import DiscoveryKind, PayloadKind, PortClass, RarityTier
from edge.core.events import HazardDamage, TerritoryDeployed
from edge.core.models import (
    Discovery,
    DiscoveryPayload,
    Encounter,
    Game,
    Ownership,
    Player,
    Sector,
    SectorForce,
    Ship,
    UniverseState,
)
from edge.core.rules import (
    BuyFighters,
    CombatAction,
    DeployBeacon,
    DeployFighters,
    JoinGame,
    Warp,
    apply_result,
    reduce,
)

CFG = load_default_config()
SMALL = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(
    update={"sector_count": 400, "start_sector": 1})})
TC = CFG.territory


# --- pure helpers -----------------------------------------------------------


def _force(**kw) -> SectorForce:
    base = dict(sector_id=2, owner=Ownership("alliance", 2), fighters=5, mines=2)
    base.update(kw)
    return SectorForce(**base)


def test_force_hostile_keys_on_owner_and_standing() -> None:
    state = _mini_state()
    force = _force()
    assert territory.force_hostile_to_player(state, force, state.players[1]) is False  # neutral
    hostile = replace(state.players[1], alliance_standing={2: -1.0})
    assert territory.force_hostile_to_player(state, force, hostile) is True
    # A player-owned garrison never bars the player.
    own = _force(owner=Ownership("player", 1))
    assert territory.force_hostile_to_player(state, own, hostile) is False


def test_fighter_foe_scales_with_count() -> None:
    small, big = territory.fighter_foe(_force(fighters=2), CFG), territory.fighter_foe(_force(fighters=10), CFG)
    assert big.hull > small.hull and big.firing_arc == "all_round" and big.combat_speed == 0


# --- state builders ---------------------------------------------------------


def _mini_state(*, black_hole: bool = False) -> UniverseState:
    game = Game(id=1, seed=1, config_version=CFG.config_version,
                created_at="1970-01-01T00:00:00Z", core_governing_alliance_id=1)
    state = UniverseState.new(game)
    state.sectors[1] = Sector(id=1, region_id=1, warps_out=(2,), distance_band="Frontier")
    state.sectors[2] = Sector(id=2, region_id=1, warps_out=(1,), distance_band="Frontier")
    state.rebuild_adjacency()
    if black_hole:
        state.discoveries[1] = Discovery(
            id=1, kind=DiscoveryKind.BLACK_HOLE, rarity_tier=RarityTier.RARE, sector_id=2,
            payload=DiscoveryPayload(kind=PayloadKind.LORE, lore="a maw"))
    state.ships[1] = Ship(id=1, type_id="trailblazer", name="T", owner_player_id=1,
                          sector_id=1, holds_total=20, hull_current=200, hull_max=200,
                          shields=50, warp_speed=3, combat_speed=3, turns_per_warp=1)
    state.players[1] = Player(id=1, name="T", ship_id=1, latinum=5000, turns_remaining=100)
    return state


def _generated():
    state = generate(SMALL, 3)
    apply_result(state, reduce(state, 1, JoinGame(name="T"), SMALL))
    dock = next(p.sector_id for p in state.ports.values() if p.klass is PortClass.STARDOCK)
    ship = state.ships[state.players[1].ship_id]
    state.ships[ship.id] = replace(ship, sector_id=dock)  # sit at the StarDock to buy
    return state


# --- buy + deploy reducers --------------------------------------------------


def test_buy_and_deploy_fighters() -> None:
    state = _generated()
    apply_result(state, reduce(state, 1, BuyFighters(count=20), SMALL))
    ship = state.ships[state.players[1].ship_id]
    assert ship.fighters == 20
    # Move to a guaranteed non-Core sector to deploy.
    non_core = next(s.id for s in state.sectors.values() if not s.is_galactic_core)
    state.ships[ship.id] = replace(ship, sector_id=non_core)
    result = reduce(state, 1, DeployFighters(count=8, mode="toll", toll=25), SMALL)
    apply_result(state, result)
    ship = state.ships[state.players[1].ship_id]
    force = state.sector_forces[ship.sector_id]
    assert ship.fighters == 12 and force.fighters == 8 and force.mode == "toll" and force.toll == 25
    assert force.owner == Ownership("player", 1)
    assert any(isinstance(e, TerritoryDeployed) for e in result.events)


def test_deploy_rejects_core() -> None:
    state = _mini_state()
    state.sectors[1] = replace(state.sectors[1], is_galactic_core=True)
    state.ships[1] = replace(state.ships[1], fighters=5)
    with pytest.raises(EconomyError, match="Core"):
        reduce(state, 1, DeployFighters(count=1), CFG)


def test_deploy_beacon_sets_text_and_charges() -> None:
    state = _mini_state()
    before = state.players[1].latinum
    apply_result(state, reduce(state, 1, DeployBeacon(text="hi there"), CFG))
    assert state.sectors[1].beacon_text == "hi there"
    assert state.players[1].latinum == before - TC.beacon_price


# --- movement entry effects -------------------------------------------------


def _make_hostile(state: UniverseState) -> None:
    state.players[1] = replace(state.players[1], alliance_standing={2: -1.0})


def test_hostile_mines_damage_on_entry_and_are_spent() -> None:
    state = _mini_state()
    state.sector_forces[2] = _force(fighters=0, mines=2)
    _make_hostile(state)
    apply_result(state, reduce(state, 1, Warp(to_sector=2), CFG))
    ship = state.ships[1]
    # 2 mines × mine_damage, minus 50 shields absorbed, clamped to leave the ship alive.
    assert ship.hull_current < 200
    assert 2 not in state.sector_forces or state.sector_forces[2].mines == 0  # spent
    assert state.players[1].active_encounter is None  # no fighters ⇒ no engagement


def test_hostile_fighters_force_engagement() -> None:
    state = _mini_state()
    state.sector_forces[2] = _force(fighters=4, mines=0)
    _make_hostile(state)
    apply_result(state, reduce(state, 1, Warp(to_sector=2), CFG))
    enc = state.players[1].active_encounter
    assert enc is not None and enc.species_id == 0 and enc.starbase_id is None


def test_retreat_from_fighters_costs_the_garrison_a_fighter() -> None:
    state = _mini_state()
    state.sector_forces[2] = _force(fighters=4, mines=0)
    # Hand the player a live fighter engagement and force a successful flee.
    foe = territory.fighter_foe(state.sector_forces[2], CFG)
    state.ships[1] = replace(state.ships[1], sector_id=2, combat_speed=99)  # guarantees flee
    state.players[1] = replace(state.players[1], active_encounter=Encounter(
        species_id=0, sector_id=2, foes=(foe,), player_shields=50))
    apply_result(state, reduce(state, 1, CombatAction(action="flee"), CFG))
    assert state.sector_forces[2].fighters == 4 - TC.retreat_fighter_cost


def test_victory_over_fighters_clears_the_garrison() -> None:
    # A generated player ship has a working engine room (Main Gun online).
    state = _generated()
    ship = state.ships[state.players[1].ship_id]
    sid = ship.sector_id
    state.sector_forces[sid] = SectorForce(sector_id=sid, owner=Ownership("alliance", 2), fighters=1)
    foe = replace(territory.fighter_foe(state.sector_forces[sid], SMALL), hull=1, hull_max=1)
    state.players[1] = replace(state.players[1], active_encounter=Encounter(
        species_id=0, sector_id=sid, foes=(foe,), player_shields=ship.shields))
    result = reduce(state, 1, CombatAction(action="fight"), SMALL)
    apply_result(state, result)
    assert sid not in state.sector_forces  # garrison wiped (empty force cleared)


def test_black_hole_damages_on_entry() -> None:
    state = _mini_state(black_hole=True)
    result = reduce(state, 1, Warp(to_sector=2), CFG)
    apply_result(state, result)
    assert state.ships[1].hull_current == 200 - TC.black_hole_damage
    assert any(isinstance(e, HazardDamage) and e.source == "black_hole" for e in result.events)


def test_black_hole_never_kills() -> None:
    state = _mini_state(black_hole=True)
    state.ships[1] = replace(state.ships[1], hull_current=5)  # below the toll
    result = reduce(state, 1, Warp(to_sector=2), CFG)
    apply_result(state, result)
    assert state.ships[1].hull_current == 1  # clamped alive (lethal-hazard→pod is a seam)
    assert any(isinstance(e, HazardDamage) for e in result.events)
