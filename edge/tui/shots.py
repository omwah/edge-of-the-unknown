"""Capture SVG screenshots of the skeleton screens for review.

Run with `pixi run shots`. Writes to docs/ui/shots/.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.widgets import TabbedContent

from edge.tui.app import EdgeApp

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
        await pilot.press("n")  # New game -> GameScreen
        await pilot.pause()
        app.save_screenshot(filename="game.svg", path=str(OUT))
        # Sector 7 holds a StarDock: docking (P) or clicking it opens the services
        # hub. Show the Hardware tab (the component emporium) rather than the
        # default Commodities tab.
        await pilot.press("p")
        await pilot.pause()
        app.screen.query_one(TabbedContent).active = "hardware"
        await pilot.pause()
        app.save_screenshot(filename="stardock.svg", path=str(OUT))
        await pilot.press("escape")  # back to GameScreen
        await pilot.pause()
        # A plain commodities port (no StarDock) opens the standalone trade screen.
        app.push_screen("port")
        await pilot.pause()
        app.save_screenshot(filename="port.svg", path=str(OUT))
        app.pop_screen()
        await pilot.pause()
        # Click the planet -> PlanetScreen.
        from edge.tui.widgets import ClickableEntry

        def entry(dest: str) -> ClickableEntry:
            return next(e for e in app.screen.query(ClickableEntry) if e._dest == dest)

        await pilot.click(entry("planet"))
        await pilot.pause()
        app.save_screenshot(filename="planet.svg", path=str(OUT))
        # Descend (D) -> SurfaceScreen.
        await pilot.press("d")
        await pilot.pause()
        app.save_screenshot(filename="surface.svg", path=str(OUT))
        await pilot.press("escape")  # ascend to orbit
        await pilot.press("escape")  # break orbit -> GameScreen
        await pilot.pause()
        # Galactic map (M).
        await pilot.press("m")
        await pilot.pause()
        app.save_screenshot(filename="map.svg", path=str(OUT))
        await pilot.press("escape")  # back to GameScreen
        await pilot.pause()
        # Ship computer (C).
        await pilot.press("c")
        await pilot.pause()
        app.save_screenshot(filename="computer.svg", path=str(OUT))
        await pilot.press("escape")  # back to GameScreen
        await pilot.pause()
        # Engine room (E).
        await pilot.press("e")
        await pilot.pause()
        app.save_screenshot(filename="engine-room.svg", path=str(OUT))
        await pilot.press("escape")  # back to GameScreen
        await pilot.pause()
        # Hail the friendly trader (Kestrel) -> AlienContactScreen.
        await pilot.click(entry("contact"))
        await pilot.pause()
        app.save_screenshot(filename="contact.svg", path=str(OUT))
        await pilot.press("escape")  # break contact -> GameScreen
        await pilot.pause()
        # Engage the hostile (Cabal Marauder) -> EncounterScreen.
        await pilot.click(entry("encounter"))
        await pilot.pause()
        app.save_screenshot(filename="encounter.svg", path=str(OUT))
        await pilot.press("escape")  # disengage -> GameScreen
        await pilot.pause()
        # Message log (G).
        await pilot.press("g")
        await pilot.pause()
        app.save_screenshot(filename="messages.svg", path=str(OUT))

    # The secret sprite gallery is a TabbedContent (one category per tab), so the
    # running app reaches it via the hidden "~" Main Menu key. Capture every tab
    # in turn so the PDF handout shows all asset categories, not just the default.
    gal = EdgeApp()
    async with gal.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.press("~")  # Main Menu -> SpriteGalleryScreen
        await pilot.pause()
        tabs = gal.screen.query_one(TabbedContent)
        for tab_id, stem in _GALLERY_TABS:
            tabs.active = tab_id
            await pilot.pause()
            gal.save_screenshot(filename=f"{stem}.svg", path=str(OUT))

    gallery_stems = ", ".join(stem for _, stem in _GALLERY_TABS)
    print(
        "wrote main-menu, game, stardock, port, planet, surface, map, computer, "
        f"engine-room, contact, encounter, messages, {gallery_stems} .svg to {OUT}"
    )


def main() -> None:
    asyncio.run(_capture())


if __name__ == "__main__":
    main()
