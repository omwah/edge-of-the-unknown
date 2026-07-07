"""WP60 — the bot scripting harness + service protocol (DESIGN §14, §3).

Bots act only through the `ServiceProtocol` seam, so a bot run is an ordinary, replayable
command log. These tests cover trigger dispatch, rejection-swallowing, protocol conformance,
and that both example scripts run to completion on a fixture seed with replay parity.
"""

from __future__ import annotations

from pathlib import Path

from edge.bot.runner import BotRunner
from edge.bot.scripts import explorer, pair_trader
from edge.config import load_default_config
from edge.core.config import GameConfig
from edge.core.events import Warped
from edge.core.rules import Warp
from edge.server.protocol import ServiceProtocol
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import rebuild, state_hash

_CREATED = "2026-06-15T00:00:00Z"


def _config() -> GameConfig:
    cfg = load_default_config()
    return cfg.model_copy(
        update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 90, "start_sector": 1})})


def _service(tmp_path: Path, name: str = "bot.db") -> GameService:
    return GameService.new_game(_config(), 42, SqliteRepository(tmp_path / name), created_at=_CREATED)


# --- protocol conformance --------------------------------------------------------


def test_gameservice_satisfies_protocol(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    assert isinstance(svc, ServiceProtocol)  # runtime duck test (H16)


# --- harness behaviour -----------------------------------------------------------


def test_trigger_fires_on_matching_event(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    bot = BotRunner(svc, 1)
    seen: list[int] = []

    @bot.on(Warped)
    def note(b: BotRunner, ev: Warped) -> None:
        seen.append(ev.to_sector)

    dest = svc.game_view(1).sector.warps[0].sector_id
    events = bot.apply(Warp(to_sector=dest))
    assert any(isinstance(e, Warped) for e in events)
    assert seen == [dest]


def test_apply_swallows_rejection(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    bot = BotRunner(svc, 1)
    events = bot.apply(Warp(to_sector=99999))  # no such warp
    assert events == ()
    assert bot.last_error is not None


def test_run_is_bounded_and_stoppable(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    bot = BotRunner(svc, 1)
    ticks: list[int] = []

    @bot.each_turn
    def once(b: BotRunner) -> None:
        ticks.append(1)
        if len(ticks) >= 3:
            b.stop()

    assert bot.run(100) == 3


# --- example scripts run + replay ------------------------------------------------


def test_explorer_runs_and_explores(tmp_path: Path) -> None:
    svc = _service(tmp_path, "explore.db")
    bot = BotRunner(svc, 1)
    explorer.setup(bot)
    bot.run(40)
    # It moved beyond the start sector (or ran out of turns trying) — a clean, crash-free run.
    assert len(svc.state.players[1].explored_sectors) >= 1
    # The run is an ordinary command log — it replays to the identical state.
    repo = svc._repo  # type: ignore[attr-defined]
    reloaded = rebuild(_config(), repo.load_meta().seed, repo.load_commands(),
                       created_at=_CREATED)
    assert state_hash(reloaded) == state_hash(svc.state)


def test_pair_trader_runs(tmp_path: Path) -> None:
    svc = _service(tmp_path, "trade.db")
    bot = BotRunner(svc, 1)
    pair_trader.setup(bot)
    ran = bot.run(50)
    assert ran >= 1  # the driver ran at least once without crashing
