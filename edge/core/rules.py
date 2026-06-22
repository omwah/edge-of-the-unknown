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

from edge.core import dialogue
from edge.core.aliens import effective_disposition
from edge.core.dev import DevPatch, apply_dev_patch

from edge.core.config import GameConfig, SpeciesConfig, TechOfferConfig
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
    AlienSpoke,
    AlienTraded,
    AttitudeChanged,
    Banked,
    Colonized,
    ColonistsRecruited,
    ComponentInstalled,
    ComponentPurchased,
    ComponentRemoved,
    Descended,
    DevicePurchased,
    DiscoveryCollected,
    DiscoveryDetected,
    Docked,
    Event,
    GenesisDeployed,
    Haggled,
    Repaired,
    ShipPurchased,
    SiteExplored,
    StarbaseSalvaged,
    Traded,
    Warped,
)
from edge.core.planets import is_colonizable, retype_planet
from edge.core.starbases import is_operational
from edge.core.models import (
    AlienSpecies,
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
    """Log/collect a revealed discovery into the codex (§7, WP5/WP6).

    Open-space: a hidden find must have been detected on entry first (sensors are
    snapshotted at entry, so re-enter after a sensor upgrade to pick up more). Surface
    sites must have been explored first (WP6). Either way takes the payload aboard
    (component / latinum / artifact; lore is codex-only) and marks it found.
    """

    discovery_id: int


@dataclass(frozen=True, slots=True)
class Descend:
    """Land on a planet's surface to explore its sites (§7, WP6). Costs turns."""

    planet_id: int


@dataclass(frozen=True, slots=True)
class Explore:
    """Reveal the next surface site of a planet (§7, WP6).

    Surveys site-by-site: each call reveals the lowest-slot still-hidden site the
    ship's sensors can resolve (obvious sites always; Rare+ sites need a sensor
    sweep). Revealed sites enter `Player.detected` and can then be logged (`Salvage`).
    """

    planet_id: int


@dataclass(frozen=True, slots=True)
class BuyGenesis:
    """Buy one Genesis torpedo from the StarDock (§4.2, WP10). A latinum sink."""


@dataclass(frozen=True, slots=True)
class DeployGenesis:
    """Terraform an eligible unowned planet in the current sector (§4.2, WP10).

    Consumes one carried Genesis torpedo and re-types the world to the configured
    colonizable type, re-rolling its yield/habitability — leaving it claimable.
    """

    planet_id: int


@dataclass(frozen=True, slots=True)
class FieldPatch:
    """Spend one repair-kit to un-knock-out a damaged component (§4.1).

    Structurally present in Phase 2 but only meaningful once Phase-3 combat sets
    `knocked_out`; against an undamaged slot it is rejected (nothing to patch).
    """

    subsystem: Subsystem
    slot_index: int


@dataclass(frozen=True, slots=True)
class Hail:
    """Open contact with a friendly species in the current sector (§6, §6.7, WP9).

    Marks the species met and advances the greeting recency ring so re-hailing
    rephrases rather than replays. No combat — Phase 2 places only friendly species.
    """

    species_id: int


@dataclass(frozen=True, slots=True)
class Converse:
    """Steer an alien conversation to a peaceful dialogue context (§6.7, WP17).

    Speaks the chosen `context` (a `dialogue._PEACEFUL_CONTEXTS` key) in the species'
    voice and advances that context's recency ring so repeats rephrase — the same
    mechanism `Hail` uses for `greeting`, generalised to every peaceful context.
    `subject_id` names the species asked about for `dossier_other` ("ask about X").
    Combat / signature contexts are Phase 3 and rejected here.
    """

    species_id: int
    context: str
    subject_id: int | None = None


@dataclass(frozen=True, slots=True)
class BuyAlienTech:
    """Buy an alien tech offer for latinum (§6, §8, WP9).

    `offer_index` indexes the species' `tech_offers`; the offer must be latinum-mode,
    reachable at the player's effective disposition, and affordable. Delivers a loose
    component or a flat aspect upgrade and raises the player's attitude with the species.
    """

    species_id: int
    offer_index: int


@dataclass(frozen=True, slots=True)
class BarterArtifact:
    """Barter a recovered artifact for an alien tech offer (§6, §8, WP9).

    The offer must be barter-mode and reachable; the player spends one artifact of the
    offer's tier (a discovery payload, §7) for tech no latinum sale gives — the
    exit-criterion payoff. Raises attitude like a purchase.
    """

    species_id: int
    offer_index: int


Command = (
    Warp | TravelTo | Dock | Trade | HaggleOffer | Deposit | Withdraw
    | BuyComponent | BuyShip | RepairAtDock
    | RecruitColonists | Colonize | SetAllocation
    | InstallComponent | SwapComponent | Cannibalize | FieldPatch
    | Salvage | Descend | Explore | BuyGenesis | DeployGenesis
    | Hail | Converse | BuyAlienTech | BarterArtifact
    | DevPatch  # dev/testing cheat (core.dev); recorded in the log like any command
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
    species: tuple[AlienSpecies, ...] = ()  # cron-mutated species positions (WP16 drift)
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
    for species in result.species:
        state.species[species.id] = species
    if result.game is not None:
        state.game = result.game


# --- reducers ---------------------------------------------------------------


def reduce(
    state: UniverseState, player_id: int, command: Command, config: GameConfig
) -> ReduceResult:
    """Validate `command` for `player_id` and return its delta + events."""
    match command:
        case Warp():
            return _warp(state, player_id, command, config)
        case TravelTo():
            return _travel(state, player_id, command, config)
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
        case Descend():
            return _descend(state, player_id, command, config)
        case Explore():
            return _explore(state, player_id, command, config)
        case BuyGenesis():
            return _buy_genesis(state, player_id, config)
        case DeployGenesis():
            return _deploy_genesis(state, player_id, command, config)
        case Hail():
            return _hail(state, player_id, command, config)
        case Converse():
            return _converse(state, player_id, command, config)
        case BuyAlienTech():
            return _buy_alien_tech(state, player_id, command, config)
        case BarterArtifact():
            return _barter_artifact(state, player_id, command, config)
        case DevPatch():
            return apply_dev_patch(state, player_id, command, config)
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


def _detect_in_sector(
    state: UniverseState, detected: frozenset[int], sensor_rating: int,
    sector_id: int, player_id: int, config: GameConfig,
) -> tuple[frozenset[int], tuple[Event, ...]]:
    """Sensor-detect the hidden open-space finds in `sector_id` **on entry** (§7, WP5).

    Pure and deterministic (no RNG): a hidden find is revealed when effective sensor
    rating clears its tier difficulty (a nebula here dims that). The result is
    snapshotted into the player's `detected` set, so later sensor upgrades only help
    on re-entry. Returns the updated set plus one `DiscoveryDetected` per new reveal;
    obvious finds are never added (the projection always shows them).
    """
    if config.discovery is None:
        return detected, ()
    in_nebula = sector_has_nebula(state, sector_id)
    revealed = set(detected)
    events: list[Event] = []
    for d in state.discoveries.values():
        if d.planet_id is not None or d.sector_id != sector_id or d.id in revealed or not d.hidden:
            continue
        if is_detectable(d, sensor_rating, in_nebula=in_nebula, config=config):
            revealed.add(d.id)
            events.append(DiscoveryDetected(player_id, d.id, d.kind.value, d.rarity_tier.name))
    if not events:
        return detected, ()
    return frozenset(revealed), tuple(events)


def _warp(state: UniverseState, player_id: int, cmd: Warp, config: GameConfig) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    if not can_warp(state.adjacency, ship.sector_id, cmd.to_sector):
        raise MovementError(f"no warp from {ship.sector_id} to {cmd.to_sector}")
    cost = ship.turns_per_warp
    if player.turns_remaining < cost:
        raise MovementError("out of turns")
    new_ship = replace(ship, sector_id=cmd.to_sector)
    detected, det_events = _detect_in_sector(
        state, player.detected, ship.sensor_rating, cmd.to_sector, player_id, config)
    new_player = replace(
        player,
        turns_remaining=player.turns_remaining - cost,
        explored_sectors=player.explored_sectors | frozenset({cmd.to_sector}),
        entered_from={**player.entered_from, cmd.to_sector: ship.sector_id},
        detected=detected,
    )
    return ReduceResult(
        events=(Warped(player_id, ship.sector_id, cmd.to_sector, cost), *det_events),
        players=(new_player,),
        ships=(new_ship,),
    )


def _should_interrupt(state: UniverseState, player: Player, sector_id: int) -> bool:
    """Whether a multi-hop journey must halt on entering `sector_id`.

    Phase-1 stub — always False. Phase 3 injects the hostile-encounter roll here
    so a `TravelTo` stops mid-route when an alien intercepts the player (§10).
    """
    return False


def _travel(state: UniverseState, player_id: int, cmd: TravelTo, config: GameConfig) -> ReduceResult:
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
    detected = player.detected
    for nxt in hops:
        if turns < cost or _should_interrupt(state, player, nxt):
            break
        turns -= cost
        events.append(Warped(player_id, current, nxt, cost))
        entered[nxt] = current
        explored = explored | frozenset({nxt})
        detected, det_events = _detect_in_sector(
            state, detected, ship.sensor_rating, nxt, player_id, config)
        events.extend(det_events)
        current = nxt

    new_ship = replace(ship, sector_id=current)
    new_player = replace(player, turns_remaining=turns, explored_sectors=explored,
                         entered_from=entered, detected=detected)
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
    # Per-day, per-port attempt history drives the patience penalty + the `max_rejections`
    # close. Reset by the daily cron, so it reconstructs exactly under replay (WP13).
    attempts = player.haggle_attempts.get(port.id, 0)
    if attempts >= hg.max_rejections:
        # Negotiation is closed for the day — the port holds firm at the fair price.
        haggled = Haggled(player_id, port.id, cmd.commodity, HaggleStatus.EXHAUSTED.value, fair)
        return ReduceResult(events=(haggled,))

    result = resolve_haggle(
        fair, cmd.counter_price, line.mode, state.rng,
        insult_frac=hg.insult_frac, history_penalty=hg.history_penalty, recent_attempts=attempts,
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
    # A non-accepted offer wears the port's patience: bump the attempt counter.
    new_player = replace(player, haggle_attempts={**player.haggle_attempts, port.id: attempts + 1})
    return ReduceResult(events=(haggled,), players=(new_player,))


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


# --- discovery: descend / explore / salvage / log to codex (§7, WP5/WP6) ----


def _planet_in_sector(state: UniverseState, ship: Ship, planet_id: int) -> Planet:
    planet = state.planets.get(planet_id)
    if planet is None or planet.sector_id != ship.sector_id:
        raise EconomyError("no such planet in this sector")
    return planet


def _surface_sites(state: UniverseState, planet_id: int) -> list[Discovery]:
    """A planet's surface-site discoveries, in slot order (§7, WP6)."""
    sites = [d for d in state.discoveries.values() if d.planet_id == planet_id]
    return sorted(sites, key=lambda d: d.site_slot)


def _descend(
    state: UniverseState, player_id: int, cmd: Descend, config: GameConfig
) -> ReduceResult:
    """Land on a planet surface (§7, WP6). A turn cost that opens site exploration."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    _planet_in_sector(state, ship, cmd.planet_id)
    cost = config.discovery.descent_turn_cost if config.discovery is not None else 1
    if player.turns_remaining < cost:
        raise MovementError("out of turns")
    new_player = replace(player, turns_remaining=player.turns_remaining - cost)
    return ReduceResult(events=(Descended(player_id, cmd.planet_id),), players=(new_player,))


def _explore(
    state: UniverseState, player_id: int, cmd: Explore, config: GameConfig
) -> ReduceResult:
    """Reveal the next still-hidden surface site the ship's sensors can resolve (§7, WP6)."""
    player = _player(state, player_id)
    ship = _ship(state, player)
    _planet_in_sector(state, ship, cmd.planet_id)
    undetected = [d for d in _surface_sites(state, cmd.planet_id) if d.id not in player.detected]
    if not undetected:
        raise EconomyError("every site here is already surveyed")
    target = next(
        (d for d in undetected
         if is_detectable(d, ship.sensor_rating, in_nebula=False, config=config)),
        None,
    )
    if target is None:
        raise EconomyError("sensors too weak to resolve the remaining sites — upgrade and retry")
    cost = config.discovery.explore_turn_cost if config.discovery is not None else 1
    if player.turns_remaining < cost:
        raise MovementError("out of turns")
    new_player = replace(player, turns_remaining=player.turns_remaining - cost,
                         detected=player.detected | frozenset({target.id}))
    return ReduceResult(
        events=(SiteExplored(player_id, cmd.planet_id, target.id,
                             target.kind.value, target.rarity_tier.name),),
        players=(new_player,),
    )


def _salvage(
    state: UniverseState, player_id: int, cmd: Salvage, config: GameConfig
) -> ReduceResult:
    """Log a revealed discovery into the codex (§7, WP5/WP6).

    Open-space: a hidden find must already be in `detected` (sensed on entry).
    Surface site: must have been explored (also in `detected`). Either way the
    payload is taken aboard (component → hold, latinum → purse, artifact → barter
    store; lore is codex-only) and the find marked `found_by`.
    """
    player = _player(state, player_id)
    ship = _ship(state, player)
    disc = state.discoveries.get(cmd.discovery_id)
    if disc is None:
        raise EconomyError("no such discovery")
    if disc.sector_id != ship.sector_id:
        raise EconomyError("that discovery is not in this sector")
    if disc.found_by is not None:
        raise EconomyError("that discovery has already been collected")
    if disc.planet_id is not None:
        if disc.id not in player.detected:
            raise EconomyError("unexplored — survey the site first")
    elif disc.hidden and disc.id not in player.detected:
        raise EconomyError("undetected — re-enter the sector with stronger sensors")
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


# --- Genesis torpedoes: buy / deploy (§4.2, WP10) ---------------------------


def _buy_genesis(state: UniverseState, player_id: int, config: GameConfig) -> ReduceResult:
    """Buy one Genesis torpedo from the StarDock (§4.2, WP10)."""
    if config.genesis is None:
        raise EconomyError("genesis torpedoes are not sold in this universe")
    player = _player(state, player_id)
    ship = _ship(state, player)
    _stardock(state, ship)
    gen = config.genesis
    if player.latinum < gen.price:
        raise EconomyError("insufficient latinum for a genesis torpedo")
    new_devices = {**ship.devices, gen.device_id: ship.devices.get(gen.device_id, 0) + 1}
    new_ship = replace(ship, devices=new_devices)
    new_player = replace(player, latinum=player.latinum - gen.price)
    return ReduceResult(
        events=(DevicePurchased(player_id, gen.device_id, gen.price),),
        players=(new_player,), ships=(new_ship,),
    )


def _deploy_genesis(
    state: UniverseState, player_id: int, cmd: DeployGenesis, config: GameConfig
) -> ReduceResult:
    """Terraform an eligible unowned planet in the current sector (§4.2, WP10).

    Deterministic: the world is re-typed to the configured `result_type` and its
    yield/habitability re-rolled from config (no RNG), so the change replays exactly.
    """
    if config.genesis is None:
        raise EconomyError("genesis torpedoes are not sold in this universe")
    player = _player(state, player_id)
    ship = _ship(state, player)
    gen = config.genesis
    if ship.devices.get(gen.device_id, 0) < 1:
        raise EconomyError("no genesis torpedo aboard")
    planet = state.planets.get(cmd.planet_id)
    if planet is None or planet.sector_id != ship.sector_id:
        raise EconomyError("no such planet in this sector")
    if planet.owner.is_owned:
        raise EconomyError("that world is claimed — genesis only re-forms unclaimed worlds")
    if planet.planet_type not in gen.eligible_types:
        raise EconomyError(f"a {planet.planet_type} world cannot be re-formed by genesis")
    new_devices = dict(ship.devices)
    new_devices[gen.device_id] = new_devices[gen.device_id] - 1
    if new_devices[gen.device_id] == 0:
        del new_devices[gen.device_id]
    new_ship = replace(ship, devices=new_devices)
    new_planet = retype_planet(planet, gen.result_type, config)
    return ReduceResult(
        events=(GenesisDeployed(player_id, planet.id, gen.result_type),),
        ships=(new_ship,), planets=(new_planet,),
    )


# --- alien contact: hail / buy / barter (§6, §8, WP9) -----------------------


def _species_here(state: UniverseState, ship: Ship, species_id: int) -> AlienSpecies:
    """The species at the player's current sector, or raise if not in contact range."""
    species = state.species.get(species_id)
    if species is None or species.sector_id != ship.sector_id:
        raise EconomyError("no such species in this sector")
    return species


def _species_config(config: GameConfig, species: AlienSpecies) -> SpeciesConfig:
    if config.roster is None:
        raise EconomyError("no species roster configured")
    sc = config.roster.species_by_id(species.roster_id)
    if sc is None:
        raise EconomyError(f"species {species.roster_id!r} is not in the roster")
    return sc


def _advance_recency(player: Player, species_id: int, context: str,
                     new_ring: tuple[int, ...]) -> dict[tuple[int, str], tuple[int, ...]]:
    """A copy of the player's dialogue recency with one (species, context) slot updated."""
    recency = dict(player.dialogue_recency)
    recency[(species_id, context)] = new_ring
    return recency


def _met(player: Player, species_id: int) -> Mapping[int, float]:
    """Mark a species met (attitude entry exists) without changing the offset."""
    if species_id in player.species_attitudes:
        return player.species_attitudes
    return {**player.species_attitudes, species_id: 0.0}


def _subject_extra(state: UniverseState, subject_id: int | None) -> dict[str, str]:
    """The `{subject}` placeholder fill for an 'ask about X' line, or empty (§6.7, WP17)."""
    if subject_id is None:
        return {}
    subject = state.species.get(subject_id)
    return {"subject": subject.name} if subject is not None else {}


def _hail(state: UniverseState, player_id: int, cmd: Hail, config: GameConfig) -> ReduceResult:
    """Open contact — the greeting case of the general conversation path (WP17)."""
    return _converse(state, player_id, Converse(cmd.species_id, "greeting"), config)


def _converse(state: UniverseState, player_id: int, cmd: Converse,
              config: GameConfig) -> ReduceResult:
    """Speak a chosen peaceful dialogue context and advance its recency ring (§6.7, WP17).

    The single ring-advancing conversation path (`Hail` is `Converse(greeting)`). Guards:
    the context must be peaceful (combat / signature lines are Phase 3) and the species
    must be in the player's sector — a rejected context raises rather than silently
    no-ops, so neither the codec nor the menu can smuggle a Phase-3 line through.
    """
    player = _player(state, player_id)
    ship = _ship(state, player)
    species = _species_here(state, ship, cmd.species_id)
    sc = _species_config(config, species)
    if cmd.context not in dialogue.reachable_contexts(sc):
        # Non-peaceful (combat / sig.*) or a context the species can't reach (its params):
        # raise rather than silently no-op, so the codec/menu can't smuggle a line through.
        raise EconomyError(f"not something you can say here ({cmd.context})")
    assert config.roster is not None
    extra = _subject_extra(state, cmd.subject_id)
    ring = player.dialogue_recency.get((species.id, cmd.context), ())
    rng = dialogue.encounter_rng(state.game.seed, species.id, cmd.context, ring)
    _, new_ring = dialogue.speak(config.roster, species, player, cmd.context,
                                 aliens=config.aliens, rng=rng, extra=extra)
    new_player = replace(
        player, species_attitudes=_met(player, species.id),
        species_last_seen={**player.species_last_seen, species.id: ship.sector_id},
        dialogue_recency=_advance_recency(player, species.id, cmd.context, new_ring))
    event = AlienSpoke(player_id, species.id, cmd.context, cmd.subject_id)
    return ReduceResult(events=(event,), players=(new_player,))


def _select_offer(config: GameConfig, species: AlienSpecies, player: Player,
                  offer_index: int) -> TechOfferConfig:
    sc = _species_config(config, species)
    if not 0 <= offer_index < len(sc.tech_offers):
        raise EconomyError("no such tech offer")
    offer = sc.tech_offers[offer_index]
    if effective_disposition(species, player) < offer.min_disposition:
        raise EconomyError("they will not offer you that yet — raise your standing first")
    return offer


def _deliver_offer(ship: Ship, offer: TechOfferConfig) -> tuple[Ship, str]:
    """Apply a tech offer to the hull: a loose component or a flat aspect bump."""
    if offer.component is not None:
        if ship.holds_free < 1:
            raise EconomyError("no free hold for the component — sell cargo first")
        component, tier = Component(offer.component), ComponentTier[offer.tier]
        key = (component, tier)
        new_ship = replace(ship, components={**ship.components, key: ship.components.get(key, 0) + 1})
        return new_ship, f"{component.value} ({offer.tier})"
    if offer.aspect == "sensors":
        return replace(ship, sensor_rating=ship.sensor_rating + offer.amount), f"sensors +{offer.amount}"
    if offer.aspect == "cloak":
        return replace(ship, cloak_rating=ship.cloak_rating + offer.amount), f"cloak +{offer.amount}"
    if offer.aspect == "holds":
        return replace(ship, holds_total=ship.holds_total + offer.amount), f"holds +{offer.amount}"
    raise EconomyError(f"unsupported tech offer ({offer.aspect})")


def _raise_attitude(player: Player, species: AlienSpecies,
                    config: GameConfig) -> tuple[Player, AttitudeChanged]:
    """Raise the player's attitude offset toward `species` (capped so effective ≤ 1)."""
    sc = _species_config(config, species)
    cap = max(0.0, 1.0 - species.base_disposition)
    current = player.species_attitudes.get(species.id, 0.0)
    new_offset = min(cap, current + sc.attitude_gain_rate)
    attitudes = {**player.species_attitudes, species.id: new_offset}
    new_player = replace(player, species_attitudes=attitudes)
    effective = effective_disposition(species, new_player)
    return new_player, AttitudeChanged(player.id, species.id, round(new_offset, 6), round(effective, 6))


def _trade_alien(state: UniverseState, player_id: int, species_id: int, offer_index: int,
                 config: GameConfig, *, barter: bool) -> ReduceResult:
    player = _player(state, player_id)
    ship = _ship(state, player)
    species = _species_here(state, ship, species_id)
    assert config.roster is not None
    offer = _select_offer(config, species, player, offer_index)

    cost = 0
    if barter:
        if offer.mode != "barter":
            raise EconomyError("that offer is a latinum sale, not a barter")
        if player.artifacts.get(offer.tier, 0) < 1:
            raise EconomyError(f"you have no Tier-{offer.tier} artifact to barter")
    else:
        if offer.mode != "latinum":
            raise EconomyError("that offer is barter-only — trade an artifact for it")
        cost = offer.price
        if player.latinum < cost:
            raise EconomyError("insufficient latinum for that offer")

    new_ship, detail = _deliver_offer(ship, offer)
    new_player = player
    if barter:
        artifacts = dict(player.artifacts)
        artifacts[offer.tier] = artifacts[offer.tier] - 1
        if artifacts[offer.tier] == 0:
            del artifacts[offer.tier]
        new_player = replace(new_player, artifacts=artifacts)
    else:
        new_player = replace(new_player, latinum=new_player.latinum - cost)

    new_player, attitude_event = _raise_attitude(new_player, species, config)
    # Advance the trade dialogue ring so a repeat sale rephrases.
    ring = player.dialogue_recency.get((species.id, "trade_open"), ())
    rng = dialogue.encounter_rng(state.game.seed, species.id, "trade_open", ring)
    _, new_ring = dialogue.speak(config.roster, species, new_player, "trade_open",
                                 aliens=config.aliens, rng=rng)
    new_player = replace(new_player,
                         dialogue_recency=_advance_recency(new_player, species.id, "trade_open", new_ring))
    kind = "barter" if barter else "buy"
    return ReduceResult(
        events=(AlienTraded(player_id, species.id, kind, detail, cost), attitude_event),
        players=(new_player,), ships=(new_ship,),
    )


def _buy_alien_tech(state: UniverseState, player_id: int, cmd: BuyAlienTech,
                    config: GameConfig) -> ReduceResult:
    return _trade_alien(state, player_id, cmd.species_id, cmd.offer_index, config, barter=False)


def _barter_artifact(state: UniverseState, player_id: int, cmd: BarterArtifact,
                     config: GameConfig) -> ReduceResult:
    return _trade_alien(state, player_id, cmd.species_id, cmd.offer_index, config, barter=True)
