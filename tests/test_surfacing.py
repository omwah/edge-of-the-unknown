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
from edge.core.rules import AdvanceAdmission, RepairStarbase, apply_result, reduce
from edge.core.starbases import is_operational
from edge.server.session import computer_view, planet_view, stardock_view, territory_view

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


# --- WP72: territory/devices + alliances projections --------------------------------


def test_territory_view_reports_stock_devices_and_own_force() -> None:
    from edge.core.models import SectorForce
    state = _state(base_owner=Ownership("none"), operational=False)
    state.ships[1] = replace(
        state.ships[1], fighters=12, mines=4, devices={"probe": 2, "interdictor": 1},
        limpets={"alliance:2": 3}, interdictor_active=True)
    state.sector_forces[1] = SectorForce(
        sector_id=1, owner=Ownership("player", 1), fighters=8, mode="toll", toll=25,
        armid_mines=2)
    t = territory_view(state, 1, CFG)
    assert (t.fighters, t.mines, t.probes) == (12, 4, 2)
    assert t.interdictor_owned and t.interdictor_active
    assert t.limpets == 3 and t.limpet_removal_fee == CFG.territory.limpet_removal_fee
    assert "8 fighters (toll, toll 25)" in t.force_line and "2 armid mines" in t.force_line
    assert not t.in_core
    assert not t.at_service_point  # no StarDock / owned base here


def test_alliance_rows_project_membership_admission_and_governor() -> None:
    from edge.core.models import Alliance
    state = _state(base_owner=Ownership("none"), operational=False)
    state.alliances = {
        1: Alliance(id=1, name="Terran Federation"),
        2: Alliance(id=2, name="Verdant Compact"),
        4: Alliance(id=4, name="Liberty Front", covets_core=True),
    }
    state.players[1] = replace(state.players[1], alliance_id=1,
                               alliance_standing={1: 1.0, 2: -0.25})
    rows = {r.alliance_id: r for r in computer_view(state, 1, CFG).alliances}
    fed, compact, front = rows[1], rows[2], rows[4]
    assert fed.member and fed.governs_core and not fed.joinable
    assert front.covets_core and front.joinable  # open gate, fee 0
    # Verdant Compact petitions behind a task price — unmet, so barred.
    assert compact.gate == "petition" and not compact.joinable
    assert compact.tasks_needed == ["prove"] and compact.tasks_done == []
    assert compact.standing == -0.25
    # Recording the admission task through the WP38 seam opens the gate.
    apply_result(state, reduce(state, 1, AdvanceAdmission(2, "prove"), CFG))
    rows2 = {r.alliance_id: r for r in computer_view(state, 1, CFG).alliances}
    assert rows2[2].tasks_done == ["prove"] and rows2[2].joinable


# --- WP73: captain's notes + the route-planner avoid list ---------------------------


def _linear_world() -> UniverseState:
    """Sectors 1—2—3 in a line plus a 1—4—3 detour, all explored."""
    game = Game(id=1, seed=1, config_version=CFG.config_version,
                created_at="1970-01-01T00:00:00Z", core_governing_alliance_id=1)
    state = UniverseState.new(game)
    state.sectors = {
        1: Sector(1, 1, (2, 4), "Frontier"),
        2: Sector(2, 1, (1, 3), "Frontier"),
        3: Sector(3, 1, (2, 4), "Frontier"),
        4: Sector(4, 1, (1, 3), "Frontier"),
    }
    state.rebuild_adjacency()
    state.ships[1] = Ship(id=1, type_id="trailblazer", name="T", owner_player_id=1,
                          sector_id=1, holds_total=20, hull_current=200, hull_max=200,
                          shields=100, warp_speed=3, combat_speed=3, turns_per_warp=1)
    state.players[1] = Player(id=1, name="T", ship_id=1, latinum=100, turns_remaining=100,
                              explored_sectors=frozenset({1, 2, 3, 4}))
    return state


def test_notes_ring_appends_sanitizes_and_removes() -> None:
    from edge.core.rules import AddNote, RemoveNote
    state = _linear_world()
    apply_result(state, reduce(state, 1, AddNote(text="  buy ore at S2\x00  "), CFG))
    apply_result(state, reduce(state, 1, AddNote(text="quill pack near S9"), CFG))
    assert state.players[1].notes == ("buy ore at S2", "quill pack near S9")
    view = computer_view(state, 1, CFG)
    assert view.notes == ["buy ore at S2", "quill pack near S9"]
    apply_result(state, reduce(state, 1, RemoveNote(index=0), CFG))
    assert state.players[1].notes == ("quill pack near S9",)


def test_avoid_list_reroutes_but_never_blocks_endpoints() -> None:
    from edge.core.rules import ToggleAvoid
    from edge.server.session import route_view
    state = _linear_world()
    direct = route_view(state, 1, 3, CFG)
    assert len(direct.hops) == 2  # 1→2→3
    apply_result(state, reduce(state, 1, ToggleAvoid(sector_id=2), CFG))
    rerouted = route_view(state, 1, 3, CFG)
    assert rerouted.reachable
    assert [h.display_id for h in rerouted.hops] == [4, 3]  # detoured around 2
    # An avoided *destination* is still plottable — the endpoint override.
    to_avoided = route_view(state, 1, 2, CFG)
    assert to_avoided.reachable and len(to_avoided.hops) == 1
    # Toggling again clears it.
    apply_result(state, reduce(state, 1, ToggleAvoid(sector_id=2), CFG))
    assert state.players[1].avoid_sectors == frozenset()


# --- WP76: corp projections for the completed T screen -------------------------------


def test_corp_view_carries_invite_ids_and_other_corps() -> None:
    from edge.core.models import Corporation
    from edge.server.session import corp_view
    state = _linear_world()
    state.players[2] = replace(state.players[1], id=2, name="Rival")
    state.corporations = {
        1: Corporation(id=1, name="Edge Haulage", tag="EDGE", ceo_player_id=1,
                       member_player_ids=frozenset({1})),
        2: Corporation(id=2, name="Void Syndicate", tag="VOID", ceo_player_id=2,
                       member_player_ids=frozenset({2}), invited_player_ids=frozenset({3})),
    }
    state.players[1] = replace(state.players[1], corp_id=1)
    view = corp_view(state, 1, CFG)
    assert view is not None and view.corp_id == 1
    assert view.other_corps == [(2, "VOID — Void Syndicate")]
    # A corpless-but-invited player sees the invite with its accept id.
    state.players[3] = replace(state.players[2], id=3, name="Free", corp_id=None)
    invited = corp_view(state, 3, CFG)
    assert invited is not None and invited.corp_id == 0
    assert invited.invite_ids == [2] and invited.invites == ["VOID — Void Syndicate"]


# --- §4.2 cargo transfer: the citadel bootstrap fix ----------------------------------


def test_cargo_transfer_breaks_the_citadel_bootstrap_deadlock() -> None:
    """A citadel draws equipment from planet *stores*, which production alone fills too
    slowly (and no hull carries a level's worth) — hauling cargo to your own world in
    trips is the intended loop, and it was missing entirely."""
    from edge.core.enums import Commodity
    from edge.core.events import CargoTransferred
    from edge.core.rules import BuildCitadel, TransferCargo

    state = _linear_world()
    lc = CFG.citadels.levels[0]
    state.planets[1] = Planet(id=1, sector_id=1, name="Home", planet_type="terrestrial_warm",
                              owner=Ownership("player", 1), colonists=lc.min_colonists)
    state.ships[1] = replace(state.ships[1], holds_total=120,
                             cargo={Commodity.EQUIPMENT: 120})
    state.players[1] = replace(state.players[1], latinum=lc.cost_latinum)
    # Trip one: "unload all" (a big number — the reducer clamps to what's aboard).
    result = reduce(state, 1, TransferCargo(1, Commodity.EQUIPMENT, 10**9), CFG)
    apply_result(state, result)
    moved = next(e for e in result.events if isinstance(e, CargoTransferred))
    assert moved.units == 120 and moved.to_planet
    assert state.planets[1].stores[Commodity.EQUIPMENT] == 120
    assert state.ships[1].cargo[Commodity.EQUIPMENT] == 0
    # Trip two tops the stores up to the level cost; the build then opens.
    state.ships[1] = replace(state.ships[1],
                             cargo={Commodity.EQUIPMENT: lc.cost_equipment - 120})
    apply_result(state, reduce(state, 1, TransferCargo(1, Commodity.EQUIPMENT, 10**9), CFG))
    apply_result(state, reduce(state, 1, BuildCitadel(planet_id=1), CFG))
    assert state.planets[1].citadel_progress == 0  # the timed build is open
    assert state.planets[1].stores.get(Commodity.EQUIPMENT, 0) == 0  # paid from stores
    # Loading back out is clamped by the free holds (goods conserved both ways).
    state.planets[1] = replace(state.planets[1],
                               stores={Commodity.EQUIPMENT: 50})
    apply_result(state, reduce(
        state, 1, TransferCargo(1, Commodity.EQUIPMENT, 10**9, to_planet=False), CFG))
    assert state.ships[1].cargo[Commodity.EQUIPMENT] == 50
    assert state.planets[1].stores[Commodity.EQUIPMENT] == 0


# --- sector presence: starbases + forces with classic-TW fog -------------------------


def test_sector_projects_starbase_and_forces_with_classic_fog() -> None:
    from edge.core.models import Region, SectorForce
    from edge.server.session import game_view

    state = _state(base_owner=Ownership("alliance", 2), operational=True)
    state.regions[1] = Region(id=1, name="Testspace")  # game_view resolves the region name
    # A foreign force with fighters AND mines: fighters announce themselves,
    # the mines stay silent (classic TW fog).
    state.sector_forces[1] = SectorForce(
        sector_id=1, owner=Ownership("alliance", 2), fighters=6, mode="toll", toll=25,
        armid_mines=3, limpet_mines=1)
    state.players[1] = replace(state.players[1], explored_sectors=frozenset({1}))
    sec = game_view(state, 1, CFG).sector
    assert len(sec.starbases) == 1
    base = sec.starbases[0]
    assert base.operational and base.planet_id == 1 and base.owner != "yours"
    force = sec.force
    assert force is not None and not force.yours
    assert force.fighters == 6 and force.mode == "toll" and force.toll == 25
    assert force.armid_mines == 0 and force.limpet_mines == 0  # fogged — not yours
    # Your own force projects its mines in full.
    state.sector_forces[1] = SectorForce(
        sector_id=1, owner=Ownership("player", 1), fighters=0, armid_mines=3, limpet_mines=1)
    force = game_view(state, 1, CFG).sector.force
    assert force is not None and force.yours
    assert force.armid_mines == 3 and force.limpet_mines == 1
    # A foreign mines-only force is invisible — you find it by hitting it.
    state.sector_forces[1] = SectorForce(
        sector_id=1, owner=Ownership("alliance", 2), fighters=0, armid_mines=3)
    assert game_view(state, 1, CFG).sector.force is None


def test_sector_codes_mark_starbases_and_known_forces() -> None:
    from edge.core.models import SectorForce
    from edge.server.session import _sector_codes

    state = _state(base_owner=Ownership("none"), operational=False)
    player = state.players[1]
    assert "#" in _sector_codes(state, 1, player)  # the derelict base still charts
    # Foreign fighters chart; foreign mines alone do not.
    state.sector_forces[1] = SectorForce(sector_id=1, owner=Ownership("alliance", 2), fighters=4)
    assert "×" in _sector_codes(state, 1, player)
    state.sector_forces[1] = SectorForce(sector_id=1, owner=Ownership("alliance", 2), armid_mines=2)
    assert "×" not in _sector_codes(state, 1, player)
    state.sector_forces[1] = SectorForce(sector_id=1, owner=Ownership("player", 1), armid_mines=2)
    assert "×" in _sector_codes(state, 1, player)  # your own minefield is charted
