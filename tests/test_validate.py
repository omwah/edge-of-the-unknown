"""WP9 — big-bang validation rejects broken universes (DESIGN §5 step 8)."""

from __future__ import annotations

import pytest

from dataclasses import replace

from edge.bigbang.validate import ValidationError, validate
from edge.config import load_default_config
from edge.core.engine_room import build_layouts
from edge.core.enums import Commodity, PortClass, PortMode, Subsystem
from edge.core.models import (
    Game,
    Ownership,
    Planet,
    Port,
    PortCommodity,
    Sector,
    Starbase,
    UniverseState,
)

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
    world = _world(sectors, ports)
    # A habitable Hub world (non-Core) satisfies the §5 step-8 colonization invariant.
    world.planets = {1: Planet(1, 2, "Eden", "terrestrial_warm", owner=Ownership("none"))}
    return world


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


def test_unowned_core_planet_rejected() -> None:
    world = _good_world()
    world.game = Game(id=1, seed=1, config_version=1, created_at="t", core_governing_alliance_id=1)
    # A Core (sector 1) planet left unowned violates the governor-owned invariant.
    world.planets[2] = Planet(2, 1, "Core World", "terrestrial_warm", owner=Ownership("none"))
    with pytest.raises(ValidationError):
        validate(world, CONFIG)


def test_unowned_fraction_decreasing_rejected() -> None:
    # Hub fully unowned but Frontier fully owned → the fraction drops across bands.
    sectors = {
        1: Sector(1, 1, (2,), "Hub", is_galactic_core=True),
        2: Sector(2, 1, (1, 3), "Hub"),
        3: Sector(3, 1, (2, 4), "Hub"),
        4: Sector(4, 1, (3,), "Frontier"),
    }
    ports = {1: _pair(1, 1, PortClass.CLASS_1), 2: _stardock(2, 2), 3: _pair(3, 3, PortClass.CLASS_5)}
    world = _world(sectors, ports)
    world.planets = {
        1: Planet(1, 2, "Eden", "terrestrial_warm", owner=Ownership("none")),       # Hub: unowned
        2: Planet(2, 4, "Outpost", "terrestrial_cool", owner=Ownership("alliance", 1)),  # Frontier: owned
    }
    with pytest.raises(ValidationError):
        validate(world, CONFIG)


def _intact_base() -> dict[Subsystem, object]:
    assert CONFIG.starbase is not None
    return build_layouts(CONFIG.starbase.subsystems)


def _derelict_base() -> dict[Subsystem, object]:
    subs = _intact_base()
    reactor = subs[Subsystem.FUSION_REACTOR]
    slots = list(reactor.slots)  # type: ignore[attr-defined]
    slots[reactor.keystone_index] = None  # type: ignore[attr-defined]
    subs[Subsystem.FUSION_REACTOR] = replace(reactor, slots=tuple(slots))  # type: ignore[type-var]
    return subs


def test_derelict_base_on_owned_planet_rejected() -> None:
    world = _good_world()
    world.planets[1] = replace(world.planets[1], owner=Ownership("alliance", 1), starbase_id=1)
    world.starbases = {
        1: Starbase(1, 2, 1, "orbital_platform", owner=Ownership("alliance", 1), subsystems=_derelict_base()),
    }
    with pytest.raises(ValidationError):  # an owned world's base must be operational
        validate(world, CONFIG)


def test_derelict_base_on_unowned_world_validates() -> None:
    world = _good_world()  # planet 1 is unowned + uninhabited
    world.planets[1] = replace(world.planets[1], starbase_id=1)
    world.starbases = {
        1: Starbase(1, 2, 1, "orbital_platform", owner=Ownership("none"), subsystems=_derelict_base()),
    }
    validate(world, CONFIG)  # no raise — a derelict on the frontier is legal salvage


def test_base_without_planet_backref_rejected() -> None:
    world = _good_world()
    # The base claims planet 1 but the planet does not point back at it.
    world.starbases = {
        1: Starbase(1, 2, 1, "orbital_platform", owner=Ownership("none"), subsystems=_derelict_base()),
    }
    with pytest.raises(ValidationError):
        validate(world, CONFIG)
