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
    corp_banks = sum(c.bank_balance for c in state.corporations.values())  # WP66 shared purses
    total = player_cash + bank + purses + treasuries + corp_banks
    return [
        "money supply (latinum):",
        f"  players (cash):   {player_cash:,}",
        f"  players (bank):   {bank:,}",
        f"  port purses:      {purses:,}",
        f"  planet treasuries:{treasuries:,}",
        f"  corp banks:       {corp_banks:,}",
        f"  TOTAL:            {total:,}",
    ]


def money_total(state: UniverseState) -> int:
    """Total latinum across every store — the numeric H10 conservation invariant (WP69).

    Sums player cash + bank, port purses, planet treasuries, and corp banks. Port-to-port
    settlement and player trades are transfers, so this only *moves* between the sources it
    counts; it changes only through the named §8 faucets/sinks (bounties, fees, drips).
    """
    return (
        sum(p.latinum for p in state.players.values())
        + sum(p.bank_balance for p in state.players.values())
        + sum(port.latinum for port in state.ports.values())
        + sum(pl.treasury for pl in state.planets.values())
        + sum(c.bank_balance for c in state.corporations.values())
    )


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


# --- tabular forms (the sysop TUI's DataTables; same facts as the line reports) ----

Rows = tuple[list[str], list[tuple[object, ...]]]  # (column headers, row tuples)


def _spatial(state: UniverseState, sector_id: int) -> int:
    """The player-facing spatial id for a sector (falls back to the internal id)."""
    return state.spatial_ids.get(sector_id, sector_id)


def players_rows(state: UniverseState) -> Rows:
    """`players_report` as sortable columns, widened with ship/record stats."""
    headers = ["id", "name", "sector", "ship", "hull", "holds", "latinum", "bank",
               "turns", "align", "xp", "bloc", "codex", "favors", "bounty"]
    rows: list[tuple[object, ...]] = []
    for pid in sorted(state.players):
        p = state.players[pid]
        ship = state.ships.get(p.ship_id)
        active = sum(1 for c in p.contracts if c.status == "active")
        rows.append((
            pid, p.name,
            _spatial(state, ship.sector_id) if ship else "—",
            ship.type_id if ship else "—",
            f"{ship.hull_current}/{ship.hull_max}" if ship else "—",
            f"{ship.holds_used}/{ship.holds_total}" if ship else "—",
            p.latinum, p.bank_balance, p.turns_remaining, p.alignment, p.experience,
            p.alliance_id if p.alliance_id is not None else "—",
            len(p.codex), active, p.bounty,
        ))
    return headers, rows


def player_detail(state: UniverseState, config: GameConfig, player_id: int) -> list[str]:
    """One player's full sysop dossier (fog bypassed) — the TUI's drill-down view.

    The sysop-side sibling of `devtool.__main__.cmd_show`, as returned lines: identity,
    location/hull, wealth, the alignment/experience record, inventory, holdings, and
    standings — everything the flat table can't fit.
    """
    p = state.players.get(player_id)
    if p is None:
        return [f"no such player {player_id}"]
    ship = state.ships.get(p.ship_id)
    corp = state.corporations.get(p.corp_id) if p.corp_id is not None else None
    bloc = state.alliances.get(p.alliance_id) if p.alliance_id is not None else None
    lines = [f"player #{p.id} {p.name}"
             + (f"  ·  corp {corp.tag} {corp.name}" if corp else "")
             + (f"  ·  bloc #{bloc.id} {bloc.name}" if bloc else "  ·  no bloc")]

    if ship is not None:
        lines += [
            "",
            f"ship: {ship.name} ({ship.type_id}) — sector {_spatial(state, ship.sector_id)} "
            f"(internal {ship.sector_id})",
            f"  hull {ship.hull_current}/{ship.hull_max}  shields {ship.shields}  "
            f"warp {ship.warp_speed}  combat {ship.combat_speed}  "
            f"cloak {ship.cloak_rating}  sensors {ship.sensor_rating}",
            f"  missiles {ship.missiles}  kits {ship.repair_kits}  fighters {ship.fighters}  "
            f"mines {ship.mines}"
            + ("  interdictor ACTIVE" if ship.interdictor_active else ""),
            f"  holds {ship.holds_used}/{ship.holds_total}  "
            f"colonists {ship.colonists:,}/{ship.colonist_capacity:,}",
        ]
        cargo = ", ".join(f"{c.value} x{n}" for c, n in ship.cargo.items() if n)
        parts = ", ".join(f"{comp.value}({tier.name}) x{n}"
                          for (comp, tier), n in ship.components.items())
        devices = ", ".join(f"{d} x{n}" for d, n in ship.devices.items() if n)
        lines += [f"  cargo:   {cargo or '—'}",
                  f"  parts:   {parts or '—'}",
                  f"  devices: {devices or '—'}"]
        if ship.limpets:
            lines.append("  limpets: " + ", ".join(f"{who} x{n}"
                                                   for who, n in ship.limpets.items()))

    artifacts = ", ".join(f"{tier} x{n}" for tier, n in p.artifacts.items() if n)
    lines += [
        "",
        f"wealth: latinum {p.latinum:,}  bank {p.bank_balance:,}  bounty {p.bounty:,}",
        f"turns:  {p.turns_remaining}",
        f"record: alignment {p.alignment}  experience {p.experience}  "
        f"codex {len(p.codex)}  detected {len(p.detected)}  "
        f"explored {len(p.explored_sectors)} sector(s)",
        f"intel:  leads {len(p.leads)}  notes {len(p.notes)}  "
        f"avoid-list {len(p.avoid_sectors)}  flown classes "
        + (", ".join(sorted(p.flown_classes)) or "—"),
        f"artifacts: {artifacts or '—'}",
    ]

    owned = sorted((pl for pl in state.planets.values()
                    if pl.owner.kind == "player" and pl.owner.ref == player_id),
                   key=lambda pl: pl.id)
    lines += ["", f"owned planets ({len(owned)}):"]
    lines += [f"  #{pl.id} {pl.name} — sector {_spatial(state, pl.sector_id)} "
              f"({pl.planet_type}, colonists {pl.colonists:,}, treasury {pl.treasury:,})"
              for pl in owned] or ["  none"]

    if p.alliance_standing:
        standing = ", ".join(f"#{aid} {s:+.1f}" for aid, s in sorted(p.alliance_standing.items()))
        lines += ["", f"alliance standings: {standing}"]
    if p.species_attitudes:
        top = sorted(p.species_attitudes.items(), key=lambda kv: -abs(kv[1]))[:8]
        lines += ["species attitudes: "
                  + ", ".join(f"{rid} {off:+.2f}" for rid, off in top)
                  + (" …" if len(p.species_attitudes) > 8 else "")]
    if p.grudges:
        lines += ["grudges held against them: "
                  + ", ".join(sorted(p.grudges))]
    active = [c for c in p.contracts if c.status == "active"]
    if active:
        lines += ["", f"active favors ({len(active)}):"]
        lines += [f"  contract {c.id}: {c.kind} for {c.issuer} — reward {c.reward_slips}, "
                  f"due d{c.deadline_day}" for c in active]
    return lines


def market_rows(state: UniverseState) -> Rows:
    """`market_report` as sortable columns (the whole book — no fog)."""
    headers = ["port", "side", "qty", "commodity", "limit"]
    rows: list[tuple[object, ...]] = []
    for pid in sorted(state.port_orders):
        port = state.ports.get(pid)
        name = port.name if port is not None else f"port {pid}"
        for o in state.port_orders[pid]:
            rows.append((name, o.side, o.qty, o.commodity.value, o.limit))
    return headers, rows


def standings_rows(state: UniverseState, config: GameConfig) -> Rows:
    """`standings_report` as sortable columns, widened with location and profile.

    `sector` is where that species' ship currently sits (the drift-cron contact point),
    as the player-facing spatial id — the sysop's "where are they all" sweep.
    """
    headers = ["id", "name", "roster", "bloc", "sector", "home band", "tech",
               "threat", "disp", "band", "cash"]
    player = state.players.get(1)
    rows: list[tuple[object, ...]] = []
    for sid in sorted(state.species):
        sp = state.species[sid]
        band = ("—" if player is None
                else disposition_band(effective_disposition(sp, player), config.aliens))
        where = "Stardock" if sp.stardock_staged else _spatial(state, sp.sector_id)
        rows.append((sid, sp.name, sp.roster_id,
                     sp.alliance_id if sp.alliance_id is not None else "—",
                     where, sp.home_band, sp.tech_level, sp.threat_tier,
                     f"{sp.base_disposition:.2f}", band, sp.cash))
    return headers, rows


def species_detail(state: UniverseState, config: GameConfig, species_id: int) -> list[str]:
    """One species instance's full sysop dossier — location, stance, roster profile.

    Merges the per-generation entity (current sector, drawn disposition, trader purse)
    with its static roster parameter set (§6.1) and every player's standing with it.
    """
    sp = state.species.get(species_id)
    if sp is None:
        return [f"no such species {species_id}"]
    bloc = state.alliances.get(sp.alliance_id) if sp.alliance_id is not None else None
    lines = [f"species #{sp.id} {sp.name} ({sp.roster_id})  ·  archetype {sp.archetype_id}"
             + (f"  ·  bloc #{bloc.id} {bloc.name} ({sp.alliance_role})" if bloc else "  ·  no bloc")]

    where = ("staged at the Stardock (the Core's standing welcome)" if sp.stardock_staged
             else f"sector {_spatial(state, sp.sector_id)} (internal {sp.sector_id})")
    lines += [
        "",
        f"ship located: {where}",
        f"home band: {sp.home_band}  ·  tech level {sp.tech_level}",
        f"disposition: base {sp.base_disposition:.2f} "
        f"(drawn from {sp.disposition_center:.2f} ± {sp.disposition_variance:.2f})",
        f"posture: trade {sp.trade_posture}  ·  treaty {sp.treaty_mode}  ·  "
        f"threat tier {sp.threat_tier}  ·  persona {sp.persona}",
    ]

    spec = None
    if config.roster is not None:
        spec = next((s for s in config.roster.species if s.id == sp.roster_id), None)
    if spec is not None:
        mech = spec.signature_mechanic.hook if spec.signature_mechanic else "—"
        lines += [
            "",
            f"roster profile: threat {spec.threat_rating:.2f}  "
            f"interception {spec.interception_rating:.2f}  "
            f"combatant {spec.combatant}  memory {spec.memory_model}  "
            f"betrayal {spec.betrayal_model}",
            f"  movement {spec.movement_policy}  ·  contracts {spec.contract_posture}  ·  "
            f"starbase {spec.starbase_policy}  ·  signature mechanic {mech}",
            f"  fleet: {', '.join(spec.fleet) or '—'}"
            + (f"  ·  escort: {', '.join(spec.pack.escort)}" if spec.pack.escort else ""),
            f"  tech offers: {len(spec.tech_offers)}"
            + (f"  ·  befriend price: {', '.join(spec.befriend_price)}"
               if spec.befriend_price else ""),
        ]
        if spec.description:
            lines.append(f"  {spec.description}")

    if sp.cash or sp.cargo:
        goods = ", ".join(f"{c.value} x{n}" for c, n in sp.cargo.items() if n) or "—"
        lines += ["", f"trader purse: {sp.cash:,} slips  ·  held goods: {goods}"]

    lines += ["", "standing per player:"]
    for pid in sorted(state.players):
        p = state.players[pid]
        att = p.species_attitudes.get(sp.roster_id, 0.0)
        eff = effective_disposition(sp, p)
        band = disposition_band(eff, config.aliens)
        seen = p.species_last_seen.get(sp.roster_id)
        grudge = " · holds a GRUDGE" if sp.roster_id in p.grudges else ""
        last = f" · last seen by them at sector {_spatial(state, seen)}" if seen else ""
        lines.append(f"  #{pid} {p.name}: attitude {att:+.2f} → effective {eff:.2f} "
                     f"({band}){last}{grudge}")
    return lines


def notices_rows(state: UniverseState) -> Rows:
    """`notices_report` as sortable columns (`idx` is the moderation index)."""
    headers = ["idx", "day", "author", "text"]
    rows: list[tuple[object, ...]] = [
        (i, n.day, f"#{n.author_player_id}", n.text) for i, n in enumerate(state.notices)
    ]
    return headers, rows
