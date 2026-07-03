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
from edge.core.enums import Commodity, Subsystem
from edge.core.events import (
    ComponentKnockedOut,
    EncounterEnded,
    SalvageCollected,
    ShipDestroyed,
)
from edge.core.models import Encounter, EncounterFoe
from edge.core.movement import shortest_path
from edge.core.dev import DevPatch
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


def test_destruction_issues_the_escape_pod() -> None:
    """Hull 0 (§10, WP26): the ship, cargo, and stores are lost; the escape pod —
    a real config hull — is issued in place and the encounter ends."""
    state = _fight_state()
    player = state.players[1]
    ship = state.ships[player.ship_id]
    state.ships[ship.id] = replace(
        ship, cargo={Commodity.FUEL_ORE: 10}, missiles=3, repair_kits=2)
    _engagement(state, (_foe(damage=100_000),))
    result = reduce(state, 1, CombatAction(action="fight"), SMALL)
    apply_result(state, result)
    assert state.players[1].active_encounter is None
    pod = state.ships[player.ship_id]
    pod_class = SMALL.ship_class(SMALL.combat.escape_pod_class)
    assert pod.type_id == pod_class.id
    assert pod.hull_current == pod_class.hull_max  # the pod arrives intact
    assert pod.sector_id == ship.sector_id  # it limps home from where the fight ended
    assert not pod.cargo and not pod.components  # everything went down with the ship
    assert pod.missiles == 0 and pod.repair_kits == 0
    destroyed = [e for e in result.events if isinstance(e, ShipDestroyed)]
    assert destroyed and destroyed[0].lost_ship == ship.type_id
    ended = [e for e in result.events if isinstance(e, EncounterEnded)]
    assert ended and ended[0].outcome == combat.DESTROYED


def _forced_knockout_config(subsystem: str):
    """A config where every hull-reaching volley knocks a component out of exactly
    `subsystem` (weight 1 there, 0 everywhere else)."""
    weights = {s: 0.0 for s in ("spindrive", "thrusters", "screens", "main_gun")}
    weights[subsystem] = 1.0
    return SMALL.model_copy(update={"combat": SMALL.combat.model_copy(
        update={"knockout_chance": 1.0, "knockout_weights": weights})})


def test_knockout_degrades_exactly_the_owning_subsystem() -> None:
    """§4.1/WP26: a hull-reaching volley knocks out one component of the weighted
    subsystem, and only that subsystem's derived aspect degrades."""
    cfg = _forced_knockout_config("thrusters")
    state = _fight_state()
    player = state.players[1]
    ship = state.ships[player.ship_id]
    state.ships[ship.id] = replace(ship, shields=0)  # bare hull: the volley localizes
    _engagement(state, (_foe(damage=10, hull=10_000, hull_max=10_000),))
    before = derive_aspects(state.ships[ship.id], cfg)
    result = reduce(state, 1, CombatAction(action="fight"), cfg)
    apply_result(state, result)
    knocked = [e for e in result.events if isinstance(e, ComponentKnockedOut)]
    assert len(knocked) == 1 and knocked[0].subsystem == "thrusters"
    after_ship = state.ships[ship.id]
    after = derive_aspects(after_ship, cfg)
    assert after.combat_speed < before.combat_speed  # the owning aspect degraded…
    assert after.warp_speed == before.warp_speed     # …and only that one
    assert after.shields == before.shields
    assert after.gun_damage == before.gun_damage
    # Derive-on-write: the stored scalar matches the derived value immediately.
    assert after_ship.combat_speed == after.combat_speed


def test_field_patch_restores_the_knocked_component() -> None:
    """A repair kit field-patches the knocked slot back to function mid-fight (§4.1)."""
    cfg = _forced_knockout_config("thrusters")
    state = _fight_state()
    player = state.players[1]
    ship = state.ships[player.ship_id]
    state.ships[ship.id] = replace(ship, shields=0, repair_kits=1)
    _engagement(state, (_foe(damage=10, hull=10_000, hull_max=10_000),))
    healthy = derive_aspects(state.ships[ship.id], cfg).combat_speed
    result = reduce(state, 1, CombatAction(action="fight"), cfg)
    apply_result(state, result)
    knocked = [e for e in result.events if isinstance(e, ComponentKnockedOut)]
    assert knocked
    sub, idx = Subsystem(knocked[0].subsystem), knocked[0].slot_index
    # Deep fight-local shields so the patch round's volley can't localize again
    # (knockout only rolls on hull-reaching damage).
    enc = state.players[1].active_encounter
    state.players[1] = replace(
        state.players[1], active_encounter=replace(enc, player_shields=10_000))
    result = reduce(state, 1, CombatAction(action="field_patch", subsystem=sub, slot_index=idx), cfg)
    apply_result(state, result)
    patched = state.ships[ship.id]
    assert patched.repair_kits == 0
    slot = patched.subsystems[sub].slots[idx]
    assert slot is not None and not slot.knocked_out
    assert derive_aspects(patched, cfg).combat_speed == healthy  # fully recovered


def test_salvage_is_conserved_and_bounded() -> None:
    """Victory salvage (§10/WP26): the latinum gained equals the event's amount and
    sits inside the configured 10–20% window; forced component drops land as loose
    Tier-I parts in the hold."""
    cfg = SMALL.model_copy(update={"combat": SMALL.combat.model_copy(
        update={"salvage_component_chance": 1.0})})
    state = _fight_state()
    player = state.players[1]
    before_latinum = player.latinum
    foes = (_foe(hull=1, shields=0, damage=1), _foe(hull=1, shields=0, damage=1))
    _engagement(state, foes)
    # Two 1-hull foes die to one gun rate-2 round? No — one fight action hits one
    # target; run rounds until victory.
    for _ in range(4):
        result = reduce(state, 1, CombatAction(action="fight"), cfg)
        apply_result(state, result)
        if state.players[1].active_encounter is None:
            break
    assert state.players[1].active_encounter is None
    salvage = [e for e in result.events if isinstance(e, SalvageCollected)]
    assert len(salvage) == 1
    ev = salvage[0]
    assert state.players[1].latinum == before_latinum + ev.latinum
    cc = cfg.combat
    lo = sum(round(f.hull_max * cc.salvage_hull_value * cc.salvage_frac_min) for f in foes)
    hi = sum(round(f.hull_max * cc.salvage_hull_value * cc.salvage_frac_max) for f in foes)
    assert lo <= ev.latinum <= hi + 1  # per-wreck rounding
    assert len(ev.components) == len(foes)  # chance forced to 1, holds are free
    ship = state.ships[player.ship_id]
    assert sum(ship.components.values()) == len(ev.components)


def test_salvage_components_need_a_free_hold() -> None:
    """With the holds full the parts are left adrift — cargo is never overwritten."""
    cfg = SMALL.model_copy(update={"combat": SMALL.combat.model_copy(
        update={"salvage_component_chance": 1.0})})
    state = _fight_state()
    player = state.players[1]
    ship = state.ships[player.ship_id]
    state.ships[ship.id] = replace(ship, cargo={Commodity.FUEL_ORE: ship.holds_total})
    _engagement(state, (_foe(hull=1, shields=0, damage=1),))
    result = reduce(state, 1, CombatAction(action="fight"), cfg)
    apply_result(state, result)
    salvage = [e for e in result.events if isinstance(e, SalvageCollected)]
    assert salvage and salvage[0].components == ()
    assert not state.ships[ship.id].components
    assert salvage[0].latinum > 0  # the latinum still pays out


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
            assert ended and ended[0].outcome in (combat.FLED, combat.DESTROYED)
            if ended[0].outcome == combat.FLED:
                return
            pytest.skip("destroyed before escaping (damage=1 per round — improbable)")
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


def test_pod_flow_replays_to_identical_hash(tmp_path: Path) -> None:
    """The WP26 golden: a fight lost to destruction reloads to the identical hash,
    with the escape pod (and everything it is *not* carrying) reconstructed."""
    svc = GameService.new_game(SMALL, 3, SqliteRepository(tmp_path / "p.db"),
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
            for hop in (back, sp.sector_id):
                svc.apply(1, Warp(to_sector=hop))
                if svc.state.players[1].active_encounter is not None:
                    engaged = True
                    break
            if engaged:
                break
    assert engaged, "seed 3 reliably intercepts en route (smoke-verified)"

    # On a 1-hull ship the first volley that defeats the shields is the end.
    svc.apply(1, DevPatch(op="set", target="ship.hull_current", value=1))
    outcome = None
    for _ in range(100):
        events = svc.apply(1, CombatAction(action="fight"))
        ended = [e for e in events if isinstance(e, EncounterEnded)]
        if ended:
            outcome = ended[0].outcome
            break
    if outcome != combat.DESTROYED:
        pytest.skip("won or fled on 1 hull before the pack broke through (improbable)")
    pod = svc.state.ships[svc.state.players[1].ship_id]
    assert pod.type_id == SMALL.combat.escape_pod_class

    expected = state_hash(svc.state)
    reloaded = GameService.load_game(SMALL, SqliteRepository(tmp_path / "p.db"))
    assert state_hash(reloaded.state) == expected
    assert reloaded.state.ships[pod.id].type_id == SMALL.combat.escape_pod_class


def test_encounter_end_writes_the_last_combat_record() -> None:
    """WP29 (H5): every encounter end stamps `Player.last_combat` — the replay-safe
    source of the `just_fled_combat` dialogue fact, written by the reducer, never the UI."""
    from edge.core.models import LastCombat

    state = _fight_state()
    _engagement(state, (_foe(hull=1, shields=0, damage=1),))
    kind = state.species[state.players[1].active_encounter.species_id].roster_id
    apply_result(state, reduce(state, 1, CombatAction(action="fight"), SMALL))
    assert state.players[1].last_combat == LastCombat(
        species=kind, outcome=combat.VICTORY, day=state.game.day_number)


# --- WP31: combat dialogue ----------------------------------------------------------


def test_round_beat_taunts_and_renders_keyed_to_round_facts() -> None:
    """The pack taunts each ongoing round; the beat is keyed to the post-round encounter
    facts and the encounter screen renders the same line (shared fact assembly)."""
    from edge.core.config import RosterConfig
    from edge.server import session

    state = _fight_state()
    _engagement(state, (_foe(hull=10_000, hull_max=10_000, shields=0, damage=1),))
    sp = state.species[state.players[1].active_encounter.species_id]
    data = SMALL.roster.model_dump()
    target = next(s for s in data["species"] if s["id"] == sp.roster_id)
    target.setdefault("dialogue_pack", {})["combat_taunt"] = [
        {"when": {"criteria": {"round": 1}}, "variants": ["First blood!"]},
        {"variants": ["Still you resist."]},
    ]
    cfg = SMALL.model_copy(update={"roster": RosterConfig.model_validate(data)})

    result = reduce(state, 1, CombatAction(action="fight"), cfg)
    apply_result(state, result)
    from edge.core.events import AlienSpoke
    assert any(isinstance(e, AlienSpoke) and e.context == "combat_taunt"
               for e in result.events)
    enc = state.players[1].active_encounter
    assert enc is not None and enc.speech_context == "combat_taunt"
    view = session.encounter_view(state, 1, cfg)
    assert view is not None and view.speech == "First blood!"  # round-1 keyed entry

    apply_result(state, reduce(state, 1, CombatAction(action="fight"), cfg))
    assert session.encounter_view(state, 1, cfg).speech == "Still you resist."


def test_bloodied_pack_sues_for_quarter() -> None:
    state = _fight_state()
    _engagement(state, (_foe(hull=0), _foe(hull=0),
                        _foe(hull=10_000, hull_max=10_000, shields=0, damage=1)))
    apply_result(state, reduce(state, 1, CombatAction(action="fight"), SMALL))
    enc = state.players[1].active_encounter
    assert enc is not None and enc.speech_context == "surrender"  # over half destroyed


def test_flee_scorn_spoken_when_the_player_escapes() -> None:
    from edge.core.events import AlienSpoke
    from edge.dialogue import instance_key

    state = _fight_state()
    _engagement(state, (_foe(hull=10_000, hull_max=10_000, shields=0, damage=1),))
    sp = state.species[state.players[1].active_encounter.species_id]
    result = None
    for _ in range(400):
        result = reduce(state, 1, CombatAction(action="flee"), SMALL)
        apply_result(state, result)
        if state.players[1].active_encounter is None:
            break
    assert state.players[1].active_encounter is None
    spoke = [e for e in result.events if isinstance(e, AlienSpoke)]
    assert [e.context for e in spoke] == ["flee_scorn"]
    assert state.players[1].dialogue_recency[(instance_key(sp), "flee_scorn")]
    names = [type(e).__name__ for e in result.events]
    assert names.index("AlienSpoke") < names.index("EncounterEnded")  # scorn, then the record
