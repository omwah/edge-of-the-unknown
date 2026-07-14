"""AmountPrompt — a small modal that asks "how many?" and dismisses with the number.

The keyboard/mouse pair to `ConfirmScreen` for actions that commit a *quantity* rather than a
yes/no: it wraps the shared `AmountStepper` (so typing, −/+ stepping, and the clamp behave as
they do on the Stardock and in the transfer workbench), clamps to `1..maximum`, and offers a
one-key "all" for the common case. Dismisses with the chosen amount, or `None` if cancelled —
so a caller reads it exactly like a confirm, and a destructive action still gets its warning
line via `message`.

It **is** the confirmation for a destructive action (an invasion is one), so it inherits
`ConfirmScreen`'s safety rule: when `dangerous`, focus lands on **Cancel**, and Enter presses
whatever is focused rather than committing from anywhere — a stray Enter can never land troops.
Enter inside the amount field submits the amount, because that is unambiguous intent.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from edge.tui.amount_stepper import AmountStepper


class AmountPrompt(ModalScreen[int | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("a", "all", "All"),
    ]

    CSS = """
    AmountPrompt { align: center middle; background: $background 60%; }
    AmountPrompt #amount-box { width: 60; height: auto; padding: 1 2; }
    AmountPrompt #amount-box Static { margin-bottom: 1; }
    AmountPrompt #amount-row { height: auto; margin-bottom: 1; }
    AmountPrompt #amount-actions { height: auto; align-horizontal: center; }
    AmountPrompt #amount-actions Button { margin: 0 1; }
    """

    def __init__(self, message: str, maximum: int, *, value: int | None = None,
                 step: int = 1, commit_label: str = "Commit",
                 dangerous: bool = False) -> None:
        super().__init__()
        self._message = message
        self._maximum = max(1, maximum)
        self._value = min(self._maximum, max(1, value if value is not None else self._maximum))
        self._step = step
        self._commit_label = commit_label
        self._dangerous = dangerous

    def compose(self) -> ComposeResult:
        with Vertical(id="amount-box", classes="modal-box"):
            yield Static(self._message)
            with Horizontal(id="amount-row"):
                yield AmountStepper("amount", value=self._value, step=self._step,
                                    maximum=self._maximum)
                yield Static(f"  [dim]of {self._maximum:,} · \\[A] all[/]")
            with Horizontal(id="amount-actions"):
                yield Button(self._commit_label, id="amount-commit",
                             variant="error" if self._dangerous else "primary")
                yield Button("Cancel", id="amount-cancel")
        yield Static()  # keeps the box off the very bottom row at compact heights

    def on_mount(self) -> None:
        # A button, never the field: a focused Input would eat `a` (all) as typing. Which button
        # is the safety rule — a destructive prompt lands on Cancel (ConfirmScreen's convention),
        # so a stray Enter after the hotkey confirms nothing.
        target = "#amount-cancel" if self._dangerous else "#amount-commit"
        self.query_one(target, Button).focus()

    def on_input_submitted(self) -> None:
        """Enter *in the amount field* commits: typing a number and pressing Enter is intent."""
        self.action_commit()

    @property
    def _stepper(self) -> AmountStepper:
        return self.query_one(AmountStepper)

    def action_all(self) -> None:
        self._stepper.set_amount(self._maximum)

    def action_commit(self) -> None:
        amount = min(self._maximum, max(1, self._stepper.amount))
        self.dismiss(amount)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "amount-commit":
            self.action_commit()
        elif event.button.id == "amount-cancel":
            self.action_cancel()
