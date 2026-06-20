"""Capture SVG screenshots of the screens for review.

Run with `pixi run shots`. Writes to docs/ui/shots/. The live screens (game,
port, stardock, map, computer) are captured against a real generated universe
(WP8): the player is navigated to a presentable sector via the service, then the
GameScreen is recomposed. The Phase 2-3 screens (planet, surface, engine room,
contact, encounter, messages) are still skeletons, captured by pushing them
directly with sample data.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from textual.widgets import TabbedContent

from edge.core.movement import shortest_path
from edge.core.rules import Warp
from edge.tui.app import EdgeApp
from edge.tui.dummy import (
    sample_contact,
    sample_encounter,
    sample_engine_room,
    sample_messages,
    sample_planet,
)
from edge.tui.screens.contact import AlienContactScreen
from edge.tui.screens.encounter import EncounterScreen
from edge.tui.screens.engine_room import EngineRoomScreen
from edge.tui.screens.messages import MessagesScreen
from edge.tui.screens.planet import PlanetScreen

OUT = Path("docs/ui/shots")

# Sprite-gallery tabs to capture, each to its own SVG: (TabPane id, file stem).
_GALLERY_TABS = [
    ("planets", "gallery-planets"),
    ("orbit", "gallery-orbit"),
    ("ports", "gallery-ports"),
    ("ships", "gallery-ships"),
    ("subsystems", "gallery-subsystems"),
]


async def _capture() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        app.save_screenshot(filename="main-menu.svg", path=str(OUT))

        await pilot.press("n")  # New game -> live GameScreen
        await pilot.pause()
        svc = app.service
        assert svc is not None
        state = svc.state
        ports = {p.sector_id: p for p in state.ports.values()}
        planet_sectors = {pl.sector_id for pl in state.planets.values()}

        async def goto(sector_id: int) -> None:
            here = state.ships[1].sector_id
            path = shortest_path(state.adjacency, here, sector_id)
            if path is None:
                return
            for hop in path[1:]:
                svc.apply(1, Warp(to_sector=hop))
            await app.screen.recompose()
            await pilot.pause()

        # A presentable sector: one that has both a port and a planet.
        nice = next((s for s in ports if s in planet_sectors), None)
        if nice is not None:
            await goto(nice)
        app.save_screenshot(filename="game.svg", path=str(OUT))

        # A plain commodities port -> the standalone trade screen.
        plain = next((s for s, p in ports.items() if p.klass.value != 9), None)
        if plain is not None:
            await goto(plain)
            await pilot.press("p")
            await pilot.pause()
            app.save_screenshot(filename="port.svg", path=str(OUT))
            await pilot.press("escape")
            await pilot.pause()

        # The StarDock -> services hub, Hardware tab.
        dock = next(s for s, p in ports.items() if p.klass.value == 9)
        await goto(dock)
        await pilot.press("p")
        await pilot.pause()
        app.screen.query_one(TabbedContent).active = "hardware"
        await pilot.pause()
        app.save_screenshot(filename="stardock.svg", path=str(OUT))
        await pilot.press("escape")
        await pilot.pause()

        await pilot.press("m")  # Galactic map (live)
        await pilot.pause()
        app.save_screenshot(filename="map.svg", path=str(OUT))
        await pilot.press("escape")
        await pilot.pause()

        await pilot.press("c")  # Ship computer (live pair-finder over seen ports)
        await pilot.pause()
        app.save_screenshot(filename="computer.svg", path=str(OUT))
        await pilot.press("escape")
        await pilot.pause()

        # The Phase 2-3 skeleton screens, pushed directly with sample data.
        app.push_screen(PlanetScreen(sample_planet()))
        await pilot.pause()
        app.save_screenshot(filename="planet.svg", path=str(OUT))
        await pilot.press("d")  # descend -> SurfaceScreen
        await pilot.pause()
        app.save_screenshot(filename="surface.svg", path=str(OUT))
        await pilot.press("escape")
        await pilot.press("escape")
        await pilot.pause()

        for name, screen in (
            ("engine-room", EngineRoomScreen(sample_engine_room())),
            ("contact", AlienContactScreen(sample_contact())),
            ("encounter", EncounterScreen(sample_encounter())),
            ("messages", MessagesScreen(sample_messages())),
        ):
            app.push_screen(screen)
            await pilot.pause()
            app.save_screenshot(filename=f"{name}.svg", path=str(OUT))
            await pilot.press("escape")
            await pilot.pause()

    # The secret sprite gallery is reached via the hidden "~" Main Menu key.
    gal = EdgeApp()
    async with gal.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.press("~")
        await pilot.pause()
        tabs = gal.screen.query_one(TabbedContent)
        for tab_id, stem in _GALLERY_TABS:
            tabs.active = tab_id
            await pilot.pause()
            gal.save_screenshot(filename=f"{stem}.svg", path=str(OUT))

    gallery_stems = ", ".join(stem for _, stem in _GALLERY_TABS)
    print(
        "wrote main-menu, game, port, stardock, map, computer, planet, surface, "
        f"engine-room, contact, encounter, messages, {gallery_stems} .svg to {OUT}"
    )


def main() -> None:
    # Capture against a throwaway save slot so "New game" starts immediately
    # (an existing real save would otherwise trip the overwrite confirm dialog)
    # and the user's actual save is never touched.
    with tempfile.TemporaryDirectory(prefix="edge-shots-") as scratch:
        os.environ["EDGE_SAVE_DIR"] = scratch
        asyncio.run(_capture())


if __name__ == "__main__":
    main()
