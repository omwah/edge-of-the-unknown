"""Combat rounds: fight / flee / missiles, arcs, and the escape floor (DESIGN §10, WP25).

Pure core. One `CombatAction` command resolves one round: the player acts (fire the
Main Gun, launch a missile, attempt to flee, or field-patch), then every surviving foe
returns fire. Every roll draws from the passed RNG — the command-stream `state.rng` —
so a fight replays exactly from `(seed, command log)` (H4).

The §10 counter-play, implemented:

- **Firing arcs.** An `ahead`/`spinal` attacker is evaded by maneuvering out of its
  firing line — a combat-speed contest; `all_round` leaves no safe angle. `spinal`
  weapons additionally fire only every other round (periodic).
- **Missiles** are finite and ignore arc — the answer to a hull you cannot line up on.
- **Flee** is a function of combat speed, interception, cloak, and accumulated hull
  damage, **clamped to `[aliens.escape_floor, flee_cap]`** — escape is always possible
  even in a crippled ship (a §13 property-test invariant: `flee_chance`).
- The Spindrive **efficiency bonus** (§4.1) applies once each to gun damage, combat
  speed (both contests), and screen deflection.

Ship destruction (hull 0 → escape pod) is WP26; until it lands, a hull driven to zero
is clamped at 1 and the ship force-disengages (`crippled`) — the explicit seam pods
replace.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from edge.core.config import CombatConfig, GameConfig
from edge.core.engine_room import ShipAspects
from edge.core.models import Encounter, EncounterFoe, Ship

COMBAT_ACTIONS = ("fight", "flee", "launch_missile", "field_patch")

FLED = "fled"
VICTORY = "victory"
CRIPPLED = "crippled"  # hull driven to zero — the WP26 escape-pod seam


class CombatError(Exception):
    """An invalid combat action (no encounter, no ammo, unknown action)."""


@dataclass(frozen=True, slots=True)
class RoundResult:
    """One resolved combat round (WP25)."""

    encounter: Encounter | None  # None ⇒ the fight ended
    ship: Ship  # hull / missiles updated
    outcome: str | None  # None while ongoing, else FLED / VICTORY / CRIPPLED
    damage_dealt: int
    damage_taken: int
    foes_destroyed: int


def flee_chance(
    combat_speed: int, efficiency_bonus: int, interception: float, cloak: int,
    hull_missing_fraction: float, config: CombatConfig, floor: float,
) -> float:
    """The player's flee probability, clamped to `[floor, flee_cap]` (§10, §13).

    A pure, named function so the escape-floor invariant has one property-test target:
    for *any* damage / speed / interception combination the result never drops below
    the configured floor.
    """
    chance = (
        config.flee_base
        + config.flee_speed_coeff * (combat_speed + efficiency_bonus)
        - config.interception_coeff * interception
        + config.cloak_coeff * cloak
        - config.damage_penalty * hull_missing_fraction
    )
    return max(floor, min(config.flee_cap, chance))


def _evade_chance(player_speed: int, foe_speed: int, config: CombatConfig) -> float:
    """The chance to slip an `ahead`/`spinal` firing line (a combat-speed contest)."""
    chance = config.evade_base + config.evade_speed_coeff * (player_speed - foe_speed)
    return max(0.0, min(config.evade_cap, chance))


def _player_damage(aspects: ShipAspects) -> int:
    """Main Gun output per round: (damage + the global bonus) × rate (§4.1)."""
    if aspects.gun_damage <= 0:
        return 0
    return (aspects.gun_damage + aspects.efficiency_bonus) * max(1, aspects.gun_rate)


def _hit_foe(foe: EncounterFoe, raw: int) -> EncounterFoe:
    """Apply `raw` damage through the foe's flat defense, shields first, then hull."""
    dmg = max(1, raw - foe.defense)
    absorbed = min(foe.shields, dmg)
    return replace(foe, shields=foe.shields - absorbed, hull=foe.hull - (dmg - absorbed))


def resolve_round(
    encounter: Encounter, ship: Ship, aspects: ShipAspects, interception: float,
    action: str, config: GameConfig, rng: random.Random, *, escape_floor: float,
) -> RoundResult:
    """Resolve one combat round: the player's `action`, then the surviving foes' fire.

    Field-patching consumes the player action (the kit spend itself is applied by the
    reducer before calling here); the pack still gets its volley.
    """
    cc = config.combat
    foes = list(encounter.foes)
    dealt = destroyed = 0
    new_missiles = ship.missiles

    if action == "fight":
        raw = _player_damage(aspects)
        if raw <= 0:
            raise CombatError("the Main Gun is offline")
        target = next((i for i, f in enumerate(foes) if f.hull > 0), None)
        if target is not None:
            before = foes[target]
            foes[target] = _hit_foe(before, raw)
            dealt = (before.shields - foes[target].shields) + (before.hull - foes[target].hull)
            if foes[target].hull <= 0:
                destroyed += 1
    elif action == "launch_missile":
        if ship.missiles <= 0:
            raise CombatError("no missiles left")
        new_missiles -= 1
        target = next((i for i, f in enumerate(foes) if f.hull > 0), None)
        if target is not None:
            before = foes[target]
            foes[target] = _hit_foe(before, cc.missile_damage)
            dealt = (before.shields - foes[target].shields) + (before.hull - foes[target].hull)
            if foes[target].hull <= 0:
                destroyed += 1
    elif action == "flee":
        missing = 1.0 - (ship.hull_current / ship.hull_max if ship.hull_max else 1.0)
        chance = flee_chance(
            aspects.combat_speed, aspects.efficiency_bonus, interception,
            ship.cloak_rating, missing, cc, escape_floor,
        )
        if rng.random() < chance:
            return RoundResult(
                encounter=None, ship=replace(ship, missiles=new_missiles),
                outcome=FLED, damage_dealt=0, damage_taken=0, foes_destroyed=0,
            )
    elif action != "field_patch":
        raise CombatError(f"unknown combat action {action!r}")

    alive = [f for f in foes if f.hull > 0]
    if not alive:
        return RoundResult(
            encounter=None, ship=replace(ship, missiles=new_missiles),
            outcome=VICTORY, damage_dealt=dealt, damage_taken=0, foes_destroyed=destroyed,
        )

    # The pack's volley. Spinal weapons fire only every other round (periodic);
    # ahead/spinal fire can be evaded on a combat-speed contest; all_round cannot.
    taken = 0
    player_speed = aspects.combat_speed + aspects.efficiency_bonus
    next_round = encounter.round + 1
    for foe in alive:
        if foe.firing_arc == "spinal" and next_round % 2 == 0:
            continue  # recharging its firing cycle this round
        if foe.firing_arc in ("ahead", "spinal"):
            if rng.random() < _evade_chance(player_speed, foe.combat_speed, cc):
                continue  # maneuvered out of the firing line
        taken += max(1, foe.damage - aspects.efficiency_bonus)  # screens deflect a little

    shields_left = encounter.player_shields
    absorbed = min(shields_left, taken)
    shields_left -= absorbed
    hull_hit = taken - absorbed
    hull_left = ship.hull_current - hull_hit

    if hull_left <= 0:
        # WP26 replaces this seam with escape pods; until then the ship is crippled at
        # 1 hull and force-disengages, so death is never unhandled.
        crippled = replace(ship, hull_current=1, missiles=new_missiles)
        return RoundResult(
            encounter=None, ship=crippled, outcome=CRIPPLED,
            damage_dealt=dealt, damage_taken=taken, foes_destroyed=destroyed,
        )

    new_encounter = replace(
        encounter, foes=tuple(foes), round=next_round, player_shields=shields_left,
    )
    new_ship = replace(ship, hull_current=hull_left, missiles=new_missiles)
    return RoundResult(
        encounter=new_encounter, ship=new_ship, outcome=None,
        damage_dealt=dealt, damage_taken=taken, foes_destroyed=destroyed,
    )
