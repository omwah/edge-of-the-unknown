"""The engine tick loop (DESIGN §9).

A short tick advances a logical tick counter and fires durable cron tasks at
configurable cadences (``ticker.crons`` in the game config).  Each cron tracks
``next_due`` (in ticks), so it fires exactly once per interval: never skipped,
never double-run.

``step()`` is the pure, synchronous heart (directly unit-testable); ``run()`` is
the thin asyncio wrapper that calls it on a real-time timer.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from edge.engine.cron import CRONS, CronFn
from edge.server.service import GameService


@dataclass
class CronTask:
    name: str
    interval: int  # in ticks
    fn: CronFn
    next_due: int


class EngineTicker:
    """Schedules and runs the Phase-1 cron tasks against a `GameService`.

    The schedule (tick counter + each cron's `next_due`) is durable (WP12): every
    step persists it, and a ticker built on a reloaded game restores it so firing
    resumes mid-interval — never double-running, never skipping.
    """

    def __init__(
        self, service: GameService, *,
        tick_seconds: float | None = None,
        ticks_per_hour: int | None = None,
        ticks_per_day: int | None = None,
    ) -> None:
        tc = service.config.ticker
        self._service = service
        self._tick_seconds = tick_seconds if tick_seconds is not None else tc.tick_seconds
        self._tick = 0
        self._running = False
        # Per-cron cadences from config; legacy kwargs override for tests.
        port_eco = ticks_per_hour if ticks_per_hour is not None else tc.crons.port_economy
        planet_gr = ticks_per_hour if ticks_per_hour is not None else tc.crons.planet_growth
        settlement = ticks_per_day if ticks_per_day is not None else tc.crons.market_settlement
        drift = tc.crons.alien_drift
        trader = tc.crons.trader_step
        interest = ticks_per_day if ticks_per_day is not None else tc.crons.interest_accrual
        turn_reset = ticks_per_day if ticks_per_day is not None else tc.crons.daily_turn_reset
        self._crons = [
            CronTask("hourly_port_economy", port_eco, CRONS["hourly_port_economy"], port_eco),
            CronTask("hourly_planet_growth", planet_gr, CRONS["hourly_planet_growth"], planet_gr),
            CronTask("market_settlement", settlement, CRONS["market_settlement"], settlement),
            CronTask("alien_drift", drift, CRONS["alien_drift"], drift),
            CronTask("trader_step", trader, CRONS["trader_step"], trader),
            CronTask("interest_accrual", interest, CRONS["interest_accrual"], interest),
            CronTask("daily_turn_reset", turn_reset, CRONS["daily_turn_reset"], turn_reset),
        ]
        self._restore_schedule()

    def _restore_schedule(self) -> None:
        """Resume the saved tick counter + per-cron next-due, if any (WP12)."""
        saved = self._service.load_engine_state()
        if saved is None:
            return
        self._tick = saved.tick
        for cron in self._crons:
            if cron.name in saved.schedule:
                cron.next_due = saved.schedule[cron.name]

    @property
    def tick(self) -> int:
        return self._tick

    def step(self) -> list[str]:
        """Advance one tick, run any now-due crons, and persist the schedule."""
        self._tick += 1
        fired: list[str] = []
        for cron in self._crons:
            while self._tick >= cron.next_due:
                result = cron.fn(self._service.state, self._service.config)
                self._service.apply_maintenance(result, cron_name=cron.name, tick=self._tick)
                cron.next_due += cron.interval
                fired.append(cron.name)
        self._service.save_engine_state(self._tick, {c.name: c.next_due for c in self._crons})
        return fired

    async def run(self) -> None:
        """Tick on a real-time timer until `stop()` (the asyncio task, §3)."""
        self._running = True
        while self._running:
            await asyncio.sleep(self._tick_seconds)
            self.step()

    def stop(self) -> None:
        self._running = False
