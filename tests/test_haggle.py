"""WP13 — multi-round haggle sessions (DESIGN §8).

The history penalty that wears a port's patience, the per-day `max_rejections` close,
the daily-cron reset of the attempt counter, and its round-trip through a reload.
"""

from __future__ import annotations

import random
from dataclasses import replace
from pathlib import Path

from edge.config import load_default_config
from edge.core.economy import PortMode, haggle_acceptance_probability
from edge.core.enums import PORT_CLASS_TRADES, Commodity, PortClass
from edge.core.models import Game, Player, Port, PortCommodity, Ship, UniverseState
from edge.core.movement import shortest_path
from edge.core.rules import Dock, HaggleOffer, Warp, apply_result, reduce
from edge.engine.cron import daily_turn_reset
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import state_hash

CFG = load_default_config()
SMALL = CFG.model_copy(update={"bigbang": CFG.bigbang.model_copy(update={"sector_count": 90})})
_CREATED = "2026-06-18T00:00:00Z"


def _world() -> UniverseState:
    """A one-sector universe with a Class-1 port (it BUYS fuel ore) and a docked player."""
    state = UniverseState(game=Game(1, 1, 1, "t", core_governing_alliance_id=1),
                          rng=random.Random(7))
    from edge.core.models import Sector

    state.sectors = {1: Sector(1, 1, (), "Hub", is_galactic_core=True)}
    trades = PORT_CLASS_TRADES[PortClass.CLASS_1]
    lines = tuple(PortCommodity(c, trades[c], 500, 1000, 11, 5) for c in Commodity)
    state.ports = {1: Port(1, 1, "P", PortClass.CLASS_1, 1, lines)}
    state.ships = {1: Ship(1, "trailblazer", "S", 1, 1, 60)}
    state.players = {1: Player(1, "you", 1, 5_000, turns_remaining=250)}
    state.rebuild_adjacency()
    return state


# --- the patience penalty --------------------------------------------------------

def test_history_penalty_lowers_acceptance_across_rounds() -> None:
    hg = CFG.economy.haggling
    fair, counter = 100, 110  # a modest over-fair counter (player sells into a BUY port)
    probs = [
        haggle_acceptance_probability(
            fair, counter, PortMode.BUY, insult_frac=hg.insult_frac,
            history_penalty=hg.history_penalty, recent_attempts=n)
        for n in range(3)
    ]
    assert probs[0] is not None
    assert probs[0] > probs[1] > probs[2]  # each prior haggle wears the port's patience


def test_insulting_offer_increments_the_attempt_counter() -> None:
    state = _world()
    res = reduce(state, 1, HaggleOffer(Commodity.FUEL_ORE, units=5, counter_price=9_999), CFG)
    apply_result(state, res)
    assert res.events[0].status == "insulting"
    assert state.players[1].haggle_attempts == {1: 1}  # the failed push counts


def test_max_rejections_closes_negotiation_at_fair() -> None:
    state = _world()
    # Two insulting offers exhaust the port's patience (default max_rejections = 2)...
    for _ in range(CFG.economy.haggling.max_rejections):
        apply_result(state, reduce(state, 1, HaggleOffer(Commodity.FUEL_ORE, 5, 9_999), CFG))
    assert state.players[1].haggle_attempts == {1: CFG.economy.haggling.max_rejections}
    # ...so the next offer is refused outright at the fair price, with no further bump.
    res = reduce(state, 1, HaggleOffer(Commodity.FUEL_ORE, 5, 12), CFG)
    apply_result(state, res)
    assert res.events[0].status == "exhausted"
    assert len(res.events) == 1  # no Traded — the port held firm
    assert state.players[1].haggle_attempts == {1: CFG.economy.haggling.max_rejections}


def test_daily_cron_resets_attempts() -> None:
    state = _world()
    state.players[1] = replace(state.players[1], haggle_attempts={1: 2})
    apply_result(state, daily_turn_reset(state, CFG))
    assert state.players[1].haggle_attempts == {}  # patience is fresh at dawn
    assert state.players[1].turns_remaining == CFG.turns_per_day


# --- replay / golden master ------------------------------------------------------

def test_attempt_counter_round_trips_through_reload(tmp_path: Path) -> None:
    svc = GameService.new_game(SMALL, 3, SqliteRepository(tmp_path / "haggle.db"), created_at=_CREATED)  # type: ignore[arg-type]
    dock = next(p for p in svc.state.ports.values() if p.klass is PortClass.STARDOCK)
    start = svc.state.ships[svc.state.players[1].ship_id].sector_id
    path = shortest_path(svc.state.adjacency, start, dock.sector_id)
    assert path is not None
    for hop in path[1:]:
        svc.apply(1, Warp(to_sector=hop))
    svc.apply(1, Dock())
    # The StarDock SELLS (the player buys), so a lowball counter of 1/u is insulting —
    # two of them bump the per-port, per-day attempt counter without any trade.
    for _ in range(2):
        svc.apply(1, HaggleOffer(Commodity.FUEL_ORE, units=1, counter_price=1))
    assert svc.state.players[1].haggle_attempts.get(dock.id) == 2
    expected = state_hash(svc.state)

    reloaded = GameService.load_game(SMALL, SqliteRepository(tmp_path / "haggle.db"))  # type: ignore[arg-type]
    assert state_hash(reloaded.state) == expected
    assert reloaded.state.players[1].haggle_attempts.get(dock.id) == 2
