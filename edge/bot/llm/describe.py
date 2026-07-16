"""Render the pilot's fog-of-war projections as a compact text observation (dev-only).

Everything here reads the same `to_public` DTOs the TUI renders — never core state — so
the model sees exactly what the player it drives would see (H16). Sector references are
**display ids** throughout (DESIGN §5.1); `ActionCatalog` maps them back internally.
"""

from __future__ import annotations

from edge.bot.runner import BotRunner
from edge.core import dto


def sidebar(bot: BotRunner) -> str:
    """The human TUI's StatusSidebar, condensed to three lines of plain text.

    Same facts as `edge.tui.widgets.StatusSidebar` (ship, aspects, integrity, armament,
    holds, colonists, latinum) plus the sector/turns header the game screen carries —
    rendered for the pilot console's status strip, refreshed every brain cycle.
    """
    g = bot.game()
    s = g.ship
    sec = g.sector
    cargo = " ".join(f"{h.label} {h.qty}" for h in s.holds if h.qty) or "empty"
    aspects = " · ".join(f"{a.label} {a.note}".strip() for a in s.aspects)
    core = f" · Core: {g.core_status}" if g.governor else ""
    return "\n".join([
        f"S{sec.display_id} {sec.region} ({sec.band or '?'}) · Turns {g.turns}/{g.max_turns}"
        f" · Latinum {s.latinum:,} slips{core}",
        f"{s.name} ({s.klass}) · {aspects}",
        f"Subsystems {s.integrity} · Gun {s.gun} · Missiles x{s.missiles} · Kits x{s.kits}"
        f" · Holds {s.holds_used}/{s.holds_total} ({cargo})"
        f" · Colonists {s.colonists:,}/{s.colonist_capacity:,}",
    ])


def observe(bot: BotRunner) -> str:
    """One observation: status, combat (if live), sector, docked port, computer intel."""
    g = bot.game()
    lines: list[str] = []
    _status(lines, g)

    encounter = bot.service.encounter_view(bot.player_id)
    if encounter is not None:
        _encounter(lines, encounter)
        return "\n".join(lines)  # combat narrows the world: nothing else is actionable

    _sector(lines, g.sector)
    port = bot.current_port()
    if port is not None:
        _docked_port(lines, port)
    _computer(lines, bot.computer())
    return "\n".join(lines)


def _status(lines: list[str], g: dto.GameState) -> None:
    ship = g.ship
    cargo = ", ".join(f"{h.label} {h.qty}" for h in ship.holds if h.qty) or "empty"
    lines.append("== YOUR STATUS ==")
    lines.append(f"Turns left: {g.turns}/{g.max_turns} · Latinum: {ship.latinum:,} slips")
    full = " — FULL, sell before buying more" if ship.holds_used >= ship.holds_total else ""
    lines.append(f"Ship: {ship.name} ({ship.klass}) · integrity {ship.integrity} · "
                 f"holds {ship.holds_used}/{ship.holds_total} ({cargo}){full}")
    lines.append(f"Missiles {ship.missiles} · repair kits {ship.kits} · "
                 f"colonists aboard {ship.colonists}/{ship.colonist_capacity}")
    if g.governor:
        lines.append(f"Core Space governor: {g.governor} · your Core status: {g.core_status}")


def _encounter(lines: list[str], enc: dto.EncounterDTO) -> None:
    lines.append("")
    lines.append(f"== COMBAT — round {enc.round_no} ==")
    lines.append(f"Engaged: {enc.title} · standing {enc.band}")
    for foe in enc.foes:
        state = "alive" if foe.alive else "destroyed"
        lines.append(f"  {foe.name}: hull {foe.hull_pct}% · shields {foe.shields_pct}% · "
                     f"arc {foe.firing_arc} · {state}")
    lines.append(f"You: hull {enc.hull_pct}% · shields {enc.shields_pct}% · {enc.combat_line} · "
                 f"{enc.integrity_flag}")
    gun = "online" if enc.gun_online else "OFFLINE"
    lines.append(f"Flee chance {enc.flee_chance}% (floor {enc.flee_floor}%) · "
                 f"missiles {enc.missiles} · main gun {gun}")
    if enc.arc_hint:
        lines.append(f"Tactical note: {enc.arc_hint}")
    if enc.speech:
        lines.append(f'They broadcast: "{enc.speech}"')
    lines.append("You are IN COMBAT: only fight / flee / launch_missile apply until it ends.")


def _sector(lines: list[str], s: dto.SectorDTO) -> None:
    lines.append("")
    lines.append(f"== SECTOR {s.display_id} — {s.region} ({s.band or 'unknown band'}) ==")
    if s.beacon:
        lines.append(f"Beacon: {s.beacon}")
    warps = []
    for w in s.warps:
        if w.address_hidden:
            warps.append("uncharted ONE-WAY exit (warp sector -1 to take it)")
            continue
        bits = [f"sector {w.display_id}"]
        bits.append(f"{w.label} ({w.band})" if w.explored and w.label else "UNEXPLORED")
        if w.codes:
            bits.append("+".join(w.codes))
        if w.one_way:
            bits.append("one-way")
        if w.hazards:
            bits.append("hazard: " + ", ".join(w.hazards))
        bits.append(f"{w.turn_cost} turn{'s' if w.turn_cost != 1 else ''}")
        warps.append(" · ".join(bits))
    lines.append("Warps out: " + ("  |  ".join(warps) if warps else "none"))
    for p in s.ports:
        dock_tag = " — the STARDOCK (shipyard, hardware, recruits)" if p.is_stardock else ""
        lines.append(f"Port here: {p.name} ({p.klass}){dock_tag} — dock to trade")
    for pl in s.planets:
        extra = ""
        if pl.ore_reserve_max:
            extra = f" · minable ore {pl.ore_reserve}/{pl.ore_reserve_max}"
        lines.append(f"Planet here: planet_id {pl.planet_id} — {pl.name} ({pl.ptype}){extra}")
    for ship in s.ships:
        if ship.contact_id is not None:
            lines.append(f"Alien ship here: species_id {ship.contact_id} — {ship.name} "
                         f"({ship.role}) — you may hail it")
        elif ship.player_id is not None:
            lines.append(f"Another captain's ship here: {ship.name}")
        else:
            lines.append(f"Vessel here: {ship.name} ({ship.role})")
    if s.anomaly is not None:
        reach = (f"hail species_id {s.anomaly.contact_id}" if s.anomaly.contactable
                 else "your sensors cannot resolve it")
        lines.append(f"Anomaly: {s.anomaly.label} — {reach}")
    for d in s.discoveries:
        if d.collected:
            status = "already logged in your codex"
        elif d.salvageable:
            status = f"SALVAGEABLE — salvage discovery_id {d.discovery_id}"
        else:
            status = "not collectable"
        lines.append(f"Discovery here: {d.label} — {status}")
    for sb in s.starbases:
        state = "operational" if sb.operational else "DERELICT (salvageable)"
        lines.append(f"Starbase here: {sb.name} · owner {sb.owner} · {state}")
    if s.force is not None:
        whose = "your" if s.force.yours else f"{s.force.owner}'s"
        lines.append(f"Deployed force here: {whose} {s.force.fighters} fighters ({s.force.mode})")


def _docked_port(lines: list[str], port: dto.PortDTO) -> None:
    lines.append("")
    lines.append(f"== DOCKED AT {port.name} ({port.klass}) ==")
    for c in port.commodities:
        side = "port SELLS to you" if c.mode == "SELL" else "port BUYS from you"
        lines.append(f"  {c.name.lower().replace(' ', '_')}: {side} @ {c.price} slips "
                     f"(stock {c.stock}/{c.capacity} · you carry {c.player_qty})")
    lines.append("Trade here with: trade {commodity, units}.")


def _computer(lines: list[str], comp: dto.ComputerDTO) -> None:
    display = {p.sector_id: p.sector_display for p in comp.ports}
    pairs = [p for p in comp.pairs if p.buy_sector in display and p.sell_sector in display][:3]
    ports = sorted((p for p in comp.ports if p.dist >= 0), key=lambda p: p.dist)[:6]
    if not pairs and not ports:
        return
    lines.append("")
    lines.append("== SHIP'S COMPUTER ==")
    for p in pairs:
        lines.append(f"Trade pair: {p.goods} — buy at sector {display[p.buy_sector]}, "
                     f"sell at sector {display[p.sell_sector]} · ~{p.per_turn} slips/turn")
    if ports:
        lines.append("Known ports: " + "  |  ".join(
            f"sector {p.sector_display} ({p.dist} hops) sells [{p.sells or '-'}] "
            f"buys [{p.buys or '-'}]" for p in ports))
