"""EdgeApp — the Textual application shell for the throwaway TUI skeleton.

Reads only the dummy DTOs in `edge.tui.dummy`; no engine/server yet (DESIGN.md
§3 keeps the TUI behind a service boundary — here that boundary is faked).
"""

from __future__ import annotations

import argparse
import random
import sys
from typing import Any, Iterable

from textual import events
from textual.app import App, SystemCommand
from textual.binding import Binding
from textual.screen import Screen

from edge.config import load_default_config
from edge.server.service import DialogueConfigMismatchError
from edge.core.config import SceneArtConfig, UIConfig
from edge.server.client import GameClient, LocalClient
from edge.server.service import GameService
from edge.store.repo import SqliteRepository
from edge.tui.chrome import notify_error, notify_warning
from edge.tui import art_adapter
from edge.tui.saves import clear_slot, default_save, has_save
from edge.tui.design import EDGE_THEMES, LayoutTier, layout_tier, screen_actions
from edge.tui.settings import load_settings, save_settings
from edge.tui.screens.main_menu import MainMenuScreen

# Fallback seed when neither the caller nor the config supplies one (random, below).
_SEED_MAX = 2**31 - 1

class EdgeApp(App[None]):
    CSS_PATH = "app.tcss"
    TITLE = "Edge of the Unknown"
    # Textual's built-in quit is ctrl+q but priority + show=False, so it shadows
    # any screen binding and never reaches the footer. Re-declare it without
    # priority so a screen's own ctrl+q binding wins display; keep it hidden here
    # so the "^q Quit" label surfaces only where a screen opts in (the GameScreen).
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=False),
        # The numbered context-action menu (WP73, D3): one key lists everything
        # doable on the current screen. App-level so every screen gets it for free.
        Binding("full_stop", "action_menu", "Actions", show=False),
        # Contextual help: `?` opens the current screen's keys + notes. App-level,
        # so every screen gets it for free (the game screen advertises it).
        Binding("question_mark", "help", "Help", show=False),
    ]

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
        # back-compat property (older screens/tests still read the synchronous `GameService`
        # through it). GroundExpeditionScreen is the first live screen moved end-to-end onto
        # the async facade (GW-WP07); the client also owns the embedded ticker.
        self.client: GameClient | None = None
        # SectorView sprite-scene sizes + warp-grid options; replaced from config
        # when a game starts.
        self.scene_art = SceneArtConfig()
        # Last station sizing inputs from the rendered SectorScene. Docked headers
        # feed them through the same resolver instead of guessing the hidden scene.
        self.sector_station_reference: tuple[int, int | None, int] | None = None
        self.ui_config = UIConfig()
        self.max_warps_per_sector = 6  # TW2002 cap; reserves the warp grid's row count
        self.computer_tab = "trade"  # last Computer subview, restored when reopened with [C]
        # WP-UI20: each Computer category remembers its own last subview.
        self.computer_subviews: dict[str, str] = {}
        self.ui_settings, self._settings_warning = load_settings()
        self.layout_tier = LayoutTier.STANDARD

    def action_action_menu(self) -> None:
        """Open the numbered context-action menu over the current screen (WP73, D3)."""
        from textual.screen import ModalScreen
        from edge.tui.screens.action_menu import ActionMenuScreen
        if isinstance(self.screen, ModalScreen):
            return  # modals (prompts, confirms, the menu itself) keep their own keys
        self.push_screen(ActionMenuScreen(self.screen))

    def action_help(self) -> None:
        """Open contextual help for the current screen (`?` anywhere)."""
        from textual.screen import ModalScreen
        from edge.tui.screens.help import HelpScreen
        if isinstance(self.screen, ModalScreen):
            return  # modals keep their own keys (and `?` may be typed input there)
        self.push_screen(HelpScreen(self.screen))

    def get_system_commands(self, screen: Screen[Any]) -> Iterable[SystemCommand]:
        """Expose current-screen actions through Textual's fuzzy command palette."""
        yield from super().get_system_commands(screen)
        for descriptor in screen_actions(screen):
            if not descriptor.enabled or not descriptor.action:
                continue

            async def run(action: str = descriptor.action) -> None:
                await screen.run_action(action)

            yield SystemCommand(descriptor.title, descriptor.help, run, discover=True)

    @property
    def service(self) -> GameService | None:
        """The synchronous game surface the screens read (WP61/WP68).

        Single-player: the in-process `GameService` via the owning `LocalClient`. Remote play:
        the `RemoteService` sync bridge over the hosted client (set once the lobby joins a game).
        """
        if self._remote_service is not None:
            return self._remote_service  # type: ignore[return-value]
        return self.client.service if isinstance(self.client, LocalClient) else None

    def on_mount(self) -> None:
        for theme in EDGE_THEMES:
            self.register_theme(theme)
        self.theme = (self.ui_settings.theme if self.ui_settings.theme in self.available_themes
                      else "edge-ansi")
        self.layout_tier = layout_tier(self.size.width, self.size.height)
        self._stamp_layout_class()  # before the first screen lays out, not a frame later
        if self._connect_url is not None:  # remote play (WP68): straight to the lobby turnstile
            from edge.tui.screens.lobby import LobbyScreen
            self.push_screen(LobbyScreen(self._connect_url))
        else:
            self.push_screen(MainMenuScreen())
        self.call_after_refresh(self._apply_layout_class)
        if self._settings_warning:
            self.call_after_refresh(
                lambda: notify_warning(self, self._settings_warning or "")
            )

    def on_resize(self, event: events.Resize) -> None:
        """Recompute the layout tier and apply its class across the screen stack."""
        tier = layout_tier(event.size.width, event.size.height)
        self.layout_tier = tier
        self._stamp_layout_class()
        self.call_after_refresh(self._apply_layout_class)

    def push_screen(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        """Push, then stamp the current tier class on the new screen (WP-UI07).

        Mount/resize alone would leave a screen pushed *between* resizes without
        the tier class, so tier-scoped CSS (e.g. `.compact .modal-box`) would
        silently not apply to it.

        The stamp is **synchronous** (PT-42 follow-up). Deferring it to
        `call_after_refresh` meant every pushed screen was laid out once with untiered
        CSS and then *again* a frame later once the class landed — which the player sees
        as the screen visibly resizing itself just after it opens (panels and modals
        snapping to a new width, art panels re-rendering at a new size). The class has to
        be on the screen before its first layout, not after it.
        """
        result = super().push_screen(*args, **kwargs)
        self._stamp_layout_class()
        self.call_after_refresh(self._sync_size_notice)
        return result

    def _stamp_layout_class(self) -> None:
        # Every screen in the stack tracks the tier: a modal must not strand a
        # stale breakpoint class on the screen it will reveal when dismissed.
        for screen in self.screen_stack:
            for tier in LayoutTier:
                screen.remove_class(tier.value)
            screen.add_class(self.layout_tier.value)

    def _apply_layout_class(self) -> None:
        self._stamp_layout_class()
        self._sync_size_notice()

    def _sync_size_notice(self) -> None:
        """Overlay the below-minimum notice under 80×24; pop it on regrowth (WP-UI05)."""
        from edge.tui.chrome import SizeNoticeScreen
        if not self.screen_stack:
            return  # nothing mounted yet; on_mount re-syncs after the first screen
        showing = isinstance(self.screen, SizeNoticeScreen)
        notice_in_stack = any(isinstance(screen, SizeNoticeScreen)
                              for screen in self.screen_stack)
        if self.layout_tier is LayoutTier.UNSUPPORTED and not notice_in_stack:
            self.push_screen(SizeNoticeScreen())
        elif self.layout_tier is not LayoutTier.UNSUPPORTED and showing:
            self.pop_screen()

    def update_ui_settings(self, **changes: Any) -> None:
        """Persist local-only presentation settings and apply the theme immediately."""
        from dataclasses import replace
        self.ui_settings = replace(self.ui_settings, **changes)
        save_settings(self.ui_settings)
        if "theme" in changes:
            self.theme = self.ui_settings.theme

    def mark_objective(self, objective_id: str) -> None:
        """Tick off a Captain's objective (WP-UI11) — local progress only.

        Called from the UI seam where the player performs the act (dock, trade,
        …). Idempotent; updates any mounted strip in place and toasts the first
        completion so the feedback lands even when the strip is off-screen.
        """
        from edge.tui.onboarding import OBJECTIVE_IDS, OBJECTIVES, ObjectivesStrip, all_done
        done = self.ui_settings.objectives_done
        if objective_id in done or objective_id not in OBJECTIVE_IDS:
            return
        done = tuple(o for o in OBJECTIVE_IDS if o in (*done, objective_id))
        self.update_ui_settings(objectives_done=done)
        if self.ui_settings.show_onboarding:
            label = next(lbl for oid, lbl, _ in OBJECTIVES if oid == objective_id)
            suffix = " — all objectives complete!" if all_done(done) else ""
            self.notify(f"{label} ✓{suffix}", title="Objective", timeout=3)
        for screen in self.screen_stack:
            for strip in screen.query(ObjectivesStrip):
                strip.show_progress(done) if not all_done(done) else strip.remove()

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
            notify_error(self, str(exc))
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


def _serve(
    host: str,
    port: int,
    *,
    plain: bool,
    connect: str | None = None,
    public_url: str | None = None,
) -> None:
    """Host the app in a browser via `textual-serve` (DESIGN §11, §15; WP68 remote).

    The served subprocess runs the *plain* `edge` invocation (never `--serve`), so each browser
    session gets an ordinary app instance and there is no recursion. With `connect`, each served
    session is an `edge --connect ws://…` remote client — the hosted-play recipe (docs/HOSTING.md).

    `public_url` is the address the *browser* reaches us on. textual-serve bakes the session
    websocket URL into the page from this (falling back to `host:port`) rather than deriving it
    from the request, so serving to any other machine — LAN, WSL, container, port-forward —
    needs it set or the page dials `ws://localhost` on the viewer's box and hangs on the splash.
    """
    from textual_serve.server import Server

    command = f"{sys.executable} -m edge.tui"
    if plain:
        command += " --plain"
    if connect:
        command += f" --connect {connect}"
    Server(
        command,
        host=host,
        port=port,
        title="Edge of the Unknown",
        public_url=public_url,
    ).serve()


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
    parser.add_argument(
        "--public-url",
        metavar="URL",
        help="address the browser reaches --serve on, e.g. http://192.168.1.50:8000; "
        "required when viewing from another machine, WSL, or a container",
    )
    parser.add_argument("--connect", metavar="URL",
                        help="play a hosted game over a websocket, e.g. ws://host:8765 (WP68)")
    args = parser.parse_args()
    if args.serve:
        _serve(
            args.host,
            args.port,
            plain=args.plain,
            connect=args.connect,
            public_url=args.public_url,
        )
        return
    EdgeApp(plain=args.plain, connect=args.connect).run()


if __name__ == "__main__":
    main()
