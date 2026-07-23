"""Example bot: buys a platoon, drops on a hostile world, and fights it to a decision
(GW-WP13).

Demonstrates driving a tactical ground assault end to end through the public service
surface: hire recruits and buy suits/ordnance at a Stardock, find the nearest
droppable Assault-access world, land the platoon, then each round fire on anything in
range, broadcast surrender terms to a cowed city, or push toward the nearest city —
ending the round once every live trooper is out of actions. The operation's own
retrieval clock forces a decision (win/loss/timeout), so this driver never needs its
own stuck-detection the way the survey bot does. Run with:

    edge-bot --script edge/bot/scripts/assaulter.py --save /tmp/assault.db
"""

from __future__ import annotations

from edge.bot.runner import BotRunner
from edge.core.config import GameConfig
from edge.core.enums import PortClass
from edge.core.groundwar.access import Assault, ground_access
from edge.core.groundwar.assault import AssaultMap, assault_map_for, tactical_projection
from edge.core.groundwar.models import AssaultOperation
from edge.core.models import Planet, Ship, UniverseState
from edge.core.rules import (
    BeginAssault, BuySuits, CombatAction, Dock, EndGroundTurn, ExtractGroundOperation,
    GroundBroadcast, GroundDrop, GroundFire, GroundMove, HireRecruits, TravelTo, Warp,
)

_SQUAD_SIZE = 6


def _pick_planet(state: UniverseState, player_id: int, config: GameConfig) -> Planet | None:
    """A droppable Assault-access world in already-charted space (`TravelTo`-reachable)."""
    player = state.players[player_id]
    ship = state.ships[player.ship_id]
    known = player.explored_sectors | {ship.sector_id}
    candidates = []
    for planet in state.planets.values():
        if planet.sector_id not in known:
            continue
        access = ground_access(state, player, planet, config)
        if isinstance(access, Assault) and access.droppable:
            candidates.append(planet)
    return min(candidates, key=lambda p: p.id) if candidates else None


def _stardock_sector(state: UniverseState) -> int | None:
    return next(
        (p.sector_id for p in state.ports.values() if p.klass is PortClass.STARDOCK), None)


def _ensure_loadout(b: BotRunner, state: UniverseState, config: GameConfig) -> bool:
    """Buy one missing loadout ingredient per call. Returns True once ready to drop."""
    player = state.players[b.player_id]
    ship = state.ships[player.ship_id]
    if ship.suits and ship.recruits > 0:
        return True
    sector = _stardock_sector(state)
    if sector is None:
        b.stop()
        return False
    if ship.sector_id != sector:
        if not b.apply(TravelTo(to_sector=sector)):
            b.stop()
        return False
    if b.current_port() is None:
        b.apply(Dock())
        return False
    assert config.groundwar is not None
    if not ship.suits:
        suit_id = next(iter(config.groundwar.suits))
        if not b.apply(BuySuits(suit_id=suit_id, count=_SQUAD_SIZE)):
            b.stop()  # can't afford even one suit — nothing more this script can do
        return False
    if ship.recruits <= 0:
        if not b.apply(HireRecruits(count=_SQUAD_SIZE)):
            b.stop()
        return False
    return True


def _drop_cells(amap: AssaultMap, config: GameConfig, count: int) -> list[tuple[int, int]]:
    assert config.groundwar is not None
    lx, ly = amap.landing_x, amap.landing_y
    cells: list[tuple[int, int]] = []
    max_radius = max(amap.width, amap.height)
    for radius in range(max_radius):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if radius > 0 and abs(dx) != radius and abs(dy) != radius:
                    continue
                x, y = lx + dx, ly + dy
                if not (0 <= x < amap.width and 0 <= y < amap.height):
                    continue
                if (x, y) in amap.blocked:
                    continue
                tc = config.groundwar.terrain.get(amap.feature[y][x])
                if tc is not None and tc.move_cost <= 0:
                    continue
                if (x, y) not in cells:
                    cells.append((x, y))
                if len(cells) >= count:
                    return cells
    return cells


def _choose_drop(
    ship: Ship, amap: AssaultMap, config: GameConfig
) -> tuple[tuple[str, int, int], ...]:
    assert config.groundwar is not None
    ceiling = min(ship.recruits, config.groundwar.max_troopers)
    suit_ids: list[str] = []
    for suit_id, owned in ship.suits.items():
        for _ in range(owned):
            if len(suit_ids) >= ceiling:
                break
            suit_ids.append(suit_id)
        if len(suit_ids) >= ceiling:
            break
    if not suit_ids:
        return ()
    cells = _drop_cells(amap, config, len(suit_ids))
    n = min(len(suit_ids), len(cells))
    return tuple((suit_ids[i], *cells[i]) for i in range(n))


def _push_target(amap: AssaultMap, op: AssaultOperation, x: int, y: int) -> tuple[int, int]:
    open_cities = [c for c in amap.cities if c.id not in op.cowed_cities] or list(amap.cities)
    target = min(open_cities, key=lambda c: abs(c.cx - x) + abs(c.cy - y))
    return target.cx, target.cy


def setup(bot: BotRunner) -> None:
    @bot.each_turn
    def drive(b: BotRunner) -> None:
        # A hostile space encounter en route would otherwise risk the ship (and with it
        # every recruit/suit aboard, per `_escape_pod`) — break it off first, like explorer.py.
        if b.service.encounter_view(b.player_id) is not None:
            b.apply(CombatAction(action="flee"))
            return
        state = b.service.state
        config = b.service.config
        player = state.players[b.player_id]
        op = player.ground_operation

        if op is None:
            if not _ensure_loadout(b, state, config):
                return
            if b.game().turns < 1:
                b.stop()
                return
            planet = _pick_planet(state, b.player_id, config)
            if planet is None:
                # Nothing eligible charted yet — push into unexplored space.
                g = b.game()
                warps = g.sector.warps
                if not warps:
                    b.stop()
                    return
                target = next((w for w in warps if w.kind == "unexplored"), warps[0])
                if not b.apply(Warp(to_sector=target.sector_id)):
                    b.stop()
                return
            ship = state.ships[player.ship_id]
            if ship.sector_id != planet.sector_id:
                if not b.apply(TravelTo(to_sector=planet.sector_id)):
                    b.stop()
                return
            if not b.apply(BeginAssault(planet.id)):
                b.stop()
            return

        if not isinstance(op, AssaultOperation):
            b.stop()  # a survey op landed on this player — not this script's job
            return

        if op.outcome is not None:
            b.apply(ExtractGroundOperation(op.operation_id))
            return

        amap = assault_map_for(state, op, config)

        if not op.dropped:
            ship = state.ships[player.ship_id]
            placements = _choose_drop(ship, amap, config)
            if not placements:
                b.apply(ExtractGroundOperation(op.operation_id))
                return
            if not b.apply(GroundDrop(op.operation_id, placements)):
                b.apply(ExtractGroundOperation(op.operation_id))
            return

        for trooper in op.platoon:
            if trooper.hp <= 0 or trooper.actions <= 0:
                continue
            proj = tactical_projection(op, amap, config, actor_id=trooper.id)
            if proj.fireable:
                tx, ty = min(proj.fireable)
                b.apply(GroundFire(op.operation_id, trooper.id, tx, ty))
                return
            if proj.can_broadcast:
                b.apply(GroundBroadcast(op.operation_id, trooper.id))
                return
            if proj.reachable:
                tx, ty = _push_target(amap, op, trooper.x, trooper.y)
                cell = min(proj.reachable, key=lambda c: abs(c[0] - tx) + abs(c[1] - ty))
                b.apply(GroundMove(op.operation_id, *cell, actor_id=trooper.id))
                return
        b.apply(EndGroundTurn(op.operation_id))
