"""WP9 — big-bang validation rejects broken universes (DESIGN §5 step 8)."""

from __future__ import annotations

import pytest

from edge.bigbang.validate import ValidationError, validate
from edge.config import load_default_config
from edge.core.enums import Commodity, PortClass, PortMode
from edge.core.models import Game, Port, PortCommodity, Sector, UniverseState

CONFIG = load_default_config()


def _world(sectors: dict[int, Sector], ports: dict[int, Port]) -> UniverseState:
    game = Game(id=1, seed=1, config_version=1, created_at="t")
    world = UniverseState.new(game)
    world.sectors = sectors
    world.ports = ports
    world.rebuild_adjacency()
    return world


def _stardock(port_id: int, sector_id: int) -> Port:
    lines = tuple(
        PortCommodity(c, PortMode.SELL, 500, 1000, 11, 5) for c in Commodity
    )
    return Port(port_id, sector_id, "StarDock", PortClass.STARDOCK, 1, lines)


def _pair(port_id: int, sector_id: int, klass: PortClass) -> Port:
    from edge.core.enums import PORT_CLASS_TRADES

    trades = PORT_CLASS_TRADES[klass]
    lines = tuple(PortCommodity(c, trades[c], 500, 1000, 11, 5) for c in Commodity)
    return Port(port_id, sector_id, "Port", klass, 1, lines)


def _good_world() -> UniverseState:
    # 1<->2<->3; StarDock at 2, an opposed BBS/SSB pair at 1 and 3.
    sectors = {
        1: Sector(1, 1, (2,), "Hub", is_galactic_core=True),
        2: Sector(2, 1, (1, 3), "Hub"),
        3: Sector(3, 1, (2,), "Hub"),
    }
    ports = {
        1: _pair(1, 1, PortClass.CLASS_1),
        2: _stardock(2, 2),
        3: _pair(3, 3, PortClass.CLASS_5),
    }
    return _world(sectors, ports)


def test_good_world_validates() -> None:
    validate(_good_world(), CONFIG)  # no raise


def test_unreachable_sector_rejected() -> None:
    world = _good_world()
    world.sectors[2] = Sector(2, 1, (1,), "Hub")  # drop the 2->3 warp; 3 unreachable
    world.rebuild_adjacency()
    with pytest.raises(ValidationError):
        validate(world, CONFIG)


def test_degree_cap_rejected() -> None:
    world = _good_world()
    world.sectors[2] = Sector(2, 1, (1, 3, 4, 5, 6, 7, 8), "Hub")  # 7 > cap of 6
    world.rebuild_adjacency()
    with pytest.raises(ValidationError):
        validate(world, CONFIG)


def test_missing_stardock_rejected() -> None:
    world = _good_world()
    del world.ports[2]  # remove the only StarDock
    with pytest.raises(ValidationError):
        validate(world, CONFIG)


def test_no_profitable_pair_rejected() -> None:
    # Two same-class ports never form a profitable opposed pair.
    sectors = {
        1: Sector(1, 1, (2,), "Hub", is_galactic_core=True),
        2: Sector(2, 1, (1, 3), "Hub"),
        3: Sector(3, 1, (2,), "Hub"),
    }
    ports = {
        1: _pair(1, 1, PortClass.CLASS_1),
        2: _stardock(2, 2),
        3: _pair(3, 3, PortClass.CLASS_1),  # same class as port 1
    }
    with pytest.raises(ValidationError):
        validate(_world(sectors, ports), CONFIG)
