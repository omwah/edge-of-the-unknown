"""WP-UI02/WP-UI22 — deterministic snapshot smoke matrix (pytest-textual-snapshot).

Captures static sample surfaces and fixed-seed live screens. Compact and
standard captures cover every screen family, while representative dense
screens also have wide and alternate-theme baselines (WP-UI22).

Regenerate accepted baselines with `pytest --snapshot-update`.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot

from edge.core.dto import Slot, Subsystem
from edge.tui.app import EdgeApp
from edge.tui.component_workbench import (
    ComponentWorkbench,
    SHIP_WORKBENCH_PROFILE,
    STARBASE_WORKBENCH_PROFILE,
    ComponentWorkbenchProfile,
    WorkbenchCapabilities,
)

SIZES = {"compact": (80, 24), "standard": (100, 34), "wide": (120, 40)}


@pytest.mark.parametrize("size", SIZES.values(), ids=SIZES.keys())
def test_main_menu_sizes(snap_compare, size: tuple[int, int]) -> None:
    assert snap_compare(EdgeApp(plain=True), terminal_size=size)


@pytest.mark.parametrize("theme", ["edge-ansi", "edge-high-contrast", "edge-monochrome"])
def test_main_menu_themes(snap_compare, theme: str) -> None:
    async def apply_theme(pilot: Pilot) -> None:
        pilot.app.theme = theme

    assert snap_compare(EdgeApp(plain=True), terminal_size=SIZES["standard"],
                        run_before=apply_theme)


async def _open_seeded_game(pilot: Pilot, *, computer: bool = False) -> None:
    from edge.tui.screens.computer import ComputerScreen
    from edge.tui.screens.game import GameScreen

    app = pilot.app
    assert isinstance(app, EdgeApp)
    service = app.start_new_game(seed=1986)
    screen = (ComputerScreen(service, app.player_id, initial_tab="ports") if computer
              else GameScreen(service, app.player_id))
    app.push_screen(screen)
    await pilot.pause()


@pytest.mark.parametrize("size", SIZES.values(), ids=SIZES.keys())
def test_sector_sizes(snap_compare, size: tuple[int, int]) -> None:
    assert snap_compare(EdgeApp(plain=True), terminal_size=size,
                        run_before=_open_seeded_game)


@pytest.mark.parametrize("size", SIZES.values(), ids=SIZES.keys())
def test_computer_sizes(snap_compare, size: tuple[int, int]) -> None:
    async def open_computer(pilot: Pilot) -> None:
        await _open_seeded_game(pilot, computer=True)

    assert snap_compare(EdgeApp(plain=True), terminal_size=size,
                        run_before=open_computer)


@pytest.mark.parametrize("size", [SIZES["compact"], SIZES["standard"]],
                         ids=["compact", "standard"])
def test_lobby_sizes(snap_compare, size: tuple[int, int]) -> None:
    from edge.tui.screens.lobby import LobbyScreen

    async def open_lobby(pilot: Pilot) -> None:
        pilot.app.push_screen(LobbyScreen("ws://host.example:8765"))
        await pilot.pause()

    assert snap_compare(EdgeApp(plain=True), terminal_size=size, run_before=open_lobby)


def _open_stardock(tab: str):
    """A run_before that starts the seeded game (docked at StarDock) on `tab` (WP-PR08)."""
    async def _run(pilot: Pilot) -> None:
        from edge.tui.screens.stardock import StarDockScreen
        app = pilot.app
        assert isinstance(app, EdgeApp)
        service = app.start_new_game(seed=1986)
        app.push_screen(StarDockScreen(service, app.player_id, initial_tab=tab))
        await pilot.pause()
    return _run


@pytest.mark.parametrize("tab", ["devices", "colonists", "tavern"])
def test_stardock_tabs_compact(snap_compare, tab: str) -> None:
    # WP-PR08 §8.1: the reworked Devices & Armaments / Colonists / bounty-board tabs at 80x24.
    assert snap_compare(EdgeApp(plain=True), terminal_size=SIZES["compact"],
                        run_before=_open_stardock(tab))


@pytest.mark.parametrize("theme", ["edge-high-contrast", "edge-monochrome"])
def test_stardock_colonists_themes(snap_compare, theme: str) -> None:
    async def run(pilot: Pilot) -> None:
        await _open_stardock("colonists")(pilot)
        pilot.app.theme = theme
        await pilot.pause()

    assert snap_compare(EdgeApp(plain=True), terminal_size=SIZES["standard"], run_before=run)


@pytest.mark.parametrize("size", [SIZES["standard"], SIZES["wide"]],
                         ids=["standard", "wide"])
def test_stardock_concourse_sizes(snap_compare, size: tuple[int, int]) -> None:
    """PT-06: compact and cinematic ANSI crops both retain the recruitment scene."""
    assert snap_compare(EdgeApp(plain=True), terminal_size=size,
                        run_before=_open_stardock("colonists"))


@pytest.mark.parametrize("tab", ["trade", "shipyard", "hardware", "devices", "bank", "tavern"])
def test_stardock_service_art_standard(snap_compare, tab: str) -> None:
    assert snap_compare(EdgeApp(plain=True), terminal_size=SIZES["standard"],
                        run_before=_open_stardock(tab))


@pytest.mark.parametrize("tab", ["trade", "shipyard", "hardware", "devices", "bank", "tavern"])
def test_stardock_service_art_wide(snap_compare, tab: str) -> None:
    assert snap_compare(EdgeApp(plain=True), terminal_size=SIZES["wide"],
                        run_before=_open_stardock(tab))


def test_options_modal(snap_compare) -> None:
    assert snap_compare(EdgeApp(plain=True), press=["o"], terminal_size=SIZES["standard"])


def test_help_modal(snap_compare) -> None:
    assert snap_compare(EdgeApp(plain=True), press=["question_mark"],
                        terminal_size=SIZES["standard"])


def test_size_notice(snap_compare) -> None:
    async def shrink(pilot: Pilot) -> None:
        await pilot.resize_terminal(70, 20)
        await pilot.pause()
        await pilot.pause()

    assert snap_compare(EdgeApp(plain=True), terminal_size=SIZES["compact"],
                        run_before=shrink)


def _sample_subsystems(profile: ComponentWorkbenchProfile) -> list[Subsystem]:
    subsystems = []
    for name in profile.subsystem_labels:
        subsystems.append(Subsystem(name=name, derived="aspect 3", slots=[
            Slot(state="filled", component="converter (I)", keystone=True),
            Slot(state="filled", component="turbine (II)"),
            Slot(state="knocked", component="radiator (I)"),
            Slot(state="empty"),
        ]))
    return subsystems


class _WorkbenchApp(App[None]):
    def __init__(self, profile: ComponentWorkbenchProfile, loose: list[str]) -> None:
        super().__init__()
        self._profile = profile
        self._loose = loose

    def on_mount(self) -> None:
        from edge.tui.design import EDGE_ANSI, EDGE_HIGH_CONTRAST, EDGE_MONOCHROME
        for theme in (EDGE_ANSI, EDGE_HIGH_CONTRAST, EDGE_MONOCHROME):
            self.register_theme(theme)

    def compose(self) -> ComposeResult:
        yield ComponentWorkbench(_sample_subsystems(self._profile), self._loose,
                                 self._profile, WorkbenchCapabilities(install=True))


@pytest.mark.parametrize("size", SIZES.values(), ids=SIZES.keys())
def test_ship_workbench_sizes(snap_compare, size: tuple[int, int]) -> None:
    app = _WorkbenchApp(SHIP_WORKBENCH_PROFILE, ["converter (I) x1", "burner (II) x2"])
    assert snap_compare(app, terminal_size=size)


def test_base_workbench_with_empty_loose_bay(snap_compare) -> None:
    app = _WorkbenchApp(STARBASE_WORKBENCH_PROFILE, [])
    assert snap_compare(app, terminal_size=SIZES["standard"])


@pytest.mark.parametrize("size", SIZES.values(), ids=SIZES.keys())
def test_planet_sizes(snap_compare, size: tuple[int, int]) -> None:
    from edge.tui.dummy import sample_planet
    from edge.tui.screens.planet import PlanetScreen

    async def open_planet(pilot: Pilot) -> None:
        pilot.app.push_screen(PlanetScreen(sample_planet()))
        await pilot.pause()

    assert snap_compare(EdgeApp(plain=True), terminal_size=size, run_before=open_planet)


@pytest.mark.parametrize("size", SIZES.values(), ids=SIZES.keys())
def test_surface_sizes(snap_compare, size: tuple[int, int]) -> None:
    from edge.tui.dummy import sample_surface
    from edge.tui.screens.surface import SurfaceScreen

    async def open_surface(pilot: Pilot) -> None:
        pilot.app.push_screen(SurfaceScreen(sample_surface()))
        await pilot.pause()

    assert snap_compare(EdgeApp(plain=True), terminal_size=size, run_before=open_surface)


@pytest.mark.parametrize("size", SIZES.values(), ids=SIZES.keys())
def test_contact_sizes(snap_compare, size: tuple[int, int]) -> None:
    from dataclasses import replace

    from edge.tui.dummy import sample_contact
    from edge.tui.screens.contact import AlienContactScreen

    async def open_contact(pilot: Pilot) -> None:
        # Exercise disabled-reply reasons as part of the visual contract without
        # persisting a local preference from a snapshot test.
        pilot.app.ui_settings = replace(pilot.app.ui_settings, show_disabled_options=True)
        pilot.app.push_screen(AlienContactScreen(sample_contact()))
        await pilot.pause()

    assert snap_compare(EdgeApp(plain=True), terminal_size=size, run_before=open_contact)


class _StaticEncounterService:
    def __init__(self) -> None:
        from edge.tui.dummy import sample_encounter_view
        self.view = sample_encounter_view()

    def encounter_view(self, player_id: int):
        return self.view

    def engine_room_view(self, player_id: int):
        from types import SimpleNamespace
        return SimpleNamespace(subsystems=[])


@pytest.mark.parametrize("size", SIZES.values(), ids=SIZES.keys())
def test_encounter_sizes(snap_compare, size: tuple[int, int]) -> None:
    from edge.tui.screens.encounter import EncounterScreen

    async def open_encounter(pilot: Pilot) -> None:
        pilot.app.push_screen(EncounterScreen(_StaticEncounterService(), 1))
        await pilot.pause()

    assert snap_compare(EdgeApp(plain=True), terminal_size=size, run_before=open_encounter)


@pytest.mark.parametrize("size", SIZES.values(), ids=SIZES.keys())
def test_territory_sizes(snap_compare, size: tuple[int, int]) -> None:
    async def open_territory(pilot: Pilot) -> None:
        from dataclasses import replace

        from edge.tui.screens.territory import TerritoryScreen

        app = pilot.app
        assert isinstance(app, EdgeApp)
        service = app.start_new_game(seed=1986)
        ship = service.state.ships[service.state.players[app.player_id].ship_id]
        outside = next(s.id for s in service.state.sectors.values()
                       if not s.is_galactic_core)
        service.state.ships[ship.id] = replace(
            ship, sector_id=outside, fighters=40, mines=8,
            devices={**ship.devices, "probe": 2, "interdictor": 1})
        app.push_screen(TerritoryScreen(service, app.player_id))
        await pilot.pause()

    assert snap_compare(EdgeApp(plain=True), terminal_size=size, run_before=open_territory)


@pytest.mark.parametrize("theme", ["edge-high-contrast", "edge-monochrome"])
@pytest.mark.parametrize("surface", ["sector", "computer", "workbench", "contact", "combat"])
def test_dense_screen_themes(snap_compare, theme: str, surface: str) -> None:
    async def open_surface(pilot: Pilot) -> None:
        pilot.app.theme = theme
        if surface == "sector":
            await _open_seeded_game(pilot)
        elif surface == "computer":
            await _open_seeded_game(pilot, computer=True)
        elif surface == "contact":
            from edge.tui.dummy import sample_contact
            from edge.tui.screens.contact import AlienContactScreen
            pilot.app.push_screen(AlienContactScreen(sample_contact()))
        elif surface == "combat":
            from edge.tui.screens.encounter import EncounterScreen
            pilot.app.push_screen(EncounterScreen(_StaticEncounterService(), 1))
        await pilot.pause()

    if surface == "workbench":
        app = _WorkbenchApp(SHIP_WORKBENCH_PROFILE,
                            ["converter (I) x1", "burner (II) x2"])

        async def theme_workbench(pilot: Pilot) -> None:
            pilot.app.theme = theme

        assert snap_compare(app, terminal_size=SIZES["standard"],
                            run_before=theme_workbench)
    else:
        assert snap_compare(EdgeApp(plain=True), terminal_size=SIZES["standard"],
                            run_before=open_surface)


@pytest.mark.parametrize("theme", ["edge-high-contrast", "edge-monochrome"])
@pytest.mark.parametrize("surface", ["port", "planet", "surface", "territory", "base"])
def test_world_art_screen_themes(snap_compare, theme: str, surface: str) -> None:
    """WP-PR10: alternate-theme baselines for the remaining art-bearing families."""
    async def open_surface(pilot: Pilot) -> None:
        from dataclasses import replace

        app = pilot.app
        assert isinstance(app, EdgeApp)
        app.theme = theme
        service = app.start_new_game(seed=1986)
        if surface == "port":
            from edge.tui.screens.port import PortScreen
            screen = PortScreen(service, app.player_id)
        elif surface == "planet":
            from edge.tui.dummy import sample_planet
            from edge.tui.screens.planet import PlanetScreen
            screen = PlanetScreen(sample_planet())
        elif surface == "surface":
            from edge.tui.dummy import sample_surface
            from edge.tui.screens.surface import SurfaceScreen
            screen = SurfaceScreen(sample_surface())
        elif surface == "territory":
            from edge.tui.screens.territory import TerritoryScreen
            ship = service.state.ships[service.state.players[app.player_id].ship_id]
            outside = next(s.id for s in service.state.sectors.values()
                           if not s.is_galactic_core)
            service.state.ships[ship.id] = replace(ship, sector_id=outside, fighters=40)
            screen = TerritoryScreen(service, app.player_id)
        else:
            from edge.tui.screens.base import BaseScreen
            base = next(iter(service.state.starbases.values()))
            ship = service.state.ships[service.state.players[app.player_id].ship_id]
            service.state.ships[ship.id] = replace(ship, sector_id=base.sector_id)
            screen = BaseScreen(service, app.player_id, base.id)
        app.push_screen(screen)
        await pilot.pause()

    assert snap_compare(EdgeApp(plain=True), terminal_size=SIZES["standard"],
                        run_before=open_surface)
