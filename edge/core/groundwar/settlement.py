"""Strategic reconciliation for tactical planetary assaults (GW-WP11).

The POC ends when its mutable ``Battle.outcome`` is chosen. Production must take
the next, atomic step: return surviving recruits/suits/ordnance, persist every
defender and structure loss, apply civilian harm, and settle surrender into
conquest or a retained native protectorate. This module is pure over frozen core
snapshots; ``edge.core.rules`` owns event emission and diplomatic side effects.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, replace

from edge.core import citadels
from edge.core.config import GameConfig
from edge.core.groundwar import assault, force, world
from edge.core.groundwar.models import AssaultOperation
from edge.core.models import Ownership, Planet, Ship
from edge.core.planets import scale_population


class SettlementError(Exception):
    """The active assault cannot be reconciled against the supplied strategic state."""


@dataclass(frozen=True, slots=True)
class AssaultSettlement:
    """All strategic deltas produced by settling one assault exactly once."""

    planet: Planet
    ship: Ship
    outcome: str
    attacker_losses: int
    attacker_survivors: int
    missiles_spent: int
    defender_losses: int
    defender_infantry: int
    defender_armor: int
    civilian_losses: int
    civilian_structures_destroyed: int
    loot: int
    control: str


def _destroyed(op: AssaultOperation, amap: assault.AssaultMap) -> dict[tuple[int, int], str]:
    """Every levelled structure as `position -> kind` (GW-WP19).

    Positional, because a world's ground layout is now one stable identity shared with
    its survey map: what fell can be recorded where it stood, so the next assault
    reopens the same breach and an expedition paints the same ruin.

    GW-WP25: **every cell** of a levelled structure is recorded, not just its anchor.
    A structure has one HP pool over its whole footprint, so a razed depot must leave
    a depot-shaped ruin — writing the anchor alone would have a survey walk through
    the rest of the rubble as if the building were still standing there.
    """
    return {
        cell: structure.kind for structure in amap.structures
        if op.structure_hp.get(structure.id, structure.hp_max) <= 0
        for cell in structure.cells
    }


def _surviving_defenders(op: AssaultOperation) -> tuple[int, int]:
    infantry = op.infantry_remaining + sum(
        unit.kind == "infantry" for unit in op.garrison_units)
    armor = op.armor_remaining + sum(unit.kind == "armor" for unit in op.garrison_units)
    return max(0, infantry), max(0, armor)


def _settle_ship(ship: Ship, op: AssaultOperation, config: GameConfig) -> tuple[Ship, int, int, int]:
    losses = Counter(t.suit_id for t in op.platoon if t.hp <= 0)
    survivors = sum(t.hp > 0 for t in op.platoon)
    returned_missiles = sum(t.missiles for t in op.platoon if t.hp > 0)
    new_ship = force.apply_casualties(ship, losses, config)
    magazine = max(0, ship.ground_missiles - op.ground_missiles_committed + returned_missiles)
    new_ship = replace(
        new_ship,
        ground_missiles=min(magazine, force.missile_capacity(new_ship, config)),
    )
    spent = max(0, ship.ground_missiles - new_ship.ground_missiles)
    return new_ship, sum(losses.values()), survivors, spent


def settle_assault(
    planet: Planet, ship: Ship, op: AssaultOperation, *, player_id: int,
    corp_id: int | None, day: int, config: GameConfig,
) -> AssaultSettlement:
    """Reconcile an extracted/ended assault into ship and planet state.

    A pre-drop abort is mutation-free. Once dropped, every result persists tactical
    attrition. Only ``surrender`` changes sovereignty: an unowned native polity
    becomes a protectorate; every owned enemy world is conquered by the attacking
    player or corporation. All surviving attackers retrieve to the ship.
    """
    if config.groundwar is None or config.citadels is None:
        raise SettlementError("ground assault settlement is not configured")
    if op.planet_id != planet.id or op.sector_id != planet.sector_id:
        raise SettlementError("the assault no longer matches this world")
    if not op.dropped:
        return AssaultSettlement(
            planet, ship, "aborted", 0, 0, 0, 0,
            planet.garrison_infantry, planet.garrison_armor, 0, 0, 0, "none")

    amap = assault.assault_map_for_state(op, config)
    # Damage folds in by position (GW-WP19): a wall already rubble when the platoon
    # dropped stays one entry, and only *newly* levelled civilian blocks charge civilian
    # harm — the pre-GW-WP19 per-kind counters could only approximate that with a max().
    persistent, fresh = world.merged_rubble(planet, _destroyed(op, amap))
    new_civilian_structures = fresh["building_civilian"]
    population_before = planet.colonists
    survival = max(
        0.0,
        1.0 - config.groundwar.settlement.civilian_loss_per_structure
        * new_civilian_structures,
    )
    population_after = round(population_before * survival)
    battered = replace(
        planet,
        population=scale_population(planet.population, population_before, population_after),
        ground_rubble=persistent,
        ground_resolve=max(0, min(config.groundwar.resolve.cap, op.resolve)),
        ground_last_assault_day=day,
    )
    infantry, armor = _surviving_defenders(op)
    defender_losses = max(
        0, op.reserved_infantry + op.reserved_armor - infantry - armor)
    battered = replace(
        battered, garrison_infantry=infantry, garrison_armor=armor)
    new_ship, attacker_losses, attacker_survivors, missiles_spent = _settle_ship(
        ship, op, config)

    outcome = op.outcome or "extracted"
    control = "none"
    loot = 0
    if outcome == "surrender":
        controller = Ownership("corp", corp_id) if corp_id is not None else Ownership("player", player_id)
        if not battered.owner.is_owned:
            battered = replace(
                battered,
                protectorate_controller=controller,
                protectorate_since=day,
                citadel_level=max(0, battered.citadel_level - 1),
                gun_integrity=0,
            )
            control = "protectorate"
        else:
            battered, loot = citadels.settle_tactical_conquest(
                battered, controller, infantry, armor, config)
            control = "conquest"

    return AssaultSettlement(
        planet=battered,
        ship=new_ship,
        outcome=outcome,
        attacker_losses=attacker_losses,
        attacker_survivors=attacker_survivors,
        missiles_spent=missiles_spent,
        defender_losses=defender_losses,
        defender_infantry=infantry,
        defender_armor=armor,
        civilian_losses=population_before - battered.colonists,
        civilian_structures_destroyed=new_civilian_structures,
        loot=loot,
        control=control,
    )


def annex_ready(planet: Planet, player_id: int, corp_id: int | None, day: int,
                config: GameConfig) -> str | None:
    """Return the D14 blocker for annexing ``planet``, or ``None`` when legal."""
    if config.groundwar is None:
        return "ground operations are not configured"
    controller = planet.protectorate_controller
    controls = ((controller.kind == "player" and controller.ref == player_id)
                or (controller.kind == "corp" and controller.ref == corp_id))
    if not controls or planet.protectorate_since is None:
        return "you do not control a protectorate here"
    if planet.owner.is_owned:
        return "this world is already sovereign territory"
    age = day - planet.protectorate_since
    if age < config.groundwar.settlement.protectorate_min_days:
        return (f"protectorate must stand for {config.groundwar.settlement.protectorate_min_days} "
                f"days ({age} elapsed)")
    resolve = planet.ground_resolve if planet.ground_resolve is not None else config.groundwar.resolve.start
    if resolve < config.groundwar.settlement.annex_resolve_threshold:
        return (f"planetary Resolve must recover to "
                f"{config.groundwar.settlement.annex_resolve_threshold} ({resolve} now)")
    return None


def annex(planet: Planet) -> Planet:
    """Convert a ready protectorate into its controller's ordinary ownership."""
    if not planet.protectorate_controller.is_owned:
        raise SettlementError("this world is not a protectorate")
    return replace(
        planet,
        owner=planet.protectorate_controller,
        protectorate_controller=Ownership("none"),
        protectorate_since=None,
        stores={
            commodity: planet.stores.get(commodity, 0)
            + planet.protectorate_stores.get(commodity, 0)
            for commodity in set(planet.stores) | set(planet.protectorate_stores)
        },
        protectorate_stores={},
    )


def consequence_units(defender_losses: int, config: GameConfig) -> int:
    """Scale headcount casualties onto the existing per-kill diplomacy economy."""
    if defender_losses <= 0 or config.groundwar is None:
        return 0
    return max(1, math.ceil(
        defender_losses / config.groundwar.settlement.defenders_per_consequence))
