"""Goal-directed NPC movement policies (DESIGN §8/§10, WP42) — pure core.

Replaces the Phase-2 pure-random drift with per-species **movement policies**. Each is a
deterministic planner: given the *already legality-filtered* legal candidate sectors (the
cron applies `may_occupy`, H8), a policy picks the next sector, drawing from the passed
drift sub-RNG exactly once (so the command-stream draw discipline is preserved and a
`wander` species stays byte-identical with the old `rng.choice(legal)`).

Policies (`SpeciesConfig.movement_policy`):

- **wander** — uniform random (the default; unchanged behaviour).
- **patrol** — hug the home band: prefer candidates in the species' `home_band`.
- **trade_seek** — drift toward the nearest port (the trade lanes).
- **hunt** — pursue the nearest player the species holds a grudge against; else wander.
- **coward** — flee the nearest player (maximise distance).

Distance is a multi-source BFS over the runtime adjacency (stdlib, pure). Ties are broken
by the single RNG draw, so hunters converge and cowards diverge deterministically.
"""

from __future__ import annotations

import random
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from edge.core.config import GameConfig
from edge.core.economy import port_unit_price
from edge.core.enums import Commodity, PortMode
from edge.core.models import AlienSpecies, Port, UniverseState


def movement_policy(config: GameConfig, sp: AlienSpecies) -> str:
    """The species' authored movement policy (`wander` if none / no roster)."""
    if config.roster is None:
        return "wander"
    sc = config.roster.species_by_id(sp.roster_id)
    return sc.movement_policy if sc is not None else "wander"


def _bfs_from(adjacency: Mapping[int, Sequence[int]], sources: Sequence[int]) -> dict[int, int]:
    """Hop distance from the nearest `sources` node to every reachable sector (BFS)."""
    dist: dict[int, int] = {s: 0 for s in sources}
    queue: deque[int] = deque(sources)
    while queue:
        node = queue.popleft()
        for nxt in adjacency.get(node, ()):
            if nxt not in dist:
                dist[nxt] = dist[node] + 1
                queue.append(nxt)
    return dist


def _pick_by_distance(
    legal: list[int], dist: Mapping[int, int], rng: random.Random, *, maximize: bool
) -> int:
    """Pick the candidate nearest (or farthest, if `maximize`) a target set.

    Unreachable candidates are treated as infinitely far — deprioritised when seeking,
    preferred when fleeing. Ties break on the single RNG draw (so the stream stays in
    lockstep with `rng.choice(legal)`).
    """
    inf = len(dist) + 1
    scored = [(dist.get(n, inf), n) for n in legal]
    target = max(d for d, _ in scored) if maximize else min(d for d, _ in scored)
    pool = [n for d, n in scored if d == target]
    return rng.choice(pool)


def _player_sectors(state: UniverseState) -> list[int]:
    return sorted({state.ships[p.ship_id].sector_id
                   for p in state.players.values() if p.ship_id in state.ships})


def _port_sectors(state: UniverseState) -> list[int]:
    return sorted({p.sector_id for p in state.ports.values()})


def _grudge_targets(state: UniverseState, sp: AlienSpecies) -> list[int]:
    """The sectors of players the species holds an active grudge against (§6.5)."""
    targets: list[int] = []
    for player in state.players.values():
        if sp.roster_id in player.grudges and player.ship_id in state.ships:
            targets.append(state.ships[player.ship_id].sector_id)
    return sorted(set(targets))


def plan_move(
    state: UniverseState, sp: AlienSpecies, legal: list[int],
    config: GameConfig, rng: random.Random,
) -> int:
    """Choose the next sector for `sp` from `legal` per its policy (§8/§10, WP42).

    `legal` is already `may_occupy`-filtered and non-empty; exactly one RNG draw is made.
    """
    policy = movement_policy(config, sp)
    if policy == "wander":
        return rng.choice(legal)
    if policy == "patrol":
        preferred = [n for n in legal if state.sectors[n].distance_band == sp.home_band]
        return rng.choice(preferred or legal)
    if policy == "trade_seek":
        dist = _bfs_from(state.adjacency, _port_sectors(state))
        return _pick_by_distance(legal, dist, rng, maximize=False)
    if policy == "hunt":
        targets = _grudge_targets(state, sp)
        if not targets:
            return rng.choice(legal)  # nothing to hunt — drift
        dist = _bfs_from(state.adjacency, targets)
        return _pick_by_distance(legal, dist, rng, maximize=False)
    if policy == "coward":
        targets = _player_sectors(state)
        if not targets:
            return rng.choice(legal)
        dist = _bfs_from(state.adjacency, targets)
        return _pick_by_distance(legal, dist, rng, maximize=True)
    return rng.choice(legal)


# --- NPC traders (DESIGN §8, WP43) ------------------------------------------
#
# A friendly merchant species works the trade lanes for real: on the `trader_step`
# cron it buys cheap stock and sells its held goods through the very same §8 pricing
# the player trades against (`economy.port_unit_price`), so its purse (`cash`) and hold
# (`cargo`) turn over and the port's stock/price move in response. The planner is a pure,
# deterministic greedy — no RNG — so a ticked trading run reloads to the identical
# `state_hash` (the Phase-2 replay rail): given a trader in a port sector, it resolves
# **one** trade, mirroring a single player `Trade`. Goods are conserved with the port;
# latinum mints/burns against the port's soft figure exactly as in `economy.execute_trade`.


@dataclass(frozen=True, slots=True)
class NpcTrade:
    """One resolved NPC trade: the updated port + species and a record of what moved."""

    port: Port
    species: AlienSpecies
    commodity: Commodity
    mode: PortMode  # the port's mode for this commodity (SELL ⇒ trader bought; BUY ⇒ sold)
    units: int
    unit_price: int
    total: int


def is_trader(config: GameConfig, sp: AlienSpecies) -> bool:
    """Whether `sp` is a merchant that runs real trades (movement policy `trade_seek`, §8)."""
    return movement_policy(config, sp) == "trade_seek"


def _trader_holds(sp: AlienSpecies) -> int:
    return sum(sp.cargo.values())


def _with_line_stock(port: Port, commodity: Commodity, new_stock: int) -> Port:
    lines = tuple(
        replace(c, stock=new_stock) if c.commodity is commodity else c
        for c in port.commodities
    )
    return replace(port, commodities=lines)


def _resolve_sell(port: Port, sp: AlienSpecies, commodity: Commodity, units: int,
                  price: int, line_stock: int) -> NpcTrade:
    """Trader sells `units` of held cargo into the port (goods conserved; cash minted)."""
    cargo = dict(sp.cargo)
    remaining = cargo[commodity] - units
    if remaining > 0:
        cargo[commodity] = remaining
    else:
        del cargo[commodity]
    new_sp = replace(sp, cargo=cargo, cash=sp.cash + units * price)
    new_port = _with_line_stock(port, commodity, line_stock + units)
    return NpcTrade(new_port, new_sp, commodity, PortMode.BUY, units, price, units * price)


def _resolve_buy(port: Port, sp: AlienSpecies, commodity: Commodity, units: int,
                 price: int, line_stock: int) -> NpcTrade:
    """Trader buys `units` from the port into its hold (goods conserved; cash burned)."""
    cargo = dict(sp.cargo)
    cargo[commodity] = cargo.get(commodity, 0) + units
    new_sp = replace(sp, cargo=cargo, cash=sp.cash - units * price)
    new_port = _with_line_stock(port, commodity, line_stock - units)
    return NpcTrade(new_port, new_sp, commodity, PortMode.SELL, units, price, units * price)


def plan_trade(state: UniverseState, sp: AlienSpecies, config: GameConfig) -> NpcTrade | None:
    """Resolve one trade for merchant `sp` at its current sector's port, or None (§8, WP43).

    Deterministic greedy, no RNG: first realise value — dump the held stack that fetches
    the most latinum from a port BUY line; else buy the cheapest genuine deal (quoted price
    below `trader_buy_discount_frac × base`) it can afford and carry. Trade size is bounded
    by `trader_trade_units`, the trader's purse/hold, and the port's stock/capacity. Ties
    break on the stable `commodities` order, so a firing reproduces exactly under replay.
    """
    port = state.port_in_sector(sp.sector_id)
    if port is None:
        return None
    econ = config.economy
    ac = config.aliens

    # 1. Sell — dump held cargo the port buys, choosing the largest-latinum stack.
    sell_best: NpcTrade | None = None
    for line in port.commodities:
        if line.mode is not PortMode.BUY:
            continue
        held = sp.cargo.get(line.commodity, 0)
        room = line.capacity - line.stock
        units = min(held, room, ac.trader_trade_units)
        if units <= 0:
            continue
        price = port_unit_price(line, econ)
        if sell_best is None or units * price > sell_best.total:
            sell_best = _resolve_sell(port, sp, line.commodity, units, price, line.stock)
    if sell_best is not None:
        return sell_best

    # 2. Buy — the cheapest real deal the trader can afford and carry.
    buy_best: NpcTrade | None = None
    for line in port.commodities:
        if line.mode is not PortMode.SELL or line.stock <= 0:
            continue
        price = port_unit_price(line, econ)
        if price >= line.base * ac.trader_buy_discount_frac:
            continue  # not a good enough deal to bother
        affordable = sp.cash // price
        room = ac.trader_cargo_capacity - _trader_holds(sp)
        units = min(ac.trader_trade_units, line.stock, affordable, room)
        if units <= 0:
            continue
        if buy_best is None or price < buy_best.unit_price:
            buy_best = _resolve_buy(port, sp, line.commodity, units, price, line.stock)
    return buy_best
