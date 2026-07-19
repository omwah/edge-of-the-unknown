"""Reusable Textual widgets for the ground-war POC.

`PlatoonComposer` packages the squad-composition control — a DataTable of suit
classes with −/+ adjustment, a latinum budget/roster check, a totals line, and a
DROP button — as one self-contained widget. It carries **no** generation or battle
logic: it just emits `Dropped(loadout)` when a valid squad is committed, leaving
seed / planet / difficulty (and what to *do* with the loadout) to the host screen.

That keeps it portable: the POC setup screen builds it from a `GroundwarConfig`,
and the main game (edge) can later reuse the same control to fund a raid from the
player's own latinum balance — pass the player's suit roster, their latinum as the
budget, whatever roster cap applies, and handle `PlatoonComposer.Dropped`.
"""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, DataTable, Static

from edge.groundwar.config import SuitClass


class PlatoonComposer(Widget):
    """Suit table + budget note + DROP button. Emits `Dropped(loadout)`."""

    DEFAULT_CSS = """
    PlatoonComposer { height: auto; }
    PlatoonComposer #composer-head { padding: 1 0 0 0; color: $text-muted; }
    PlatoonComposer #composer-table { height: auto; max-height: 12; margin-top: 1; }
    PlatoonComposer #composer-note { padding: 1 0; height: auto; }
    """

    class Dropped(Message):
        """Posted when the DROP button commits a valid squad."""

        def __init__(self, loadout: dict[str, int]) -> None:
            self.loadout = loadout
            super().__init__()

    def __init__(
        self,
        suits: dict[str, SuitClass],
        *,
        budget: int,
        max_troopers: int,
        initial: dict[str, int] | None = None,
        role_blurbs: dict[str, str] | None = None,
        drop_label: str = "DROP!",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.suits = suits
        self.budget = budget
        self.max_troopers = max_troopers
        self.types = list(suits)  # stable row order
        self.role_blurbs = role_blurbs or {}
        self.drop_label = drop_label
        self.counts: dict[str, int] = {t: 0 for t in self.types}
        for k, n in (initial or {}).items():
            if k in self.counts:
                self.counts[k] = n

    def compose(self) -> ComposeResult:
        yield Static("SQUAD — Tab here, ↑↓ to move, − / + to adjust", id="composer-head")
        yield DataTable(id="composer-table")
        yield Static(id="composer-note")
        yield Button(self.drop_label, id="composer-drop", variant="success")

    def on_mount(self) -> None:
        t = self.query_one("#composer-table", DataTable)
        t.cursor_type = "row"
        t.zebra_stripes = True
        t.add_column("Suit", key="suit", width=10)
        t.add_column("×", key="count", width=5)
        t.add_column("Latinum", key="cost", width=9)
        t.add_column("Role", key="role", width=16)
        for k in self.types:
            s = self.suits[k]
            t.add_row(s.label, f"×{self.counts[k]}", str(s.cost),
                      self.role_blurbs.get(k, ""), key=k)
        self._refresh()

    # --- composed state --------------------------------------------------------

    @property
    def spent(self) -> int:
        return sum(self.suits[k].cost * n for k, n in self.counts.items())

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def loadout(self) -> dict[str, int]:
        """Suit -> count, dropping the zeroes — the payload of `Dropped`."""
        return {k: n for k, n in self.counts.items() if n > 0}

    @property
    def valid(self) -> bool:
        return 0 < self.total <= self.max_troopers and self.spent <= self.budget

    def _refresh(self) -> None:
        t = self.query_one("#composer-table", DataTable)
        for k in self.types:
            t.update_cell(k, "count", f"×{self.counts[k]}")
        over = self.spent > self.budget or self.total > self.max_troopers
        note = Text()
        note.append(f"  {self.total}/{self.max_troopers} troopers · "
                    f"{self.spent}/{self.budget} latinum",
                    "bold red" if over else "bold bright_green")
        if self.total == 0:
            note.append("  — pick a squad!", "bold red")
        self.query_one("#composer-note", Static).update(note)
        self.query_one("#composer-drop", Button).disabled = not self.valid

    # --- input -----------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        """− / + adjust the count of the suit under the table cursor."""
        if event.key not in ("plus", "minus", "equals_sign"):
            return
        t = self.query_one("#composer-table", DataTable)
        if self.app.focused is not t:
            return
        delta = -1 if event.key == "minus" else 1
        k = self.types[t.cursor_row]
        self.counts[k] = max(0, self.counts[k] + delta)
        self._refresh()
        event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "composer-drop":
            return
        event.stop()
        if self.valid:
            self.post_message(self.Dropped(self.loadout))
        else:
            self.app.bell()
