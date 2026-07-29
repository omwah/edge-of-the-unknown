"""GW-WP16 — Cloud City tactical assault end-to-end (drop/fight/broadcast/settle).

Exercises the unmodified `edge.core.groundwar.assault` action functions and
`edge.core.groundwar.settlement.settle_assault` (D8) against a
`generate_cloud_city_assault_map` battlefield, proving the "zero-touch" claim in
the GW-WP16 plan by actually running the shared tactical/settlement engine
against the new topology rather than just reading the code. Mirrors the
surgical-state technique `test_groundwar_assault_actions.py` already uses
(`_battle_for`/`_freeze_battle` direct hp zeroing) to reach a cowed/surrender
state deterministically without a long combat grind.
"""

from __future__ import annotations

from random import Random

import pytest

from edge.config import load_default_config
from edge.core.combat import CombatError
from edge.core.enums import Commodity
from edge.core.groundwar import assault as ga
from edge.core.groundwar import settlement as gs
from edge.core.groundwar.models import AssaultOperation
from edge.core.models import Ownership, Planet, Ship

CFG = load_default_config()
GW = CFG.groundwar
assert GW is not None


def _map(*, seed: int = 7, cloud_city_size: int = 3, citadel_level: int = 2) -> ga.AssaultMap:
    return ga.generate_cloud_city_assault_map(
        CFG, seed=seed, cloud_city_size=cloud_city_size, citadel_level=citadel_level)


def _op(amap: ga.AssaultMap, *, reserved_infantry: int = 4, reserved_armor: int = 0,
        retrieval_turn: int = 20, citadel_level: int = 2) -> AssaultOperation:
    return AssaultOperation(
        operation_id=1, planet_id=1, sector_id=1, planet_type="jovian", seed=7,
        # GW-WP19: the map identity is the world's `world_seed`, so it must match the
        # seed `_map` generated from or `settle_assault` regenerates a different station.
        world_seed=7,
        started_day=1, resolve=GW.resolve.start, retrieval_turn=retrieval_turn,
        cities=3, citadel_level=citadel_level,
        surrender_threshold=GW.resolve.surrender_threshold,
        reserved_infantry=reserved_infantry, reserved_armor=reserved_armor,
    )


def _drop_at(amap: ga.AssaultMap, op: AssaultOperation, rng: Random, x: int, y: int,
             suit: str = "command") -> AssaultOperation:
    return ga.assault_drop(op, amap, CFG, rng, [(suit, x, y)])


def _planet(**kw: object) -> Planet:
    base: dict[str, object] = dict(
        id=1, sector_id=1, name="Skyhold", planet_type="jovian",
        owner=Ownership("alliance", 5), cloud_city_size=3,
        population={"vesk": 20_000},
        stores={Commodity.EQUIPMENT: 40}, citadel_level=2, citadel_progress=0,
        garrison_infantry=4, garrison_armor=0,
    )
    base.update(kw)
    return Planet(**base)  # type: ignore[arg-type]


def _ship() -> Ship:
    return Ship(
        id=1, type_id="trailblazer", name="S.S. Boarder", owner_player_id=1,
        sector_id=1, holds_total=60, passenger_capacity=20,
        recruits=2, suits={"command": 2}, ground_missiles=0,
    )


# --- drop + fight + broadcast (whole-station cowed/surrender) -----------------


def test_drop_lands_on_a_valid_deployment_zone() -> None:
    amap = _map()
    rng = Random(1)
    op = _drop_at(amap, _op(amap), rng, amap.landing_x, amap.landing_y)
    assert op.dropped
    assert len(op.platoon) == 1


def test_broadcast_rejected_before_whole_station_is_cowed() -> None:
    amap = _map()
    rng = Random(2)
    op = _drop_at(amap, _op(amap, reserved_infantry=0), rng, amap.landing_x, amap.landing_y)
    tid = op.platoon[0].id
    with pytest.raises(CombatError):
        ga.assault_broadcast(op, amap, CFG, tid)


def test_broadcast_succeeds_once_every_district_defense_is_down() -> None:
    """Whole-station cowed (interview decision): zeroing every active defense
    ACROSS EVERY PHYSICAL ROOM (not just one district) is what silences the
    single shared city — `_check_cowed`/`city_cowed` need no changes at all to
    already mean this, since every structure shares one `city_id`."""
    amap = _map()
    city = amap.cities[0]
    rng = Random(2)
    op = _drop_at(amap, _op(amap, reserved_infantry=0), rng, city.cx, city.cy)
    battle = ga._battle_for(op, amap, CFG, rng)  # noqa: SLF001
    for s in battle.structures.values():
        if s.kind in ("turret", "aa", "sensor", "citadel_gun"):
            s.hp = 0
    op = ga._freeze_battle(op, battle)  # noqa: SLF001
    tid = op.platoon[0].id
    new_op, _log = ga.assault_broadcast(op, amap, CFG, tid)
    assert city.id in new_op.broadcast_cities
    assert new_op.resolve < op.resolve


def test_surrender_when_resolve_crosses_threshold() -> None:
    amap = _map()
    op = _op(amap, reserved_infantry=0)
    battle = ga._battle_for(op, amap, CFG, Random(1))  # noqa: SLF001
    battle.resolve = op.surrender_threshold + 1
    ga._apply_resolve(battle, -5, "test strike")  # noqa: SLF001
    op = ga._freeze_battle(op, battle)  # noqa: SLF001
    assert op.outcome == "surrender"


def test_retrieval_clock_ends_the_mission_unbowed() -> None:
    # citadel_level=0 / size=1 (no aa/citadel_gun risk to the lone trooper across
    # several end-turns) isolates the retrieval-clock mechanic, mirroring why
    # `test_groundwar_assault_actions.py`'s own `_map()` default is `citadel_level=0`.
    amap = _map(cloud_city_size=1, citadel_level=0)
    rng = Random(20)
    op = _drop_at(amap, _op(amap, reserved_infantry=0, retrieval_turn=3, citadel_level=0), rng,
                  amap.landing_x, amap.landing_y)
    for _ in range(5):
        if op.outcome is not None:
            break
        op, _ = ga.assault_end_turn(op, amap, CFG, rng)
    assert op.outcome == "retrieval"


# --- settlement (D8) — conquest, the realistic Cloud City outcome -------------
#
# A Cloud City always has an owner once built (`BuildStagingArea` claims the
# world on first build, DESIGN.md §4.2), so the below-friendly assault target
# is always someone's alliance/player/corp holding — the "unowned native
# protectorate" branch `settle_assault` also supports is a terrestrial-only
# scenario for a station and isn't exercised here.


def test_settle_assault_surrender_conquers_a_cloud_city() -> None:
    planet = _planet(cloud_city_size=1, citadel_level=0)
    ship = _ship()
    amap = _map(cloud_city_size=1, citadel_level=0)
    rng = Random(4)
    op = _drop_at(amap, _op(amap, reserved_infantry=0, citadel_level=0), rng,
                  amap.landing_x, amap.landing_y)
    battle = ga._battle_for(op, amap, CFG, rng)  # noqa: SLF001
    battle.resolve = op.surrender_threshold + 1
    ga._apply_resolve(battle, -10, "test strike")  # noqa: SLF001
    op = ga._freeze_battle(op, battle)  # noqa: SLF001
    assert op.outcome == "surrender"

    settled = gs.settle_assault(
        planet, ship, op, player_id=1, corp_id=None, day=10, config=CFG)
    assert settled.outcome == "surrender"
    assert settled.control == "conquest"
    assert settled.planet.owner == Ownership("player", 1)
    # The Cloud City's own state (size, staged berths) survives conquest untouched
    # — settle_assault only ever touches ownership/garrison/damage/population.
    assert settled.planet.cloud_city_size == planet.cloud_city_size


def test_settle_assault_extraction_leaves_ownership_untouched() -> None:
    # citadel_level=0 / size=1 for the same reason the retrieval-clock test above gives:
    # this asserts what *settlement* does with a `retrieval` outcome, so the drop must
    # survive to reach one. A fully-armed station (the `_map()`/`_op()` defaults, size 3
    # and citadel 2) shoots a lone capsule down during `assault_drop` on most seeds — the
    # op is already `wiped` before the end-turn below, and `assault_end_turn` rightly
    # refuses to run a defense phase for a finished operation. That is the guns working,
    # not a settlement bug, so the fixture drops somewhere undefended instead.
    planet = _planet(cloud_city_size=1, citadel_level=0)
    ship = _ship()
    amap = _map(cloud_city_size=1, citadel_level=0)
    rng = Random(5)
    op = _drop_at(amap, _op(amap, reserved_infantry=0, retrieval_turn=1, citadel_level=0), rng,
                  amap.landing_x, amap.landing_y)
    assert op.outcome is None, "the drop must survive for the retrieval clock to be the cause"
    op, _ = ga.assault_end_turn(op, amap, CFG, rng)
    assert op.outcome == "retrieval"

    settled = gs.settle_assault(
        planet, ship, op, player_id=1, corp_id=None, day=10, config=CFG)
    assert settled.outcome == "retrieval"
    assert settled.control == "none"
    assert settled.planet.owner == planet.owner
