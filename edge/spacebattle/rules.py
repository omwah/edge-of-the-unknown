"""All state mutation for the space-battle POC lives here (the UI only reads).

Turn shape (IGOUGO): `begin_turn(side)` refreshes actions and sensor reveals;
the side spends per-piece actions (ships: thrust / rotate / fire / salvo /
launch / recover / mine — wings: move / attack / intercept); `end_turn(side)`
then applies physics for that side: ships drift by their velocity (sweeping
mines), the side's missile salvos chase their targets, and wings burn fuel.

Facing-keyed damage: which aspect a hit strikes is the bearing from the target
to the shooter relative to the target's facing — dead ahead is a fore *rake*
(bonus damage), dead astern an aft rake, everything else the flanks. Screens
ablate per quadrant; once a quadrant's screen is gone, hull damage may knock
out a component homed in that quadrant (gun, drive, launchers, sensors).
"""

from __future__ import annotations

import math
from random import Random

from edge.spacebattle.config import Quadrant, ShipClass, SpacebattleConfig
from edge.spacebattle.model import (
    DIRS, FACING_NAMES, Battle, Debris, FighterWing, Mine, Rock, Salvo, Ship, Side,
)

PLAYER_NAMES = ("EDS Resolute", "EDS Farlight", "EDS Kestrel", "EDS Vagrant")
ENEMY_NAMES = ("Red Talon", "Void Reaver", "Black Sun", "Iron Wake")

# --- geometry ---------------------------------------------------------------


def dist(x1: int, y1: int, x2: int, y2: int) -> int:
    return max(abs(x1 - x2), abs(y1 - y2))


def octant(dx: int, dy: int) -> int:
    """Nearest facing octant for a board vector (y grows downward)."""
    if dx == 0 and dy == 0:
        return 0
    ang = math.atan2(-dy, dx)  # flip y so octants run counterclockwise on screen
    return round(ang / (math.pi / 4)) % 8


def cardinal(dx: int, dy: int) -> int:
    """Nearest cardinal facing (0 E, 2 N, 4 W, 6 S) for a board vector — ships
    face the four cardinals only; bearings stay full octants."""
    if dx == 0 and dy == 0:
        return 0
    ang = math.atan2(-dy, dx)
    return (round(ang / (math.pi / 2)) % 4) * 2


def _octant_diff(a: int, b: int) -> int:
    d = (a - b) % 8
    return min(d, 8 - d)


def salvo_arc_ok(ship: Ship, tx: int, ty: int) -> bool:
    """Launchers are flank components: salvos launch at targets abeam or on the
    quarter (octant diff 2–3 off the bow) — never through the forward wedge or
    dead astern. Guns want the nose on; missiles want the beam on. A starbase's
    launchers are ring mounts: every direction is abeam."""
    if ship.cls.station:
        return True
    diff = _octant_diff(octant(tx - ship.x, ty - ship.y), ship.facing)
    return diff in (2, 3)


def arc_ok(ship: Ship, tx: int, ty: int) -> bool:
    """Is the cell inside the ship's main-gun firing arc at its current facing?"""
    arc = ship.cls.main_gun.arc
    if arc == "all_round":
        return True
    diff = _octant_diff(octant(tx - ship.x, ty - ship.y), ship.facing)
    return diff == 0 if arc == "spinal" else diff <= 1


def los_blocked(b: Battle, x1: int, y1: int, x2: int, y2: int) -> bool:
    """Does rock or wreckage sit on the fire line between two cells (exclusive)?
    Walks the same diagonal-first step path salvos and drift use."""
    x, y = x1, y1
    while (x, y) != (x2, y2):
        x += 0 if x == x2 else (1 if x2 > x else -1)
        y += 0 if y == y2 else (1 if y2 > y else -1)
        if (x, y) != (x2, y2) and ((x, y) in b.rocks or (x, y) in b.debris):
            return True
    return False


def station_integrity(ship: Ship) -> float:
    """Fraction of a station's components still online — the spacebattle
    projection of `edge.core.starbases.component_integrity` (§4.2): a base's
    defense strength scales with its surviving components."""
    total = sum(len(comps) for comps in ship.cls.components.values())
    if total == 0:
        return 1.0
    return max(0.0, 1.0 - len(ship.down) / total)


def quadrant_struck(target: Ship, fx: int, fy: int, rng: Random) -> Quadrant:
    """Aspect a shot from (fx, fy) strikes: dead ahead/astern rakes, else flanks."""
    if (fx, fy) == (target.x, target.y):  # a mine under the keel — anyone's guess
        return rng.choice(("fore", "aft", "port", "starboard"))
    rel = (octant(fx - target.x, fy - target.y) - target.facing) % 8
    if rel == 0:
        return "fore"
    if rel == 4:
        return "aft"
    return "port" if rel < 4 else "starboard"  # octants run CCW; facing E puts N to port


# --- damage -----------------------------------------------------------------


def apply_damage(b: Battle, target: Ship, dmg: int, quad: Quadrant, label: str,
                 attacker: tuple[int, int] | None = None) -> None:
    """Screens ablate first; leak-through shaves hull and may knock out a
    component. Fore/aft hits rake; an aft rake against a ship fleeing directly
    away from the shooter is a *kilt* shot and rakes harder still."""
    if quad in ("fore", "aft"):
        mult = b.config.combat.raking_bonus
        if quad == "aft" and attacker is not None and target.speed > 0 \
                and b.config.combat.kilt_bonus > mult:
            away_x, away_y = target.x - attacker[0], target.y - attacker[1]
            if target.vx * away_x + target.vy * away_y > 0:
                mult = b.config.combat.kilt_bonus
                b.log("hit", f"{label} goes straight up {target.name}'s kilt!",
                      target.x, target.y, friendly=target.side == "enemy")
        dmg = int(dmg * mult)
    absorbed = min(target.screens.get(quad, 0), dmg)
    if absorbed:
        target.screens[quad] = target.screens[quad] - absorbed
    through = dmg - absorbed
    friendly = target.side == "enemy"
    b.log("hit", f"{label} strikes {target.name}'s {quad}: "
                 f"{absorbed} screened, {through} to hull.",
          target.x, target.y, friendly=friendly)
    if through <= 0:
        return
    target.hull -= through
    target.hull_hit = True  # sidewall generators can't regen while the hull rings
    if target.hull <= 0:
        b.log("destroyed", f"{target.name} BREAKS UP.", target.x, target.y,
              friendly=friendly)
        _check_outcome(b)
        return
    if b.rng.random() < b.config.combat.knockout_chance:
        candidates = [c for c in target.cls.components.get(quad, ())
                      if c not in target.down]
        if candidates:
            comp = b.rng.choice(candidates)
            target.down.add(comp)
            b.log("knockout", f"{target.name}: {comp.replace('_', ' ')} knocked out "
                              f"({quad} hit).", target.x, target.y, friendly=friendly)
            if comp == "fusion_reactor":
                # The §4.2 emergent-derelict rule: the reactor keystone is out,
                # the base can no longer power itself — it is disabled, not razed.
                b.log("destroyed", f"REACTOR SCRAM — {target.name} goes dark!",
                      target.x, target.y, friendly=friendly)
                _check_outcome(b)


def _check_outcome(b: Battle) -> None:
    if b.outcome is not None:
        return
    # Siege objective first: a starbase falls when razed OR when its reactor
    # keystone is knocked out (the main game's §4.2 disable rule) — and with the
    # base gone, the surviving picket doesn't fight on.
    stations = [s for s in b.ships if s.side == "enemy" and s.cls.station]
    if stations and all(not s.alive or not s.reactor_ok for s in stations):
        b.outcome = "victory"
        if any(s.alive for s in stations):
            b.log("outcome", "The starbase is dark — boarding parties take the "
                             "ring, and the picket scatters. The base is YOURS.")
        else:
            b.log("outcome", "The starbase is razed to drifting slag — nothing "
                             "left to claim, but the sector is yours.")
        return
    if not b.fleet("enemy"):
        b.outcome = "victory"
        b.log("outcome", "Enemy fleet destroyed — the sector is yours.")
    elif not b.fleet("player"):
        b.outcome = "defeat"
        b.log("outcome", "Your fleet is gone.", friendly=False)


# --- ship actions -----------------------------------------------------------


def do_thrust(b: Battle, ship: Ship, tx: int, ty: int) -> bool:
    """Bend velocity toward the cell (one action). Includes one free 45° of
    facing toward the burn — further rotation is its own action."""
    if ship.turn_taken:
        return False
    if ship.cls.station:
        b.log("info", f"{ship.name} is a station — it holds its orbit.")
        return False
    dx, dy = tx - ship.x, ty - ship.y
    if dx == 0 and dy == 0:  # burn to a stop instead
        want_vx = want_vy = 0
    else:
        m = ship.max_speed
        want_vx = max(-m, min(m, dx))
        want_vy = max(-m, min(m, dy))
    t = ship.thrust_rating
    dvx = max(-t, min(t, want_vx - ship.vx))
    dvy = max(-t, min(t, want_vy - ship.vy))
    if dvx == 0 and dvy == 0:
        b.log("info", f"{ship.name}: already on that vector.")
        return False
    ship.vx += dvx
    ship.vy += dvy
    if dx or dy:  # the free 90° nudge toward the burn direction
        want = cardinal(dx, dy)
        if ship.facing != want:
            step = 2 if (want - ship.facing) % 8 <= 4 else -2
            ship.facing = (ship.facing + step) % 8
    ship.actions -= 1
    b.log("thrust", f"{ship.name} burns to vector ({ship.vx:+d},{ship.vy:+d}), "
                    f"facing {FACING_NAMES[ship.facing]}.", ship.x, ship.y)
    return True


def do_rotate(b: Battle, ship: Ship, facing: int) -> bool:
    """Come about to any cardinal facing (one action)."""
    facing = (facing % 8) & ~1  # snap odd octants down to a cardinal
    if ship.turn_taken or facing == ship.facing:
        return False
    if ship.cls.station:
        b.log("info", f"{ship.name} is a station — it does not come about.")
        return False
    ship.facing = facing
    ship.actions -= 1
    b.log("thrust", f"{ship.name} comes about to {FACING_NAMES[ship.facing]}.",
          ship.x, ship.y)
    return True


def fire_gun(b: Battle, ship: Ship, tx: int, ty: int) -> bool:
    if ship.turn_taken:
        return False
    if not ship.gun_ok:
        b.log("info", f"{ship.name}: main gun is knocked out.")
        return False
    gun = ship.cls.main_gun
    d = dist(ship.x, ship.y, tx, ty)
    if d > gun.range:
        b.log("info", f"{ship.name}: out of gun range ({d} > {gun.range}).")
        return False
    if not arc_ok(ship, tx, ty):
        b.log("info", f"{ship.name}: target outside the {gun.arc} arc — come about.")
        return False
    if los_blocked(b, ship.x, ship.y, tx, ty):
        b.log("info", f"{ship.name}: debris blocks the firing line.")
        return False
    target = b.ship_at(tx, ty)
    wing = b.wing_at(tx, ty) if target is None else None
    if target is None and wing is None:
        b.log("info", "Nothing at that cell to shoot.")
        return False
    ship.actions -= 1
    friendly = ship.side == "player"
    dmg = gun.damage
    if ship.cls.station:
        # A battered base hits softer — damage scales with surviving components,
        # after `edge.core.starbases.assault_foe` (0.5 + 0.5 × integrity).
        dmg = max(1, round(dmg * (0.5 + 0.5 * station_integrity(ship))))
    if target is not None:
        acc = gun.accuracy - gun.falloff * d \
            - b.config.combat.velocity_evasion * target.speed
        if b.rng.random() < max(0.05, acc):
            apply_damage(b, target, dmg,
                         quadrant_struck(target, ship.x, ship.y, b.rng),
                         f"{ship.name}'s main gun", attacker=(ship.x, ship.y))
        else:
            b.log("miss", f"{ship.name}'s main gun misses {target.name}.",
                  tx, ty, friendly=friendly)
    elif wing is not None:
        if b.rng.random() < max(0.05, gun.accuracy - gun.falloff * d - 0.2):
            lost = min(wing.strength, 1 + dmg // 8)
            wing.strength -= lost
            b.log("hit", f"{ship.name}'s main gun rips through the fighter wing "
                         f"(-{lost} craft).", tx, ty, friendly=friendly)
        else:
            b.log("miss", f"{ship.name}'s main gun misses the fighters.",
                  tx, ty, friendly=friendly)
    return True


def launch_salvo(b: Battle, ship: Ship, target: Ship) -> bool:
    cost = b.config.combat.salvo_action_cost
    if ship.turn_taken:
        return False
    if ship.actions < cost:
        b.log("info", f"{ship.name}: a launch takes the whole turn "
                      f"({cost} actions).")
        return False
    if not ship.launcher_ok:
        b.log("info", f"{ship.name}: launchers are knocked out.")
        return False
    if ship.salvos <= 0:
        b.log("info", f"{ship.name}: missile racks are empty.")
        return False
    if not salvo_arc_ok(ship, target.x, target.y):
        b.log("info", f"{ship.name}: launchers bear abeam — bring the "
                      f"broadside onto the target.")
        return False
    ship.salvos -= 1
    ship.actions -= cost
    ms = ship.cls.missile
    b.salvos.append(Salvo(
        id=b.next_id(), side=ship.side, x=ship.x, y=ship.y, target_id=target.id,
        count=ship.cls.salvo_size, damage=ms.damage, speed=ms.speed,
        endurance=ms.endurance, accuracy=ms.accuracy))
    b.log("salvo", f"{ship.name} launches a {ship.cls.salvo_size}-bird salvo at "
                   f"{target.name}.", ship.x, ship.y, friendly=ship.side == "player")
    return True


def _reachable_deploy(b: Battle, ship: Ship, tx: int, ty: int) -> bool:
    # A station's footprint fills the adjacent cells, so its deploy ring sits
    # just outside the hull.
    reach = b.config.combat.deploy_reach + ship.cls.size // 2
    return b.in_bounds(tx, ty) and dist(ship.x, ship.y, tx, ty) <= reach


def launch_wing(b: Battle, ship: Ship, tx: int, ty: int, *, free: bool = False) -> bool:
    """Put a docked wing on the rack cell next to the ship. `free` skips the
    action cost (peacetime deployment)."""
    if not free and ship.turn_taken:
        return False
    if ship.wings_docked <= 0:
        b.log("info", f"{ship.name}: no wings docked.")
        return False
    if not _reachable_deploy(b, ship, tx, ty) or b.cell_occupied(tx, ty):
        b.log("info", "Wings launch to a free cell alongside the carrier.")
        return False
    ship.wings_docked -= 1
    if not free:
        ship.actions -= 1
    fc = b.config.fighters
    b.wings.append(FighterWing(
        id=b.next_id(), side=ship.side, x=tx, y=ty, strength=fc.wing_size,
        endurance=fc.endurance, carrier_id=ship.id,
        facing=octant(tx - ship.x, ty - ship.y)))
    b.log("launch", f"{ship.name} launches a fighter wing.", tx, ty,
          friendly=ship.side == "player")
    return True


def recover_wing(b: Battle, ship: Ship, wing: FighterWing) -> bool:
    if ship.turn_taken:
        return False
    if wing.side != ship.side or not _reachable_deploy(b, ship, wing.x, wing.y):
        b.log("info", "Recovery needs a friendly wing alongside.")
        return False
    wing.strength = 0  # off the board; rearms to a full docked wing (POC simplification)
    ship.wings_docked += 1
    ship.actions -= 1
    b.log("launch", f"{ship.name} recovers the wing for rearming.",
          wing.x, wing.y, friendly=ship.side == "player")
    return True


def lay_mine(b: Battle, ship: Ship, tx: int, ty: int, *, free: bool = False) -> bool:
    """Drop a mine on an adjacent cell (or anywhere in the zone when `free`,
    i.e. peacetime deployment — the ship needn't be walked around)."""
    if not free and ship.turn_taken:
        return False
    if ship.mines <= 0:
        b.log("info", f"{ship.name}: no mines left.")
        return False
    if not free and not _reachable_deploy(b, ship, tx, ty):
        b.log("info", "In combat, mines drop alongside the ship.")
        return False
    if not b.in_bounds(tx, ty) or b.mine_at(tx, ty) is not None \
            or (tx, ty) in b.rocks or (tx, ty) in b.debris:
        b.log("info", "No room for a mine there.")
        return False
    ship.mines -= 1
    if not free:
        ship.actions -= 1
    b.mines.append(Mine(id=b.next_id(), side=ship.side, x=tx, y=ty,
                        revealed=ship.side == "player"))
    b.log("mine", f"{ship.name} lays a mine.", tx, ty, friendly=ship.side == "player")
    return True


def fire_lance(b: Battle, ship: Ship, tx: int, ty: int) -> bool:
    """The gravity lance (player-only refit): at knife range, through the
    forward wedge, the struck quadrant's screen collapses to nothing. No hull
    damage — the lance opens the door; something else walks through it."""
    lc = b.config.lance
    if ship.turn_taken:
        return False
    if not ship.lance:
        b.log("info", f"{ship.name} carries no grav lance.")
        return False
    if ship.lance_charge > 0:
        b.log("info", f"{ship.name}: lance capacitor charging "
                      f"({ship.lance_charge} turn(s)).")
        return False
    if ship.actions < b.config.ship_actions:
        b.log("info", f"{ship.name}: the lance discharge takes the whole turn.")
        return False
    d = dist(ship.x, ship.y, tx, ty)
    if d > lc.range:
        b.log("info", f"{ship.name}: the lance only bites at knife range "
                      f"({lc.range} cells).")
        return False
    if _octant_diff(octant(tx - ship.x, ty - ship.y), ship.facing) > 1:
        b.log("info", f"{ship.name}: the lance fires through the forward wedge.")
        return False
    if los_blocked(b, ship.x, ship.y, tx, ty):
        b.log("info", f"{ship.name}: debris blocks the lance.")
        return False
    target = b.ship_at(tx, ty)
    if target is None:
        b.log("info", "Nothing there to lance.")
        return False
    ship.actions = 0
    ship.lance_charge = lc.recharge_turns
    quad = quadrant_struck(target, ship.x, ship.y, b.rng)
    target.screens[quad] = 0
    b.log("knockout", f"GRAV LANCE — {target.name}'s {quad} screen collapses!",
          target.x, target.y, friendly=ship.side == "player")
    return True


def damage_control(b: Battle, ship: Ship) -> bool:
    """All hands to damage control: the whole turn spent, one knocked-out
    component comes back online."""
    cost = b.config.combat.damage_control_cost
    if ship.turn_taken or ship.actions < cost:
        return False
    if not ship.down:
        b.log("info", f"{ship.name}: nothing needs damage control.")
        return False
    comp = b.rng.choice(sorted(ship.down))
    ship.down.discard(comp)
    ship.actions -= cost
    b.log("launch", f"{ship.name}: damage-control parties restore the "
                    f"{comp.replace('_', ' ')}.", ship.x, ship.y,
          friendly=ship.side == "player")
    return True


def launch_drone(b: Battle, ship: Ship, tx: int, ty: int) -> bool:
    """Throw a one-use recon probe downrange: hidden enemy mines around the
    probe point light up."""
    dc = b.config.drone
    if ship.turn_taken:
        return False
    if ship.drones <= 0:
        b.log("info", f"{ship.name}: no recon drones left.")
        return False
    if not b.in_bounds(tx, ty) or dist(ship.x, ship.y, tx, ty) > dc.range:
        b.log("info", f"{ship.name}: beyond drone range ({dc.range}).")
        return False
    ship.drones -= 1
    ship.actions -= 1
    foe: Side = "enemy" if ship.side == "player" else "player"
    found = 0
    for m in b.mines:
        if m.side == foe and not m.revealed \
                and dist(m.x, m.y, tx, ty) <= dc.reveal_radius:
            m.revealed = True
            found += 1
    b.log("sensor", f"{ship.name}'s recon drone sweeps the area — "
                    f"{found} mine(s) painted." if found else
                    f"{ship.name}'s recon drone sweeps the area — clear.",
          tx, ty, friendly=ship.side == "player")
    return True


# --- fighter actions --------------------------------------------------------


def move_wing(b: Battle, wing: FighterWing, tx: int, ty: int) -> bool:
    if wing.turn_taken:
        return False
    if not b.in_bounds(tx, ty) or dist(wing.x, wing.y, tx, ty) > b.config.fighters.speed:
        b.log("info", "Beyond the wing's dash range.")
        return False
    if b.cell_occupied(tx, ty):
        b.log("info", "That cell is occupied.")
        return False
    wing.facing = octant(tx - wing.x, ty - wing.y)
    wing.x, wing.y = tx, ty
    wing.actions -= 1
    return True


def wing_attack(b: Battle, wing: FighterWing, tx: int, ty: int) -> bool:
    if wing.turn_taken:
        return False
    fc = b.config.fighters
    d = dist(wing.x, wing.y, tx, ty)
    if d > fc.gun.range:
        b.log("info", "Target outside the fighters' gun range.")
        return False
    if los_blocked(b, wing.x, wing.y, tx, ty):
        b.log("info", "Debris blocks the fighters' run.")
        return False
    target = b.ship_at(tx, ty)
    other = b.wing_at(tx, ty) if target is None else None
    if target is None and other is None:
        b.log("info", "Nothing there to strafe.")
        return False
    wing.actions -= 1
    wing.facing = octant(tx - wing.x, ty - wing.y)
    friendly = wing.side == "player"
    if target is not None:
        acc = max(0.05, fc.gun.accuracy - b.config.combat.velocity_evasion * target.speed)
        hits = sum(1 for _ in range(wing.strength) if b.rng.random() < acc)
        if hits:
            apply_damage(b, target, hits * fc.gun.damage,
                         quadrant_struck(target, wing.x, wing.y, b.rng),
                         f"A {wing.strength}-craft strafing run",
                         attacker=(wing.x, wing.y))
        else:
            b.log("miss", "The strafing run scores nothing.", tx, ty, friendly=friendly)
    elif other is not None:
        acc = fc.gun.accuracy + fc.dogfight_bonus
        hits = sum(1 for _ in range(wing.strength) if b.rng.random() < acc)
        lost = min(other.strength, hits // 2)
        other.strength -= lost
        b.log("hit" if lost else "miss",
              f"Dogfight: {lost} enemy craft splashed." if lost
              else "Dogfight: no kills this pass.", tx, ty, friendly=friendly)
    return True


def intercept_salvo(b: Battle, wing: FighterWing, salvo: Salvo) -> bool:
    if wing.turn_taken:
        return False
    if salvo.side == wing.side or dist(wing.x, wing.y, salvo.x, salvo.y) > 1:
        b.log("info", "Interception needs an enemy salvo alongside.")
        return False
    wing.actions -= 1
    downed = sum(1 for _ in range(wing.strength)
                 if b.rng.random() < b.config.fighters.intercept_per_craft)
    downed = min(downed, salvo.count)
    salvo.count -= downed
    friendly = wing.side == "player"
    if salvo.count <= 0:
        b.salvos.remove(salvo)
        b.log("intercept", f"Fighters splash the whole salvo ({downed} birds).",
              wing.x, wing.y, friendly=friendly)
    else:
        b.log("intercept", f"Fighters thin the salvo by {downed}; "
                           f"{salvo.count} birds still tracking.",
              wing.x, wing.y, friendly=friendly)
    return True


# --- turn machinery ---------------------------------------------------------


def begin_turn(b: Battle, side: Side, *, first: bool = False) -> None:
    """Refresh actions, tick the lance capacitor, regenerate sidewalls, and run
    the side's sensor sweep (mine reveals)."""
    if side == "player" and not first:
        b.turn += 1
    regen = b.config.combat.screen_regen
    for s in b.fleet(side):
        s.actions = b.config.ship_actions
        if s.lance_charge > 0:
            s.lance_charge -= 1
            if s.lance_charge == 0:
                b.log("info", f"{s.name}: grav lance capacitor charged.",
                      friendly=side == "player")
        if regen > 0 and not first and not s.hull_hit:
            for q, cap in s.cls.screens.items():
                if f"shield_{q}" in s.down:
                    continue  # that facing's shield generator is knocked out
                if s.screens.get(q, 0) < cap:
                    s.screens[q] = min(cap, s.screens.get(q, 0) + regen)
        s.hull_hit = False
    for w in b.side_wings(side):
        w.actions = b.config.fighter_actions
    _reveal_mines(b, side)


def _reveal_mines(b: Battle, side: Side) -> None:
    foe: Side = "enemy" if side == "player" else "player"
    spotters = [(s.x, s.y, s.sensor_range) for s in b.fleet(side)] + \
               [(w.x, w.y, 3) for w in b.side_wings(side)]
    for m in b.mines:
        if m.side == foe and not m.revealed:
            if any(dist(m.x, m.y, x, y) <= r for x, y, r in spotters):
                m.revealed = True
                if side == "player":
                    b.log("sensor", "Sensors paint a mine.", m.x, m.y)


def end_turn(b: Battle, side: Side) -> None:
    """The side's physics: ships drift on their vectors (sweeping mines), its
    salvos chase, and its wings burn fuel."""
    for s in list(b.fleet(side)):
        _drift(b, s)
    _advance_salvos(b, side)
    for w in list(b.side_wings(side)):
        w.endurance -= 1
        if w.endurance <= 0:
            w.strength = 0
            b.log("destroyed", "A fighter wing fuels out and goes ballistic — lost.",
                  w.x, w.y, friendly=side != "player")
    _check_outcome(b)


def _drift(b: Battle, ship: Ship) -> None:
    if ship.cls.station:  # a station holds its orbit
        return
    steps = max(abs(ship.vx), abs(ship.vy))
    for _ in range(steps):
        nx = ship.x + (0 if ship.vx == 0 else (1 if ship.vx > 0 else -1))
        ny = ship.y + (0 if ship.vy == 0 else (1 if ship.vy > 0 else -1))
        if not b.in_bounds(nx, ny):  # scrape the board edge: kill the vector
            ship.vx = ship.vy = 0
            b.log("info", f"{ship.name} brakes hard at the sector boundary.",
                  ship.x, ship.y)
            return
        blocker = b.ship_at(nx, ny)
        if blocker is not None and blocker is not ship:
            ship.vx = ship.vy = 0  # sheer off rather than ram
            b.log("info", f"{ship.name} sheers off to avoid collision.",
                  ship.x, ship.y)
            return
        rock = b.rock_at(nx, ny)
        if rock is not None:  # plough into the debris: rock pulverized, hull rung
            speed = ship.speed
            quad = quadrant_struck(ship, nx, ny, b.rng)
            ship.x, ship.y = nx, ny
            ship.vx = ship.vy = 0
            del b.rocks[(nx, ny)]
            rc = b.config.rocks
            b.log("mine", f"{ship.name} ploughs into rocky debris at speed {speed}!",
                  nx, ny, friendly=ship.side == "enemy")
            apply_damage(b, ship, rc.impact_base + rc.impact_per_speed * speed,
                         quad, "The impact")
            return
        deb = b.debris.get((nx, ny))
        if deb is not None:  # smash THROUGH the wreckage: lighter hit, vector kept
            speed = ship.speed
            quad = quadrant_struck(ship, nx, ny, b.rng)
            del b.debris[(nx, ny)]
            ship.x, ship.y = nx, ny
            dc = b.config.debris
            b.log("mine", f"{ship.name} smashes through drifting wreckage!",
                  nx, ny, friendly=ship.side == "enemy")
            apply_damage(b, ship, dc.impact_base + dc.impact_per_speed * speed,
                         quad, "The wreckage")
            if not ship.alive:
                return
            continue
        ship.x, ship.y = nx, ny
        mine = next((m for m in b.mines if (m.x, m.y) == (nx, ny)
                     and m.side != ship.side), None)
        if mine is not None:
            b.mines.remove(mine)
            b.log("mine", f"MINE! {ship.name} runs onto a mine.", nx, ny,
                  friendly=ship.side == "enemy")
            apply_damage(b, ship, b.config.combat.mine_damage,
                         quadrant_struck(ship, nx, ny, b.rng), "The mine blast")
            if not ship.alive:
                return


def _advance_salvos(b: Battle, side: Side) -> None:
    for salvo in list(b.salvos):
        if salvo.side != side:
            continue
        target = b.ship(salvo.target_id)
        if target is None or not target.alive:
            b.salvos.remove(salvo)
            b.log("info", "A salvo loses lock and self-destructs.", salvo.x, salvo.y)
            continue
        for _ in range(salvo.speed):
            px, py = salvo.x, salvo.y
            salvo.x += 0 if salvo.x == target.x else (1 if target.x > salvo.x else -1)
            salvo.y += 0 if salvo.y == target.y else (1 if target.y > salvo.y else -1)
            if (salvo.x, salvo.y) in b.rocks:
                b.salvos.remove(salvo)
                b.log("info", "A salvo shreds itself against rocky debris.",
                      salvo.x, salvo.y)
                break
            if (salvo.x, salvo.y) in b.debris:
                b.salvos.remove(salvo)
                b.log("info", "A salvo shreds itself against drifting wreckage.",
                      salvo.x, salvo.y)
                break
            if (salvo.x, salvo.y) in target.cells:
                _salvo_strike(b, salvo, target, px, py)
                break
        else:
            salvo.endurance -= 1
            if salvo.endurance <= 0:
                b.salvos.remove(salvo)
                b.log("info", "A salvo burns out and fizzles.", salvo.x, salvo.y)


def _salvo_strike(b: Battle, salvo: Salvo, target: Ship, fx: int, fy: int) -> None:
    b.salvos.remove(salvo)
    friendly = salvo.side == "player"
    # Terminal point-defense: the target thins the salvo before impact rolls,
    # weaker through a quadrant whose screen is already down.
    approach = quadrant_struck(target, fx, fy, b.rng)
    pd = b.config.combat.point_defense if target.screens.get(approach, 0) > 0 \
        else b.config.combat.point_defense_open
    downed = sum(1 for _ in range(salvo.count) if b.rng.random() < pd)
    if downed:
        salvo.count -= downed
        b.log("intercept", f"{target.name}'s point-defense splashes {downed} "
                           f"bird(s).", target.x, target.y, friendly=not friendly)
        if salvo.count <= 0:
            return
    acc = max(0.05, salvo.accuracy - b.config.combat.velocity_evasion * target.speed)
    hits = sum(1 for _ in range(salvo.count) if b.rng.random() < acc)
    if hits <= 0:
        b.log("miss", f"The salvo bursts wide of {target.name}.",
              target.x, target.y, friendly=friendly)
        return
    apply_damage(b, target, hits * salvo.damage, approach,
                 f"{hits} of {salvo.count} birds", attacker=(fx, fy))


# --- setup ------------------------------------------------------------------


def make_battle(config: SpacebattleConfig, seed: int, scenario_key: str) -> Battle:
    return Battle(config=config, rng=Random(seed), seed=seed,
                  scenario_key=scenario_key)


def spawn_ship(b: Battle, side: Side, cls: ShipClass, name: str,
               x: int, y: int, facing: int, *, lance: bool = False) -> Ship:
    salvos = cls.salvos
    if lance:  # the experimental refit sails with a bled-down magazine
        salvos = int(round(cls.salvos * (1.0 - b.config.lance.salvo_penalty)))
    ship = Ship(
        id=b.next_id(), side=side, cls=cls, name=name, x=x, y=y, facing=facing,
        hull=cls.hull_max, screens=dict(cls.screens), salvos=salvos,
        wings_docked=cls.fighter_wings, mines=cls.mine_stock,
        drones=cls.recon_drones if side == "player" else 0, lance=lance)
    b.ships.append(ship)
    return ship


def seed_rocks(b: Battle) -> None:
    """Scatter rocky-debris clumps across the midfield (belt scenarios) — a
    random-walk blob per cluster, after `edge.art.terrain`'s clustered belts."""
    sc = b.config.scenarios[b.scenario_key]
    if sc.rock_clusters <= 0:
        return
    x_lo = int(b.config.width * 0.22)
    x_hi = int(b.config.width * 0.88)
    for _ in range(sc.rock_clusters):
        x = b.rng.randint(x_lo, x_hi)
        y = b.rng.randint(1, b.config.height - 2)
        for _cell in range(sc.rock_cluster_size):
            if b.in_bounds(x, y) and (x, y) not in b.rocks \
                    and not b.cell_occupied(x, y):
                b.rocks[(x, y)] = Rock(id=b.next_id(), x=x, y=y)
            dx, dy = b.rng.choice(DIRS)
            x = max(x_lo, min(x_hi, x + dx))
            y = max(1, min(b.config.height - 2, y + dy))


def seed_debris(b: Battle) -> None:
    """Scatter drifting-wreckage clumps across the midfield (graveyard
    scenarios) — same random-walk blobs as `seed_rocks`, different matter."""
    sc = b.config.scenarios[b.scenario_key]
    if sc.debris_clusters <= 0:
        return
    x_lo = int(b.config.width * 0.22)
    x_hi = int(b.config.width * 0.88)
    for _ in range(sc.debris_clusters):
        x = b.rng.randint(x_lo, x_hi)
        y = b.rng.randint(1, b.config.height - 2)
        for _cell in range(sc.debris_cluster_size):
            if b.in_bounds(x, y) and (x, y) not in b.debris \
                    and not b.cell_occupied(x, y):
                b.debris[(x, y)] = Debris(id=b.next_id(), x=x, y=y)
            dx, dy = b.rng.choice(DIRS)
            x = max(x_lo, min(x_hi, x + dx))
            y = max(1, min(b.config.height - 2, y + dy))


def setup_siege(b: Battle) -> None:
    """Starbase assault: the base sits deep in the sector behind its perimeter
    defense — a hidden mine ring sown from its own stock, fighter pickets
    already out, guard ships at anchor. It spawns facing W (toward the warp-in),
    so the reactor quadrant is the FAR side: the attacker has to fight around
    behind it, through everything the perimeter can throw."""
    sc = b.config.scenarios[b.scenario_key]
    assert sc.station is not None
    cls = b.config.ships[sc.station]
    bx, by = int(b.config.width * 0.78), b.config.height // 2
    base = spawn_ship(b, "enemy", cls, "Starbase VIGIL", bx, by, 4)
    for i, key in enumerate(sc.enemy):  # the guard picket at anchor
        gy = by + (i + 1) * 5 * (1 if i % 2 == 0 else -1)
        gy = max(0, min(b.config.height - 1, gy))
        spawn_ship(b, "enemy", b.config.ships[key],
                   ENEMY_NAMES[i % len(ENEMY_NAMES)], bx - 3, gy, 4)
    fc = b.config.fighters
    while base.wings_docked > 0:  # fighter pickets ringing the base
        for _try in range(40):
            wx = bx + b.rng.randint(-4, 4)
            wy = by + b.rng.randint(-4, 4)
            if dist(wx, wy, bx, by) >= 2 and b.in_bounds(wx, wy) \
                    and not b.cell_occupied(wx, wy):
                base.wings_docked -= 1
                b.wings.append(FighterWing(
                    id=b.next_id(), side="enemy", x=wx, y=wy,
                    strength=fc.wing_size, endurance=fc.endurance,
                    carrier_id=base.id, facing=4))
                break
        else:
            base.wings_docked -= 1  # nowhere to picket it; eat it
    ring, base.mines = base.mines, 0  # the hidden perimeter mine ring
    for _ in range(ring):
        for _try in range(60):
            ang = b.rng.uniform(0.0, 2.0 * math.pi)
            r = b.rng.randint(4, 7)
            mx, my = bx + round(math.cos(ang) * r), by + round(math.sin(ang) * r)
            if b.in_bounds(mx, my) and b.mine_at(mx, my) is None \
                    and not b.cell_occupied(mx, my):
                b.mines.append(Mine(id=b.next_id(), side="enemy", x=mx, y=my))
                break
    b.log("sensor", "The starbase's perimeter is live — pickets out, guard "
                    "ships at anchor, and the approaches are almost certainly "
                    "mined. Kill its reactor or raze it.", friendly=False)


def warp_in_enemy(b: Battle) -> None:
    """The attack arrives: enemy fleet materializes on the right edge, facing in."""
    sc = b.config.scenarios[b.scenario_key]
    for i, key in enumerate(sc.enemy):
        y = int(b.config.height / 2 + (i - (len(sc.enemy) - 1) / 2) * 4)
        y = max(0, min(b.config.height - 1, y))
        b.rocks.pop((b.config.width - 2, y), None)  # the warp flare clears the cell
        b.debris.pop((b.config.width - 2, y), None)
        spawn_ship(b, "enemy", b.config.ships[key], ENEMY_NAMES[i % len(ENEMY_NAMES)],
                   b.config.width - 2, y, 4)
    b.log("sensor", "CONTACT — hostile fleet warping in on the sector's far side!",
          friendly=False)


def setup_ambush(b: Battle) -> None:
    """Ambushed scenario: the enemy is already set up mid-sector — screens out,
    mines seeded and hidden — and you warp into their trap."""
    sc = b.config.scenarios[b.scenario_key]
    cx = int(b.config.width * 0.65)
    ships = []
    for i, key in enumerate(sc.enemy):
        y = int(b.config.height / 2 + (i - (len(sc.enemy) - 1) / 2) * 5)
        s = spawn_ship(b, "enemy", b.config.ships[key],
                       ENEMY_NAMES[i % len(ENEMY_NAMES)], cx,
                       max(0, min(b.config.height - 1, y)), 4)
        ships.append(s)
    fc = b.config.fighters
    for s in ships:  # their patrol screens are already out, picketing the approach
        while s.wings_docked > 0:
            for _try in range(30):
                wx = s.x - b.rng.randint(2, 4)
                wy = s.y + b.rng.randint(-2, 2)
                if b.in_bounds(wx, wy) and not b.cell_occupied(wx, wy):
                    s.wings_docked -= 1
                    b.wings.append(FighterWing(
                        id=b.next_id(), side="enemy", x=wx, y=wy,
                        strength=fc.wing_size, endurance=fc.endurance,
                        carrier_id=s.id, facing=4))
                    break
            else:
                s.wings_docked -= 1  # nowhere to picket it (crowded seed); eat it
    for _ in range(sc.enemy_mines):  # a minefield across the approach lanes
        for _try in range(50):
            mx = b.rng.randint(int(b.config.width * 0.30), cx - 2)
            my = b.rng.randint(1, b.config.height - 2)
            if b.mine_at(mx, my) is None and not b.cell_occupied(mx, my):
                b.mines.append(Mine(id=b.next_id(), side="enemy", x=mx, y=my))
                break


# --- the enemy bot ----------------------------------------------------------


def enemy_turn(b: Battle) -> None:
    """Heuristic opposition: salvo at range, close and rake, screen with wings."""
    if b.outcome is not None:
        return
    begin_turn(b, "enemy")
    for ship in list(b.fleet("enemy")):
        guard = 0
        while ship.alive and ship.actions > 0 and b.outcome is None and guard < 6:
            guard += 1
            if not _bot_ship_action(b, ship):
                break
    for wing in list(b.side_wings("enemy")):
        guard = 0
        while wing.alive and wing.actions > 0 and b.outcome is None and guard < 6:
            guard += 1
            if not _bot_wing_action(b, wing):
                break
    end_turn(b, "enemy")


def _drift_hits_rock(b: Battle, ship: Ship) -> bool:
    """Would the ship's current vector carry it into rock or wreckage next drift?"""
    x, y, vx, vy = ship.x, ship.y, ship.vx, ship.vy
    for _ in range(max(abs(vx), abs(vy))):
        x += 0 if vx == 0 else (1 if vx > 0 else -1)
        y += 0 if vy == 0 else (1 if vy > 0 else -1)
        if (x, y) in b.rocks or (x, y) in b.debris:
            return True
    return False


def _beam_facing(ship: Ship, tx: int, ty: int) -> int:
    """The cardinal facing that puts (tx, ty) abeam with the least turning."""
    bear = octant(tx - ship.x, ty - ship.y)
    options = [f for f in (0, 2, 4, 6) if _octant_diff(bear, f) in (2, 3)]
    return min(options, key=lambda f: _octant_diff(f, ship.facing)) \
        if options else ship.facing


def _bot_station_action(b: Battle, ship: Ship) -> bool:
    """The starbase fights from its anchorage: gun what's in range, salvo what
    isn't, put its remaining wings out when the attack closes, and work damage
    control between exchanges."""
    players = sorted(b.fleet("player"),
                     key=lambda s: dist(ship.x, ship.y, s.x, s.y))
    if not players:
        return False
    target = players[0]
    d = dist(ship.x, ship.y, target.x, target.y)
    gun = ship.cls.main_gun
    if d <= gun.range and ship.gun_ok \
            and not los_blocked(b, ship.x, ship.y, target.x, target.y):
        return fire_gun(b, ship, target.x, target.y)
    if ship.salvos > 0 and ship.launcher_ok \
            and ship.actions >= b.config.combat.salvo_action_cost \
            and d <= ship.cls.missile.speed * ship.cls.missile.endurance:
        return launch_salvo(b, ship, target)
    if ship.wings_docked > 0 and d <= ship.cls.sensor_range + 6:
        reach = b.config.combat.deploy_reach + ship.cls.size // 2
        for ddx, ddy in DIRS:
            wx, wy = ship.x + ddx * reach, ship.y + ddy * reach
            if b.in_bounds(wx, wy) and not b.cell_occupied(wx, wy):
                return launch_wing(b, ship, wx, wy)
    if ship.down and ship.actions >= b.config.combat.damage_control_cost:
        return damage_control(b, ship)
    return False


def _bot_ship_action(b: Battle, ship: Ship) -> bool:
    if ship.cls.station:
        return _bot_station_action(b, ship)
    players = sorted(b.fleet("player"),
                     key=lambda s: dist(ship.x, ship.y, s.x, s.y))
    if not players:
        return False
    target = players[0]
    if _drift_hits_rock(b, ship):  # all stop before the belt eats the hull
        return do_thrust(b, ship, ship.x, ship.y)
    d = dist(ship.x, ship.y, target.x, target.y)
    gun = ship.cls.main_gun
    # Long range: work the missile envelope — launch if the beam bears (a full
    # turn), otherwise come about to present the broadside for next turn.
    if d > gun.range and ship.salvos > 0 and ship.launcher_ok \
            and d <= ship.cls.missile.speed * ship.cls.missile.endurance:
        if salvo_arc_ok(ship, target.x, target.y):
            if ship.actions >= b.config.combat.salvo_action_cost:
                return launch_salvo(b, ship, target)
        elif ship.actions >= b.config.ship_actions:
            return do_rotate(b, ship, _beam_facing(ship, target.x, target.y))
    # Standing off with damage: put the parties to work before closing again.
    if ship.down and d > gun.range \
            and ship.actions >= b.config.combat.damage_control_cost:
        return damage_control(b, ship)
    if d <= gun.range and ship.gun_ok:
        if los_blocked(b, ship.x, ship.y, target.x, target.y):
            return do_thrust(b, ship, target.x, target.y)  # maneuver for a clear line
        if arc_ok(ship, target.x, target.y):
            return fire_gun(b, ship, target.x, target.y)
        return do_rotate(b, ship, cardinal(target.x - ship.x, target.y - ship.y))
    if ship.wings_docked > 0 and d <= 14:
        for ddx, ddy in DIRS:
            wx, wy = ship.x + ddx, ship.y + ddy
            if b.in_bounds(wx, wy) and not b.cell_occupied(wx, wy):
                return launch_wing(b, ship, wx, wy)
    return do_thrust(b, ship, target.x, target.y)


def _bot_wing_action(b: Battle, wing: FighterWing) -> bool:
    fc = b.config.fighters
    # 1. Splash inbound player salvos threatening the fleet.
    threats = sorted((s for s in b.salvos if s.side == "player"),
                     key=lambda s: dist(wing.x, wing.y, s.x, s.y))
    if threats:
        s = threats[0]
        if dist(wing.x, wing.y, s.x, s.y) <= 1:
            return intercept_salvo(b, wing, s)
        if dist(wing.x, wing.y, s.x, s.y) <= fc.speed + 1:
            return _wing_step_toward(b, wing, s.x, s.y)
    # 2. Dogfight the nearest player wing, else strafe the nearest ship.
    marks: list[tuple[int, int]] = [(w.x, w.y) for w in b.side_wings("player")]
    marks += [(s.x, s.y) for s in b.fleet("player")]
    if not marks:
        return False
    mx, my = min(marks, key=lambda m: dist(wing.x, wing.y, m[0], m[1]))
    if dist(wing.x, wing.y, mx, my) <= fc.gun.range:
        return wing_attack(b, wing, mx, my)
    return _wing_step_toward(b, wing, mx, my)


def _wing_step_toward(b: Battle, wing: FighterWing, tx: int, ty: int) -> bool:
    """Dash to the free cell closest to the mark within the wing's speed."""
    best: tuple[int, int] | None = None
    best_d = dist(wing.x, wing.y, tx, ty)
    fc = b.config.fighters
    for dx in range(-fc.speed, fc.speed + 1):
        for dy in range(-fc.speed, fc.speed + 1):
            nx, ny = wing.x + dx, wing.y + dy
            if not b.in_bounds(nx, ny) or b.cell_occupied(nx, ny):
                continue
            nd = dist(nx, ny, tx, ty)
            if nd < best_d:
                best, best_d = (nx, ny), nd
    if best is None:
        return False
    return move_wing(b, wing, best[0], best[1])
