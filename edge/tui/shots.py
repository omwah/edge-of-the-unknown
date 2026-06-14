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
        app.save_screenshot(filename="game.svg", path=str(OUT))
        await pilot.press("p")
        await pilot.pause()
        app.save_screenshot(filename="port.svg", path=str(OUT))
    print(f"wrote {OUT}/game.svg and {OUT}/port.svg")


def main() -> None:
    asyncio.run(_capture())


if __name__ == "__main__":
    main()
