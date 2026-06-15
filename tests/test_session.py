"""WP9 — fog-of-war projections: computer & map views (DESIGN §3, §9, §11)."""

from __future__ import annotations

from edge.config import load_default_config
from edge.core.dto import CommodityLine
from edge.core.enums import PORT_CLASS_TRADES, Commodity, PortClass
from edge.core.models import (
    Game,
    Player,
    Port,
    PortCommodity,
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


def test_commodity_line_trend_and_ratio_edges() -> None:
    flat = CommodityLine("Fuel Ore", "SELL", 500, 1000, 11, 11, 0)
    assert flat.trend == "="  # price == base_price
    assert CommodityLine("Fuel Ore", "SELL", 0, 0, 11, 11, 0).stock_ratio == 0.0
