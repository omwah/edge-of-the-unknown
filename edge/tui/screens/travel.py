"""TravelPromptScreen — pick a destination for multi-hop travel (WP-C).

A small modal that asks for a destination sector number and dismisses with it
(or `None` on cancel). The GameScreen turns the answer into a `TravelTo` command,
which is route-locked to sectors the player has already uncovered (§9, §11).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class TravelPromptScreen(ModalScreen[int | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    TravelPromptScreen { align: center middle; }
    TravelPromptScreen #travel-box {
        width: 48; height: auto; padding: 1 2; border: round $primary; background: $surface;
    }
    TravelPromptScreen #travel-box Static { margin-bottom: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="travel-box"):
            yield Static("[b]Travel to sector[/]  [dim](known route only · Esc to cancel)[/]")
            yield Input(placeholder="sector number", id="travel-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        try:
            self.dismiss(int(event.value.strip()))
        except ValueError:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
