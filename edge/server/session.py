"""Fog-of-war projections: core entities -> public DTOs (DESIGN §3).

The single boundary where internal state becomes a client view. Every projection
takes the authoritative `UniverseState` and the viewing player's id and emits the
`edge.core.dto` shapes the TUI consumes — marking unexplored warps rather than
revealing them, and computing live prices through `core.economy`. The TUI never
sees a core model, only these DTOs.
"""

from __future__ import annotations

from collections.abc import Mapping

from edge.bigbang.topology import bfs_distances
from edge.core import dto
from edge.core.config import GameConfig
from edge.core.economy import port_unit_price
from edge.core.engine_room import build_subsystems, derive_aspects
from edge.core.enums import Commodity, Component, ComponentTier, PortClass, PortMode, Subsystem
from edge.core.events import (
    Banked,
    ComponentInstalled,
    ComponentPurchased,
    ComponentRemoved,
    Docked,
    Event,
    Haggled,
    Repaired,
    ShipPurchased,
    TurnsReset,
    Traded,
    Warped,
)
from edge.core.models import Player, Port, Sector, Ship, SubsystemState, UniverseState

_LABEL = {Commodity.FUEL_ORE: "Fuel", Commodity.ORGANICS: "Org", Commodity.EQUIPMENT: "Equ"}
_FULL = {Commodity.FUEL_ORE: "Fuel Ore", Commodity.ORGANICS: "Organics", Commodity.EQUIPMENT: "Equipment"}
_BAND_ORDER = ("Hub", "Frontier", "Deep", "Void")


def _bar10(value: int, maximum: int) -> int:
    return max(0, min(10, round(value / maximum * 10))) if maximum else 0


def _display(state: UniverseState, sector_id: int) -> int:
    """The spatial display id for a sector (§5.1); falls back to the internal id.

    The fallback keeps hand-built (test) states — which never ran the big bang and
    so have no `spatial_ids` — rendering their internal ids unchanged.
    """
    return state.spatial_ids.get(sector_id, sector_id)


def _sector_codes(state: UniverseState, sector_id: int) -> list[str]:
    """Short content tokens for an explored sector: port (S=StarDock/P) and planet."""
    codes: list[str] = []
    port = state.port_in_sector(sector_id)
    if port is not None:
        codes.append("S" if port.klass is PortClass.STARDOCK else "P")
    if any(pl.sector_id == sector_id for pl in state.planets.values()):
        codes.append("@")
    return codes


def _neighbor(state: UniverseState, player: Player, sector_id: int) -> dto.NeighborDTO:
    """A sidebar quick-reference row — region/band/codes only once explored (fog of war)."""
    sector = state.sectors[sector_id]
    did = _display(state, sector_id)
    if sector_id in player.explored_sectors:
        region = state.regions[sector.region_id].name
        return dto.NeighborDTO(
            sector_id=sector_id, name=f"[{did}] {region}", band=sector.distance_band,
            explored=True, codes=_sector_codes(state, sector_id), display_id=did,
        )
    return dto.NeighborDTO(
        sector_id=sector_id, name=f"[{did}] —", band="?", explored=False, display_id=did
    )


def _ship_dto(state: UniverseState, ship: Ship, player: Player, sector: Sector) -> dto.ShipDTO:
    aspects = [
        dto.Aspect("Shields", _bar10(ship.shields, max(ship.hull_max, 1)), f"{ship.shields}%"),
        dto.Aspect("Warp", min(10, ship.warp_speed), str(ship.warp_speed)),
        dto.Aspect("Combat", min(10, ship.combat_speed), str(ship.combat_speed)),
        dto.Aspect("Cloak", min(10, ship.cloak_rating), "off" if ship.cloak_rating == 0 else str(ship.cloak_rating)),
        dto.Aspect("Sensors", min(10, ship.sensor_rating * 3), f"Tier {ship.sensor_rating}"),
    ]
    holds = [dto.Hold(_LABEL[c], ship.cargo.get(c, 0), ship.holds_total) for c in Commodity]
    neighbors = [_neighbor(state, player, t) for t in sector.warps_out]
    return dto.ShipDTO(
        name=ship.name, klass=ship.type_id.title(), aspects=aspects, integrity="all nominal",
        holds_used=ship.holds_used, holds_total=ship.holds_total, holds=holds,
        gun="online", missiles=ship.missiles, kits=ship.repair_kits,
        latinum=player.latinum, band=sector.distance_band, neighbors=neighbors,
    )


def _gravity_arrow(here: int, there: int) -> str:
    """Direction of a warp relative to the Core: closer / deeper / level (§11)."""
    if there < here:
        return "<<"
    if there > here:
        return ">>"
    return "--"


def _warp_kind(target: int, came_from: int | None, explored: frozenset[int]) -> str:
    """The warp's colour band: the way back you came / visited / still unmapped (WP-C)."""
    if target == came_from:
        return "backtrack"
    return "explored" if target in explored else "unexplored"


def _sector_dto(
    state: UniverseState, player: Player, sector: Sector, core_hops: dict[int, int]
) -> dto.SectorDTO:
    ports = [p.name for p in state.ports.values() if p.sector_id == sector.id]
    planets = [f"{pl.name}  {pl.planet_type}" for pl in state.planets.values() if pl.sector_id == sector.id]
    here = core_hops.get(sector.id, 0)
    came_from = player.entered_from.get(sector.id)
    warps = [
        dto.WarpDTO(
            sector_id=target,
            arrow=_gravity_arrow(here, core_hops.get(target, here)),
            kind=_warp_kind(target, came_from, player.explored_sectors),
            display_id=_display(state, target),
        )
        for target in sector.warps_out
    ]
    region = state.regions[sector.region_id].name
    return dto.SectorDTO(
        region=region, sector_id=sector.id, flavor=f"{sector.distance_band.lower()} space",
        beacon=sector.beacon_text, band=sector.distance_band,
        ports=ports, planets=planets, ships=[], warps=warps, display_id=_display(state, sector.id),
    )


def game_view(state: UniverseState, player_id: int, config: GameConfig) -> dto.GameState:
    """The primary game-screen bundle for `player_id` (§11)."""
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    sector = state.sectors[ship.sector_id]
    core_hops = state.core_hops or bfs_distances(state.adjacency, 1)  # cached at gen (WP-C)
    return dto.GameState(
        turns=player.turns_remaining, max_turns=config.turns_per_day,
        ship=_ship_dto(state, ship, player, sector),
        sector=_sector_dto(state, player, sector, core_hops),
    )


def port_view(state: UniverseState, player_id: int, port_id: int, config: GameConfig) -> dto.PortDTO:
    """The trade view for a port, with live §8 prices and the player's holdings."""
    port = state.ports[port_id]
    ship = state.ships[state.players[player_id].ship_id]
    lines = [
        dto.CommodityLine(
            name=_FULL[line.commodity], mode=line.mode.name, stock=line.stock,
            capacity=line.capacity, price=port_unit_price(line, config.economy),
            base_price=round(line.base), player_qty=ship.cargo.get(line.commodity, 0),
        )
        for line in port.commodities
    ]
    return dto.PortDTO(
        name=port.name, klass=f"Class {port.klass.value}", sector_id=port.sector_id,
        commodities=lines, display_id=_display(state, port.sector_id),
    )


_ENGINE_ORDER = (Subsystem.SPINDRIVE, Subsystem.SCREENS, Subsystem.THRUSTERS, Subsystem.MAIN_GUN)
_SUBSYSTEM_DISPLAY = {
    Subsystem.SPINDRIVE: "SPINDRIVE", Subsystem.SCREENS: "SCREENS",
    Subsystem.THRUSTERS: "THRUSTERS", Subsystem.MAIN_GUN: "MAIN GUN",
}


def _slot_dto(sub: SubsystemState, idx: int) -> dto.Slot:
    comp = sub.slots[idx]
    keystone = idx == sub.keystone_index
    if comp is None:
        return dto.Slot(state="empty", keystone=keystone)
    state = "knocked" if comp.knocked_out else "filled"
    return dto.Slot(state=state, component=comp.kind.value, keystone=keystone)


def engine_room_view(state: UniverseState, player_id: int, config: GameConfig) -> dto.EngineRoomDTO:
    """The player ship's slotted subsystems + derived aspects (§4.1, UI_MOCKUPS §8).

    Reads the live derived values through `derive_aspects` so the panel always
    reflects the installed parts; loose components are listed as the install pool.
    """
    ship = state.ships[state.players[player_id].ship_id]
    aspects = derive_aspects(ship, config)
    derived_label = {
        Subsystem.SPINDRIVE: f"warp {aspects.warp_speed}",
        Subsystem.SCREENS: f"shields {aspects.shields}",
        Subsystem.THRUSTERS: f"combat spd {aspects.combat_speed}",
        Subsystem.MAIN_GUN: f"dmg {aspects.gun_damage} · rate {aspects.gun_rate}",
    }
    panels: list[dto.Subsystem] = []
    subsystems = ship.subsystems or {}
    for kind in _ENGINE_ORDER:
        sub = subsystems.get(kind)
        if sub is None:
            continue
        panels.append(dto.Subsystem(
            name=_SUBSYSTEM_DISPLAY[kind], derived=derived_label[kind],
            slots=[_slot_dto(sub, i) for i in range(len(sub.slots))],
        ))
    on_hand = [
        f"{comp.value} ({tier.name}) x{n}"
        for (comp, tier), n in sorted(ship.components.items(), key=lambda kv: (kv[0][0].value, kv[0][1].value))
        if n > 0
    ]
    return dto.EngineRoomDTO(
        ship=ship.name, efficiency_bonus=f"+{aspects.efficiency_bonus} all",
        subsystems=panels, kits=ship.repair_kits, on_hand=on_hand,
    )


def stardock_view(state: UniverseState, player_id: int, config: GameConfig) -> dto.StarDockDTO:
    """The StarDock hardware + shipyard catalogs for the docked player (§8, §11).

    Hardware prices come from the economy block; the shipyard shows each hull's
    derived stats and its trade-in-adjusted net price against the player's current
    hull, flagging what is affordable and which hull is already flown.
    """
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    econ = config.economy

    hardware: list[dto.HardwareItem] = []
    for cname in config.hardware.components:
        for tname in config.hardware.tiers:
            price = econ.component_price(ComponentTier[tname])
            if price is None:  # tier III isn't stocked for latinum
                continue
            hardware.append(dto.HardwareItem(
                component=Component(cname).value, tier=tname, price=price,
                affordable=player.latinum >= price and ship.holds_free >= 1,
            ))

    trade_in = round(config.ship_class(ship.type_id).price * econ.ship_trade_in_frac)
    shipyard: list[dto.ShipyardItem] = []
    for klass in config.ship_classes:
        a = derive_aspects(Ship(
            id=0, type_id=klass.id, name=klass.name, owner_player_id=None, sector_id=0,
            holds_total=klass.holds_total, shields=klass.shields_max, warp_speed=klass.warp_speed,
            combat_speed=klass.combat_speed, turns_per_warp=klass.turns_per_warp,
            subsystems=build_subsystems(klass),
        ), config)
        net = klass.price - trade_in
        shipyard.append(dto.ShipyardItem(
            class_id=klass.id, name=klass.name, role=klass.role, price=klass.price,
            net_price=net, holds=klass.holds_total, shields=a.shields, warp=a.warp_speed,
            combat=a.combat_speed, affordable=player.latinum >= net, owned=klass.id == ship.type_id,
        ))

    return dto.StarDockDTO(
        sector_display=_display(state, ship.sector_id),
        latinum=player.latinum, hardware=hardware, shipyard=shipyard,
    )


def _ordered_bands(present: set[str]) -> list[str]:
    ranked = [b for b in _BAND_ORDER if b in present]
    return ranked + sorted(present - set(ranked))


def map_view(state: UniverseState, player_id: int) -> dto.MapDTO:
    """A banded overview; per-band sector/port/explored counts (§10)."""
    player = state.players[player_id]
    here = state.sectors[state.ships[player.ship_id].sector_id]
    bands: dict[str, list[Sector]] = {}
    for sector in state.sectors.values():
        bands.setdefault(sector.distance_band, []).append(sector)
    port_sectors = {p.sector_id for p in state.ports.values()}
    out = []
    for name in _ordered_bands(set(bands)):
        secs = bands[name]
        explored = sum(1 for s in secs if s.id in player.explored_sectors)
        ports = sum(1 for s in secs if s.id in port_sectors)
        out.append(dto.MapBand(
            title=f"Band · {name}",
            rows=[f"{len(secs)} sectors", f"{explored} explored", f"{ports} ports"],
        ))
    return dto.MapDTO(
        you_sector=here.id, you_band=here.distance_band, bands=out,
        you_display=_display(state, here.id),
    )


def computer_view(state: UniverseState, player_id: int, config: GameConfig) -> dto.ComputerDTO:
    """Pair-trade finder over the ports the player has discovered (§9, §11)."""
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    dist = bfs_distances(state.adjacency, ship.sector_id)
    seen = [p for p in state.ports.values() if p.sector_id in player.explored_sectors]
    pairs: list[dto.TradePair] = []
    for buy_from in seen:
        for sell_to in seen:
            if buy_from.id == sell_to.id:
                continue
            best = _best_pair(buy_from, sell_to, ship.holds_total, dist, config)
            if best is not None:
                pairs.append(best)
    pairs.sort(key=lambda tp: tp.per_turn, reverse=True)
    top = pairs[:3]
    return dto.ComputerDTO(pairs=top, selected=top[0].pair if top else "—")


def format_event(event: Event, display: Mapping[int, int] | None = None) -> str:
    """Render one event as a log/ticker line — the single shared formatter (§11/§12).

    Returns "" for events that should not surface to the player (e.g. per-commodity
    stock regen), so callers can filter them out. `display` maps internal sector ids
    to spatial display ids (§5.1); absent it, internal ids are shown.
    """
    if isinstance(event, Warped):
        shown = (display or {}).get(event.to_sector, event.to_sector)
        return f"[cyan]» Warp to Sector {shown}[/]  (-{event.turn_cost} turn)"
    if isinstance(event, Docked):
        return "[magenta]⚓ Docked.[/]"
    if isinstance(event, Traded):
        verb = "Bought" if event.mode is PortMode.SELL else "Sold"
        return f"{verb} {event.units} {event.commodity.value} @ {event.unit_price} = {event.total} slips"
    if isinstance(event, Haggled):
        price = "—" if event.price is None else event.price
        return f"Haggle {event.status} @ {price}"
    if isinstance(event, ComponentPurchased):
        return f"[green]Bought {event.component} ({event.tier})[/]  (-{event.cost} slips)"
    if isinstance(event, ShipPurchased):
        credit = f" (trade-in +{event.trade_in})" if event.trade_in else ""
        return f"[green]Acquired {event.ship_class_id}[/]  (-{event.cost} slips){credit}"
    if isinstance(event, ComponentInstalled):
        return f"[green]Installed {event.component} ({event.tier})[/] in {event.subsystem}"
    if isinstance(event, ComponentRemoved):
        return f"Removed {event.component} ({event.tier}) from {event.subsystem}"
    if isinstance(event, Repaired):
        return f"[green]Field-patched {event.subsystem} slot {event.slot_index}[/]"
    if isinstance(event, Banked):
        return f"Bank {event.kind}: {event.amount}  (balance {event.balance})"
    if isinstance(event, TurnsReset):
        return f"[green]Turns reset to {event.turns}[/]"
    return ""  # StockRegenerated and any unmodelled event: not player-facing


def stardock_signpost(state: UniverseState) -> str | None:
    """The opening navigation beacon naming the StarDock's location (WP-B).

    Derived from state (the Class-9 port) rather than persisted, so it survives a
    reload and never duplicates. An intentional reveal of a known landmark (§5).
    """
    dock = next((p for p in state.ports.values() if p.klass is PortClass.STARDOCK), None)
    if dock is None:
        return None
    region = state.regions[state.sectors[dock.sector_id].region_id].name
    return f"Navigation beacon: StarDock lies in Sector {_display(state, dock.sector_id)} — {region}."


def messages_view(state: UniverseState, events: list[Event]) -> dto.MessagesDTO:
    """Project the durable event log into a newest-first message list (§11, §12)."""
    lines = (format_event(e, state.spatial_ids) for e in events)
    entries = [dto.LogEntry(when="", text=text) for text in lines if text]
    entries.reverse()  # newest first
    signpost = stardock_signpost(state)
    if signpost is not None:
        entries.append(dto.LogEntry(when="start", text=f"[yellow]{signpost}[/]"))
    return dto.MessagesDTO(events=entries)


def _best_pair(buy_from: Port, sell_to: Port, units: int, dist: dict[int, int],
               config: GameConfig) -> dto.TradePair | None:
    da, db = dist.get(buy_from.sector_id), dist.get(sell_to.sector_id)
    if da is None or db is None:
        return None
    hops = max(1, da + db)
    best_margin = 0
    best_goods = ""
    for commodity in Commodity:
        a, b = buy_from.line(commodity), sell_to.line(commodity)
        if a is None or b is None or a.mode is not PortMode.SELL or b.mode is not PortMode.BUY:
            continue
        margin = port_unit_price(b, config.economy) - port_unit_price(a, config.economy)
        if margin > best_margin:
            best_margin, best_goods = margin, _LABEL[commodity]
    if best_margin <= 0:
        return None
    profit = best_margin * units
    return dto.TradePair(
        pair=f"{buy_from.name} <-> {sell_to.name}", goods=best_goods,
        dist=hops, profit_rt=profit, per_turn=profit // hops,
    )
