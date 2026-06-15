"""WP1 checks: enums, port-class triples, and the core domain models."""

from __future__ import annotations

import dataclasses

import pytest

from edge.core.enums import PORT_CLASS_TRADES, Commodity, PortClass, PortMode
from edge.core.models import (
    Game,
    Player,
    Port,
    PortCommodity,
    Ship,
    UniverseState,
)


def _game(seed: int = 42) -> Game:
    return Game(id=1, seed=seed, config_version=1, created_at="2026-06-15T00:00:00Z")


def test_port_class_trades_cover_every_class_and_commodity() -> None:
    assert set(PORT_CLASS_TRADES) == set(PortClass)
    for klass, trades in PORT_CLASS_TRADES.items():
        assert set(trades) == set(Commodity), klass
        assert all(isinstance(m, PortMode) for m in trades.values())


def test_opposed_classes_exist_for_pair_trading() -> None:
    # CLASS_1 (BBS) and CLASS_5 (SSB) must be opposed on every commodity — the
    # canonical pair-trade route the §5 validation guarantees within 5 hops.
    bbs = PORT_CLASS_TRADES[PortClass.CLASS_1]
    ssb = PORT_CLASS_TRADES[PortClass.CLASS_5]
    assert all(bbs[c] is not ssb[c] for c in Commodity)


def test_ship_hold_accounting() -> None:
    ship = Ship(
        id=1, type_id="trailblazer", name="S.S. Wayfarer", owner_player_id=1,
        sector_id=7, holds_total=60,
        cargo={Commodity.FUEL_ORE: 20, Commodity.ORGANICS: 12},
    )
    assert ship.holds_used == 32
    assert ship.holds_free == 28


def test_port_line_lookup() -> None:
    port = Port(
        id=1, sector_id=3, name="Sol Exchange", klass=PortClass.CLASS_1, size=4,
        commodities=(
            PortCommodity(Commodity.FUEL_ORE, PortMode.BUY, 410, 4000, 11, 5),
        ),
    )
    assert port.line(Commodity.FUEL_ORE) is not None
    assert port.line(Commodity.EQUIPMENT) is None


def test_models_are_frozen() -> None:
    player = Player(id=1, name="you", ship_id=1, latinum=2_000)
    with pytest.raises(dataclasses.FrozenInstanceError):
        player.latinum = 0  # type: ignore[misc]
    assert player.explored_sectors == frozenset()


def test_universestate_rng_is_seeded_and_reproducible() -> None:
    a = UniverseState.new(_game(seed=123))
    b = UniverseState.new(_game(seed=123))
    assert [a.rng.random() for _ in range(5)] == [b.rng.random() for _ in range(5)]


def test_rebuild_adjacency_projects_warps() -> None:
    from edge.core.models import Sector

    universe = UniverseState.new(_game())
    universe.sectors = {
        1: Sector(id=1, region_id=1, warps_out=(2, 3), distance_band="Hub"),
        2: Sector(id=2, region_id=1, warps_out=(1,), distance_band="Hub"),
    }
    universe.rebuild_adjacency()
    assert universe.adjacency == {1: (2, 3), 2: (1,)}
