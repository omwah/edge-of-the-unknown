"""WP-UI22 geometry guards for compact player-facing screens."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from textual.widget import Widget

from edge.tui.app import EdgeApp
from edge.tui.screens.computer import ComputerScreen
from edge.tui.screens.game import GameScreen
from edge.tui.screens.lobby import LobbyScreen


def _has_scrollable_ancestor(widget: Widget) -> bool:
    parent = widget.parent
    while isinstance(parent, Widget):
        if parent.is_scrollable:
            return True
        parent = parent.parent
    return False


def _assert_controls_reachable(app: EdgeApp) -> None:
    screen_region = app.screen.region
    for widget in app.screen.query("*"):
        if not widget.can_focus or not widget.display or widget.disabled:
            continue
        visible = widget.region.intersection(screen_region)
        assert visible or _has_scrollable_ancestor(widget), (
            f"{type(app.screen).__name__} control {widget.id or type(widget).__name__} "
            "is outside the viewport and has no keyboard-scrollable ancestor"
        )


@pytest.mark.parametrize(
    "surface",
    [
        "sector", "computer", "lobby", "port", "stardock", "planet", "surface",
        "contact", "encounter", "territory", "base", "help", "detail-modal",
    ],
)
async def test_compact_art_screen_controls_are_visible_or_scrollable(surface: str) -> None:
    """Every WP-PR10 art-bearing family stays operable at the 80x24 floor.

    The two modal cases cover the shared help and detail/picker containers used by
    art-screen overlays; individual prompt contents do not change their geometry.
    """
    app = EdgeApp(plain=True)
    async with app.run_test(size=(80, 24)) as pilot:
        service = app.start_new_game(seed=1986)
        if surface == "sector":
            screen = GameScreen(service, app.player_id)
        elif surface == "computer":
            screen = ComputerScreen(service, app.player_id, initial_tab="ports")
        elif surface == "lobby":
            screen = LobbyScreen("ws://host.example:8765")
        elif surface == "port":
            from edge.tui.screens.port import PortScreen
            screen = PortScreen(service, app.player_id)
        elif surface == "stardock":
            from edge.tui.screens.stardock import StardockScreen
            screen = StardockScreen(service, app.player_id, initial_tab="devices")
        elif surface == "planet":
            from edge.tui.dummy import sample_planet
            from edge.tui.screens.planet import PlanetScreen
            screen = PlanetScreen(sample_planet())
        elif surface == "surface":
            from edge.tui.dummy import sample_surface
            from edge.tui.screens.surface import SurfaceScreen
            screen = SurfaceScreen(sample_surface())
        elif surface == "contact":
            from edge.tui.dummy import sample_contact
            from edge.tui.screens.contact import AlienContactScreen
            screen = AlienContactScreen(sample_contact())
        elif surface == "encounter":
            from edge.tui.dummy import sample_encounter_view
            from edge.tui.screens.encounter import EncounterScreen

            class StaticEncounterService:
                def encounter_view(self, player_id: int):
                    return sample_encounter_view()

                def engine_room_view(self, player_id: int):
                    return SimpleNamespace(subsystems=[])

            screen = EncounterScreen(StaticEncounterService(), app.player_id)
        elif surface == "territory":
            from edge.tui.screens.territory import TerritoryScreen
            ship = service.state.ships[service.state.players[app.player_id].ship_id]
            outside = next(s.id for s in service.state.sectors.values()
                           if not s.is_galactic_core)
            service.state.ships[ship.id] = replace(ship, sector_id=outside, fighters=40)
            screen = TerritoryScreen(service, app.player_id)
        elif surface == "base":
            from edge.tui.screens.base import BaseScreen
            base = next(iter(service.state.starbases.values()))
            ship = service.state.ships[service.state.players[app.player_id].ship_id]
            service.state.ships[ship.id] = replace(ship, sector_id=base.sector_id)
            screen = BaseScreen(service, app.player_id, base.id)
        elif surface == "help":
            from edge.tui.screens.help import HelpScreen
            screen = HelpScreen(GameScreen(service, app.player_id))
        else:
            from edge.tui.screens.picker import ListPicker
            screen = ListPicker("Object details", [("Inspect", "inspect"), ("Leave", "leave")])

        app.push_screen(screen)
        await pilot.pause()
        await pilot.pause()
        _assert_controls_reachable(app)
