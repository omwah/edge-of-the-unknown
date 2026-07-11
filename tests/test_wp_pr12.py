"""WP-PR12 — precise Genesis errors + starbase-assault set-piece art (playtest PT-24/25).

Two thin seams:
  * `genesis_blocker` is the single human reason a `DeployGenesis` is barred; the reducer
    raises it and `PlanetDTO.genesis_blocker` shows it, so the text can never drift.
  * A starbase assault projects `EncounterDTO.target_kind == "starbase"` (+ owner archetype
    and a stable per-base seed) so the encounter screen draws port art, not a ship sprite.
"""

from __future__ import annotations

from dataclasses import replace

from helpers import generate_with_player
from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core.economy import EconomyError
from edge.core.models import EncounterFoe, Ownership, Planet
from edge.core.planets import genesis_valid_target, is_colonizable
from edge.core.rules import (
    AssaultStarbase,
    DeployGenesis,
    JoinGame,
    apply_result,
    reduce,
)
from edge.server.session import encounter_view, planet_view

CONFIG = load_default_config().model_copy(
    update={"bigbang": load_default_config().bigbang.model_copy(update={"sector_count": 120})}
)
_DEVICE = CONFIG.genesis.device_id  # type: ignore[union-attr]


# --- Genesis blocker: reducer + projection parity ----------------------------


def _eligible_planet(state: object) -> object:
    return next(pl for pl in state.planets.values()  # type: ignore[attr-defined]
                if not pl.owner.is_owned and pl.planet_type in CONFIG.genesis.eligible_types  # type: ignore[union-attr]
                and not is_colonizable(pl.planet_type, CONFIG))


def _place(state: object, planet: object, *, torpedo: bool) -> None:
    """Sit the ship over `planet`, with or without a Genesis torpedo aboard."""
    devices = {_DEVICE: 1} if torpedo else {}
    state.ships[1] = replace(  # type: ignore[attr-defined]
        state.ships[1], sector_id=planet.sector_id, devices=devices)  # type: ignore[attr-defined]


def _blocker_seen_by_reducer(state: object, planet_id: int) -> str:
    try:
        reduce(state, 1, DeployGenesis(planet_id=planet_id), CONFIG)  # type: ignore[arg-type]
    except EconomyError as exc:
        return str(exc)
    return ""


def test_no_torpedo_blocker() -> None:
    state = generate_with_player(CONFIG, 7)  # type: ignore[arg-type]
    planet = _eligible_planet(state)
    _place(state, planet, torpedo=False)
    view = planet_view(state, 1, planet.id, CONFIG)  # type: ignore[attr-defined]
    assert not view.genesis_has_device
    assert view.genesis_blocker == "no genesis torpedo aboard"
    assert _blocker_seen_by_reducer(state, planet.id) == view.genesis_blocker


def test_owned_world_blocker() -> None:
    state = generate_with_player(CONFIG, 7)  # type: ignore[arg-type]
    owned = next(pl for pl in state.planets.values() if pl.owner.is_owned)
    _place(state, owned, torpedo=True)
    view = planet_view(state, 1, owned.id, CONFIG)
    assert view.genesis_has_device and not view.genesis_eligible
    assert view.genesis_blocker == "that world is claimed — genesis only re-forms unclaimed worlds"
    assert _blocker_seen_by_reducer(state, owned.id) == view.genesis_blocker


def test_ineligible_type_blocker_names_the_type() -> None:
    state = generate_with_player(CONFIG, 7)  # type: ignore[arg-type]
    planet = _eligible_planet(state)
    # Retype it to an asteroid belt — a spatial feature Genesis can never re-form.
    state.planets[planet.id] = replace(state.planets[planet.id], planet_type="asteroid_belt")
    _place(state, planet, torpedo=True)
    view = planet_view(state, 1, planet.id, CONFIG)
    assert view.genesis_has_device and not view.genesis_eligible
    assert view.genesis_blocker == "a asteroid_belt world cannot be re-formed by genesis"
    assert _blocker_seen_by_reducer(state, planet.id) == view.genesis_blocker


def test_valid_target_has_no_blocker_and_deploys() -> None:
    state = generate_with_player(CONFIG, 7)  # type: ignore[arg-type]
    planet = _eligible_planet(state)
    _place(state, planet, torpedo=True)
    view = planet_view(state, 1, planet.id, CONFIG)
    assert view.genesis_has_device and view.genesis_eligible and view.genesis_blocker == ""
    assert genesis_valid_target(state.planets[planet.id], CONFIG)
    apply_result(state, reduce(state, 1, DeployGenesis(planet_id=planet.id), CONFIG))
    assert is_colonizable(state.planets[planet.id].planet_type, CONFIG)  # re-formed


# --- starbase assault set-piece art ------------------------------------------

SMALL = CONFIG.model_copy(update={"bigbang": CONFIG.bigbang.model_copy(
    update={"sector_count": 400, "start_sector": 1})})


def _assault_state() -> object:
    state = generate(SMALL, 3)
    apply_result(state, reduce(state, 1, JoinGame(name="T"), SMALL))
    ship = state.ships[state.players[1].ship_id]
    from edge.core.engine_room import build_layouts
    from edge.core.models import Starbase
    base = Starbase(id=77, sector_id=ship.sector_id, planet_id=500,
                    ship_class_id="orbital_platform", owner=Ownership("alliance", 2),
                    subsystems=build_layouts(SMALL.starbase.subsystems))
    state.planets[500] = Planet(id=500, sector_id=ship.sector_id, name="Holt",
                                planet_type="barren", owner=Ownership("alliance", 2), starbase_id=77)
    state.starbases[77] = base
    apply_result(state, reduce(state, 1, AssaultStarbase(starbase_id=77), SMALL))
    return state


def test_assault_encounter_projects_starbase_target() -> None:
    state = _assault_state()
    view = encounter_view(state, 1, SMALL)  # type: ignore[arg-type]
    assert view is not None
    assert view.target_kind == "starbase"
    assert view.target_seed == 77  # the stable per-base art seed


def test_ordinary_ship_encounter_stays_ship() -> None:
    """A regression guard: a base-less encounter keeps ship art (target_kind default)."""
    state = _assault_state()
    player = state.players[1]
    enc = player.active_encounter
    assert enc is not None
    # Drop the base link but keep a foe → an ordinary ship fight.
    foe = EncounterFoe(ship_class_id="orbital_platform", name="Marauder", hull=100, hull_max=100,
                       shields=0, damage=1, firing_arc="ahead", combat_speed=1, defense=0)
    state.players[1] = replace(player, active_encounter=replace(enc, starbase_id=None, foes=(foe,)))
    view = encounter_view(state, 1, SMALL)  # type: ignore[arg-type]
    assert view is not None
    assert view.target_kind == "ship"
    assert view.target_seed == 0
