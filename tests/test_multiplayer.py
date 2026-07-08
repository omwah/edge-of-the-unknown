"""WP69 — multiplayer QA: bot swarms, determinism, fog, conservation, PvP end-to-end.

The Phase-4 correctness proofs, in the fast in-process suite (the socket swarms are the same
shape around a loop). The headline is the single-writer determinism check: a swarm run *is* a
totally-ordered command log, so `rebuild(seed, log)` reproduces the live `state_hash`. Alongside
it: fog holds on the write side (no event about an unseen sector reaches a player), latinum is
conserved across concurrent trading, and the corp-war → PvP-kill → bounty-claim stack works with
three players in one universe.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from edge.bot import BotSwarm
from edge.bot.runner import BotRunner
from edge.config import load_default_config
from edge.core.enums import Commodity
from edge.core.events import BountyPosted, GovernanceChanged, ShipDestroyed
from edge.core.rules import (
    AttackPlayer, CombatAction, DeclareCorpWar, Dock, FormCorp, JoinGame, Trade, Warp,
)
from edge.core.dev import DevPatch
from edge.devtool.reports import money_total
from edge.engine.cron import resolve_cron
from edge.server import session
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.store.snapshots import rebuild, state_hash

_AT = "2026-07-08T00:00:00Z"


def _cfg() -> object:
    base = load_default_config()
    return base.model_copy(update={"bigbang": base.bigbang.model_copy(
        update={"sector_count": 90, "start_sector": 1})})


def _game(tmp_path: Path, players: int, seed: int = 11) -> GameService:
    """A fresh game with `players` seats, each enrolled through a logged JoinGame (§3)."""
    svc = GameService.new_game(_cfg(), seed, SqliteRepository(tmp_path / "mp.db"), created_at=_AT)  # type: ignore[arg-type]
    for pid in range(2, players + 1):
        svc.apply(pid, JoinGame())
    return svc


def _commodity(label: str) -> Commodity:
    return Commodity(label.lower().replace(" ", "_"))


def _trader(bot: BotRunner) -> None:
    """A self-contained wander-trader: trade when docked, else dock/warp on (per-bot, no globals)."""

    @bot.each_turn
    def turn(b: BotRunner) -> None:
        g = b.game()
        if g.turns < 12:
            b.stop()
            return
        if b.service.encounter_view(b.player_id) is not None:
            b.apply(CombatAction(action="flee"))
            return
        port = b.current_port()
        if port is not None:
            for c in port.commodities:  # sell everything the port buys
                if c.mode == "BUY" and c.player_qty > 0:
                    b.apply(Trade(commodity=_commodity(c.name), units=c.player_qty))
            sell = next((c for c in port.commodities if c.mode == "SELL" and c.price > 0), None)
            if sell is not None:
                units = min(g.ship.holds_total, g.ship.latinum // max(1, sell.price))
                if units > 0:
                    b.apply(Trade(commodity=_commodity(sell.name), units=units))
            if g.sector.warps:
                b.apply(Warp(to_sector=g.sector.warps[0].sector_id))
            return
        if g.sector.ports:
            b.apply(Dock())
            return
        if g.sector.warps:
            b.apply(Warp(to_sector=g.sector.warps[0].sector_id))


# --- determinism (the H14 single-writer proof) -------------------------------


def test_swarm_run_replays_to_identical_hash(tmp_path: Path) -> None:
    svc = _game(tmp_path, players=3)
    swarm = BotSwarm(svc)
    for pid in (1, 2, 3):
        swarm.add(pid, _trader)
    swarm.run(rounds=60)
    live = state_hash(svc.state)
    rebuilt = rebuild(_cfg(), 11, svc._repo.load_commands(), created_at=_AT,  # type: ignore[attr-defined]
                      maintenance=svc._repo.load_maintenance(),  # type: ignore[attr-defined]
                      cron_resolver=resolve_cron)
    assert state_hash(rebuilt) == live


# --- conservation (H10) ------------------------------------------------------


def test_concurrent_trading_conserves_latinum(tmp_path: Path) -> None:
    svc = _game(tmp_path, players=3)
    before = money_total(svc.state)  # no ticker, no combat ⇒ no faucet/sink fires
    swarm = BotSwarm(svc)
    for pid in (1, 2, 3):
        swarm.add(pid, _trader)
    swarm.run(rounds=60)
    assert money_total(svc.state) == before  # every slip only moved between stores


# --- fog on the write side (extends WP65) ------------------------------------


def test_no_event_ever_reaches_a_player_for_an_unseen_sector(tmp_path: Path) -> None:
    svc = _game(tmp_path, players=3)
    swarm = BotSwarm(svc)
    for pid in (1, 2, 3):
        swarm.add(pid, _trader)
    swarm.run(rounds=40)
    state = svc.state
    events = svc._repo.load_events()  # type: ignore[attr-defined]
    for event in events:
        anchor = session._event_sector(event, state)  # the sector the event happened in
        if anchor is None:
            continue  # global/unanchored: fog doesn't apply
        for pid, player in state.players.items():
            if not session.event_visible_to(state, event, pid):
                continue
            ship = state.ships.get(player.ship_id)
            present = ship is not None and ship.sector_id == anchor
            # a visible sector-anchored event must be one the player is at or has charted
            assert present or anchor in player.explored_sectors or _event_owner(event) == pid


def _event_owner(event: object) -> int | None:
    pid = getattr(event, "player_id", None)
    return int(pid) if pid is not None else None


# --- corp war → PvP kill → third-party bounty claim (WP66+WP67 end to end) ----


def _place_together(svc: GameService, pids: list[int]) -> int:
    """Teleport every seat to one shared frontier sector; return that sector id."""
    state = svc.state
    noncore = next(sid for sid, sec in sorted(state.sectors.items()) if not sec.is_galactic_core)
    for pid in pids:
        svc.apply(pid, DevPatch("teleport", "", value=noncore))
    return noncore


def test_corp_war_pvp_kill_and_bounty_claim_across_three_players(tmp_path: Path) -> None:
    svc = _game(tmp_path, players=3)
    state = svc.state
    _place_together(svc, [1, 2, 3])
    # Fund and arm two rival corps; weaken player 2 so the duel resolves quickly.
    for pid in (1, 2):
        svc.apply(pid, DevPatch("set", "latinum", 100_000))
        svc.apply(pid, FormCorp(name=f"Corp{pid}", tag=f"C{pid}"))
    svc.apply(1, DeclareCorpWar(target_corp_id=2))
    s2 = state.ships[state.players[2].ship_id]
    # A priced hull (scout_marauder) so a lawful kill posts a real bounty; hull 1 ends it fast.
    state.ships[s2.id] = replace(s2, hull_current=1, type_id="scout_marauder")

    svc.apply(1, AttackPlayer(target_player_id=2))
    kill_events: list[object] = []
    for _ in range(30):
        if state.players[1].active_encounter is None:
            break
        kill_events.extend(svc.apply(1, CombatAction(action="fight")))
    assert any(isinstance(e, ShipDestroyed) and e.player_id == 2 for e in kill_events)
    assert any(isinstance(e, BountyPosted) for e in kill_events)  # p1 outlawed for a lawful kill
    bounty_on_p1 = state.players[1].bounty
    assert bounty_on_p1 > 0

    # Player 3 hunts the outlaw: pods player 1 and claims the bounty (the WP44 pod-kill hook).
    s1 = state.ships[state.players[1].ship_id]
    state.ships[s1.id] = replace(s1, hull_current=1)
    p3_latinum_before = state.players[3].latinum
    svc.apply(3, AttackPlayer(target_player_id=1))
    for _ in range(30):
        if state.players[3].active_encounter is None:
            break
        svc.apply(3, CombatAction(action="fight"))
    assert state.players[3].latinum >= p3_latinum_before + bounty_on_p1  # collected the bounty
    assert state.players[1].bounty == 0  # reset once podded


# --- a governance flip reaches every spectator (global event) ----------------


def test_governance_flip_reaches_all_players(tmp_path: Path) -> None:
    svc = _game(tmp_path, players=3)
    events = svc.apply(1, DevPatch("flip_governor", "", value=2))  # dev trigger (WP49)
    flip = next(e for e in events if isinstance(e, GovernanceChanged))
    for pid in svc.state.players:
        assert session.event_visible_to(svc.state, flip, pid)  # global ⇒ every seat sees it
