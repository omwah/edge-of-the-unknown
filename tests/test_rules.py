"""WP3 — command reducers over a tiny hand-built universe (DESIGN §3)."""

from __future__ import annotations

import pytest

from edge.config import load_default_config
from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError, build_subsystems
from edge.core.enums import Commodity, Component, ComponentTier, PortClass, PortMode, Subsystem
from edge.core.events import (
    Banked,
    Colonized,
    ColonistsRecruited,
    ComponentPurchased,
    Docked,
    ShipPurchased,
    Traded,
    Warped,
)
from edge.core.models import (
    Game,
    Ownership,
    Planet,
    Player,
    Port,
    PortCommodity,
    Ship,
    Starbase,
    UniverseState,
)
from edge.core.movement import MovementError
from edge.core.rules import (
    BuyComponent,
    BuyShip,
    Cannibalize,
    Colonize,
    Deposit,
    Dock,
    HaggleOffer,
    InstallComponent,
    RecruitColonists,
    RepairAtDock,
    SetAllocation,
    Trade,
    TravelTo,
    Warp,
    Withdraw,
    apply_result,
    reduce,
)

CONFIG = load_default_config()


def _universe() -> UniverseState:
    """Sectors 1<->2; a StarDock (sells all) sits in sector 2 with the player."""
    game = Game(id=1, seed=1, config_version=1, created_at="2026-06-15T00:00:00Z")
    state = UniverseState.new(game)
    from edge.core.models import Sector

    state.sectors = {
        1: Sector(id=1, region_id=1, warps_out=(2,), distance_band="Hub", is_galactic_core=True),
        2: Sector(id=2, region_id=1, warps_out=(1,), distance_band="Hub", is_galactic_core=True),
    }
    state.rebuild_adjacency()
    state.ports = {
        1: Port(
            id=1, sector_id=2, name="Sol StarDock", klass=PortClass.STARDOCK, size=1,
            commodities=(
                PortCommodity(Commodity.FUEL_ORE, PortMode.SELL, 500, 1000, 11, 5),
                PortCommodity(Commodity.ORGANICS, PortMode.SELL, 500, 1000, 5, 2),
            ),
        )
    }
    state.ships = {
        1: Ship(id=1, type_id="trailblazer", name="S.S. Wayfarer", owner_player_id=1,
                sector_id=2, holds_total=60, turns_per_warp=1, shields=80),
    }
    state.players = {
        1: Player(id=1, name="you", ship_id=1, latinum=10_000, turns_remaining=250),
    }
    return state


def _do(state: UniverseState, command: object) -> object:
    result = reduce(state, 1, command, CONFIG)  # type: ignore[arg-type]
    apply_result(state, result)
    return result


def test_warp_costs_turns_and_records_exploration() -> None:
    from dataclasses import replace

    state = _universe()
    # Move the ship to sector 1 first so we can warp back to 2.
    state.ships[1] = replace(state.ships[1], sector_id=1)
    result = _do(state, Warp(to_sector=2))
    assert isinstance(result.events[0], Warped)  # type: ignore[attr-defined]
    assert state.players[1].turns_remaining == 249
    assert state.ships[1].sector_id == 2
    assert 2 in state.players[1].explored_sectors


def _line_universe() -> UniverseState:
    """Sectors 1<->2<->3<->4 in a line; player starts at 1 with only 1 explored."""
    from edge.core.models import Sector

    game = Game(id=1, seed=1, config_version=1, created_at="2026-06-15T00:00:00Z")
    state = UniverseState.new(game)
    state.sectors = {
        1: Sector(id=1, region_id=1, warps_out=(2,), distance_band="Hub"),
        2: Sector(id=2, region_id=1, warps_out=(1, 3), distance_band="Hub"),
        3: Sector(id=3, region_id=1, warps_out=(2, 4), distance_band="Frontier"),
        4: Sector(id=4, region_id=1, warps_out=(3,), distance_band="Frontier"),
    }
    state.rebuild_adjacency()
    state.ships = {
        1: Ship(id=1, type_id="trailblazer", name="S.S.", owner_player_id=1,
                sector_id=1, holds_total=60, turns_per_warp=1),
    }
    state.players = {
        1: Player(id=1, name="you", ship_id=1, latinum=0, turns_remaining=250,
                  explored_sectors=frozenset({1})),
    }
    return state


def test_warp_records_breadcrumb() -> None:
    state = _line_universe()
    _do(state, Warp(to_sector=2))
    assert dict(state.players[1].entered_from) == {2: 1}
    _do(state, Warp(to_sector=3))
    assert state.players[1].entered_from[3] == 2  # last-entered-from per sector


def test_travel_to_multi_hop_known_route() -> None:
    state = _line_universe()
    _do(state, Warp(to_sector=2))  # uncover the route 1->2->3
    _do(state, Warp(to_sector=3))
    turns = state.players[1].turns_remaining
    result = _do(state, TravelTo(to_sector=1))  # travel back along explored sectors
    assert state.ships[1].sector_id == 1
    assert len(result.events) == 2  # two hops: 3->2, 2->1  # type: ignore[attr-defined]
    assert state.players[1].turns_remaining == turns - 2
    assert state.players[1].entered_from[1] == 2  # crumb updated on the way back


def test_travel_to_rejects_unexplored_route() -> None:
    state = _line_universe()
    _do(state, Warp(to_sector=2))  # explored {1, 2} only
    with pytest.raises(MovementError):
        reduce(state, 1, TravelTo(to_sector=4), CONFIG)  # route past 3/4 not uncovered


def test_travel_to_a_logged_lead_flies_the_full_graph() -> None:
    """A logged coordinate lead is the map (§6.7): TravelTo its destination routes over the
    full graph and charts each hop, while a non-lead unexplored destination is still rejected."""
    from dataclasses import replace

    from edge.core.models import Lead

    state = _line_universe()  # player at 1, explored {1}; line 1-2-3-4
    with pytest.raises(MovementError):
        reduce(state, 1, TravelTo(to_sector=4), CONFIG)  # no lead, route uncharted → rejected

    lead = Lead(kind="discovery", ref=99, sector_id=4, source_species="vesk", summary="a relic")
    state.players[1] = replace(state.players[1], leads=(lead,))
    result = _do(state, TravelTo(to_sector=4))  # the tip's coordinates unlock the course
    assert len(result.events) == 3  # 1->2->3->4, all flown in one engage  # type: ignore[attr-defined]
    assert state.ships[1].sector_id == 4
    assert {2, 3, 4} <= state.players[1].explored_sectors  # the route is charted as it flies


def test_movement_errors_name_the_spatial_id_not_the_internal_one() -> None:
    """Player-facing route/warp errors must speak in spatial ids (§5.1), never internal ones."""
    state = _line_universe()
    state.spatial_ids = {1: 10001, 2: 10002, 3: 10003, 4: 40004}
    _do(state, Warp(to_sector=2))  # explored {1, 2} only
    with pytest.raises(MovementError, match=r"no uncovered route to 40004$"):
        reduce(state, 1, TravelTo(to_sector=4), CONFIG)
    with pytest.raises(MovementError, match=r"no warp from 10002 to 40004$"):
        reduce(state, 1, Warp(to_sector=4), CONFIG)  # 2 and 4 are not adjacent


def test_travel_to_same_sector_and_out_of_turns_are_rejected() -> None:
    from dataclasses import replace

    state = _line_universe()
    with pytest.raises(MovementError):
        reduce(state, 1, TravelTo(to_sector=1), CONFIG)  # already in that sector
    _do(state, Warp(to_sector=2))
    state.players[1] = replace(state.players[1], turns_remaining=0)
    with pytest.raises(MovementError):
        reduce(state, 1, TravelTo(to_sector=1), CONFIG)  # can't afford the first hop


def test_travel_to_stops_partway_when_turns_run_out() -> None:
    from dataclasses import replace

    state = _line_universe()
    _do(state, Warp(to_sector=2))  # uncover 1->2->3
    _do(state, Warp(to_sector=3))
    state.players[1] = replace(state.players[1], turns_remaining=1)  # only one hop's worth
    result = _do(state, TravelTo(to_sector=1))  # 3->2->1 needs two
    assert state.ships[1].sector_id == 2  # halted midway
    assert len(result.events) == 1 and state.players[1].turns_remaining == 0  # type: ignore[attr-defined]


def test_warp_rejects_illegal_and_when_out_of_turns() -> None:
    state = _universe()
    with pytest.raises(MovementError):
        reduce(state, 1, Warp(to_sector=99), CONFIG)
    from dataclasses import replace

    state.players[1] = replace(state.players[1], turns_remaining=0)
    state.ships[1] = replace(state.ships[1], sector_id=1)
    with pytest.raises(MovementError):
        reduce(state, 1, Warp(to_sector=2), CONFIG)


def test_dock_costs_one_turn() -> None:
    state = _universe()
    _do(state, Dock())
    assert state.players[1].turns_remaining == 249
    res = reduce(state, 1, Dock(), CONFIG)
    assert isinstance(res.events[0], Docked)


def test_trade_buy_moves_goods_and_burns_latinum() -> None:
    state = _universe()
    before = state.players[1].latinum
    result = _do(state, Trade(commodity=Commodity.FUEL_ORE, units=10))
    traded = result.events[0]  # type: ignore[attr-defined]
    assert isinstance(traded, Traded)
    assert state.ships[1].cargo[Commodity.FUEL_ORE] == 10
    assert state.ports[1].commodities[0].stock == 490  # 500 - 10
    assert state.players[1].latinum == before - traded.total


def _with_engine_room(state: UniverseState) -> None:
    """Give the docked ship the starter engine room (so install/derive applies)."""
    from dataclasses import replace

    from edge.core.engine_room import apply_derived
    sc = CONFIG.starter_ship
    ship = replace(state.ships[1], type_id=sc.id, subsystems=build_subsystems(sc))
    state.ships[1] = apply_derived(ship, CONFIG)


def test_buy_component_costs_latinum_and_fills_a_hold() -> None:
    state = _universe()
    result = _do(state, BuyComponent(Component.TURBINE, ComponentTier.I))
    assert isinstance(result.events[0], ComponentPurchased)  # type: ignore[attr-defined]
    ship = state.ships[1]
    assert ship.components[(Component.TURBINE, ComponentTier.I)] == 1
    assert state.players[1].latinum == 10_000 - CONFIG.economy.tier_i_component_latinum


def test_buy_component_then_install_raises_derived_aspect() -> None:
    state = _universe()
    _with_engine_room(state)
    warp0 = state.ships[1].warp_speed
    _do(state, BuyComponent(Component.ACCELERATOR, ComponentTier.I))
    empty = state.ships[1].subsystems[Subsystem.SPINDRIVE].slots.index(None)  # type: ignore[index,union-attr]
    _do(state, InstallComponent(Subsystem.SPINDRIVE, empty, Component.ACCELERATOR, ComponentTier.I))
    assert state.ships[1].warp_speed == warp0 + 1  # the new part lifts warp speed


def test_buy_tier_iii_component_rejected() -> None:
    with pytest.raises(EconomyError):
        _do(_universe(), BuyComponent(Component.TURBINE, ComponentTier.III))


def test_buy_ship_swaps_hull_and_carries_cargo() -> None:
    from dataclasses import replace

    state = _universe()
    state.players[1] = replace(state.players[1], latinum=50_000)  # afford the hull
    state.ships[1] = replace(state.ships[1], cargo={Commodity.FUEL_ORE: 5})
    result = _do(state, BuyShip("scout_marauder"))
    assert isinstance(result.events[0], ShipPurchased)  # type: ignore[attr-defined]
    ship = state.ships[1]
    assert ship.type_id == "scout_marauder"
    assert ship.holds_total == CONFIG.ship_class("scout_marauder").holds_total
    assert ship.cargo[Commodity.FUEL_ORE] == 5  # cargo migrated
    assert ship.subsystems is not None  # arrives with the new hull's engine room
    assert state.players[1].latinum == 50_000 - 20_000  # net cost (free starter → 0 trade-in)


def test_buy_ship_refused_when_cargo_exceeds_new_holds() -> None:
    from dataclasses import replace

    state = _universe()
    # Scout Marauder holds only 30; load 40 cargo so the swap can't fit.
    state.ships[1] = replace(state.ships[1], cargo={Commodity.FUEL_ORE: 40})
    with pytest.raises(EconomyError):
        _do(state, BuyShip("scout_marauder"))


def test_buy_ship_requires_stardock() -> None:
    from dataclasses import replace

    state = _universe()
    state.ports[1] = replace(state.ports[1], klass=PortClass.CLASS_1)
    with pytest.raises(EconomyError):
        _do(state, BuyShip("scout_marauder"))


def test_buy_ship_rejects_current_hull_and_unknown() -> None:
    state = _universe()
    with pytest.raises(EconomyError):
        _do(state, BuyShip("trailblazer"))  # already flown (the free starter)
    with pytest.raises(EconomyError):
        _do(state, BuyShip("nonesuch"))


def test_buy_component_needs_latinum_and_a_free_hold() -> None:
    from dataclasses import replace

    poor = _universe()
    poor.players[1] = replace(poor.players[1], latinum=10)
    with pytest.raises(EconomyError):
        _do(poor, BuyComponent(Component.TURBINE, ComponentTier.I))

    full = _universe()
    full.ships[1] = replace(full.ships[1], cargo={Commodity.FUEL_ORE: full.ships[1].holds_total})
    with pytest.raises(EconomyError):
        _do(full, BuyComponent(Component.TURBINE, ComponentTier.I))


def test_repair_at_dock_restores_knocked_out_for_latinum() -> None:
    from dataclasses import replace

    from edge.core.engine_room import apply_derived

    state = _universe()
    _with_engine_room(state)
    sub = state.ships[1].subsystems[Subsystem.THRUSTERS]  # type: ignore[index]
    slots = list(sub.slots)
    slots[1] = replace(slots[1], knocked_out=True)  # type: ignore[arg-type]
    subsystems = {**state.ships[1].subsystems, Subsystem.THRUSTERS: replace(sub, slots=tuple(slots))}  # type: ignore[dict-item]
    state.ships[1] = apply_derived(replace(state.ships[1], subsystems=subsystems), CONFIG)
    combat_damaged = state.ships[1].combat_speed
    lat0 = state.players[1].latinum
    _do(state, RepairAtDock(Subsystem.THRUSTERS, 1))
    assert state.ships[1].combat_speed > combat_damaged  # restored
    assert state.players[1].latinum < lat0  # paid for the repair


def test_repair_at_dock_rejected_when_nothing_damaged() -> None:
    state = _universe()
    _with_engine_room(state)
    with pytest.raises(EngineRoomError):
        _do(state, RepairAtDock(Subsystem.THRUSTERS, 0))


# --- colonists: recruit / colonize / allocation (§4.2, §8) ------------------


def _with_colony_world(state: UniverseState, ptype: str = "terrestrial_warm") -> None:
    """Place an unowned colonizable world in the player's sector (2)."""
    profile = CONFIG.planets.types[ptype]
    state.planets = {1: Planet(
        id=1, sector_id=2, name="New Eden", planet_type=ptype,
        owner=Ownership("none"), habitability_cap=profile.habitability,
    )}


def test_recruit_colonists_at_stardock_pays_incentive() -> None:
    from dataclasses import replace

    state = _universe()
    state.ships[1] = replace(state.ships[1], colonist_capacity=100)
    result = _do(state, RecruitColonists(count=40))
    assert isinstance(result.events[0], ColonistsRecruited)  # type: ignore[attr-defined]
    assert state.ships[1].colonists == 40
    assert state.players[1].latinum == 10_000 - 40 * CONFIG.economy.colonist_incentive


def test_recruit_clamped_to_berths() -> None:
    from dataclasses import replace

    state = _universe()
    state.ships[1] = replace(state.ships[1], colonist_capacity=30)
    _do(state, RecruitColonists(count=100))
    assert state.ships[1].colonists == 30  # the separate occupancy limit caps it


def test_colonize_claims_unowned_world_and_moves_colonists() -> None:
    from dataclasses import replace

    state = _universe()
    state.ships[1] = replace(state.ships[1], colonist_capacity=100, colonists=50)
    _with_colony_world(state)
    result = _do(state, Colonize(planet_id=1, colonists=30))
    assert isinstance(result.events[0], Colonized)  # type: ignore[attr-defined]
    assert state.planets[1].owner == Ownership("player", 1)
    assert state.planets[1].colonists == 30
    assert state.ships[1].colonists == 20  # the rest stay aboard
    assert state.planets[1].allocation  # a default split was set


def test_colonize_rejects_owned_and_uncolonizable() -> None:
    from dataclasses import replace

    state = _universe()
    state.ships[1] = replace(state.ships[1], colonist_capacity=100, colonists=50)
    _with_colony_world(state, "barren")  # uncolonizable
    with pytest.raises(EconomyError):
        _do(state, Colonize(planet_id=1, colonists=10))
    _with_colony_world(state)  # now colonizable but pre-owned
    state.planets[1] = replace(state.planets[1], owner=Ownership("alliance", 1))
    with pytest.raises(EconomyError):
        _do(state, Colonize(planet_id=1, colonists=10))


def test_recruit_emigration_from_inhabited_world_is_free() -> None:
    from dataclasses import replace

    state = _universe()
    state.ships[1] = replace(state.ships[1], colonist_capacity=100)
    state.planets = {1: Planet(1, 2, "Homeworld", "terrestrial_warm", inhabited_by_species_id=7)}
    _do(state, RecruitColonists(count=20, from_planet=1))
    assert state.ships[1].colonists == 20
    assert state.players[1].latinum == 10_000  # emigration costs no incentive


def test_recruit_rejects_nonpositive_and_no_berths() -> None:
    from dataclasses import replace

    state = _universe()
    state.ships[1] = replace(state.ships[1], colonist_capacity=0)
    with pytest.raises(EconomyError):
        _do(state, RecruitColonists(count=5))  # no berths
    state.ships[1] = replace(state.ships[1], colonist_capacity=10)
    with pytest.raises(EconomyError):
        _do(state, RecruitColonists(count=0))  # non-positive


def test_colonize_requires_colonists_and_presence() -> None:
    from dataclasses import replace

    state = _universe()
    state.ships[1] = replace(state.ships[1], colonist_capacity=100, colonists=5)
    _with_colony_world(state)
    with pytest.raises(EconomyError):
        _do(state, Colonize(planet_id=1, colonists=10))  # more than aboard
    state.ships[1] = replace(state.ships[1], sector_id=1)  # leave the planet's sector
    with pytest.raises(EconomyError):
        _do(state, Colonize(planet_id=1, colonists=1))


def test_buy_ship_refused_when_colonists_exceed_new_berths() -> None:
    from dataclasses import replace

    state = _universe()
    state.players[1] = replace(state.players[1], latinum=60_000)
    state.ships[1] = replace(state.ships[1], colonist_capacity=100, colonists=80)
    with pytest.raises(EconomyError):  # Scout Marauder berths only 50
        _do(state, BuyShip("scout_marauder"))


def test_set_allocation_normalizes_and_requires_ownership() -> None:
    from dataclasses import replace

    state = _universe()
    state.ships[1] = replace(state.ships[1], colonist_capacity=100, colonists=50)
    _with_colony_world(state)
    _do(state, Colonize(planet_id=1, colonists=30))
    _do(state, SetAllocation(planet_id=1, allocation={"fuel_ore": 1.0, "organics": 3.0}))
    alloc = state.planets[1].allocation
    assert abs(sum(alloc.values()) - 1.0) < 1e-9  # normalized to a unit split
    assert alloc[Commodity.ORGANICS] == 0.75
    # an all-zero allocation is rejected (must be positive)
    with pytest.raises(EconomyError):
        _do(state, SetAllocation(planet_id=1, allocation={"fuel_ore": 0.0}))
    # a world the player does not own is rejected
    state.planets[1] = replace(state.planets[1], owner=Ownership("alliance", 1))
    with pytest.raises(EconomyError):
        _do(state, SetAllocation(planet_id=1, allocation={"fuel_ore": 1.0}))


def test_bank_deposit_then_withdraw() -> None:
    state = _universe()
    _do(state, Deposit(amount=1_000))
    assert (state.players[1].latinum, state.players[1].bank_balance) == (9_000, 1_000)
    result = _do(state, Withdraw(amount=400))
    assert isinstance(result.events[0], Banked)  # type: ignore[attr-defined]
    assert (state.players[1].latinum, state.players[1].bank_balance) == (9_400, 600)


def test_haggle_is_deterministic_from_seed() -> None:
    a = _universe()
    b = _universe()
    cmd = HaggleOffer(commodity=Commodity.FUEL_ORE, units=5, counter_price=10)
    ra = reduce(a, 1, cmd, CONFIG)
    rb = reduce(b, 1, cmd, CONFIG)
    # Same seed -> same haggle resolution (status + any resulting trade).
    assert [type(e) for e in ra.events] == [type(e) for e in rb.events]


def test_buy_component_requires_stardock() -> None:
    state = _universe()
    from dataclasses import replace

    state.ports[1] = replace(state.ports[1], klass=PortClass.CLASS_1)
    with pytest.raises(EconomyError):
        reduce(state, 1, BuyComponent(Component.TURBINE, ComponentTier.I), CONFIG)


def test_unknown_player_rejected() -> None:
    with pytest.raises(MovementError):
        reduce(_universe(), 99, Dock(), CONFIG)


def test_dock_and_trade_require_a_port() -> None:
    from dataclasses import replace

    state = _universe()
    state.ships[1] = replace(state.ships[1], sector_id=1)  # sector 1 has no port
    with pytest.raises(MovementError):
        reduce(state, 1, Dock(), CONFIG)
    with pytest.raises(MovementError):
        reduce(state, 1, Trade(commodity=Commodity.FUEL_ORE, units=1), CONFIG)


# --- WP4: orbital starbase salvage (§4.2) -----------------------------------


def _with_starbase(state: UniverseState, *, derelict: bool, owner: Ownership) -> Starbase:
    """Hang a base off a planet in the player's sector (2); return the base."""
    from dataclasses import replace as _replace

    from edge.core.engine_room import build_layouts
    from edge.core.enums import Subsystem

    assert CONFIG.starbase is not None
    subs = build_layouts(CONFIG.starbase.subsystems)
    if derelict:
        reactor = subs[Subsystem.FUSION_REACTOR]
        slots = list(reactor.slots)
        slots[reactor.keystone_index] = None  # strip the keystone → derelict
        subs[Subsystem.FUSION_REACTOR] = _replace(reactor, slots=tuple(slots))
    base = Starbase(id=1, sector_id=2, planet_id=1, ship_class_id="orbital_platform",
                    owner=owner, subsystems=subs)
    state.starbases = {1: base}
    state.planets = {1: Planet(1, 2, "World", "barren", starbase_id=1)}
    return base


def _first_filled(base: Starbase) -> tuple[object, int]:
    from edge.core.enums import Subsystem  # noqa: F401

    for subsystem, sub in base.subsystems.items():
        for idx, comp in enumerate(sub.slots):
            if comp is not None:
                return subsystem, idx
    raise AssertionError("no filled slot")


def test_salvage_derelict_starbase_conserves_components() -> None:
    state = _universe()
    base = _with_starbase(state, derelict=True, owner=Ownership("none"))
    subsystem, idx = _first_filled(base)
    before = sum(state.ships[1].components.values())
    _do(state, Cannibalize(subsystem=subsystem, slot_index=idx, starbase_id=1))  # type: ignore[arg-type]
    after = sum(state.ships[1].components.values())
    assert after == before + 1  # the ship gained exactly what the base lost
    assert state.starbases[1].subsystems[subsystem].slots[idx] is None


def test_salvage_operational_starbase_rejected() -> None:
    state = _universe()
    base = _with_starbase(state, derelict=False, owner=Ownership("alliance", 1))
    subsystem, idx = _first_filled(base)
    with pytest.raises(EngineRoomError):
        reduce(state, 1, Cannibalize(subsystem=subsystem, slot_index=idx, starbase_id=1), CONFIG)


def test_salvage_player_owned_operational_base_allowed() -> None:
    state = _universe()
    base = _with_starbase(state, derelict=False, owner=Ownership("player", 1))
    subsystem, idx = _first_filled(base)
    _do(state, Cannibalize(subsystem=subsystem, slot_index=idx, starbase_id=1))  # type: ignore[arg-type]
    assert state.starbases[1].subsystems[subsystem].slots[idx] is None


def test_salvage_requires_base_in_sector() -> None:
    from dataclasses import replace

    state = _universe()
    base = _with_starbase(state, derelict=True, owner=Ownership("none"))
    subsystem, idx = _first_filled(base)
    state.ships[1] = replace(state.ships[1], sector_id=1)  # leave the base's sector
    with pytest.raises(EngineRoomError):
        reduce(state, 1, Cannibalize(subsystem=subsystem, slot_index=idx, starbase_id=1), CONFIG)
