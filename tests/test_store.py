"""WP5 — persistence + golden-master replay (DESIGN §12, §13).

Records a command sequence to SQLite, then proves that regenerating from the
seed and replaying the saved log reproduces the exact same state hash — through
both a reloaded repository and a gzipped portable save.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core.enums import Commodity, PortClass
from edge.core.movement import shortest_path
from edge.core.rules import (
    Command,
    Deposit,
    Dock,
    HaggleOffer,
    JoinGame,
    Trade,
    Warp,
    Withdraw,
    apply_result,
    reduce,
)
from edge.store.repo import SqliteRepository
from edge.store.snapshots import (
    export_save,
    import_save,
    rebuild,
    rebuild_from_bundle,
    state_hash,
)

_CREATED = "2026-06-15T00:00:00Z"


def _small_config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 90, "start_sector": 1})})


def _scripted_commands(state: object) -> list[tuple[int, Command]]:
    """A deterministic run: warp to the Stardock, trade, haggle, and bank."""
    dock = next(p for p in state.ports.values() if p.klass is PortClass.STARDOCK)  # type: ignore[attr-defined]
    path = shortest_path(state.adjacency, 1, dock.sector_id)  # type: ignore[attr-defined]
    assert path is not None
    # The player joins via a recorded JoinGame (the big bang no longer seeds players),
    # so it leads the log and `rebuild` reconstructs the player before replaying the rest.
    commands: list[tuple[int, Command]] = [(1, JoinGame())]
    commands += [(1, Warp(to_sector=s)) for s in path[1:]]
    commands += [
        (1, Dock()),
        (1, Trade(commodity=Commodity.FUEL_ORE, units=5)),
        (1, HaggleOffer(commodity=Commodity.ORGANICS, units=3, counter_price=4)),
        (1, Deposit(amount=300)),
        (1, Withdraw(amount=100)),
    ]
    return commands


def test_command_log_replay_reproduces_state(tmp_path: Path) -> None:
    config = _small_config()
    seed = 42
    live = generate(config, seed, created_at=_CREATED)  # type: ignore[arg-type]
    commands = _scripted_commands(live)

    repo = SqliteRepository(tmp_path / "game.db")
    repo.save_meta(live.game)
    for player_id, command in commands:
        apply_result(live, reduce(live, player_id, command, config))  # type: ignore[arg-type]
        repo.append_command(player_id, command)
    expected = state_hash(live)

    # Reload from the repository and replay -> identical state.
    meta = repo.load_meta()
    assert meta.seed == seed and meta.created_at == _CREATED
    reloaded = rebuild(config, meta.seed, repo.load_commands(), created_at=meta.created_at)  # type: ignore[arg-type]
    assert state_hash(reloaded) == expected

    # The gzipped portable save round-trips to the same state too.
    blob = export_save(repo)
    bundle = import_save(blob)
    assert bundle.seed == seed
    assert state_hash(rebuild_from_bundle(config, bundle)) == expected  # type: ignore[arg-type]
    repo.close()


def test_ticked_game_export_round_trips(tmp_path: Path) -> None:
    """WP12: a portable save of a *ticked* game replays its maintenance timeline."""
    from edge.engine.cron import resolve_cron
    from edge.engine.ticker import EngineTicker
    from edge.server.service import GameService

    config = _small_config()
    svc = GameService.new_game(config, 42, SqliteRepository(tmp_path / "t.db"), created_at=_CREATED)  # type: ignore[arg-type]
    target = svc.state.sectors[1].warps_out[0]
    svc.apply(1, Warp(to_sector=target))
    ticker = EngineTicker(svc, tick_seconds=0.0, ticks_per_hour=2, ticks_per_day=5)
    for _ in range(6):
        ticker.step()
    expected = state_hash(svc.state)

    blob = export_save(SqliteRepository(tmp_path / "t.db"))
    bundle = import_save(blob)
    assert bundle.maintenance  # the maintenance timeline travelled with the save
    rebuilt = rebuild_from_bundle(config, bundle, cron_resolver=resolve_cron)  # type: ignore[arg-type]
    assert state_hash(rebuilt) == expected


def test_repo_context_manager_and_missing_meta(tmp_path: Path) -> None:
    from edge.core.events import Banked
    from edge.store.repo import SqliteRepository

    with SqliteRepository(tmp_path / "empty.db") as repo:
        with pytest.raises(LookupError):
            repo.load_meta()  # nothing saved yet
        seq = repo.append_event(Banked(1, "interest", 5, 105), tick=3)
        assert seq >= 1  # event_log row id returned


def test_meta_persists_and_commands_are_ordered(tmp_path: Path) -> None:
    config = _small_config()
    live = generate(config, 7, created_at=_CREATED)  # type: ignore[arg-type]
    repo = SqliteRepository(tmp_path / "g.db")
    repo.save_meta(live.game)
    seqs = [repo.append_command(1, Deposit(amount=n)) for n in (10, 20, 30)]
    assert seqs == sorted(seqs)  # monotonic sequence
    loaded = repo.load_commands()
    assert [rc.seq for rc in loaded] == seqs
    assert all(isinstance(rc.command, Deposit) for rc in loaded)
    repo.close()
