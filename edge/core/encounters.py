"""Encounter rolls: interrupt, detection, greeting-vs-violence, pack spawn (DESIGN §10, WP24).

Pure core — every function is deterministic in its inputs; the caller (the movement
reducers in `core.rules`) passes `state.rng`, so encounter randomness rides the
command stream and a journey replays exactly (H4). The flow, per sector entered:

1. **Interrupt** — the band's `encounters.interrupt_chance` fires (0 in the Hub) and a
   species present in the sector is drawn with weight **inverse to threat rating**
   (common weak raiders harass the frontier; apex predators are rarely seen).
2. **Detection** — the species' sensors (its lead hull's rating) against the player's
   cloak plus nebula cover; an undetected player slips away freely (no halt).
3. **Greeting vs violence** — rolled against effective disposition: friendly-band
   always greets, hostile-band always attacks, the wary middle interpolates linearly
   (a genuine coin-flip at the midpoint). A `combatant: false` species — or one with
   no fleet to field — can never reach violence.
4. **Pack spawn** — a violent opener spawns the encounter group per the species'
   `pack_behavior`/`escort` (§6.1), each foe a frozen stat snapshot of its hull class
   scaled by the species' threat rating.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from edge.core.aliens import (
    FRIENDLY,
    alliance_standing_shift,
    disposition_band,
    effective_disposition,
    governor_hostile,
    grudge_shift,
)
from edge.core.config import GameConfig, PackConfig, SpeciesConfig
from edge.core.discovery import sector_has_nebula
from edge.core.models import AlienSpecies, Encounter, EncounterFoe, Player, Ship, UniverseState


@dataclass(frozen=True, slots=True)
class EncounterRoll:
    """What an interrupt roll produced (WP24).

    `detected=False` ⇒ the player slipped away unseen (no halt, no encounter).
    `hostile=False` (with `detected=True`) ⇒ a peaceful opener — the journey halts and
    the contact screen takes over; nothing is stored on the player.
    `hostile=True` ⇒ `encounter` carries the spawned pack for `Player.active_encounter`.
    """

    species: AlienSpecies
    detected: bool
    hostile: bool
    encounter: Encounter | None = None


def species_in_sector(state: UniverseState, sector_id: int) -> list[AlienSpecies]:
    """The species instances present in `sector_id`, in stable id order."""
    return [sp for _, sp in sorted(state.species.items()) if sp.sector_id == sector_id]


def _species_cfg(config: GameConfig, species: AlienSpecies) -> SpeciesConfig | None:
    if config.roster is None:
        return None
    try:
        return config.roster.species_by_id(species.roster_id)
    except KeyError:
        return None


def _lead_hull_sensor(config: GameConfig, sc: SpeciesConfig) -> int:
    """The species' sensor rating — its lead fleet hull's, 0 for a shipless kind."""
    if not sc.fleet:
        return 0
    return config.ship_class(sc.fleet[0]).sensor_rating


def roll_encounter(
    state: UniverseState, player: Player, ship: Ship, sector_id: int,
    config: GameConfig, rng: random.Random,
) -> EncounterRoll | None:
    """Roll the §10 encounter chain for entering `sector_id`; None ⇒ nothing happened.

    Draw discipline: RNG is only touched when an encounter is *possible* (a non-zero
    band chance and a candidate species present) — both preconditions are pure
    functions of state, so the command-stream draw order stays deterministic.
    """
    sector = state.sectors[sector_id]
    # Core law (§6.3, WP38): a player aligned against the Core governor is engaged on
    # sight by any governing combatant present — the Core stops being a sanctuary. This
    # fires regardless of the band's interrupt chance (the Hub is safe only for the
    # governor's own). Whether it triggers is a pure function of state, so the
    # command-stream draw order stays deterministic (H4).
    if config.roster is not None and sector.is_galactic_core and governor_hostile(state, player):
        defender = _governing_defender(state, config, sector_id)
        if defender is not None:
            sc = _species_cfg(config, defender)
            if sc is not None and sc.combatant and sc.fleet:
                pack = spawn_pack(defender, sc, sector_id, ship, config, rng)
                pack = replace(pack, speech_context="combat_open")
                return EncounterRoll(species=defender, detected=True, hostile=True, encounter=pack)

    band = sector.distance_band
    chance = config.encounters.interrupt_chance.get(band, 0.0)
    candidates = species_in_sector(state, sector_id)
    if chance <= 0.0 or not candidates or config.roster is None:
        return None
    if rng.random() >= chance:
        return None

    species = _draw_species(candidates, config, rng)
    sc = _species_cfg(config, species)
    if sc is None:
        return None

    # Detection: the species' sensors vs the player's cloak, dimmed by nebula cover.
    enc = config.encounters
    detect = enc.detection_base + enc.detection_sensor_coeff * _lead_hull_sensor(config, sc)
    detect -= enc.detection_cloak_coeff * ship.cloak_rating
    if sector_has_nebula(state, sector_id):
        detect -= enc.nebula_cover
    if rng.random() >= max(0.0, min(1.0, detect)):
        return EncounterRoll(species=species, detected=False, hostile=False)

    # Greeting vs violence, against effective disposition (§6/§10) shifted down by any
    # active grudge the species holds against the player (§6.5, WP27). Non-combatants
    # and shipless kinds can never reach violence.
    if sc.combatant and sc.fleet:
        disp = max(0.0, effective_disposition(species, player)
                   - grudge_shift(species, player)
                   - alliance_standing_shift(player, species))
        hostility, amity = config.aliens.hostility_threshold, config.aliens.amity_threshold
        if disp >= amity:
            violence = 0.0
        elif disp < hostility:
            violence = 1.0
        else:
            violence = (amity - disp) / (amity - hostility)
        if violence > 0.0 and rng.random() < violence:
            pack = spawn_pack(species, sc, sector_id, ship, config, rng)
            # The opener beat (§6.7, WP31): a friendly-band species opening fire —
            # a grudge-shifted violence roll — is a betrayal, not a mere attack.
            band = disposition_band(effective_disposition(species, player), config.aliens)
            opener = "betrayal" if band == FRIENDLY else "combat_open"
            pack = replace(pack, speech_context=opener)
            return EncounterRoll(species=species, detected=True, hostile=True, encounter=pack)
    return EncounterRoll(species=species, detected=True, hostile=False)


def _governing_defender(
    state: UniverseState, config: GameConfig, sector_id: int
) -> AlienSpecies | None:
    """A governing-alliance combatant present in `sector_id`, or None (§6.3 Core law)."""
    gov = state.game.core_governing_alliance_id
    for sp in species_in_sector(state, sector_id):
        if sp.alliance_id != gov:
            continue
        sc = _species_cfg(config, sp)
        if sc is not None and sc.combatant and sc.fleet:
            return sp
    return None


def _draw_species(candidates: list[AlienSpecies], config: GameConfig,
                  rng: random.Random) -> AlienSpecies:
    """Weight-draw the encountered species — inverse to threat rating (§10)."""
    enc = config.encounters
    weights: list[float] = []
    for sp in candidates:
        sc = _species_cfg(config, sp)
        threat = sc.threat_rating if sc is not None else 0.0
        w = 1.0 / (1.0 + threat) if enc.weight_inverse_threat else 1.0
        weights.append(max(enc.weight_floor, w))
    return rng.choices(candidates, weights=weights, k=1)[0]


def spawn_pack(species: AlienSpecies, sc: SpeciesConfig, sector_id: int, ship: Ship,
               config: GameConfig, rng: random.Random) -> Encounter:
    """Spawn the encounter group per the species' pack behavior (§6.1, §10)."""
    hulls = _pack_hulls(sc.pack, sc.fleet, config, rng)
    foes = tuple(_foe(config, sc, hull, i) for i, hull in enumerate(hulls))
    return Encounter(
        species_id=species.id, sector_id=sector_id, foes=foes,
        round=0, player_shields=ship.shields, detected=True,
    )


def _pack_hulls(pack: PackConfig, fleet: list[str], config: GameConfig,
                rng: random.Random) -> list[str]:
    lead = fleet[0]
    if pack.behavior == "escorted":
        return [lead, *pack.escort]
    if pack.behavior in ("swarm", "family_group", "colony"):
        size = rng.randint(config.combat.swarm_size_min, config.combat.swarm_size_max)
        return [lead] * size
    return [lead]  # solo


def _foe(config: GameConfig, sc: SpeciesConfig, hull_id: str, index: int) -> EncounterFoe:
    """A frozen stat snapshot for one pack member (hull class × species threat)."""
    klass = config.ship_class(hull_id)
    weapon = config.weapons[klass.armament[0]] if klass.armament else None
    threat_bonus = round(sc.threat_rating * config.combat.threat_damage_scale)
    damage = (weapon.damage if weapon is not None else 1) + threat_bonus
    defense = sum(d.value for d in klass.defenses
                  if d.type in ("armour", "screens", "energy_plates"))
    return EncounterFoe(
        ship_class_id=klass.id,
        name=f"{sc.name} {klass.name}" + (f" #{index + 1}" if index else ""),
        hull=klass.hull_max, hull_max=klass.hull_max, shields=klass.shields_max,
        damage=max(1, damage),
        firing_arc=weapon.firing_arc if weapon is not None else "all_round",
        combat_speed=klass.combat_speed,
        defense=defense,
    )
