"""EdgeApp — the Textual application shell for the throwaway TUI skeleton.

Reads only the dummy DTOs in `edge.tui.dummy`; no engine/server yet (DESIGN.md
§3 keeps the TUI behind a service boundary — here that boundary is faked).
"""

from __future__ import annotations

import argparse

from textual.app import App
from textual.theme import Theme

from edge.tui.dummy import sample_port
from edge.tui.screens.main_menu import MainMenuScreen
from edge.tui.screens.port import PortScreen

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
    SCREENS = {"port": lambda: PortScreen(sample_port())}
    TITLE = "Edge of the Unknown"

    def __init__(self, plain: bool = False) -> None:
        super().__init__()
        self.plain = plain

    def on_mount(self) -> None:
        self.register_theme(TW2002_THEME)
        self.theme = "tw2002"
        self.push_screen(MainMenuScreen())


def main() -> None:
    parser = argparse.ArgumentParser(prog="edge")
    parser.add_argument(
        "--plain", action="store_true", help="disable starfield/CRT animation effects"
    )
    args = parser.parse_args()
    EdgeApp(plain=args.plain).run()


if __name__ == "__main__":
    main()
