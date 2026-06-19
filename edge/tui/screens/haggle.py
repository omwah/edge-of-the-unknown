"""HaggleScreen — the multi-round haggle session (DESIGN §8, WP13).

A modal over the trade screen: the player types a per-unit counter and sees a live
likelihood hint (accepted / likely / unlikely / insulting / exhausted) from
`GameService.haggle_quote`. Submitting issues a `HaggleOffer`; the screen reacts to the
`Haggled` result and **stays open across rounds** — accept closes the deal, a pass burns
the port's patience ("Round N of M"), and once the per-day `max_rejections` is reached
the port holds firm at the fair price. Esc walks away. Dismisses `True` if a deal closed
(the caller refreshes), else `False`.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from edge.core.economy import EconomyError
from edge.core.enums import Commodity
from edge.core.events import Traded
from edge.core.rules import HaggleOffer
from edge.server.service import GameService

_LABEL_COLOUR = {
    "accepted": "green", "likely": "green", "unlikely": "yellow",
    "insulting": "red", "exhausted": "red",
}


class HaggleScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "walk", "Walk away")]

    CSS = """
    HaggleScreen { align: center middle; }
    HaggleScreen #haggle-box {
        width: 54; height: auto; padding: 1 2; border: round $secondary; background: $surface;
    }
    HaggleScreen #haggle-box Static { margin-bottom: 1; }
    HaggleScreen #haggle-round { color: $secondary; margin-bottom: 0; }
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
        q = service.haggle_quote(player_id, commodity, fair)
        self._attempts = q.attempts
        self._max = q.max_attempts

    def compose(self) -> ComposeResult:
        with Vertical(id="haggle-box"):
            yield Static(f"[b]Haggle: {self._verb} {self._name}[/]  [dim](Esc to walk away)[/]")
            yield Static(self._round_text(), id="haggle-round")
            yield Static(f"Quote  [yellow]{self._fair}[/]/u  ×  {self._units} units", id="haggle-quote")
            yield Input(placeholder="your counter price /u", id="haggle-input")
            yield Static(self._opening_hint(), id="haggle-hint")

    def _round_text(self) -> str:
        if self._attempts >= self._max:
            return f"[red]Round {self._max} of {self._max} — they've closed negotiations.[/]"
        return f"Round {self._attempts + 1} of {self._max}"

    def _opening_hint(self) -> str:
        if self._attempts >= self._max:
            return "[red]They won't budge today. Walk away (Esc).[/]"
        return "[dim]Enter a counter to see how it lands.[/]"

    def _counter(self, raw: str) -> int | None:
        try:
            value = int(raw.strip())
        except ValueError:
            return None
        return value if value > 0 else None

    def on_input_changed(self, event: Input.Changed) -> None:
        hint = self.query_one("#haggle-hint", Static)
        counter = self._counter(event.value)
        if counter is None:
            hint.update(self._opening_hint())
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
        if counter is None:
            return
        try:
            events = self._service.apply(
                self._pid, HaggleOffer(commodity=self._commodity, units=self._units, counter_price=counter))
        except EconomyError as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return

        if any(isinstance(e, Traded) for e in events):
            self.notify(f"Deal! {self._verb} {self._units} {self._name} @ {counter}/u.", timeout=2)
            self.dismiss(True)
            return

        # No deal: re-read the port's patience and reflect the spent round.
        self._attempts = self._service.haggle_quote(self._pid, self._commodity, self._fair).attempts
        self.query_one("#haggle-round", Static).update(self._round_text())
        self.query_one("#haggle-input", Input).value = ""
        if self._attempts >= self._max:
            self.query_one("#haggle-hint", Static).update(
                "[red]They won't haggle further today. Walk away (Esc).[/]")
        else:
            self.notify("No deal — counter again or walk away.", severity="warning", timeout=2)
            self.query_one("#haggle-hint", Static).update(
                "[dim]They passed. Sweeten the offer or Esc to walk.[/]")

    def action_walk(self) -> None:
        self.dismiss(False)
