"""Pure cron reducers run by the engine tick loop (DESIGN §9).

Each is a deterministic `(state, config) -> ReduceResult` — no RNG, no I/O — so
the engine layer mutates state only through the same reducer/event discipline as
player commands. Phase-1 crons: the daily turn reset, daily interest accrual, and
the hourly port-economy regen (re-exported from `port_economy`).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import replace

from edge.core import contracts, npc, territory
from edge.core.aliens import attitude_locked, decay_grudges, effective_disposition, may_occupy
from edge.core.discovery import entity_species
from edge.core.config import GameConfig
from edge.core.economy import accrue_interest as _accrue
from edge.core.enums import PortClass
from edge.core.events import (
    AlienDestroyed, AlienMoved, AttitudeChanged, Banked, CitadelCompleted, ColonyGrew,
    ContractFailed, Event, MarketSettled, PlanetProduced, PortOrderFilled, TurnsReset,
)
from edge.core.citadels import advance_build
from edge.core.governance import apply_intrigue, flip_core_governor, npc_seizure_ready
from edge.core.market import (
    clear_filled, desired_stock_frac, hinterland_drift, liquidity_drip, match_orders,
    orders_from_ports,
)
from edge.core.models import (
    AlienSpecies, Alliance, Planet, Player, Port, SectorForce, Starbase, UniverseState,
)
from edge.core.planets import produce
from edge.core.rules import ReduceResult
from edge.engine.port_economy import regenerate_ports

CronFn = Callable[[UniverseState, GameConfig], ReduceResult]

__all__ = [
    "daily_turn_reset", "accrue_interest", "regenerate_ports", "hourly_port_economy",
    "market_settlement", "governance_tick", "planet_growth", "alien_drift", "trader_step",
    "CronFn", "CRONS", "resolve_cron",
]


def hourly_port_economy(state: UniverseState, config: GameConfig) -> ReduceResult:
    """The hourly port-economy tick: order-book market, or the legacy regen (§8, WP47).

    With ``economy.market.enabled`` (the `config_version 4` default) each port's
    unseen hinterland trickles a little stock toward its pivot (`hinterland_drift`,
    a much gentler residual than the legacy 5%) and then the whole order book is
    reposted from the drifted stocks (`orders_from_ports`) — a total replacement, so
    the book stays bounded and reconstructs under replay. With the market disabled
    this is the **byte-identical** legacy `regenerate_ports` body (the durable cron
    name is unchanged so old saves resolve to the same reducer).
    """
    econ = config.economy
    if not econ.market.enabled:
        return regenerate_ports(state, config)
    new_ports = [
        replace(port, commodities=tuple(
            replace(line, stock=hinterland_drift(line, econ,
                                                 desired_frac=desired_stock_frac(port, econ)))
            for line in port.commodities
        ))
        for port in state.ports.values()
    ]
    book = orders_from_ports({p.id: p for p in new_ports}, econ)
    return ReduceResult(ports=tuple(new_ports), port_orders=book)


def market_settlement(state: UniverseState, config: GameConfig) -> ReduceResult:
    """The daily order-book settlement: match the book, move goods+latinum, drip purses (§8, WP47).

    Matches every crossed order (`match_orders`, conservation self-asserted), applies
    the resulting stock and purse deltas to the ports, tops each purse toward its
    liquidity floor (`liquidity_drip`), and clears filled orders from the book. Emits
    one fog-safe `MarketSettled` aggregate plus a `PortOrderFilled` for each side of
    each match at a port the player has explored (the `planet_growth` log discipline).
    Pure and RNG-free, so the ticked market reloads to the identical `state_hash`.
    """
    econ = config.economy
    if not econ.market.enabled or not state.port_orders:
        return ReduceResult()
    settlement = match_orders(state.port_orders, state.ports, econ)

    explored: set[int] = set()
    for player in state.players.values():
        explored |= player.explored_sectors
    events: list[Event] = []
    if settlement.fills:
        events.append(MarketSettled(
            matches=len(settlement.fills),
            volume=sum(f.qty for f in settlement.fills),
            slips=sum(f.total for f in settlement.fills),
        ))
    for fill in settlement.fills:
        buyer, seller = state.ports[fill.buyer_port_id], state.ports[fill.seller_port_id]
        if buyer.sector_id in explored:
            events.append(PortOrderFilled(buyer.id, fill.commodity, "buy",
                                          fill.qty, fill.unit_price, seller.id))
        if seller.sector_id in explored:
            events.append(PortOrderFilled(seller.id, fill.commodity, "sell",
                                          fill.qty, fill.unit_price, buyer.id))

    changed: list[Port] = []
    for pid, port in state.ports.items():
        stock_d = settlement.stock_deltas.get(pid, {})
        settled = replace(port, commodities=tuple(
            replace(line, stock=line.stock + stock_d.get(line.commodity, 0))
            for line in port.commodities
        ), latinum=port.latinum + settlement.latinum_deltas.get(pid, 0))
        settled = replace(settled, latinum=settled.latinum + liquidity_drip(settled, econ))
        if settled != port:
            changed.append(settled)

    residual = clear_filled(state.port_orders, settlement)
    return ReduceResult(events=tuple(events), ports=tuple(changed), port_orders=residual)


def governance_tick(state: UniverseState, config: GameConfig) -> ReduceResult:
    """NPC Core seizures + leadership intrigue on the daily clock (§6.3, WP51).

    A salted sub-RNG keyed by `(seed, governance_seq)` — never the shared command RNG —
    keeps every roll deterministic and reproducible under the maintenance replay (the
    `alien_drift` pattern, H11). Per eligible `covets_core` bloc it rolls `seizure_chance`
    to flip the Core (at most one flip per firing, `flip_core_governor` cause
    `npc_seizure`); per bloc with an `internal_rival_species_id` it rolls `intrigue_chance`
    to swap leadership (and, if `intrigue_turns_outward`, turn the bloc's live
    `Alliance.covets_core` on). One `ReduceResult` folds the whole firing; `species_arcs`,
    grudges, and standings are untouched — NPC upheavals are political, not personal.
    """
    gc = config.aliens.governance
    if not gc.enabled or config.roster is None:
        return ReduceResult()
    firing = state.game.governance_seq
    rng = random.Random(f"{state.game.seed}|governance|{firing}")
    events: list[Event] = []
    game = state.game
    planets: dict[int, Planet] = {}
    starbases: dict[int, Starbase] = {}
    species: dict[int, AlienSpecies] = {}
    alliances: dict[int, Alliance] = {}

    # 1. NPC Core seizure — at most one flip per firing (a flip re-keys the whole Core).
    for aid in sorted(a.id for a in config.roster.alliances):
        if not npc_seizure_ready(state, config, aid):
            continue
        if rng.random() < gc.seizure_chance:
            delta = flip_core_governor(state, config, aid, cause="npc_seizure")
            game = delta.game
            planets.update({p.id: p for p in delta.planets})
            starbases.update({b.id: b for b in delta.starbases})
            species.update({s.id: s for s in delta.species})
            events.extend(delta.events)
            break

    # 2. Leadership intrigue — an internal coup within each bloc that authored a rival.
    for ac in sorted(config.roster.alliances, key=lambda a: a.id):
        if ac.internal_rival_species_id is None:
            continue
        if rng.random() >= gc.intrigue_chance:
            continue
        intrigue = apply_intrigue(state, ac, species)
        if intrigue is None:
            continue
        species.update({s.id: s for s in intrigue.species})
        events.append(intrigue.event)
        if ac.intrigue_turns_outward and ac.id in state.alliances:
            base = alliances.get(ac.id, state.alliances[ac.id])
            if not base.covets_core:
                alliances[ac.id] = replace(base, covets_core=True)

    game = replace(game, governance_seq=firing + 1)
    return ReduceResult(
        events=tuple(events), game=game,
        planets=tuple(planets.values()), starbases=tuple(starbases.values()),
        species=tuple(species.values()), alliances=tuple(alliances.values()),
    )


def daily_turn_reset(state: UniverseState, config: GameConfig) -> ReduceResult:
    """Refill every player's turns and advance the game day (TWINSTR.DOC, §9).

    Also clears the per-day haggle-attempt counters (§8, WP13) so each port's patience
    is fresh at dawn, cools each player's finite grudges by the holder species'
    `attitude_gain_rate` (§6.5, WP27 — permanent vendettas never decay), and fails any
    favor past its deadline (§6.7, WP57 — an escort thereby releases its merchant back to
    the drift rails); like turns, all of it rides the daily cron through the replay timeline.
    """
    gain_rates = (
        {sp.id: sp.attitude_gain_rate for sp in config.roster.species}
        if config.roster is not None else {}
    )
    day = state.game.day_number + 1
    # An engaged interdictor levies a per-day turn tax (§14, WP56) — the day opens with
    # fewer turns, so running it is a stance, not a free default.
    interdictor = config.devices.get("interdictor")
    tax = interdictor.turn_tax if interdictor is not None else 0

    def _reset_turns(p: Player) -> int:
        ship = state.ships.get(p.ship_id)
        if ship is not None and ship.interdictor_active and tax:
            return max(0, config.turns_per_day - tax)
        return config.turns_per_day

    players: list[Player] = []
    events: list[Event] = []
    for p in state.players.values():
        reset = decay_grudges(
            replace(p, turns_remaining=_reset_turns(p), haggle_attempts={}),
            gain_rates, config.aliens, day,
        )
        # Deadlines are checked against the *new* day (a job due on day D lapses on D+1).
        reset, lapsed = contracts.expire_deadlines(reset, day)
        players.append(reset)
        events.append(TurnsReset(player_id=reset.id, turns=reset.turns_remaining))
        events.extend(ContractFailed(reset.id, c.id, c.kind, "deadline") for c in lapsed)
    game = replace(state.game, day_number=day)
    return ReduceResult(events=tuple(events), players=tuple(players), game=game)


def planet_growth(state: UniverseState, config: GameConfig) -> ReduceResult:
    """Run BNT production for every owned planet (§4.2, §8).

    Pure and deterministic. Only the player's own colonies announce output (so the
    log isn't flooded by every alliance holding); alliance worlds evolve silently —
    their stores still update, just without an event.
    """
    changed = []
    events: list[Event] = []
    for planet in state.planets.values():
        produced = produce(planet, config)
        # Advance any open citadel build on the same tick — colonist-days accrue toward
        # completion in proportion to the (already-produced) colony size (§4.2, WP54).
        built, completed = advance_build(produced, config)
        if built is planet:
            continue  # neither production nor a build changed anything
        changed.append(built)
        if completed:
            events.append(CitadelCompleted(built.id, built.citadel_level))
        if planet.owner.kind == "player" and planet.owner.ref is not None:
            events.append(PlanetProduced(planet.id, planet.owner.ref))
            if built.colonists != planet.colonists:
                events.append(ColonyGrew(planet.id, built.colonists))
    return ReduceResult(events=tuple(events), planets=tuple(changed))


def _pinned_species(state: UniverseState) -> frozenset[int]:
    """Species staged at the StarDock — the hub's standing welcome; they don't wander (§6.3)."""
    dock = next((p for p in state.ports.values() if p.klass is PortClass.STARDOCK), None)
    if dock is None:
        return frozenset()
    return frozenset(s.id for s in state.species.values() if s.sector_id == dock.sector_id)


def alien_drift(state: UniverseState, config: GameConfig) -> ReduceResult:
    """Drift each species to a legal adjacent sector on the tick clock (§6.3, WP16).

    A per-firing **sub-RNG** salted from `(seed, drift_seq)` keeps movement deterministic
    and reproducible under replay without ever drawing from the shared command-stream
    `state.rng`. `drift_seq` (a counter on `Game`) advances each firing, so live and
    reloaded runs seed identically. Territory is gated by `may_occupy` (no Core, no rival
    bloc); StarDock contacts are pinned. Non-Entity species pick their destination by their
    **movement policy** (`core.npc.plan_move`, WP42 — one RNG draw, so `wander` stays
    byte-identical); the Entity roams by its own rules (§7, WP36). `AlienMoved` is emitted
    only for a move that touches a player's current sector, so the log isn't flooded.
    """
    aliens = config.aliens
    if not aliens.drift_enabled or not state.species:
        return ReduceResult()
    firing = state.game.drift_seq
    rng = random.Random(f"{state.game.seed}|alien_drift|{firing}")
    pinned = _pinned_species(state)
    entity = entity_species(state, config)  # the roaming Entity drifts by its own rules (§7, WP36)
    entity_id = entity.id if entity is not None else None
    player_sectors = {state.ships[p.ship_id].sector_id for p in state.players.values()}
    # Interdicted sectors pin their occupants (§14, WP56): while a player's interdictor is
    # engaged in a sector, no NPC may drift *out* of it.
    interdicted = {state.ships[p.ship_id].sector_id for p in state.players.values()
                   if state.ships[p.ship_id].interdictor_active}
    moved: list[AlienSpecies] = []
    removed_ids: list[int] = []
    events: list[Event] = []
    # Territory depletion accrued this firing, so several entrants into one defended sector
    # deplete its mines/fighters in turn (§10, WP-PR02). Read here, applied at the end.
    force_overrides: dict[int, SectorForce] = {}
    for sp in sorted(state.species.values(), key=lambda s: s.id):
        if sp.id in pinned:
            continue
        if contracts.is_convoyed(state, sp.id):
            continue  # under player escort — moves with the convoy, not the drift rail (WP57)
        if sp.sector_id in interdicted:
            continue  # pinned by an active interdictor
        is_entity = sp.id == entity_id
        if rng.random() >= (aliens.entity_drift_chance if is_entity else aliens.drift_move_chance):
            continue
        # The Entity roams anywhere non-Core (unbound by the alliance/rival occupancy rules);
        # every other species is gated by `may_occupy`.
        legal = [n for n in sorted(state.adjacency.get(sp.sector_id, ()))
                 if (not state.sectors[n].is_galactic_core if is_entity
                     else may_occupy(state, sp, n, aliens))]
        if not legal:
            continue
        # The Entity keeps its own wander; every other species drifts by its policy (WP42).
        dst = rng.choice(legal) if is_entity else npc.plan_move(state, sp, legal, config, rng)
        touches = sp.sector_id in player_sectors or dst in player_sectors
        # Sector-entry defenses fire on the drifting NPC exactly as on a player warp (§10,
        # WP-PR02): resolve entry first, then move or destroy based on survival. The Entity is
        # a shipless contact and never triggers territory.
        entry = (territory.NpcEntry(False, None, "") if is_entity
                 else territory.resolve_npc_entry(
                     state, sp, force_overrides.get(dst, state.sector_forces.get(dst)), config))
        if entry.force is not None:
            force_overrides[dst] = entry.force
        if entry.destroyed:
            removed_ids.append(sp.id)  # a downed NPC never reaches the destination
            if touches:
                events.append(AlienDestroyed(sp.id, dst, entry.cause))
            continue
        moved.append(replace(sp, sector_id=dst))
        if touches:
            events.append(AlienMoved(sp.id, sp.sector_id, dst))
    game = replace(state.game, drift_seq=firing + 1)
    return ReduceResult(
        events=tuple(events), species=tuple(moved), removed_species_ids=tuple(removed_ids),
        sector_forces=tuple(force_overrides.values()), game=game)


def _trader_rapport(player: Player, species: AlienSpecies,
                    config: GameConfig) -> tuple[Player, AttitudeChanged | None]:
    """Warm a player toward a merchant it shares a market with (§8, WP43) — pure.

    Trading alongside a working merchant builds standing: the player's attitude offset
    toward the species kind ticks up by `trader_alongside_attitude`, capped so effective
    disposition never exceeds 1. A permanent grudge (§6.5) locks the offset — amends do
    not move it. This is the cron-side light touch (no reputation spillover, unlike the
    §6.4 trade/favour path); returns the player unchanged (event None) when nothing moves.
    """
    roster_id = species.roster_id
    if attitude_locked(player, roster_id):
        return player, None
    cap = max(0.0, 1.0 - species.base_disposition)
    current = player.species_attitudes.get(roster_id, 0.0)
    new_offset = min(cap, current + config.aliens.trader_alongside_attitude)
    if new_offset <= current:
        return player, None
    new_offset = round(new_offset, 6)
    updated = replace(player,
                      species_attitudes={**player.species_attitudes, roster_id: new_offset})
    event = AttitudeChanged(player.id, species.id, new_offset,
                            round(effective_disposition(species, updated), 6))
    return updated, event


def trader_step(state: UniverseState, config: GameConfig) -> ReduceResult:
    """Run one trade for every NPC merchant working a port this firing (§8, WP43).

    Friendly merchant species (movement policy `trade_seek`, `core.npc.is_trader`) hold a
    persistent purse + hold on their `AlienSpecies` row. Each firing, a merchant sitting in
    a port sector executes one deterministic trade (`core.npc.plan_trade`) through the §8
    pricing — goods conserved with the port, prices feeding back — so stock and standing
    move without the player. A fresh trader (empty hold, no purse — its generated state) is
    seeded to `aliens.trader_start_cash` first; that state is unreachable again once it
    trades, so the seed fires exactly once. Any player sharing the market warms toward the
    merchant (`_trader_rapport`). Pure and RNG-free, so a ticked run reloads to the identical
    `state_hash` (the WP12 replay rail).
    """
    ac = config.aliens
    if not state.species:
        return ReduceResult()
    species_out: list[AlienSpecies] = []
    ports_out: list[Port] = []
    players: dict[int, Player] = {}
    events: list[Event] = []
    for sp in sorted(state.species.values(), key=lambda s: s.id):
        if not npc.is_trader(config, sp) or state.port_in_sector(sp.sector_id) is None:
            continue  # only a merchant actually at a market trades this firing
        if contracts.is_convoyed(state, sp.id):
            continue  # under player escort — off the trade rail until delivered (WP57)
        seeded = replace(sp, cash=ac.trader_start_cash) if sp.cash == 0 and not sp.cargo else sp
        trade = npc.plan_trade(state, seeded, config)
        if trade is None:
            if seeded is not sp:  # seeded a fresh trader with no deal on offer yet
                species_out.append(seeded)
            continue
        species_out.append(trade.species)
        ports_out.append(trade.port)
        # Players sharing this market warm toward the merchant — trading alongside it (§8).
        for player in state.players.values():
            ship = state.ships.get(player.ship_id)
            if ship is None or ship.sector_id != sp.sector_id:
                continue
            updated, event = _trader_rapport(players.get(player.id, player), sp, config)
            if event is not None:
                players[player.id] = updated
                events.append(event)
    return ReduceResult(events=tuple(events), species=tuple(species_out),
                        ports=tuple(ports_out), players=tuple(players.values()))


def accrue_interest(state: UniverseState, config: GameConfig) -> ReduceResult:
    """Compound interest on every non-empty bank balance (§8)."""
    rate = config.economy.bank_interest_per_day
    players = []
    events = []
    for p in state.players.values():
        if p.bank_balance <= 0:
            continue
        new_balance = _accrue(p.bank_balance, rate)
        if new_balance == p.bank_balance:
            continue
        players.append(replace(p, bank_balance=new_balance))
        events.append(Banked(p.id, "interest", new_balance - p.bank_balance, new_balance))
    return ReduceResult(events=tuple(events), players=tuple(players))


# The canonical cron name → pure reducer registry (WP12). The ticker schedules
# these by name and persists each firing as a `MaintenanceTick`; replay (rebuild)
# resolves the name back to the reducer through `resolve_cron`, re-running it in
# the merged command+maintenance order. Names are durable — keep them stable.
CRONS: dict[str, CronFn] = {
    "hourly_port_economy": hourly_port_economy,
    "hourly_planet_growth": planet_growth,
    "market_settlement": market_settlement,
    "governance_tick": governance_tick,
    "alien_drift": alien_drift,
    "trader_step": trader_step,
    "interest_accrual": accrue_interest,
    "daily_turn_reset": daily_turn_reset,
}


def resolve_cron(name: str) -> CronFn:
    """The pure reducer for a persisted cron name (raises on an unknown name)."""
    try:
        return CRONS[name]
    except KeyError as exc:
        raise ValueError(f"unknown cron {name!r}") from exc
