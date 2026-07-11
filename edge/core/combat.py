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
- **Localized damage** (§4.1, WP26): a volley that reaches the hull may additionally
  knock out one subsystem component — the pick weighted toward exposed/forward
  systems — degrading that aspect immediately (the gun slows, the thrusters fail and
  the flee floor is all that is left, or the screens themselves weaken).
- **Destruction** (§10, WP26): hull driven to zero is the `destroyed` outcome — the
  reducer drops the player to an escape pod (ship and cargo lost, the pod limps home).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from edge.core.config import CombatConfig, GameConfig
from edge.core.engine_room import ShipAspects, derive_aspects
from edge.core.enums import Subsystem
from edge.core.models import Encounter, EncounterFoe, Ship

COMBAT_ACTIONS = ("fight", "flee", "launch_missile", "field_patch")

FLED = "fled"
VICTORY = "victory"
DESTROYED = "destroyed"  # hull driven to zero — the reducer issues the escape pod
RETREATED = "retreated"  # a bloodied pack breaks off — the reducer relocates the survivors


class CombatError(Exception):
    """An invalid combat action (no encounter, no ammo, unknown action)."""


@dataclass(frozen=True, slots=True)
class RoundResult:
    """One resolved combat round (WP25/WP26)."""

    encounter: Encounter | None  # None ⇒ the fight ended
    ship: Ship  # hull / missiles / knocked slots updated
    outcome: str | None  # None while ongoing, else FLED / VICTORY / DESTROYED
    damage_dealt: int
    damage_taken: int
    foes_destroyed: int
    # A component knocked out by this round's volley (§4.1, WP26), if any:
    # (subsystem, slot index, component kind value). The reducer re-derives aspects.
    knockout: tuple[Subsystem, int, str] | None = None


def player_foe(ship: Ship, config: GameConfig, name: str) -> EncounterFoe:
    """Build the combat foe for a *defending player's* live ship (§14, WP67 — attacker-driven PvP).

    The defender fights back automatically from the very aspects their own fights use: gun
    damage / shields / combat speed are subsystem-derived (§4.1), so a tuned engine room
    defends its owner even offline. Hull is the ship's *current* hull (a wounded ship enters the
    fight wounded); the firing arc comes from the hull's Main Gun weapon. `defense` sums the
    hull's flat armour/screens like the NPC and starbase foes, so one combat model serves all.
    """
    aspects = derive_aspects(ship, config)
    klass = config.ship_class(ship.type_id)
    weapon = config.weapons[klass.armament[0]] if klass.armament else None
    arc = weapon.firing_arc if weapon is not None else "ahead"
    damage = max(1, aspects.gun_damage + aspects.efficiency_bonus)
    defense = sum(d.value for d in klass.defenses
                  if d.type in ("armour", "screens", "energy_plates"))
    hull = max(1, ship.hull_current)
    return EncounterFoe(
        ship_class_id=klass.id, name=name, hull=hull, hull_max=ship.hull_max,
        shields=aspects.shields, damage=damage, firing_arc=arc,
        combat_speed=aspects.combat_speed, defense=defense,
    )


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


def _roll_knockout(
    ship: Ship, cc: CombatConfig, rng: random.Random
) -> tuple[Ship, tuple[Subsystem, int, str] | None]:
    """Maybe knock out one component after a hull-reaching volley (§4.1, WP26).

    The subsystem pick is weighted toward exposed/forward systems (`knockout_weights`);
    within the subsystem a uniformly-drawn active slot goes down. A flat NPC hull
    (no engine room) or a ship with nothing left to knock out is untouched. Draw
    order is fixed (chance roll, then the weighted pick) so replays stay exact (H4).
    """
    if ship.subsystems is None or rng.random() >= cc.knockout_chance:
        return ship, None
    candidates = [
        (sub, [i for i, c in enumerate(st.slots) if c is not None and not c.knocked_out])
        for sub, st in sorted(ship.subsystems.items(), key=lambda kv: kv[0].value)
    ]
    candidates = [(sub, idx) for sub, idx in candidates if idx]
    if not candidates:
        return ship, None  # everything is already dark
    weights = [cc.knockout_weights.get(sub.value, 1.0) for sub, _ in candidates]
    sub, indices = rng.choices(candidates, weights=weights)[0]
    slot_index = rng.choice(indices)
    state = ship.subsystems[sub]
    comp = state.slots[slot_index]
    assert comp is not None
    slots = list(state.slots)
    slots[slot_index] = replace(comp, knocked_out=True)
    subsystems = dict(ship.subsystems)
    subsystems[sub] = replace(state, slots=tuple(slots))
    return replace(ship, subsystems=subsystems), (sub, slot_index, comp.kind.value)


def resolve_round(
    encounter: Encounter, ship: Ship, aspects: ShipAspects, interception: float,
    action: str, config: GameConfig, rng: random.Random, *, escape_floor: float,
    npc_retreat_chance: float = 0.0,
) -> RoundResult:
    """Resolve one combat round: the player's `action`, then the surviving foes' fire.

    Field-patching consumes the player action (the kit spend itself is applied by the
    reducer before calling here); the pack still gets its volley.

    `npc_retreat_chance` (§10, WP-PR03) is the per-round probability a *bloodied* surviving
    pack breaks off. It is 0 in every fight where retreat is impossible or forbidden (a
    fixed garrison, a fearsome pack, no legal warp out — the reducer decides), so the RNG
    stream is only perturbed when a real retreat is on the table. The roll fires after the
    volley/knockout draws and only once the pack's aggregate hull is at or below
    `combat.npc_retreat_hull_frac`; on success the encounter ends `RETREATED` and the
    reducer relocates the survivors and reports concrete counts.
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
        # Destroyed (§10, WP26): the reducer drops the player to the escape pod.
        wreck = replace(ship, hull_current=0, missiles=new_missiles)
        return RoundResult(
            encounter=None, ship=wreck, outcome=DESTROYED,
            damage_dealt=dealt, damage_taken=taken, foes_destroyed=destroyed,
        )

    new_ship = replace(ship, hull_current=hull_left, missiles=new_missiles)
    knockout = None
    if hull_hit > 0:
        # Damage that defeats the screens may localize into a component (§4.1).
        new_ship, knockout = _roll_knockout(new_ship, cc, rng)

    # A bloodied pack may break off (§10, WP-PR03). Gated by `npc_retreat_chance` (0 when
    # retreat is impossible/forbidden) so the RNG stream is untouched in every other fight;
    # the roll only fires once the survivors' aggregate hull is at or below the config floor.
    if npc_retreat_chance > 0.0:
        hull_now = sum(f.hull for f in alive)
        hull_cap = sum(f.hull_max for f in alive)
        if hull_cap > 0 and hull_now / hull_cap <= cc.npc_retreat_hull_frac \
                and rng.random() < npc_retreat_chance:
            return RoundResult(
                encounter=None, ship=new_ship, outcome=RETREATED,
                damage_dealt=dealt, damage_taken=taken, foes_destroyed=destroyed,
                knockout=knockout,
            )

    new_encounter = replace(
        encounter, foes=tuple(foes), round=next_round, player_shields=shields_left,
    )
    return RoundResult(
        encounter=new_encounter, ship=new_ship, outcome=None,
        damage_dealt=dealt, damage_taken=taken, foes_destroyed=destroyed,
        knockout=knockout,
    )
