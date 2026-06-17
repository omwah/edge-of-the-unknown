"""ConfirmScreen — a small yes/no modal that dismisses with a bool.

Used where an action is destructive (e.g. "New game" overwrites the single save
slot). Defaults focus to the *deny* button so a stray Enter never destroys data.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "deny", "Cancel"),
        Binding("n", "deny", "No"),
        Binding("y", "confirm", "Yes"),
    ]

    CSS = """
    ConfirmScreen { align: center middle; }
    ConfirmScreen #confirm-box {
        width: 56; height: auto; padding: 1 2; border: round $primary; background: $surface;
    }
    ConfirmScreen #confirm-box Static { margin-bottom: 1; }
    ConfirmScreen #confirm-actions { height: auto; align-horizontal: center; }
    ConfirmScreen #confirm-actions Button { margin: 0 1; }
    """

    def __init__(self, message: str, *, confirm_label: str = "Yes",
                 deny_label: str = "No") -> None:
        super().__init__()
        self._message = message
        self._confirm_label = confirm_label
        self._deny_label = deny_label

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Static(self._message)
            with Horizontal(id="confirm-actions"):
                yield Button(self._confirm_label, id="confirm", variant="error")
                yield Button(self._deny_label, id="deny", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#deny", Button).focus()  # safe default: don't destroy on a stray Enter

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_deny(self) -> None:
        self.dismiss(False)
