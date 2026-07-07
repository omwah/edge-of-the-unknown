"""Sysop read-only reports over the raw game state (DESIGN §A.4 — WP59).

Dev tooling (the `devtool`/`tui` exemption tier, never imported by any runtime layer):
these `sysop_view` functions take the **raw** `UniverseState` and bypass fog of war —
the sysop is trusted and sees everything, unlike the fog-enforcing `server.session`
projections. They **never** move into `server/` (that boundary must stay fog-honest);
they live here so the console and its tests share one source of truth.

Each returns a list of plain strings (report lines) so the console prints them and a test
can assert on them. The headline audit is `money_supply` — the H10 conservation check made
a *tool*: total latinum across players, banks, port purses, and treasuries.
"""

from __future__ import annotations

from edge.core.aliens import disposition_band, effective_disposition
from edge.core.config import GameConfig
from edge.core.governance import _operational_core_bases, npc_seizure_ready
from edge.core.models import UniverseState


def players_report(state: UniverseState) -> list[str]:
    """Per-player latinum / bank / turns / alliance / standings (bypassing fog)."""
    lines = [f"players ({len(state.players)}):"]
    for pid in sorted(state.players):
        p = state.players[pid]
        lines.append(
            f"  #{pid} {p.name}: latinum {p.latinum:,}  bank {p.bank_balance:,}  "
            f"turns {p.turns_remaining}  align {p.alignment}  bloc {p.alliance_id}")
        if p.alliance_standing:
            standing = ", ".join(f"{aid}:{s:+.1f}" for aid, s in sorted(p.alliance_standing.items()))
            lines.append(f"      standings: {standing}")
        if p.contracts:
            active = [c for c in p.contracts if c.status == "active"]
            lines.append(f"      active favors: {len(active)}")
    return lines


def money_supply(state: UniverseState) -> list[str]:
    """The economy's total latinum, by source — the H10 conservation audit as a tool (§8)."""
    player_cash = sum(p.latinum for p in state.players.values())
    bank = sum(p.bank_balance for p in state.players.values())
    purses = sum(port.latinum for port in state.ports.values())
    treasuries = sum(pl.treasury for pl in state.planets.values())
    total = player_cash + bank + purses + treasuries
    return [
        "money supply (latinum):",
        f"  players (cash):   {player_cash:,}",
        f"  players (bank):   {bank:,}",
        f"  port purses:      {purses:,}",
        f"  planet treasuries:{treasuries:,}",
        f"  TOTAL:            {total:,}",
    ]


def market_report(state: UniverseState) -> list[str]:
    """Open order books per port (the whole book — no fog)."""
    if not state.port_orders:
        return ["market: no open orders"]
    lines = ["market order book:"]
    for pid in sorted(state.port_orders):
        port = state.ports.get(pid)
        name = port.name if port is not None else f"port {pid}"
        for o in state.port_orders[pid]:
            lines.append(f"  {name}: {o.side} {o.qty} {o.commodity.value} @ {o.limit}")
    return lines


def standings_report(state: UniverseState, config: GameConfig) -> list[str]:
    """Every placed species' kind / alliance / effective disposition toward player 1."""
    player = state.players.get(1)
    lines = [f"species ({len(state.species)}):"]
    for sid in sorted(state.species):
        sp = state.species[sid]
        band = ("—" if player is None
                else disposition_band(effective_disposition(sp, player), config.aliens))
        lines.append(f"  #{sid} {sp.name} ({sp.roster_id}) bloc {sp.alliance_id} — {band}")
    return lines


def governance_report(state: UniverseState, config: GameConfig) -> list[str]:
    """Current Core governor, its grip, and each covets_core bloc's seizure readiness."""
    gov_id = state.game.core_governing_alliance_id
    gov = state.alliances.get(gov_id) if gov_id is not None else None
    lines = [
        f"Core governor: {gov.name if gov else '— (ungoverned)'} (id {gov_id})",
        f"  incumbent operational Core bases: {_operational_core_bases(state, gov_id)}",
    ]
    coveters = [a for a in state.alliances.values() if a.covets_core and a.id != gov_id]
    for a in sorted(coveters, key=lambda a: a.id):
        lines.append(f"  covets_core: #{a.id} {a.name} — seizure-ready "
                     f"{npc_seizure_ready(state, config, a.id)}")
    return lines


def notices_report(state: UniverseState) -> list[str]:
    """The tavern noticeboard (all entries, indexed for moderation)."""
    if not state.notices:
        return ["notices: none"]
    return ["notices:"] + [
        f"  [{i}] d{n.day} by #{n.author_player_id}: {n.text}"
        for i, n in enumerate(state.notices)
    ]
