"""WP7 — the engine cron reducers and tick scheduler (DESIGN §9)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from edge.config import load_default_config
from edge.engine.cron import accrue_interest, daily_turn_reset, regenerate_ports
from edge.engine.ticker import EngineTicker
from edge.server.service import GameService
from edge.store.repo import SqliteRepository

_CREATED = "2026-06-15T00:00:00Z"


def _config() -> object:
    cfg = load_default_config()
    return cfg.model_copy(update={"bigbang": cfg.bigbang.model_copy(update={"sector_count": 90})})


def _service(tmp_path: Path) -> GameService:
    return GameService.new_game(_config(), 42, SqliteRepository(tmp_path / "g.db"), created_at=_CREATED)  # type: ignore[arg-type]


def test_daily_turn_reset_refills_and_advances_day(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    svc._state.players[1] = replace(svc.state.players[1], turns_remaining=3)  # type: ignore[attr-defined]
    day0 = svc.state.game.day_number
    svc.apply_maintenance(daily_turn_reset(svc.state, svc.config))
    assert svc.state.players[1].turns_remaining == 250
    assert svc.state.game.day_number == day0 + 1


def test_interest_grows_only_nonempty_balances(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    svc._state.players[1] = replace(svc.state.players[1], bank_balance=10_000)  # type: ignore[attr-defined]
    svc.apply_maintenance(accrue_interest(svc.state, svc.config))
    assert svc.state.players[1].bank_balance == 10_050  # 0.5%/day


def test_regen_moves_stock_toward_desired(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    port = next(iter(svc.state.ports.values()))
    drained = replace(port, commodities=tuple(replace(c, stock=0) for c in port.commodities))
    svc._state.ports[port.id] = drained  # type: ignore[attr-defined]
    svc.apply_maintenance(regenerate_ports(svc.state, svc.config))
    assert all(c.stock > 0 for c in svc.state.ports[port.id].commodities)


def test_cron_cadence_fires_once_per_interval(tmp_path: Path) -> None:
    svc = _service(tmp_path)
    ticker = EngineTicker(svc, tick_seconds=0.0, ticks_per_hour=2, ticks_per_day=5)
    fired_by_tick = [ticker.step() for _ in range(5)]
    # hourly (interval 2) at ticks 2 and 4; the day crons (interval 5) at tick 5.
    assert fired_by_tick[1] == ["hourly_port_economy"]  # tick 2
    assert fired_by_tick[3] == ["hourly_port_economy"]  # tick 4
    assert fired_by_tick[4] == ["interest_accrual", "daily_turn_reset"]  # tick 5
    assert fired_by_tick[0] == [] and fired_by_tick[2] == []  # no spurious/double fires


async def test_async_run_ticks_then_stops(tmp_path: Path) -> None:
    import asyncio

    svc = _service(tmp_path)
    ticker = EngineTicker(svc, tick_seconds=0.001, ticks_per_hour=2, ticks_per_day=5)
    task = asyncio.create_task(ticker.run())
    await asyncio.sleep(0.05)
    ticker.stop()
    await asyncio.wait_for(task, timeout=1.0)
    assert ticker.tick > 0  # the loop advanced
