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


def test_game_view_sector_title_carries_band() -> None:
    view = session.game_view(_nav_world(), 1, CONFIG)
    assert view.sector.region == "Sol Core" and view.sector.band == "Hub"


def test_commodity_line_trend_and_ratio_edges() -> None:
    flat = CommodityLine("Fuel Ore", "SELL", 500, 1000, 11, 11, 0)
    assert flat.trend == "="  # price == base_price
    assert CommodityLine("Fuel Ore", "SELL", 0, 0, 11, 11, 0).stock_ratio == 0.0
