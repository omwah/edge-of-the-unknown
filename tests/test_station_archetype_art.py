"""Fixed builder archetypes and responsive port/starbase raster kits."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from edge.art.stations import (
    PORT_SERVICES, STARBASE_SERVICES, STATION_ARCHETYPES, render_station_art, station_asset,
)
from edge.art.generator import generate_sprite
from edge.bigbang.station_archetypes import assign_station_archetypes
from edge.config import load_default_config
from edge.core.config import PlanetSpriteSize, SceneArtConfig, SpriteSize
from edge.core.enums import PortClass
from edge.core.models import (
    Game, Ownership, Port, Region, Sector, Starbase, UniverseState,
)
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui.station_art import station_icon_dimensions


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


def test_station_dimensions_preserve_original_primary_and_lone_branches() -> None:
    cfg = SceneArtConfig(
        planet=PlanetSpriteSize(min_height=4, max_height=20),
        port=SpriteSize(min_width=1, min_height=1, max_width=30, max_height=10),
        stardock=SpriteSize(min_width=1, min_height=1, max_width=36, max_height=12),
        starbase=SpriteSize(min_width=1, min_height=1, max_width=40, max_height=20),
        port_scale=0.25,
        stardock_scale=0.5,
        starbase_scale=0.75,
    )
    assert cfg.station_dimensions(
        "port", primary_height=20, body_height=99) == (12, 5)
    assert cfg.station_dimensions(
        "stardock", primary_height=20, body_height=99) == (24, 10)
    assert cfg.station_dimensions(
        "starbase", primary_height=20, body_height=99) == (36, 15)
    # No primary: exactly the old body_h * 0.6 / width * 2.6 branch; scales do not apply.
    assert cfg.station_dimensions(
        "port", primary_height=None, body_height=10) == (15, 6)


def test_docked_header_reuses_the_sector_composers_resolved_size() -> None:
    cfg = SceneArtConfig()
    app = SimpleNamespace(
        scene_art=cfg,
        sector_station_reference=(7, 20, 99),
    )
    assert station_icon_dimensions(app, "port", False) == cfg.station_dimensions(
        "port", primary_height=20, body_height=99)


def test_docked_header_rejects_a_reference_from_another_sector() -> None:
    """The published reference is only trusted for the sector being drawn: a caller
    that names its sector must never be sized by a stale cache from elsewhere."""
    cfg = SceneArtConfig()
    app = SimpleNamespace(
        scene_art=cfg,
        sector_station_reference=(7, 20, 99),
    )
    assert station_icon_dimensions(app, "port", False, expect_sector=7) == (
        cfg.station_dimensions("port", primary_height=20, body_height=99))
    # Mismatch ⇒ fall back to the kind's bounds, exactly like a direct-open screen.
    assert station_icon_dimensions(app, "port", False, expect_sector=8) == (
        cfg.port.max_width, cfg.port.max_height)


async def test_stardock_header_keeps_the_stardock_exterior(monkeypatch) -> None:
    """Scaling the left-hand silhouette must never route it through port art."""
    from edge.tui import art_adapter
    from edge.tui.app import EdgeApp
    from edge.tui.screens.stardock import _DockStructureArt

    calls: list[tuple[str, str]] = []
    real_sprite = art_adapter.sprite

    def recording_sprite(entity: str, subtype: str, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((entity, subtype))
        return real_sprite(entity, subtype, **kwargs)

    monkeypatch.setattr(art_adapter, "sprite", recording_sprite)
    app = EdgeApp()
    async with app.run_test(size=(110, 36)) as pilot:
        cinematic = app.layout_tier.value == "wide"
        size = station_icon_dimensions(app, "stardock", cinematic)
        await app.mount(_DockStructureArt(7, "humanoid_diplomat", cinematic, size))
        await pilot.pause()

    assert ("port", "stardock") in calls
    assert ("port", "trading_port") not in calls


async def test_station_header_vertically_centers_exterior_and_banner() -> None:
    from edge.tui.app import EdgeApp
    from edge.tui.station_art import StationArtHeader

    app = EdgeApp()
    async with app.run_test(size=(110, 36)) as pilot:
        header = StationArtHeader(
            "port", "humanoid_diplomat", "trade", identity=7,
        )
        await app.mount(header)
        await pilot.pause()
        icon, banner = list(header.children)
        # A 9-row port beside an 8-row banner has no exact cell midpoint. Bias the
        # shorter banner down one row instead of top-aligning it; doubled midpoints
        # then differ by only one half-row.
        assert banner.region.y == icon.region.y + 1
        icon_midpoint = 2 * icon.region.y + icon.region.height
        banner_midpoint = 2 * banner.region.y + banner.region.height
        assert abs(icon_midpoint - banner_midpoint) == 1


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
