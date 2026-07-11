"""Orbital starbase helpers (DESIGN §4.2) — pure core, no I/O, no RNG.

A starbase reuses the engine-room slotted-subsystem model (§4.1) minus mobility,
plus a `fusion_reactor`. **Derelict is emergent, not a stored flag**: a base is
operational only while its reactor keystone (the structural `converter`) is filled
and undamaged — strip or knock it out and the base can no longer power itself, so
it reads as derelict. The big bang makes unowned-world bases derelict by removing
that keystone, leaving the remaining components as a salvage cache (WP4); repair is
just refilling the slot (Phase 3). `is_operational` is the seam Phase-3 planetary
defense will read.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from edge.core.enums import Subsystem
from edge.core.models import EncounterFoe, Starbase, UniverseState

if TYPE_CHECKING:
    from edge.core.config import GameConfig


def base_in_sector(state: UniverseState, sector_id: int) -> Starbase | None:
    """The orbital base in `sector_id`, or None (WP78).

    At most one exists — the big bang places at most one planet per sector and a base
    hangs off a planet — but iterate id-sorted so a hand-built state stays deterministic.
    """
    return next(
        (b for b in sorted(state.starbases.values(), key=lambda b: b.id)
         if b.sector_id == sector_id),
        None,
    )


def is_operational(base: Starbase) -> bool:
    """Whether `base` can power itself — its reactor keystone is filled and intact.

    Derelict is exactly `not is_operational(base)` (§4.2): no separate flag.
    """
    reactor = base.subsystems.get(Subsystem.FUSION_REACTOR)
    if reactor is None or reactor.keystone_index is None:
        return False
    keystone = reactor.slots[reactor.keystone_index]
    return keystone is not None and not keystone.knocked_out


def services_operational(base: Starbase, config: GameConfig) -> bool:
    """Whether `base` may offer forward services — powered *and* above the integrity gate.

    Stricter than `is_operational` (§4.2, WP-PR04): the reactor keystone must be live and
    the surviving-component integrity must meet `starbase.service_integrity_min`. A base
    above the powered line but battered below the threshold is still salvageable/repairable
    (recovery never closes) yet withholds market/hardware/munitions/bank until repaired
    back above it. The single predicate the service reducers *and* the DTO projection read,
    so hidden tabs and command legality can't drift.
    """
    if not is_operational(base):
        return False
    threshold = config.starbase.service_integrity_min if config.starbase is not None else 0.0
    return component_integrity(base) >= threshold


def component_integrity(base: Starbase) -> float:
    """The fraction of the base's slots holding a live component (§4.2, WP40).

    Defense strength scales with this — surviving components + an intact reactor make a
    base formidable; a stripped one is a pushover. 0.0 for a base with no slots.
    """
    total = sum(len(st.slots) for st in base.subsystems.values())
    if total == 0:
        return 0.0
    active = sum(len(st.active) for st in base.subsystems.values())
    return active / total


def assault_foe(base: Starbase, config: GameConfig) -> EncounterFoe:
    """Build the set-piece combat foe for assaulting `base` (§4.2, §10 — WP40).

    An immobile all-round emplacement (no arc to slip, no flee) whose hull, shields, and
    damage scale with its surviving component integrity and reactor. A base must be
    operational to defend — a derelict is salvaged/repaired, not fought.
    """
    sbcfg = config.starbase
    assert sbcfg is not None
    klass = config.ship_class(base.ship_class_id)
    integrity = component_integrity(base)
    hull = max(1, round(klass.hull_max * (sbcfg.defense_hull_floor
                                          + (1.0 - sbcfg.defense_hull_floor) * integrity)))
    shields = round(klass.shields_max * integrity)
    weapon = config.weapons[klass.armament[0]] if klass.armament else None
    damage = max(1, round((weapon.damage if weapon is not None else 1) * (0.5 + 0.5 * integrity)))
    defense = sum(d.value for d in klass.defenses
                  if d.type in ("armour", "screens", "energy_plates"))
    return EncounterFoe(
        ship_class_id=klass.id, name=klass.name,
        hull=hull, hull_max=hull, shields=shields, damage=damage,
        firing_arc="all_round", combat_speed=0, defense=defense,
    )
