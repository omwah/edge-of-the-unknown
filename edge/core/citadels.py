"""Citadels — planetary defense levels, treasury, timed builds, and the gun (§4.2, §14).

Pure core (no I/O, no RNG in the build/defense math; the invasion roll of WP55 draws
from the reducer's `state.rng`). A citadel is raised in three cumulative levels on an
owned colony, each **paid up front** (equipment from the planet's stores + latinum) and
completed as a **timed build**: `Planet.citadel_progress` accrues the colony's headcount
per planet-growth tick until it reaches the level's `build_colonist_days`, so bigger
colonies build faster (the point of the colonist gate). Level 1 grants the treasury +
a garrison bonus, level 2 the fixed **citadel gun** that joins sector defense exactly as
an orbital base does, level 3 a **siege shield** (WP55). An in-progress build is neither
lootable nor cancellable — conquest inherits it (interview decision 2).

Invariants owned here: costs conserve (equipment leaves stores, latinum burns — a §8
sink); one build open per planet; a build completes exactly once; the gun foe's stats
derive from config, so a silenced/absent gun never defends.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from edge.core.config import CitadelConfig, GameConfig
from edge.core.enums import Commodity
from edge.core.models import EncounterFoe, Ownership, Planet

CITADEL_MAX = 3


class CitadelError(Exception):
    """A citadel build/treasury operation was rejected (raised by the reducers)."""


def _levels(config: GameConfig) -> CitadelConfig:
    if config.citadels is None:
        raise CitadelError("citadels are not buildable in this universe")
    return config.citadels


def level_config(config: GameConfig, level: int):  # -> CitadelLevelConfig
    """The config for citadel `level` (1-based). Raises for an out-of-range level."""
    cfg = _levels(config)
    if not 1 <= level <= len(cfg.levels):
        raise CitadelError(f"no citadel level {level}")
    return cfg.levels[level - 1]


def building(planet: Planet) -> bool:
    """Whether a timed build is currently open on `planet` (§4.2, WP54)."""
    return planet.citadel_progress >= 0


def open_build(planet: Planet, config: GameConfig) -> tuple[Planet, int]:
    """Open a timed build for the next citadel level, paying its cost (§4.2, WP54).

    Validates the ladder (next level exists, none in progress, colony large enough) and
    that the planet's equipment stores + treasury/latinum cover the cost. The equipment
    leaves `stores` and the latinum is charged to the *caller* (the reducer debits the
    player), so this returns the planet with equipment removed and progress opened at 0.
    Returns `(planet, target_level)`.
    """
    if building(planet):
        raise CitadelError("a citadel build is already in progress here")
    target = planet.citadel_level + 1
    lc = level_config(config, target)  # raises if past the top
    if planet.colonists < lc.min_colonists:
        raise CitadelError(
            f"need {lc.min_colonists} colonists for citadel level {target} "
            f"(have {planet.colonists})")
    have_equipment = planet.stores.get(Commodity.EQUIPMENT, 0)
    if have_equipment < lc.cost_equipment:
        raise CitadelError(
            f"need {lc.cost_equipment} equipment in stores (have {have_equipment})")
    stores = {**planet.stores, Commodity.EQUIPMENT: have_equipment - lc.cost_equipment}
    return replace(planet, stores=stores, citadel_progress=0), target


def advance_build(planet: Planet, config: GameConfig) -> tuple[Planet, bool]:
    """Advance an open build by one production tick, returning `(planet, completed)`.

    Accrues the colony's current headcount into `citadel_progress` (integer-exact, so
    replay is exact). On reaching the level's `build_colonist_days` the build completes:
    `citadel_level += 1`, progress cleared, and — if this level grants the gun — the gun
    is seeded to full integrity. A no-op (returns the same planet, False) when no build is
    open or the colony is empty (a build simply stalls without colonists).
    """
    if not building(planet) or config.citadels is None:
        return planet, False
    if planet.colonists <= 0:
        return planet, False  # no labour → no progress this tick (stalls, never regresses)
    target = planet.citadel_level + 1
    lc = config.citadels.levels[target - 1]
    progress = planet.citadel_progress + planet.colonists
    if progress < lc.build_colonist_days:
        return replace(planet, citadel_progress=progress), False
    # Completed: raise the level, clear the build, and seed the gun if this level grants it.
    gun = (config.citadels.gun_hull
           if target >= config.citadels.gun_min_level and planet.gun_integrity <= 0
           else planet.gun_integrity)
    return replace(planet, citadel_level=target, citadel_progress=-1,
                   gun_integrity=gun), True


def has_gun(planet: Planet, config: GameConfig) -> bool:
    """Whether `planet` fields an operational citadel gun (§4.2, WP54/WP55)."""
    if config.citadels is None:
        return False
    return planet.citadel_level >= config.citadels.gun_min_level and planet.gun_integrity > 0


def citadel_foe(planet: Planet, config: GameConfig) -> EncounterFoe:
    """The immobile foe a planet's citadel gun fields in sector defense (§4.2, WP54).

    Reuses the `EncounterFoe` spawn pattern (after `starbases.assault_foe` and
    `territory.fighter_foe`): an all-round emplacement with no arc to slip and no flee,
    scaled off config gun stats and current `gun_integrity` (so a battered gun hits
    softer — WP55 ticks integrity down). Stats derive purely from config.
    """
    cfg = _levels(config)
    frac = planet.gun_integrity / cfg.gun_hull if cfg.gun_hull else 0.0
    return EncounterFoe(
        ship_class_id="citadel_gun", name=f"{planet.name} citadel gun",
        hull=max(1, planet.gun_integrity), hull_max=cfg.gun_hull,
        shields=round(cfg.gun_shields * frac), damage=cfg.gun_damage,
        firing_arc="all_round", combat_speed=0, defense=cfg.gun_defense,
    )


def siege_shielded(planet: Planet, config: GameConfig, base_operational: bool) -> bool:
    """Whether the L3 siege shield bars invasion of `planet` (§4.2, WP55).

    True when the citadel is at `shield_min_level` *and* something still stands to project
    it — its orbital base is operational or its gun is live. Once both fall, the shield
    drops and a ground assault becomes possible.
    """
    if config.citadels is None or planet.citadel_level < config.citadels.shield_min_level:
        return False
    return base_operational or has_gun(planet, config)


def citadel_defense_mult(planet: Planet, config: GameConfig) -> float:
    """The garrison multiplier the citadel level grants in the invasion math (§4.2, WP55)."""
    if config.citadels is None or planet.citadel_level < 1:
        return 1.0
    return config.citadels.levels[min(planet.citadel_level, CITADEL_MAX) - 1].garrison_mult


@dataclass(frozen=True, slots=True)
class InvasionOutcome:
    """The result of a ground assault (§4.2, §14, WP55) — folded into the reducer.

    `victory` flips the world; `attacker_survivors` become the new garrison on victory;
    `fighters_lost` is the committed count that died. Pure over its inputs.
    """

    victory: bool
    attacker_survivors: int
    defender_survivors: int
    fighters_lost: int


def resolve_invasion(
    planet: Planet, attacker_fighters: int, config: GameConfig, rng: random.Random,
) -> InvasionOutcome:
    """Resolve a ground assault: attacker fighters vs the citadel-scaled garrison (§4.2, WP55).

    Per-round percentile exchange (BNT §A.3 shape): each round both sides lose a random
    fraction — in `[invasion_round_lo, invasion_round_hi]` — of the *other's* current
    strength (at least one each, so a fight always terminates), until one side breaks.
    Victory is the attacker outlasting the defender. Draws (both wiped) count as a repulse
    — you must *hold* the ground to take it. Draws from the passed rng (the reducer's
    `state.rng`, H4), so a siege replays exactly.
    """
    cfg = _levels(config)
    attacker = attacker_fighters
    defender = round(planet.fighters * citadel_defense_mult(planet, config))
    while attacker > 0 and defender > 0:
        a_loss = max(1, round(defender * rng.uniform(cfg.invasion_round_lo, cfg.invasion_round_hi)))
        d_loss = max(1, round(attacker * rng.uniform(cfg.invasion_round_lo, cfg.invasion_round_hi)))
        attacker = max(0, attacker - a_loss)
        defender = max(0, defender - d_loss)
    victory = attacker > 0 and defender <= 0
    return InvasionOutcome(
        victory=victory, attacker_survivors=attacker, defender_survivors=defender,
        fighters_lost=attacker_fighters - attacker,
    )


def conquer(planet: Planet, player_id: int, survivors: int, config: GameConfig) -> tuple[Planet, int]:
    """The post-victory planet state + captured latinum (§4.2, WP55).

    Owner flips to the invader; the citadel drops one level (its defences are spent); the
    garrison becomes the surviving attacker fighters; colonists are spared at
    `civilian_survival_frac`; the treasury is captured (returned as latinum, zeroed on the
    planet — conserved). Stores stay with the now-player-owned world (its salvage is simply
    the player's henceforth). Any open build is inherited (progress untouched).
    """
    cfg = _levels(config)
    captured = planet.treasury
    new_planet = replace(
        planet, owner=Ownership("player", player_id),
        citadel_level=max(0, planet.citadel_level - 1),
        fighters=survivors, gun_integrity=0, treasury=0,
        colonists=round(planet.colonists * cfg.civilian_survival_frac),
    )
    return new_planet, captured
