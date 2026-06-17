"""Derived ship aspects from slotted subsystems (DESIGN §4.1) — pure core.

The engine-room model makes a player hull's `shields` / `warp_speed` /
`combat_speed` / `turns_per_warp` plus its main-gun damage/rate and one global
combat bonus **derived** from the components filling four subsystems, rather than
flat scalars. `derive_aspects` is the single formula; the reducers in `core.rules`
call `apply_derived` to write the derived scalars back onto the `Ship` whenever a
slot changes (derive-on-write), so everything downstream keeps reading plain
aspect fields and `state_hash` stays a function of stored values.

No I/O, no randomness — a pure function of `(ship, config)` (CLAUDE.md).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from edge.core.config import AspectFormula, EngineRoomConfig, GameConfig, ShipClassConfig
from edge.core.enums import Component, ComponentTier, Subsystem
from edge.core.models import InstalledComponent, Ship, SubsystemState


class EngineRoomError(Exception):
    """An invalid engine-room operation (illegal slot, wrong tier, missing part)."""


@dataclass(frozen=True, slots=True)
class ShipAspects:
    """The scalars derived from a hull's slotted subsystems (DESIGN §4.1)."""

    shields: int
    warp_speed: int
    combat_speed: int
    turns_per_warp: int
    gun_damage: int
    gun_rate: int
    efficiency_bonus: int  # the one global combat bonus from spindrive efficiency


def build_subsystems(klass: ShipClassConfig) -> dict[Subsystem, SubsystemState] | None:
    """Instantiate a hull's starting subsystems from its config layout (§4.1).

    Base components fill the first slots at Tier I (index 0 = keystone); the rest
    start empty. Returns `None` for a hull with no engine room (an NPC flat hull).
    """
    if klass.subsystems is None:
        return None
    built: dict[Subsystem, SubsystemState] = {}
    for name, layout in klass.subsystems.items():
        filled: list[InstalledComponent | None] = [
            InstalledComponent(Component(c), ComponentTier.I) for c in layout.base_components
        ]
        filled.extend([None] * (layout.slot_count - len(layout.base_components)))
        keystone_index = layout.base_components.index(layout.keystone)
        built[Subsystem(name)] = SubsystemState(slots=tuple(filled), keystone_index=keystone_index)
    return built


def _apply(formula: AspectFormula, active: int, tier_bonus: int) -> int:
    return round(formula.base + formula.per_component * active + formula.per_tier * tier_bonus)


def _counts(sub: SubsystemState) -> tuple[int, int]:
    """(active component count, summed tier bonus) for a subsystem's filled slots."""
    active = sub.active
    return len(active), sum(c.tier.value - 1 for c in active)


def derive_aspects(ship: Ship, config: GameConfig) -> ShipAspects:
    """Compute the derived scalars for `ship` from its subsystems (§4.1).

    A hull with no engine room (`subsystems is None`) returns its flat scalars
    unchanged — the NPC fallback — with no main-gun/efficiency contribution.
    """
    if ship.subsystems is None:
        return ShipAspects(
            shields=ship.shields, warp_speed=ship.warp_speed, combat_speed=ship.combat_speed,
            turns_per_warp=ship.turns_per_warp, gun_damage=0, gun_rate=0, efficiency_bonus=0,
        )
    er = config.engine_room

    def aspect(subsystem: Subsystem) -> int:
        sub = ship.subsystems[subsystem]  # type: ignore[index]
        active, tier_bonus = _counts(sub)
        return _apply(er.aspects[subsystem.value], active, tier_bonus)

    warp_speed = aspect(Subsystem.SPINDRIVE)
    combat_speed = aspect(Subsystem.THRUSTERS)
    shields = aspect(Subsystem.SCREENS)
    gun_damage = aspect(Subsystem.MAIN_GUN)

    gun_active, _ = _counts(ship.subsystems[Subsystem.MAIN_GUN])
    gun_rate = er.gun_rate_base + (gun_active // er.gun_rate_step if er.gun_rate_step else 0)

    spin_active, spin_tier_bonus = _counts(ship.subsystems[Subsystem.SPINDRIVE])
    efficiency_bonus = max(0, _apply(er.efficiency, spin_active, spin_tier_bonus))

    turns_per_warp = max(1, round(er.warp_turn_divisor / warp_speed)) if warp_speed > 0 else ship.turns_per_warp
    return ShipAspects(
        shields=shields, warp_speed=warp_speed, combat_speed=combat_speed,
        turns_per_warp=turns_per_warp, gun_damage=gun_damage, gun_rate=gun_rate,
        efficiency_bonus=efficiency_bonus,
    )


def apply_derived(ship: Ship, config: GameConfig) -> Ship:
    """Return `ship` with its stored aspect scalars refreshed from its subsystems.

    A no-op for an NPC flat hull (derive returns the same scalars). This is the
    derive-on-write seam the reducers call after every slot mutation (§4.1).
    """
    a = derive_aspects(ship, config)
    return replace(
        ship, shields=a.shields, warp_speed=a.warp_speed,
        combat_speed=a.combat_speed, turns_per_warp=a.turns_per_warp,
    )


def legal_components(klass: ShipClassConfig, subsystem: Subsystem) -> frozenset[Component]:
    """The components installable into `subsystem` on this hull (config layout)."""
    if klass.subsystems is None or subsystem.value not in klass.subsystems:
        return frozenset()
    return frozenset(Component(c) for c in klass.subsystems[subsystem.value].legal_components)


def tier_ceiling(er: EngineRoomConfig) -> ComponentTier:
    """The highest installable component tier (config), as a `ComponentTier`."""
    return ComponentTier[er.tier_ceiling]
