"""WP-PR07 — settling more colonists onto an already-owned colony (playtest PT-11).

`SettleColonists` is the top-up counterpart to `Colonize`: it adds people from the ship's
berth to a world the player already owns, clamped to what is aboard and the world's remaining
habitability. Distinct command, distinct event — it never claims and never touches cargo holds.
"""

from __future__ import annotations


import pytest

from edge.config import load_default_config
from edge.core.economy import EconomyError
from edge.core.events import ColonistsSettled
from edge.core.models import (
    Game, Ownership, Planet, Player, Sector, Ship, UniverseState,
)
from edge.core.rules import SettleColonists, apply_result, reduce

CFG = load_default_config()


def _state(*, owner: Ownership, ptype: str = "terrestrial_warm", colonists: int = 100,
           cap: int = 1000, aboard: int = 300) -> UniverseState:
    game = Game(id=1, seed=1, config_version=CFG.config_version,
                created_at="1970-01-01T00:00:00Z", core_governing_alliance_id=1)
    state = UniverseState.new(game)
    state.sectors[1] = Sector(id=1, region_id=1, warps_out=(), distance_band="Frontier")
    state.rebuild_adjacency()
    state.planets[1] = Planet(id=1, sector_id=1, name="Eden", planet_type=ptype,
                              owner=owner, colonists=colonists, habitability_cap=cap)
    state.ships[1] = Ship(id=1, type_id="trailblazer", name="T", owner_player_id=1,
                          sector_id=1, holds_total=20, hull_current=200, hull_max=200,
                          shields=50, warp_speed=3, combat_speed=3, turns_per_warp=1,
                          colonists=aboard, colonist_capacity=1000)
    state.players[1] = Player(id=1, name="T", ship_id=1, latinum=5000, turns_remaining=100)
    return state


def test_settle_tops_up_owned_colony() -> None:
    state = _state(owner=Ownership("player", 1))
    result = reduce(state, 1, SettleColonists(1, 150), CFG)
    apply_result(state, result)
    assert state.planets[1].colonists == 250 and state.ships[1].colonists == 150
    assert any(isinstance(e, ColonistsSettled) and e.colonists == 150 for e in result.events)


def test_settle_clamps_to_aboard_and_habitability() -> None:
    # Only 40 berths free below the cap; ship carries 300 — accept 40.
    state = _state(owner=Ownership("player", 1), colonists=960, cap=1000, aboard=300)
    result = reduce(state, 1, SettleColonists(1, 10**9), CFG)
    apply_result(state, result)
    assert state.planets[1].colonists == 1000 and state.ships[1].colonists == 260


def test_settle_rejected_when_at_cap() -> None:
    state = _state(owner=Ownership("player", 1), colonists=1000, cap=1000)
    with pytest.raises(EconomyError, match="habitability cap"):
        reduce(state, 1, SettleColonists(1, 10), CFG)


def test_settle_rejected_on_unowned_world() -> None:
    state = _state(owner=Ownership("none"))
    with pytest.raises(EconomyError, match="do not own"):
        reduce(state, 1, SettleColonists(1, 10), CFG)


def test_settle_rejected_with_no_colonists_aboard() -> None:
    state = _state(owner=Ownership("player", 1), aboard=0)
    with pytest.raises(EconomyError, match="no colonists aboard"):
        reduce(state, 1, SettleColonists(1, 10), CFG)


def test_settle_rejected_on_uncolonizable_world() -> None:
    state = _state(owner=Ownership("player", 1), ptype="barren", cap=0)
    with pytest.raises(EconomyError, match="cannot hold colonists"):
        reduce(state, 1, SettleColonists(1, 10), CFG)


# --- WP-PR07 §8.1 follow-up: commodity conservation under transfer sequences ---

from dataclasses import replace  # noqa: E402

from hypothesis import given, settings  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from edge.core.enums import Commodity  # noqa: E402
from edge.core.rules import TransferCargo  # noqa: E402


def _transfer_state() -> UniverseState:
    """An owned colony with stores + a ship with cargo and free holds, same sector."""
    state = _state(owner=Ownership("player", 1))
    planet = state.planets[1]
    state.planets[1] = replace(planet, stores={Commodity.FUEL_ORE: 50, Commodity.EQUIPMENT: 20})
    ship = state.ships[1]
    state.ships[1] = replace(ship, holds_total=200,
                             cargo={Commodity.ORGANICS: 40, Commodity.EQUIPMENT: 10})
    return state


@settings(max_examples=60, deadline=None)
@given(steps=st.lists(
    st.tuples(st.sampled_from(list(Commodity)), st.integers(-999, 999), st.booleans()),
    max_size=25))
def test_transfer_cargo_conserves_each_commodity(steps) -> None:
    """Every `TransferCargo` moves goods between ship holds and colony stores without
    minting or destroying any — the per-commodity total (aboard + in stores) is invariant."""
    state = _transfer_state()

    def totals() -> dict[Commodity, int]:
        ship, planet = state.ships[1], state.planets[1]
        return {c: ship.cargo.get(c, 0) + planet.stores.get(c, 0) for c in Commodity}

    before = totals()
    for commodity, units, to_planet in steps:
        try:
            apply_result(state, reduce(
                state, 1, TransferCargo(1, commodity, units, to_planet=to_planet), CFG))
        except EconomyError:
            pass  # rejected transfers (non-positive / nothing to move) leave state untouched
    assert totals() == before
    # And nothing ever goes negative (the §13 invariant).
    ship, planet = state.ships[1], state.planets[1]
    assert all(v >= 0 for v in ship.cargo.values()) and all(v >= 0 for v in planet.stores.values())
