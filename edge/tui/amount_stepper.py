"""Shared exact-amount field with −/+ stepping for logistics and recruitment."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input


class AmountStepper(Horizontal):
    """An integer input followed by decrement/increment buttons."""

    DEFAULT_CSS = """
    AmountStepper { width: auto; height: auto; }
    AmountStepper Input { width: 11; }
    AmountStepper .step { width: 5; min-width: 5; }
    """

    def __init__(
        self, key: str, *, value: int = 0, step: int = 10, maximum: int | None = None
    ) -> None:
        super().__init__(id=f"stepper-{key}")
        self.key = key
        self.step = step
        self.maximum = maximum
        self.initial_value = value

    def compose(self) -> ComposeResult:
        # `select_on_focus=False`: focusing must not select the whole amount, or the next
        # keystroke silently *replaces* it instead of extending it — which breaks typing a
        # multi-digit amount (the Stardock's Colonists tab types the first digit for you,
        # then hands the field focus so the rest is ordinary typing).
        yield Input(value=str(self.initial_value), id=f"amt-{self.key}", type="integer",
                    select_on_focus=False)
        yield Button("−", id=f"dec-{self.key}", classes="step")
        yield Button("+", id=f"inc-{self.key}", classes="step")

    @property
    def amount(self) -> int:
        try:
            value = max(0, int(self.query_one(Input).value or "0"))
        except ValueError:
            value = 0
        return min(value, self.maximum) if self.maximum is not None else value

    def set_amount(self, value: int) -> None:
        value = max(0, value)
        if self.maximum is not None:
            value = min(value, self.maximum)
        self.query_one(Input).value = str(value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == f"dec-{self.key}":
            self.set_amount(self.amount - self.step)
            event.stop()
        elif event.button.id == f"inc-{self.key}":
            self.set_amount(self.amount + self.step)
            event.stop()
