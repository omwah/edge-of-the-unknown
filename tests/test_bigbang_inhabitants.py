"""GW-WP09-PRE — the inhabited universe: native peoples, populations, holdings.

Before this pass, nothing in the tree ever set a native `Planet.population`, so a
generated universe held no inhabitants — and because the ground-access classifier keys
"inhabited" off exactly that (plus Cloud Cities), **no generated world could route to
assault at all**. These tests pin the seeding contract and, most importantly, the
end-to-end fact that a real generated world now reaches `Assault` through the
production classifier rather than through hand-built state.
"""

from __future__ import annotations

import pytest

from edge.bigbang.generator import generate
from edge.bigbang.inhabitants import (
    ground_target_counts,
    is_assaultable_for_a_fresh_player,
    seed_inhabitants,
    target_floors,
)
from edge.bigbang.validate import ValidationError, validate
from edge.config import load_default_config
from edge.core.aliens import resolve_species_by_kind
from edge.core.groundwar.access import Assault, Survey, ground_access
from edge.core.models import UniverseState
from edge.core.planets import colonist_capacity, native_population_key
from edge.core.starbases import is_operational
from helpers import generate_with_player

CFG = load_default_config()
SEEDS = (1986, 2, 7, 42)


@pytest.fixture(scope="module")
def world() -> UniverseState:
    return generate(CFG, 1986)


def _inhabited(state: UniverseState) -> list[object]:
    return [p for p in state.planets.values() if p.population]


# --- the gap this work package closes ----------------------------------------


def test_a_generated_universe_has_inhabitants(world: UniverseState) -> None:
    """The whole point: worlds carry peoples, not just types and owners."""
    inhabited = _inhabited(world)
    assert inhabited, "the big bang seeded no inhabitants at all"
    assert all(p.colonists > 0 for p in inhabited), "an inhabited world with nobody on it"


def test_a_real_generated_world_routes_to_assault() -> None:
    """The case that could not be written before this WP without hand-building state.

    Drives the production `ground_access` classifier — not the generation-time helper —
    so this proves the tactical path has live targets, which GW-WP09-WP12 build against.
    """
    state = generate_with_player(CFG, 1986)
    player = state.players[1]
    modes = [ground_access(state, player, p, CFG) for p in state.planets.values()]
    assaults = [m for m in modes if isinstance(m, Assault)]
    surveys = [m for m in modes if isinstance(m, Survey)]
    assert assaults, "no generated world routes to assault"
    assert any(m.settlements for m in surveys), "no friendly world offers survey settlements"


def test_unaligned_worlds_keep_no_owner_beside_their_people(world: UniverseState) -> None:
    """The D2 protectorate's subject: a people with no flag (`owner=none` + species id).

    Risk 6 in the plan — surrender must record control without misusing `owner=none`,
    which requires that shape to exist in the first place.
    """
    unaligned = [p for p in _inhabited(world) if not p.owner.is_owned]
    assert unaligned, "no unaligned inhabited worlds — the protectorate has no subject"


# --- coherence with the systems already shipped ------------------------------


def test_population_never_exceeds_what_the_world_can_hold(world: UniverseState) -> None:
    for planet in _inhabited(world):
        capacity = colonist_capacity(planet, CFG)
        assert capacity > 0, f"planet {planet.id} holds people it has no room for"
        assert planet.colonists <= capacity


def test_no_derelict_base_sits_on_an_inhabited_world(world: UniverseState) -> None:
    """A derelict must sit on an unowned *and uninhabited* world (the §4.2 starbase
    rule the validator enforces) — so the seeding pass skips those worlds, exactly as
    a bloc's home cluster does when it claims territory."""
    for planet in _inhabited(world):
        if planet.starbase_id is None:
            continue
        base = world.starbases.get(planet.starbase_id)
        assert base is None or is_operational(base)


def test_the_core_is_lived_in_and_still_sanctuary(world: UniverseState) -> None:
    core = [p for p in world.planets.values()
            if world.sectors[p.sector_id].is_galactic_core]
    assert any(p.population for p in core), "an empty capital"
    # G13 holds regardless of who lives there.
    assert not any(is_assaultable_for_a_fresh_player(world, p, CFG) for p in core)


def test_citadel_holdings_are_coherent(world: UniverseState) -> None:
    """L2+ raises the fixed gun — a rung of the orbital ladder a ground assault must
    clear first (G12) — and only a fortified world banks a treasury."""
    assert CFG.citadels is not None
    for planet in _inhabited(world):
        if planet.citadel_level >= CFG.citadels.gun_min_level:
            assert planet.gun_integrity > 0
        else:
            assert planet.gun_integrity == 0
        if planet.citadel_level == 0:
            assert planet.treasury == 0


# --- determinism + the generation invariant ----------------------------------


def test_seeding_is_deterministic_for_a_seed() -> None:
    a, b = generate(CFG, 7), generate(CFG, 7)
    assert {p.id: (p.population, p.citadel_level) for p in a.planets.values()} == \
           {p.id: (p.population, p.citadel_level) for p in b.planets.values()}


def test_re_seeding_an_already_seeded_state_changes_nothing(world: UniverseState) -> None:
    """The pass is a function of (seed, world), so running it twice is a no-op — it
    only ever settles worlds that have no people yet."""
    before = {p.id: p.population for p in world.planets.values()}
    seed_inhabitants(world, CFG)
    assert {p.id: p.population for p in world.planets.values()} == before


@pytest.mark.parametrize("seed", SEEDS)
def test_every_seed_fields_its_target_floor(seed: int) -> None:
    """The floor holds *by construction* — the top-up settles wary peoples onto free
    frontier worlds rather than leaving it to chance, because the shortage that
    produces an empty universe is in the species draw, which retrying does not fix."""
    state = generate(CFG, seed)
    assaultable, friendly = ground_target_counts(state, CFG)
    assault_floor, friendly_floor = target_floors(state, CFG)
    assert assaultable >= assault_floor
    assert friendly >= friendly_floor
    validate(state, CFG)  # the shipped universe satisfies its own invariant


def test_the_floor_is_capped_by_what_a_universe_can_supply() -> None:
    """A configured floor is a target for a full-size universe, not a law of nature.

    A tiny universe — or a cast drawn with no below-amity species, which the friendly
    roster skew makes possible — cannot field targets, and rejecting it would make
    generation impossible rather than correct.
    """
    from dataclasses import replace

    state = generate(CFG, 1986)
    # A wholly peaceable cast — every species at or above amity, which the friendly
    # roster skew really does produce (a 60-sector universe draws one routinely).
    amity = CFG.aliens.amity_threshold
    for sid, species in list(state.species.items()):
        state.species[sid] = replace(species, base_disposition=max(species.base_disposition, amity))
    assert target_floors(state, CFG)[0] == 0, "a peaceable universe owes no targets"
    validate(state, CFG)  # ... and it is a valid universe, not a failed one


def test_the_invariant_rejects_a_universe_that_could_field_targets_but_does_not(
    world: UniverseState,
) -> None:
    """Guard against the seeding pass silently regressing to doing nothing."""
    from dataclasses import replace

    stripped = generate(CFG, 1986)
    for pid, planet in list(stripped.planets.items()):
        stripped.planets[pid] = replace(planet, population={})
    with pytest.raises(ValidationError, match="assaultable"):
        validate(stripped, CFG)


# --- the orbit view names who lives there -------------------------------------


def test_the_orbit_view_names_a_worlds_people() -> None:
    """The World & colony panel reads the inhabiting species off the projection."""
    from edge.server import session

    state = generate_with_player(CFG, 1986)
    inhabited = next(p for p in state.planets.values() if p.population)
    view = session.planet_view(state, 1, inhabited.id, CFG)
    key = native_population_key(inhabited, CFG)
    assert key is not None
    species = resolve_species_by_kind(state, key, CFG.roster)
    assert species is not None
    assert view.species == species.name


def test_a_world_the_player_settles_is_peopled_by_their_own_kind() -> None:
    """A colony's people came from the Stardock recruitment office, so the orbit view
    names the roster's `player_species_id` rather than leaving the world blank — it has
    a population, so it is not uninhabited (GW-WP09-PRE)."""
    from dataclasses import replace

    from edge.core.models import Ownership
    from edge.server import session

    state = generate_with_player(CFG, 1986)
    target = next(p for p in state.planets.values()
                  if not p.population and colonist_capacity(p, CFG) > 0)
    state.planets[target.id] = replace(
        target, owner=Ownership("player", 1), population={"terran": 500})
    view = session.planet_view(state, 1, target.id, CFG)
    assert CFG.roster is not None and CFG.roster.player_species_id == "terran"
    assert view.species == "Terrans"


def test_an_empty_world_names_nobody() -> None:
    from edge.server import session

    state = generate_with_player(CFG, 1986)
    empty = next(p for p in state.planets.values() if not p.population)
    assert session.planet_view(state, 1, empty.id, CFG).species == ""
