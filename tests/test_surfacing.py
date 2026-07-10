"""WP71 — surfacing pass 1: the projection seams behind the new TUI affordances.

The starbase assault/repair/claim affordances on the planet screen, and the StarDock
bank tab, all read new projection fields (`PlanetDTO.base_*`, `StarDockDTO.bank_*`);
these tests pin that seam. The commands themselves (AssaultStarbase / RepairStarbase /
ClaimStarbase / Deposit / Withdraw / DeliverContract / AbandonContract / RepairAtDock /
SwapComponent / FieldPatch) are covered by their WP40/WP53/WP57 suites.
"""

from __future__ import annotations

from dataclasses import replace

from edge.config import load_default_config
from edge.core.engine_room import build_layouts
from edge.core.enums import Subsystem
from edge.core.models import (
    Game,
    Ownership,
    Planet,
    Player,
    Sector,
    Ship,
    Starbase,
    SubsystemState,
    UniverseState,
)
from edge.core.rules import RepairStarbase, apply_result, reduce
from edge.core.starbases import is_operational
from edge.server.session import planet_view, stardock_view

CFG = load_default_config()


def _base_subsystems(*, operational: bool) -> dict[Subsystem, SubsystemState]:
    layouts = build_layouts(CFG.starbase.subsystems)
    if not operational:
        reactor = layouts[Subsystem.FUSION_REACTOR]
        slots = list(reactor.slots)
        slots[reactor.keystone_index] = None  # strip the keystone → derelict
        layouts[Subsystem.FUSION_REACTOR] = replace(reactor, slots=tuple(slots))
    return layouts


def _state(*, base_owner: Ownership, operational: bool) -> UniverseState:
    game = Game(id=1, seed=1, config_version=CFG.config_version,
                created_at="1970-01-01T00:00:00Z", core_governing_alliance_id=1)
    state = UniverseState.new(game)
    state.sectors[1] = Sector(id=1, region_id=1, warps_out=(), distance_band="Frontier")
    state.rebuild_adjacency()
    state.planets[1] = Planet(id=1, sector_id=1, name="P", planet_type="barren",
                              owner=base_owner, starbase_id=1)
    state.starbases[1] = Starbase(
        id=1, sector_id=1, planet_id=1, ship_class_id="orbital_platform",
        owner=base_owner, subsystems=_base_subsystems(operational=operational))
    state.ships[1] = Ship(id=1, type_id="trailblazer", name="T", owner_player_id=1,
                          sector_id=1, holds_total=20, hull_current=200, hull_max=200,
                          shields=100, warp_speed=3, combat_speed=3, turns_per_warp=1)
    state.players[1] = Player(id=1, name="T", ship_id=1, latinum=100_000,
                              turns_remaining=100, bank_balance=2_500)
    return state


def test_derelict_base_projects_repair_affordance_keystone_first() -> None:
    state = _state(base_owner=Ownership("none"), operational=False)
    p = planet_view(state, 1, 1, CFG)
    assert p.starbase_derelict and not p.base_assaultable and not p.base_claimable
    assert p.base_empty_slots, "a stripped keystone must surface as an open slot"
    subsystem, slot_index, is_keystone = p.base_empty_slots[0]
    assert is_keystone and subsystem == Subsystem.FUSION_REACTOR.value


def test_repairing_the_keystone_flips_the_base_claimable() -> None:
    state = _state(base_owner=Ownership("none"), operational=False)
    p = planet_view(state, 1, 1, CFG)
    subsystem, slot_index, _ = p.base_empty_slots[0]
    reactor = state.starbases[1].subsystems[Subsystem.FUSION_REACTOR]
    keystone = build_layouts(CFG.starbase.subsystems)[Subsystem.FUSION_REACTOR] \
        .slots[reactor.keystone_index]
    assert keystone is not None
    state.ships[1] = replace(state.ships[1], components={(keystone.kind, keystone.tier): 1})
    apply_result(state, reduce(state, 1, RepairStarbase(
        1, Subsystem(subsystem), slot_index, keystone.kind, keystone.tier), CFG))
    assert is_operational(state.starbases[1])
    p2 = planet_view(state, 1, 1, CFG)
    assert p2.base_claimable and not p2.starbase_derelict
    assert p2.base_claim_cost == CFG.starbase.claim_cost


def test_operational_foreign_base_projects_assault_not_repair() -> None:
    state = _state(base_owner=Ownership("alliance", 2), operational=True)
    p = planet_view(state, 1, 1, CFG)
    assert p.base_assaultable and not p.base_claimable
    assert p.base_empty_slots == []  # an operational foreign base is not yours to refit


def test_stardock_view_exposes_the_bank_counter() -> None:
    state = _state(base_owner=Ownership("none"), operational=False)
    dock = stardock_view(state, 1, CFG)
    assert dock.bank_balance == 2_500
    assert dock.interest_per_day == CFG.economy.bank_interest_per_day > 0
