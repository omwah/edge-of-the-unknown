"""Pure cron reducers run by the engine tick loop (DESIGN §9).

Each is a deterministic `(state, config) -> ReduceResult` — no RNG, no I/O — so
the engine layer mutates state only through the same reducer/event discipline as
player commands. Phase-1 crons: the daily turn reset, daily interest accrual, and
the hourly port-economy regen (re-exported from `port_economy`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from edge.core.config import GameConfig
from edge.core.economy import accrue_interest as _accrue
from edge.core.events import Banked, ColonyGrew, Event, PlanetProduced, TurnsReset
from edge.core.models import UniverseState
from edge.core.planets import produce
from edge.core.rules import ReduceResult
from edge.engine.port_economy import regenerate_ports

CronFn = Callable[[UniverseState, GameConfig], ReduceResult]

__all__ = [
    "daily_turn_reset", "accrue_interest", "regenerate_ports", "planet_growth",
    "CronFn", "CRONS", "resolve_cron",
]


def daily_turn_reset(state: UniverseState, config: GameConfig) -> ReduceResult:
    """Refill every player's turns and advance the game day (TWINSTR.DOC, §9).

    Also clears the per-day haggle-attempt counters (§8, WP13) so each port's patience
    is fresh at dawn; like turns, this rides the daily cron through the replay timeline.
    """
    players = tuple(
        replace(p, turns_remaining=config.turns_per_day, haggle_attempts={})
        for p in state.players.values()
    )
    events = tuple(TurnsReset(player_id=p.id, turns=config.turns_per_day) for p in players)
    game = replace(state.game, day_number=state.game.day_number + 1)
    return ReduceResult(events=events, players=players, game=game)


def planet_growth(state: UniverseState, config: GameConfig) -> ReduceResult:
    """Run BNT production for every owned planet (§4.2, §8).

    Pure and deterministic. Only the player's own colonies announce output (so the
    log isn't flooded by every alliance holding); alliance worlds evolve silently —
    their stores still update, just without an event.
    """
    changed = []
    events: list[Event] = []
    for planet in state.planets.values():
        produced = produce(planet, config)
        if produced is planet:
            continue
        changed.append(produced)
        if planet.owner.kind == "player" and planet.owner.ref is not None:
            events.append(PlanetProduced(planet.id, planet.owner.ref))
            if produced.colonists != planet.colonists:
                events.append(ColonyGrew(planet.id, produced.colonists))
    return ReduceResult(events=tuple(events), planets=tuple(changed))


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


# The canonical cron name → pure reducer registry (WP12). The ticker schedules
# these by name and persists each firing as a `MaintenanceTick`; replay (rebuild)
# resolves the name back to the reducer through `resolve_cron`, re-running it in
# the merged command+maintenance order. Names are durable — keep them stable.
CRONS: dict[str, CronFn] = {
    "hourly_port_economy": regenerate_ports,
    "hourly_planet_growth": planet_growth,
    "interest_accrual": accrue_interest,
    "daily_turn_reset": daily_turn_reset,
}


def resolve_cron(name: str) -> CronFn:
    """The pure reducer for a persisted cron name (raises on an unknown name)."""
    try:
        return CRONS[name]
    except KeyError as exc:
        raise ValueError(f"unknown cron {name!r}") from exc
