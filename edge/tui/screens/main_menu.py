"""MainMenuScreen — title + starfield + menu (UI_MOCKUPS.md §0)."""

from __future__ import annotations

import asyncio

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical

from edge.tui.chrome import EdgeScreen
from textual.widgets import Button, Static

from edge.tui.saves import has_save, save_summary
from edge.tui.screens.confirm import ConfirmScreen
from edge.tui.screens.game import GameScreen
from edge.tui.screens.sprites_gallery import SpriteGalleryScreen
from edge.tui.widgets import Starfield
from edge.server.service import DialogueConfigMismatchError

_BANNER = r"""
 ___ ___   ___ ___    ___  ___   _____ _  _ ___
| __|   \ / __| __|  / _ \| __| |_   _| || | __|
| _|| |) | (_ | _|  | (_) | _|    | | | __ | _|
|___|___/ \___|___|  \___/|_|     |_| |_||_|___|

 _   _ _  _ _  ___  _  _____      ___  _
| | | | \| | |/ / \| |/ _ \ \    / / \| |
| |_| | .` | ' <| .` | (_) \ \/\/ /| .` |
 \___/|_|\_|_|\_\_|\_|\___/ \_/\_/ |_|\_|
""".strip("\n")
_SUBTITLE = "\ntrade · discover · navigate the alien frontier"
_FOOTER = "v0.1"


class MainMenuScreen(EdgeScreen):
    BINDINGS = [
        Binding("n", "new_game", "New game"),
        Binding("c", "continue_game", "Continue"),
        Binding("o", "options", "Options"),
        Binding("q", "quit_app", "Quit"),
        # Arrow keys walk the menu buttons like a classic title screen.
        Binding("down", "app.focus_next", "Next", show=False),
        Binding("up", "app.focus_previous", "Previous", show=False),
        # Secret: open the sprite gallery (dev preview). Unadvertised.
        Binding("~", "gallery", "Sprite gallery", show=False),
    ]
    # WP-UI06: new_game overwrites the single save slot — its method confirms
    # via the shared ConfirmScreen (enforced by tests/test_ui_actions.py).
    ACTION_DANGER = {"new_game": "destructive"}

    _loading = False

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # A save load is in flight — block every menu action (including arrow-key
        # focus movement) so the title screen can't be driven while it's busy.
        if self._loading:
            return False
        return super().check_action(action, parameters)

    def _set_menu_disabled(self, disabled: bool) -> None:
        for button in self.query(Button):
            button.disabled = disabled

    def compose(self) -> ComposeResult:
        saved = has_save()
        settings = getattr(self.app, "ui_settings", None)
        reduced = bool(settings and settings.reduced_motion)
        yield Starfield(animate=not getattr(self.app, "plain", False) and not reduced)
        with Container(id="menu-box"):
            yield Static(_BANNER, classes="title")
            yield Static(_SUBTITLE, classes="subtitle")
            # The saved-game card sits between the title block and the actions, so
            # the button list stays uninterrupted (WP-UI11 follow-up).
            if saved and (summary := save_summary()) is not None:
                card = Static(
                    f"Day {summary.day_number} · [dim]Seed {summary.seed}[/]\n"
                    f"Last Played {summary.last_played}",
                    classes="save-card",
                )
                card.border_title = "Saved game"
                yield card
            with Vertical(id="menu-items"):
                # The likely intent leads and is the sole primary action: Continue
                # when a save exists, otherwise New game (WP-UI11).
                new = Button("N  New game", id="new", variant="default" if saved else "primary")
                cont = Button("C  Continue" if saved else "C  Continue  (no save found)",
                              id="continue", disabled=not saved,
                              variant="primary" if saved else "default")
                yield from (cont, new) if saved else (new, cont)
                yield Button("O  Options", id="options")
                yield Button("Q  Quit", id="quit")
            yield Static(_FOOTER, classes="footer")

    def on_mount(self) -> None:
        # With a save present, Continue is the likely intent — focus it (and it's
        # enabled); otherwise fall back to New game.
        self.query_one("#continue" if has_save() else "#new", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "new":
                self.action_new_game()
            case "continue":
                self.action_continue_game()
            case "options":
                self.action_options()
            case "quit":
                self.action_quit_app()

    def action_new_game(self) -> None:
        # A new game replaces the single save slot — confirm before destroying it.
        if has_save():
            self.app.push_screen(
                ConfirmScreen(
                    "Starting a new game overwrites your existing save. Continue?",
                    confirm_label="Overwrite", deny_label="Keep save",
                ),
                self._on_new_game_confirmed,
            )
            return
        self._begin_new_game()

    def _on_new_game_confirmed(self, overwrite: bool | None) -> None:
        if overwrite:
            self._begin_new_game()

    def _begin_new_game(self) -> None:
        service = self.app.start_new_game()  # type: ignore[attr-defined]
        self.app.push_screen(GameScreen(service, self.app.player_id))  # type: ignore[attr-defined]

    @work(exclusive=True, group="continue-game")
    async def action_continue_game(self) -> None:
        if not has_save():
            self.notify("No save found — start a new game.", timeout=2)
            return
        self._loading = True
        self._set_menu_disabled(True)
        button = self.query_one("#continue", Button)
        button.label = "Loading saved game…"

        def progress(stage: str, done: int, total: int) -> None:
            self.app.call_from_thread(self._show_load_progress, stage, done, total)

        try:
            service = await asyncio.to_thread(
                self.app.continue_game,  # type: ignore[attr-defined]
                worker_thread=True,
                progress=progress,
            )
        except DialogueConfigMismatchError as exc:
            self.notify(str(exc), title="Error", severity="error", timeout=6)
            self._loading = False
            self._set_menu_disabled(False)
            button.label = "C  Continue"
            return
        if service is None:
            self._loading = False
            self._set_menu_disabled(False)
            button.label = "C  Continue"
            return  # error already shown via app.notify
        self._loading = False
        self._set_menu_disabled(False)
        self.app.attach_local_game(service)  # type: ignore[attr-defined]
        self.app.push_screen(GameScreen(service, self.app.player_id))  # type: ignore[attr-defined]

    def _show_load_progress(self, stage: str, done: int, total: int) -> None:
        button = self.query_one("#continue", Button)
        if total > 0:
            button.label = f"{stage}  {min(100, done * 100 // total)}%"
        else:
            button.label = stage

    def action_gallery(self) -> None:
        self.app.push_screen(SpriteGalleryScreen())

    def action_options(self) -> None:
        from edge.tui.screens.options import OptionsScreen
        self.app.push_screen(OptionsScreen())

    def action_quit_app(self) -> None:
        self.app.exit()
