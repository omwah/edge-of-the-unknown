"""Reusable Textual widgets for the ground-war POC.

`CountSelector` is a generic "pick a quantity of each of several things" table — a
header, one 3-high row per item (arbitrary display columns + a Units count with
right-side − / + buttons), row selection with ↑ / ↓ and − / + keys, an optional
per-unit-cost budget and total cap that block unaffordable adds, and the DataTable
look (zebra stripes, bold header, block-cursor highlight). It knows nothing about
what is being counted; it just posts `Changed` when a count moves. Reuse it
wherever a count-of-each selection is needed.

`PlatoonComposer` is the ground-war-specific squad composer built *on top of*
`CountSelector`: it feeds the selector the suit roster (Suit / Latinum / Role
columns, per-suit latinum cost, the latinum budget, the trooper cap), adds a DROP
button, and emits `Dropped(loadout)` when a valid squad is committed. That keeps
it portable: the main game (edge) can later fund a raid from the player's own
latinum by handing the same widget the player's suits and balance.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Static

from edge.groundwar.config import SuitClass

_COUNT_W = 6   # Units column width
_BTNS_W = 12   # header spacer over the two − / + buttons (5 + margin, ×2)


class _PmButton(Button):
    """A row's − / + button: mouse-clickable but not a Tab stop, so keyboard play
    stays on the selector's row highlight rather than cycling every little button.

    The press animation is disabled — for a stepper, the count updating is the
    feedback, and the lingering `-active` style otherwise left the button looking
    stuck 'pressed' after a click."""

    can_focus = False

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.active_effect_duration = 0.0


@dataclass(frozen=True)
class CountColumn:
    """One display column of a `CountSelector` (besides Units + the buttons)."""

    header: str
    width: int


@dataclass(frozen=True)
class CountItem:
    """One selectable row: a key, its display `cells` (one per `CountColumn`), an
    optional per-unit `cost` charged against the budget, and a starting count."""

    key: str
    cells: Sequence[str]
    cost: int = 0
    initial: int = 0


class CountSelector(Widget, can_focus=True):
    """A table for picking a count of each of several items. Emits `Changed`.

    Focus it and use ↑ / ↓ to pick a row and − / + to adjust; or click the row's
    − / + buttons. Adds that would exceed `budget` or `max_total` are refused.
    """

    DEFAULT_CSS = """
    CountSelector { height: auto; width: auto; }
    CountSelector .cs-row { height: 3; width: auto; }
    CountSelector .cs-row > Static { height: 100%; content-align: left middle; }
    /* Zebra stripes + bold header + block-cursor highlight, matching DataTable. */
    CountSelector .cs-row.even { background: $boost; }
    CountSelector .cs-head {
        height: 1; width: auto; text-style: bold; background: $panel; color: $foreground;
    }
    CountSelector .cs-head > Static { height: 1; }
    CountSelector .cs-row.selected {
        background: $block-cursor-blurred-background;
        color: $block-cursor-blurred-foreground;
        text-style: $block-cursor-blurred-text-style;
    }
    CountSelector:focus .cs-row.selected {
        background: $block-cursor-background;
        color: $block-cursor-foreground;
        text-style: $block-cursor-text-style;
    }
    CountSelector Button.cs-pm {
        width: 5; min-width: 5; height: 3; margin: 0 0 0 1; padding: 0;
    }
    CountSelector #cs-note { padding: 1 0; height: auto; }
    """

    class Changed(Message):
        """Posted whenever a count changes (add or remove)."""

        def __init__(self, selector: "CountSelector") -> None:
            self.selector = selector
            super().__init__()

    def __init__(
        self,
        items: Sequence[CountItem],
        *,
        columns: Sequence[CountColumn],
        budget: int | None = None,
        max_total: int | None = None,
        count_header: str = "Units",
        units_label: str = "units",
        currency_label: str = "latinum",
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.columns = list(columns)
        self.items = list(items)
        self.keys = [it.key for it in self.items]
        self._cost = {it.key: it.cost for it in self.items}
        self.budget = budget
        self.max_total = max_total
        self.count_header = count_header
        self.units_label = units_label
        self.currency_label = currency_label
        self.selected_row = 0
        self.counts: dict[str, int] = {it.key: max(0, it.initial) for it in self.items}

    @staticmethod
    def _cell(text: str, width: int, cls_id: str | None = None) -> Static:
        cell = Static(text, id=cls_id)
        cell.styles.width = width
        return cell

    def compose(self) -> ComposeResult:
        with Horizontal(classes="cs-row cs-head"):
            yield self._cell(self.count_header, _COUNT_W)
            for col in self.columns:
                yield self._cell(col.header, col.width)
            yield self._cell("", _BTNS_W)
        for i, it in enumerate(self.items):
            zebra = "even" if i % 2 == 0 else "odd"
            with Horizontal(classes=f"cs-row {zebra}", id=f"cs-row-{it.key}"):
                yield self._cell(str(self.counts[it.key]), _COUNT_W, f"cs-count-{it.key}")
                for col, val in zip(self.columns, it.cells):
                    yield self._cell(str(val), col.width)
                yield _PmButton("−", id=f"cs-minus-{it.key}", classes="cs-pm")
                yield _PmButton("+", id=f"cs-plus-{it.key}", classes="cs-pm")
        yield Static(id="cs-note")

    def on_mount(self) -> None:
        self._highlight()
        self._refresh(notify=False)

    # --- selected state --------------------------------------------------------

    @property
    def spent(self) -> int:
        return sum(self._cost[k] * n for k, n in self.counts.items())

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def within_limits(self) -> bool:
        return ((self.budget is None or self.spent <= self.budget)
                and (self.max_total is None or self.total <= self.max_total))

    @property
    def selected_key(self) -> str:
        return self.keys[self.selected_row]

    def nonzero(self) -> dict[str, int]:
        """Counts with the zeroes dropped."""
        return {k: n for k, n in self.counts.items() if n > 0}

    def _can_add(self, key: str) -> bool:
        """Whether one more of `key` fits both the budget and the total cap."""
        if self.budget is not None and self.spent + self._cost[key] > self.budget:
            return False
        if self.max_total is not None and self.total >= self.max_total:
            return False
        return True

    def _highlight(self) -> None:
        for i, k in enumerate(self.keys):
            self.query_one(f"#cs-row-{k}").set_class(i == self.selected_row, "selected")

    def _refresh(self, *, notify: bool = True) -> None:
        for k in self.keys:
            self.query_one(f"#cs-count-{k}", Static).update(str(self.counts[k]))
        over = not self.within_limits
        note = Text()
        pieces = [f"{self.total}"
                  + (f"/{self.max_total}" if self.max_total is not None else "")
                  + f" {self.units_label}"]
        if self.budget is not None:
            pieces.append(f"{self.spent}/{self.budget} {self.currency_label}")
        note.append("  " + " · ".join(pieces),
                    "bold red" if over else "bold bright_green")
        self.query_one("#cs-note", Static).update(note)
        if notify:
            self.post_message(self.Changed(self))

    def _adjust(self, key: str, delta: int) -> None:
        if delta > 0 and not self._can_add(key):
            self.app.bell()  # can't afford another / roster full
            return
        self.counts[key] = max(0, self.counts[key] + delta)
        self._refresh()

    # --- input -----------------------------------------------------------------

    def on_key(self, event: events.Key) -> None:
        if event.key in ("up", "down"):
            step = -1 if event.key == "up" else 1
            self.selected_row = (self.selected_row + step) % len(self.keys)
            self._highlight()
            event.stop()
        elif event.key in ("plus", "minus", "equals_sign"):
            self._adjust(self.selected_key, -1 if event.key == "minus" else 1)
            event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith(("cs-minus-", "cs-plus-")):
            k = bid.split("-", 2)[2]
            self.selected_row = self.keys.index(k)  # keep the highlight in sync
            self._highlight()
            self._adjust(k, -1 if bid.startswith("cs-minus-") else 1)
            event.stop()


class PlatoonComposer(Widget):
    """Squad composer over a `CountSelector` + a DROP button. Emits `Dropped`."""

    DEFAULT_CSS = """
    PlatoonComposer { height: auto; width: auto; }
    PlatoonComposer #composer-head { padding: 1 0 0 0; color: $text-muted; }
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
        self.role_blurbs = role_blurbs or {}
        self.drop_label = drop_label
        self.initial = initial or {}

    def compose(self) -> ComposeResult:
        yield Static("SQUAD — ↑ ↓ select, − / + adjust (or click the row buttons)",
                     id="composer-head")
        items = [
            CountItem(
                key=k,
                cells=(s.label, str(s.cost), self.role_blurbs.get(k, "")),
                cost=s.cost,
                initial=self.initial.get(k, 0),
            )
            for k, s in self.suits.items()
        ]
        columns = [CountColumn("Suit", 12), CountColumn("Latinum", 10),
                   CountColumn("Role", 18)]
        yield CountSelector(items, columns=columns, budget=self.budget,
                            max_total=self.max_troopers, units_label="troopers",
                            currency_label="latinum", id="composer-selector")
        yield Button(self.drop_label, id="composer-drop", variant="success")

    def on_mount(self) -> None:
        self._sync_drop()

    @property
    def selector(self) -> CountSelector:
        return self.query_one("#composer-selector", CountSelector)

    @property
    def loadout(self) -> dict[str, int]:
        return self.selector.nonzero()

    @property
    def valid(self) -> bool:
        s = self.selector
        return s.total > 0 and s.within_limits

    def _sync_drop(self) -> None:
        self.query_one("#composer-drop", Button).disabled = not self.valid

    def on_count_selector_changed(self, event: CountSelector.Changed) -> None:
        self._sync_drop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "composer-drop":
            event.stop()
            if self.valid:
                self.post_message(self.Dropped(self.loadout))
            else:
                self.app.bell()
