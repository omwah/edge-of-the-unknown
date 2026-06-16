"""Fog-of-war projections: core entities -> public DTOs (DESIGN §3).

The single boundary where internal state becomes a client view. Every projection
takes the authoritative `UniverseState` and the viewing player's id and emits the
`edge.core.dto` shapes the TUI consumes — marking unexplored warps rather than
revealing them, and computing live prices through `core.economy`. The TUI never
sees a core model, only these DTOs.
"""

from __future__ import annotations

from edge.bigbang.topology import bfs_distances
from edge.core import dto
from edge.core.config import GameConfig
from edge.core.economy import port_unit_price
from edge.core.enums import Commodity, PortClass, PortMode
from edge.core.models import Player, Port, Sector, Ship, UniverseState

_LABEL = {Commodity.FUEL_ORE: "Fuel", Commodity.ORGANICS: "Org", Commodity.EQUIPMENT: "Equ"}
_FULL = {Commodity.FUEL_ORE: "Fuel Ore", Commodity.ORGANICS: "Organics", Commodity.EQUIPMENT: "Equipment"}
_BAND_ORDER = ("Hub", "Frontier", "Deep", "Void")


def _bar10(value: int, maximum: int) -> int:
    return max(0, min(10, round(value / maximum * 10))) if maximum else 0


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
    if sector_id in player.explored_sectors:
        region = state.regions[sector.region_id].name
        return dto.NeighborDTO(
            sector_id=sector_id, name=f"[{sector_id}] {region}",
            band=sector.distance_band, explored=True, codes=_sector_codes(state, sector_id),
        )
    return dto.NeighborDTO(sector_id=sector_id, name=f"[{sector_id}] —", band="?", explored=False)


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


def _sector_dto(
    state: UniverseState, player: Player, sector: Sector, core_hops: dict[int, int]
) -> dto.SectorDTO:
    ports = [p.name for p in state.ports.values() if p.sector_id == sector.id]
    planets = [f"{pl.name}  {pl.planet_type}" for pl in state.planets.values() if pl.sector_id == sector.id]
    here = core_hops.get(sector.id, 0)
    warps = [
        dto.WarpDTO(
            sector_id=target,
            arrow=_gravity_arrow(here, core_hops.get(target, here)),
            kind="explored" if target in player.explored_sectors else "unexplored",
        )
        for target in sector.warps_out
    ]
    region = state.regions[sector.region_id].name
    return dto.SectorDTO(
        region=region, sector_id=sector.id, flavor=f"{sector.distance_band.lower()} space",
        beacon=sector.beacon_text, band=sector.distance_band,
        ports=ports, planets=planets, ships=[], warps=warps,
    )


def game_view(state: UniverseState, player_id: int, config: GameConfig) -> dto.GameState:
    """The primary game-screen bundle for `player_id` (§11)."""
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    sector = state.sectors[ship.sector_id]
    core_hops = bfs_distances(state.adjacency, 1)
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
        name=port.name, klass=f"Class {port.klass.value}", sector_id=port.sector_id, commodities=lines
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
    return dto.MapDTO(you_sector=here.id, you_band=here.distance_band, bands=out)


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
