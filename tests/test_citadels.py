"""WP54 — citadels: levels, treasury, timed builds, the planetary gun (DESIGN §4.2, §14).

Covers the build ladder + validation, exact colonist-day accrual under the planet-growth
cron (a ticked build reloads to an identical hash and completes exactly once), the
one-build-per-planet rule, treasury conservation, and the citadel gun's config-derived
defense foe.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from edge.config import load_default_config
from edge.core import citadels
from edge.core.citadels import CitadelError
from edge.core.enums import Commodity
from edge.core.models import (
    Game,
    Ownership,
    Planet,
    Player,
    Sector,
    Ship,
    UniverseState,
)
from edge.core.combat import CombatError
from edge.core.rules import (
    BuildCitadel, InvadePlanet, PlanetDeposit, PlanetWithdraw, SetAllocation, apply_result, reduce,
)
from edge.engine.cron import planet_growth

CFG = load_default_config()
L1 = CFG.citadels.levels[0]  # type: ignore[union-attr]


def _world(*, colonists: int = 200, equipment: int = 1000, latinum: int = 50_000,
           level: int = 0) -> UniverseState:
    """A single owned colony in the player's sector (no port), ready to fortify."""
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t"))
    state.sectors = {1: Sector(1, 1, (), "Frontier")}
    state.rebuild_adjacency()
    state.planets = {
        1: Planet(1, 1, "Bastion", "terrestrial_warm", owner=Ownership("player", 1),
                  colonists=colonists, habitability_cap=100_000,
                  stores={Commodity.EQUIPMENT: equipment}, citadel_level=level),
    }
    state.ships = {1: Ship(id=1, type_id="trailblazer", name="S.S.", owner_player_id=1,
                           sector_id=1, holds_total=60, turns_per_warp=1)}
    state.players = {1: Player(id=1, name="you", ship_id=1, latinum=latinum, turns_remaining=250)}
    return state


def test_build_citadel_pays_up_front_and_opens_a_build() -> None:
    state = _world()
    before_eq = state.planets[1].stores[Commodity.EQUIPMENT]
    before_lat = state.players[1].latinum
    apply_result(state, reduce(state, 1, BuildCitadel(1), CFG))
    planet = state.planets[1]
    assert planet.citadel_progress == 0  # build opened
    assert planet.citadel_level == 0  # not yet complete
    assert planet.stores[Commodity.EQUIPMENT] == before_eq - L1.cost_equipment
    assert state.players[1].latinum == before_lat - L1.cost_latinum


def test_build_rejects_too_few_colonists_or_equipment_or_latinum() -> None:
    with pytest.raises(CitadelError):  # colonist gate
        reduce(_world(colonists=L1.min_colonists - 1), 1, BuildCitadel(1), CFG)
    with pytest.raises(CitadelError):  # equipment gate
        reduce(_world(equipment=L1.cost_equipment - 1), 1, BuildCitadel(1), CFG)
    from edge.core.economy import EconomyError
    with pytest.raises(EconomyError):  # latinum gate
        reduce(_world(latinum=L1.cost_latinum - 1), 1, BuildCitadel(1), CFG)


def test_only_one_build_open_per_planet() -> None:
    state = _world()
    apply_result(state, reduce(state, 1, BuildCitadel(1), CFG))
    with pytest.raises(CitadelError):
        reduce(state, 1, BuildCitadel(1), CFG)


def test_timed_build_accrues_and_completes_exactly_once() -> None:
    state = _world(colonists=L1.min_colonists)
    apply_result(state, reduce(state, 1, BuildCitadel(1), CFG))
    # Freeze growth so accrual is exactly `colonists` per firing (isolates the build math).
    state.planets[1] = replace(state.planets[1], colonists=L1.min_colonists,
                               habitability_cap=L1.min_colonists)
    completed_events = 0
    fired = 0
    while state.planets[1].citadel_level < 1 and fired < 10_000:
        res = planet_growth(state, CFG)
        apply_result(state, res)
        completed_events += sum(1 for e in res.events
                                if type(e).__name__ == "CitadelCompleted")
        fired += 1
    assert state.planets[1].citadel_level == 1
    assert state.planets[1].citadel_progress == -1  # build cleared
    assert completed_events == 1  # fires exactly once
    # One more tick does not re-complete or reopen.
    res = planet_growth(state, CFG)
    assert not any(type(e).__name__ == "CitadelCompleted" for e in res.events)


def test_build_stalls_without_colonists() -> None:
    state = _world(colonists=L1.min_colonists)
    apply_result(state, reduce(state, 1, BuildCitadel(1), CFG))
    state.planets[1] = replace(state.planets[1], colonists=0)
    p, completed = citadels.advance_build(state.planets[1], CFG)
    assert not completed and p.citadel_progress == 0  # no labour → no progress


def test_treasury_deposit_withdraw_conserves_latinum() -> None:
    state = _world(level=1)
    total_before = state.players[1].latinum + state.planets[1].treasury
    apply_result(state, reduce(state, 1, PlanetDeposit(1, 5_000), CFG))
    assert state.planets[1].treasury == 5_000
    apply_result(state, reduce(state, 1, PlanetWithdraw(1, 2_000), CFG))
    assert state.planets[1].treasury == 3_000
    assert state.players[1].latinum + state.planets[1].treasury == total_before  # conserved
    with pytest.raises(Exception):  # overdraw rejected
        reduce(state, 1, PlanetWithdraw(1, 999_999), CFG)


def test_treasury_requires_a_citadel() -> None:
    from edge.core.economy import EconomyError
    with pytest.raises(EconomyError):
        reduce(_world(level=0), 1, PlanetDeposit(1, 1_000), CFG)


def test_citadel_foe_derives_from_config() -> None:
    cfg = CFG.citadels
    assert cfg is not None
    planet = replace(_world(level=2).planets[1], citadel_level=2, gun_integrity=cfg.gun_hull)
    foe = citadels.citadel_foe(planet, CFG)
    assert foe.hull == cfg.gun_hull and foe.damage == cfg.gun_damage
    assert foe.firing_arc == "all_round" and foe.combat_speed == 0
    assert citadels.has_gun(planet, CFG)
    # A silenced gun (integrity 0) no longer defends.
    assert not citadels.has_gun(replace(planet, gun_integrity=0), CFG)


def test_l3_siege_shield_predicate() -> None:
    cfg = CFG.citadels
    assert cfg is not None
    l3 = replace(_world(level=3).planets[1], citadel_level=3, gun_integrity=cfg.gun_hull)
    assert citadels.siege_shielded(l3, CFG, base_operational=False)  # gun projects the shield
    down = replace(l3, gun_integrity=0)
    assert not citadels.siege_shielded(down, CFG, base_operational=False)  # nothing stands
    assert citadels.siege_shielded(down, CFG, base_operational=True)  # base projects it


def test_owner_only_gating() -> None:
    from edge.core.economy import EconomyError
    state = _world()
    state.planets[1] = replace(state.planets[1], owner=Ownership("alliance", 2))
    with pytest.raises(EconomyError):
        reduce(state, 1, BuildCitadel(1), CFG)


# --- WP55: planetary siege + conquest ----------------------------------------


def _enemy_world(*, fighters: int = 100, level: int = 0, gun: int = 0) -> UniverseState:
    """An alliance-owned world in the player's sector, ready to invade (no base)."""
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t"))
    state.sectors = {1: Sector(1, 1, (), "Frontier")}
    state.rebuild_adjacency()
    state.alliances = {}
    state.planets = {
        1: Planet(1, 1, "Redoubt", "terrestrial_warm", owner=Ownership("alliance", 2),
                  colonists=1000, habitability_cap=100_000, citadel_level=level,
                  fighters=fighters, gun_integrity=gun),
    }
    state.ships = {1: Ship(id=1, type_id="trailblazer", name="S.S.", owner_player_id=1,
                           sector_id=1, holds_total=60, turns_per_warp=1, fighters=500)}
    state.players = {1: Player(id=1, name="you", ship_id=1, latinum=0, turns_remaining=250,
                               alignment=0)}
    return state


def test_invasion_commits_fighters_and_flips_ownership_on_victory() -> None:
    state = _enemy_world(fighters=10)  # a token garrison — the attacker should win
    before = state.ships[1].fighters
    apply_result(state, reduce(state, 1, InvadePlanet(1, 300), CFG))
    planet = state.planets[1]
    assert planet.owner == Ownership("player", 1)  # flipped
    assert state.ships[1].fighters == before - 300  # committed fighters left the ship
    assert planet.gun_integrity == 0
    assert state.players[1].alliance_standing.get(2) == -1.0  # bloc soured


def test_invasion_ladder_rejects_until_gun_is_down() -> None:
    # A live citadel gun bars a ground assault.
    state = _enemy_world(fighters=10, level=2, gun=CFG.citadels.gun_hull)  # type: ignore[union-attr]
    with pytest.raises(CombatError):
        reduce(state, 1, InvadePlanet(1, 300), CFG)
    # With the gun silenced (integrity 0) the assault is legal.
    state.planets[1] = replace(state.planets[1], gun_integrity=0)
    reduce(state, 1, InvadePlanet(1, 300), CFG)  # no raise


def test_invasion_fighters_never_minted_and_repulse_costs_them() -> None:
    # An overwhelming garrison repulses a token assault; committed fighters die.
    state = _enemy_world(fighters=100_000)
    before_ship = state.ships[1].fighters
    apply_result(state, reduce(state, 1, InvadePlanet(1, 5), CFG))
    assert state.ships[1].fighters == before_ship - 5  # the 5 committed are gone
    assert state.planets[1].owner == Ownership("alliance", 2)  # not taken
    assert state.players[1].alignment < 0  # alignment hit on the failed assault


def test_cannot_invade_a_core_world() -> None:
    state = _enemy_world(fighters=10)
    state.sectors = {1: replace(state.sectors[1], is_galactic_core=True)}
    with pytest.raises(CombatError):
        reduce(state, 1, InvadePlanet(1, 300), CFG)


def test_set_allocation_with_fighter_share_normalizes_to_one() -> None:
    state = _world(level=1)
    apply_result(state, reduce(state, 1, SetAllocation(
        1, allocation={"fuel_ore": 1.0, "organics": 1.0, "equipment": 1.0}, fighter=1.0), CFG))
    planet = state.planets[1]
    total = sum(planet.allocation.values()) + planet.fighter_allocation
    assert abs(total - 1.0) < 1e-9  # the §4.2 invariant
    assert abs(planet.fighter_allocation - 0.25) < 1e-9


def test_garrison_production_mints_fighters() -> None:
    from edge.core.planets import produce
    state = _world(level=1)
    state.planets[1] = replace(state.planets[1], colonists=1000, fighter_allocation=1.0, allocation={})
    grown = produce(state.planets[1], CFG)
    assert grown.fighters > 0  # the fighter share minted defenders
