"""RumorModal — reveals the lead a tavern rumour just bought (WP-PR2-03 / PT-35).

Buying a rumour used to only flash a "logged in your computer" line; the player
never saw what they paid for. This small modal shows the purchased lead's human
summary, then the lead stays filed in the ship's computer as before. Keyboard-first:
Enter or Escape (or the Close button) dismisses it.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class RumorModal(ModalScreen[None]):
    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("enter", "close", "Close"),
    ]

    CSS = """
    RumorModal { align: center middle; background: $background 60%; }
    RumorModal #rumor-box { max-width: 60; }
    RumorModal #rumor-box Static { margin-bottom: 1; }
    RumorModal #rumor-actions { height: auto; align-horizontal: center; }
    """

    def __init__(self, summary: str) -> None:
        super().__init__()
        self._summary = summary

    def compose(self) -> ComposeResult:
        with Vertical(id="rumor-box", classes="modal-box"):
            yield Static("[b yellow]RUMOUR[/]")
            yield Static(f"“{self._summary}”")
            yield Static("[dim]Logged to your computer as a lead you can plot.[/]")
            with Horizontal(id="rumor-actions"):
                yield Button("Close", id="close", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#close", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
