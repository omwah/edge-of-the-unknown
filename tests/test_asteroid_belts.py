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
    # Through `normalize_belt`, as the big bang builds one — which is what seeds the finite ore
    # reserve (PT-52). A belt straight out of the constructor has none, and would read as spent.
    state.planets[1] = normalize_belt(
        Planet(id=1, sector_id=1, name="Rubble", planet_type="asteroid_belt"), CFG)
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
    assert belt_mining_yield(state.planets[1], CFG) is None
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


# --- a belt is finite (PT-52, WP-PR2-13) --------------------------------------


def test_generation_seeds_a_band_weighted_reserve() -> None:
    """Every belt is born with ore in it, and the deep fields are the rich ones."""
    from collections import defaultdict

    from edge.bigbang.generator import generate

    state = generate(CFG, 4)
    belts = [p for p in state.planets.values() if p.planet_type == "asteroid_belt"]
    assert belts, "seed 4 generated no belts to check"
    assert all(b.ore_reserve == b.ore_reserve_max > 0 for b in belts)  # full, and seeded

    by_band: dict[str, list[int]] = defaultdict(list)
    for b in belts:
        by_band[state.sectors[b.sector_id].distance_band].append(b.ore_reserve_max)
    means = {band: sum(v) / len(v) for band, v in by_band.items() if v}
    if "Hub" in means and "Void" in means:  # the gradient the band scale encodes
        assert means["Void"] > means["Hub"]


def test_mining_draws_the_reserve_down_and_never_regrows() -> None:
    state = _state_with_belt()
    belt = state.planets[1]
    start = belt.ore_reserve
    assert start > 0

    result = reduce(state, 1, MineBelt(planet_id=1), CFG)
    apply_result(state, result)
    # The reserve loses exactly what went aboard — the ship's 20 holds cap this haul below the
    # nominal 50-unit yield, and ore that never left the field is still in it.
    hauled = next(e for e in result.events if isinstance(e, BeltMined)).amount
    assert hauled == state.ships[1].holds_total == 20
    assert state.planets[1].ore_reserve == start - hauled
    assert state.planets[1].ore_reserve_max == start  # the ceiling is what it *was*

    # The reserve is not replenished by a production tick — a worked field stays worked.
    from edge.core.planets import produce
    assert produce(state.planets[1], CFG).ore_reserve == start - hauled


def test_a_haul_is_clamped_to_the_ore_actually_left() -> None:
    state = _state_with_belt()
    state.planets[1] = replace(state.planets[1], ore_reserve=7)  # nearly spent
    result = reduce(state, 1, MineBelt(planet_id=1), CFG)
    apply_result(state, result)
    mined = next(e for e in result.events if isinstance(e, BeltMined))
    assert mined.amount == 7  # not the nominal `asteroid_mining` haul
    assert state.ships[1].cargo[Commodity.EQUIPMENT] == 7
    assert state.planets[1].ore_reserve == 0


def test_a_worked_out_belt_rejects_and_projects_no_haul() -> None:
    state = _state_with_belt()
    state.planets[1] = replace(state.planets[1], ore_reserve=0)
    with pytest.raises(EconomyError, match="worked out"):
        reduce(state, 1, MineBelt(planet_id=1), CFG)
    view = planet_view(state, 1, 1, CFG)
    assert view.mine_yield == 0  # the affordance greys out — legality and UI agree
    assert view.ore_reserve == 0 and view.ore_reserve_max > 0


def test_an_unseeded_belt_is_full_not_spent() -> None:
    """`normalize_belt` converges a pre-PT-52 (reserve-less) belt on a full field."""
    raw = Planet(id=9, sector_id=1, name="Legacy", planet_type="asteroid_belt")
    assert raw.ore_reserve == 0 and raw.ore_reserve_max == 0
    fixed = normalize_belt(raw, CFG)
    assert fixed.ore_reserve == fixed.ore_reserve_max == CFG.planets.belt_reserve_base
    assert normalize_belt(fixed, CFG) is fixed  # still idempotent

    spent = replace(fixed, ore_reserve=0)  # a *genuinely* exhausted belt is left alone
    assert normalize_belt(spent, CFG).ore_reserve == 0


def test_belt_art_thins_as_the_field_empties() -> None:
    from edge.tui import art_adapter

    def rocks(depletion: float) -> set[tuple[int, int]]:
        art = art_adapter.sprite("planet", "asteroid_belt", seed=3, width=24, height=8,
                                 depletion=depletion)
        return {(x, y) for y, line in enumerate(art.plain.split("\n"))
                for x, ch in enumerate(line) if ch != " "}

    full, half, spent = rocks(0.0), rocks(0.5), rocks(1.0)
    assert full and not spent  # a worked-out field is empty rock
    assert half < full  # …and the rocks that remain are the *same* rocks, not a redraw
