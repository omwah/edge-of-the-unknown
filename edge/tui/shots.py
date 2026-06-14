"""Capture SVG screenshots of the skeleton screens for review.

Run with `pixi run shots`. Writes to docs/ui/shots/.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from edge.tui.app import EdgeApp

OUT = Path("docs/ui/shots")


async def _capture() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        app.save_screenshot(filename="main-menu.svg", path=str(OUT))
        await pilot.press("n")  # New game -> GameScreen
        await pilot.pause()
        app.save_screenshot(filename="game.svg", path=str(OUT))
        await pilot.press("p")  # dock at port
        await pilot.pause()
        app.save_screenshot(filename="port.svg", path=str(OUT))
        await pilot.press("escape")  # back to GameScreen
        await pilot.pause()
        # Click the sector's Stardock port -> StarDockScreen.
        from edge.tui.widgets import ClickableEntry

        entries = list(app.screen.query(ClickableEntry))
        await pilot.click(entries[0])
        await pilot.pause()
        app.save_screenshot(filename="stardock.svg", path=str(OUT))
        await pilot.press("escape")
        await pilot.pause()
        # Click the planet -> PlanetScreen.
        await pilot.click(list(app.screen.query(ClickableEntry))[1])
        await pilot.pause()
        app.save_screenshot(filename="planet.svg", path=str(OUT))
    print(f"wrote main-menu, game, port, stardock, planet .svg to {OUT}")


def main() -> None:
    asyncio.run(_capture())


if __name__ == "__main__":
    main()
