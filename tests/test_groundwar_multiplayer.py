"""GW-WP13 — multiplayer contention over ground operations.

Extends `tests/test_multiplayer.py`'s `BotSwarm` pattern (WP69) to survey/assault:
several seats share one authoritative `GameService`, stepped round-robin so their
ground-operation commands interleave into one totally-ordered log. The headline
proof is the same single-writer determinism check WP69 established — `rebuild(seed,
log)` must reproduce the live `state_hash` — plus two contention-specific
invariants WP13 asks for: no surface discovery is ever double-claimed across
players (G8, now stress-tested under real concurrent pressure rather than a single
player's own race), and two players assaulting the *same* world concurrently never
drives its garrison headcount negative.
"""

from __future__ import annotations

from pathlib import Path

from edge.bot import BotSwarm
from edge.bot.scripts import assaulter, surveyor
from edge.config import load_default_config
from edge.core.config import GameConfig
from edge.core.enums import PortClass
from edge.core.groundwar.access import Assault, ground_access
from edge.core.rules import BuySuits, DevPatch, Dock, HireRecruits, JoinGame
from edge.engine.cron import resolve_cron
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import rebuild, state_hash

_CREATED = "2026-07-23T00:00:00Z"
_SEED = 11
_ROUNDS = 140


def _cfg() -> GameConfig:
    base = load_default_config()
    return base.model_copy(update={"bigbang": base.bigbang.model_copy(
        update={"sector_count": 400, "start_sector": 1})})


def _game(tmp_path: Path, name: str) -> GameService:
    svc = GameService.new_game(
        _cfg(), _SEED, SqliteRepository(tmp_path / name), created_at=_CREATED)
    svc.apply(2, JoinGame())
    return svc


def _assert_replays(svc: GameService) -> None:
    repo = svc._repo  # type: ignore[attr-defined]
    live = state_hash(svc.state)
    rebuilt = rebuild(
        _cfg(), _SEED, repo.load_commands(), created_at=_CREATED,
        maintenance=repo.load_maintenance(), cron_resolver=resolve_cron)
    assert state_hash(rebuilt) == live


def test_two_surveyors_never_double_claim_a_discovery(tmp_path: Path) -> None:
    svc = _game(tmp_path, "gw-survey-mp.db")
    swarm = BotSwarm(svc)
    for pid in (1, 2):
        swarm.add(pid, surveyor.setup)
    swarm.run(rounds=_ROUNDS)

    claimed_ids = [
        rec.discovery_id
        for player in svc.state.players.values()
        for rec in player.artifact_records
    ]
    assert claimed_ids  # the swarm actually excavated something
    assert len(claimed_ids) == len(set(claimed_ids))  # G8: no discovery claimed twice

    _assert_replays(svc)


def _arm_for_assault(svc: GameService, player_id: int, stardock_sector: int, suit_id: str) -> None:
    svc.apply(player_id, DevPatch("set", "latinum", 200_000))
    svc.apply(player_id, DevPatch("teleport", "", value=stardock_sector))
    svc.apply(player_id, Dock())
    svc.apply(player_id, BuySuits(suit_id=suit_id, count=6))
    svc.apply(player_id, HireRecruits(count=6))


def test_two_assaulters_on_the_same_world_replay_deterministically(tmp_path: Path) -> None:
    svc = _game(tmp_path, "gw-assault-mp.db")
    state = svc.state
    stardock = next(p.sector_id for p in state.ports.values() if p.klass is PortClass.STARDOCK)
    assert svc.config.groundwar is not None
    suit_id = next(iter(svc.config.groundwar.suits))
    for pid in (1, 2):
        _arm_for_assault(svc, pid, stardock, suit_id)

    p1 = state.players[1]
    target = next(
        planet for planet in state.planets.values()
        if isinstance(access := ground_access(state, p1, planet, svc.config), Assault)
        and access.droppable
    )
    for pid in (1, 2):
        svc.apply(pid, DevPatch("teleport", "", value=target.sector_id))

    swarm = BotSwarm(svc)
    for pid in (1, 2):
        swarm.add(pid, assaulter.setup)
    swarm.run(rounds=_ROUNDS)

    settled = svc.state.planets[target.id]
    assert settled.garrison_infantry >= 0  # no negative headcount from a double-settlement race
    assert settled.garrison_armor >= 0

    _assert_replays(svc)
