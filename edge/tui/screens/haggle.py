"""HaggleScreen — counter-offer prompt for a single haggle (DESIGN §8).

A small modal over the trade screen: the player types a per-unit counter price for
the highlighted commodity and sees a live likelihood hint (accepted / likely /
unlikely / insulting) from `GameService.haggle_quote`. Submitting dismisses with the
counter price; the caller turns it into a `HaggleOffer` command. Esc / empty cancels.

Phase 1 resolves one offer at a time (no rounds / history) — the multi-round session
is a drafted Phase-2 work package.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from edge.core.economy import EconomyError
from edge.core.enums import Commodity
from edge.server.service import GameService

_LABEL_COLOUR = {"accepted": "green", "likely": "green", "unlikely": "yellow", "insulting": "red"}


class HaggleScreen(ModalScreen[int | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    HaggleScreen { align: center middle; }
    HaggleScreen #haggle-box {
        width: 52; height: auto; padding: 1 2; border: round $secondary; background: $surface;
    }
    HaggleScreen #haggle-box Static { margin-bottom: 1; }
    HaggleScreen #haggle-hint { margin-bottom: 0; }
    """

    def __init__(
        self, service: GameService, player_id: int, commodity: Commodity,
        name: str, mode: str, fair: int, units: int,
    ) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id
        self._commodity = commodity
        self._name = name
        self._verb = "Sell" if mode == "BUY" else "Buy"  # mode is the port's stance
        self._fair = fair
        self._units = units

    def compose(self) -> ComposeResult:
        with Vertical(id="haggle-box"):
            yield Static(f"[b]Haggle: {self._verb} {self._name}[/]  [dim](Esc to walk away)[/]")
            yield Static(f"Quote  [yellow]{self._fair}[/]/u  ×  {self._units} units    "
                         f"[dim]fair ~ {self._fair}[/]")
            yield Input(placeholder="your counter price /u", id="haggle-input")
            yield Static("[dim]Enter a counter to see how it lands.[/]", id="haggle-hint")

    def _counter(self, raw: str) -> int | None:
        try:
            return int(raw.strip())
        except ValueError:
            return None

    def on_input_changed(self, event: Input.Changed) -> None:
        hint = self.query_one("#haggle-hint", Static)
        counter = self._counter(event.value)
        if counter is None or counter <= 0:
            hint.update("[dim]Enter a counter to see how it lands.[/]")
            return
        try:
            quote = self._service.haggle_quote(self._pid, self._commodity, counter)
        except EconomyError as exc:
            hint.update(f"[red]{exc}[/]")
            return
        colour = _LABEL_COLOUR.get(quote.label, "white")
        hint.update(f"At [yellow]{counter}[/]/u  ·  [{colour}]{quote.label}[/]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        counter = self._counter(event.value)
        self.dismiss(counter if counter is not None and counter > 0 else None)

    def action_cancel(self) -> None:
        self.dismiss(None)
