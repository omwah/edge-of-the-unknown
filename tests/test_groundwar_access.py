"""GW-WP04 — the one ground-access contract (GW plan §Ground-access contract).

Table coverage of `edge.core.groundwar.access.ground_access` across landability, the
inhabited/friendly/below-friendly split (D1), Core sanctuary (G13), the Cloud City seam
(D9), the siege-ladder blockers (G12), and assault-disabled universes — plus DTO/reducer
lockstep: `PlanetDTO.ground_mode` mirrors the classifier, and `BeginSurvey` rejects a
non-survey world with the classifier's own reason.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.config import load_default_config
from edge.core.groundwar.access import (
    Assault,
    OrbitalOnly,
    Survey,
    ground_access,
)
from edge.core.models import (
    AlienSpecies,
    Game,
    Ownership,
    Planet,
    Player,
    Sector,
    Ship,
    UniverseState,
)
from edge.core.rules import BeginAssault, BeginSurvey, ReinforceGarrison, apply_result, reduce
from edge.store.snapshots import state_hash
from edge.core.economy import EconomyError
from edge.core.groundwar.force import GroundForceError
from edge.core.groundwar.models import SurveyOperation
from edge.server import session

CFG = load_default_config()
AMITY = CFG.aliens.amity_threshold  # type: ignore[union-attr]
GUN_MIN = CFG.citadels.gun_min_level  # type: ignore[union-attr]


def _state(planet: Planet, *, core: bool = False, player_alliance: int | None = None) -> UniverseState:
    """A one-sector universe holding `planet` with player 1 in the same sector."""
    state = UniverseState.new(Game(1, 1, CFG.config_version, "t"))
    state.sectors = {1: Sector(1, 1, (), "Hub" if core else "Frontier", is_galactic_core=core)}
    state.rebuild_adjacency()
    state.planets = {planet.id: planet}
    state.ships = {1: Ship(id=1, type_id="trailblazer", name="S.S.", owner_player_id=1,
                           sector_id=1, holds_total=60, turns_per_warp=1)}
    state.players = {1: Player(id=1, name="you", ship_id=1, latinum=10_000,
                               turns_remaining=250, alliance_id=player_alliance)}
    return state


def _planet(**kw: object) -> Planet:
    base = dict(id=1, sector_id=1, name="World", planet_type="terrestrial_warm",
                habitability_cap=100_000)
    base.update(kw)
    return Planet(**base)  # type: ignore[arg-type]


def _species(disp: float, *, alliance: int | None = None) -> AlienSpecies:
    return AlienSpecies(
        id=7, roster_id="vesk", name="Vesk", archetype_id="a", sector_id=1,
        home_band="Frontier", tech_level=1, base_disposition=disp,
        disposition_center=disp, disposition_variance=0.0, alliance_id=alliance)


# --- landability & the Cloud City seam (D9) ----------------------------------


def _pair(planet: Planet, **skw: object) -> tuple[UniverseState, Planet]:
    state = _state(planet, **skw)  # type: ignore[arg-type]
    return state, planet


def test_belt_is_orbital_only() -> None:
    state, planet = _pair(_planet(planet_type="asteroid_belt"))
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, OrbitalOnly)
    assert access.mode == "orbital_only"


def test_bare_jovian_is_orbital_only() -> None:
    state, planet = _pair(_planet(planet_type="jovian"))
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, OrbitalOnly)


# --- GW-WP16: the Cloud City assault gate ------------------------------------
#
# The gate is **on** in the production default (`config/groundwar_default.yaml`,
# GW-M5) — `CFG` here already has it enabled, so `_GATE_ON` is just a readable
# alias for the tests below; `_GATE_OFF` constructs the pre-WP16 config
# explicitly for the two regression tests that need it.

_GATE_ON = CFG
_GATE_OFF = CFG.model_copy(update={
    "groundwar": CFG.groundwar.model_copy(update={"cloud_city_assault_enabled": False})})  # type: ignore[union-attr]


def test_inhabited_cloud_city_surveys_with_gate_off() -> None:
    """With the assault gate off, a Cloud City never assaults — it routes to the
    GW-WP17 walking tour instead of the pre-WP17 permanent `OrbitalOnly`."""
    state, planet = _pair(_planet(planet_type="jovian", cloud_city_size=2))
    access = ground_access(state, state.players[1], planet, _GATE_OFF)
    assert isinstance(access, Survey)
    assert access.settlements is False


def test_unowned_cloud_city_with_no_species_assaults_by_default() -> None:
    """The production default (gate on): an unowned Cloud City with nothing
    inhabiting it resolvable is below-friendly by the same fallthrough every
    other ownerless, species-less world uses."""
    state, planet = _pair(_planet(planet_type="jovian", cloud_city_size=2))
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)


def test_gate_on_below_friendly_cloud_city_routes_to_assault() -> None:
    """A below-friendly (unaligned, below-amity) Cloud City assaults once the
    migration flag is on — the same below-friendly routing every other
    inhabited world already gets (D1)."""
    planet = _planet(planet_type="jovian", cloud_city_size=2,
                     population={"vesk": 5_000})
    state = _state(planet)
    state.species = {7: _species(AMITY - 0.1)}
    access = ground_access(state, state.players[1], planet, _GATE_ON)
    assert isinstance(access, Assault)


def test_gate_on_friendly_cloud_city_surveys() -> None:
    """Even with the gate on, a friendly/owned Cloud City never assaults (D9) — it
    routes to `Survey` (GW-WP17), the walking tour of its own interior."""
    planet = _planet(planet_type="jovian", cloud_city_size=2,
                     owner=Ownership("player", 1))
    state, _ = _pair(planet)
    access = ground_access(state, state.players[1], planet, _GATE_ON)
    assert isinstance(access, Survey)
    assert access.settlements is False


def test_gate_on_bare_gas_giant_stays_orbital_only() -> None:
    """The gate only ever applies to a *built* Cloud City (`cloud_city_size > 0`)."""
    state, planet = _pair(_planet(planet_type="jovian"))
    access = ground_access(state, state.players[1], planet, _GATE_ON)
    assert isinstance(access, OrbitalOnly)
    assert "gas giant" in access.reason


def test_gate_on_core_cloud_city_stays_orbital_only() -> None:
    """G13 Core sanctuary holds for a Cloud City exactly like any other world."""
    planet = _planet(planet_type="jovian", cloud_city_size=2,
                     population={"vesk": 5_000})
    state = _state(planet, core=True)
    state.species = {7: _species(AMITY - 0.1)}
    access = ground_access(state, state.players[1], planet, _GATE_ON)
    assert isinstance(access, OrbitalOnly)
    assert "Core" in access.reason


def test_gate_on_below_friendly_cloud_city_without_citadels_stays_orbital_only() -> None:
    cfg = _GATE_ON.model_copy(update={"citadels": None})
    planet = _planet(planet_type="jovian", cloud_city_size=2,
                     population={"vesk": 5_000})
    state = _state(planet)
    state.species = {7: _species(AMITY - 0.1)}
    access = ground_access(state, state.players[1], planet, cfg)
    assert isinstance(access, OrbitalOnly)
    assert "not enabled" in access.reason


def test_gate_off_is_unaffected_by_below_friendly_standing() -> None:
    """Regression guard: the same below-friendly Cloud City never assaults when the
    flag is explicitly off (the pre-WP16 / migration-rollback state) — it surveys
    (GW-WP17) rather than assaults, exactly as a gate-on friendly one does."""
    planet = _planet(planet_type="jovian", cloud_city_size=2,
                     population={"vesk": 5_000})
    state = _state(planet)
    state.species = {7: _species(AMITY - 0.1)}
    access = ground_access(state, state.players[1], planet, _GATE_OFF)
    assert isinstance(access, Survey)


# --- survey routing (D1: uninhabited / friendly) -----------------------------


def test_uninhabited_landable_world_surveys_without_settlements() -> None:
    state, planet = _pair(_planet())
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Survey)
    assert access.settlements is False


def test_player_owned_inhabited_world_surveys_with_settlements() -> None:
    state, planet = _pair(_planet(owner=Ownership("player", 1), population={"terran": 500}))
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Survey)
    assert access.settlements is True


def test_own_alliance_world_surveys() -> None:
    state, planet = _pair(_planet(owner=Ownership("alliance", 5), population={"terran": 500}),
                          player_alliance=5)
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Survey)


def test_friendly_species_world_surveys() -> None:
    planet = _planet(population={"vesk": 500})
    state = _state(planet)
    state.species = {7: _species(AMITY + 0.2)}
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Survey)
    assert access.settlements is True


# --- assault routing (D1: inhabited & below friendly) ------------------------


def test_hostile_species_world_assaults() -> None:
    planet = _planet(population={"vesk": 500})
    state = _state(planet)
    state.species = {7: _species(0.1)}
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)
    assert access.inhabited is True
    assert access.droppable  # no defences standing


def test_neutral_species_world_still_assaults() -> None:
    # Below amity but above hostility — D1 routes it to assault all the same.
    planet = _planet(population={"vesk": 500})
    state = _state(planet)
    state.species = {7: _species(AMITY - 0.05)}
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)


def test_rival_alliance_world_assaults() -> None:
    state, planet = _pair(_planet(owner=Ownership("alliance", 6), population={"terran": 500}),
                          player_alliance=5)
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)
    assert access.owner == Ownership("alliance", 6)


def test_grudge_pushes_a_mild_species_into_assault() -> None:
    from edge.core.models import Grudge
    planet = _planet(population={"vesk": 500})
    state = _state(planet)
    state.species = {7: _species(AMITY + 0.05)}  # nominally friendly...
    grudged = replace(state.players[1], grudges={"vesk": Grudge(
        holder="vesk", target="player", cause="x", severity=0.3, created_day=0, duration_days=30)})
    access = ground_access(state, grudged, planet, CFG)
    assert isinstance(access, Assault)  # ...but the grudge drops it below amity


# --- Core sanctuary (G13) ----------------------------------------------------


def test_core_world_never_assaults() -> None:
    planet = _planet(population={"vesk": 500})
    state = _state(planet, core=True)
    state.species = {7: _species(0.05)}  # deeply hostile
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, OrbitalOnly)
    assert "Core" in access.reason


# --- siege-ladder blockers (G12) ---------------------------------------------


def test_live_citadel_gun_blocks_the_drop() -> None:
    planet = _planet(population={"vesk": 500}, citadel_level=GUN_MIN, gun_integrity=50)
    state = _state(planet)
    state.species = {7: _species(0.1)}
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)
    assert not access.droppable
    assert access.blockers[0] == "silence the citadel gun first"


def test_planet_dto_exposes_every_standing_siege_blocker() -> None:
    planet = _planet(
        population={"vesk": 500}, citadel_level=CFG.citadels.shield_min_level,
        gun_integrity=CFG.citadels.gun_hull,
    )
    state = _state(planet)
    state.species = {7: _species(0.1)}
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)
    assert access.blockers == (
        "silence the citadel gun first", "the siege shield holds",
    )
    view = session.planet_view(state, 1, planet.id, CFG)
    assert view.ground_blockers == list(access.blockers)


# --- assault disabled --------------------------------------------------------


def test_hostile_world_is_orbital_only_when_citadels_disabled() -> None:
    cfg = CFG.model_copy(update={"citadels": None})
    planet = _planet(population={"vesk": 500})
    state = _state(planet)
    state.species = {7: _species(0.1)}
    access = ground_access(state, state.players[1], planet, cfg)
    assert isinstance(access, OrbitalOnly)
    assert "not enabled" in access.reason


# --- DTO / reducer lockstep --------------------------------------------------


@pytest.mark.parametrize("build", [
    lambda: (_planet(), None, None),                                   # uninhabited survey
    lambda: (_planet(planet_type="asteroid_belt"), None, None),        # orbital only
])
def test_planet_dto_mode_matches_classifier(build) -> None:
    planet, species, _ = build()
    state = _state(planet)
    if species is not None:
        state.species = {7: species}
    access = ground_access(state, state.players[1], planet, CFG)
    view = session.planet_view(state, 1, planet.id, CFG)
    assert view.ground_mode == access.mode


# --- BeginAssault (GW-WP09, D7-D11) -------------------------------------------


def test_begin_assault_opens_operation_on_a_droppable_hostile_world() -> None:
    planet = _planet(population={"vesk": 500}, habitability_cap=100_000,
                     garrison_infantry=400, garrison_armor=20)
    state = _state(planet)
    state.species = {7: _species(0.1)}
    result = reduce(state, 1, BeginAssault(planet.id), CFG)
    assert result.players
    op = result.players[0].ground_operation
    assert op is not None and op.kind == "assault"
    assert op.planet_id == planet.id
    assert op.reserved_infantry == 400 and op.reserved_armor == 20
    assert op.cities >= CFG.groundwar.assault_difficulty.min_cities  # type: ignore[union-attr]


def test_begin_assault_does_not_mutate_the_planet() -> None:
    planet = _planet(population={"vesk": 500}, garrison_infantry=100, garrison_armor=5)
    state = _state(planet)
    state.species = {7: _species(0.1)}
    reduce(state, 1, BeginAssault(planet.id), CFG)
    assert state.planets[planet.id] == planet  # decision #1: nothing is spent at begin


def test_begin_assault_rejects_orbital_only_and_survey_worlds() -> None:
    for build_planet in (
        lambda: _planet(planet_type="asteroid_belt"),
        lambda: _planet(),  # uninhabited — surveys
        lambda: _planet(population={"vesk": 500}),  # friendly species (default disposition)
    ):
        planet = build_planet()
        state = _state(planet)
        state.species = {7: _species(CFG.aliens.amity_threshold + 0.2)}  # type: ignore[union-attr]
        access = ground_access(state, state.players[1], planet, CFG)
        with pytest.raises(EconomyError) as excinfo:
            reduce(state, 1, BeginAssault(planet.id), CFG)
        assert str(excinfo.value) == access.reason
        assert state.players[1].ground_operation is None


def test_begin_assault_rejects_when_the_citadel_gun_still_stands() -> None:
    planet = _planet(population={"vesk": 500}, citadel_level=GUN_MIN, gun_integrity=50)
    state = _state(planet)
    state.species = {7: _species(0.1)}
    with pytest.raises(EconomyError, match="silence the citadel gun first"):
        reduce(state, 1, BeginAssault(planet.id), CFG)
    assert state.players[1].ground_operation is None


def test_begin_assault_second_call_is_rejected_while_one_is_open() -> None:
    from edge.core.movement import MovementError

    planet = _planet(population={"vesk": 500})
    state = _state(planet)
    state.species = {7: _species(0.1)}
    result = reduce(state, 1, BeginAssault(planet.id), CFG)
    state.players[1] = result.players[0]
    with pytest.raises(MovementError):
        reduce(state, 1, BeginAssault(planet.id), CFG)


@pytest.mark.parametrize("fighters", [0, 1, 500, 9999])
def test_begin_assault_ignores_the_player_ships_fighters(fighters: int) -> None:
    """Fighters are a space asset (D7) — assault difficulty/reservation never reads them."""
    planet = _planet(population={"vesk": 500}, garrison_infantry=250)
    state = _state(planet)
    state.species = {7: _species(0.1)}
    state.ships[1] = replace(state.ships[1], fighters=fighters)
    result = reduce(state, 1, BeginAssault(planet.id), CFG)
    op = result.players[0].ground_operation
    assert op is not None and op.reserved_infantry == 250


# --- ReinforceGarrison (GW-WP09, D15) -----------------------------------------


def _owned_reinforceable_state(*, recruits: int = 10, suits: dict[str, int] | None = None,
                               garrison_infantry: int = 0) -> tuple[UniverseState, Planet]:
    planet = _planet(owner=Ownership("player", 1), population={"terran": 5_000},
                     garrison_infantry=garrison_infantry)
    state = _state(planet)
    state.ships[1] = replace(state.ships[1], recruits=recruits,
                             suits=dict(suits if suits is not None else {"marauder": 6}))
    return state, planet


def test_reinforce_garrison_transfers_atomically() -> None:
    state, planet = _owned_reinforceable_state(recruits=10, suits={"marauder": 6})
    result = reduce(state, 1, ReinforceGarrison(planet.id, "marauder", 4), CFG)
    assert len(result.ships) == 1 and len(result.planets) == 1
    new_ship, new_planet = result.ships[0], result.planets[0]
    assert new_ship.recruits == 6
    assert new_ship.suits.get("marauder", 0) == 2
    assert new_planet.garrison_infantry == 4


def test_reinforce_garrison_rejects_insufficient_recruits_or_suits() -> None:
    state, planet = _owned_reinforceable_state(recruits=2, suits={"marauder": 6})
    with pytest.raises((EconomyError, GroundForceError)):
        reduce(state, 1, ReinforceGarrison(planet.id, "marauder", 5), CFG)  # only 2 recruits
    state2, planet2 = _owned_reinforceable_state(recruits=10, suits={"marauder": 1})
    with pytest.raises((EconomyError, GroundForceError)):
        reduce(state2, 1, ReinforceGarrison(planet2.id, "marauder", 5), CFG)  # only 1 suit


def test_reinforce_garrison_rejects_non_owner() -> None:
    planet = _planet(owner=Ownership("alliance", 9), population={"vesk": 500})
    state = _state(planet)
    state.ships[1] = replace(state.ships[1], recruits=10, suits={"marauder": 6})
    with pytest.raises(EconomyError):
        reduce(state, 1, ReinforceGarrison(planet.id, "marauder", 2), CFG)


def test_reinforce_garrison_rejects_cloud_city_and_non_landable() -> None:
    for ptype in ("jovian", "asteroid_belt"):
        planet = _planet(owner=Ownership("player", 1), planet_type=ptype)
        state = _state(planet)
        state.ships[1] = replace(state.ships[1], recruits=10, suits={"marauder": 6})
        with pytest.raises(EconomyError):
            reduce(state, 1, ReinforceGarrison(planet.id, "marauder", 2), CFG)


def test_reinforce_garrison_never_creates_armor() -> None:
    """Only big-bang seeding and militia recovery ever touch `garrison_armor` — a
    reinforcement, regardless of suit class, adds infantry only (decisions #5/#9)."""
    state, planet = _owned_reinforceable_state(recruits=10, suits={"marauder": 6, "scout": 4})
    for suit_id in ("marauder", "scout"):
        result = reduce(state, 1, ReinforceGarrison(planet.id, suit_id, 2), CFG)
        assert result.planets[0].garrison_armor == 0


def test_begin_survey_rejects_assault_world_with_classifier_reason() -> None:
    planet = _planet(population={"vesk": 500})
    state = _state(planet)
    state.species = {7: _species(0.1)}
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)
    with pytest.raises(EconomyError) as excinfo:
        reduce(state, 1, BeginSurvey(planet.id), CFG)
    assert str(excinfo.value) == access.reason


def test_begin_survey_opens_on_a_friendly_world() -> None:
    planet = _planet(population={"vesk": 500})
    state = _state(planet)
    state.species = {7: _species(AMITY + 0.2)}
    result = reduce(state, 1, BeginSurvey(planet.id), CFG)
    assert result.players and result.players[0].ground_operation is not None


def test_begin_survey_on_a_cloud_city_snapshots_its_size_and_finds_nothing() -> None:
    """GW-WP17: an owned Cloud City opens a tour, not an assault; the operation
    snapshots `cloud_city_size` (so a city that grows mid-tour can't reshuffle rooms
    underfoot) and never carries any visible surface site."""
    planet = _planet(planet_type="jovian", cloud_city_size=3, owner=Ownership("player", 1))
    state = _state(planet)
    result = reduce(state, 1, BeginSurvey(planet.id), CFG)
    op = result.players[0].ground_operation
    assert isinstance(op, SurveyOperation)
    assert op.cloud_city_size == 3
    assert op.visible_discovery_ids == frozenset()


_CRATE_CFG = CFG.model_copy(update={"groundwar": CFG.groundwar.model_copy(  # type: ignore[union-attr]
    update={"cloud_city": CFG.groundwar.cloud_city.model_copy(  # type: ignore[union-attr]
        update={"crate_chance": 1.0})})})


def _cloud_city_tour_at_a_crate(equipment: int = 0) -> tuple[UniverseState, SurveyOperation, object]:
    """A landed Cloud City tour with the explorer standing on an unopened crate
    (GW-WP18) — `crate_chance` forced to 1.0 so a crate is guaranteed."""
    from edge.core.groundwar import survey as gw_survey

    from edge.core.enums import Commodity

    planet = _planet(planet_type="jovian", cloud_city_size=3, owner=Ownership("player", 1))
    state = _state(planet)
    state.ships[1] = replace(
        state.ships[1], cargo={Commodity.EQUIPMENT: equipment} if equipment else {})
    result = reduce(state, 1, BeginSurvey(planet.id), _CRATE_CFG)
    apply_result(state, result)
    op = state.players[1].ground_operation
    assert isinstance(op, SurveyOperation)
    smap = gw_survey.survey_map_for(state, op, _CRATE_CFG)
    assert smap.crates  # crate_chance 1.0 guarantees at least one
    crate = smap.crates[0]
    op = replace(op, landed=True, explorer_x=crate.x, explorer_y=crate.y)
    state.players[1] = replace(state.players[1], ground_operation=op)
    return state, op, crate


def test_open_crate_grants_a_tier_i_component() -> None:
    from edge.core.rules import OpenCrate

    state, op, crate = _cloud_city_tour_at_a_crate()
    result = reduce(state, 1, OpenCrate(op.operation_id), _CRATE_CFG)
    ship = result.ships[0]
    assert sum(n for (_, tier), n in ship.components.items() if tier.name == "I") == 1
    new_op = result.players[0].ground_operation
    assert crate.id in new_op.opened_crate_ids


def test_open_crate_rejects_an_already_opened_crate() -> None:
    from edge.core.economy import EconomyError as _EconomyError
    from edge.core.rules import OpenCrate

    state, op, crate = _cloud_city_tour_at_a_crate()
    apply_result(state, reduce(state, 1, OpenCrate(op.operation_id), _CRATE_CFG))
    with pytest.raises((_EconomyError, Exception)):  # MovementError: "already opened"
        reduce(state, 1, OpenCrate(op.operation_id), _CRATE_CFG)


def test_open_crate_refuses_and_leaves_it_unopened_when_hold_is_full() -> None:
    from edge.core.rules import OpenCrate

    state, op, crate = _cloud_city_tour_at_a_crate(equipment=60)  # fills the 60-hold ship
    with pytest.raises(EconomyError, match="no free hold"):
        reduce(state, 1, OpenCrate(op.operation_id), _CRATE_CFG)
    # Unopened — a later sale that frees hold space still lets it be opened.
    live_op = state.players[1].ground_operation
    assert crate.id not in live_op.opened_crate_ids


def test_open_crate_rejects_when_no_crate_underfoot() -> None:
    from edge.core.rules import OpenCrate

    state, op, crate = _cloud_city_tour_at_a_crate()
    off_crate = replace(op, explorer_x=0, explorer_y=0)
    state.players[1] = replace(state.players[1], ground_operation=off_crate)
    with pytest.raises(Exception, match="no crate here"):
        reduce(state, 1, OpenCrate(off_crate.operation_id), _CRATE_CFG)


def test_begin_assault_replay_is_deterministic() -> None:
    """A short command log ending in BeginAssault, replayed twice from the same seed,
    reaches a bit-identical `state_hash` and an identical `AssaultOperation`."""
    def run() -> tuple[str, object]:
        planet = _planet(population={"vesk": 500}, garrison_infantry=300, garrison_armor=15)
        state = _state(planet)
        state.species = {7: _species(0.1)}
        apply_result(state, reduce(state, 1, BeginAssault(planet.id), CFG))
        return state_hash(state), state.players[1].ground_operation

    hash_a, op_a = run()
    hash_b, op_b = run()
    assert hash_a == hash_b
    assert op_a == op_b
