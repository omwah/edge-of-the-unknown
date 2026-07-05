"""HelpScreen — a centred Help modal (Ctrl+H), opening on the Warp Legend.

A reference overlay for the sector screen. It currently holds the warp colour/arrow
legend that used to sit in the status sidebar; it is structured so further help
sections can be appended beneath it later.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from edge.tui.widgets import warp_legend_markup


class HelpScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close"),
        Binding("q", "close", "Close"),
    ]

    CSS = """
    /* Translucent so the game window shows through behind the box (the global
       `Screen` rule would otherwise paint it opaque and blank the screen). */
    HelpScreen { align: center middle; background: $background 60%; }
    HelpScreen #help-box {
        width: 80; max-height: 80%; height: auto; padding: 1 2;
        border: round $primary; background: $surface;
    }
    HelpScreen #help-title { text-style: bold; color: $primary; margin-bottom: 1; }
    HelpScreen .help-section { text-style: bold; color: $secondary; margin-top: 1; }
    HelpScreen #help-footer { color: $text-muted; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        # Resolve config-driven anchor side from the app
        ui_config = getattr(self.app, "ui_config", None)
        side = ui_config.nav_core_anchor_side if ui_config else "left"

        with VerticalScroll(id="help-box"):
            yield Static("Help", id="help-title")
            yield Static(warp_legend_markup(side))
            yield Static("[dim]Esc to close[/]", id="help-footer")

    def action_close(self) -> None:
        self.dismiss(None)
