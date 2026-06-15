"""WP5 — persistence + golden-master replay (DESIGN §12, §13).

Records a command sequence to SQLite, then proves that regenerating from the
seed and replaying the saved log reproduces the exact same state hash — through
both a reloaded repository and a gzipped portable save.
"""

from __future__ import annotations

from pathlib import Path

from edge.bigbang.generator import generate
from edge.config import load_default_config
from edge.core.enums import Commodity, PortClass
from edge.core.movement import shortest_path
from edge.core.rules import (
    Command,
    Deposit,
    Dock,
    HaggleOffer,
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
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 90})})


def _scripted_commands(state: object) -> list[tuple[int, Command]]:
    """A deterministic run: warp to the StarDock, trade, haggle, and bank."""
    dock = next(p for p in state.ports.values() if p.klass is PortClass.STARDOCK)  # type: ignore[attr-defined]
    path = shortest_path(state.adjacency, 1, dock.sector_id)  # type: ignore[attr-defined]
    assert path is not None
    commands: list[tuple[int, Command]] = [(1, Warp(to_sector=s)) for s in path[1:]]
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
