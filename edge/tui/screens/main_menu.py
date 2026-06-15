"""MainMenuScreen — title + starfield + menu (UI_MOCKUPS.md §0)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from edge.tui.dummy import sample_state
from edge.tui.screens.game import GameScreen
from edge.tui.screens.sprites_gallery import SpriteGalleryScreen
from edge.tui.widgets import Starfield

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
_SUBTITLE = "trade · discover · navigate the alien frontier"
_FOOTER = "v0.1"


class MainMenuScreen(Screen):
    BINDINGS = [
        Binding("n", "new_game", "New game"),
        Binding("c", "unavailable", "Continue"),
        Binding("l", "unavailable", "Load"),
        Binding("o", "unavailable", "Options"),
        Binding("q", "quit_app", "Quit"),
        # Secret: open the sprite gallery (dev preview). Unadvertised.
        Binding("~", "gallery", "Sprite gallery", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Starfield(animate=not getattr(self.app, "plain", False))
        with Container(id="menu-box"):
            yield Static(_BANNER, classes="title")
            yield Static(_SUBTITLE, classes="subtitle")
            with Vertical(id="menu-items"):
                yield Button("N  New game", id="new", variant="primary")
                yield Button("C  Continue  (no save found)", id="continue", disabled=True)
                yield Button("L  Load game …", id="load")
                yield Button("O  Options", id="options")
                yield Button("Q  Quit", id="quit")
            yield Static(_FOOTER, classes="footer")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "new":
                self.action_new_game()
            case "quit":
                self.action_quit_app()
            case _:
                self.action_unavailable()

    def action_new_game(self) -> None:
        self.app.push_screen(GameScreen(sample_state()))

    def action_gallery(self) -> None:
        self.app.push_screen(SpriteGalleryScreen())

    def action_unavailable(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)

    def action_quit_app(self) -> None:
        self.app.exit()
