"""edge.engine — time and background simulation (DESIGN §9).

An asyncio ticker: a short tick that consumes the event log plus durable cron
tasks (daily turn reset, hourly port-economy regen, interest accrual) with
persisted `next_due_at`, so a reloaded save never double-runs or skips a tick.
"""

from __future__ import annotations
