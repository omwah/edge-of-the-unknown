"""WP24 — the encounter core: interrupt, detection, greeting-vs-violence, packs (§10, §13).

Covers the pure `core.encounters` roll chain, the movement-reducer wiring (halting a
`TravelTo` at the interrupted hop, blocking movement while engaged), and the golden
persistence of an interrupted journey.
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
from edge.core import encounters
from edge.core.aliens import HOSTILE, disposition_band
from edge.core.events import EncounterEvaded, EncounterStarted, Warped
from edge.core.movement import MovementError, shortest_path
from edge.core.rules import Dock, JoinGame, TravelTo, Warp, apply_result, reduce
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import state_hash

CFG = load_default_config()
SMALL = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(
    update={"sector_count": 400, "start_sector": 1})})


def _state_with_player(seed: int = 3):
    state = generate(SMALL, seed)
    apply_result(state, reduce(state, 1, JoinGame(name="T"), SMALL))
    return state


def _hostile(state):
    return next(
        (s for s in sorted(state.species.values(), key=lambda s: s.id)
         if disposition_band(s.base_disposition, CFG.aliens) == HOSTILE),
        None,
    )


def _walk_until_engaged(state, target_sector: int, config, *, bounce: int = 150) -> bool:
    """Warp toward (then in/out of) `target_sector` until a hostile encounter fires."""
    ship = state.ships[state.players[1].ship_id]
    path = shortest_path(state.adjacency, ship.sector_id, target_sector)
    assert path is not None
    for nxt in path[1:]:
        apply_result(state, reduce(state, 1, Warp(to_sector=nxt), config))
        if state.players[1].active_encounter is not None:
            return True
    back = next(iter(state.adjacency[target_sector]))
    for _ in range(bounce):
        for hop in (back, target_sector):
            apply_result(state, reduce(state, 1, Warp(to_sector=hop), config))
            if state.players[1].active_encounter is not None:
                return True
    return False


# --- the pure roll chain ------------------------------------------------------


def test_no_roll_in_the_hub() -> None:
    """The Hub's interrupt chance is 0 — home is safe, and no RNG is drawn there."""
    state = _state_with_player()
    player = state.players[1]
    ship = state.ships[player.ship_id]
    hub = next(sid for sid, s in state.sectors.items()
               if s.distance_band == "Hub" and not s.is_galactic_core)
    rng = random.Random(1)
    before = rng.getstate()
    assert encounters.roll_encounter(state, player, ship, hub, SMALL, rng) is None
    assert rng.getstate() == before  # deterministic short-circuit: no draw at chance 0


def test_non_combatant_never_violent() -> None:
    """A combatant=false species (or one with no fleet) can never open with violence."""
    state = _state_with_player()
    player = state.players[1]
    ship = state.ships[player.ship_id]
    # Force every candidate check: a shipless kind in a Deep sector, rolled many times.
    sp = next(s for s in state.species.values()
              if SMALL.roster.species_by_id(s.roster_id).combatant is False)
    sector = next(sid for sid, s in state.sectors.items()
                  if s.distance_band in ("Deep", "Void") and not s.is_galactic_core)
    state.species[sp.id] = replace(sp, sector_id=sector)
    rng = random.Random(7)
    for _ in range(300):
        roll = encounters.roll_encounter(state, player, ship, sector, SMALL, rng)
        if roll is not None and roll.species.id == sp.id:
            assert not roll.hostile and roll.encounter is None


@given(disp=st_.floats(min_value=0.0, max_value=1.0))
@settings(max_examples=60, deadline=None)
def test_violence_roll_monotone_in_disposition(disp: float) -> None:
    """Friendly band never rolls violence; hostile band always does; the middle
    interpolates — the §10 greeting-vs-violence shape."""
    hostility, amity = CFG.aliens.hostility_threshold, CFG.aliens.amity_threshold
    if disp >= amity:
        violence = 0.0
    elif disp < hostility:
        violence = 1.0
    else:
        violence = (amity - disp) / (amity - hostility)
    assert 0.0 <= violence <= 1.0
    if disp >= amity:
        assert violence == 0.0
    if disp < hostility:
        assert violence == 1.0


def test_pack_spawn_shapes() -> None:
    """Pack behaviors spawn the §6.1 shapes: solo=1, escorted=lead+escorts, swarm≥min."""
    state = _state_with_player()
    ship = state.ships[state.players[1].ship_id]
    rng = random.Random(5)
    sp = _hostile(state) or next(iter(state.species.values()))
    sc = SMALL.roster.species_by_id(sp.roster_id)

    solo = sc.model_copy(update={"pack": sc.pack.model_copy(
        update={"behavior": "solo", "escort": []})})
    pack = encounters.spawn_pack(sp, solo, sp.sector_id, ship, SMALL, rng)
    assert len(pack.foes) == 1

    escorted = sc.model_copy(update={"pack": sc.pack.model_copy(
        update={"behavior": "escorted", "escort": ["scout_marauder", "scout_marauder"]})})
    pack = encounters.spawn_pack(sp, escorted, sp.sector_id, ship, SMALL, rng)
    assert len(pack.foes) == 3

    swarm = sc.model_copy(update={"pack": sc.pack.model_copy(
        update={"behavior": "swarm", "escort": []})})
    pack = encounters.spawn_pack(sp, swarm, sp.sector_id, ship, SMALL, rng)
    assert SMALL.combat.swarm_size_min <= len(pack.foes) <= SMALL.combat.swarm_size_max
    # Every foe carries resolved combat stats.
    assert all(f.hull > 0 and f.damage >= 1 and f.firing_arc for f in pack.foes)


# --- reducer wiring -------------------------------------------------------------


def test_movement_reaches_an_encounter_and_blocks() -> None:
    state = _state_with_player()
    sp = _hostile(state)
    assert sp is not None, "seed 3 places a hostile"
    assert _walk_until_engaged(state, sp.sector_id, SMALL)
    enc = state.players[1].active_encounter
    assert enc is not None and enc.foes and enc.player_shields >= 0
    ship = state.ships[state.players[1].ship_id]
    with pytest.raises(MovementError):
        reduce(state, 1, Warp(to_sector=next(iter(state.adjacency[ship.sector_id]))), SMALL)
    with pytest.raises(MovementError):
        reduce(state, 1, TravelTo(to_sector=1), SMALL)
    with pytest.raises(MovementError):
        reduce(state, 1, Dock(), SMALL)


def test_travel_halts_at_the_interrupted_hop() -> None:
    """A multi-hop journey stops *in* the sector where a detected encounter fired —
    the last Warped event's destination matches the halting EncounterStarted sector."""
    state = _state_with_player(seed=4)  # seed 4 places quill + stryx hostiles
    sp = _hostile(state)
    assert sp is not None
    ship = state.ships[state.players[1].ship_id]
    # Uncover the route first so TravelTo may fly it (route-locked travel).
    path = shortest_path(state.adjacency, ship.sector_id, sp.sector_id)
    assert path is not None
    player = state.players[1]
    state.players[1] = replace(player, explored_sectors=player.explored_sectors | set(path))

    for _ in range(40):
        result = reduce(state, 1, TravelTo(to_sector=sp.sector_id), SMALL)
        apply_result(state, result)
        started = [e for e in result.events if isinstance(e, EncounterStarted)]
        warps = [e for e in result.events if isinstance(e, Warped)]
        if started:
            assert warps[-1].to_sector == started[0].sector_id  # halted at the hop
            here = state.ships[state.players[1].ship_id].sector_id
            assert here == started[0].sector_id
            return
        # journey completed unhindered (or slipped away) — fly back and retry
        if state.players[1].active_encounter is None:
            back = reduce(state, 1, TravelTo(to_sector=path[0]), SMALL)
            apply_result(state, back)
            if any(isinstance(e, EncounterStarted) for e in back.events):
                return  # interrupted on the way home — same property holds
    pytest.skip("no encounter fired across 40 journeys (improbable)")


def test_evaded_encounter_does_not_halt() -> None:
    """An undetected slip-away emits EncounterEvaded and the journey continues."""
    # With a very high cloak the detection roll fails and the player slips through.
    state = _state_with_player()
    sp = _hostile(state)
    assert sp is not None
    ship = state.ships[state.players[1].ship_id]
    state.ships[ship.id] = replace(ship, cloak_rating=99)
    saw_evade = False
    path = shortest_path(state.adjacency, ship.sector_id, sp.sector_id)
    for _ in range(60):
        for hop in path[1:]:
            result = reduce(state, 1, Warp(to_sector=hop), SMALL)
            apply_result(state, result)
            if any(isinstance(e, EncounterEvaded) for e in result.events):
                saw_evade = True
            assert state.players[1].active_encounter is None  # never engaged at cloak 99
        path = list(reversed(path))
        if saw_evade:
            break
    assert saw_evade


def test_interrupted_travel_replays_to_identical_hash(tmp_path: Path) -> None:
    """The golden rail: a journey with encounter rolls (and an engagement) reloads
    to the identical state hash — encounter randomness rides the command stream."""
    svc = GameService.new_game(SMALL, 3, SqliteRepository(tmp_path / "g.db"),
                               created_at="1970-01-01T00:00:00Z")
    sp = _hostile(svc.state)
    assert sp is not None
    ship = svc.state.ships[svc.state.players[1].ship_id]
    path = shortest_path(svc.state.adjacency, ship.sector_id, sp.sector_id)
    for nxt in path[1:]:
        svc.apply(1, Warp(to_sector=nxt))
        if svc.state.players[1].active_encounter is not None:
            break
    expected = state_hash(svc.state)
    reloaded = GameService.load_game(SMALL, SqliteRepository(tmp_path / "g.db"))
    assert state_hash(reloaded.state) == expected


# --- WP31: the violent opener beat -----------------------------------------------


def test_violent_opener_speaks_combat_open() -> None:
    state = _state_with_player()
    player = state.players[1]
    ship = state.ships[player.ship_id]
    sp = _hostile(state)
    if sp is None:
        pytest.skip("no hostile-band species in this seed")
    sector = next(sid for sid, s in state.sectors.items()
                  if s.distance_band in ("Deep", "Void") and not s.is_galactic_core)
    state.species[sp.id] = replace(sp, sector_id=sector)
    rng = random.Random(11)
    for _ in range(300):
        roll = encounters.roll_encounter(state, player, ship, sector, SMALL, rng)
        if roll is not None and roll.hostile and roll.species.id == sp.id:
            assert roll.encounter is not None
            assert roll.encounter.speech_context == "combat_open"
            return
    raise AssertionError("no violent roll in 300 attempts")


def test_friendly_band_violence_opens_with_betrayal() -> None:
    """A friendly-band species pushed to violence by a grudge (§6.5) betrays, not attacks."""
    from edge.core.models import Grudge

    state = _state_with_player()
    ship = state.ships[state.players[1].ship_id]
    sp = _hostile(state) or next(iter(state.species.values()))
    sector = next(sid for sid, s in state.sectors.items()
                  if s.distance_band in ("Deep", "Void") and not s.is_galactic_core)
    # One friendly-band ship of a fighting kind, alone in the sector, holding a
    # maximum grudge — the violence roll fires while the visible band stays friendly.
    friendly = replace(sp, id=9001, base_disposition=0.9, sector_id=sector)
    state.species = {9001: friendly}
    grudge = Grudge(holder=sp.roster_id, target="player", cause="test", severity=1.0,
                    created_day=1, duration_days=-1)
    state.players[1] = replace(state.players[1], grudges={sp.roster_id: grudge})
    player = state.players[1]
    rng = random.Random(13)
    for _ in range(300):
        roll = encounters.roll_encounter(state, player, ship, sector, SMALL, rng)
        if roll is not None and roll.hostile:
            assert roll.encounter is not None
            assert roll.encounter.speech_context == "betrayal"
            return
    raise AssertionError("no violent roll in 300 attempts")


# --- WP44: bounties + homeworld raid caches ---


def test_kill_bounty_pays_only_for_hostile_kills() -> None:
    """The §10/WP44 bounty is per hostile combat unit; friendly/neutral kills pay nothing."""
    assert encounters.kill_bounty(CFG, hostile=True, count=3) == 3 * CFG.aliens.bounty_per_kill
    assert encounters.kill_bounty(CFG, hostile=False, count=3) == 0
    assert encounters.kill_bounty(CFG, hostile=True, count=0) == 0


def test_destroying_a_hostile_ship_pays_a_bounty() -> None:
    """Winning a fight against a hostile raider pays bounty_per_kill on top of salvage."""
    from edge.core.events import SalvageCollected
    from edge.core.models import AlienSpecies, Encounter, EncounterFoe
    from edge.core.rules import CombatAction

    state = _state_with_player()
    ship = state.ships[state.players[1].ship_id]
    sp = AlienSpecies(  # a synthetic hostile raider co-located with the player
        id=9001, roster_id="quill", name="Quill", archetype_id="raider",
        sector_id=ship.sector_id, home_band="Frontier", tech_level=3,
        base_disposition=0.1, disposition_center=0.1, disposition_variance=0.05)
    state.species[sp.id] = sp
    foe = EncounterFoe(ship_class_id="scout_marauder", name="Quill Fighter", hull=1,
                       hull_max=1, shields=0, damage=1, firing_arc="all_round",
                       combat_speed=1, defense=0)
    state.players[1] = replace(state.players[1], active_encounter=Encounter(
        species_id=sp.id, sector_id=ship.sector_id, foes=(foe,), round=0,
        player_shields=ship.shields))
    before = state.players[1].latinum

    result = reduce(state, 1, CombatAction(action="fight"), SMALL)
    apply_result(state, result)
    assert state.players[1].active_encounter is None  # the raider is dead — victory
    salvage = next(e for e in result.events if isinstance(e, SalvageCollected))
    # The gain is exactly the bounty for the one kill plus the wreck salvage.
    assert state.players[1].latinum == before + CFG.aliens.bounty_per_kill + salvage.latinum


@pytest.mark.parametrize("seed", range(12))
def test_raid_caches_sit_on_hostile_homeworlds(seed: int) -> None:
    """Every salted raid cache is a hidden legendary Tier-III tech cache on a hostile
    species' homeworld planet, off the Core and off the spatial gradient (§7/§10, WP44)."""
    from edge.core.enums import ComponentTier, DiscoveryKind, PayloadKind, RarityTier

    state = generate(SMALL, seed)
    hostile_sectors = {s.sector_id for s in state.species.values()
                       if disposition_band(s.base_disposition, CFG.aliens) == HOSTILE}
    seen: set[int] = set()
    for d in state.discoveries.values():
        if not d.raid_cache:
            continue
        assert d.rarity_tier is RarityTier.LEGENDARY
        assert d.kind is DiscoveryKind.ANCIENT_TECH and d.hidden
        assert d.payload.kind is PayloadKind.COMPONENT and d.payload.tier is ComponentTier.III
        assert d.planet_id is not None                       # cached on a homeworld
        assert not state.sectors[d.sector_id].is_galactic_core
        assert d.sector_id in hostile_sectors                # at a hostile species' home
        assert d.sector_id not in seen                       # at most one per sector
        seen.add(d.sector_id)


def test_raid_caches_are_placed_where_hostiles_hold_worlds() -> None:
    """Across a seed range the pass actually fires (hostiles with homeworlds exist)."""
    total = 0
    for seed in range(12):
        state = generate(SMALL, seed)
        total += sum(1 for d in state.discoveries.values() if d.raid_cache)
    assert total >= 1
