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
from edge.core.config import SceneArtConfig, UIConfig
from edge.engine.ticker import EngineTicker
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui import art_adapter
from edge.tui.saves import clear_slot, default_save, has_save
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
        # SectorView sprite-scene sizes + warp-grid options; replaced from config
        # when a game starts.
        self.scene_art = SceneArtConfig()
        self.ui_config = UIConfig()

    def on_mount(self) -> None:
        self.register_theme(TW2002_THEME)
        self.theme = "tw2002"
        self.push_screen(MainMenuScreen())

    def start_new_game(self, seed: int = DEFAULT_SEED) -> GameService:
        """Generate a fresh universe on disk and start the background ticker.

        Single-player embeds the service (DESIGN §3). The repository is a WAL
        SQLite file (the single save slot); a new game replaces any prior slot so
        its command log starts clean. The ticker runs as a Textual worker
        (cancelled on exit).
        """
        config = load_default_config()
        self._apply_art_config(config)
        save = default_save()
        save.parent.mkdir(parents=True, exist_ok=True)
        clear_slot()
        self.service = GameService.new_game(config, seed, SqliteRepository(save))
        self._start_ticker(self.service)
        return self.service

    def continue_game(self) -> GameService | None:
        """Reload the saved game by replaying its command log (DESIGN §12).

        Returns None when no save exists. The big bang is regenerated from the
        saved seed, then the durable command log is replayed on top.
        """
        if not has_save():
            return None
        config = load_default_config()
        self._apply_art_config(config)
        self.service = GameService.load_game(config, SqliteRepository(default_save()))
        self._start_ticker(self.service)
        return self.service

    def _apply_art_config(self, config: object) -> None:
        """Validate art coverage and read scene-sprite sizes before a game starts.

        `validate_art_coverage` raises if any roster species names an archetype the
        art engine can't paint (fail fast on roster/art drift). The art layer is
        presentation, so this check lives here in the TUI, not in core/server.
        """
        art_adapter.validate_art_coverage(config)  # type: ignore[arg-type]
        self.scene_art = config.scene  # type: ignore[attr-defined]
        self.ui_config = config.ui  # type: ignore[attr-defined]

    def _start_ticker(self, service: GameService) -> None:
        self._ticker = EngineTicker(service)
        self.run_worker(self._ticker.run(), name="engine-ticker", group="engine")


def _serve(host: str, port: int, *, plain: bool) -> None:
    """Host the app in a browser via `textual-serve` (DESIGN §11, §15).

    The served subprocess runs the *plain* `edge` invocation (never `--serve`), so
    each browser session gets an ordinary app instance and there is no recursion.
    """
    from textual_serve.server import Server

    command = "python -m edge.tui --plain" if plain else "python -m edge.tui"
    Server(command, host=host, port=port).serve()


def main() -> None:
    parser = argparse.ArgumentParser(prog="edge")
    parser.add_argument(
        "--plain", action="store_true", help="disable starfield/CRT animation effects"
    )
    parser.add_argument(
        "--serve", action="store_true", help="host the app in a web browser instead of the terminal"
    )
    parser.add_argument("--host", default="localhost", help="bind host for --serve")
    parser.add_argument("--port", type=int, default=8000, help="bind port for --serve")
    args = parser.parse_args()
    if args.serve:
        _serve(args.host, args.port, plain=args.plain)
        return
    EdgeApp(plain=args.plain).run()


if __name__ == "__main__":
    main()
