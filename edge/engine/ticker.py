"""The engine tick loop (DESIGN §9).

twclone's two-level scheduling, Phase-1 subset: a short tick advances a logical
tick counter and fires durable cron tasks at their cadence — hourly port-economy
regen, daily interest accrual, daily turn reset. Each cron tracks `next_due` (in
ticks), so it fires exactly once per interval: never skipped, never double-run.

`step()` is the pure, synchronous heart (directly unit-testable); `run()` is the
thin asyncio wrapper that calls it on a real-time timer. Cadence is given in ticks
so tests can drive fast, deterministic ticks while real time uses 3600/86400.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from edge.core.config import GameConfig
from edge.core.models import UniverseState
from edge.core.rules import ReduceResult
from edge.engine.cron import accrue_interest, daily_turn_reset, planet_growth, regenerate_ports
from edge.server.service import GameService

CronFn = Callable[[UniverseState, GameConfig], ReduceResult]


@dataclass
class CronTask:
    name: str
    interval: int  # in ticks
    fn: CronFn
    next_due: int


class EngineTicker:
    """Schedules and runs the Phase-1 cron tasks against a `GameService`."""

    def __init__(
        self, service: GameService, *, tick_seconds: float = 1.0,
        ticks_per_hour: int = 3600, ticks_per_day: int = 86_400,
    ) -> None:
        self._service = service
        self._tick_seconds = tick_seconds
        self._tick = 0
        self._running = False
        self._crons = [
            CronTask("hourly_port_economy", ticks_per_hour, regenerate_ports, ticks_per_hour),
            CronTask("hourly_planet_growth", ticks_per_hour, planet_growth, ticks_per_hour),
            CronTask("interest_accrual", ticks_per_day, accrue_interest, ticks_per_day),
            CronTask("daily_turn_reset", ticks_per_day, daily_turn_reset, ticks_per_day),
        ]

    @property
    def tick(self) -> int:
        return self._tick

    def step(self) -> list[str]:
        """Advance one tick and run any now-due crons; return their names."""
        self._tick += 1
        fired: list[str] = []
        for cron in self._crons:
            while self._tick >= cron.next_due:
                self._service.apply_maintenance(cron.fn(self._service.state, self._service.config))
                cron.next_due += cron.interval
                fired.append(cron.name)
        return fired

    async def run(self) -> None:
        """Tick on a real-time timer until `stop()` (the asyncio task, §3)."""
        self._running = True
        while self._running:
            await asyncio.sleep(self._tick_seconds)
            self.step()

    def stop(self) -> None:
        self._running = False
