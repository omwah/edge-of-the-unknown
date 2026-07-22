"""GW-WP10 — authoritative tactical assault actions and planetary AI.

Two layers, mirroring the survey split (`test_groundwar_survey.py` pure /
`test_groundwar_survey_actions.py` reducer-level): direct calls into the ported
POC battle engine (`edge.core.groundwar.assault`) for combat mechanics that are
easiest to engineer deterministically (destroyed-wall passability, Resolve in both
directions, casualty ceiling/wipe, surrender, retrieval timeout, sortie pool
capping, jamming), and `reduce()`-driven reducer tests for command validation,
event emission, and command-log replay determinism.
"""

from __future__ import annotations

import math
from dataclasses import replace
from random import Random

import pytest
from hypothesis import given, settings, strategies as st

from edge.config import load_default_config
from edge.core.combat import CombatError
from edge.core.groundwar import assault as ga
from edge.core.groundwar.models import AssaultOperation
from edge.core.models import AlienSpecies, Game, Planet, Player, Sector, Ship, UniverseState
from edge.core.movement import MovementError
from edge.core.rules import (
    BeginAssault, EndGroundTurn, ExtractGroundOperation, GroundDrop,
    GroundFire, GroundJump, GroundMove, apply_result, reduce,
)
from edge.store.snapshots import state_hash

CFG = load_default_config()
GW = CFG.groundwar  # type: ignore[union-attr]


# --- pure battle-engine fixtures ---------------------------------------------


def _map(*, seed: int = 42, planet_type: str = "terrestrial_warm", cities: int = 1,
         citadel_level: int = 0) -> ga.AssaultMap:
    return ga.generate_assault_map(
        CFG, seed=seed, planet_type=planet_type, cities=cities, citadel_level=citadel_level)


def _op(amap: ga.AssaultMap, *, reserved_infantry: int = 10, reserved_armor: int = 0,
        retrieval_turn: int = 20, seed: int = 42, citadel_level: int = 0) -> AssaultOperation:
    return AssaultOperation(
        operation_id=1, planet_id=1, sector_id=1, planet_type="terrestrial_warm", seed=seed,
        started_day=1, resolve=GW.resolve.start, retrieval_turn=retrieval_turn,
        cities=len(amap.cities), citadel_level=citadel_level,
        surrender_threshold=GW.resolve.surrender_threshold,
        reserved_infantry=reserved_infantry, reserved_armor=reserved_armor,
    )


def _passable(amap: ga.AssaultMap, x: int, y: int) -> bool:
    if not (0 <= x < amap.width and 0 <= y < amap.height) or (x, y) in amap.blocked:
        return False
    tc = GW.terrain.get(amap.feature[y][x])
    return tc is None or tc.move_cost > 0


def _drop_at(amap: ga.AssaultMap, op: AssaultOperation, rng: Random, x: int, y: int,
             suit: str = "marauder") -> AssaultOperation:
    return ga.assault_drop(op, amap, CFG, rng, [(suit, x, y)])


# --- geometry: destroyed structures become passable rubble -------------------


def test_destroyed_wall_becomes_passable_rubble() -> None:
    amap = _map()

    def passable_and_clear(x: int, y: int, mid: tuple[int, int] | None) -> bool:
        return _passable(amap, x, y) and (mid is None or _passable(amap, *mid))

    target: tuple | None = None
    for s in amap.structures:
        if s.kind != "wall":
            continue
        for dx, dy in ((0, -2), (0, 2), (-2, 0), (2, 0)):
            tx, ty = s.x + dx, s.y + dy
            mid = (s.x + dx // 2, s.y + dy // 2) if dx == 0 or dy == 0 else None
            if passable_and_clear(tx, ty, mid):
                target = (s, tx, ty)
                break
        if target:
            break
    assert target is not None
    wall, tx, ty = target

    rng = Random(3)
    op = _drop_at(amap, _op(amap), rng, tx, ty)
    tid = op.platoon[0].id
    for _ in range(300):
        op, *_ = ga.assault_fire(op, amap, CFG, rng, tid, wall.x, wall.y)
        if op.structure_hp.get(wall.id, wall.hp_max) <= 0:
            break
        if op.platoon[0].actions <= 0:
            op = ga.assault_end_turn(op, amap, CFG, rng)
    assert op.structure_hp.get(wall.id, wall.hp_max) <= 0
    if op.platoon[0].actions <= 0:
        op = ga.assault_end_turn(op, amap, CFG, rng)

    moved = ga.assault_move(op, amap, CFG, tid, wall.x, wall.y)
    trooper = next(t for t in moved.platoon if t.id == tid)
    assert (trooper.x, trooper.y) == (wall.x, wall.y)


def test_live_wall_blocks_movement() -> None:
    amap = _map()
    wall = next(s for s in amap.structures if s.kind == "wall")
    # An adjacent legal cell that is NOT the wall itself.
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        tx, ty = wall.x + dx, wall.y + dy
        if _passable(amap, tx, ty):
            break
    rng = Random(1)
    op = _drop_at(amap, _op(amap), rng, tx, ty)
    tid = op.platoon[0].id
    with pytest.raises(MovementError):
        ga.assault_move(op, amap, CFG, tid, wall.x, wall.y)


# --- action economy -----------------------------------------------------------


def test_actions_per_turn_enforced_and_reset_on_end_turn() -> None:
    amap = _map()
    rng = Random(5)
    op = _drop_at(amap, _op(amap), rng, amap.landing_x, amap.landing_y)
    tid = op.platoon[0].id
    assert op.platoon[0].actions == GW.platoon.actions_per_turn
    # Spend every action on jumps to a legal nearby cell repeatedly.
    for _ in range(GW.platoon.actions_per_turn):
        trooper = next(t for t in op.platoon if t.id == tid)
        options = [
            (trooper.x + dx, trooper.y + dy)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if _passable(amap, trooper.x + dx, trooper.y + dy)
        ]
        tx, ty = options[0]
        op = ga.assault_move(op, amap, CFG, tid, tx, ty)
    assert next(t for t in op.platoon if t.id == tid).actions == 0
    with pytest.raises(MovementError):
        ga.assault_move(op, amap, CFG, tid, tx, ty)
    op = ga.assault_end_turn(op, amap, CFG, rng)
    assert next(t for t in op.platoon if t.id == tid).actions == GW.platoon.actions_per_turn


def test_jump_charges_deplete_and_reject_when_spent() -> None:
    amap = _map()
    rng = Random(9)
    op = _drop_at(amap, _op(amap), rng, amap.landing_x, amap.landing_y, suit="scout")
    tid = op.platoon[0].id
    suit = GW.suits["scout"]
    charges = suit.jump_charges
    assert charges > 0
    a, b = (amap.landing_x, amap.landing_y), (amap.landing_x + 1, amap.landing_y)
    assert _passable(amap, *b)
    for i in range(charges):
        target = b if i % 2 == 0 else a
        op, _hit = ga.assault_jump(op, amap, CFG, rng, tid, *target)
        op = ga.assault_end_turn(op, amap, CFG, rng)  # refresh actions/charges-gate between jumps
    trooper = next(t for t in op.platoon if t.id == tid)
    assert trooper.jump_charges == 0
    other = a if trooper.x != a[0] or trooper.y != a[1] else b
    with pytest.raises(MovementError):
        ga.assault_jump(op, amap, CFG, rng, tid, *other)


def test_missile_ammo_depletes_and_rejects_when_spent() -> None:
    """A single missile one-shots most emplacements (structure_mult=2.0), so proving
    depletion by repeated fire is fragile (the target dies before ammo runs out) —
    set the trooper's magazine to zero directly and check the reducer refuses."""
    amap = _map()
    wall = next(s for s in amap.structures if s.kind == "wall")
    for dx, dy in ((0, -2), (0, 2), (-2, 0), (2, 0)):
        tx, ty = wall.x + dx, wall.y + dy
        if _passable(amap, tx, ty):
            break
    rng = Random(11)
    op = _drop_at(amap, _op(amap), rng, tx, ty)
    tid = op.platoon[0].id
    assert op.platoon[0].missiles > 0
    depleted = replace(op, platoon=tuple(
        replace(t, missiles=0) if t.id == tid else t for t in op.platoon))
    with pytest.raises(CombatError):
        ga.assault_fire(depleted, amap, CFG, rng, tid, wall.x, wall.y, missile=True)


# --- detection / jamming -------------------------------------------------------


def test_firing_always_reveals_the_shooter() -> None:
    """A city's sensor radius (16 x a 1.4 signature = 22.4 cells) outranges every suit's
    weapon (<= 13), so any position close enough to legally fire at a city structure is
    already inside its own sensor's detection radius — "undetected before firing" is not
    reachable through legal drop placement. Construct the trooper's `detected=False`
    directly on the scratch battle instead, isolating the one reliable invariant: firing
    always reveals you, regardless of prior detection state."""
    amap = _map()
    wall = next(s for s in amap.structures if s.kind == "wall")
    for dx, dy in ((0, -2), (0, 2), (-2, 0), (2, 0)):
        tx, ty = wall.x + dx, wall.y + dy
        if _passable(amap, tx, ty):
            break
    op = _op(amap, reserved_infantry=0)
    battle = ga._battle_for(op, amap, CFG, Random(4))  # noqa: SLF001
    tid = 9_999
    battle.troopers[tid] = ga._Trooper(  # noqa: SLF001
        id=tid, suit_id="marauder", name="T", x=tx, y=ty, hp=80, missiles=3, jump_charges=4,
        mp=3, actions=2, detected=False)
    trooper = battle.troopers[tid]
    assert trooper.detected is False
    ga.fire_at(battle, trooper, wall.x, wall.y)
    assert trooper.detected is True  # firing reveals you


# --- resolve moves in both directions ------------------------------------------


def test_resolve_drains_on_structure_destroyed() -> None:
    amap = _map()
    wall = next(s for s in amap.structures if s.kind == "wall")
    for dx, dy in ((0, -2), (0, 2), (-2, 0), (2, 0)):
        tx, ty = wall.x + dx, wall.y + dy
        if _passable(amap, tx, ty):
            break
    rng = Random(3)
    op = _drop_at(amap, _op(amap), rng, tx, ty)
    tid = op.platoon[0].id
    start_resolve = op.resolve
    for _ in range(300):
        op, *_ = ga.assault_fire(op, amap, CFG, rng, tid, wall.x, wall.y)
        if op.structure_hp.get(wall.id, wall.hp_max) <= 0:
            break
        if op.platoon[0].actions <= 0:
            op = ga.assault_end_turn(op, amap, CFG, rng)
    assert op.resolve < start_resolve


def test_resolve_hardens_on_civilian_building_destroyed() -> None:
    amap = _map(citadel_level=0)
    civ = next((s for s in amap.structures if s.kind == "building_civilian"), None)
    assert civ is not None, "expected at least one civilian building block"
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        tx, ty = civ.x + dx, civ.y + dy
        if _passable(amap, tx, ty):
            break
    rng = Random(6)
    op = _drop_at(amap, _op(amap), rng, tx, ty)
    tid = op.platoon[0].id
    start_resolve = op.resolve
    for _ in range(300):
        op, *_ = ga.assault_fire(op, amap, CFG, rng, tid, civ.x, civ.y)
        if op.structure_hp.get(civ.id, civ.hp_max) <= 0:
            break
        if op.outcome is not None:
            break
        if op.platoon[0].actions <= 0:
            op = ga.assault_end_turn(op, amap, CFG, rng)
    assert op.structure_hp.get(civ.id, civ.hp_max) <= 0
    assert op.resolve > start_resolve  # atrocity stiffens the defenders


def test_resolve_never_exceeds_configured_cap() -> None:
    battle = ga._battle_for(_op(_map()), _map(), CFG, Random(1))  # noqa: SLF001 — pure scratch, test-local
    ga._apply_resolve(battle, 10_000, "test overflow")  # noqa: SLF001
    assert battle.resolve == GW.resolve.cap


# --- broadcast requires a cowed city ------------------------------------------


def test_broadcast_rejected_before_city_is_cowed() -> None:
    amap = _map(cities=1)
    city = amap.cities[0]
    rng = Random(2)
    op = _drop_at(amap, _op(amap, reserved_infantry=0), rng, city.cx, city.cy - 1, suit="command")
    tid = op.platoon[0].id
    with pytest.raises(CombatError):
        ga.assault_broadcast(op, amap, CFG, tid)


def test_broadcast_succeeds_once_city_is_fully_silenced() -> None:
    amap = _map(cities=1, citadel_level=0)
    city = amap.cities[0]
    # A world with zero reserved garrison and every active defense (turret/aa/citadel_gun)
    # knocked out by direct state surgery is trivially "cowed" — isolates broadcast legality
    # from the (already separately tested) fire/destroy mechanics.
    rng = Random(2)
    op = _drop_at(amap, _op(amap, reserved_infantry=0), rng, city.cx, city.cy, suit="command")
    battle = ga._battle_for(op, amap, CFG, rng)  # noqa: SLF001
    for s in battle.structures.values():
        if s.city_id == city.id and s.kind in ("turret", "aa", "citadel_gun"):
            s.hp = 0
    op = ga._freeze_battle(op, battle)  # noqa: SLF001
    tid = op.platoon[0].id
    new_op = ga.assault_broadcast(op, amap, CFG, tid)
    assert city.id in new_op.broadcast_cities
    assert new_op.resolve < op.resolve


# --- sortie pool capping (garrison-deployment decision) ------------------------


def test_sorties_never_exceed_the_finite_remaining_pool() -> None:
    amap = _map(cities=1)
    rng = Random(8)
    op = _op(amap, reserved_infantry=6, reserved_armor=0, retrieval_turn=40)
    op = _drop_at(amap, op, rng, amap.landing_x, amap.landing_y)
    preplaced = len(op.garrison_units)
    assert preplaced + op.infantry_remaining == 6  # conservation: nothing minted (G8)
    for _ in range(35):
        if op.outcome is not None:
            break
        op = ga.assault_end_turn(op, amap, CFG, rng)
    # Total ever fielded (still alive + already-dead) can never exceed the reserved pool.
    assert op.infantry_remaining >= 0
    total_fielded = 6 - op.infantry_remaining
    assert total_fielded <= 6


# --- casualty ceiling / wipe / surrender / retrieval outcomes ------------------


def test_casualty_ceiling_aborts_the_mission() -> None:
    amap = _map()
    rng = Random(1)
    op = _op(amap, reserved_infantry=0)
    battle = ga._battle_for(op, amap, CFG, rng)  # noqa: SLF001
    battle.next_id = len(amap.structures) + 1
    for i in range(4):
        tid = battle.next_unit_id()
        battle.troopers[tid] = ga._Trooper(  # noqa: SLF001
            id=tid, suit_id="marauder", name=f"T{i}", x=amap.landing_x, y=amap.landing_y,
            hp=100, missiles=0, jump_charges=0)
    battle.initial_strength = 4
    op = ga._freeze_battle(op, battle)  # noqa: SLF001

    battle = ga._battle_for(op, amap, CFG, rng)  # noqa: SLF001
    battle.troopers[op.platoon[0].id].hp = 0
    battle.troopers[op.platoon[1].id].hp = 0
    battle.troopers[op.platoon[2].id].hp = 0
    ga._check_casualties(battle)  # noqa: SLF001
    op = ga._freeze_battle(op, battle)  # noqa: SLF001
    assert op.outcome == "casualties"  # 3/4 > default 0.5 ceiling


def test_wipe_when_every_trooper_dies() -> None:
    amap = _map()
    rng = Random(1)
    op = _op(amap, reserved_infantry=0)
    op = _drop_at(amap, op, rng, amap.landing_x, amap.landing_y)
    battle = ga._battle_for(op, amap, CFG, rng)  # noqa: SLF001
    for t in battle.troopers.values():
        t.hp = 0
    ga._check_casualties(battle)  # noqa: SLF001
    op = ga._freeze_battle(op, battle)  # noqa: SLF001
    assert op.outcome == "wiped"


def test_surrender_when_resolve_crosses_threshold() -> None:
    amap = _map()
    op = _op(amap, reserved_infantry=0)
    battle = ga._battle_for(op, amap, CFG, Random(1))  # noqa: SLF001
    battle.resolve = op.surrender_threshold + 1
    ga._apply_resolve(battle, -5, "test strike")  # noqa: SLF001
    op = ga._freeze_battle(op, battle)  # noqa: SLF001
    assert op.outcome == "surrender"


def test_retrieval_clock_ends_the_mission_unbowed() -> None:
    amap = _map()
    rng = Random(20)
    op = _op(amap, reserved_infantry=0, retrieval_turn=3)
    op = _drop_at(amap, op, rng, amap.landing_x, amap.landing_y)
    for _ in range(5):
        if op.outcome is not None:
            break
        op = ga.assault_end_turn(op, amap, CFG, rng)
    assert op.outcome == "retrieval"
    assert op.local_turn == 3


def test_actions_reject_once_outcome_is_settled() -> None:
    amap = _map()
    op = _op(amap, reserved_infantry=0, retrieval_turn=1)
    rng = Random(2)
    op = _drop_at(amap, op, rng, amap.landing_x, amap.landing_y)
    op = ga.assault_end_turn(op, amap, CFG, rng)
    assert op.outcome == "retrieval"
    with pytest.raises(MovementError):
        ga.assault_end_turn(op, amap, CFG, rng)
    with pytest.raises(MovementError):
        ga.assault_move(op, amap, CFG, op.platoon[0].id, amap.landing_x, amap.landing_y)


# --- determinism (pure engine) -------------------------------------------------


def test_pure_battle_replay_is_deterministic() -> None:
    amap = _map()

    def run() -> AssaultOperation:
        rng = Random(7)
        op = _drop_at(amap, _op(amap, retrieval_turn=6), rng, amap.landing_x, amap.landing_y)
        while op.outcome is None:
            op = ga.assault_end_turn(op, amap, CFG, rng)
        return op

    assert run() == run()


@settings(max_examples=30, deadline=None)
@given(seed=st.integers(min_value=0, max_value=10_000))
def test_resolve_and_casualties_stay_in_bounds(seed: int) -> None:
    """Hypothesis: whatever the seed, Resolve stays capped and casualties never
    exceed the platoon that dropped (GW plan's "Hypothesis termination and bounds")."""
    amap = _map(seed=seed % 97)
    rng = Random(seed)
    op = _op(amap, reserved_infantry=8, reserved_armor=2, retrieval_turn=10, seed=seed % 97)
    op = _drop_at(amap, op, rng, amap.landing_x, amap.landing_y)
    turns = 0
    while op.outcome is None and turns < 15:
        op = ga.assault_end_turn(op, amap, CFG, rng)
        turns += 1
    assert 0 <= op.resolve <= GW.resolve.cap
    assert op.casualties <= op.initial_strength
    assert op.infantry_remaining >= 0 and op.armor_remaining >= 0


# --- reducer-level: BeginAssault -> GroundDrop -> tactical actions ------------


def _species(disp: float) -> AlienSpecies:
    return AlienSpecies(
        id=7, roster_id="vesk", name="Vesk", archetype_id="a", sector_id=1,
        home_band="Frontier", tech_level=1, base_disposition=disp,
        disposition_center=disp, disposition_variance=0.0)


def _reducer_world(*, reserved_infantry: int = 10, reserved_armor: int = 0) -> UniverseState:
    """A one-sector, droppable hostile world (mirrors `test_groundwar_access.py`'s
    `_hostile species, no defenses` fixture) with a ship carrying a small platoon."""
    state = UniverseState.new(Game(1, 5, CFG.config_version, "t"))
    state.sectors = {1: Sector(1, 1, (), "Frontier")}
    state.rebuild_adjacency()
    state.planets = {1: Planet(
        id=1, sector_id=1, name="World", planet_type="terrestrial_warm",
        habitability_cap=100_000, population={"vesk": 500},
        garrison_infantry=reserved_infantry, garrison_armor=reserved_armor)}
    state.species = {7: _species(0.1)}
    state.ships = {1: Ship(
        id=1, type_id="trailblazer", name="S.S.", owner_player_id=1, sector_id=1,
        holds_total=60, turns_per_warp=1, passenger_capacity=20, recruits=4,
        suits={"marauder": 4})}
    state.players = {1: Player(id=1, name="you", ship_id=1, latinum=10_000, turns_remaining=250)}
    return state


def _dropped(st: UniverseState) -> AssaultOperation:
    apply_result(st, reduce(st, 1, BeginAssault(1), CFG))
    op = st.players[1].ground_operation
    amap = ga.assault_map_for(st, op, CFG)
    apply_result(st, reduce(
        st, 1, GroundDrop(op.operation_id, (("marauder", amap.landing_x, amap.landing_y),)), CFG))
    return st.players[1].ground_operation


def test_ground_drop_rejects_a_loadout_the_ship_cannot_field() -> None:
    st = _reducer_world()
    apply_result(st, reduce(st, 1, BeginAssault(1), CFG))
    op = st.players[1].ground_operation
    amap = ga.assault_map_for(st, op, CFG)
    with pytest.raises(Exception):  # GroundForceError surfaces as EconomyError
        reduce(st, 1, GroundDrop(op.operation_id, (
            ("marauder", amap.landing_x, amap.landing_y),
        ) * 5), CFG)  # only 4 suits owned


def test_ground_drop_then_ground_move_ground_fire_and_end_turn() -> None:
    st = _reducer_world(reserved_infantry=0)
    op = _dropped(st)
    assert op.dropped and len(op.platoon) == 1
    tid = op.platoon[0].id
    amap = ga.assault_map_for(st, op, CFG)
    trooper = op.platoon[0]
    options = [
        (trooper.x + dx, trooper.y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if _passable(amap, trooper.x + dx, trooper.y + dy)
    ]
    assert options
    apply_result(st, reduce(st, 1, GroundMove(op.operation_id, *options[0], actor_id=tid), CFG))
    op = st.players[1].ground_operation
    assert (op.platoon[0].x, op.platoon[0].y) == options[0]
    apply_result(st, reduce(st, 1, EndGroundTurn(op.operation_id), CFG))
    op = st.players[1].ground_operation
    assert op.local_turn == 1


def test_ground_fire_and_ground_jump_events_reach_the_log() -> None:
    """`GroundDrop` may legally land anywhere passable, not only the map's generated
    landing zone (§3), so this test drops the platoon adjacent to a chosen wall
    directly rather than reusing `_dropped()`'s landing-zone drop — `derive_difficulty`
    can lay out several cities far apart, and the landing zone need not be near any
    of them."""
    from edge.core.events import GroundFired, GroundJumped

    st = _reducer_world(reserved_infantry=0)
    apply_result(st, reduce(st, 1, BeginAssault(1), CFG))
    op = st.players[1].ground_operation
    amap = ga.assault_map_for(st, op, CFG)
    # Passable terrain can still block line of sight (forest), so pick a candidate that
    # clears both — a pre-drop scratch battle (no troopers yet) is enough to check LOS.
    los_battle = ga._battle_for(op, amap, CFG, None)  # noqa: SLF001
    wall, tx, ty = next(
        (s, s.x + dx, s.y + dy)
        for s in amap.structures if s.kind == "wall"
        for dx, dy in ((0, -2), (0, 2), (-2, 0), (2, 0))
        if _passable(amap, s.x + dx, s.y + dy)
        and ga._line_of_sight(los_battle, s.x + dx, s.y + dy, s.x, s.y)  # noqa: SLF001
    )
    apply_result(st, reduce(st, 1, GroundDrop(op.operation_id, (("marauder", tx, ty),)), CFG))
    op = st.players[1].ground_operation
    tid = op.platoon[0].id

    result = reduce(st, 1, GroundFire(op.operation_id, tid, wall.x, wall.y), CFG)
    assert any(isinstance(e, GroundFired) for e in result.events)
    apply_result(st, result)
    op = st.players[1].ground_operation
    trooper = op.platoon[0]
    jump_target = next(
        (trooper.x + dx, trooper.y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        if _passable(amap, trooper.x + dx, trooper.y + dy)
    )
    result2 = reduce(st, 1, GroundJump(op.operation_id, tid, *jump_target), CFG)
    assert any(isinstance(e, GroundJumped) for e in result2.events)


def test_extract_ground_operation_clears_a_live_assault() -> None:
    st = _reducer_world(reserved_infantry=0)
    op = _dropped(st)
    apply_result(st, reduce(st, 1, ExtractGroundOperation(op.operation_id), CFG))
    assert st.players[1].ground_operation is None


def test_end_ground_turn_charges_the_configured_macro_turn_quantum() -> None:
    st = _reducer_world(reserved_infantry=0)
    op = _dropped(st)
    before = st.players[1].turns_remaining
    apply_result(st, reduce(st, 1, EndGroundTurn(op.operation_id), CFG))
    spent = before - st.players[1].turns_remaining
    expected = math.ceil(1 / GW.pressure.local_turns_per_main_turn) * GW.pressure.main_turn_cost
    assert spent == expected


def test_end_ground_turn_rejected_when_no_turns_left() -> None:
    st = _reducer_world(reserved_infantry=0)
    op = _dropped(st)
    st.players[1] = replace(st.players[1], turns_remaining=0)  # type: ignore[index]
    with pytest.raises(Exception):
        reduce(st, 1, EndGroundTurn(op.operation_id), CFG)


def test_command_log_rebuilds_to_identical_hash() -> None:
    def play() -> str:
        st = _reducer_world(reserved_infantry=0)
        op = _dropped(st)
        apply_result(st, reduce(st, 1, EndGroundTurn(op.operation_id), CFG))
        op = st.players[1].ground_operation
        apply_result(st, reduce(st, 1, ExtractGroundOperation(op.operation_id), CFG))
        return state_hash(st)

    assert play() == play()


def test_reload_mid_battle_at_multiple_turns_replays_identically() -> None:
    def play(turns: int) -> str:
        st = _reducer_world(reserved_infantry=0)
        op = _dropped(st)
        for _ in range(turns):
            apply_result(st, reduce(st, 1, EndGroundTurn(op.operation_id), CFG))
            op = st.players[1].ground_operation
            if op.outcome is not None:
                break
        return state_hash(st)

    for n in (1, 2, 3):
        assert play(n) == play(n)
