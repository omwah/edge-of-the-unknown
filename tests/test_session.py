"""WP9 — fog-of-war projections: computer & map views (DESIGN §3, §9, §11)."""

from __future__ import annotations

from edge.config import load_default_config
from edge.core.dto import CommodityLine
from edge.core.enums import PORT_CLASS_TRADES, Commodity, PortClass
from edge.core.models import (
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


def test_game_view_neighbors_fog_of_war_and_codes() -> None:
    view = session.game_view(_nav_world(), 1, CONFIG)
    by_id = {n.sector_id: n for n in view.ship.neighbors}
    # Explored neighbour 3 names its region/band and lists its port + planet codes.
    assert by_id[3].explored
    assert by_id[3].name == "[3] Halaf Verge" and by_id[3].band == "Frontier"
    assert by_id[3].codes == ["P", "@"]
    # Unexplored neighbour 6 stays masked: no region, no codes.
    assert not by_id[6].explored
    assert by_id[6].name == "[6] —" and by_id[6].band == "?" and by_id[6].codes == []


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
    assert all(n.display_id == n.sector_id for n in view.ship.neighbors)


def test_display_ids_surface_spatial_ids_when_present() -> None:
    world = _nav_world()  # player at sector 2; warps 1, 3, 6
    world.spatial_ids = {1: 10101, 2: 10102, 3: 20101, 6: 10103}
    view = session.game_view(world, 1, CONFIG)
    assert view.sector.display_id == 10102  # sector title shows the spatial id
    assert {w.sector_id: w.display_id for w in view.sector.warps} == {1: 10101, 3: 20101, 6: 10103}
    by_id = {n.sector_id: n for n in view.ship.neighbors}
    assert by_id[3].name == "[20101] Halaf Verge"  # explored neighbour embeds the spatial id
    assert by_id[6].name == "[10103] —"  # masked neighbour still numbered spatially
    # The gravity arrows are unchanged — they key off core_hops, not the display id.
    assert {w.sector_id: w.arrow for w in view.sector.warps} == {1: "<<", 3: ">>", 6: "--"}
    # The StarDock signpost would use the spatial id too (sector 3 hosts the SSB port here).
    world.ports[3] = _port(3, 3, PortClass.STARDOCK)
    assert "Sector 20101" in (session.stardock_signpost(world) or "")


def test_format_event_uses_display_map_for_warps() -> None:
    from edge.core.events import Warped

    assert "Sector 12" in session.format_event(Warped(1, 7, 12, 1))  # no map -> internal id
    assert "Sector 20116" in session.format_event(Warped(1, 7, 12, 1), {12: 20116})


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

    assert "Sector 12" in session.format_event(Warped(1, 7, 12, 1))
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
    # Per-commodity restock is not player-facing — filtered out of the log.
    assert session.format_event(StockRegenerated(3, Commodity.EQUIPMENT, 480)) == ""


def test_signpost_is_none_without_a_stardock() -> None:
    world = _nav_world()  # ports are a Class-5 SSB only — no StarDock
    assert session.stardock_signpost(world) is None
    assert session.messages_view(world, []).events == []


def test_commodity_line_trend_and_ratio_edges() -> None:
    flat = CommodityLine("Fuel Ore", "SELL", 500, 1000, 11, 11, 0)
    assert flat.trend == "="  # price == base_price
    assert CommodityLine("Fuel Ore", "SELL", 0, 0, 11, 11, 0).stock_ratio == 0.0
