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
from edge import dialogue
from edge.dialogue.intel import pick_intel_target
from edge.core import dto
from edge.server import mapgraph
from edge.server import terrain as terrain_art
from edge.core.aliens import disposition_band, effective_disposition
from edge.core.config import GameConfig, RosterConfig
from edge.core.discovery import is_detectable
from edge.core.economy import EconomyError, haggle_acceptance_probability, port_unit_price
from edge.core.engine_room import build_subsystems, derive_aspects
from edge.core.movement import RoutePlan, one_way_exits, plan_route, plan_route_legs
from edge.core.enums import (
    PORT_CLASS_TRADES,
    Commodity,
    Component,
    ComponentTier,
    DiscoveryKind,
    PortClass,
    PortMode,
    Subsystem,
)
from edge.core.events import (
    AlienMoved,
    Banked,
    Colonized,
    ColonistsRecruited,
    ColonyGrew,
    ComponentInstalled,
    ComponentPurchased,
    ComponentRemoved,
    Descended,
    DevicePurchased,
    DiscoveryCollected,
    DiscoveryDetected,
    Docked,
    GenesisDeployed,
    SiteExplored,
    Event,
    Haggled,
    LeadAccepted,
    PlanetProduced,
    Repaired,
    ShipPurchased,
    StarbaseSalvaged,
    TurnsReset,
    Traded,
    Warped,
)
from edge.core.models import (
    AlienSpecies,
    Planet,
    Player,
    Port,
    Sector,
    Ship,
    SubsystemState,
    UniverseState,
)
from edge.core.planets import is_colonizable, pretty_planet_type
from edge.core.starbases import is_operational

_LABEL = {Commodity.FUEL_ORE: "Fuel", Commodity.ORGANICS: "Org", Commodity.EQUIPMENT: "Equ"}
_FULL = {Commodity.FUEL_ORE: "Fuel Ore", Commodity.ORGANICS: "Organics", Commodity.EQUIPMENT: "Equipment"}


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


def _ship_dto(state: UniverseState, ship: Ship, player: Player, sector: Sector) -> dto.ShipDTO:
    aspects = [
        dto.Aspect("Shields", _bar10(ship.shields, max(ship.hull_max, 1)), f"{ship.shields}%"),
        dto.Aspect("Warp", min(10, ship.warp_speed), str(ship.warp_speed)),
        dto.Aspect("Combat", min(10, ship.combat_speed), str(ship.combat_speed)),
        dto.Aspect("Cloak", min(10, ship.cloak_rating), "off" if ship.cloak_rating == 0 else str(ship.cloak_rating)),
        dto.Aspect("Sensors", min(10, ship.sensor_rating * 3), f"Tier {ship.sensor_rating}"),
    ]
    holds = [dto.Hold(_LABEL[c], ship.cargo.get(c, 0), ship.holds_total) for c in Commodity]
    return dto.ShipDTO(
        name=ship.name, klass=ship.type_id.title(), aspects=aspects, integrity="all nominal",
        holds_used=ship.holds_used, holds_total=ship.holds_total, holds=holds,
        gun="online", missiles=ship.missiles, kits=ship.repair_kits,
        latinum=player.latinum, band=sector.distance_band,
        colonists=ship.colonists, colonist_capacity=ship.colonist_capacity,
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


def _warp_dto(
    state: UniverseState, player: Player, sector: Sector, target: int, here: int,
    came_from: int | None, core_hops: dict[int, int],
) -> dto.WarpDTO:
    """One outbound warp, with region/band/codes filled only once explored (fog of war)."""
    did = _display(state, target)
    kind = _warp_kind(target, came_from, player.explored_sectors)
    arrow = _gravity_arrow(here, core_hops.get(target, here))
    tgt = state.sectors[target]
    if target in player.explored_sectors:
        return dto.WarpDTO(
            sector_id=target, arrow=arrow, label=state.regions[tgt.region_id].name,
            kind=kind, display_id=did, band=tgt.distance_band,
            codes=_sector_codes(state, target),
        )
    return dto.WarpDTO(sector_id=target, arrow=arrow, kind=kind, display_id=did, band="?")


def _discovery_label(kind: str, rarity: str) -> str:
    if kind == DiscoveryKind.WORMHOLE.value:
        return "Wormhole · one-way warp"  # shown only once scanned (warns of the one-way)
    return f"{kind.replace('_', ' ').capitalize()} · {rarity.capitalize()}"


def _sector_discoveries(state: UniverseState, player: Player, sector_id: int) -> list[dto.SectorDiscovery]:
    """Open-space finds the player can see in `sector_id`: obvious + detected-on-entry (§7).

    A hidden find shows only once it was detected on entry (`player.detected`), so a
    sensor upgrade reveals more only after re-entering. An already-logged find stays
    listed (it's in the codex).
    """
    out: list[dto.SectorDiscovery] = []
    for d in state.discoveries.values():
        if d.planet_id is not None or d.sector_id != sector_id:
            continue  # surface sites are reached by descent (WP6), not listed in space
        collected = d.found_by is not None
        visible = (not d.hidden) or (d.id in player.detected)
        if not (collected or visible):
            continue
        warp_to = None
        if d.kind is DiscoveryKind.WORMHOLE:
            exits = one_way_exits(state.adjacency, sector_id)
            warp_to = exits[0] if exits else None
        out.append(dto.SectorDiscovery(
            discovery_id=d.id, label=_discovery_label(d.kind.value, d.rarity_tier.name),
            kind=d.kind.value, rarity=d.rarity_tier.name,
            salvageable=visible and not collected, collected=collected, warp_to=warp_to,
        ))
    return out


def _species_ship_role(species: AlienSpecies, config: GameConfig) -> str:
    """The art ship role for a species' vessel, from its fleet's lead hull (§6.1).

    Resolves roster `fleet[0]` → that ship class's `role`; falls back to "fighter"
    (the art engine's own ship default) when the species has no fleet / no roster
    entry, so a vessel always paints with *some* role rather than guessing on its name.
    """
    roster = config.roster
    sc = roster.species_by_id(species.roster_id) if roster is not None else None
    if sc is not None and sc.fleet:
        try:
            return config.ship_class(sc.fleet[0]).role
        except KeyError:
            pass
    return "fighter"


def _controlling_archetype(state: UniverseState, sector_id: int) -> str | None:
    """The palette of the species controlling `sector_id`'s region, or None (§4).

    Styles the port sprite the same way in every view (sector scene + trade screens),
    so a port keeps one identity regardless of where it's drawn.
    """
    sector = state.sectors.get(sector_id)
    region = state.regions.get(sector.region_id) if sector is not None else None
    cid = region.controlling_species_id if region is not None else None
    controller = state.species.get(cid) if cid is not None else None
    return controller.archetype_id if controller is not None else None


def _sector_dto(
    state: UniverseState, player: Player, sector: Sector, core_hops: dict[int, int],
    config: GameConfig,
) -> dto.SectorDTO:
    # The sector's controlling species (region controller) styles its port sprite.
    port_archetype = _controlling_archetype(state, sector.id)
    ports = [
        dto.SectorPortDTO(
            port_id=p.id, name=p.name, klass=_port_klass_label(p.klass),
            is_stardock=p.klass is PortClass.STARDOCK, archetype_id=port_archetype,
        )
        for p in state.ports.values() if p.sector_id == sector.id
    ]
    planets = [
        dto.SectorPlanetDTO(planet_id=pl.id, name=pl.name, ptype=pl.planet_type)
        for pl in state.planets.values() if pl.sector_id == sector.id
    ]
    # A staged species shows as a present vessel so the player can see (and hail) it —
    # friendly contacts are visible just like ports/planets (§6, WP9). The vessel carries
    # its own species' palette (`archetype_id`) and `contact_id` is the hail target.
    here_species = [sp for sp in sorted(state.species.values(), key=lambda s: s.id)
                    if sp.sector_id == sector.id]
    ships = [
        dto.SectorShipDTO(
            name=f"{sp.name} vessel", role=_species_ship_role(sp, config),
            archetype_id=sp.archetype_id, contact_id=sp.id,
        )
        for sp in here_species
    ]
    here = core_hops.get(sector.id, 0)
    came_from = player.entered_from.get(sector.id)
    warps = [
        _warp_dto(state, player, sector, target, here, came_from, core_hops)
        for target in sector.warps_out
    ]
    region = state.regions[sector.region_id].name
    return dto.SectorDTO(
        region=region, sector_id=sector.id, flavor=f"{sector.distance_band.lower()} space",
        beacon=sector.beacon_text, band=sector.distance_band,
        ports=ports, planets=planets, ships=ships, warps=warps,
        discoveries=_sector_discoveries(state, player, sector.id),
        display_id=_display(state, sector.id),
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
        sector=_sector_dto(state, player, sector, core_hops, config),
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
        archetype_id=_controlling_archetype(state, port.sector_id),
    )


# Above this acceptance probability a non-insulting counter reads as "likely".
_HAGGLE_LIKELY_P = 0.5


def haggle_quote(
    state: UniverseState, player_id: int, commodity: Commodity, counter_price: int, config: GameConfig
) -> dto.HaggleQuote:
    """An advisory read on `counter_price` for the player's docked port (§8, WP-haggle).

    Mirrors what `_haggle` would compute (the §8 fair price + the port's acceptance
    odds at the player's current attempt count), but commits nothing — a UI guidance
    hint only, so it has no effect on replay (WP13).
    """
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    port = state.port_in_sector(ship.sector_id)
    line = port.line(commodity) if port is not None else None
    if line is None or port is None:
        raise EconomyError(f"this port does not trade {commodity.value}")
    fair = port_unit_price(line, config.economy)
    hg = config.economy.haggling
    attempts = player.haggle_attempts.get(port.id, 0)
    if attempts >= hg.max_rejections:
        label = "exhausted"
    else:
        p = haggle_acceptance_probability(
            fair, counter_price, line.mode, insult_frac=hg.insult_frac,
            history_penalty=hg.history_penalty, recent_attempts=attempts,
        )
        if p is None:
            label = "insulting"
        elif p >= 1.0:
            label = "accepted"
        elif p >= _HAGGLE_LIKELY_P:
            label = "likely"
        else:
            label = "unlikely"
    return dto.HaggleQuote(
        commodity=_FULL[commodity], fair=fair, counter=counter_price,
        mode=line.mode.name, label=label, attempts=attempts, max_attempts=hg.max_rejections,
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


_COMMODITY_PCT = {Commodity.FUEL_ORE: "Fuel", Commodity.ORGANICS: "Org", Commodity.EQUIPMENT: "Equ"}


def _owner_label(state: UniverseState, planet: Planet, player_id: int) -> str:
    owner = planet.owner
    if owner.kind == "none":
        return "unowned"
    if owner.kind == "player":
        return "you" if owner.ref == player_id else f"player {owner.ref}"
    alliance = state.alliances.get(owner.ref) if owner.ref is not None else None
    return alliance.name if alliance is not None else "alliance"


def planet_view(state: UniverseState, player_id: int, planet_id: int, config: GameConfig) -> dto.PlanetDTO:
    """The orbit view of a planet for `player_id` (§4.2): type, owner, colony, stores."""
    planet = state.planets[planet_id]
    ship = state.ships[state.players[player_id].ship_id]
    colonizable = is_colonizable(planet.planet_type, config)
    owned_by_you = planet.owner.kind == "player" and planet.owner.ref == player_id
    genesis = config.genesis
    ship_genesis = ship.devices.get(genesis.device_id, 0) if genesis is not None else 0
    genesis_eligible = (
        genesis is not None and not planet.owner.is_owned
        and planet.planet_type in genesis.eligible_types
    )
    stores = [(_FULL[c], planet.stores.get(c, 0)) for c in Commodity]
    allocation = [(_FULL[c], round(planet.allocation.get(c, 0.0) * 100)) for c in Commodity]
    base = state.starbases.get(planet.starbase_id) if planet.starbase_id is not None else None
    starbase_status: str | None = None
    starbase_derelict = False
    salvage: list[tuple[str, int, str]] = []
    if base is not None:
        operational = is_operational(base)
        starbase_derelict = not operational
        starbase_status = "operational" if operational else "derelict — salvageable"
        base_owned_by_you = base.owner.kind == "player" and base.owner.ref == player_id
        if not operational or base_owned_by_you:  # the cannibalize-allowed condition (§4.2)
            for subsystem, sub in base.subsystems.items():
                for idx, comp in enumerate(sub.slots):
                    if comp is not None:
                        salvage.append((subsystem.value, idx, comp.kind.value))
    return dto.PlanetDTO(
        planet_id=planet.id, name=planet.name, ptype=planet.planet_type,
        owner=_owner_label(state, planet, player_id), colonizable=colonizable,
        claimable=colonizable and not planet.owner.is_owned, owned_by_you=owned_by_you,
        colonists=planet.colonists, habitability_cap=planet.habitability_cap,
        stores=stores, allocation=allocation, ship_colonists=ship.colonists,
        ship_colonist_capacity=ship.colonist_capacity,
        ship_genesis=ship_genesis, genesis_eligible=genesis_eligible,
        starbase=starbase_status, starbase_id=planet.starbase_id,
        starbase_derelict=starbase_derelict, salvage=salvage,
    )


_SITE_NAME = {
    "ruins": "Ruins", "artifact": "Artifact Cache", "ancient_tech": "Ancient Tech",
    "crashed_ship": "Crashed Ship",
}


def _payload_lines(payload: object) -> list[str]:
    """Human-readable detail lines for a revealed site's payload (§7)."""
    from edge.core.enums import PayloadKind
    from edge.core.models import DiscoveryPayload

    assert isinstance(payload, DiscoveryPayload)
    if payload.kind is PayloadKind.COMPONENT and payload.component is not None and payload.tier is not None:
        return [f"component: {payload.component.value} (Tier {payload.tier.name})"]
    if payload.kind is PayloadKind.LATINUM:
        return [f"{payload.latinum:,} latinum"]
    if payload.kind is PayloadKind.ARTIFACT and payload.barter_tier is not None:
        return [f"artifact — barter ≈ Tier {payload.barter_tier}"]
    return [payload.lore or "a fragment of lore"]


def surface_view(state: UniverseState, player_id: int, planet_id: int, config: GameConfig) -> dto.SurfaceDTO:
    """The descended-planet view: terrain + surface sites with explore/log state (§7, WP6)."""
    planet = state.planets[planet_id]
    ship = state.ships[state.players[player_id].ship_id]
    detected = state.players[player_id].detected
    sites_src = sorted(
        (d for d in state.discoveries.values() if d.planet_id == planet_id),
        key=lambda d: d.site_slot,
    )
    sites: list[dto.SurfaceSite] = []
    explorable = False
    for site in sites_src:
        explored = site.id in detected
        collected = site.found_by is not None
        masked = site.hidden and not explored  # an unsurveyed hidden site stays unknown
        if not (explored or collected) and is_detectable(site, ship.sensor_rating, in_nebula=False, config=config):
            explorable = True
        marker = "[?]" if masked else f"[{site.site_slot + 1}]"
        status = "logged" if collected else ("explored" if explored else "unexplored")
        if collected:
            payload = ["[dim]logged to codex[/]"]
        elif explored:
            payload = _payload_lines(site.payload)
        elif masked:
            payload = ["[dim]needs a sensor sweep[/]"]
        else:
            payload = ["[dim]survey to reveal[/]"]
        sites.append(dto.SurfaceSite(
            marker=marker,
            name="(unsurveyed)" if masked else _SITE_NAME.get(site.kind.value, site.kind.value),
            rarity="?" if masked else site.rarity_tier.name.capitalize(),
            status=status, payload=payload, discovery_id=site.id,
            salvageable=explored and not collected,
            kind="" if masked else site.kind.value,  # "" hides the kind (and its art) until surveyed
        ))
    terrain = terrain_art.render_terrain(
        planet.planet_type, sites, seed=state.game.seed, planet_id=planet_id,
    )
    return dto.SurfaceDTO(
        planet=planet.name, descent_fuel="n/a", terrain=terrain, sites=sites,
        planet_id=planet_id, explorable=explorable,
        terrain_blurb=terrain_art.blurb_for(planet.planet_type),
        ptype=planet.planet_type,
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


def map_view(
    state: UniverseState, player_id: int, *,
    route_dest: int | None = None, full_graph: bool = False,
    config: GameConfig | None = None,
) -> dto.LocalMapDTO:
    """The local sector ego-graph centered on the player (§10, §11, Map tab).

    A node-and-edge graph of the surrounding sectors in gravity columns, baked to
    Rich-markup rows by `mapgraph`. Reach is `config.ui.local_map_radius` (falling
    back to the module default when no config is supplied). When `route_dest` is
    given, the plotted course is overlaid (same explored/full-graph gating as
    `route_view` — `full_graph` honours a coordinate lead only from its origin, §6.7).
    """
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    here = state.sectors[ship.sector_id]
    radius = config.ui.local_map_radius if config is not None else mapgraph.LOCAL_RADIUS
    route: list[int] = []
    if route_dest is not None:
        lead = (next((ld for ld in player.leads if ld.sector_id == route_dest), None)
                if full_graph else None)
        at_origin = lead is not None and ship.sector_id == lead.origin_sector
        plan = plan_route(
            state.adjacency, ship.sector_id, route_dest,
            allowed=None if at_origin else set(player.explored_sectors),
            turns_per_warp=ship.turns_per_warp,
        )
        if plan.reachable:
            route = [ship.sector_id, *(h.sector_id for h in plan.hops)]
    rows, legend, nodes = mapgraph.build_local_map(state, player, radius=radius, route=route)
    return dto.LocalMapDTO(
        you_sector=here.id, you_band=here.distance_band, rows=rows, legend=legend,
        you_display=_display(state, here.id), nodes=nodes,
    )


def _codex_entries(state: UniverseState, player: Player) -> list[dto.CodexEntry]:
    """The player's logged discoveries, richest first (§7, §11 Codex tab)."""
    entries: list[tuple[int, dto.CodexEntry]] = []
    for did in player.codex:
        disc = state.discoveries.get(did)
        if disc is None:
            continue
        if disc.planet_id is not None:
            location = (f"Sector {_display(state, disc.sector_id)} · "
                        f"Planet {disc.planet_id} · site {disc.site_slot + 1}")
        else:
            location = f"Sector {_display(state, disc.sector_id)}"
        entries.append((disc.rarity_tier.value, dto.CodexEntry(
            name=f"{disc.kind.value} · {disc.rarity_tier.name}", location=location,
            rarity=disc.rarity_tier.name, detail="; ".join(_payload_lines(disc.payload)),
            sector_id=disc.sector_id,
        )))
    entries.sort(key=lambda t: (-t[0], t[1].name))
    return [e for _, e in entries]


def _offer_summary(sc: object) -> str:
    """A compact last-seen tech-offer summary for the dossier (§6.6)."""
    labels = []
    for o in getattr(sc, "tech_offers", []):
        what = o.component or o.aspect or "?"
        labels.append(f"{what}({o.tier})")
    return ", ".join(labels) if labels else "—"


def _representative_by_kind(state: UniverseState) -> dict[str, AlienSpecies]:
    """A representative placed record per species kind (`roster_id` → lowest-id ship).

    Reputation/dossier are keyed by kind, so views that need a concrete record for a kind
    (name, alliance, base disposition — identical across that kind's ships) pick one here.
    """
    out: dict[str, AlienSpecies] = {}
    for sp in sorted(state.species.values(), key=lambda s: s.id):
        out.setdefault(sp.roster_id, sp)
    return out


def _dossier_entries(state: UniverseState, player: Player, config: GameConfig) -> list[dto.DossierEntry]:
    """Every met species *kind* with standing, last-seen offers, and a voiced self-note (§6.6, §11)."""
    if config.roster is None:
        return []
    roster = config.roster
    # One row per species *kind* met — reputation is keyed by `roster_id`, so many ships of
    # a species collapse to a single dossier entry. Resolve a representative placed record
    # per kind (lowest instance id) for its name / alliance / base disposition.
    representative = _representative_by_kind(state)
    out: list[dto.DossierEntry] = []
    for rid in sorted(player.species_attitudes):
        species = representative.get(rid)
        if species is None:
            continue
        sc = roster.species_by_id(species.roster_id)
        allied = player.alliance_id is not None and player.alliance_id == species.alliance_id
        effective = effective_disposition(species, player)
        alliance = roster.alliance(species.alliance_id) if species.alliance_id is not None else None
        seen = player.species_last_seen.get(rid)
        out.append(dto.DossierEntry(
            species=species.name, alliance=alliance.name if alliance else "unaligned",
            band=disposition_band(effective, config.aliens),
            standing=dialogue.standing_for(effective, allied=allied, aliens=config.aliens),
            disposition_filled=max(0, min(5, round(effective * 5))), effective=round(effective, 3),
            offers=_offer_summary(sc),
            last_seen=str(_display(state, seen)) if seen is not None else "—",
            note=_line(state, roster, species, player, "dossier_self", config),
        ))
    return out


def _port_klass_label(klass: PortClass) -> str:
    """A Ports-tab class label: 'Class 1 (BBS)' / 'StarDock' (§11, WP15)."""
    if klass is PortClass.STARDOCK:
        return "StarDock"
    trades = PORT_CLASS_TRADES[klass]
    mnemonic = "".join("B" if trades[c] is PortMode.BUY else "S" for c in Commodity)
    return f"Class {klass.value} ({mnemonic})"


def _port_directory(state: UniverseState, player_id: int) -> list[dto.PortDirEntry]:
    """Every known port (explored sectors), nearest first — the Ports tab (§11, WP15)."""
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    dist = bfs_distances(state.adjacency, ship.sector_id)
    out: list[dto.PortDirEntry] = []
    for port in state.ports.values():
        if port.sector_id not in player.explored_sectors:
            continue  # fog of war: a port appears only once its sector is explored
        buys = [_LABEL[c] for c in Commodity if (ln := port.line(c)) and ln.mode is PortMode.BUY]
        sells = [_LABEL[c] for c in Commodity if (ln := port.line(c)) and ln.mode is PortMode.SELL]
        out.append(dto.PortDirEntry(
            port_id=port.id, sector_id=port.sector_id,
            sector_display=_display(state, port.sector_id), name=port.name,
            klass=_port_klass_label(port.klass),
            buys=", ".join(buys) or "—", sells=", ".join(sells) or "—",
            dist=dist.get(port.sector_id, -1),
        ))
    out.sort(key=lambda e: (e.dist if e.dist >= 0 else 1 << 30, e.sector_display))
    return out


def _planet_directory(state: UniverseState, player_id: int) -> list[dto.PlanetDirEntry]:
    """Every charted planet (explored sectors), nearest first — the Planets tab (§11, §4.2)."""
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    dist = bfs_distances(state.adjacency, ship.sector_id)
    out: list[dto.PlanetDirEntry] = []
    for planet in state.planets.values():
        if planet.sector_id not in player.explored_sectors:
            continue  # fog of war: a planet appears only once its sector is explored
        species = (
            state.species.get(planet.inhabited_by_species_id)
            if planet.inhabited_by_species_id is not None else None
        )
        stores = "  ".join(f"{_LABEL[c]} {planet.stores.get(c, 0)}" for c in Commodity)
        out.append(dto.PlanetDirEntry(
            planet_id=planet.id, sector_id=planet.sector_id,
            sector_display=_display(state, planet.sector_id), name=planet.name,
            ptype=pretty_planet_type(planet.planet_type), owner=_owner_label(state, planet, player_id),
            colonists=planet.colonists,
            species=species.name if species is not None else "—",
            stores=stores, dist=dist.get(planet.sector_id, -1),
        ))
    out.sort(key=lambda e: (e.dist if e.dist >= 0 else 1 << 30, e.sector_display))
    return out


def computer_view(state: UniverseState, player_id: int, config: GameConfig) -> dto.ComputerDTO:
    """Pair-trade finder + discovery codex + alien dossier + ports/planets directory (§9, §11)."""
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    dist = bfs_distances(state.adjacency, ship.sector_id)
    seen = [p for p in state.ports.values() if p.sector_id in player.explored_sectors]
    pairs: list[dto.TradePair] = []
    for buy_from in seen:
        for sell_to in seen:
            if buy_from.id == sell_to.id:
                continue
            best = _best_pair(state, buy_from, sell_to, ship.holds_total, dist, config)
            if best is not None:
                pairs.append(best)
    pairs.sort(key=lambda tp: tp.per_turn, reverse=True)
    top = pairs[:3]
    return dto.ComputerDTO(
        pairs=top, selected=top[0].pair if top else "—",
        codex=_codex_entries(state, player), dossier=_dossier_entries(state, player, config),
        ports=_port_directory(state, player_id), planets=_planet_directory(state, player_id),
        leads=leads_view(state, player_id, config),
    )


def _hop_label(state: UniverseState, sector_id: int) -> str:
    """A Route-tab hop label: spatial id plus any port/planet markers (§11, WP14)."""
    did = _display(state, sector_id)
    words = []
    for code in _sector_codes(state, sector_id):
        words.append({"S": "StarDock", "P": "port", "@": "planet"}.get(code, code))
    return f"({did}) · {' '.join(words)}" if words else f"({did})"


def _route_dto(state: UniverseState, player: Player, plan: RoutePlan,
               *, origin_hint: int | None = None) -> dto.RouteDTO:
    """Map a pure `RoutePlan` to the read-only, spatial-id Route DTO (§11, WP14).

    `origin_hint` (a spatial id) tailors the unreachable reason for a lead the player can't
    plot from here: the full-graph "tip is the map" route only opens at the lead's origin
    sector (§6.7), so point them back to it.
    """
    hops = [
        dto.RouteHopDTO(
            display_id=_display(state, h.sector_id),
            label=_hop_label(state, h.sector_id),
            one_way=h.one_way,
        )
        for h in plan.hops
    ]
    turns = player.turns_remaining
    affordable = turns >= plan.turn_cost
    if not plan.reachable and origin_hint is not None:
        reason = f"Return to sector {origin_hint} to plot this lead."
    elif not plan.reachable:
        reason = "No charted route — explore a path there first."
    elif plan.src == plan.dst:
        reason = "You are already here."
    elif not affordable:
        reason = f"Out of turns — needs {plan.turn_cost}, you have {turns}."
    else:
        reason = ""
    one_ways = sum(1 for h in hops if h.one_way)
    parts = [f"{len(hops)} hop{'s' if len(hops) != 1 else ''}", f"{plan.turn_cost} turns"]
    if one_ways:
        parts.append(f"{one_ways} one-way")
    return dto.RouteDTO(
        origin_display=_display(state, plan.src),
        dest_display=_display(state, plan.dst),
        hops=hops,
        turn_cost=plan.turn_cost,
        turns_remaining=turns,
        affordable=affordable,
        reachable=plan.reachable,
        reason=reason,
        hazards=[],  # Phase-3 encounter seam (empty in Phase 2)
        summary=" · ".join(parts),
    )


def route_view(
    state: UniverseState, player_id: int, dst_sector: int, config: GameConfig,
    *, full_graph: bool = False
) -> dto.RouteDTO:
    """Plot the fewest-hop route to `dst_sector` (§11, WP14).

    Routes through explored space by default. `full_graph` marks a coordinate-lead plot:
    the tip is the map (§6.7), but only **from the sector it was obtained in** — away from
    that origin the route is still locked to charted space, and if none exists the DTO's
    reason points the player back to the lead's origin sector.
    """
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    lead = (next((ld for ld in player.leads if ld.sector_id == dst_sector), None)
            if full_graph else None)
    at_origin = lead is not None and ship.sector_id == lead.origin_sector
    plan = plan_route(
        state.adjacency, ship.sector_id, dst_sector,
        allowed=None if at_origin else set(player.explored_sectors),
        turns_per_warp=ship.turns_per_warp,
    )
    origin_hint = (_display(state, lead.origin_sector)
                   if lead is not None and not at_origin and not plan.reachable else None)
    return _route_dto(state, player, plan, origin_hint=origin_hint)


def route_legs_view(
    state: UniverseState, player_id: int, waypoints: list[int], config: GameConfig
) -> dto.RouteDTO:
    """Plot a multi-leg route through `waypoints` (the Trade round trip, §11, WP14)."""
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    plan = plan_route_legs(
        state.adjacency, ship.sector_id, waypoints,
        allowed=set(player.explored_sectors), turns_per_warp=ship.turns_per_warp,
    )
    return _route_dto(state, player, plan)


def leads_view(state: UniverseState, player_id: int, config: GameConfig) -> list[dto.LeadDTO]:
    """The player's accepted coordinate tips as plottable rows (§6.7 intel, Computer screen).

    The tip is the map, but only from where it was obtained: at the lead's origin sector the
    route is planned over the **full** graph (unvisited destination and all); away from it the
    route is locked to charted space, so distance/turns/reachable reflect what the player can
    actually plot from here. `origin_coords` lets the screen show "return to S{origin}" when
    the lead can't be plotted now.
    """
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    roster = config.roster
    rows: list[dto.LeadDTO] = []
    for lead in player.leads:
        at_origin = ship.sector_id == lead.origin_sector
        plan = plan_route(state.adjacency, ship.sector_id, lead.sector_id,
                          allowed=None if at_origin else set(player.explored_sectors),
                          turns_per_warp=ship.turns_per_warp)
        source = lead.source_species
        if roster is not None and (sc := roster.species_by_id(lead.source_species)) is not None:
            source = sc.name
        rows.append(dto.LeadDTO(
            summary=lead.summary, source=source,
            coords=state.spatial_ids.get(lead.sector_id, lead.sector_id),
            distance=len(plan.hops) if plan.reachable else -1,
            turn_cost=plan.turn_cost, reachable=plan.reachable,
            sector_id=lead.sector_id,
            at_origin=at_origin,
            origin_coords=state.spatial_ids.get(lead.origin_sector, lead.origin_sector),
        ))
    return rows


def _line(state: UniverseState, roster: object, species: AlienSpecies, player: Player,
          context: str, config: GameConfig, *, salt: str = "",
          extra: Mapping[str, str] | None = None,
          facts: Mapping[str, object] | None = None) -> str:
    """Render a dialogue line **read-only** (the recency ring is not advanced here).

    The projection shows a stable line until a reducer (hail/trade) advances the ring;
    both seed the same deterministic RNG, so they agree and replay reproduces them.
    """
    ring = player.dialogue_recency.get((species.roster_id, context), ())
    rng = dialogue.encounter_rng(state.game.seed, species.roster_id, context + salt, ring)
    text, _ = dialogue.speak(roster, species, player, context,  # type: ignore[arg-type]
                             aliens=config.aliens, rng=rng, extra=extra, facts=facts)
    return text


def _contact_verbs(species: AlienSpecies, sc: object, offers: list[dto.TechOfferDTO],
                   *, subjects_available: bool, has_intel: bool = False,
                   asked_intel: bool = False) -> list[dto.ContactVerbDTO]:
    """Derive the conversation verb menu from species params (§6.7), greying with reasons.

    Rows are tagged Say (dialogue) / Do (mechanical) so the TUI groups and dispatches them
    (WP17): Ask about… / Farewell speak a dialogue context; the rest act. There is no Greet
    verb — the screen opens already greeted; re-greeting only re-rolls the variant and is a
    dev affordance the dialogue play-test harness adds back as "Regreet". Farewell is the single
    exit (it speaks a parting line then closes); Escape is the silent quick-exit, so there is no
    separate Leave verb.
    """
    posture = getattr(sc, "trade_posture", "open")
    treaty_mode = getattr(sc, "treaty_mode", "open")
    combatant = getattr(sc, "combatant", True)
    has_latinum = any(o.mode == "latinum" and o.available for o in offers)
    has_barter = any(o.mode == "barter" and o.available for o in offers)

    # SAY — peaceful dialogue verbs (no mechanical effect; advance the recency ring). No Greet:
    # the screen opens already greeted (re-greeting only re-rolls the variant — a dev affordance
    # the play-test harness adds back as "Regreet").
    verbs = [
        dto.ContactVerbDTO("ask", "Ask about…", subjects_available,
                           "" if subjects_available else "no other species met yet",
                           kind="say", context="dossier_other", needs_subject=True),
        # INTEL — ask where to explore; a friendly speaker may volunteer coordinates (§6.7).
        dto.ContactVerbDTO("intel", "Ask for coordinates", kind="say",
                           context="offer_coordinates"),
    ]
    # LOG COORDINATES — a "do" verb, enabled only once you've *asked* (the offer is on screen)
    # and a tip is actually on offer; you cannot log a route the speaker has not volunteered.
    can_log = asked_intel and has_intel
    log_reason = "" if can_log else (
        "no coordinates on offer" if asked_intel else "ask for coordinates first")
    verbs.append(dto.ContactVerbDTO("accept_lead", "Log coordinates", can_log, log_reason))
    # TRADE — offered in Phase 2 except behind a Phase-3 gate. With stock it opens the buy menu;
    # with an empty shelf (open posture but nothing affordable, or a `refuses` species) the screen
    # speaks the persona's `trade_refuse` beat, so "no trade" is a voiced reply, not a dead button.
    if posture == "alliance_gated":
        verbs.append(dto.ContactVerbDTO("trade", "Trade", False, "requires alliance membership (Phase 3)"))
    elif posture == "circuit_gated":
        verbs.append(dto.ContactVerbDTO("trade", "Trade", False, "needs a reprogram circuit (Phase 3)"))
    else:
        verbs.append(dto.ContactVerbDTO("trade", "Buy tech" if has_latinum else "Trade"))
    # BARTER (artifacts → tech no latinum sale offers).
    verbs.append(dto.ContactVerbDTO("barter", "Barter artifact", has_barter,
                                    "" if has_barter else "they offer no barter"))
    # TREATY — Phase 3.
    treaty_reason = {
        "none": "they sign no treaties", "superfluous": "a treaty would be superfluous",
        "home_planet_only": "treaty requires their homeworld (Phase 3)",
    }.get(treaty_mode, "treaties open in a later phase")
    verbs.append(dto.ContactVerbDTO("treaty", "Treaty", False, treaty_reason))
    # FIGHT — Phase 3; Phase 2 places only friendly species.
    verbs.append(dto.ContactVerbDTO("fight", "Attack", False,
                                    "non-combatant" if not combatant else "they are friendly"))
    # SAY — the single exit: speak a parting line, then break contact. (Escape is the silent
    # quick-exit, so there is no separate "Leave" verb.)
    verbs.append(dto.ContactVerbDTO("farewell", "Farewell", kind="say", context="farewell"))
    return verbs


# The always-present floor (§6.7): top-level verbs the contact screen keeps on offer even on an
# authored branching node, so a player can always ask about other species or take their leave.
# Each is dropped when an authored reply already covers it (see `_contact_floor`).
_FLOOR_KEYS = ("ask", "farewell")


def _contact_floor(verbs: list[dto.ContactVerbDTO], choices: list[dto.ContactChoiceDTO],
                   context: str, roster: RosterConfig) -> list[dto.ContactVerbDTO]:
    """The floor verbs to append after authored `choices` on the configured floor context (§6.7).

    Empty unless the node carries authored `choices` (else the derived menu already shows
    these) and is the configured `floor_context`. A floor verb is
    dropped when an authored reply already provides the same navigation — Ask about… when a
    choice targets `dossier_other`, Farewell when a choice already speaks a `"leave"` action — so the
    grammar's explicit wording wins and the default only fills a gap.
    """
    if not choices or context != roster.floor_context:
        return []
    covered = {
        "ask": any(c.next_context == "dossier_other" for c in choices),
        "farewell": any(c.action == "leave" for c in choices),
    }
    return [v for v in verbs if v.key in roster.floor_keys and not covered.get(v.key, False)]


def _tech_offers(species: AlienSpecies, sc: object, player: Player, ship: Ship,
                 effective: float) -> list[dto.TechOfferDTO]:
    """Annotate each tech offer with its price/barter cost and availability (§6, §8)."""
    out: list[dto.TechOfferDTO] = []
    for i, offer in enumerate(getattr(sc, "tech_offers", [])):
        label = (f"{offer.component} ({offer.tier})" if offer.component
                 else f"{offer.aspect} +{offer.amount}")
        needs_hold = offer.component is not None
        reachable = effective >= offer.min_disposition
        reason = ""
        if offer.mode == "latinum":
            price, barter_cost = offer.price, ""
            available = reachable and player.latinum >= price and (not needs_hold or ship.holds_free >= 1)
            if not reachable:
                reason = f"needs standing ≥ {offer.min_disposition:.2f}"
            elif player.latinum < price:
                reason = "insufficient latinum"
            elif needs_hold and ship.holds_free < 1:
                reason = "no free hold"
        else:  # barter
            price, barter_cost = 0, f"1 Tier-{offer.tier} artifact"
            have = player.artifacts.get(offer.tier, 0) >= 1
            available = reachable and have and (not needs_hold or ship.holds_free >= 1)
            if not reachable:
                reason = f"needs standing ≥ {offer.min_disposition:.2f}"
            elif not have:
                reason = f"need a Tier-{offer.tier} artifact"
            elif needs_hold and ship.holds_free < 1:
                reason = "no free hold"
        out.append(dto.TechOfferDTO(
            index=i, label=label, tier=offer.tier, mode=offer.mode, price=price,
            barter_cost=barter_cost, available=available, reason=reason,
        ))
    return out


def _contact_choices(state: UniverseState, roster: object, species: AlienSpecies,
                     player: Player, context: str, config: GameConfig, *, standing: str,
                     ctx: Mapping[str, str],
                     facts: Mapping[str, object] | None = None) -> list[dto.ContactChoiceDTO]:
    """The authored player replies on the active node (§6.7 branching), or [] for a plain node.

    Resolves the node's line entry **read-only** with the same RNG inputs the reducer uses
    (same `encounter_rng` seed ⇒ same winning entry), then projects each choice whose `when`
    holds — preserving its canonical index so the `Converse` command picks the right reply.
    An empty result tells the TUI to fall back to the derived Say/Do verb menu.
    """
    ring = player.dialogue_recency.get((species.roster_id, context), ())
    rng = dialogue.encounter_rng(state.game.seed, species.roster_id, context, ring)
    entry = dialogue.entry_for(roster, species, player, context,  # type: ignore[arg-type]
                               aliens=config.aliens, rng=rng, facts=facts)
    if entry is None or not entry.choices:
        return []
    out: list[dto.ContactChoiceDTO] = []
    for i, choice in enumerate(entry.choices):
        if not dialogue.when_matches(choice.when, standing=standing, treaty=False, facts=facts):
            continue
        enabled, reason = True, ""
        if choice.action == "attack":  # recognised but Phase-3-gated
            enabled, reason = False, "you cannot attack here (Phase 3)"
        out.append(dto.ContactChoiceDTO(
            index=i, text=dialogue.fill(choice.text, ctx), action=choice.action or "",
            next_context=choice.next_context or "", enabled=enabled, reason=reason))
    return out


def contact_view(state: UniverseState, player_id: int, species_id: int,
                 config: GameConfig, active_context: str = "greeting",
                 active_subject: int | None = None) -> dto.ContactDTO:
    """The alien-contact screen for a species in the player's sector (§6, §6.7, §11).

    Renders the **active context's** line (the greeting by default; a "say" verb sets
    another, WP17), the derived verb menu, the tech-offer list (latinum vs barter, gated
    by effective disposition), and dossier lines about other met species in this species'
    voice. Read-only: dialogue lines are stable until a hail/converse/trade reducer
    advances the recency ring (the reducer speaks from the pre-advance ring and both seed
    the same `encounter_rng`, so what is shown matches what was spoken).
    """
    if config.roster is None:
        raise EconomyError("no species roster configured")
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    species = state.species.get(species_id)
    if species is None:
        raise EconomyError("no such species")
    roster = config.roster
    sc = roster.species_by_id(species.roster_id)

    allied = player.alliance_id is not None and player.alliance_id == species.alliance_id
    effective = effective_disposition(species, player)
    standing = dialogue.standing_for(effective, allied=allied, aliens=config.aliens)
    band = disposition_band(effective, config.aliens)
    alliance = roster.alliance(species.alliance_id) if species.alliance_id is not None else None

    offers = _tech_offers(species, sc, player, ship, effective)
    # "Ask about" other met *kinds* (never the species' own kind). Reputation is keyed by
    # `roster_id`, so each subject is presented via a representative ship instance id — the
    # Converse command still targets a concrete ship.
    representative = _representative_by_kind(state)
    others = [
        rep for rid in sorted(player.species_attitudes)
        if rid != species.roster_id and (rep := representative.get(rid)) is not None
    ]
    dossier = [
        _line(state, roster, species, player, "dossier_other", config,
              salt=f":{rep.roster_id}", extra={"subject": rep.name})
        for rep in others
    ]
    subjects = [(rep.id, rep.name) for rep in others]

    # The line shown is the active context's (default greeting); a "say" verb sets it. For
    # `dossier_other` it narrates the picked subject (or the first met other) — with no salt,
    # so it matches the variant the `Converse` reducer spoke (same `encounter_rng` seed).
    # The intel "map" tip the speaker can offer right now (None unless friendly + knows
    # somewhere unvisited). Computed once: it gates the Log-coordinates verb and, when the
    # offer_coordinates line is shown, binds the same {coords}/{target}/… the reducer will.
    intel = pick_intel_target(state, player, species, aliens=config.aliens)

    # Show the active context if it is a peaceful intent or an authored branch node; combat /
    # sig.* lines stay Phase 3, so anything else falls back to the opener.
    shown = (active_context if (active_context in dialogue._PEACEFUL_CONTEXTS
                                or active_context.startswith(dialogue.BRANCH_PREFIX))
             else "greeting")
    subject_extra: dict[str, str] | None = None
    facts: dict[str, object] | None = None
    if shown == "dossier_other" or shown.startswith("branch.dossier_other."):
        sid = active_subject if active_subject is not None else (subjects[0][0] if subjects else None)
        subj = state.species.get(sid) if sid is not None else None
        if subj is None:
            shown = "greeting"  # nothing to ask about — fall back to the opener
        else:
            subject_extra = {"subject": subj.name}
            facts = {"subject": subj.roster_id}
    elif shown == "offer_coordinates":
        facts = {"has_intel_target": intel is not None}
        if intel is not None:
            subject_extra = intel.bindings()
    speech = _line(state, roster, species, player, shown, config, extra=subject_extra, facts=facts)
    # Authored player replies on the shown node (§6.7 branching); empty ⇒ derived verb menu.
    choice_ctx: dict[str, str] = {
        "player": player.name, "species": species.name,
        "alliance": alliance.name if alliance else "the unaligned",
    }
    if subject_extra:
        choice_ctx.update(subject_extra)
    choices = _contact_choices(state, roster, species, player, shown, config,
                               standing=standing, ctx=choice_ctx, facts=facts)
    verbs = _contact_verbs(species, sc, offers, subjects_available=bool(subjects),
                           has_intel=intel is not None, asked_intel=(shown == "offer_coordinates"))
    return dto.ContactDTO(
        species=species.name, roster_id=species.roster_id, persona=species.persona,
        alliance=alliance.name if alliance else "unaligned",
        standing=standing, band=band, disposition_filled=max(0, min(5, round(effective * 5))),
        base_disposition=round(species.base_disposition, 3),
        attitude=round(player.species_attitudes.get(species.roster_id, 0.0), 3),
        effective=round(effective, 3),
        opener=speech,
        verbs=verbs,
        offers=offers, dossier=dossier, subjects=subjects,
        intel_summary=intel.summary() if intel is not None else "",
        choices=choices, floor_verbs=_contact_floor(verbs, choices, shown, roster),
    )


def format_event(event: Event) -> str:
    """Render one event's body as a log/ticker line — the single shared formatter (§11/§12).

    Returns "" for events that should not surface to the player (e.g. per-commodity stock
    regen), so callers can filter them out. The sector an event happened in is supplied by
    the gutter that `format_log_line` prepends, so bodies never name their own sector.
    """
    if isinstance(event, Warped):
        # The destination sector rides in the log's gutter (format_log_line), so the
        # body no longer repeats it — just the action and its turn cost. A one-way
        # warp gets a heads-up: there's no direct warp back (the way home differs, §9).
        warn = "  [yellow]⚠ one-way warp — no direct way back[/]" if event.one_way else ""
        return f"[cyan]Warp to sector[/]  (-{event.turn_cost} turn){warn}"
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
    if isinstance(event, StarbaseSalvaged):
        return f"[green]Salvaged {event.component} ({event.tier})[/] from a derelict starbase"
    if isinstance(event, DevicePurchased):
        return f"[green]Bought {event.device_id.replace('_', ' ')}[/]  (-{event.cost} slips)"
    if isinstance(event, GenesisDeployed):
        return f"[green]✦ Genesis: world re-formed to {event.new_type.replace('_', ' ')}[/]"
    if isinstance(event, Descended):
        return "[magenta]▼ Descended to the surface.[/]"
    if isinstance(event, SiteExplored):
        return f"[cyan]✦ Site surveyed: {event.kind.replace('_', ' ')} ({event.rarity.lower()})[/]"
    if isinstance(event, DiscoveryDetected):
        return f"[cyan]✦ Sensors: {event.kind.replace('_', ' ')} ({event.rarity.lower()})[/]"
    if isinstance(event, DiscoveryCollected):
        gain = f" — {event.reward}" if event.reward else ""
        return f"[green]✦ Logged {event.kind.replace('_', ' ')} ({event.rarity.lower()}){gain}[/]"
    if isinstance(event, LeadAccepted):
        return f"[cyan]✦ Coordinates logged — a {event.kind.replace('_', ' ')} lead.[/]"
    if isinstance(event, ColonistsRecruited):
        via = "StarDock" if event.source == "stardock" else "emigration"
        cost = f"  (-{event.cost} slips)" if event.cost else ""
        return f"Recruited {event.count} colonists ({via}){cost}"
    if isinstance(event, Colonized):
        return f"[green]Colonized world {event.planet_id}[/] with {event.colonists} colonists"
    if isinstance(event, ColonyGrew):
        return f"Colony {event.planet_id} grew to {event.colonists}"
    if isinstance(event, PlanetProduced):
        return ""  # produced-output ticks are not surfaced per-tick (avoid log flood)
    if isinstance(event, Banked):
        return f"Bank {event.kind}: {event.amount}  (balance {event.balance})"
    if isinstance(event, TurnsReset):
        return f"[green]Turns reset to {event.turns}[/]"
    if isinstance(event, AlienMoved):
        # Only emitted for a move touching the player's sector (WP16), so it's always relevant.
        return "[cyan]✦ An alien vessel warps through the sector.[/]"
    return ""  # StockRegenerated and any unmodelled event: not player-facing


def _event_sector(event: Event, state: UniverseState) -> int | None:
    """The internal sector id where `event` happened, for the log's sector gutter (§11/§12).

    Resolved from whatever anchor the event carries — a sector directly, a port/planet/
    discovery's location, or the acting player's current ship sector. Returns None only
    when no anchor resolves (e.g. a hand-built state missing the referenced entity).
    """
    if isinstance(event, Warped):
        return event.to_sector
    if isinstance(event, Docked):
        return event.sector_id
    if isinstance(event, AlienMoved):
        return event.to_sector
    if isinstance(event, (Traded, Haggled)):
        port = state.ports.get(event.port_id)
        return port.sector_id if port is not None else None
    if isinstance(event, (GenesisDeployed, Descended, SiteExplored, Colonized, ColonyGrew, PlanetProduced)):
        planet = state.planets.get(event.planet_id)
        return planet.sector_id if planet is not None else None
    if isinstance(event, (DiscoveryDetected, DiscoveryCollected)):
        disc = state.discoveries.get(event.discovery_id)
        return disc.sector_id if disc is not None else None
    if isinstance(event, (ComponentPurchased, ShipPurchased, ComponentInstalled, ComponentRemoved,
                          Repaired, DevicePurchased, StarbaseSalvaged, ColonistsRecruited,
                          LeadAccepted, Banked, TurnsReset)):
        player = state.players.get(event.player_id)
        if player is None:
            return None
        ship = state.ships.get(player.ship_id)
        return ship.sector_id if ship is not None else None
    return None


def format_log_line(event: Event, state: UniverseState) -> str:
    """A surfaced event line prefixed with the spatial sector id where it happened (§11/§12).

    The single place the log and the live ticker stamp the leading `S{spatial}` gutter, so
    every player-facing line names its location. Returns "" for non-surfaced events so callers
    keep filtering them out.
    """
    text = format_event(event)
    if not text:
        return ""
    sector = _event_sector(event, state)
    if sector is None:
        return text
    # The » decor separates the sector gutter from the body on every line.
    return f"[grey46]S{_display(state, sector)} »[/] {text}"


def _event_turn_cost(event: Event, config: GameConfig) -> int:
    """Turns an event spent — used to reconstruct the day/turn each log line is stamped with.

    Mirrors the turn costs the reducers charge (§9): warps carry their own cost, docking is
    one turn, and the descent/explore/salvage actions read the discovery config (defaulting
    to 1 like the reducers do). Every other event is free, so it shares the running turn.
    """
    if isinstance(event, Warped):
        return event.turn_cost
    if isinstance(event, Docked):
        return 1
    disc = config.discovery
    if isinstance(event, Descended):
        return disc.descent_turn_cost if disc is not None else 1
    if isinstance(event, SiteExplored):
        return disc.explore_turn_cost if disc is not None else 1
    if isinstance(event, DiscoveryCollected):
        return disc.salvage_turn_cost if disc is not None else 1
    return 0


def messages_view(
    state: UniverseState, events: list[Event], config: GameConfig, player_id: int = 1
) -> dto.MessagesDTO:
    """Project the durable event log into a newest-first message list (§11, §12).

    Each line's `when` carries the game day and the turn-of-day it happened on, rebuilt by
    walking the log: the day rolls over on the player's `TurnsReset` (the daily cron, §9) and
    the turn count accrues each event's turn cost, so a free event shares the turn of the last
    turn-spending action before it.
    """
    day, turn = 1, 0
    entries: list[dto.LogEntry] = []
    for event in events:
        if isinstance(event, TurnsReset) and event.player_id == player_id:
            day, turn = day + 1, 0
        else:
            turn += _event_turn_cost(event, config)
        text = format_log_line(event, state)
        if text:
            entries.append(dto.LogEntry(when=f"D{day} · T{turn}", text=text))
    entries.reverse()  # newest first
    return dto.MessagesDTO(events=entries)


def _best_pair(state: UniverseState, buy_from: Port, sell_to: Port, units: int,
               dist: dict[int, int], config: GameConfig) -> dto.TradePair | None:
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
        pair=(f"{buy_from.name} (S{_display(state, buy_from.sector_id)}) <-> "
              f"{sell_to.name} (S{_display(state, sell_to.sector_id)})"),
        goods=best_goods,
        dist=hops, profit_rt=profit, per_turn=profit // hops,
        buy_sector=buy_from.sector_id, sell_sector=sell_to.sector_id,
    )
