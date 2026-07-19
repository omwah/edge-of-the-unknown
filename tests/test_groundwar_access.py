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
from edge.core.rules import BeginSurvey, reduce
from edge.core.economy import EconomyError
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


def test_inhabited_cloud_city_is_orbital_only_until_gate() -> None:
    state, planet = _pair(_planet(planet_type="jovian", cloud_city_size=2))
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, OrbitalOnly)
    assert "Cloud City" in access.reason


# --- survey routing (D1: uninhabited / friendly) -----------------------------


def test_uninhabited_landable_world_surveys_without_settlements() -> None:
    state, planet = _pair(_planet())
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Survey)
    assert access.settlements is False


def test_player_owned_inhabited_world_surveys_with_settlements() -> None:
    state, planet = _pair(_planet(owner=Ownership("player", 1), colonists=500))
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Survey)
    assert access.settlements is True


def test_own_alliance_world_surveys() -> None:
    state, planet = _pair(_planet(owner=Ownership("alliance", 5), colonists=500),
                          player_alliance=5)
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Survey)


def test_friendly_species_world_surveys() -> None:
    planet = _planet(inhabited_by_species_id=7)
    state = _state(planet)
    state.species = {7: _species(AMITY + 0.2)}
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Survey)
    assert access.settlements is True


# --- assault routing (D1: inhabited & below friendly) ------------------------


def test_hostile_species_world_assaults() -> None:
    planet = _planet(inhabited_by_species_id=7)
    state = _state(planet)
    state.species = {7: _species(0.1)}
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)
    assert access.inhabited is True
    assert access.droppable  # no defences standing


def test_neutral_species_world_still_assaults() -> None:
    # Below amity but above hostility — D1 routes it to assault all the same.
    planet = _planet(inhabited_by_species_id=7)
    state = _state(planet)
    state.species = {7: _species(AMITY - 0.05)}
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)


def test_rival_alliance_world_assaults() -> None:
    state, planet = _pair(_planet(owner=Ownership("alliance", 6), colonists=500),
                          player_alliance=5)
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)
    assert access.owner == Ownership("alliance", 6)


def test_grudge_pushes_a_mild_species_into_assault() -> None:
    from edge.core.models import Grudge
    planet = _planet(inhabited_by_species_id=7)
    state = _state(planet)
    state.species = {7: _species(AMITY + 0.05)}  # nominally friendly...
    grudged = replace(state.players[1], grudges={"vesk": Grudge(
        holder="vesk", target="player", cause="x", severity=0.3, created_day=0, duration_days=30)})
    access = ground_access(state, grudged, planet, CFG)
    assert isinstance(access, Assault)  # ...but the grudge drops it below amity


# --- Core sanctuary (G13) ----------------------------------------------------


def test_core_world_never_assaults() -> None:
    planet = _planet(inhabited_by_species_id=7)
    state = _state(planet, core=True)
    state.species = {7: _species(0.05)}  # deeply hostile
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, OrbitalOnly)
    assert "Core" in access.reason


# --- siege-ladder blockers (G12) ---------------------------------------------


def test_live_citadel_gun_blocks_the_drop() -> None:
    planet = _planet(inhabited_by_species_id=7, citadel_level=GUN_MIN, gun_integrity=50)
    state = _state(planet)
    state.species = {7: _species(0.1)}
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)
    assert not access.droppable
    assert access.blockers[0] == "silence the citadel gun first"


# --- assault disabled --------------------------------------------------------


def test_hostile_world_is_orbital_only_when_citadels_disabled() -> None:
    cfg = CFG.model_copy(update={"citadels": None})
    planet = _planet(inhabited_by_species_id=7)
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


def test_begin_survey_rejects_assault_world_with_classifier_reason() -> None:
    planet = _planet(inhabited_by_species_id=7)
    state = _state(planet)
    state.species = {7: _species(0.1)}
    access = ground_access(state, state.players[1], planet, CFG)
    assert isinstance(access, Assault)
    with pytest.raises(EconomyError) as excinfo:
        reduce(state, 1, BeginSurvey(planet.id), CFG)
    assert str(excinfo.value) == access.reason


def test_begin_survey_opens_on_a_friendly_world() -> None:
    planet = _planet(inhabited_by_species_id=7)
    state = _state(planet)
    state.species = {7: _species(AMITY + 0.2)}
    result = reduce(state, 1, BeginSurvey(planet.id), CFG)
    assert result.players and result.players[0].ground_operation is not None
