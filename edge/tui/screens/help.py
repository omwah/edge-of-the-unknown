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
    HelpScreen { align: center middle; }
    HelpScreen #help-box {
        width: 64; max-height: 80%; height: auto; padding: 1 2;
        border: round $primary; background: $surface;
    }
    HelpScreen #help-title { text-style: bold; color: $primary; margin-bottom: 1; }
    HelpScreen .help-section { text-style: bold; color: $secondary; margin-top: 1; }
    HelpScreen #help-footer { color: $text-muted; margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-box"):
            yield Static("Help", id="help-title")
            yield Static("Warp Legend", classes="help-section")
            yield Static(warp_legend_markup())
            yield Static("[dim]Esc to close[/]", id="help-footer")

    def action_close(self) -> None:
        self.dismiss(None)
