"""EdgeApp — the Textual application shell for the throwaway TUI skeleton.

Reads only the dummy DTOs in `edge.tui.dummy`; no engine/server yet (DESIGN.md
§3 keeps the TUI behind a service boundary — here that boundary is faked).
"""

from __future__ import annotations

import argparse
import random

from textual.app import App
from textual.binding import Binding
from textual.theme import Theme

from edge.config import load_default_config
from edge.server.service import DialogueConfigMismatchError
from edge.core.config import SceneArtConfig, UIConfig
from edge.server.client import LocalClient
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui import art_adapter
from edge.tui.saves import clear_slot, default_save, has_save
from edge.tui.screens.main_menu import MainMenuScreen

# Fallback seed when neither the caller nor the config supplies one (random, below).
_SEED_MAX = 2**31 - 1

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

    def __init__(self, plain: bool = False, connect: str | None = None) -> None:
        super().__init__()
        self.plain = plain
        # A remote-play target (`edge --connect ws://…`, WP68): when set, on_mount opens the
        # LobbyScreen instead of the local main menu, and `service` resolves to the sync bridge.
        self._connect_url = connect
        self._remote_service: object | None = None
        self._remote_bridge: object | None = None
        # The app talks to the game exclusively through a `GameClient` (WP61); single-player
        # is a `LocalClient` wrapping the in-process service. `service` stays exposed as a
        # back-compat property (screens/tests read the synchronous `GameService` through it —
        # Textual's compose/render are synchronous, so the screen-level await migration is
        # deferred; the load-bearing seam is that the *client* now owns the ticker).
        self.client: LocalClient | None = None
        # SectorView sprite-scene sizes + warp-grid options; replaced from config
        # when a game starts.
        self.scene_art = SceneArtConfig()
        self.ui_config = UIConfig()
        self.max_warps_per_sector = 6  # TW2002 cap; reserves the warp grid's row count
        self.computer_tab = "trade"  # last Computer tab, restored when reopened with [C]

    @property
    def service(self) -> GameService | None:
        """The synchronous game surface the screens read (WP61/WP68).

        Single-player: the in-process `GameService` via the owning `LocalClient`. Remote play:
        the `RemoteService` sync bridge over the hosted client (set once the lobby joins a game).
        """
        if self._remote_service is not None:
            return self._remote_service  # type: ignore[return-value]
        return self.client.service if self.client is not None else None

    def on_mount(self) -> None:
        self.register_theme(TW2002_THEME)
        self.theme = "tw2002"
        if self._connect_url is not None:  # remote play (WP68): straight to the lobby turnstile
            from edge.tui.screens.lobby import LobbyScreen
            self.push_screen(LobbyScreen(self._connect_url))
        else:
            self.push_screen(MainMenuScreen())

    def on_unmount(self) -> None:
        """Tear down the remote loop/thread on exit (WP68)."""
        if self._remote_bridge is not None:
            self._remote_bridge.close()  # type: ignore[attr-defined]

    def start_new_game(self, seed: int | None = None) -> GameService:
        """Generate a fresh universe on disk and start the background ticker.

        The seed comes from `seed` if given, else `config.seed`, else a random roll
        (config `seed:` left empty). The chosen seed is persisted, so the game still
        replays from (seed, command log).

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
        if seed is None:
            seed = config.seed if config.seed is not None else random.randrange(_SEED_MAX)
        service = GameService.new_game(config, seed, SqliteRepository(save))
        self.client = LocalClient(service, player_id=self.player_id)
        self._start_ticker(self.client)
        return service

    def continue_game(self) -> GameService | None:
        """Reload the saved game by replaying its command log (DESIGN §12).

        Returns None when no save exists or when the save is incompatible with the current
        dialogue config (mismatch shown as a notification). The big bang is regenerated from
        the saved seed, then the durable command log is replayed on top.
        """
        if not has_save():
            return None
        config = load_default_config()
        self._apply_art_config(config)
        try:
            service = GameService.load_game(config, SqliteRepository(default_save()))
        except DialogueConfigMismatchError as exc:
            self.notify(str(exc), severity="error", timeout=8)
            return None
        self.client = LocalClient(service, player_id=self.player_id)
        self._start_ticker(self.client)
        return service

    def _apply_art_config(self, config: object) -> None:
        """Validate art coverage and read scene-sprite sizes before a game starts.

        `validate_art_coverage` raises if any roster species names an archetype the
        art engine can't paint (fail fast on roster/art drift). The art layer is
        presentation, so this check lives here in the TUI, not in core/server.
        """
        art_adapter.validate_art_coverage(config)  # type: ignore[arg-type]
        self.scene_art = config.scene  # type: ignore[attr-defined]
        self.ui_config = config.ui  # type: ignore[attr-defined]
        self.max_warps_per_sector = config.bigbang.max_warps_per_sector  # type: ignore[attr-defined]

    def _start_ticker(self, client: LocalClient) -> None:
        """Run the client-owned engine ticker as a Textual worker (WP61).

        The ticker is owned by whoever owns the service — `LocalClient` here, the net server
        for a hosted game (WP63) — so the TUI just starts it and forgets it.
        """
        self.run_worker(client.run_ticker(), name="engine-ticker", group="engine")


def _serve(host: str, port: int, *, plain: bool, connect: str | None = None) -> None:
    """Host the app in a browser via `textual-serve` (DESIGN §11, §15; WP68 remote).

    The served subprocess runs the *plain* `edge` invocation (never `--serve`), so each browser
    session gets an ordinary app instance and there is no recursion. With `connect`, each served
    session is an `edge --connect ws://…` remote client — the hosted-play recipe (docs/HOSTING.md).
    """
    from textual_serve.server import Server

    command = "python -m edge.tui"
    if plain:
        command += " --plain"
    if connect:
        command += f" --connect {connect}"
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
    parser.add_argument("--connect", metavar="URL",
                        help="play a hosted game over a websocket, e.g. ws://host:8765 (WP68)")
    args = parser.parse_args()
    if args.serve:
        _serve(args.host, args.port, plain=args.plain, connect=args.connect)
        return
    EdgeApp(plain=args.plain, connect=args.connect).run()


if __name__ == "__main__":
    main()
