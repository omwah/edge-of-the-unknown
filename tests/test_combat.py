"""WP25 — combat rounds: the escape floor, arcs, missiles, and full-fight goldens (§10, §13).

The headline invariant is the hypothesis property `flee_chance ≥ escape_floor` under
arbitrary damage / speed / interception — escape is always possible even in a crippled
ship. The reducer-level tests drive real fights through the service so the golden rail
covers a complete engagement.
"""

from __future__ import annotations

import random
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st_

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core import combat
from edge.core.aliens import HOSTILE, disposition_band
from edge.core.combat import CombatError, flee_chance
from edge.core.engine_room import derive_aspects
from edge.core.events import EncounterEnded
from edge.core.models import Encounter, EncounterFoe
from edge.core.movement import shortest_path
from edge.core.rules import (
    BuyMissiles,
    CombatAction,
    JoinGame,
    Warp,
    apply_result,
    reduce,
)
from edge.core.economy import EconomyError
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import state_hash

CFG = load_default_config()
SMALL = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(
    update={"sector_count": 400, "start_sector": 1})})


# --- the §13 escape-floor property ---------------------------------------------


@given(
    speed=st_.integers(min_value=0, max_value=50),
    bonus=st_.integers(min_value=0, max_value=20),
    interception=st_.floats(min_value=0.0, max_value=1.0),
    cloak=st_.integers(min_value=0, max_value=50),
    missing=st_.floats(min_value=0.0, max_value=1.0),
)
@settings(max_examples=300, deadline=None)
def test_flee_chance_never_below_the_floor(
    speed: int, bonus: int, interception: float, cloak: int, missing: float,
) -> None:
    """§10/§13: for ANY damage/engine/interception combination the flee probability
    never drops below the configured escape floor (and never exceeds the cap)."""
    floor = CFG.aliens.escape_floor
    chance = flee_chance(speed, bonus, interception, cloak, missing, CFG.combat, floor)
    assert floor <= chance <= CFG.combat.flee_cap


# --- pure round mechanics --------------------------------------------------------


def _foe(**kw) -> EncounterFoe:
    base = dict(ship_class_id="scout_marauder", name="Foe", hull=50, hull_max=50,
                shields=20, damage=10, firing_arc="all_round", combat_speed=4, defense=0)
    base.update(kw)
    return EncounterFoe(**base)


def _fight_state(seed: int = 3):
    state = generate(SMALL, seed)
    apply_result(state, reduce(state, 1, JoinGame(name="T"), SMALL))
    return state


def _engagement(state, foes: tuple[EncounterFoe, ...]) -> None:
    """Put the player into a synthetic engagement (state-level test rig)."""
    player = state.players[1]
    ship = state.ships[player.ship_id]
    sp = next(iter(sorted(state.species.values(), key=lambda s: s.id)))
    enc = Encounter(species_id=sp.id, sector_id=ship.sector_id, foes=foes,
                    round=0, player_shields=ship.shields)
    state.players[1] = replace(player, active_encounter=enc)


def test_fight_round_damages_shields_then_hull() -> None:
    state = _fight_state()
    _engagement(state, (_foe(shields=5, hull=500, hull_max=500, damage=30),))
    ship_before = state.ships[state.players[1].ship_id]
    result = reduce(state, 1, CombatAction(action="fight"), SMALL)
    apply_result(state, result)
    enc = state.players[1].active_encounter
    assert enc is not None and enc.round == 1
    foe = enc.foes[0]
    assert foe.shields == 0 and foe.hull < 500  # gun broke the screen, bit the hull
    # The player's fight-local shields absorbed before hull.
    took = 30 - derive_aspects(ship_before, SMALL).efficiency_bonus
    assert enc.player_shields == ship_before.shields - took
    assert state.ships[ship_before.id].hull_current == ship_before.hull_current


def test_missiles_are_finite_and_conserved() -> None:
    state = _fight_state()
    player = state.players[1]
    ship = state.ships[player.ship_id]
    state.ships[ship.id] = replace(ship, missiles=2)
    _engagement(state, (_foe(hull=10_000, hull_max=10_000, shields=0, damage=1),))
    for expected_left in (1, 0):
        result = reduce(state, 1, CombatAction(action="launch_missile"), SMALL)
        apply_result(state, result)
        assert state.ships[ship.id].missiles == expected_left
    with pytest.raises(CombatError):
        reduce(state, 1, CombatAction(action="launch_missile"), SMALL)


def test_spinal_foe_fires_every_other_round() -> None:
    """A spinal attacker recharges between volleys — even rounds are safe from it."""
    state = _fight_state()
    player = state.players[1]
    ship = state.ships[player.ship_id]
    # Deep shield pool so a round-1 spinal hit can never cripple the rig.
    state.ships[ship.id] = replace(ship, shields=100_000)
    _engagement(state, (_foe(firing_arc="spinal", damage=1000, hull=10_000,
                             hull_max=10_000, combat_speed=0),))
    # Round 1 (odd): the spinal weapon may fire (evasion contest applies).
    # Round 2 (even): it must not fire at all.
    result = reduce(state, 1, CombatAction(action="fight"), SMALL)
    apply_result(state, result)
    before = state.players[1].active_encounter.player_shields
    hull_before = state.ships[state.players[1].ship_id].hull_current
    result = reduce(state, 1, CombatAction(action="fight"), SMALL)
    apply_result(state, result)
    enc = state.players[1].active_encounter
    assert enc is not None  # a silent even round can never end the fight
    assert enc.player_shields == before  # no damage taken on the recharge round
    assert state.ships[state.players[1].ship_id].hull_current == hull_before


def test_victory_ends_the_encounter() -> None:
    state = _fight_state()
    _engagement(state, (_foe(hull=1, shields=0, damage=1),))
    result = reduce(state, 1, CombatAction(action="fight"), SMALL)
    apply_result(state, result)
    assert state.players[1].active_encounter is None
    ended = [e for e in result.events if isinstance(e, EncounterEnded)]
    assert ended and ended[0].outcome == combat.VICTORY


def test_crippled_seam_clamps_hull_and_disengages() -> None:
    """Until WP26 escape pods land, a killing volley leaves the ship at 1 hull and
    force-disengages — death is never unhandled (the documented WP26 seam)."""
    state = _fight_state()
    _engagement(state, (_foe(damage=100_000),))
    result = reduce(state, 1, CombatAction(action="fight"), SMALL)
    apply_result(state, result)
    assert state.players[1].active_encounter is None
    assert state.ships[state.players[1].ship_id].hull_current == 1
    ended = [e for e in result.events if isinstance(e, EncounterEnded)]
    assert ended and ended[0].outcome == combat.CRIPPLED


def test_flee_eventually_succeeds_even_when_crippled() -> None:
    """The floor in action: a wrecked, slow, cloakless ship against a perfect
    interceptor still escapes within a bounded number of attempts."""
    state = _fight_state()
    player = state.players[1]
    ship = state.ships[player.ship_id]
    state.ships[ship.id] = replace(ship, hull_current=1, combat_speed=0, cloak_rating=0)
    # A harmless foe so the fight can run long; interception comes from the species.
    _engagement(state, (_foe(damage=1, hull=10_000, hull_max=10_000),))
    for attempt in range(400):
        result = reduce(state, 1, CombatAction(action="flee"), SMALL)
        apply_result(state, result)
        if state.players[1].active_encounter is None:
            ended = [e for e in result.events if isinstance(e, EncounterEnded)]
            assert ended and ended[0].outcome in (combat.FLED, combat.CRIPPLED)
            if ended[0].outcome == combat.FLED:
                return
            pytest.skip("crippled before escaping (damage=1 per round — improbable)")
    raise AssertionError("never escaped in 400 attempts despite the 10% floor")


# --- StarDock missiles ------------------------------------------------------------


def test_buy_missiles_at_stardock(tmp_path: Path) -> None:
    svc = GameService.new_game(SMALL, 3, SqliteRepository(tmp_path / "m.db"),
                               created_at="1970-01-01T00:00:00Z")
    ship = svc.state.ships[svc.state.players[1].ship_id]
    dock = next(p for p in svc.state.ports.values() if p.klass.name == "STARDOCK")
    # start_sector=1 here — fly to the dock first (charted route from enrollment).
    path = shortest_path(svc.state.adjacency, ship.sector_id, dock.sector_id)
    for nxt in path[1:]:
        svc.apply(1, Warp(to_sector=nxt))
        if svc.state.players[1].active_encounter is not None:
            pytest.skip("intercepted on the way to the dock")
    before = svc.state.players[1].latinum
    svc.apply(1, BuyMissiles(count=2))
    assert svc.state.ships[ship.id].missiles == ship.missiles + 2
    assert svc.state.players[1].latinum == before - 2 * SMALL.combat.missile_price
    with pytest.raises(EconomyError):
        svc.apply(1, BuyMissiles(count=10**6))  # unaffordable


def test_buy_missiles_needs_stardock() -> None:
    state = _fight_state()
    with pytest.raises(EconomyError):
        reduce(state, 1, BuyMissiles(count=1), SMALL)  # start sector 1: no dock here


# --- the full-fight golden ---------------------------------------------------------


def _hostile(state):
    return next(
        (s for s in sorted(state.species.values(), key=lambda s: s.id)
         if disposition_band(s.base_disposition, CFG.aliens) == HOSTILE),
        None,
    )


def test_full_fight_replays_to_identical_hash(tmp_path: Path) -> None:
    """The golden rail across a complete engagement: engage → rounds → outcome →
    reload reproduces the hash (encounter + combat RNG rides the command stream)."""
    svc = GameService.new_game(SMALL, 3, SqliteRepository(tmp_path / "g.db"),
                               created_at="1970-01-01T00:00:00Z")
    sp = _hostile(svc.state)
    assert sp is not None
    ship = svc.state.ships[svc.state.players[1].ship_id]
    path = shortest_path(svc.state.adjacency, ship.sector_id, sp.sector_id)
    engaged = False
    for nxt in path[1:]:
        svc.apply(1, Warp(to_sector=nxt))
        if svc.state.players[1].active_encounter is not None:
            engaged = True
            break
    if not engaged:
        back = next(iter(svc.state.adjacency[sp.sector_id]))
        for _ in range(100):
            svc.apply(1, Warp(to_sector=back))
            if svc.state.players[1].active_encounter is not None:
                engaged = True
                break
            svc.apply(1, Warp(to_sector=sp.sector_id))
            if svc.state.players[1].active_encounter is not None:
                engaged = True
                break
    assert engaged, "seed 3 reliably intercepts en route (smoke-verified)"

    rounds = 0
    while svc.state.players[1].active_encounter is not None and rounds < 100:
        svc.apply(1, CombatAction(action="fight"))
        rounds += 1
    assert rounds and svc.state.players[1].active_encounter is None

    expected = state_hash(svc.state)
    reloaded = GameService.load_game(SMALL, SqliteRepository(tmp_path / "g.db"))
    assert state_hash(reloaded.state) == expected
