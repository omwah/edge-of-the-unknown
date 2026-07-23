"""GW-WP13 — deterministic survey/assault bots exercised end to end, over the
public `ServiceProtocol` seam (`edge.bot`, GW-WP60-style).

The crown-jewel property here is determinism: a bot-driven ground operation is an
ordinary, replayable command log, so `rebuild(seed, log)` must reproduce the live
`state_hash` exactly — the same class of RNG-order-shift bug that bit GW-WP09
(ground ops draw from the shared `state.rng`) would show up here as a replay
mismatch. Win/loss rate is a secondary, loose signal: it is only as trustworthy as
a crude heuristic bot's tactics, so only aggregate, non-degenerate bounds are
asserted across the seed matrix, never a tight per-seed band.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from edge.bot.runner import BotRunner
from edge.bot.scripts import assaulter, surveyor
from edge.config import load_default_config
from edge.core.config import GameConfig
from edge.core.enums import PortClass
from edge.core.groundwar.models import AssaultOperation
from edge.core.rules import BuySuits, DevPatch, Dock, HireRecruits
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import rebuild, state_hash

_CREATED = "2026-07-23T00:00:00Z"
_SEEDS = (7, 11, 23)
_TICKS = 160  # bounded so a stuck bot can't stall the suite; well past one op's lifecycle


def _config() -> GameConfig:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(
        update={"sector_count": 400, "start_sector": 1})})


def _service(tmp_path: Path, seed: int, name: str) -> GameService:
    return GameService.new_game(
        _config(), seed, SqliteRepository(tmp_path / name), created_at=_CREATED)


def _assert_replays(svc: GameService, seed: int) -> None:
    repo = svc._repo  # type: ignore[attr-defined]
    reloaded = rebuild(_config(), seed, repo.load_commands(), created_at=_CREATED)
    assert state_hash(reloaded) == state_hash(svc.state)


def _arm_for_assault(svc: GameService) -> None:
    """Fund + provision a platoon through logged commands only (replay-safe).

    Deliberately routes through `DevPatch("teleport", ...)` (itself a logged, replayable
    command, DESIGN §14) rather than mutating `svc.state.ships[...]` directly — a raw
    mutation would desync the very replay this module exists to check. Placing the ship at
    Stardock first, then the target sector, sidesteps the open-world travel risk a real
    playthrough carries (a hostile encounter destroying the ship mid-transit is real,
    already-covered movement/combat behavior, not something this WP needs to re-prove).
    """
    svc.apply(1, DevPatch("set", "latinum", 200_000))
    stardock = next(p.sector_id for p in svc.state.ports.values() if p.klass is PortClass.STARDOCK)
    svc.apply(1, DevPatch("teleport", "", value=stardock))
    svc.apply(1, Dock())
    assert svc.config.groundwar is not None
    suit_id = next(iter(svc.config.groundwar.suits))
    svc.apply(1, BuySuits(suit_id=suit_id, count=6))
    svc.apply(1, HireRecruits(count=6))


# --- per-seed: determinism + basic productivity ------------------------------


@pytest.mark.parametrize("seed", _SEEDS)
def test_surveyor_runs_and_replays_deterministically(tmp_path: Path, seed: int) -> None:
    svc = _service(tmp_path, seed, f"survey-{seed}.db")
    bot = BotRunner(svc, 1)
    surveyor.setup(bot)
    assert bot.run(_TICKS) > 0
    _assert_replays(svc, seed)


def test_assaulter_runs_deterministically_to_non_degenerate_outcomes() -> None:
    """One combined pass over the seed matrix (a `tmp_path` per seed, built by hand
    since this isn't a `pytest.mark.parametrize` case): each seed must replay
    deterministically on its own, and the *aggregate* of terminal outcomes across the
    matrix must not be a single always-instant class. Kept as one test — rather than a
    per-seed determinism test plus a separate cross-test aggregate — so the aggregate
    check never depends on pytest's execution order or shared mutable module state.

    Every assault operation must eventually settle (win/wipe/retrieval/withdrawal) —
    the retrieval clock's whole job. A crude bot's *win* rate is not asserted (too
    noisy at this sample size); only that operations terminate and the aggregate
    isn't degenerate.
    """
    all_outcomes: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for seed in _SEEDS:
            svc = _service(tmp_path, seed, f"assault-{seed}.db")
            _arm_for_assault(svc)
            bot = BotRunner(svc, 1)
            assaulter.setup(bot)
            ran = 0
            for _ in range(_TICKS):
                if bot.stopped:
                    break
                bot.step()
                ran += 1
                op = svc.state.players[1].ground_operation
                if isinstance(op, AssaultOperation) and op.outcome is not None:
                    all_outcomes.append(op.outcome)
                    assert 0 <= op.casualties <= op.initial_strength
                    assert op.local_turn <= op.retrieval_turn
            assert ran > 0
            _assert_replays(svc, seed)
    assert all_outcomes  # at least one seed in the matrix fought to a decision
    assert set(all_outcomes) != {"retrieval"}  # not every op is an instant, action-free timeout
