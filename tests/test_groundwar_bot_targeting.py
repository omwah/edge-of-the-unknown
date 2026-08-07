"""The assault bot's target-selection policy, pinned directly.

Split out from `test_groundwar_bots.py` (determinism and outcomes) because this asks a
different question: *what does the platoon shoot at*, which an outcome column cannot
answer. A watched run showed roughly half of every shot going into walls; a shot audit
put half of that inside the objective, where a breach is already open and a wall is worth
0.5 Resolve per action against a military block's 3.0. The bot was picking them anyway —
per-kill ranking put walls last, but last place is still first when nothing better is in
line of sight, and the old inside-goal (the city centre) parked troopers where that was
the common case.

Both halves of that are asserted here because both are silent failures: nothing crashes,
no test goes red, the platoon simply spends its clock on masonry and times out.
"""

from __future__ import annotations

import pytest

from dataclasses import replace

from edge.bot.runner import BotRunner
from edge.bot.scripts import assaulter
from edge.bot.scripts.assaulter import _SCOUT_LEASH, _advance_cell, _alive, _hunt_goal, \
    _move_goal, _role, _scout_regroup, _target_value
from edge.config import load_default_config
from edge.core.config import GameConfig
from edge.core.groundwar.assault import assault_map_for
from edge.core.groundwar.models import AssaultOperation
from edge.groundwar import harness
from edge.groundwar.spectate import Scenario, build_state
from edge.server.service import GameService
from edge.store.repo import SqliteRepository

_SEED = 1


@pytest.fixture(scope="module")
def dropped() -> tuple[GameConfig, AssaultOperation, object]:
    """A real map with a real platoon on the ground — no hand-built fixtures.

    The values under test are read off generated geometry (city footprints, interior
    walls, emplacement mix), so a synthetic two-structure map would assert the policy
    against a world that never occurs.
    """
    config = load_default_config()
    scenario = Scenario(seed=_SEED, citadel_level=0,
                        planet_type="terrestrial_warm", habitability_cap=8_000)
    service = GameService(
        build_state(scenario, config), config, SqliteRepository(":memory:"))
    bot = BotRunner(service, harness.PLAYER_ID)
    assaulter.setup(bot)
    for _ in range(4_000):
        op = service.state.players[harness.PLAYER_ID].ground_operation
        if isinstance(op, AssaultOperation) and op.dropped:
            return config, op, assault_map_for(service.state, op, config)
        if bot.stopped:
            break
        bot.step()
    pytest.fail("bot never landed a platoon")


def test_interior_walls_are_never_worth_an_action(dropped) -> None:  # type: ignore[no-untyped-def]
    """Inside the objective a wall must be refused outright, not merely ranked low.

    Ranking is not enough: `min()` over the fireable set returns *something* whenever the
    set is non-empty, so a low score still gets fired at when it is the only score. Only
    returning None takes the cell out of the running and leaves the trooper `adrift`, so
    it walks somewhere useful instead.
    """
    config, op, amap = dropped
    walls = [s for s in amap.structures if s.kind in {"wall", "gate"}]
    assert walls, "generated city has no perimeter to test against"
    for wall in walls[:20]:
        assert _target_value(
            amap, op, config, (wall.x, wall.y), (wall.x + 1, wall.y), inside=True) is None


def test_targets_are_ranked_by_resolve_per_action(dropped) -> None:
    """A wall must rank below every payload target, on the per-shot measure.

    Per *kill* a wall (2) already sorted under a military block (3) — the gap that
    mattered was hidden in hit points: 200 against 50, so the true ratio is six to one,
    not three to two. Asserting the ordering rather than the numbers keeps this honest
    if the config is retuned.
    """
    config, op, amap = dropped
    outside = (0, 0)

    def value(kind: str) -> float | None:
        for s in amap.structures:
            if s.kind == kind and _alive(op, s):
                return _target_value(amap, op, config, (s.x, s.y), outside)
        return None

    wall = value("wall")
    assert wall is not None
    for kind in ("building_military", "sensor", "turret", "aa", "citadel_gun"):
        better = value(kind)
        if better is None:
            continue  # not every generated city fields every emplacement
        assert better > wall, f"{kind} must outrank a wall segment per action spent"


def test_hunt_goal_picks_a_live_target_over_the_city_centre(dropped) -> None:
    """The other half: standing on the centre is what made walls the only thing in range.

    A trooper whose goal is the geometric centre stops being `adrift` the moment it
    arrives and then never moves again, so its line of sight is frozen wherever it
    happens to be. Aiming at live emplacements and garrison instead keeps it closing
    while there is Resolve left to take.
    """
    config, op, amap = dropped
    city = next((c for c in amap.cities if c.is_citadel), amap.cities[0])
    trooper = next(t for t in op.platoon if t.hp > 0)
    goal = _hunt_goal(amap, op, city, trooper)
    if goal is None:
        pytest.skip("objective already stripped of live targets at drop time")
    assert goal != (city.cx, city.cy) or any(
        (u.x, u.y) == goal and u.hp > 0 for u in op.garrison_units)
    # GW-WP27: `goal` may be any cell of a footprint, not just its anchor — `_hunt_goal`
    # walks to the nearest face of a multi-cell building, not necessarily its (x, y).
    hit = [s for s in amap.structures
           if goal in s.cells and s.city_id == city.id]
    garrison = [u for u in op.garrison_units if (u.x, u.y) == goal and u.hp > 0]
    assert hit or garrison, "hunt goal must be an actual target, not empty ground"
    if hit:
        assert hit[0].kind not in {"wall", "gate", "building_civilian"}


def test_scout_regroups_only_once_it_has_outrun_its_marauder_escort(dropped) -> None:  # type: ignore[no-untyped-def]
    """GW-WP29: a scout's move (6) and jump_range (10) let it outpace the marauder
    pack (move 3) it needs for cover — traced losses showed scouts dying alone, turns
    before any marauder made contact. `_scout_regroup` is what stops that.

    GW-WP30: the leash trips at the same distance it always did, but over-leash it now
    hands back the escort's cell to close on rather than a "stop moving" flag. The old
    flag froze the scout for the rest of the operation, because the pack it was told to
    wait for is attacking and never comes back.
    """
    config, op, _amap = dropped
    scout = next(t for t in op.platoon if _role(config.groundwar.suits[t.suit_id]) == "scout")
    anchor = next(
        t for t in op.platoon if _role(config.groundwar.suits[t.suit_id]) == "marauder")
    # Pin every marauder to one point so `min()` over the pack has a single, known answer.
    platoon = tuple(
        replace(t, x=anchor.x, y=anchor.y)
        if _role(config.groundwar.suits[t.suit_id]) == "marauder" else t
        for t in op.platoon)

    near = replace(scout, x=anchor.x, y=anchor.y + _SCOUT_LEASH)
    op_near = replace(op, platoon=tuple(
        near if t.id == scout.id else t for t in platoon))
    assert _scout_regroup(near, op_near, config) is None

    far = replace(scout, x=anchor.x, y=anchor.y + _SCOUT_LEASH + 1)
    op_far = replace(op, platoon=tuple(
        far if t.id == scout.id else t for t in platoon))
    assert _scout_regroup(far, op_far, config) == (anchor.x, anchor.y), \
        "an over-leash scout must be sent back to its escort, not merely stopped"

    dead_marauders = tuple(
        replace(t, hp=0) if _role(config.groundwar.suits[t.suit_id]) == "marauder" else t
        for t in op.platoon)
    op_no_escort = replace(op, platoon=dead_marauders)
    assert _scout_regroup(far, op_no_escort, config) is None, \
        "a scout with no living marauder to rejoin must go on alone"


def test_command_keeps_station_on_the_pack_and_never_enters_the_objective(dropped) -> None:  # type: ignore[no-untyped-def]
    """GW-WP30: the two halves of the Command fix, which have to hold together.

    Holding at `broadcast_range - 1` off the city's near face put Command *inside its own
    hold ring at the drop* (~12 cells out against a hold of 13), so it never moved and
    took zero actions in a whole operation — abandoning the `command_radius` aura that is
    its reason to exist the moment the marauders advanced. It now follows the pack. The
    rule that fix must not break is D31's: Command never enters the objective.
    """
    config, op, amap = dropped
    city = next((c for c in amap.cities if c.is_citadel), amap.cities[0])
    suit = config.groundwar.suits["command"]

    # A pack deep inside the capital: the goal Command closes on is inside the walls...
    pack = (city.cx, city.cy)
    goal, hold = _move_goal(city, None, suit, "command", at=(city.x0 - 20, city.y0 - 20),
                            inside=False, pack=pack)
    assert goal == pack, "Command must keep station on the pack, not on a fixed standoff"
    assert hold == max(1, suit.command_radius - 1)

    # ...but every cell it may step to stays outside them.
    reachable = frozenset(
        {(city.cx, city.cy), (city.x0 + 1, city.y0 + 1), (city.x0 - 1, city.y0 - 1)})
    cell = _advance_cell(reachable, goal, keep_out=city)
    assert cell is not None and not city.inside(*cell), \
        "Command may shadow the platoon to the wall but never through it"

    # With no pack left there is nobody to follow, so it falls back to the standoff.
    goal, hold = _move_goal(city, None, suit, "command", at=(city.x0 - 20, city.y0 - 20),
                            inside=False, pack=None)
    assert hold == max(1, suit.broadcast_range - 1)
