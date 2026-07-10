"""ListPicker — the shared pick-one-from-a-list modal (keyboard + mouse).

Every "choose one" prompt (tech offers, dossier subjects, commodities, garrison
modes) rides this one modal: ↑/↓ move the highlight, Enter confirms it, a click
picks a row directly, Esc cancels. The overlay is translucent — the screen
underneath stays visible behind the box (the ActionMenu/Help convention) instead
of blanking to the background colour.

Dismisses with the picked option's `ref` (an int or str the caller supplied), or
None on cancel.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from edge.tui.widgets import ClickableEntry


class ListPicker(ModalScreen[int | str | None]):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("enter", "choose", "Choose", priority=True),
    ]

    CSS = """
    /* Translucent so the screen underneath shows through behind the box. */
    ListPicker { align: center middle; background: $background 60%; }
    ListPicker #picker-box {
        width: 50; max-height: 80%; height: auto; padding: 1 2;
        border: round $primary; background: $surface;
    }
    ListPicker #picker-title { margin-bottom: 1; }
    ListPicker #picker-hint { margin-top: 1; color: $text-muted; }
    """

    def __init__(self, title: str, options: list[tuple[str, int | str]],
                 *, width: int = 50) -> None:
        """`options` are (markup label, ref) rows; the ref comes back on dismiss."""
        super().__init__()
        self._title = title
        self._options = options
        self._width = width
        self._index = 0
        self._rows: list[ClickableEntry] = []

    def compose(self) -> ComposeResult:
        box = Vertical(id="picker-box")
        box.styles.width = self._width
        with box:
            yield Static(f"[b]{self._title}[/]", id="picker-title")
            self._rows = [
                ClickableEntry(self._line(i), dest="pick", ref=str(i), classes="picker-row")
                for i in range(len(self._options))
            ]
            with VerticalScroll():
                yield from self._rows
            yield Static("[dim]↑/↓ select · Enter choose · click picks · Esc cancels[/]",
                         id="picker-hint")

    def _line(self, i: int) -> str:
        label, _ = self._options[i]
        if i == self._index:
            return f"[reverse] ▸ {label} [/]"
        return f"   {label}"

    def _refresh_rows(self, *indices: int) -> None:
        for i in indices:
            if 0 <= i < len(self._rows):
                self._rows[i].update(self._line(i))

    def _move(self, delta: int) -> None:
        if not self._options:
            return
        old = self._index
        self._index = (self._index + delta) % len(self._options)
        self._refresh_rows(old, self._index)

    def action_cursor_up(self) -> None:
        self._move(-1)

    def action_cursor_down(self) -> None:
        self._move(1)

    def action_choose(self) -> None:
        if self._options:
            self.dismiss(self._options[self._index][1])

    @on(ClickableEntry.Picked)
    def on_row_picked(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest == "pick" and msg.ref is not None:
            self.dismiss(self._options[int(msg.ref)][1])

    def action_cancel(self) -> None:
        self.dismiss(None)
