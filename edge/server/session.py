"""Fog-of-war projections: core entities -> public DTOs (DESIGN §3).

The single boundary where internal state becomes a client view. Every projection
takes the authoritative `UniverseState` and the viewing player's id and emits the
`edge.core.dto` shapes the TUI consumes — marking unexplored warps rather than
revealing them, and computing live prices through `core.economy`. The TUI never
sees a core model, only these DTOs.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping

from edge.bigbang.topology import bfs_distances
from edge import dialogue
from edge.dialogue import facts as dialogue_facts
from edge.dialogue.intel import pick_intel_target, pick_rumor
from edge.core import dto
from edge.server import mapgraph
from edge.server import navstrip
from edge.server import terrain as terrain_art
from edge.core import citadels
from edge.core import combat
from edge.core import contracts
from edge.core import encounters
from edge.core import territory
from edge.core.aliens import (
    admission_met,
    admission_tasks_done,
    alliance_standing,
    core_status,
    disposition_band,
    effective_disposition,
    seizure_progress,
)
from edge.core.config import DialogueChoice, GameConfig
from edge.core.discovery import entity_contactable, entity_species, is_detectable
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
    AdmissionAdvanced,
    AlienMoved,
    AlienSpoke,
    AllianceJoined,
    AllianceLeadershipChanged,
    AllianceResigned,
    Banked,
    Colonized,
    ColonistsRecruited,
    ColonyGrew,
    CombatRound,
    ComponentInstalled,
    CitadelBuildStarted,
    CitadelCompleted,
    ContractAccepted,
    ContractCompleted,
    ContractFailed,
    NoticePosted,
    RumorHeard,
    CitadelGunSilenced,
    ComponentKnockedOut,
    ComponentPurchased,
    ComponentRemoved,
    CoreLawNotice,
    Descended,
    InterdictorToggled,
    InvasionRepulsed,
    LimpetsRemoved,
    PlanetBanked,
    PlanetInvaded,
    ProbeReport,
    DevicePurchased,
    DiscoveryCollected,
    DiscoveryDetected,
    Docked,
    EncounterEnded,
    EncounterEvaded,
    EncounterStarted,
    GenesisDeployed,
    GovernanceChanged,
    GrudgeFormed,
    HazardDamage,
    SiteExplored,
    Event,
    Haggled,
    LeadAccepted,
    MarketSettled,
    PortOrderFilled,
    PlanetProduced,
    PlayerAttacked,
    BountyPosted,
    Repaired,
    SalvageCollected,
    ShipDestroyed,
    ShipPurchased,
    StarbaseClaimed,
    StarbaseRazed,
    StarbaseRepaired,
    StarbaseSalvaged,
    TerritoryDeployed,
    TurnsReset,
    Traded,
    Warped,
)
from edge.core.models import (
    AlienSpecies,
    Ownership,
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
    came_from: int | None, core_hops: dict[int, int], bearing: float,
) -> dto.WarpDTO:
    """One outbound warp, with region/band/codes filled only once explored (fog of war)."""
    did = _display(state, target)
    kind = _warp_kind(target, came_from, player.explored_sectors)
    arrow = _gravity_arrow(here, core_hops.get(target, here))
    brg = bearing
    tgt = state.sectors[target]
    if target in player.explored_sectors:
        return dto.WarpDTO(
            sector_id=target, arrow=arrow, label=state.regions[tgt.region_id].name,
            kind=kind, display_id=did, band=tgt.distance_band,
            codes=_sector_codes(state, target), bearing=brg,
        )
    return dto.WarpDTO(sector_id=target, arrow=arrow, kind=kind, display_id=did,
                       band="?", bearing=brg)


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
        if d.kind is DiscoveryKind.ENTITY:
            continue  # the reserved Entity codex row is a marker, shown as an anomaly not a find (§7, WP35)
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


_TRAIL_LEN = 4  # how many prior sectors the nav-rose breadcrumb shows (§11)


def _trail(state: UniverseState, player: Player, here: int) -> list[int]:
    """Recent-route breadcrumb: spatial ids of the last sectors travelled (oldest → newest).

    Walked statelessly back through `player.entered_from` (already recorded per move),
    so it needs no new `Player` field and stays reproducible from `(seed, command log)`.
    Stops at a missing link or a cycle; the current sector is excluded (it's the `@`).
    """
    crumbs: list[int] = []
    seen = {here}
    cur = player.entered_from.get(here)
    while cur is not None and cur not in seen and len(crumbs) < _TRAIL_LEN:
        crumbs.append(_display(state, cur))
        seen.add(cur)
        cur = player.entered_from.get(cur)
    crumbs.reverse()  # oldest → newest
    return crumbs


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
    # its own species' palette (`archetype_id`) and `contact_id` is the hail target. The
    # roaming Entity fields no ship (§7): it is shown as an anomalous presence, not a vessel.
    entity = entity_species(state, config)
    here_species = [sp for sp in sorted(state.species.values(), key=lambda s: s.id)
                    if sp.sector_id == sector.id and (entity is None or sp.id != entity.id)]
    ships = [
        dto.SectorShipDTO(
            name=f"{sp.name} vessel", role=_species_ship_role(sp, config),
            archetype_id=sp.archetype_id, contact_id=sp.id,
        )
        for sp in here_species
    ]
    # Other players' ships (§14, WP70 — the WP67 projection promise): visible whenever
    # co-located, like any vessel; `player_id` is the AttackPlayer target. The corp tag
    # and outlaw marker ride in the name (fog-safe: name/corp/bounty are public identity).
    for pid, other in sorted(state.players.items()):
        if pid == player.id:
            continue
        other_ship = state.ships.get(other.ship_id)
        if other_ship is None or other_ship.sector_id != sector.id:
            continue
        corp = state.corporations.get(other.corp_id) if other.corp_id is not None else None
        label = other.name + (f" [{corp.tag}]" if corp is not None else "")
        if other.bounty > 0:
            label += " ☠"
        ships.append(dto.SectorShipDTO(
            name=label, role=config.ship_class(other_ship.type_id).role,
            player_id=pid,
        ))
    here = core_hops.get(sector.id, 0)
    came_from = player.entered_from.get(sector.id)
    topo_bearings = mapgraph.local_layout_bearings(state, player, sector.id)
    warps = [
        _warp_dto(state, player, sector, target, here, came_from, core_hops, topo_bearings.get(target, 0.0))
        for target in sector.warps_out
    ]
    region = state.regions[sector.region_id].name
    core_bearing = math.pi  # direction home is always West/left in map columns (§11 anchor)
    # The roaming Entity's always-on presence hint, computed live from its *current* sector
    # (§7, WP35, H2) — never `Player.detected`. Opening contact is Legendary-sensor-gated; the
    # fog-safe label never names the being. Absent unless the Entity is here right now.
    anomaly: dto.SectorAnomalyDTO | None = None
    if entity is not None and entity.sector_id == sector.id:
        ship = state.ships[player.ship_id]
        contactable = entity_contactable(state, ship.sensor_rating, sector.id, config)
        anomaly = dto.SectorAnomalyDTO(
            label="an anomalous presence distorts local space",
            contact_id=entity.id, contactable=contactable)
    return dto.SectorDTO(
        region=region, sector_id=sector.id, flavor=f"{sector.distance_band.lower()} space",
        beacon=sector.beacon_text, band=sector.distance_band,
        ports=ports, planets=planets, ships=ships, warps=warps,
        discoveries=_sector_discoveries(state, player, sector.id), anomaly=anomaly,
        display_id=_display(state, sector.id),
        core_bearing=core_bearing, trail=_trail(state, player, sector.id),
    )


def game_view(state: UniverseState, player_id: int, config: GameConfig) -> dto.GameState:
    """The primary game-screen bundle for `player_id` (§11)."""
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    sector = state.sectors[ship.sector_id]
    core_hops = state.core_hops or bfs_distances(state.adjacency, 1)  # cached at gen (WP-C)
    sector_dto = _sector_dto(state, player, sector, core_hops, config)
    gov_id = state.game.core_governing_alliance_id
    gov_alliance = state.alliances.get(gov_id) if gov_id is not None else None
    return dto.GameState(
        turns=player.turns_remaining, max_turns=config.turns_per_day,
        ship=_ship_dto(state, ship, player, sector),
        sector=sector_dto,
        nav=navstrip.build_nav_strip(
            sector_dto, core_anchor_side=config.ui.nav_core_anchor_side),
        governor=gov_alliance.name if gov_alliance is not None else None,
        core_status=core_status(state, player),
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
    base_assaultable = False
    base_claimable = False
    base_claim_cost = config.starbase.claim_cost if config.starbase is not None else 0
    base_empty_slots: list[tuple[str, int, bool]] = []
    if base is not None:
        operational = is_operational(base)
        starbase_derelict = not operational
        starbase_status = "operational" if operational else "derelict — salvageable"
        base_owned_by_you = base.owner.kind == "player" and base.owner.ref == player_id
        base_assaultable = operational and not base_owned_by_you
        base_claimable = operational and not base.owner.is_owned
        if not operational or base_owned_by_you:  # the cannibalize-allowed condition (§4.2)
            for subsystem, sub in base.subsystems.items():
                for idx, comp in enumerate(sub.slots):
                    if comp is not None:
                        salvage.append((subsystem.value, idx, comp.kind.value))
                    else:
                        base_empty_slots.append(
                            (subsystem.value, idx, idx == sub.keystone_index))
            # Keystone slots first: filling the reactor keystone is what flips a
            # derelict operational (§4.2), so repair heads straight for it.
            base_empty_slots.sort(key=lambda t: (not t[2], t[0], t[1]))
    # Citadel affordance (§4.2, WP54): the next-level cost + build progress, owner-only.
    citadel_target = 0
    citadel_pct = 0
    can_build = False
    next_cost: tuple[int, int] | None = None
    if config.citadels is not None and owned_by_you:
        if citadels.building(planet):
            citadel_target = planet.citadel_level + 1
            lc = config.citadels.levels[citadel_target - 1]
            citadel_pct = min(100, round(planet.citadel_progress * 100 / lc.build_colonist_days))
        elif planet.citadel_level < len(config.citadels.levels):
            nxt = config.citadels.levels[planet.citadel_level]  # next level's config
            can_build = True
            next_cost = (nxt.cost_equipment, nxt.cost_latinum)
    # Invasion affordance (§4.2, WP55): a hostile owned world outside the Core, with its
    # base razed, gun silenced, and no siege shield — the ladder the reducer enforces.
    can_invade = False
    invade_blocker = ""
    if (config.citadels is not None and planet.owner.is_owned and not owned_by_you
            and not state.sectors[planet.sector_id].is_galactic_core):
        if any(b.sector_id == planet.sector_id and is_operational(b) for b in state.starbases.values()):
            invade_blocker = "raze the orbital base first"
        elif citadels.has_gun(planet, config):
            invade_blocker = "silence the citadel gun first"
        elif citadels.siege_shielded(planet, config, base_operational=False):
            invade_blocker = "the siege shield holds"
        elif ship.fighters < 1:
            invade_blocker = "no fighters aboard to commit"
        else:
            can_invade = True
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
        citadel_level=planet.citadel_level, treasury=planet.treasury, fighters=planet.fighters,
        citadel_build_target=citadel_target, citadel_build_pct=citadel_pct,
        can_build_citadel=can_build, citadel_next_cost=next_cost,
        fighter_allocation_pct=round(planet.fighter_allocation * 100),
        can_invade=can_invade, invade_blocker=invade_blocker, ship_fighters=ship.fighters,
        base_assaultable=base_assaultable, base_claimable=base_claimable,
        base_claim_cost=base_claim_cost, base_empty_slots=base_empty_slots,
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


def corp_view(state: UniverseState, player_id: int, config: GameConfig) -> dto.CorpDTO | None:
    """The player's corporation for the `T` screen — roster, bank, holdings, wars (§4, WP66).

    Read-only. Returns None when the player is in no corp *and* holds no standing invites; when
    corpless-but-invited it returns a shell DTO carrying only the invite list (so the screen can
    offer accept). Holding counts derive live from ownership, never stored.
    """
    player = state.players.get(player_id)
    if player is None:
        return None
    if player.corp_id is None:
        invites = [f"{c.tag} — {c.name}" for c in sorted(state.corporations.values(), key=lambda c: c.id)
                   if player_id in c.invited_player_ids]
        if not invites:
            return None
        return dto.CorpDTO(corp_id=0, name="", tag="", is_ceo=False, bank_balance=0, invites=invites)
    c = state.corporations[player.corp_id]
    owner = Ownership("corp", c.id)
    members = [
        dto.CorpMemberDTO(
            player_id=pid,
            name=state.players[pid].name if pid in state.players else f"Captain #{pid}",
            is_ceo=(pid == c.ceo_player_id))
        for pid in sorted(c.member_player_ids)
    ]
    war_tags = sorted(
        state.corporations[rid].tag for rid in c.at_war_with if rid in state.corporations)
    return dto.CorpDTO(
        corp_id=c.id, name=c.name, tag=c.tag, is_ceo=(c.ceo_player_id == player_id),
        bank_balance=c.bank_balance, members=members,
        planet_count=sum(1 for p in state.planets.values() if p.owner == owner),
        starbase_count=sum(1 for b in state.starbases.values() if b.owner == owner),
        at_war_with=war_tags,
    )


def tavern_view(state: UniverseState, player_id: int, config: GameConfig) -> dto.TavernDTO:
    """The StarDock tavern panel: rumors, the bounty board, and the noticeboard (§14, WP58).

    Read-only. Rumor availability is computed live against the Core-welcome species' pooled
    knowledge (the same deterministic pick the `BuyRumor` reducer makes, so the panel never
    lies about a buyable tip). The bounty board reads live from hostile-band standings, the
    player's active grudges (who hunts them), their open favors, and the governance situation.
    """
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    port = state.port_in_sector(ship.sector_id)
    at_dock = port is not None and port.klass is PortClass.STARDOCK
    rumor_available = False
    if at_dock and port is not None:
        speakers = [sp for sp in state.species.values() if sp.sector_id == port.sector_id]
        rumor_available = pick_rumor(
            state, player, speakers, aliens=config.aliens,
            entity=entity_species(state, config)) is not None

    bounties: list[str] = []
    if config.roster is not None:
        for rid in sorted(player.species_attitudes):
            sc = config.roster.species_by_id(rid)
            sp = next((s for s in state.species.values() if s.roster_id == rid), None)
            if sc is None or sp is None:
                continue
            if disposition_band(effective_disposition(sp, player), config.aliens) == "hostile":
                bounties.append(f"Bounty on {sp.name}: {config.aliens.bounty_per_kill} slips/kill.")
    for rid, grudge in sorted(player.grudges.items()):
        name = next((s.name for s in state.species.values() if s.roster_id == rid), rid)
        bounties.append(f"The {name} hunt you (grudge {grudge.severity:.2f}).")
    bounties += _governance_intel(state, player)[:1]  # the current-governor line

    notices = [
        dto.NoticeDTO(
            author="You" if n.author_player_id == player_id else f"Captain #{n.author_player_id}",
            day=n.day, text=n.text)
        for n in state.notices
    ]
    return dto.TavernDTO(
        rumor_price=config.tavern.rumor_price, rumor_available=rumor_available,
        bounties=bounties, notices=notices, contracts=_contracts_view(state, player))


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
        if klass.price <= 0:
            continue  # never sold (the escape pod is issued by the wreck, §10)
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

    devices = [
        (device_id, spec.price, player.latinum >= spec.price)
        for device_id, spec in sorted(config.devices.items())
    ]
    return dto.StarDockDTO(
        sector_display=_display(state, ship.sector_id),
        latinum=player.latinum, hardware=hardware, shipyard=shipyard, devices=devices,
        bank_balance=player.bank_balance,
        interest_per_day=config.economy.bank_interest_per_day,
    )


def territory_view(state: UniverseState, player_id: int, config: GameConfig) -> dto.TerritoryDTO:
    """Carried territory stock, devices, and this sector's own force (§10/§14 — WP72).

    Feeds the Deploy/Devices screen: what the ship carries (fighters, mines, probes,
    interdictor, attached limpets), whether deployment is barred (the Core), and the
    player's existing force in the sector — all the entrant's own knowledge.
    """
    from edge.core.services import service_point

    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    sector = state.sectors[ship.sector_id]
    force = state.sector_forces.get(ship.sector_id)
    force_line = ""
    if force is not None and force.owner.kind == "player" and force.owner.ref == player_id:
        bits: list[str] = []
        if force.fighters:
            toll = f", toll {force.toll}" if force.mode == "toll" else ""
            bits.append(f"{force.fighters} fighters ({force.mode}{toll})")
        if force.armid_mines:
            bits.append(f"{force.armid_mines} armid mines")
        if force.limpet_mines:
            bits.append(f"{force.limpet_mines} limpet mines")
        force_line = " · ".join(bits)
    devices = sorted((d, n) for d, n in ship.devices.items() if n > 0)
    return dto.TerritoryDTO(
        sector_display=_display(state, ship.sector_id),
        in_core=sector.is_galactic_core,
        fighters=ship.fighters, mines=ship.mines, devices=devices,
        limpets=sum(ship.limpets.values()),
        interdictor_owned=ship.devices.get("interdictor", 0) > 0,
        interdictor_active=ship.interdictor_active,
        probes=ship.devices.get("probe", 0),
        beacon_text=sector.beacon_text or "",
        force_line=force_line,
        limpet_removal_fee=config.territory.limpet_removal_fee,
        at_service_point=service_point(state, player, ship, config) is not None,
    )


def starbase_services_view(
    state: UniverseState, player_id: int, config: GameConfig
) -> dto.StarbaseServicesDTO | None:
    """Forward-base services for the ship's current sector, or None (§4.2, WP53).

    Resolved through the same `services.service_point` seam the reducers gate on, so the
    catalog the player sees and what the reducer will accept never drift (H4). Only a
    *player-owned* base yields a view here — a StarDock has its own screen.
    """
    from edge.core.services import COMPONENTS, MUNITIONS, service_point

    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    sp = service_point(state, player, ship, config)
    if sp is None or sp.kind != "player_base":
        return None
    econ = config.economy
    stock_tiers = (config.starbase.services.component_stock_tiers
                   if config.starbase is not None else [])
    hardware: list[dto.HardwareItem] = []
    if COMPONENTS in sp.services:
        for cname in config.hardware.components:
            for tname in config.hardware.tiers:
                if tname not in stock_tiers:
                    continue  # this base does not stock this tier (§4.2)
                base_price = econ.component_price(ComponentTier[tname])
                if base_price is None:  # barter-only tier
                    continue
                price = round(base_price * sp.fee_frac)
                hardware.append(dto.HardwareItem(
                    component=Component(cname).value, tier=tname, price=price,
                    affordable=player.latinum >= price and ship.holds_free >= 1,
                ))
    missile_price = round(config.combat.missile_price * sp.fee_frac) if MUNITIONS in sp.services else 0
    return dto.StarbaseServicesDTO(
        sector_display=_display(state, ship.sector_id), latinum=player.latinum,
        bank_balance=player.bank_balance, hardware=hardware,
        services=sorted(sp.services), fee_frac=sp.fee_frac, missile_price=missile_price,
    )


def map_view(
    state: UniverseState, player_id: int, *,
    route_dest: int | None = None, full_graph: bool = False,
    config: GameConfig | None = None, fit_width: int | None = None,
) -> dto.LocalMapDTO:
    """The local sector ego-graph centered on the player (§10, §11, Map tab).

    A node-and-edge graph of the surrounding sectors in gravity columns, baked to
    Rich-markup rows by `mapgraph`. Reach is `config.ui.local_map_radius` (falling
    back to the module default when no config is supplied), unless `fit_width` is
    given — the Map tab's available character width — in which case the reach is grown
    to show as many sectors as fit that width. When `route_dest` is given, the plotted
    course is overlaid (same explored/full-graph gating as `route_view` — `full_graph`
    honours a coordinate lead only from its origin, §6.7).
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
    rows, legend, nodes = mapgraph.build_local_map(
        state, player, radius=radius, route=route, max_width=fit_width)
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
            role=species.alliance_role,  # re-derived live, so an intrigue coup follows (WP51)
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
    """Pair-trade finder + discovery codex + alien dossier + ports/planets directory (§9, §11).

    The pair finder quotes from live §8 prices over *explored* ports only — unchanged by
    the WP47 order book, and it never leaks an unexplored port's stock (the fog contract;
    the Market tab, `market_view`, honours the same explored-sectors gate).
    """
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
        contracts=_contracts_view(state, player),
        seizure=_seizure_status(state, player, config),
        governance_intel=_governance_intel(state, player),
        alliances=_alliance_rows(state, player, config),
    )


def _alliance_rows(state: UniverseState, player: Player,
                   config: GameConfig) -> list[dto.AllianceRowDTO]:
    """Every bloc with the player's standing + admission state (§6.3 — WP72).

    Blocs are world knowledge (the roster is public lore); what is *player*-scoped —
    standing, ledger progress, membership, affordability — comes from the player's own
    state, so the projection leaks nothing another player couldn't know.
    """
    roster = config.roster
    if roster is None:
        return []
    rows: list[dto.AllianceRowDTO] = []
    for al in sorted(state.alliances.values(), key=lambda a: a.id):
        ac = roster.alliance(al.id)
        if ac is None:
            continue
        member = player.alliance_id == al.id
        joinable, blocker = True, ""
        if member:
            joinable, blocker = False, "you are a sworn member"
        elif ac.membership_gate == "petition" and not admission_met(player, ac):
            joinable, blocker = False, "admission price unmet"
        elif player.latinum < ac.admission_fee:
            joinable, blocker = False, "cannot afford the admission fee"
        rows.append(dto.AllianceRowDTO(
            alliance_id=al.id, name=al.name, banner=al.banner,
            standing=round(alliance_standing(player, al.id), 3), member=member,
            governs_core=al.id == state.game.core_governing_alliance_id,
            covets_core=al.covets_core, gate=ac.membership_gate, fee=ac.admission_fee,
            tasks_done=sorted(admission_tasks_done(player, al.id)),
            tasks_needed=list(ac.admission_price),
            joinable=joinable, join_blocker=blocker,
        ))
    return rows


def _contracts_view(state: UniverseState, player: Player) -> list[dto.ContractDTO]:
    """The player's active favors for the Computer's contracts panel (§6.7, WP57)."""
    return [
        dto.ContractDTO(
            contract_id=c.id, kind=c.kind, issuer=c.issuer,
            summary=contracts.target_label(state, c), reward=c.reward_slips,
            deadline_day=c.deadline_day,
            dest_display=(state.spatial_ids.get(c.dest_sector, c.dest_sector)
                          if c.dest_sector is not None else 0),
        )
        for c in contracts.active(player)
    ]


def _governance_intel(state: UniverseState, player: Player) -> list[str]:
    """Standing intel on Core governance for the dossier's alliance section (§6.3, WP52).

    Names the current governor, the player's status in the Core, and every bloc that
    covets it — the same facts a flip re-keys, read live so the dossier tracks the world.
    """
    gov_id = state.game.core_governing_alliance_id
    gov = state.alliances.get(gov_id) if gov_id is not None else None
    lines = [
        f"Core governor: {gov.name if gov else 'none (contested)'}.",
        f"Your standing in the Core: {core_status(state, player)}.",
    ]
    coveters = sorted(
        (a for a in state.alliances.values() if a.covets_core and a.id != gov_id),
        key=lambda a: a.id,
    )
    for a in coveters:
        lines.append(f"The {a.name} covet the Core.")
    return lines


def _seizure_status(
    state: UniverseState, player: Player, config: GameConfig
) -> dto.SeizureStatusDTO | None:
    """The Core-seizure checklist for the bloc the player champions, or None (§6.3, WP50).

    Surfaces only when the player has sworn to a `covets_core` bloc with a `core_seizure`
    ladder. The flags come straight from `aliens.seizure_progress` — the same predicate the
    petition reducer gates on — so the checklist and the reducer never drift (H4).
    """
    if config.roster is None or player.alliance_id is None:
        return None
    ac = config.roster.alliance(player.alliance_id)
    if ac is None or ac.core_seizure is None:
        return None
    prog = seizure_progress(state, player, ac, ac.core_seizure)
    return dto.SeizureStatusDTO(
        alliance_id=ac.id, alliance_name=ac.name,
        tasks_done=sorted(prog.tasks_done & set(prog.tasks_required)),
        tasks_needed=list(prog.tasks_required), tasks_met=prog.tasks_met,
        bases_razed=prog.bases_razed, bases_needed=prog.bases_required, bases_met=prog.bases_met,
        fee=prog.fee, fee_affordable=prog.fee_affordable, consented=prog.consented,
        already_governs=prog.already_governs, ready=prog.ready,
    )


def market_view(
    state: UniverseState, events: list[Event], config: GameConfig, player_id: int = 1
) -> dto.MarketDTO:
    """The order-book market for the Computer's Market tab (§8, WP48).

    Fog-respecting: only ports in the player's explored sectors appear (the same
    contract as the Ports directory), so the projection can never name an unexplored
    port's book. Purses read live (stale-by-design). The last-settlement aggregates
    come from the most recent `MarketSettled` in the durable log.
    """
    if not config.economy.market.enabled:
        return dto.MarketDTO(enabled=False)
    player = state.players[player_id]
    orders: list[dto.MarketOrderDTO] = []
    purses: list[tuple[int, str, int]] = []
    for port in sorted(state.ports.values(), key=lambda p: p.id):
        if port.sector_id not in player.explored_sectors:
            continue  # fog of war: never surface an unexplored port's book
        disp = _display(state, port.sector_id)
        purses.append((disp, port.name, port.latinum))
        for order in state.port_orders.get(port.id, ()):
            side = "buys" if order.side == "buy" else "sells"
            orders.append(dto.MarketOrderDTO(
                sector_display=disp, port_name=port.name, commodity=_LABEL[order.commodity],
                side=side, qty=order.qty, limit=order.limit,
            ))
    orders.sort(key=lambda o: (o.sector_display, o.commodity, o.side))
    purses.sort()
    last = next((e for e in reversed(events) if isinstance(e, MarketSettled)), None)
    if last is None:
        return dto.MarketDTO(enabled=True, orders=orders, purses=purses)
    return dto.MarketDTO(
        enabled=True, orders=orders, purses=purses, last_matches=last.matches,
        last_volume=last.volume, last_slips=last.slips,
        summary=f"{last.matches} matches · {last.volume} units · {last.slips} slips",
    )


def _hop_label(state: UniverseState, sector_id: int) -> str:
    """A Route-tab hop label: spatial id plus any port/planet markers (§11, WP14)."""
    did = _display(state, sector_id)
    words = []
    for code in _sector_codes(state, sector_id):
        words.append({"S": "StarDock", "P": "port", "@": "planet"}.get(code, code))
    return f"({did}) · {' '.join(words)}" if words else f"({did})"


def _route_hazards(state: UniverseState, player: Player, plan: RoutePlan,
                   config: GameConfig) -> list[str]:
    """Hazard warnings for a plotted route (§11, WP75 — the A4 seam finally lit).

    Fog-of-war-safe: reads only what the player already knows — black holes and hostile
    deployed forces in **explored** hop sectors, plus the per-band encounter interrupt
    risk (world knowledge, a config fact). Feeds the Computer's hazard-confirm modal.
    """
    hazards: list[str] = []
    risky_hops = 0
    deepest = ""
    deepest_chance = 0.0
    for hop in plan.hops:
        sid = hop.sector_id
        did = _display(state, sid)
        if sid in player.explored_sectors:
            if territory.sector_has_black_hole(state, sid):
                hazards.append(f"Black hole at ({did}) — gravity toll on entry")
            force = state.sector_forces.get(sid)
            if force is not None and territory.force_hostile_to_player(
                    state, force, player, pvp_enabled=config.pvp.enabled):
                kinds: list[str] = []
                if force.fighters > 0:
                    kinds.append(f"{force.fighters} fighters")
                if force.armid_mines > 0 or force.limpet_mines > 0:
                    kinds.append("mines")
                if kinds:
                    hazards.append(f"Hostile {' + '.join(kinds)} at ({did})")
        chance = config.encounters.interrupt_chance.get(
            state.sectors[sid].distance_band, 0.0)
        if chance > 0.0:
            risky_hops += 1
            if chance > deepest_chance:
                deepest_chance = chance
                deepest = state.sectors[sid].distance_band
    if risky_hops:
        hazards.append(
            f"Encounter risk on {risky_hops} hop{'s' if risky_hops != 1 else ''}"
            f" (deepest band: {deepest})")
    return hazards


def _route_dto(state: UniverseState, player: Player, plan: RoutePlan,
               config: GameConfig, *, origin_hint: int | None = None) -> dto.RouteDTO:
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
        hazards=_route_hazards(state, player, plan, config) if plan.reachable else [],
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
    return _route_dto(state, player, plan, config, origin_hint=origin_hint)


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
    return _route_dto(state, player, plan, config)


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
    entity = entity_species(state, config)  # for live Entity-lead staleness (§7, WP36)
    rows: list[dto.LeadDTO] = []
    for lead in player.leads:
        at_origin = ship.sector_id == lead.origin_sector
        plan = plan_route(state.adjacency, ship.sector_id, lead.sector_id,
                          allowed=None if at_origin else set(player.explored_sectors),
                          turns_per_warp=ship.turns_per_warp)
        source = lead.source_species
        if roster is not None and (sc := roster.species_by_id(lead.source_species)) is not None:
            source = sc.name
        # An Entity lead points at a last-known sector; the Entity roams, so the trail has
        # gone cold if it has since moved on (derived read-only at projection, H3).
        stale = (lead.kind == "entity" and entity is not None
                 and entity.sector_id != lead.sector_id)
        rows.append(dto.LeadDTO(
            summary=lead.summary, source=source,
            coords=state.spatial_ids.get(lead.sector_id, lead.sector_id),
            distance=len(plan.hops) if plan.reachable else -1,
            turn_cost=plan.turn_cost, reachable=plan.reachable,
            sector_id=lead.sector_id,
            at_origin=at_origin,
            origin_coords=state.spatial_ids.get(lead.origin_sector, lead.origin_sector),
            stale=stale,
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
    key = dialogue.instance_key(species)
    ring = player.dialogue_recency.get((key, context), ())
    rng = dialogue.encounter_rng(state.game.seed, key, context + salt, ring)
    text, _ = dialogue.speak(roster, species, player, context,  # type: ignore[arg-type]
                             aliens=config.aliens, rng=rng, extra=extra, facts=facts)
    return text


def _gate_choice(choice: DialogueChoice, *, posture: str, treaty_mode: str,
                 has_barter: bool, has_intel: bool, subjects_available: bool,
                 has_contract: bool = False,
                 attack_block: str | None = None) -> tuple[bool, str]:
    """Gate one authored reply, greying it with a reason (§6.7).

    The mechanical actions and the Phase-3 navigations carry the same availability checks and
    reasons the derived verb menu used to — now hung on the authored `choices` instead. A plain
    conversational transition (no recognised action/target) is always offered.
    """
    if choice.action == "attack":
        # FIGHT — live since WP70. `attack_block` is `encounters.first_strike_block`'s
        # verdict, the same gate the AttackSpecies reducer raises, so menu and rule agree.
        return (True, "") if attack_block is None else (False, attack_block)
    if choice.action == "trade":   # empty shelves are handled by the trade_refuse beat, not a gate.
        if posture == "alliance_gated":
            return False, "requires alliance membership (Phase 3)"
        if posture == "circuit_gated":
            return False, "needs a reprogram circuit (Phase 3)"
        return True, ""
    if choice.action == "barter":
        return (True, "") if has_barter else (False, "they offer no barter")
    if choice.action == "accept_lead":  # LOG COORDINATES — only what the speaker has volunteered.
        return (True, "") if has_intel else (False, "no coordinates on offer")
    if choice.action == "accept_contract":  # TAKE THE JOB — only when one is on offer (WP57).
        return (True, "") if has_contract else (False, "no work on offer")
    if choice.next_context == "dossier_other":  # ASK ABOUT… another met species.
        return (True, "") if subjects_available else (False, "no other species met yet")
    if choice.next_context == "treaty_offer":  # TREATY — Phase 3.
        return False, {
            "none": "they sign no treaties", "superfluous": "a treaty would be superfluous",
            "home_planet_only": "treaty requires their homeworld (Phase 3)",
        }.get(treaty_mode, "treaties open in a later phase")
    return True, ""


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
                     ctx: Mapping[str, str], sc: object, offers: list[dto.TechOfferDTO],
                     has_intel: bool, subjects_available: bool,
                     has_contract: bool = False, attack_block: str | None = None,
                     facts: Mapping[str, object] | None = None) -> list[dto.ContactChoiceDTO]:
    """The authored player replies on the active node — the whole reply menu (§6.7).

    Resolves the node's line entry **read-only** with the same RNG inputs the reducer uses
    (same `encounter_rng` seed ⇒ same winning entry), then projects each choice whose `when`
    holds — preserving its canonical index so the `Converse` command picks the right reply.
    Each reply is gated (`enabled`/`reason`) from the species params + live offers, carrying the
    availability the derived verb menu used to. Empty only on a node with no authored choices
    (e.g. a terminal lore beat the player backs out of); the `generic` persona's `start_context`
    choices are the guaranteed baseline via the fallback chain.
    """
    key = dialogue.instance_key(species)
    ring = player.dialogue_recency.get((key, context), ())
    rng = dialogue.encounter_rng(state.game.seed, key, context, ring)
    source = dialogue.choices_for(roster, species, player, context,  # type: ignore[arg-type]
                                  aliens=config.aliens, rng=rng, facts=facts)
    if not source:
        return []
    posture = getattr(sc, "trade_posture", "open")
    treaty_mode = getattr(sc, "treaty_mode", "open")
    has_barter = any(o.mode == "barter" and o.available for o in offers)
    out: list[dto.ContactChoiceDTO] = []
    for i, choice in enumerate(source):
        if not dialogue.when_matches(choice.when, standing=standing, treaty=False, facts=facts):
            continue
        enabled, reason = _gate_choice(
            choice, posture=posture, treaty_mode=treaty_mode,
            has_barter=has_barter, has_intel=has_intel, subjects_available=subjects_available,
            has_contract=has_contract, attack_block=attack_block)
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
    intel = pick_intel_target(state, player, species, aliens=config.aliens,
                              entity=entity_species(state, config))

    # Show the active context if it is a peaceful intent, an authored branch node, or a
    # signature-mechanic prompt (LIVE since WP33 — rendered read-only from the persisted
    # `sig_stage`, so the reducer's applied verdict and this view agree; combat lines stay
    # on the encounter screen). Anything else falls back to the opener.
    shown = (active_context if (active_context in dialogue._PEACEFUL_CONTEXTS
                                or active_context.startswith(dialogue.BRANCH_PREFIX)
                                or active_context.startswith("sig."))
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
    elif shown in ("contract_offer", "contract_report"):
        # The favor the speaker would offer right now (§6.7, WP57) — the same deterministic
        # pick the accept reducer makes, so the shown line and booked job agree (lockstep).
        offer = contracts.pick_contract(state, species, player, config)
        facts = {"has_contract_offer": offer is not None}
        if offer is not None:
            subject_extra = contracts.offer_bindings(state, offer, config)
    # The live visit's session facts join the node's own (§6.7, WP28) — the same shared
    # merge the Converse reducer makes, so line and menu agree on both sides (lockstep).
    facts = dialogue_facts.contact_facts(state, player, species, roster=roster, extra=facts)
    speech = _line(state, roster, species, player, shown, config, extra=subject_extra, facts=facts)
    # Authored player replies on the shown node (§6.7 branching); empty ⇒ derived verb menu.
    choice_ctx: dict[str, str] = {
        "player": player.name, "species": species.name,
        "alliance": alliance.name if alliance else "the unaligned",
    }
    if subject_extra:
        choice_ctx.update(subject_extra)
    choices = _contact_choices(state, roster, species, player, shown, config,
                               standing=standing, ctx=choice_ctx, facts=facts, sc=sc,
                               offers=offers, has_intel=intel is not None,
                               subjects_available=bool(subjects),
                               has_contract=contracts.pick_contract(
                                   state, species, player, config) is not None,
                               attack_block=(
                                   encounters.first_strike_block(state, ship, species, sc, config)
                                   if sc is not None else "unknown species"))
    # A seeded-random portrait variant so different individuals of the same species show
    # different faces, deterministically keyed to the game seed + species instance id.
    # Uses the same string-seed `random.Random` pattern as `encounter_rng` (stable across
    # processes, replay-exact). The value is an arbitrary int that `resolve_portrait` mods
    # by the candidate count.
    portrait_variant = random.Random(
        f"{state.game.seed}|portrait|{species_id}"
    ).randint(0, 2**31)
    return dto.ContactDTO(
        species=species.name, roster_id=species.roster_id, persona=species.persona,
        alliance=alliance.name if alliance else "unaligned",
        standing=standing, band=band, disposition_filled=max(0, min(5, round(effective * 5))),
        base_disposition=round(species.base_disposition, 3),
        attitude=round(player.species_attitudes.get(species.roster_id, 0.0), 3),
        effective=round(effective, 3),
        opener=speech,
        offers=offers, dossier=dossier, subjects=subjects,
        intel_summary=intel.summary() if intel is not None else "",
        choices=choices,
        portrait_variant=portrait_variant,
        singular_entity=bool(sc is not None and sc.singular_entity),
        alliance_id=species.alliance_id,
        alliance_member=(species.alliance_id is not None
                         and player.alliance_id == species.alliance_id),
    )


_ARC_HINTS = {
    "spinal": "arc: spinal — strafe past its firing line (it recharges between volleys)",
    "ahead": "arc: ahead — maneuver out of the firing line (combat-speed contest)",
    "all_round": "arc: all-round — no safe angle; missiles or firepower settle this",
}

# Log-line bodies for the spoken combat beats (§6.7, WP31). The voiced corpus line
# itself renders on the encounter screen (`EncounterDTO.speech`); the log records
# that the beat happened without duplicating rotating dialogue text into the ticker.
_COMBAT_BEAT_LINES = {
    "combat_open": "[red]⚔ They open fire with a challenge on the wideband.[/]",
    "betrayal": "[red]⚔ A supposed friend turns weapons on you.[/]",
    "combat_taunt": "[red]⚔ The pack taunts you over the wideband.[/]",
    "surrender": "[yellow]⚑ Bloodied, they signal for quarter.[/]",
    "flee_scorn": "[yellow]⚑ Jeers chase your retreating engines.[/]",
}


def encounter_view(state: UniverseState, player_id: int, config: GameConfig) -> dto.EncounterDTO | None:
    """The live hostile encounter (§10, WP24/25), or None when the player is not engaged.

    View/reducer lockstep (H4): the flee chance shown is computed by the very
    `combat.flee_chance` the `CombatAction` reducer rolls, from the same inputs, so the
    number on screen is the number the dice see.
    """
    player = state.players[player_id]
    enc = player.active_encounter
    if enc is None:
        return None
    ship = state.ships[player.ship_id]
    species = state.species.get(enc.species_id)
    name = species.name if species is not None else "Unknown"
    archetype = species.archetype_id if species is not None else ""
    interception = 0.0
    if species is not None and config.roster is not None:
        roster_species = config.roster.species_by_id(species.roster_id)
        if roster_species is not None:
            interception = roster_species.interception_rating
    effective = effective_disposition(species, player) if species is not None else 0.0
    band = disposition_band(effective, config.aliens)

    aspects = derive_aspects(ship, config)
    missing = 1.0 - (ship.hull_current / ship.hull_max if ship.hull_max else 1.0)
    flee = combat.flee_chance(
        aspects.combat_speed, aspects.efficiency_bonus, interception, ship.cloak_rating,
        missing, config.combat, config.aliens.escape_floor,
    )

    foes = [
        dto.EncounterFoeDTO(
            name=f.name,
            hull_filled=_bar10(max(0, f.hull), f.hull_max),
            hull_pct=round(100 * max(0, f.hull) / f.hull_max) if f.hull_max else 0,
            shields_pct=round(100 * f.shields / max(1, f.shields)) if f.shields else 0,
            firing_arc=f.firing_arc,
            alive=f.hull > 0,
        )
        for f in enc.foes
    ]
    lead_arc = next((f.firing_arc for f in enc.foes if f.hull > 0), "all_round")
    alive = sum(1 for f in enc.foes if f.hull > 0)
    title = f"{name} pack (x{alive})" if alive > 1 else name

    knocked = [
        f"{sub.value}: {sum(1 for c in st.slots if c is not None and c.knocked_out)} out"
        for sub, st in (ship.subsystems or {}).items()
        if any(c is not None and c.knocked_out for c in st.slots)
    ]
    shields_pct = round(100 * enc.player_shields / max(1, ship.shields)) if ship.shields else 0
    # The pack's combat beat (§6.7, WP31), rendered read-only in the species' voice
    # under the same encounter facts the reducer spoke it with (shared assembly).
    speech = ""
    if enc.speech_context is not None and species is not None and config.roster is not None:
        beat_facts = dialogue_facts.contact_facts(
            state, player, species, roster=config.roster,
            extra=dialogue_facts.encounter_facts(enc))
        speech = _line(state, config.roster, species, player, enc.speech_context, config,
                       facts=beat_facts)
    return dto.EncounterDTO(
        species_id=enc.species_id,
        title=title,
        species_name=name,
        archetype_id=archetype,
        band=band,
        disposition_filled=round(effective * 5),
        round_no=enc.round + 1,
        foes=foes,
        arc_hint=_ARC_HINTS.get(lead_arc, ""),
        shields_pct=min(100, shields_pct),
        hull_pct=round(100 * ship.hull_current / max(1, ship.hull_max)),
        combat_line=(
            f"Combat spd {aspects.combat_speed}"
            + (f" (+{aspects.efficiency_bonus} eff)" if aspects.efficiency_bonus else "")
            + f"   vs intercept {interception:.1f}"
        ),
        integrity_flag="; ".join(knocked) if knocked else "all nominal",
        flee_chance=round(flee * 100),
        flee_floor=round(config.aliens.escape_floor * 100),
        missiles=ship.missiles,
        repair_kits=ship.repair_kits,
        gun_online=aspects.gun_damage > 0,
        speech=speech,
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
        line = f"{verb} {event.units} {event.commodity.value} @ {event.unit_price} = {event.total} slips"
        if event.requested and event.requested > event.units:
            # A hard port purse capped the fill (WP47) — say so, like TW's short quote.
            line += f"  [yellow](the port could only afford {event.units} of {event.requested})[/]"
        return line
    if isinstance(event, MarketSettled):
        return (f"[grey46]⇄ Markets settled: {event.matches} matches · "
                f"{event.volume} units · {event.slips} slips moved.[/]")
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
    if isinstance(event, EncounterStarted):
        if event.hostile:
            return f"[red]⚔ INTERCEPTED — a hostile pack (x{event.pack_size}) opens fire![/]"
        return "[yellow]⚠ Intercepted — they hail you.[/]"
    if isinstance(event, EncounterEvaded):
        return "[cyan]✦ Sensors: a contact sweeps past — they never saw you.[/]"
    if isinstance(event, AlienSpoke) and event.context in _COMBAT_BEAT_LINES:
        # Combat beats surface in the log (§6.7, WP31); conversational AlienSpoke
        # events stay silent — the contact screen carries those lines itself.
        return _COMBAT_BEAT_LINES[event.context]
    if isinstance(event, CombatRound):
        return (f"[red]⚔ Round {event.round}[/]: dealt {event.damage_dealt}, "
                f"took {event.damage_taken} ({event.foes_left} foes left)")
    if isinstance(event, EncounterEnded):
        return {
            "fled": "[yellow]↯ Broke away — escaped the engagement.[/]",
            "victory": "[green]⚔ Victory — the pack is destroyed.[/]",
            "destroyed": "[red]✖ Ship lost — the escape pod tumbles clear.[/]",
        }.get(event.outcome, f"Encounter ended: {event.outcome}")
    if isinstance(event, ComponentKnockedOut):
        return f"[red]✖ Direct hit — {event.subsystem} {event.component} knocked out![/]"
    if isinstance(event, ShipDestroyed):
        return f"[red]✖ The {event.lost_ship} breaks up — you take to the escape pod.[/]"
    if isinstance(event, SalvageCollected):
        parts = f" + {', '.join(event.components)}" if event.components else ""
        return f"[green]⛏ Salvaged {event.latinum} latinum from the wrecks{parts}.[/]"
    if isinstance(event, GrudgeFormed):
        tail = "they will never forget" if event.permanent else "they will remember"
        return f"[red]☠ The {event.species_kind} mark you — {tail}.[/]"
    if isinstance(event, CoreLawNotice):
        return "[yellow]⚖ Governor's patrol: your record is known here. Mind yourself.[/]"
    if isinstance(event, GovernanceChanged):
        return "[yellow]⚑ The Core changes hands — a new alliance governs the heart of the galaxy.[/]"
    if isinstance(event, AllianceLeadershipChanged):
        return f"[yellow]⚑ A coup: the {event.new_leader_roster} seize leadership of their bloc.[/]"
    if isinstance(event, AdmissionAdvanced):
        return f"[green]✔ Admission task complete: {event.task}.[/]"
    if isinstance(event, AllianceJoined):
        return "[green]⚑ You have sworn to a new banner. Old friends may now be foes.[/]"
    if isinstance(event, AllianceResigned):
        return "[yellow]⚑ You renounce your banner — old enmities cool.[/]"
    if isinstance(event, StarbaseRazed):
        return f"[red]☄ The starbase is razed — its world lies open (bounty {event.bounty}).[/]"
    if isinstance(event, StarbaseRepaired):
        return f"[green]⚙ Base repaired: {event.subsystem} slot {event.slot_index} refilled.[/]"
    if isinstance(event, StarbaseClaimed):
        return "[green]⚑ The base is yours — a forward foothold on the frontier.[/]"
    if isinstance(event, CitadelBuildStarted):
        return f"[cyan]⛨ Citadel level {event.target_level} construction begun.[/]"
    if isinstance(event, CitadelCompleted):
        return f"[green]⛨ Citadel level {event.level} complete — the world stands fortified.[/]"
    if isinstance(event, PlanetBanked):
        verb = "deposited to" if event.kind == "deposit" else "withdrawn from"
        return f"[dim]⛁ {event.amount:,} slips {verb} the citadel treasury (now {event.balance:,}).[/]"
    if isinstance(event, CitadelGunSilenced):
        return "[yellow]⚔ The citadel gun falls silent — the ground lies open.[/]"
    if isinstance(event, PlanetInvaded):
        return (f"[green]⚑ The world is taken — {event.colonists:,} colonists spared, "
                f"{event.loot:,} slips seized (lost {event.fighters_lost} fighters).[/]")
    if isinstance(event, InvasionRepulsed):
        return f"[red]✖ The ground assault is thrown back — {event.fighters_lost} fighters lost.[/]"
    if isinstance(event, ProbeReport):
        if event.destroyed:
            return f"[yellow]◈ Probe lost — charted {event.sectors_charted} new sectors before it fell.[/]"
        return (f"[cyan]◈ Probe report: {event.sectors_charted} new sectors, "
                f"{event.ports} ports, {event.planets} planets, {event.contacts} contacts.[/]")
    if isinstance(event, InterdictorToggled):
        return ("[cyan]◈ Interdictor engaged — the sector is pinned.[/]" if event.active
                else "[dim]◈ Interdictor disengaged.[/]")
    if isinstance(event, LimpetsRemoved):
        return f"[green]◈ {event.count} limpet(s) stripped from the hull ({event.fee} slips).[/]"
    if isinstance(event, TerritoryDeployed):
        if event.kind == "beacon":
            return "[cyan]⚑ Beacon planted.[/]"
        return f"[cyan]⚑ Deployed {event.count} {event.kind} to hold the sector.[/]"
    if isinstance(event, HazardDamage):
        label = "Mines" if event.source == "mine" else "Gravity shear"
        return f"[red]✷ {label} — {event.damage} hull damage![/]"
    if isinstance(event, ContractAccepted):
        return (f"[cyan]✎ Favor accepted ({event.kind}) — {event.reward:,} slips on delivery, "
                f"due day {event.deadline_day}.[/]")
    if isinstance(event, ContractCompleted):
        return f"[green]✓ Favor fulfilled — {event.reward:,} slips paid.[/]"
    if isinstance(event, ContractFailed):
        why = "deadline passed" if event.reason == "deadline" else "abandoned"
        return f"[yellow]✖ Favor failed ({why}).[/]"
    if isinstance(event, RumorHeard):
        return f"[cyan]✎ A tavern rumour points the way — a new lead logged ({event.price} slips).[/]"
    if isinstance(event, NoticePosted):
        return "[dim]✎ Your notice is pinned to the board.[/]"
    if isinstance(event, PlayerAttacked):
        return "[red]⚔ A rival captain opens fire — PvP engagement![/]"
    if isinstance(event, BountyPosted):
        return f"[red]⚠ You are outlawed — a {event.total:,}-slip bounty rides on your head.[/]"
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
    if isinstance(event, (EncounterStarted, EncounterEvaded)):
        return event.sector_id
    if isinstance(event, (ShipDestroyed, CoreLawNotice, StarbaseRazed,
                          TerritoryDeployed, HazardDamage)):
        return event.sector_id
    if isinstance(event, (CombatRound, EncounterEnded, ComponentKnockedOut,
                          SalvageCollected, GrudgeFormed)):
        player = state.players.get(event.player_id)
        ship = state.ships.get(player.ship_id) if player is not None else None
        return ship.sector_id if ship is not None else None
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
    if isinstance(event, (CitadelGunSilenced, PlanetInvaded, InvasionRepulsed)):
        planet = state.planets.get(event.planet_id)
        return planet.sector_id if planet is not None else None
    if isinstance(event, PortOrderFilled):
        port = state.ports.get(event.port_id)
        return port.sector_id if port is not None else None
    if isinstance(event, PlayerAttacked):
        return event.sector_id
    return None


# Galaxy-wide announcements: every player hears them wherever they are (§6.3/§8) — a
# governance flip, a market settlement aggregate, an alliance leadership change reach all.
_GLOBAL_EVENTS: tuple[type[Event], ...] = (
    MarketSettled, GovernanceChanged, AllianceLeadershipChanged, CoreLawNotice,
)

# Events a bystander sharing the sector witnesses first-hand: arrivals, drift, combat,
# destruction, deployment, siege. A non-actor receives one only when present in — or having
# charted — the sector (the fog write-side twin, WP65). Every *other* event is private to its
# acting player (their own ledger: trades, banking, purchases, contracts, colony ticks).
_SECTOR_PUBLIC_EVENTS: tuple[type[Event], ...] = (
    Warped, AlienMoved, ShipDestroyed, StarbaseRazed, TerritoryDeployed, HazardDamage,
    EncounterStarted, EncounterEvaded, EncounterEnded, CombatRound, ComponentKnockedOut,
    SalvageCollected, GrudgeFormed, GenesisDeployed, CitadelGunSilenced, PlanetInvaded,
    InvasionRepulsed, PortOrderFilled, PlayerAttacked,
)


def _event_player(event: Event) -> int | None:
    """The acting/addressed player of an event, if any (its `player_id`/`owner_player_id`)."""
    pid = getattr(event, "player_id", None)
    if pid is not None:
        return int(pid)
    owner = getattr(event, "owner_player_id", None)
    return int(owner) if owner is not None else None


def event_visible_to(state: UniverseState, event: Event, player_id: int) -> bool:
    """Whether `player_id` should receive `event` under the fog-of-war broadcast policy (WP65).

    The write-side twin of the read projections' explored-sectors gate: a global announcement
    reaches everyone; a sector-witnessed event reaches its actor plus any player present in or
    having charted the sector; every other event is private to its acting player. Single-player
    (one seat) sees exactly what it saw before — the actor short-circuit, global pass-through, and
    the fog-safe emission of drift/settlement events mean nothing it used to see is now hidden.
    """
    if isinstance(event, _GLOBAL_EVENTS):
        return True
    owner = _event_player(event)
    if isinstance(event, _SECTOR_PUBLIC_EVENTS):
        if owner is not None and owner == player_id:
            return True  # the actor always sees their own action, wherever they now are
        sector = _event_sector(event, state)
        if sector is None:
            return owner is None or owner == player_id
        viewer = state.players.get(player_id)
        if viewer is None:
            return False
        ship = state.ships.get(viewer.ship_id)
        if ship is not None and ship.sector_id == sector:
            return True  # present in the sector — witnessed live
        return sector in viewer.explored_sectors  # charted it — hears of it after the fact
    # Private / player-addressed (or an unowned, fog-safe-emitted event with no anchor).
    return owner is None or owner == player_id


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
        if not event_visible_to(state, event, player_id):
            continue  # fog write-side twin (WP65): another player's private/off-sector event
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
