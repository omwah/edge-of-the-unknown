"""Fixed builder archetypes and responsive port/starbase raster kits."""

from __future__ import annotations

from dataclasses import replace

import pytest

from edge.art.stations import (
    PORT_SERVICES, STARBASE_SERVICES, STATION_ARCHETYPES, render_station_art, station_asset,
)
from edge.art.generator import generate_sprite
from edge.bigbang.station_archetypes import assign_station_archetypes
from edge.config import load_default_config
from edge.core.enums import PortClass
from edge.core.models import (
    Game, Ownership, Port, Region, Sector, Starbase, UniverseState,
)
from edge.server.service import GameService
from edge.store.repo import SqliteRepository


@pytest.mark.parametrize("kind,services", [
    ("port", PORT_SERVICES), ("starbase", STARBASE_SERVICES),
])
@pytest.mark.parametrize("archetype", sorted(STATION_ARCHETYPES))
@pytest.mark.parametrize("cinematic", [False, True], ids=["standard", "wide"])
def test_every_archetype_has_responsive_service_art(
    kind: str, services: frozenset[str], archetype: str, cinematic: bool,
) -> None:
    root = station_asset(kind, archetype, next(iter(services)), cinematic=cinematic).parents[1]
    if kind == "port":
        assert (root / "source" / f"{archetype}_exterior_sheet.png").is_file()
    else:
        assert (root / "source" / f"{archetype}_services_sheet.png").is_file()
    for service in services:
        path = station_asset(kind, archetype, service, cinematic=cinematic)
        assert path.is_file(), path


@pytest.mark.parametrize("theme", ["edge-ansi", "edge-high-contrast", "edge-monochrome"])
@pytest.mark.parametrize("condition", ["open", "derelict", "hostile"])
def test_station_art_renders_theme_and_condition_treatments(theme: str, condition: str) -> None:
    banner = render_station_art(
        "starbase", "telepath_aristocrat", "status", theme,
        cinematic=False, condition=condition,
    )
    assert len(banner.plain.splitlines()) <= 8 and max(map(len, banner.plain.splitlines())) <= 56


@pytest.mark.parametrize("subtype", ["trading_port", "starbase"])
def test_archetype_icons_are_distinct_procedural_cell_art(subtype: str) -> None:
    icons = [generate_sprite(
        "port", subtype, seed=17, width=24, height=8,
        archetype_id=archetype,
    ) for archetype in sorted(STATION_ARCHETYPES)]
    assert len({icon.plain for icon in icons}) == len(STATION_ARCHETYPES)
    assert all(len(icon.plain.splitlines()) <= 8 for icon in icons)


def test_assignment_is_seeded_roster_driven_and_fixed_after_capture() -> None:
    cfg = load_default_config()
    game = Game(1, 99, cfg.config_version, "1970-01-01T00:00:00Z")
    state = UniverseState.new(game)
    state.regions[1] = Region(1, "Compact", controlling_alliance_id=2)
    state.sectors[1] = Sector(1, 1, (), "Hub")
    state.ports[1] = Port(1, 1, "Market", PortClass.CLASS_1, 1, ())
    state.starbases[1] = Starbase(
        1, 1, 1, "orbital_platform", owner=Ownership("alliance", 3),
    )

    assign_station_archetypes(state, cfg)
    assert state.ports[1].archetype_id in {sp.archetype_id for sp in cfg.roster.species}
    assert state.starbases[1].archetype_id in {sp.archetype_id for sp in cfg.roster.species}
    captured = replace(state.starbases[1], owner=Ownership("player", 1))
    assert captured.archetype_id == state.starbases[1].archetype_id


def test_sector_projection_uses_the_same_stored_archetype_as_docked_screens(tmp_path) -> None:
    cfg = load_default_config()
    service = GameService.new_game(cfg, 77, SqliteRepository(tmp_path / "archetype.db"))
    state = service.state
    player = state.players[1]
    ship = state.ships[player.ship_id]

    ordinary = next(port for port in state.ports.values()
                    if port.klass is not PortClass.STARDOCK
                    and not any(base.sector_id == port.sector_id
                                for base in state.starbases.values()))
    state.ships[ship.id] = replace(ship, sector_id=ordinary.sector_id)
    sector = service.game_view(1).sector
    assert sector.ports[0].archetype_id == ordinary.archetype_id
    assert service.current_port_view(1).archetype_id == ordinary.archetype_id  # type: ignore[union-attr]

    base = next(iter(state.starbases.values()))
    state.ships[ship.id] = replace(state.ships[ship.id], sector_id=base.sector_id)
    sector = service.game_view(1).sector
    projected = next(item for item in sector.starbases if item.starbase_id == base.id)
    assert projected.archetype_id == base.archetype_id
    assert service.starbase_view(1, base.id).archetype_id == base.archetype_id
