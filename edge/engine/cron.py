"""Pure cron reducers run by the engine tick loop (DESIGN §9).

Each is a deterministic `(state, config) -> ReduceResult` — no RNG, no I/O — so
the engine layer mutates state only through the same reducer/event discipline as
player commands. Phase-1 crons: the daily turn reset, daily interest accrual, and
the hourly port-economy regen (re-exported from `port_economy`).
"""

from __future__ import annotations

from dataclasses import replace

from edge.core.config import GameConfig
from edge.core.economy import accrue_interest as _accrue
from edge.core.events import Banked, TurnsReset
from edge.core.models import UniverseState
from edge.core.rules import ReduceResult
from edge.engine.port_economy import regenerate_ports

__all__ = ["daily_turn_reset", "accrue_interest", "regenerate_ports"]


def daily_turn_reset(state: UniverseState, config: GameConfig) -> ReduceResult:
    """Refill every player's turns and advance the game day (TWINSTR.DOC, §9)."""
    players = tuple(
        replace(p, turns_remaining=config.turns_per_day) for p in state.players.values()
    )
    events = tuple(TurnsReset(player_id=p.id, turns=config.turns_per_day) for p in players)
    game = replace(state.game, day_number=state.game.day_number + 1)
    return ReduceResult(events=events, players=players, game=game)


def accrue_interest(state: UniverseState, config: GameConfig) -> ReduceResult:
    """Compound interest on every non-empty bank balance (§8)."""
    rate = config.economy.bank_interest_per_day
    players = []
    events = []
    for p in state.players.values():
        if p.bank_balance <= 0:
            continue
        new_balance = _accrue(p.bank_balance, rate)
        if new_balance == p.bank_balance:
            continue
        players.append(replace(p, bank_balance=new_balance))
        events.append(Banked(p.id, "interest", new_balance - p.bank_balance, new_balance))
    return ReduceResult(events=tuple(events), players=tuple(players))
