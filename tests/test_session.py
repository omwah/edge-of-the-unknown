"""WP9 — fog-of-war projections: computer & map views (DESIGN §3, §9, §11)."""

from __future__ import annotations

from edge.config import load_default_config
from edge.core.dto import CommodityLine
from edge.core.enums import PORT_CLASS_TRADES, Commodity, PortClass
from edge.core.models import (
    AlienSpecies,
    Game,
    Planet,
    Player,
    Port,
    PortCommodity,
    Region,
    Sector,
    Ship,
    UniverseState,
)
from edge.server import session

CONFIG = load_default_config()


def _port(pid: int, sid: int, klass: PortClass) -> Port:
    trades = PORT_CLASS_TRADES[klass]
    lines = tuple(PortCommodity(c, trades[c], 500, 1000, 11, 5) for c in Commodity)
    return Port(pid, sid, f"Port {pid}", klass, 1, lines)


def _world() -> UniverseState:
    game = Game(1, 1, 1, "t", core_governing_alliance_id=1)
    world = UniverseState.new(game)
    world.sectors = {
        1: Sector(1, 1, (2,), "Hub", is_galactic_core=True),
        2: Sector(2, 1, (1, 3), "Hub"),
        3: Sector(3, 1, (2, 4), "Hub"),
        4: Sector(4, 1, (3,), "Frontier"),  # a second band, to order
        5: Sector(5, 1, (), "Weird"),  # a band outside the canonical order
    }
    world.regions = {}
    world.ports = {
        1: _port(1, 1, PortClass.CLASS_1),  # BBS — buys fuel/org
        3: _port(3, 3, PortClass.CLASS_5),  # SSB — sells fuel/org
    }
    world.ships = {1: Ship(1, "trailblazer", "S.S.", 1, 2, 60)}
    world.players = {
        1: Player(1, "you", 1, 2_000, turns_remaining=250,
                  explored_sectors=frozenset({1, 2, 3})),
    }
    world.rebuild_adjacency()
    return world


def _species(sid: int, sector_id: int, name: str) -> AlienSpecies:
    return AlienSpecies(
        id=sid, roster_id=f"sp{sid}", name=name, archetype_id="trader", sector_id=sector_id,
        home_band="Hub", tech_level=1, base_disposition=0.8,
        disposition_center=0.8, disposition_variance=0.05,
    )


def test_staged_species_surfaces_as_a_ship_in_its_sector() -> None:
    """A friendly contact is visible as a present vessel so the player can see/hail it."""
    world = _world()
    world.regions = {1: Region(1, "Hub")}  # game_view renders the sector region label
    world.species = {
        1: _species(1, 2, "Vesk"),   # in the player's sector (sector 2)
        2: _species(2, 4, "Selvani"),  # elsewhere
    }
    here = session.game_view(world, 1, CONFIG).sector
    assert [s.name for s in here.ships] == ["Vesk vessel"]  # only the one in this sector
    assert [s.contact_id for s in here.ships] == [1]  # clicking the row hails species 1


def test_empty_sector_lists_no_ships() -> None:
    world = _world()  # no species placed
    world.regions = {1: Region(1, "Hub")}
    assert session.game_view(world, 1, CONFIG).sector.ships == []


def test_engine_room_view_projects_slots_and_derived_aspects() -> None:
    from edge.core.engine_room import build_subsystems
    from edge.core.enums import Component, ComponentTier

    world = _world()
    sc = CONFIG.starter_ship
    world.ships[1] = Ship(
        1, sc.id, sc.name, 1, 2, sc.holds_total, shields=sc.shields_max,
        warp_speed=sc.warp_speed, combat_speed=sc.combat_speed, repair_kits=2,
        subsystems=build_subsystems(sc),
        components={(Component.CONVERTER, ComponentTier.II): 1},
    )
    er = session.engine_room_view(world, 1, CONFIG)
    assert [s.name for s in er.subsystems] == ["SPINDRIVE", "SCREENS", "THRUSTERS", "MAIN GUN"]
    spindrive = er.subsystems[0]
    assert spindrive.derived == "warp 3"
    assert spindrive.slots[0].keystone and spindrive.slots[0].state == "filled"
    assert spindrive.slots[-1].state == "empty"
    assert er.efficiency_bonus == "+2 all"
    assert er.kits == 2
    assert er.on_hand == ["converter (II) x1"]


def test_engine_room_view_handles_a_flat_hull() -> None:
    """An NPC-style flat hull (no subsystems) projects no panels, not an error."""
    er = session.engine_room_view(_world(), 1, CONFIG)  # _world's ship has subsystems=None
    assert er.subsystems == []


def test_stardock_view_lists_hardware_and_shipyard() -> None:
    world = _world()
    # Put a StarDock under the player and give them real buying power.
    world.ports[2] = _port(2, 2, PortClass.STARDOCK)
    world.players[1] = Player(1, "you", 1, 60_000, turns_remaining=250,
                              explored_sectors=frozenset({1, 2, 3}))
    sv = session.stardock_view(world, 1, CONFIG)
    # Hardware: Tier I + II only (III is barter-only and absent).
    assert sv.hardware and {h.tier for h in sv.hardware} == {"I", "II"}
    assert all(h.price > 0 for h in sv.hardware)
    # Shipyard: every buyable hull, with the trailblazer flagged owned nowhere
    # (the player flies it but it isn't in ship_classes) and net price ≤ price.
    ids = {s.class_id for s in sv.shipyard}
    assert "scout_marauder" in ids
    scout = next(s for s in sv.shipyard if s.class_id == "scout_marauder")
    assert scout.affordable and scout.net_price == scout.price  # free starter → no trade-in


def test_planet_view_reports_ownership_and_claimability() -> None:
    from edge.core.models import Ownership, Planet

    world = _world()
    world.planets = {
        1: Planet(1, 2, "Eden", "terrestrial_warm", owner=Ownership("none"), habitability_cap=100_000),
        2: Planet(2, 3, "Gasworld", "jovian", owner=Ownership("alliance", 1)),
    }
    world.ships[1] = Ship(1, "trailblazer", "S.S.", 1, 2, 60, colonist_capacity=100, colonists=20)
    eden = session.planet_view(world, 1, 1, CONFIG)
    assert eden.owner == "unowned" and eden.colonizable and eden.claimable
    assert eden.ship_colonists == 20
    gas = session.planet_view(world, 1, 2, CONFIG)
    assert not gas.colonizable and not gas.claimable  # jovian is extraction-only


def test_planet_view_owner_labels() -> None:
    from edge.core.models import Alliance, Ownership, Planet

    world = _world()
    world.alliances = {1: Alliance(1, "Federation")}
    world.planets = {
        1: Planet(1, 2, "Mine", "terrestrial_warm", owner=Ownership("player", 1)),
        2: Planet(2, 3, "Theirs", "terrestrial_cool", owner=Ownership("alliance", 1)),
    }
    assert session.planet_view(world, 1, 1, CONFIG).owner == "you"
    assert session.planet_view(world, 1, 1, CONFIG).owned_by_you
    assert session.planet_view(world, 1, 2, CONFIG).owner == "Federation"


def test_computer_view_finds_profitable_pair() -> None:
    cv = session.computer_view(_world(), 1, CONFIG)
    assert cv.pairs  # at least one opposed pair among discovered ports
    assert cv.selected != "—"
    assert all(tp.per_turn >= 0 for tp in cv.pairs)


def test_computer_view_empty_without_discovered_ports() -> None:
    world = _world()
    world.players[1] = Player(1, "you", 1, 2_000, explored_sectors=frozenset({2}))
    cv = session.computer_view(world, 1, CONFIG)
    assert cv.pairs == [] and cv.selected == "—"


# --- WP14: route_view / route_legs_view ---


def test_route_view_maps_to_spatial_ids_and_costs() -> None:
    # Ship at sector 2; route to 3 is one hop (no spatial_ids: display == internal).
    rv = session.route_view(_world(), 1, 3, CONFIG)
    assert rv.reachable and rv.affordable and rv.reason == ""
    assert [h.display_id for h in rv.hops] == [3]
    assert rv.origin_display == 2 and rv.dest_display == 3
    assert rv.turn_cost == 1  # 1 hop * turns_per_warp(1)
    assert rv.hazards == []  # Phase-2 seam stays empty


def test_route_view_out_of_turns_is_reachable_but_unaffordable() -> None:
    world = _world()
    world.players[1] = Player(1, "you", 1, 2_000, turns_remaining=0,
                              explored_sectors=frozenset({1, 2, 3}))
    rv = session.route_view(world, 1, 3, CONFIG)
    assert rv.reachable and not rv.affordable
    assert "turns" in rv.reason.lower()


def test_route_view_fogged_destination_is_unreachable() -> None:
    # Sector 4 is not explored — no charted route within the fog set.
    rv = session.route_view(_world(), 1, 4, CONFIG)
    assert not rv.reachable and rv.hops == []
    assert rv.reason != ""


def test_route_legs_view_walks_the_trade_round_trip() -> None:
    world = _world()
    pair = session.computer_view(world, 1, CONFIG).pairs[0]
    assert pair.buy_sector != -1 and pair.sell_sector != -1
    rv = session.route_legs_view(world, 1, [pair.buy_sector, pair.sell_sector], CONFIG)
    assert rv.reachable
    assert rv.dest_display == session._display(world, pair.sell_sector)


# --- WP15: ports directory ---


def test_port_directory_lists_explored_ports_nearest_first() -> None:
    cv = session.computer_view(_world(), 1, CONFIG)
    # Both fixture ports sit in explored sectors (1 and 3); ship is at sector 2.
    sectors = {e.sector_id for e in cv.ports}
    assert sectors == {1, 3}
    dists = [e.dist for e in cv.ports]
    assert dists == sorted(dists)  # nearest first
    assert all(e.dist == 1 for e in cv.ports)  # 2->1 and 2->3 are each one hop


def test_port_directory_honours_fog_of_war() -> None:
    world = _world()
    # Explore only sector 2 (no ports there): the directory is empty.
    world.players[1] = Player(1, "you", 1, 2_000, explored_sectors=frozenset({2}))
    cv = session.computer_view(world, 1, CONFIG)
    assert cv.ports == []


def test_port_directory_buy_sell_labels_match_class() -> None:
    cv = session.computer_view(_world(), 1, CONFIG)
    bbs = next(e for e in cv.ports if e.sector_id == 1)  # CLASS_1 = BBS
    assert "BBS" in bbs.klass
    assert bbs.buys == "Fuel, Org" and bbs.sells == "Equ"


def test_map_view_orders_bands_and_counts() -> None:
    mv = session.map_view(_world(), 1)
    assert mv.you_sector == 2 and mv.you_band == "Hub"
    titles = [b.title for b in mv.bands]
    # canonical bands first, then any extras alphabetically.
    assert titles == ["Band · Hub", "Band · Frontier", "Band · Weird"]


def _nav_world() -> UniverseState:
    """A small graph for the sidebar/gravity projections (WP-A).

    Hops from the Core (sector 1): 1=0, 2=1, 6=1, 3=2. Player sits at sector 2.
    """
    game = Game(1, 1, 1, "t", core_governing_alliance_id=1)
    world = UniverseState.new(game)
    world.regions = {1: Region(1, "Sol Core"), 2: Region(2, "Halaf Verge")}
    world.sectors = {
        1: Sector(1, 1, (2, 6), "Hub", is_galactic_core=True),
        2: Sector(2, 1, (1, 3, 6), "Hub"),
        3: Sector(3, 2, (2,), "Frontier"),
        6: Sector(6, 1, (1, 2), "Hub"),
    }
    world.ports = {3: _port(3, 3, PortClass.CLASS_5)}
    world.planets = {1: Planet(1, 3, "Halaf I", "terrestrial_warm")}
    world.ships = {1: Ship(1, "trailblazer", "S.S.", 1, 2, 60)}
    world.players = {
        1: Player(1, "you", 1, 2_000, turns_remaining=250,
                  explored_sectors=frozenset({1, 2, 3})),
    }
    world.rebuild_adjacency()
    return world


def test_game_view_warp_fog_of_war_and_codes() -> None:
    view = session.game_view(_nav_world(), 1, CONFIG)
    by_id = {w.sector_id: w for w in view.sector.warps}
    # Explored warp 3 names its region/band and lists its port + planet codes.
    assert by_id[3].explored
    assert by_id[3].label == "Halaf Verge" and by_id[3].band == "Frontier"
    assert by_id[3].codes == ["P", "@"]
    # Unexplored warp 6 stays masked: no region, no codes.
    assert not by_id[6].explored
    assert by_id[6].label is None and by_id[6].band == "?" and by_id[6].codes == []


def test_game_view_gravity_arrows() -> None:
    view = session.game_view(_nav_world(), 1, CONFIG)
    arrows = {w.sector_id: w.arrow for w in view.sector.warps}
    assert arrows == {1: "<<", 3: ">>", 6: "--"}  # toward Core / deeper / level


def test_game_view_marks_the_way_back() -> None:
    from dataclasses import replace

    world = _nav_world()  # player at sector 2
    world.players[1] = replace(world.players[1], entered_from={2: 1})  # arrived from 1
    kinds = {w.sector_id: w.kind for w in session.game_view(world, 1, CONFIG).sector.warps}
    assert kinds[1] == "backtrack"  # the way we came in
    assert kinds[3] == "explored"  # visited, but not the breadcrumb
    assert kinds[6] == "unexplored"


def test_game_view_sector_title_carries_band() -> None:
    view = session.game_view(_nav_world(), 1, CONFIG)
    assert view.sector.region == "Sol Core" and view.sector.band == "Hub"


def test_display_ids_fall_back_to_internal_without_spatial_ids() -> None:
    # A fixture state never ran the numbering pass: display_id mirrors the internal id.
    view = session.game_view(_nav_world(), 1, CONFIG)
    assert view.sector.display_id == view.sector.sector_id == 2
    assert all(w.display_id == w.sector_id for w in view.sector.warps)


def test_display_ids_surface_spatial_ids_when_present() -> None:
    world = _nav_world()  # player at sector 2; warps 1, 3, 6
    world.spatial_ids = {1: 10101, 2: 10102, 3: 20101, 6: 10103}
    view = session.game_view(world, 1, CONFIG)
    assert view.sector.display_id == 10102  # sector title shows the spatial id
    assert {w.sector_id: w.display_id for w in view.sector.warps} == {1: 10101, 3: 20101, 6: 10103}
    by_id = {w.sector_id: w for w in view.sector.warps}
    assert by_id[3].label == "Halaf Verge" and by_id[3].display_id == 20101  # explored warp
    assert by_id[6].label is None and by_id[6].display_id == 10103  # masked warp, still numbered
    # The gravity arrows are unchanged — they key off core_hops, not the display id.
    assert {w.sector_id: w.arrow for w in view.sector.warps} == {1: "<<", 3: ">>", 6: "--"}


def test_format_event_warp_body_defers_sector_to_the_gutter() -> None:
    from edge.core.events import Warped

    # The body names the action, not the sector — the gutter (format_log_line) carries it.
    line = session.format_event(Warped(1, 7, 12, 1))
    assert "Warp to sector" in line
    assert "Sector 12" not in line and "»" not in line


def test_format_event_flags_a_one_way_warp() -> None:
    from edge.core.events import Warped

    # A one-way warp warns the player there's no direct way back; a normal warp doesn't.
    assert "one-way" in session.format_event(Warped(1, 7, 12, 1, one_way=True))
    assert "one-way" not in session.format_event(Warped(1, 7, 12, 1))


def test_format_event_covers_kinds_and_filters_noise() -> None:
    from edge.core.enums import PortMode
    from edge.core.events import (
        Banked,
        Docked,
        Haggled,
        StockRegenerated,
        Traded,
        TurnsReset,
        Warped,
    )

    assert "Warp to sector" in session.format_event(Warped(1, 7, 12, 1))
    assert session.format_event(Docked(1, 12, 3))
    assert "Bought" in session.format_event(Traded(1, 3, Commodity.FUEL_ORE, PortMode.SELL, 5, 13, 65))
    assert "Sold" in session.format_event(Traded(1, 3, Commodity.FUEL_ORE, PortMode.BUY, 5, 13, 65))
    assert "Haggle" in session.format_event(Haggled(1, 3, Commodity.ORGANICS, "rejected", None))
    assert session.format_event(Banked(1, "deposit", 500, 500))
    assert session.format_event(TurnsReset(1, 250))
    from edge.core.events import (
        ComponentInstalled,
        ComponentPurchased,
        ComponentRemoved,
        Repaired,
        ShipPurchased,
    )
    assert "Bought" in session.format_event(ComponentPurchased(1, "turbine", "II", 8_000))
    assert "Acquired" in session.format_event(ShipPurchased(1, "scout_marauder", 20_000, 0))
    assert "Installed" in session.format_event(ComponentInstalled(1, "spindrive", 3, "turbine", "II"))
    assert "Removed" in session.format_event(ComponentRemoved(1, "main_gun", 2, "linkage", "I"))
    assert "patched" in session.format_event(Repaired(1, "thrusters", 1))
    from edge.core.events import LeadAccepted
    assert "Coordinates logged" in session.format_event(LeadAccepted(1, 2, "discovery", 5, 12))
    # Per-commodity restock is not player-facing — filtered out of the log.
    assert session.format_event(StockRegenerated(3, Commodity.EQUIPMENT, 480)) == ""


def test_format_log_line_always_tags_the_sector() -> None:
    """Every surfaced log line carries a leading spatial-sector gutter (§11/§12)."""
    from edge.core.enums import PortMode
    from edge.core.events import Banked, Docked, StockRegenerated, Traded, Warped

    world = _world()  # ship 1 sits in sector 2; port 3 is in sector 3
    # A sector-anchored event tags that sector; spatial_ids map through it.
    world.spatial_ids = {3: 20103}
    assert session.format_log_line(Warped(1, 2, 3, 1), world).startswith("[grey46]S20103 »[/] ")
    # A trade resolves the sector from the port it happened at.
    sell = Traded(1, 3, Commodity.FUEL_ORE, PortMode.SELL, 5, 13, 65)
    assert session.format_log_line(sell, world).startswith("[grey46]S20103 »[/] ")
    assert session.format_log_line(Docked(1, 3, 3), world).startswith("[grey46]S20103 »[/] ")
    # A located-nowhere player action falls back to the actor's current ship sector (2).
    assert session.format_log_line(Banked(1, "deposit", 500, 500), world).startswith("[grey46]S2 »[/] ")
    # Non-surfaced events stay empty — no gutter stamped onto nothing.
    assert session.format_log_line(StockRegenerated(3, Commodity.EQUIPMENT, 480), world) == ""


def test_messages_view_stamps_day_and_turn() -> None:
    """Each log line's `when` carries the game day + turn-of-day, day rolling on TurnsReset."""
    from edge.core.events import Banked, Docked, TurnsReset, Warped

    world = _world()
    events: list[object] = [
        Warped(1, 2, 3, 2),                 # day 1, +2 turns -> t2
        Docked(1, 3, 3),                    # +1 turn -> t3
        Banked(1, "deposit", 500, 500),     # free -> shares t3
        TurnsReset(1, 250),                 # day rolls over -> day 2, t0
        Warped(1, 3, 2, 1),                 # day 2, +1 turn -> t1
    ]
    view = session.messages_view(world, events, CONFIG)  # type: ignore[arg-type]
    assert [e.when for e in view.events] == [  # newest first
        "D2 · T1", "D2 · T0", "D1 · T3", "D1 · T3", "D1 · T2",
    ]


def test_messages_view_empty_without_events() -> None:
    world = _nav_world()
    assert session.messages_view(world, [], CONFIG).events == []


def test_commodity_line_trend_and_ratio_edges() -> None:
    flat = CommodityLine("Fuel Ore", "SELL", 500, 1000, 11, 11, 0)
    assert flat.trend == "="  # price == base_price
    assert CommodityLine("Fuel Ore", "SELL", 0, 0, 11, 11, 0).stock_ratio == 0.0


# --- WP16: drift fog split (dossier remembers; sector view tracks live position) ---


def test_drift_keeps_dossier_last_seen_while_sector_view_tracks_position() -> None:
    from dataclasses import replace

    from edge.core.models import Region

    world = _world()
    world.regions = {1: Region(1, "Hub")}
    world.species = {1: _species(1, 2, "Vesk")}  # at the player's sector (2)
    world.players[1] = replace(world.players[1],
                               species_attitudes={"sp1": 0.1}, species_last_seen={"sp1": 2})

    # Before drift: visible here; dossier last-seen names the hail sector.
    assert [s.name for s in session.game_view(world, 1, CONFIG).sector.ships] == ["Vesk vessel"]
    seen0 = session.computer_view(world, 1, CONFIG).dossier[0].last_seen
    assert seen0 == str(session._display(world, 2))

    # Drift carries it to sector 3: it leaves the player's view, but last-seen is frozen.
    world.species[1] = replace(world.species[1], sector_id=3)
    assert session.game_view(world, 1, CONFIG).sector.ships == []  # must be re-found
    seen1 = session.computer_view(world, 1, CONFIG).dossier[0].last_seen
    assert seen1 == str(session._display(world, 2))  # still the hail sector, not the live position
