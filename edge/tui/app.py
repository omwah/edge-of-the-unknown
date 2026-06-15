"""EdgeApp — the Textual application shell for the throwaway TUI skeleton.

Reads only the dummy DTOs in `edge.tui.dummy`; no engine/server yet (DESIGN.md
§3 keeps the TUI behind a service boundary — here that boundary is faked).
"""

from __future__ import annotations

import argparse

from textual.app import App
from textual.binding import Binding
from textual.theme import Theme

from edge.config import load_default_config
from edge.engine.ticker import EngineTicker
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui.screens.main_menu import MainMenuScreen

# A fixed default seed for "New game" — chosen so the player's opening neighbourhood
# reads well (a curated universe per the WP8 screenshot decision).
DEFAULT_SEED = 4

TW2002_THEME = Theme(
    name="tw2002",
    primary="#00cccc",      # cyan
    secondary="#cccc00",    # yellow
    accent="#cc00cc",       # magenta
    foreground="#c0c0c0",
    background="#000000",
    surface="#0a0a0a",
    panel="#101418",
    success="#00cc00",
    warning="#cccc00",
    error="#cc3030",
    dark=True,
)


class EdgeApp(App[None]):
    CSS_PATH = "app.tcss"
    TITLE = "Edge of the Unknown"
    # Textual's built-in quit is ctrl+q but priority + show=False, so it shadows
    # any screen binding and never reaches the footer. Re-declare it without
    # priority so a screen's own ctrl+q binding wins display; keep it hidden here
    # so the "^q Quit" label surfaces only where a screen opts in (the GameScreen).
    BINDINGS = [Binding("ctrl+q", "quit", "Quit", show=False)]

    player_id = 1

    def __init__(self, plain: bool = False) -> None:
        super().__init__()
        self.plain = plain
        self.service: GameService | None = None
        self._ticker: EngineTicker | None = None

    def on_mount(self) -> None:
        self.register_theme(TW2002_THEME)
        self.theme = "tw2002"
        self.push_screen(MainMenuScreen())

    def start_new_game(self, seed: int = DEFAULT_SEED) -> GameService:
        """Generate a fresh universe in-process and start the background ticker.

        Single-player embeds the service (DESIGN §3). The repository is in-memory
        for the skeleton; the ticker runs as a Textual worker (cancelled on exit).
        """
        config = load_default_config()
        self.service = GameService.new_game(config, seed, SqliteRepository(":memory:"))
        self._ticker = EngineTicker(self.service)
        self.run_worker(self._ticker.run(), name="engine-ticker", group="engine")
        return self.service


def main() -> None:
    parser = argparse.ArgumentParser(prog="edge")
    parser.add_argument(
        "--plain", action="store_true", help="disable starfield/CRT animation effects"
    )
    args = parser.parse_args()
    EdgeApp(plain=args.plain).run()


if __name__ == "__main__":
    main()
