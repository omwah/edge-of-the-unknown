"""Turn rules for the ground-war POC — pure over (Battle, seeded rng).

IGOUGO: the player moves/fires every trooper, then `defense_phase` runs the whole
planetary response (detection, turret/citadel-gun fire, garrison AI, escalating
sorties, the clock). Only this module mutates `Battle`. The win axis is the
planetary *resolve* meter: demonstrated military damage drains it, atrocity
(civilian blocks) and dead troopers restore it; the planet capitulates at the
difficulty's threshold — if it happens before retrieval, casualties stay under
the ceiling, and anyone is left standing.
"""

from __future__ import annotations

import heapq
import math

from edge.groundwar.config import EmplacementStats, WeaponStats
from edge.groundwar.model import Battle, GarrisonUnit, Structure, Trooper

TROOPER_NAMES = (
    "Rico", "Zim", "Flores", "Levy", "Jelal", "Kitten", "Shujumi", "Brumby",
    "Rasczak", "Migliaccio", "Bronski", "Cunha", "Navarre", "Mahmud",
)

RESOLVE_CAP = 120.0
RUBBLE_COST = 2  # moving through a destroyed structure cell


# --- terrain & geometry ------------------------------------------------------


def move_cost(battle: Battle, x: int, y: int) -> int:
    """Entry cost of a cell on foot; 0 == impassable (live structure or hard terrain)."""
    s = battle.structure_at(x, y)
    if s is not None:
        return 0 if s.alive else RUBBLE_COST
    tc = battle.config.terrain.get(battle.feature[y][x])
    return tc.move_cost if tc else 1


def cover_at(battle: Battle, x: int, y: int) -> float:
    s = battle.structure_at(x, y)
    if s is not None:
        return 0.15 if not s.alive else 0.0  # rubble is decent cover
    tc = battle.config.terrain.get(battle.feature[y][x])
    return tc.cover if tc else 0.0


def occupied(battle: Battle, x: int, y: int) -> bool:
    return battle.trooper_at(x, y) is not None or battle.garrison_at(x, y) is not None


def dist(ax: int, ay: int, bx: int, by: int) -> float:
    return math.hypot(ax - bx, ay - by)


def line_of_sight(battle: Battle, ax: int, ay: int, bx: int, by: int) -> bool:
    """Bresenham; blocked by LOS-blocking terrain or a live structure between endpoints."""
    dx, dy = abs(bx - ax), abs(by - ay)
    sx, sy = (1 if ax < bx else -1), (1 if ay < by else -1)
    err = dx - dy
    x, y = ax, ay
    while True:
        if (x, y) != (ax, ay) and (x, y) != (bx, by):
            s = battle.structure_at(x, y)
            if s is not None and s.alive:
                return False
            tc = battle.config.terrain.get(battle.feature[y][x])
            if tc is not None and tc.blocks_los:
                return False
        if (x, y) == (bx, by):
            return True
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


def reachable(battle: Battle, trooper: Trooper) -> dict[tuple[int, int], int]:
    """Dijkstra over move costs within one move action's range; {} once spent."""
    if trooper.actions <= 0:
        return {}
    start = (trooper.x, trooper.y)
    best: dict[tuple[int, int], int] = {start: 0}
    heap: list[tuple[int, tuple[int, int]]] = [(0, start)]
    while heap:
        cost, (x, y) = heapq.heappop(heap)
        if cost > best.get((x, y), 1 << 30):
            continue
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not battle.in_bounds(nx, ny):
                continue
            step = move_cost(battle, nx, ny)
            if step <= 0 or occupied(battle, nx, ny):
                continue
            nc = cost + step
            if nc <= trooper.mp and nc < best.get((nx, ny), 1 << 30):
                best[(nx, ny)] = nc
                heapq.heappush(heap, (nc, (nx, ny)))
    del best[start]
    return best


# --- resolve -----------------------------------------------------------------


def _apply_resolve(battle: Battle, delta: float, why: str) -> None:
    """delta < 0 drains defender resolve (good for the player); > 0 hardens it."""
    battle.resolve = max(0.0, min(RESOLVE_CAP, battle.resolve + delta))
    arrow = "falls" if delta < 0 else "hardens"
    battle.log("resolve", f"Planetary resolve {arrow} {abs(delta):.0f} — {why} "
                          f"({battle.resolve:.0f} left)", friendly=delta < 0)
    if battle.resolve <= battle.surrender_threshold and battle.outcome is None:
        battle.outcome = "surrender"
        battle.log("outcome", "The planetary government sues for peace. SURRENDER.",
                   friendly=True)


def _escalation_bonus(battle: Battle) -> float:
    p = battle.config.pressure
    waves = (battle.turn - 1) // p.escalation_every
    return min(p.escalation_acc_cap, waves * p.escalation_acc_bonus)


def _check_cowed(battle: Battle, city_id: int) -> None:
    city = next(c for c in battle.cities if c.id == city_id)
    if not city.cowed_scored and battle.city_cowed(city):
        city.cowed_scored = True
        _apply_resolve(battle, -battle.config.resolve.city_cowed,
                       f"{city.name} lies silenced")


def _structure_destroyed(battle: Battle, s: Structure) -> None:
    r = battle.config.resolve
    drains = {
        "turret": r.turret_destroyed, "aa": r.aa_destroyed, "sensor": r.sensor_destroyed,
        "wall": r.wall_breached, "gate": r.wall_breached,
        "citadel_gun": r.citadel_gun_destroyed,
        "building_military": r.military_building_destroyed,
    }
    label = s.kind.replace("_", " ")
    battle.log("destroyed", f"{label} destroyed", s.x, s.y, friendly=True)
    if s.kind == "building_civilian":
        _apply_resolve(battle, r.civilian_building_destroyed,
                       "civilian block leveled — atrocity stiffens them")
    else:
        _apply_resolve(battle, -drains[s.kind], f"{label} destroyed")
    _check_cowed(battle, s.city_id)


# --- attacks -----------------------------------------------------------------


def _command_bonus(battle: Battle, trooper: Trooper) -> float:
    for ally in battle.live_troopers():
        if ally is not trooper and ally.suit.command_radius > 0 \
                and dist(ally.x, ally.y, trooper.x, trooper.y) <= ally.suit.command_radius:
            return ally.suit.command_acc_bonus
    return 0.0


def _trooper_hit(battle: Battle, trooper: Trooper, damage: int, source: str) -> None:
    dmg = max(1, damage - trooper.suit.armor)
    trooper.hp -= dmg
    battle.log("hit", f"{trooper.name} takes {dmg} from {source}"
                      f" ({max(0, trooper.hp)} hp)", trooper.x, trooper.y, friendly=False)
    if not trooper.alive:
        battle.log("killed", f"{trooper.name} is KIA.", trooper.x, trooper.y, friendly=False)
        _apply_resolve(battle, battle.config.resolve.trooper_killed,
                       f"{trooper.name} down — the defenders take heart")
        _check_casualties(battle)


def fire_at(
    battle: Battle, trooper: Trooper, tx: int, ty: int, *, missile: bool = False,
) -> bool:
    """Attack the cell (structure or garrison unit). Returns True if the action spent."""
    if trooper.actions <= 0 or battle.outcome is not None:
        return False
    weapon: WeaponStats = trooper.suit.missile if missile else trooper.suit.weapon
    if missile and trooper.missiles <= 0:
        battle.log("info", f"{trooper.name}: no missiles left.")
        return False
    if dist(trooper.x, trooper.y, tx, ty) > weapon.range:
        battle.log("info", f"{trooper.name}: target out of range.")
        return False
    if not line_of_sight(battle, trooper.x, trooper.y, tx, ty):
        battle.log("info", f"{trooper.name}: no line of sight.")
        return False
    target_s = battle.structure_at(tx, ty)
    target_g = battle.garrison_at(tx, ty)
    if (target_s is None or not target_s.alive) and target_g is None:
        battle.log("info", f"{trooper.name}: nothing to shoot there.")
        return False

    trooper.actions -= 1
    trooper.fired = True
    if missile:
        trooper.missiles -= 1
    acc = weapon.accuracy + _command_bonus(battle, trooper)
    if not trooper.detected:
        acc += battle.config.garrison.undetected_first_strike
    trooper.detected = True  # firing reveals you
    kind = "missile" if missile else "shot"
    if target_g is not None:
        acc -= cover_at(battle, tx, ty)
        if battle.rng.random() < acc:
            gcls = getattr(battle.config.garrison, target_g.kind)
            dmg = max(1, weapon.damage - gcls.armor)
            target_g.hp -= dmg
            battle.log(kind, f"{trooper.name} hits {target_g.kind} for {dmg}", tx, ty)
            if not target_g.alive:
                battle.log("destroyed", f"{target_g.kind} unit destroyed", tx, ty)
                _apply_resolve(battle, -battle.config.resolve.garrison_killed,
                               "garrison unit destroyed")
                _check_cowed(battle, target_g.city_id)
        else:
            battle.log("miss", f"{trooper.name} misses the {target_g.kind}", tx, ty)
    else:
        assert target_s is not None
        if battle.rng.random() < acc:
            dmg = round(weapon.damage * weapon.structure_mult)
            target_s.hp -= dmg
            battle.log(kind, f"{trooper.name} hits the {target_s.kind.replace('_', ' ')} "
                             f"for {dmg}", tx, ty)
            if not target_s.alive:
                _structure_destroyed(battle, target_s)
        else:
            battle.log("miss", f"{trooper.name}'s {kind} goes wide", tx, ty)
    return True


def broadcast_terms(battle: Battle, trooper: Trooper) -> bool:
    """A Command suit dictates terms over a cowed city — the big resolve strike."""
    if trooper.suit.broadcast_range <= 0 or trooper.actions <= 0 \
            or battle.outcome is not None:
        return False
    for city in battle.cities:
        if city.broadcast_done:
            continue
        if dist(trooper.x, trooper.y, city.cx, city.cy) > trooper.suit.broadcast_range:
            continue
        if not battle.city_cowed(city):
            battle.log("info", f"{city.name} still resists — silence its defenses first.")
            continue
        city.broadcast_done = True
        trooper.actions -= 1
        trooper.fired = True
        battle.log("broadcast", f"{trooper.name} broadcasts terms over {city.name}: "
                                f"\"We can do this to every city you have.\"",
                   city.cx, city.cy)
        _apply_resolve(battle, -battle.config.resolve.broadcast,
                       f"terms dictated over {city.name}")
        return True
    battle.log("info", f"{trooper.name}: no cowed city in broadcast range.")
    return False


# --- movement ----------------------------------------------------------------


def do_move(battle: Battle, trooper: Trooper, x: int, y: int) -> bool:
    """One action: walk anywhere within the suit's move range."""
    if battle.outcome is not None or trooper.actions <= 0:
        return False
    options = reachable(battle, trooper)
    cost = options.get((x, y))
    if cost is None:
        return False
    trooper.x, trooper.y = x, y
    trooper.actions -= 1
    return True


def _aa_reaction_acc(aa_cfg: EmplacementStats, distance: float,
                     escalation: float = 0.0) -> float:
    """AA hit chance against a drop/jump: base accuracy, plus a point-blank ramp
    that fades from full bonus at the muzzle to nothing at the edge of range,
    plus any escalation stiffening. Landing in the heart of the umbrella is deadly."""
    prox = 0.0
    if aa_cfg.range > 0:
        prox = aa_cfg.point_blank_bonus * (1.0 - min(1.0, distance / aa_cfg.range))
    return aa_cfg.accuracy + prox + escalation


def do_jump(battle: Battle, trooper: Trooper, x: int, y: int) -> bool:
    """One action: jump-jet hop — ignores terrain, draws AA reaction fire."""
    if battle.outcome is not None or trooper.actions <= 0 or trooper.jump_charges <= 0:
        return False
    if not battle.in_bounds(x, y) or dist(trooper.x, trooper.y, x, y) > trooper.suit.jump_range:
        return False
    if move_cost(battle, x, y) <= 0 or occupied(battle, x, y):
        return False
    trooper.actions -= 1
    trooper.jump_charges -= 1
    trooper.x, trooper.y = x, y
    battle.log("jump", f"{trooper.name} jumps — on the bounce!", x, y)
    aa_cfg = battle.config.defenses.aa
    for s in battle.structures.values():
        if s.kind != "aa" or not s.alive or trooper.hp <= 0:
            continue
        d = dist(s.x, s.y, x, y)
        if d <= aa_cfg.range:
            if battle.rng.random() < _aa_reaction_acc(aa_cfg, d, _escalation_bonus(battle)):
                _trooper_hit(battle, trooper, aa_cfg.damage, "AA fire mid-air")
            else:
                battle.log("miss", "AA fire bursts wide of the jump arc", x, y,
                           friendly=False)
    return True


# --- the drop ----------------------------------------------------------------


def resolve_drop(battle: Battle, drops: list[tuple[str, int, int]]) -> None:
    """Create the platoon at its landing cells and run AA fire on the way down."""
    aa_cfg = battle.config.defenses.aa
    for i, (suit_key, x, y) in enumerate(drops):
        suit = battle.config.suits[suit_key]
        t = Trooper(id=battle.next_id(), suit=suit,
                    name=f"{TROOPER_NAMES[i % len(TROOPER_NAMES)]}",
                    x=x, y=y, hp=suit.hp, missiles=suit.missiles,
                    jump_charges=suit.jump_charges)
        battle.troopers.append(t)
        battle.log("drop", f"{t.name} ({suit.label}) capsule down", x, y)
        for s in battle.structures.values():
            if s.kind != "aa" or not s.alive:
                continue
            d = dist(s.x, s.y, x, y)
            if d <= aa_cfg.range:
                if battle.rng.random() < _aa_reaction_acc(aa_cfg, d):
                    _trooper_hit(battle, t, aa_cfg.damage, "anti-drop fire")
                else:
                    battle.log("miss", f"flak brackets {t.name}'s capsule", x, y,
                               friendly=False)
    battle.dropped = True
    battle.initial_strength = len(battle.troopers)
    _check_casualties(battle)
    start_player_phase(battle)


# --- detection ---------------------------------------------------------------


def _sensor_jammed(battle: Battle, sensor: Structure) -> bool:
    return any(
        t.suit.jam_radius > 0 and dist(t.x, t.y, sensor.x, sensor.y) <= t.suit.jam_radius
        for t in battle.live_troopers()
    )


def update_detection(battle: Battle) -> None:
    sensors = [s for s in battle.structures.values() if s.kind == "sensor" and s.alive]
    for t in battle.live_troopers():
        seen = False
        for s in sensors:
            if _sensor_jammed(battle, s):
                continue
            if dist(s.x, s.y, t.x, t.y) <= battle.config.defenses.sensor.radius * t.suit.signature:
                seen = True
                break
        if not seen:
            for g in battle.garrison.values():
                gcls = getattr(battle.config.garrison, g.kind)
                if g.alive and dist(g.x, g.y, t.x, t.y) <= gcls.sight \
                        and line_of_sight(battle, g.x, g.y, t.x, t.y):
                    seen = True
                    break
        t.detected = seen or t.fired  # firing this turn keeps you lit


# --- defense phase (the planet's go) ------------------------------------------


def _emplacement_fire(battle: Battle) -> None:
    bonus = _escalation_bonus(battle)
    stats = {"turret": battle.config.defenses.turret,
             "citadel_gun": battle.config.defenses.citadel_gun}
    for s in battle.structures.values():
        if s.kind not in stats or not s.alive or battle.outcome is not None:
            continue
        w = stats[s.kind]
        targets = [t for t in battle.live_troopers()
                   if t.detected and dist(s.x, s.y, t.x, t.y) <= w.range
                   and line_of_sight(battle, s.x, s.y, t.x, t.y)]
        if not targets:
            continue
        target = min(targets, key=lambda t: dist(s.x, s.y, t.x, t.y))
        acc = w.accuracy + bonus - cover_at(battle, target.x, target.y)
        if battle.rng.random() < acc:
            _trooper_hit(battle, target, w.damage, s.kind.replace("_", " "))
        else:
            battle.log("miss", f"{s.kind.replace('_', ' ')} fire misses {target.name}",
                       target.x, target.y, friendly=False)


def _garrison_step(battle: Battle, g: GarrisonUnit) -> None:
    gcls = getattr(battle.config.garrison, g.kind)
    visible = [t for t in battle.live_troopers() if t.detected]
    if not visible:
        return
    target = min(visible, key=lambda t: dist(g.x, g.y, t.x, t.y))
    in_range = (dist(g.x, g.y, target.x, target.y) <= gcls.weapon.range
                and line_of_sight(battle, g.x, g.y, target.x, target.y))
    if in_range:
        acc = gcls.weapon.accuracy - cover_at(battle, target.x, target.y)
        if battle.rng.random() < acc:
            _trooper_hit(battle, target, gcls.weapon.damage, f"garrison {g.kind}")
        else:
            battle.log("miss", f"garrison {g.kind} misses {target.name}",
                       target.x, target.y, friendly=False)
        return
    # close the distance: greedy steps toward the target
    for _ in range(gcls.move):
        dx = (target.x > g.x) - (target.x < g.x)
        dy = (target.y > g.y) - (target.y < g.y)
        steps = [(g.x + dx, g.y + dy), (g.x + dx, g.y), (g.x, g.y + dy)]
        moved = False
        for nx, ny in steps:
            if battle.in_bounds(nx, ny) and move_cost(battle, nx, ny) > 0 \
                    and not occupied(battle, nx, ny):
                g.x, g.y = nx, ny
                moved = True
                break
        if not moved:
            break


def _spawn_sortie(battle: Battle) -> None:
    p = battle.config.pressure
    if battle.turn % p.escalation_every != 0:
        return
    wave = battle.turn // p.escalation_every
    size = battle.config.garrison.sortie_base + battle.config.garrison.sortie_growth * (wave - 1)
    for city in battle.cities:
        if battle.city_cowed(city):
            continue  # a silenced city sends no one
        n = max(1, round(size * battle.garrison_mult * (1.5 if city.is_citadel else 1.0)))
        gates = [s for s in battle.structures.values()
                 if s.city_id == city.id and s.kind == "gate"]
        spawn_from = gates or [s for s in battle.structures.values()
                               if s.city_id == city.id and s.kind == "wall"][:2]
        placed = 0
        for gate in spawn_from:
            for r in range(1, 5):
                for nx, ny in ((gate.x - r, gate.y), (gate.x + r, gate.y),
                               (gate.x, gate.y - r), (gate.x, gate.y + r)):
                    if placed >= n:
                        break
                    if battle.in_bounds(nx, ny) and move_cost(battle, nx, ny) > 0 \
                            and not occupied(battle, nx, ny):
                        kind = "armor" if wave >= battle.config.garrison.armor_from_wave \
                            and placed % 3 == 2 else "infantry"
                        gcls = getattr(battle.config.garrison, kind)
                        u = GarrisonUnit(id=battle.next_id(), kind=kind, x=nx, y=ny,
                                         hp=gcls.hp, hp_max=gcls.hp, city_id=city.id)
                        battle.garrison[u.id] = u
                        placed += 1
        if placed:
            battle.log("sortie", f"{city.name} sorties: {placed} unit(s) take the field",
                       city.cx, city.cy, friendly=False)


def _check_casualties(battle: Battle) -> None:
    if battle.outcome is not None or not battle.dropped:
        return
    dead = battle.casualties()
    if dead >= battle.initial_strength:
        battle.outcome = "wiped"
        battle.log("outcome", "The platoon is gone. Nobody made retrieval.", friendly=False)
    elif dead > battle.config.pressure.casualty_ceiling * battle.initial_strength:
        battle.outcome = "casualties"
        battle.log("outcome", "Casualties past doctrine ceiling — mission aborted, "
                              "survivors recalled to the boat.", friendly=False)


def start_player_phase(battle: Battle) -> None:
    for t in battle.live_troopers():
        t.mp = t.suit.move
        t.actions = battle.config.actions_per_turn
        t.fired = False
    update_detection(battle)


def defense_phase(battle: Battle) -> None:
    """The planet's whole turn; advances the clock and checks every outcome."""
    if battle.outcome is not None:
        return
    update_detection(battle)
    _emplacement_fire(battle)
    for g in sorted(battle.garrison.values(), key=lambda u: u.id):
        if g.alive and battle.outcome is None:
            _garrison_step(battle, g)
    if battle.outcome is None:
        _spawn_sortie(battle)
    if battle.outcome is None and battle.turn >= battle.config.pressure.retrieval_turns:
        battle.outcome = "retrieval"
        battle.log("outcome", "The retrieval boat lifts with the planet unbowed. "
                              "Mission failed.", friendly=False)
    battle.turn += 1
    if battle.outcome is None:
        left = battle.config.pressure.retrieval_turns - battle.turn + 1
        battle.log("info", f"— Turn {battle.turn} · retrieval in {left} —")
        start_player_phase(battle)
