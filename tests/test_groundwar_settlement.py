"""GW-WP11 — strategic assault settlement, protectorates, and consequences."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given, settings, strategies as st

from edge.config import load_default_config
from edge.core.enums import Commodity
from edge.core.events import (
    GrudgeFormed,
    GroundAssaultSettled,
    PlanetInvaded,
    ProtectorateAnnexed,
    ProtectorateEstablished,
)
from edge.core.groundwar import assault
from edge.core.groundwar import settlement as gs
from edge.core.groundwar.models import (
    AssaultGarrisonUnit,
    AssaultOperation,
    AssaultTrooper,
)
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
from edge.core.rules import AnnexProtectorate, ExtractGroundOperation, apply_result, reduce
from edge.store.snapshots import state_hash

CFG = load_default_config()
GW = CFG.groundwar
assert GW is not None


def _planet(owner: Ownership = Ownership("none"), *, roster_id: str = "vesk") -> Planet:
    return Planet(
        id=1,
        sector_id=1,
        name="Haven",
        planet_type="terrestrial_warm",
        owner=owner,
        population={roster_id: 1_000},
        habitability_cap=10_000,
        stores={Commodity.FUEL_ORE: 80, Commodity.EQUIPMENT: 40},
        citadel_level=2,
        citadel_progress=37,
        treasury=900,
        fighters=12,
        gun_integrity=55,
        garrison_infantry=8,
        garrison_armor=2,
    )


def _ship(*, count: int = 2, missiles: int = 6) -> Ship:
    return Ship(
        id=1,
        type_id="trailblazer",
        name="S.S. Settlement",
        owner_player_id=1,
        sector_id=1,
        holds_total=60,
        passenger_capacity=20,
        recruits=count,
        suits={"marauder": count},
        ground_missiles=missiles,
    )


def _trooper(tid: int, *, hp: int, missiles: int = 0) -> AssaultTrooper:
    return AssaultTrooper(
        id=tid,
        suit_id="marauder",
        name=f"T{tid}",
        x=1,
        y=1,
        hp=hp,
        missiles=missiles,
        jump_charges=0,
    )


def _operation(
    planet: Planet,
    *,
    outcome: str | None = "retrieval",
    dropped: bool = True,
    platoon: tuple[AssaultTrooper, ...] | None = None,
    structure_hp: dict[int, int] | None = None,
) -> AssaultOperation:
    return AssaultOperation(
        operation_id=17,
        planet_id=planet.id,
        sector_id=planet.sector_id,
        planet_type=planet.planet_type,
        seed=42,
        started_day=3,
        resolve=35,
        retrieval_turn=20,
        cities=1,
        citadel_level=planet.citadel_level,
        surrender_threshold=GW.resolve.surrender_threshold,
        reserved_infantry=8,
        reserved_armor=2,
        outcome=outcome,
        dropped=dropped,
        platoon=platoon or (_trooper(100, hp=80, missiles=1), _trooper(101, hp=0)),
        garrison_units=(
            AssaultGarrisonUnit(200, "infantry", 2, 2, 20, 1),
            AssaultGarrisonUnit(201, "armor", 3, 2, 30, 1),
        ),
        structure_hp=structure_hp or {},
        infantry_remaining=2,
        armor_remaining=0,
        initial_strength=2,
        ground_missiles_committed=4,
    )


def _species(roster_id: str) -> AlienSpecies:
    sc = next(species for species in CFG.roster.species if species.id == roster_id)
    return AlienSpecies(
        id=7,
        roster_id=roster_id,
        name=sc.name,
        archetype_id=sc.archetype_id,
        sector_id=1,
        home_band="Frontier",
        tech_level=sc.tech_level,
        base_disposition=sc.disposition_center,
        disposition_center=sc.disposition_center,
        disposition_variance=0.0,
    )


def _world(planet: Planet, operation: AssaultOperation, *, roster_id: str) -> UniverseState:
    state = UniverseState.new(Game(1, 5, CFG.config_version, "t", day_number=10))
    state.sectors = {1: Sector(1, 1, (), "Frontier")}
    state.rebuild_adjacency()
    state.planets = {1: planet}
    state.species = {7: _species(roster_id)}
    state.ships = {1: _ship()}
    state.players = {
        1: Player(
            id=1,
            name="you",
            ship_id=1,
            latinum=100,
            turns_remaining=250,
            ground_operation=operation,
        )
    }
    return state


def test_pre_drop_abort_is_mutation_free() -> None:
    planet = _planet()
    ship = _ship()
    settled = gs.settle_assault(
        planet,
        ship,
        _operation(planet, dropped=False, platoon=()),
        player_id=1,
        corp_id=None,
        day=5,
        config=CFG,
    )
    assert settled.planet is planet
    assert settled.ship is ship
    assert settled.outcome == "aborted"


def test_retrieval_returns_survivors_and_debits_dead_recruit_suit_and_ordnance() -> None:
    planet = _planet()
    settled = gs.settle_assault(
        planet,
        _ship(),
        _operation(planet),
        player_id=1,
        corp_id=None,
        day=5,
        config=CFG,
    )
    assert (settled.attacker_losses, settled.attacker_survivors) == (1, 1)
    assert settled.ship.recruits == 1
    assert settled.ship.suits == {"marauder": 1}
    assert settled.ship.ground_missiles == 3  # 4 loaded, 1 unused round returned
    assert settled.missiles_spent == 3
    assert (settled.defender_infantry, settled.defender_armor) == (3, 1)
    assert settled.defender_losses == 6
    assert settled.planet.owner == planet.owner


@settings(max_examples=20, deadline=None)
@given(total=st.integers(min_value=1, max_value=5), dead=st.integers(min_value=0, max_value=5))
def test_attacker_headcount_and_suit_conservation(total: int, dead: int) -> None:
    dead = min(dead, total)
    planet = _planet()
    platoon = tuple(_trooper(i, hp=0 if i < dead else 50) for i in range(total))
    op = replace(
        _operation(planet, platoon=platoon),
        ground_missiles_committed=0,
        garrison_units=(),
    )
    settled = gs.settle_assault(
        planet,
        _ship(count=total, missiles=0),
        op,
        player_id=1,
        corp_id=None,
        day=5,
        config=CFG,
    )
    assert settled.attacker_losses + settled.attacker_survivors == total
    assert settled.ship.recruits == settled.attacker_survivors
    assert settled.ship.suits.get("marauder", 0) == settled.attacker_survivors


@pytest.mark.parametrize(
    "former_owner",
    [Ownership("alliance", 4), Ownership("player", 2), Ownership("corp", 3)],
)
def test_surrender_conquers_every_owned_kind_and_preserves_open_build(
    former_owner: Ownership,
) -> None:
    planet = _planet(former_owner)
    settled = gs.settle_assault(
        planet,
        _ship(),
        _operation(planet, outcome="surrender"),
        player_id=1,
        corp_id=None,
        day=5,
        config=CFG,
    )
    assert settled.control == "conquest"
    assert settled.planet.owner == Ownership("player", 1)
    assert settled.loot == 900 and settled.planet.treasury == 0
    assert settled.planet.citadel_level == 1
    assert settled.planet.citadel_progress == 37
    assert settled.planet.stores == planet.stores
    assert (settled.planet.garrison_infantry, settled.planet.garrison_armor) == (3, 1)


def test_failed_assault_persists_defender_and_structure_damage_without_control_flip() -> None:
    planet = _planet(Ownership("alliance", 4))
    amap = assault.assault_map_for_state(_operation(planet), CFG)
    wall = next(structure for structure in amap.structures if structure.kind == "wall")
    op = _operation(planet, outcome="casualties", structure_hp={wall.id: 0})
    settled = gs.settle_assault(
        planet, _ship(), op, player_id=1, corp_id=None, day=5, config=CFG)
    assert settled.control == "none"
    assert settled.planet.owner == Ownership("alliance", 4)
    # GW-WP19: damage persists by position, so the record names the wall that fell.
    assert (wall.x, wall.y, "wall") in [
        (entry.x, entry.y, entry.kind) for entry in settled.planet.ground_rubble]
    assert settled.planet.ground_resolve == 35
    assert settled.planet.ground_last_assault_day == 5


def test_civilian_destruction_persists_population_loss_without_erasing_species() -> None:
    planet = _planet()
    amap = assault.assault_map_for_state(_operation(planet), CFG)
    civilian = next(
        structure for structure in amap.structures if structure.kind == "building_civilian")
    settled = gs.settle_assault(
        planet,
        _ship(),
        _operation(planet, structure_hp={civilian.id: 0}),
        player_id=1,
        corp_id=None,
        day=5,
        config=CFG,
    )
    assert settled.civilian_structures_destroyed == 1
    assert settled.civilian_losses > 0
    assert set(settled.planet.population) == {"vesk"}
    assert [(entry.x, entry.y) for entry in settled.planet.ground_rubble] == [
        (civilian.x, civilian.y)]


def test_unaligned_surrender_creates_native_protectorate_and_permanent_grudge() -> None:
    planet = _planet(roster_id="concordance")
    state = _world(
        planet,
        _operation(planet, outcome="surrender"),
        roster_id="concordance",
    )
    result = reduce(state, 1, ExtractGroundOperation(17), CFG)
    assert any(isinstance(event, GroundAssaultSettled) for event in result.events)
    assert any(isinstance(event, ProtectorateEstablished) for event in result.events)
    assert any(isinstance(event, GrudgeFormed) and event.permanent for event in result.events)
    assert not any(isinstance(event, PlanetInvaded) for event in result.events)
    apply_result(state, result)
    protected = state.planets[1]
    assert protected.owner == Ownership("none")
    assert protected.protectorate_controller == Ownership("player", 1)
    assert protected.population == {"concordance": 1_000}
    assert protected.stores == planet.stores and protected.treasury == 900
    assert state.players[1].grudges["concordance"].duration_days < 0


def test_protectorate_annexation_has_time_and_resolve_gates_then_merges_share() -> None:
    planet = replace(
        _planet(roster_id="concordance"),
        protectorate_controller=Ownership("player", 1),
        protectorate_since=5,
        protectorate_stores={Commodity.FUEL_ORE: 7, Commodity.ORGANICS: 3},
        ground_resolve=GW.settlement.annex_resolve_threshold,
    )
    assert "days" in (gs.annex_ready(planet, 1, None, 6, CFG) or "")
    low = replace(planet, protectorate_since=0, ground_resolve=1)
    assert "Resolve" in (gs.annex_ready(low, 1, None, 10, CFG) or "")

    state = _world(planet, _operation(planet, dropped=False), roster_id="concordance")
    state.players[1] = replace(state.players[1], ground_operation=None)
    before_alignment = state.players[1].alignment
    result = reduce(state, 1, AnnexProtectorate(1), CFG)
    assert any(isinstance(event, ProtectorateAnnexed) for event in result.events)
    assert any(isinstance(event, GrudgeFormed) and event.permanent for event in result.events)
    apply_result(state, result)
    annexed = state.planets[1]
    assert annexed.owner == Ownership("player", 1)
    assert annexed.protectorate_controller == Ownership("none")
    assert annexed.stores[Commodity.FUEL_ORE] == 87
    assert annexed.stores[Commodity.ORGANICS] == 3
    assert state.players[1].alignment == before_alignment - GW.settlement.annex_alignment_penalty


def test_daily_resolve_recovery_is_once_per_day_and_rubble_does_not_heal() -> None:
    rubble = (GroundRubble(10, 10, "wall"), GroundRubble(11, 10, "wall"))
    planet = replace(
        _planet(), ground_resolve=20, ground_rubble=rubble, ground_last_assault_day=5)
    recovered = assault.apply_ground_recovery(planet, CFG, 6)
    assert recovered.ground_resolve == 20 + GW.settlement.resolve_recovery_per_day
    assert recovered.ground_rubble == rubble
    assert assault.apply_ground_recovery(recovered, CFG, 6) == recovered


def test_full_siege_settlement_replay_hash_is_deterministic() -> None:
    def play() -> str:
        planet = _planet(roster_id="concordance")
        state = _world(
            planet,
            _operation(planet, outcome="surrender"),
            roster_id="concordance",
        )
        apply_result(state, reduce(state, 1, ExtractGroundOperation(17), CFG))
        return state_hash(state)

    assert play() == play()
