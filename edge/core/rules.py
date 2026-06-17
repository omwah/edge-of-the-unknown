"""Command → (state delta, events) reducers (DESIGN §3) — the only state mutators.

Each reducer is pure: it reads the `UniverseState`, validates the command, and
returns a `ReduceResult` of new frozen entities plus the events that occurred —
it never edits state in place. `apply_result` performs the actual upsert into the
mutable container (the service wraps that in a store transaction, WP6). Invariants
are delegated to `core.economy` and `core.movement`; randomness (haggling) is
drawn from the state-owned RNG, so replay from `(seed, command log)` is exact.

Command set: movement (Warp, TravelTo, Dock), trade (Trade, HaggleOffer), banking
(Deposit, Withdraw), StarDock services (BuyComponent, BuyShip, RepairAtDock), and
engine-room work (InstallComponent, SwapComponent, Cannibalize, FieldPatch).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import assert_never

from edge.core.config import GameConfig
from edge.core.economy import (
    EconomyError,
    HaggleStatus,
    deposit,
    execute_trade,
    port_unit_price,
    resolve_haggle,
    withdraw,
)
from edge.core.engine_room import (
    EngineRoomError,
    apply_derived,
    build_subsystems,
    legal_components,
    tier_ceiling,
)
from edge.core.discovery import is_detectable, sector_has_nebula
from edge.core.enums import (
    Commodity,
    Component,
    ComponentTier,
    PayloadKind,
    PortClass,
    Subsystem,
)
from edge.core.events import (
    Banked,
    Colonized,
    ColonistsRecruited,
    ComponentInstalled,
    ComponentPurchased,
    ComponentRemoved,
    DiscoveryCollected,
    Docked,
    Event,
    Haggled,
    Repaired,
    ShipPurchased,
    StarbaseSalvaged,
    Traded,
    Warped,
)
from edge.core.planets import is_colonizable
from edge.core.starbases import is_operational
from edge.core.models import (
    Discovery,
    Game,
    InstalledComponent,
    Ownership,
    Planet,
    Player,
    Port,
    Ship,
    Starbase,
    SubsystemState,
    UniverseState,
)
from edge.core.movement import MovementError, can_warp, shortest_path

# --- commands ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Warp:
    to_sector: int


@dataclass(frozen=True, slots=True)
class TravelTo:
    """A multi-hop warp to a known sector along its uncovered route (WP-C)."""

    to_sector: int


@dataclass(frozen=True, slots=True)
class Dock:
    pass


@dataclass(frozen=True, slots=True)
class Trade:
    commodity: Commodity
    units: int
    unit_price: int | None = None  # None => quote at the §8 price (quick-trade)


@dataclass(frozen=True, slots=True)
class HaggleOffer:
    commodity: Commodity
    units: int
    counter_price: int


@dataclass(frozen=True, slots=True)
class Deposit:
    amount: int


@dataclass(frozen=True, slots=True)
class Withdraw:
    amount: int


@dataclass(frozen=True, slots=True)
class BuyComponent:
    """Buy a loose component from the StarDock hardware emporium (§8). Tier III is barter-only."""

    component: Component
    tier: ComponentTier


@dataclass(frozen=True, slots=True)
class BuyShip:
    """Trade the current hull for a buyable class at the StarDock shipyard (§8)."""

    ship_class_id: str


@dataclass(frozen=True, slots=True)
class RepairAtDock:
    """StarDock restoration of a knocked-out component (§4.1). Inert until Phase-3 combat."""

    subsystem: Subsystem
    slot_index: int


@dataclass(frozen=True, slots=True)
class RecruitColonists:
    """Recruit colonists into the ship's occupancy (§4.2). Recruited, never bought.

    `from_planet` None ⇒ StarDock recruitment office (pay a per-head latinum incentive);
    a planet id ⇒ emigration from that inhabited world (the disposition gate lands in WP7).
    """

    count: int
    from_planet: int | None = None


@dataclass(frozen=True, slots=True)
class Colonize:
    """Settle recruited colonists onto an unowned colonizable world, claiming it (§8)."""

    planet_id: int
    colonists: int


@dataclass(frozen=True, slots=True)
class SetAllocation:
    """Set a player-owned colony's production split over the trio (§8)."""

    planet_id: int
    allocation: dict[str, float]  # Commodity value -> share


@dataclass(frozen=True, slots=True)
class InstallComponent:
    """Slot a loose component from the hold into an empty subsystem slot (§4.1)."""

    subsystem: Subsystem
    slot_index: int
    component: Component
    tier: ComponentTier


@dataclass(frozen=True, slots=True)
class SwapComponent:
    """Replace a filled slot's component with a loose one; the old part returns to the hold."""

    subsystem: Subsystem
    slot_index: int
    component: Component
    tier: ComponentTier


@dataclass(frozen=True, slots=True)
class Cannibalize:
    """Pull a component out of a filled slot into the loose-part inventory (§4.1).

    `starbase_id` None ⇒ strip the player's own ship; a starbase id ⇒ salvage an
    orbital base in the current sector (§4.2, WP4) — allowed only when that base is
    derelict or player-owned. The salvaged part lands in the ship's loose inventory.
    """

    subsystem: Subsystem
    slot_index: int
    starbase_id: int | None = None


@dataclass(frozen=True, slots=True)
class Salvage:
    """Log/collect a currently-visible open-space discovery into the codex (§7, WP5).

    Visibility is recomputed live from the ship's sensors (obvious finds always; a
    hidden find only when sensors clear its tier difficulty). Takes the payload
    aboard (component / latinum / artifact; lore is codex-only) and marks it found.
    Surface sites are reached by descent (WP6), not from space.
    """

    discovery_id: int


@dataclass(frozen=True, slots=True)
class FieldPatch:
    """Spend one repair-kit to un-knock-out a damaged component (§4.1).

    Structurally present in Phase 2 but only meaningful once Phase-3 combat sets
    `knocked_out`; against an undamaged slot it is rejected (nothing to patch).
    """

    subsystem: Subsystem
    slot_index: int


Command = (
    Warp | TravelTo | Dock | Trade | HaggleOffer | Deposit | Withdraw
    | BuyComponent | BuyShip | RepairAtDock
    | RecruitColonists | Colonize | SetAllocation
    | InstallComponent | SwapComponent | Cannibalize | FieldPatch
    | Salvage
)


# --- result -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReduceResult:
    """The events that occurred plus the new entities to upsert into state."""

    events: tuple[Event, ...] = ()
    players: tuple[Player, ...] = ()
    ships: tuple[Ship, ...] = ()
    ports: tuple[Port, ...] = ()
    planets: tuple[Planet, ...] = ()
    starbases: tuple[Starbase, ...] = ()
    discoveries: tuple[Discovery, ...] = ()
    game: Game | None = None  # set by maintenance reducers (e.g. daily day-number bump)


def apply_result(state: UniverseState, result: ReduceResult) -> None:
    """Upsert a reducer's new entities into the mutable container (sanctioned)."""
    for player in result.players:
        state.players[player.id] = player
    for ship in result.ships:
        state.ships[ship.id] = ship
    for port in result.ports:
        state.ports[port.id] = port
    for planet in result.planets:
        state.planets[planet.id] = planet
    for starbase in result.starbases:
        state.starbases[starbase.id] = starbase
    for discovery in result.discoveries:
        state.discoveries[discovery.id] = discovery
    if result.game is not None:
        state.game = result.game


# --- reducers ---------------------------------------------------------------


def reduce(
    state: UniverseState, player_id: int, command: Command, config: GameConfig
) -> ReduceResult:
    """Validate `command` for `player_id` and return its delta + events."""
    match command:
        case Warp():
            return _warp(state, player_id, command)
        case TravelTo():
            return _travel(state, player_id, command)
        case Dock():
            return _dock(state, player_id)
        case Trade():
            return _trade(state, player_id, command, config)
        case HaggleOffer():
            return _haggle(state, player_id, command, config)
        case Deposit():
            return _bank(state, player_id, command.amount, withdraw_=False)
        case Withdraw():
            return _bank(state, player_id, command.amount, withdraw_=True)
        case BuyComponent():
            return _buy_component(state, player_id, command, config)
        case BuyShip():
            return _buy_ship(state, player_id, command, config)
        case RepairAtDock():
            return _repair_at_dock(state, player_id, command, config)
        case RecruitColonists():
            return _recruit_colonists(state, player_id, command, config)
        case Colonize():
            return _colonize(state, player_id, command, config)
        case SetAllocation():
            return _set_allocation(state, player_id, command, config)
        case InstallComponent():
            return _install_component(state, player_id, command, config)
        case SwapComponent():
            return _swap_component(state, player_id, command, config)
        case Cannibalize():
            return _cannibalize(state, player_id, command, config)
        case FieldPatch():
            return _field_patch(state, player_id, command, config)
        case Salvage():
            return _salvage(state, player_id, command, config)
        case _ as unreachable:
            assert_never(unreachable)


def _player(state: UniverseState, player_id: int) -> Player:
    player = state.players.get(player_id)
    if player is None:
        raise MovementError(f"no such player {player_id}")
    return player


def _ship(state: UniverseState, player: Player) -> Ship:
    return state.ships[player.ship_id]


def _docked_port(state: UniverseState, ship: Ship) -> Port:
    port = state.port_in_sector(ship.sector_id)
    if port is None:
        raise MovementError("no port in this sector")
    return port


def _warp(state: UniverseState, player_id: int, cmd: Warp) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    if not can_warp(state.adjacency, ship.sector_id, cmd.to_sector):
        raise MovementError(f"no warp from {ship.sector_id} to {cmd.to_sector}")
    cost = ship.turns_per_warp
    if player.turns_remaining < cost:
        raise MovementError("out of turns")
    new_ship = replace(ship, sector_id=cmd.to_sector)
    new_player = replace(
        player,
        turns_remaining=player.turns_remaining - cost,
        explored_sectors=player.explored_sectors | frozenset({cmd.to_sector}),
        entered_from={**player.entered_from, cmd.to_sector: ship.sector_id},
    )
    return ReduceResult(
        events=(Warped(player_id, ship.sector_id, cmd.to_sector, cost),),
        players=(new_player,),
        ships=(new_ship,),
    )


def _should_interrupt(state: UniverseState, player: Player, sector_id: int) -> bool:
    """Whether a multi-hop journey must halt on entering `sector_id`.

    Phase-1 stub — always False. Phase 3 injects the hostile-encounter roll here
    so a `TravelTo` stops mid-route when an alien intercepts the player (§10).
    """
    return False


def _travel(state: UniverseState, player_id: int, cmd: TravelTo) -> ReduceResult:
    """Multi-hop warp along a *known* route (§9, §11, WP-C).

    Route-locked: the path is found through already-explored sectors only, so the
    player can only `TravelTo` a destination whose route they have uncovered. The
    journey applies hop-by-hop (one `Warped` per hop), halting early if turns run
    out or `_should_interrupt` fires — the same per-sector seam combat will use.
    """
    player = _player(state, player_id)
    ship = _ship(state, player)
    path = shortest_path(state.adjacency, ship.sector_id, cmd.to_sector,
                         allowed=set(player.explored_sectors))
    if path is None:
        raise MovementError(f"no uncovered route to {cmd.to_sector}")
    hops = path[1:]
    if not hops:
        raise MovementError("already in that sector")
    cost = ship.turns_per_warp
    if player.turns_remaining < cost:
        raise MovementError("out of turns")

    events: list[Event] = []
    current = ship.sector_id
    turns = player.turns_remaining
    explored = player.explored_sectors
    entered = dict(player.entered_from)
    for nxt in hops:
        if turns < cost or _should_interrupt(state, player, nxt):
            break
        turns -= cost
        events.append(Warped(player_id, current, nxt, cost))
        entered[nxt] = current
        explored = explored | frozenset({nxt})
        current = nxt

    new_ship = replace(ship, sector_id=current)
    new_player = replace(player, turns_remaining=turns,
                         explored_sectors=explored, entered_from=entered)
    return ReduceResult(events=tuple(events), players=(new_player,), ships=(new_ship,))


def _dock(state: UniverseState, player_id: int) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    port = _docked_port(state, ship)
    if player.turns_remaining < 1:
        raise MovementError("out of turns")
    new_player = replace(player, turns_remaining=player.turns_remaining - 1)
    return ReduceResult(
        events=(Docked(player_id, ship.sector_id, port.id),), players=(new_player,)
    )


def _trade(
    state: UniverseState, player_id: int, cmd: Trade, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    port = _docked_port(state, ship)
    line = port.line(cmd.commodity)
    if line is None:
        raise EconomyError(f"port does not trade {cmd.commodity.value}")
    price = cmd.unit_price if cmd.unit_price is not None else port_unit_price(line, config.economy)
    out = execute_trade(
        port=port, ship=ship, player=player,
        commodity=cmd.commodity, units=cmd.units, unit_price=price,
    )
    return ReduceResult(
        events=(Traded(player_id, port.id, cmd.commodity, out.mode, out.units, out.unit_price, out.total),),
        players=(out.player,), ships=(out.ship,), ports=(out.port,),
    )


def _haggle(
    state: UniverseState, player_id: int, cmd: HaggleOffer, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    port = _docked_port(state, ship)
    line = port.line(cmd.commodity)
    if line is None:
        raise EconomyError(f"port does not trade {cmd.commodity.value}")
    fair = port_unit_price(line, config.economy)
    hg = config.economy.haggling
    # Recent-attempt history is not tracked in Phase 1 (no haggle-history field
    # on Player yet), so recent_attempts is 0 here.
    result = resolve_haggle(
        fair, cmd.counter_price, line.mode, state.rng,
        insult_frac=hg.insult_frac, history_penalty=hg.history_penalty, recent_attempts=0,
    )
    haggled = Haggled(player_id, port.id, cmd.commodity, result.status.value, result.price)
    if result.status is HaggleStatus.ACCEPTED and result.price is not None:
        out = execute_trade(
            port=port, ship=ship, player=player,
            commodity=cmd.commodity, units=cmd.units, unit_price=result.price,
        )
        traded = Traded(player_id, port.id, cmd.commodity, out.mode, out.units, out.unit_price, out.total)
        return ReduceResult(
            events=(haggled, traded), players=(out.player,), ships=(out.ship,), ports=(out.port,),
        )
    return ReduceResult(events=(haggled,))


def _bank(
    state: UniverseState, player_id: int, amount: int, *, withdraw_: bool
) -> ReduceResult:
    player = _player(state, player_id)
    new_player = withdraw(player, amount) if withdraw_ else deposit(player, amount)
    kind = "withdraw" if withdraw_ else "deposit"
    return ReduceResult(
        events=(Banked(player_id, kind, amount, new_player.bank_balance),),
        players=(new_player,),
    )


# --- StarDock services: buy component / buy hull / repair (§8, §11) ---------


def _stardock(state: UniverseState, ship: Ship) -> Port:
    """The StarDock in the ship's current sector, or raise (services are dock-only)."""
    port = _docked_port(state, ship)
    if port.klass is not PortClass.STARDOCK:
        raise EconomyError("that service is offered only at a StarDock")
    return port


def _buy_component(
    state: UniverseState, player_id: int, cmd: BuyComponent, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    _stardock(state, ship)
    price = config.economy.component_price(cmd.tier)
    if price is None:
        raise EconomyError(f"tier {cmd.tier.name} components are barter-only, not for sale")
    if cmd.component.value not in config.hardware.components or cmd.tier.name not in config.hardware.tiers:
        raise EconomyError(f"this dock does not stock {cmd.component.value} (tier {cmd.tier.name})")
    if player.latinum < price:
        raise EconomyError("insufficient latinum for the component")
    if ship.holds_free < 1:
        raise EconomyError("no free hold for the component — sell cargo first")
    key = (cmd.component, cmd.tier)
    new_components = {**ship.components, key: ship.components.get(key, 0) + 1}
    new_ship = replace(ship, components=new_components)
    new_player = replace(player, latinum=player.latinum - price)
    return ReduceResult(
        events=(ComponentPurchased(player_id, cmd.component.value, cmd.tier.name, price),),
        players=(new_player,), ships=(new_ship,),
    )


def _buy_ship(
    state: UniverseState, player_id: int, cmd: BuyShip, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    _stardock(state, ship)
    try:
        new_class = config.ship_class(cmd.ship_class_id)
    except KeyError as exc:
        raise EconomyError(f"no such hull {cmd.ship_class_id!r}") from exc
    if new_class.id == ship.type_id:
        raise EconomyError("you already fly that hull")
    if new_class.price <= 0:
        raise EconomyError("that hull is not for sale")

    # Trade-in credit for the current hull (the starter hull is free → 0 credit).
    old_class = config.ship_class(ship.type_id)
    trade_in = round(old_class.price * config.economy.ship_trade_in_frac)
    net_cost = new_class.price - trade_in
    if player.latinum < net_cost:
        raise EconomyError("insufficient latinum for the hull, even after trade-in")
    if ship.colonists > new_class.colonist_capacity:
        raise EconomyError("the new hull has too few berths for your colonists — settle them first")

    # The old hull's installed components return to loose inventory; the new hull
    # arrives with its own fresh base slots. Cargo and existing loose parts carry over.
    returned = _strip_installed(ship)
    merged = dict(ship.components)
    for key, count in returned.items():
        merged[key] = merged.get(key, 0) + count
    new_ship = apply_derived(replace(
        ship, type_id=new_class.id, name=new_class.name, holds_total=new_class.holds_total,
        hull_max=new_class.hull_max, hull_current=new_class.hull_max,
        cloak_rating=new_class.cloak_rating, sensor_rating=new_class.sensor_rating,
        shields=new_class.shields_max, warp_speed=new_class.warp_speed,
        combat_speed=new_class.combat_speed, turns_per_warp=new_class.turns_per_warp,
        colonist_capacity=new_class.colonist_capacity,
        subsystems=build_subsystems(new_class), components=merged,
    ), config)
    if new_ship.holds_used > new_ship.holds_total:
        raise EconomyError(
            "returned components plus cargo exceed the new hull's holds — "
            "sell components down to make room first"
        )
    new_player = replace(player, latinum=player.latinum - net_cost)
    return ReduceResult(
        events=(ShipPurchased(player_id, new_class.id, net_cost, trade_in),),
        players=(new_player,), ships=(new_ship,),
    )


def _strip_installed(ship: Ship) -> dict[tuple[Component, ComponentTier], int]:
    """Count every component installed in the hull's subsystems (for trade-in return)."""
    counts: dict[tuple[Component, ComponentTier], int] = {}
    for sub in (ship.subsystems or {}).values():
        for slot in sub.slots:
            if slot is not None:
                key = (slot.kind, slot.tier)
                counts[key] = counts.get(key, 0) + 1
    return counts


def _repair_at_dock(
    state: UniverseState, player_id: int, cmd: RepairAtDock, config: GameConfig
) -> ReduceResult:
    """Pay the StarDock to restore a knocked-out component (§4.1, §8).

    Inert in Phase 2 (nothing is knocked out yet); the path is exercised in Phase 3.
    """
    player = _player(state, player_id)
    ship = _engine_ship(state, player_id)
    _stardock(state, ship)
    sub = _subsystem(ship, cmd.subsystem)
    _check_slot(sub, cmd.slot_index)
    comp = sub.slots[cmd.slot_index]
    if comp is None:
        raise EngineRoomError("slot is empty — nothing to repair")
    if not comp.knocked_out:
        raise EngineRoomError("component is not knocked out")
    price = config.economy.component_price(comp.tier) or config.economy.tier_ii_component_latinum
    cost = round(price * config.economy.repair_cost_frac)
    if player.latinum < cost:
        raise EconomyError("insufficient latinum for the repair")
    new_ship = _with_slot(ship, cmd.subsystem, cmd.slot_index, replace(comp, knocked_out=False))
    new_ship = apply_derived(new_ship, config)
    new_player = replace(player, latinum=player.latinum - cost)
    return ReduceResult(
        events=(Repaired(player_id, cmd.subsystem.value, cmd.slot_index),),
        players=(new_player,), ships=(new_ship,),
    )


# --- colonists: recruit / colonize / allocation (§4.2, §8) ------------------


def _even_allocation() -> dict[Commodity, float]:
    """An equal split of production over the trio — the default for a new colony."""
    share = 1.0 / len(Commodity)
    return {c: share for c in Commodity}


def _recruit_colonists(
    state: UniverseState, player_id: int, cmd: RecruitColonists, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    if cmd.count <= 0:
        raise EconomyError("recruit count must be positive")
    free = ship.colonist_capacity - ship.colonists
    if free <= 0:
        raise EconomyError("no colonist berths free")
    count = min(cmd.count, free)  # clamp to the ship's separate occupancy limit (§4.2)

    if cmd.from_planet is None:
        # StarDock recruitment office — a per-head latinum incentive (not a purchase).
        _stardock(state, ship)
        cost = count * config.economy.colonist_incentive
        if player.latinum < cost:
            raise EconomyError("insufficient latinum for the recruitment incentive")
        new_player = replace(player, latinum=player.latinum - cost)
        new_ship = replace(ship, colonists=ship.colonists + count)
        return ReduceResult(
            events=(ColonistsRecruited(player_id, "stardock", count, cost),),
            players=(new_player,), ships=(new_ship,),
        )

    # Emigration from an inhabited world in orbit (the disposition gate lands in WP7).
    planet = state.planets.get(cmd.from_planet)
    if planet is None or planet.sector_id != ship.sector_id:
        raise EconomyError("no such world here to recruit from")
    if planet.inhabited_by_species_id is None:
        raise EconomyError("that world has no population to emigrate")
    new_ship = replace(ship, colonists=ship.colonists + count)
    return ReduceResult(
        events=(ColonistsRecruited(player_id, "emigration", count, 0),), ships=(new_ship,),
    )


def _colonize(
    state: UniverseState, player_id: int, cmd: Colonize, config: GameConfig
) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    planet = state.planets.get(cmd.planet_id)
    if planet is None or planet.sector_id != ship.sector_id:
        raise EconomyError("no such world in this sector")
    if planet.owner.is_owned:
        raise EconomyError("that world is already claimed")  # Core worlds are governor-owned
    if not is_colonizable(planet.planet_type, config):
        raise EconomyError(f"a {planet.planet_type} world cannot be colonized")
    if cmd.colonists <= 0:
        raise EconomyError("must land at least one colonist")
    if cmd.colonists > ship.colonists:
        raise EconomyError("not enough colonists aboard")
    new_ship = replace(ship, colonists=ship.colonists - cmd.colonists)
    new_planet = replace(
        planet, owner=Ownership("player", player_id),
        colonists=planet.colonists + cmd.colonists,
        allocation=planet.allocation or _even_allocation(),
    )
    return ReduceResult(
        events=(Colonized(player_id, planet.id, cmd.colonists),),
        ships=(new_ship,), planets=(new_planet,),
    )


def _set_allocation(
    state: UniverseState, player_id: int, cmd: SetAllocation, config: GameConfig
) -> ReduceResult:
    _player(state, player_id)
    planet = state.planets.get(cmd.planet_id)
    if planet is None:
        raise EconomyError("no such world")
    if planet.owner.kind != "player" or planet.owner.ref != player_id:
        raise EconomyError("you do not own that world")
    alloc = {c: float(cmd.allocation.get(c.value, 0.0)) for c in Commodity}
    total = sum(alloc.values())
    if total <= 0:
        raise EconomyError("allocation must be positive")
    normalized = {c: v / total for c, v in alloc.items()}
    return ReduceResult(planets=(replace(planet, allocation=normalized),))


# --- engine room: install / swap / cannibalize / field-patch (§4.1) ---------


def _engine_ship(state: UniverseState, player_id: int) -> Ship:
    ship = _ship(state, _player(state, player_id))
    if ship.subsystems is None:
        raise EngineRoomError("this hull has no engine room")
    return ship


def _subsystem(ship: Ship, subsystem: Subsystem) -> SubsystemState:
    assert ship.subsystems is not None  # guarded by _engine_ship
    sub = ship.subsystems.get(subsystem)
    if sub is None:
        raise EngineRoomError(f"hull has no {subsystem.value} subsystem")
    return sub


def _check_slot(sub: SubsystemState, slot_index: int) -> None:
    if not 0 <= slot_index < len(sub.slots):
        raise EngineRoomError(f"no slot {slot_index} in subsystem")


def _validate_install(
    ship: Ship, subsystem: Subsystem, component: Component, tier: ComponentTier, config: GameConfig
) -> None:
    klass = config.ship_class(ship.type_id)
    if component not in legal_components(klass, subsystem):
        raise EngineRoomError(f"{component.value} is not legal in {subsystem.value}")
    if tier.value > tier_ceiling(config.engine_room).value:
        raise EngineRoomError(f"tier {tier.name} exceeds the install ceiling")


def _inv_take(components: Mapping[tuple[Component, ComponentTier], int],
              key: tuple[Component, ComponentTier]) -> dict[tuple[Component, ComponentTier], int]:
    """Return the inventory with one of `key` removed; raise if none on hand."""
    have = components.get(key, 0)
    if have < 1:
        raise EngineRoomError(f"no {key[0].value} (tier {key[1].name}) in the hold")
    new = dict(components)
    if have == 1:
        del new[key]
    else:
        new[key] = have - 1
    return new


def _inv_add(components: Mapping[tuple[Component, ComponentTier], int],
             key: tuple[Component, ComponentTier]) -> dict[tuple[Component, ComponentTier], int]:
    """Return the inventory with one of `key` added."""
    new = dict(components)
    new[key] = new.get(key, 0) + 1
    return new


def _with_slot(ship: Ship, subsystem: Subsystem, slot_index: int,
               value: InstalledComponent | None) -> Ship:
    """Return `ship` with one subsystem slot replaced (subsystems map copied)."""
    assert ship.subsystems is not None
    sub = ship.subsystems[subsystem]
    slots = list(sub.slots)
    slots[slot_index] = value
    new_sub = replace(sub, slots=tuple(slots))
    return replace(ship, subsystems={**ship.subsystems, subsystem: new_sub})


def _install_component(
    state: UniverseState, player_id: int, cmd: InstallComponent, config: GameConfig
) -> ReduceResult:
    ship = _engine_ship(state, player_id)
    sub = _subsystem(ship, cmd.subsystem)
    _check_slot(sub, cmd.slot_index)
    if sub.slots[cmd.slot_index] is not None:
        raise EngineRoomError("slot is already filled")
    _validate_install(ship, cmd.subsystem, cmd.component, cmd.tier, config)
    new_components = _inv_take(ship.components, (cmd.component, cmd.tier))
    new_ship = _with_slot(ship, cmd.subsystem, cmd.slot_index,
                          InstalledComponent(cmd.component, cmd.tier))
    new_ship = apply_derived(replace(new_ship, components=new_components), config)
    return ReduceResult(
        events=(ComponentInstalled(player_id, cmd.subsystem.value, cmd.slot_index,
                                   cmd.component.value, cmd.tier.name),),
        ships=(new_ship,),
    )


def _swap_component(
    state: UniverseState, player_id: int, cmd: SwapComponent, config: GameConfig
) -> ReduceResult:
    ship = _engine_ship(state, player_id)
    sub = _subsystem(ship, cmd.subsystem)
    _check_slot(sub, cmd.slot_index)
    old = sub.slots[cmd.slot_index]
    if old is None:
        raise EngineRoomError("slot is empty — install instead of swap")
    _validate_install(ship, cmd.subsystem, cmd.component, cmd.tier, config)
    # The new part comes off the hold; the old part goes back on (conserved).
    new_components = _inv_add(
        _inv_take(ship.components, (cmd.component, cmd.tier)), (old.kind, old.tier)
    )
    new_ship = _with_slot(ship, cmd.subsystem, cmd.slot_index,
                          InstalledComponent(cmd.component, cmd.tier))
    new_ship = apply_derived(replace(new_ship, components=new_components), config)
    return ReduceResult(
        events=(
            ComponentRemoved(player_id, cmd.subsystem.value, cmd.slot_index,
                             old.kind.value, old.tier.name),
            ComponentInstalled(player_id, cmd.subsystem.value, cmd.slot_index,
                               cmd.component.value, cmd.tier.name),
        ),
        ships=(new_ship,),
    )


def _cannibalize(
    state: UniverseState, player_id: int, cmd: Cannibalize, config: GameConfig
) -> ReduceResult:
    if cmd.starbase_id is not None:
        return _cannibalize_starbase(state, player_id, cmd, config)
    ship = _engine_ship(state, player_id)
    sub = _subsystem(ship, cmd.subsystem)
    _check_slot(sub, cmd.slot_index)
    comp = sub.slots[cmd.slot_index]
    if comp is None:
        raise EngineRoomError("slot is already empty")
    if ship.holds_free < 1:
        raise EngineRoomError("no free hold for the salvaged component — sell cargo first")
    new_components = _inv_add(ship.components, (comp.kind, comp.tier))
    new_ship = _with_slot(ship, cmd.subsystem, cmd.slot_index, None)
    new_ship = apply_derived(replace(new_ship, components=new_components), config)
    return ReduceResult(
        events=(ComponentRemoved(player_id, cmd.subsystem.value, cmd.slot_index,
                                 comp.kind.value, comp.tier.name),),
        ships=(new_ship,),
    )


def _cannibalize_starbase(
    state: UniverseState, player_id: int, cmd: Cannibalize, config: GameConfig
) -> ReduceResult:
    """Strip a component out of an orbital starbase into the ship's hold (§4.2, WP4).

    Allowed only when the base is derelict (the frontier salvage cache) or already
    player-owned. The base loses exactly what the ship gains (components conserved).
    """
    assert cmd.starbase_id is not None
    player = _player(state, player_id)
    ship = _ship(state, player)
    base = state.starbases.get(cmd.starbase_id)
    if base is None or base.sector_id != ship.sector_id:
        raise EngineRoomError("no such starbase in this sector")
    player_owned = base.owner.kind == "player" and base.owner.ref == player_id
    if is_operational(base) and not player_owned:
        raise EngineRoomError("that starbase is operational — only a derelict or your own base can be salvaged")
    sub = base.subsystems.get(cmd.subsystem)
    if sub is None:
        raise EngineRoomError(f"starbase has no {cmd.subsystem.value} subsystem")
    _check_slot(sub, cmd.slot_index)
    comp = sub.slots[cmd.slot_index]
    if comp is None:
        raise EngineRoomError("slot is already empty")
    if ship.holds_free < 1:
        raise EngineRoomError("no free hold for the salvaged component — sell cargo first")
    slots = list(sub.slots)
    slots[cmd.slot_index] = None
    new_base = replace(base, subsystems={**base.subsystems, cmd.subsystem: replace(sub, slots=tuple(slots))})
    new_ship = replace(ship, components=_inv_add(ship.components, (comp.kind, comp.tier)))
    return ReduceResult(
        events=(StarbaseSalvaged(player_id, base.id, cmd.subsystem.value, cmd.slot_index,
                                 comp.kind.value, comp.tier.name),),
        ships=(new_ship,), starbases=(new_base,),
    )


def _field_patch(
    state: UniverseState, player_id: int, cmd: FieldPatch, config: GameConfig
) -> ReduceResult:
    ship = _engine_ship(state, player_id)
    sub = _subsystem(ship, cmd.subsystem)
    _check_slot(sub, cmd.slot_index)
    comp = sub.slots[cmd.slot_index]
    if comp is None:
        raise EngineRoomError("slot is empty — nothing to patch")
    if not comp.knocked_out:
        raise EngineRoomError("component is not knocked out")
    if ship.repair_kits < 1:
        raise EngineRoomError("no repair kits")
    new_ship = _with_slot(ship, cmd.subsystem, cmd.slot_index,
                          replace(comp, knocked_out=False))
    new_ship = apply_derived(replace(new_ship, repair_kits=ship.repair_kits - 1), config)
    return ReduceResult(
        events=(Repaired(player_id, cmd.subsystem.value, cmd.slot_index),),
        ships=(new_ship,),
    )


# --- discovery: salvage / log to codex (§7, WP5) ----------------------------


def _salvage(
    state: UniverseState, player_id: int, cmd: Salvage, config: GameConfig
) -> ReduceResult:
    """Log a currently-visible open-space discovery into the codex (§7, WP5).

    Visibility is recomputed live from the ship's sensors here (the same gate the
    sector view uses), so you can only log what you can presently see. The payload
    is taken aboard (component → hold, latinum → purse, artifact → barter store;
    lore is codex-only) and the find marked `found_by`. Surface sites (`planet_id`
    set) are reached by descent in WP6, not from space.
    """
    player = _player(state, player_id)
    ship = _ship(state, player)
    disc = state.discoveries.get(cmd.discovery_id)
    if disc is None:
        raise EconomyError("no such discovery")
    if disc.planet_id is not None or disc.sector_id != ship.sector_id:
        raise EconomyError("that discovery is not in this sector")
    if disc.found_by is not None:
        raise EconomyError("that discovery has already been collected")
    in_nebula = sector_has_nebula(state, ship.sector_id)
    if not is_detectable(disc, ship.sensor_rating, in_nebula=in_nebula, config=config):
        raise EconomyError("undetected — your sensors can't pick it out here")
    cost = config.discovery.salvage_turn_cost if config.discovery is not None else 1
    if player.turns_remaining < cost:
        raise MovementError("out of turns")

    payload = disc.payload
    new_player = replace(player, turns_remaining=player.turns_remaining - cost,
                         codex=player.codex | frozenset({disc.id}))
    new_ship = ship
    if payload.kind is PayloadKind.COMPONENT and payload.component is not None and payload.tier is not None:
        if ship.holds_free < 1:
            raise EngineRoomError("no free hold for the salvaged component — sell cargo first")
        key = (payload.component, payload.tier)
        new_ship = replace(ship, components={**ship.components, key: ship.components.get(key, 0) + 1})
    elif payload.kind is PayloadKind.LATINUM:
        new_player = replace(new_player, latinum=new_player.latinum + payload.latinum)
    elif payload.kind is PayloadKind.ARTIFACT and payload.barter_tier is not None:
        artifacts = dict(player.artifacts)
        artifacts[payload.barter_tier] = artifacts.get(payload.barter_tier, 0) + 1
        new_player = replace(new_player, artifacts=artifacts)
    # LORE: codex-only, nothing material.
    new_disc = replace(disc, found_by=player_id)
    return ReduceResult(
        events=(DiscoveryCollected(player_id, disc.id, disc.kind.value,
                                   disc.rarity_tier.name, payload.kind.value),),
        players=(new_player,), ships=(new_ship,), discoveries=(new_disc,),
    )
