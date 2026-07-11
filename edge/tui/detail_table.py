"""DetailTable — the standardized Computer table (WP-UI21).

One widget for every Computer subview table so alignment, zebra stripes,
cursor style, headers, empty states, filtering, sorting, column folding, and
detail views are never re-implemented per subview:

- **Stable row keys**: hosts supply `(key, cells)` rows; the cursor is
  preserved by key across refreshes, filtering, and sorting, and actions
  resolve the highlighted row through its key — never a raw row index.
- **`/` filtering**: an always-visible one-line filter narrows the *displayed*
  rows by case-insensitive substring across every column (including folded
  ones). Purely presentational — the host's DTO lists are never touched.
- **Sorting**: clicking a sortable header (marked ↕/▲/▼) sorts by that column,
  numeric-aware; clicking again reverses. `O` cycles the sort from the
  keyboard. Only columns declared `sortable` participate.
- **Tier awareness**: columns marked `fold` are hidden at the compact tier and
  surface in the row detail instead — Enter/click on a row opens a detail
  overlay in compact, while the wide tier shows a persistent side detail pane
  that follows the highlighted row.
- **Empty states**: zero rows swap the table for the shared `EmptyState`
  (distinguishing "nothing here yet" from "nothing matches the filter").

Presentation-only: the module never imports the service or issues commands.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, Static

from edge.tui.chrome import EmptyState

Cell = "str | Text"
Row = "tuple[str, tuple[object, ...]]"


@dataclass(frozen=True)
class ColumnSpec:
    """One column: its header, tier folding, sortability, and alignment."""

    label: str
    fold: bool = False      # hidden at the compact tier; shown in row detail
    sortable: bool = False  # header click / `O` sorts by this column
    right: bool = False     # numeric column — right-aligned


def _plain(cell: object) -> str:
    return cell.plain if isinstance(cell, Text) else Text.from_markup(str(cell)).plain


def _cell_markup(cell: object) -> str:
    return cell.markup if isinstance(cell, Text) else str(cell)


def _sort_value(cell: object) -> tuple[int, float] | tuple[int, str]:
    """Numeric-aware sort key: '1,240', 'S12', '87%' sort as numbers."""
    s = _plain(cell).strip().replace(",", "").rstrip("%")
    m = re.fullmatch(r"[A-Za-z]?(-?\d+(?:\.\d+)?)", s)
    if m:
        return (0, float(m.group(1)))
    return (1, s.lower())


class DetailOverlay(ModalScreen[None]):
    """The compact-tier row detail: every column (folded ones included)."""

    BINDINGS = [Binding("escape", "close", "Close"),
                Binding("enter", "close", "Close", show=False)]

    CSS = """
    DetailOverlay { align: center middle; background: $background 60%; }
    DetailOverlay .overlay-hint { margin-top: 1; color: $text-muted; }
    """

    def __init__(self, title: str, lines: list[str]) -> None:
        super().__init__()
        self._title = title
        self._lines = lines

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-box"):
            yield Static(f"[b]{self._title}[/]")
            yield Static("\n".join(self._lines))
            yield Static("[dim]Esc closes[/]", classes="overlay-hint")

    def action_close(self) -> None:
        self.dismiss(None)


class DetailTable(Vertical):
    BINDINGS = [
        Binding("slash", "open_filter", "Filter", show=False),
        Binding("o", "cycle_sort", "Sort", show=False),
    ]

    DEFAULT_CSS = """
    DetailTable { height: auto; }
    DetailTable #dt-body { height: auto; }
    DetailTable .dt-main { height: auto; width: 1fr; }
    DetailTable .table-filter {
        height: 1; border: none; padding: 0 1; margin-top: 1;
        background: $boost; color: $text-muted;
    }
    DetailTable .table-filter:focus { color: $text; background: $surface; }
    /* Visible only at the wide tier — toggled programmatically in _rebuild,
       because scoped DEFAULT_CSS cannot key off the screen's tier class. */
    DetailTable .table-detail {
        width: 34; height: auto; max-height: 18;
        overflow-y: auto; margin: 1 0 0 2; border: round $primary; padding: 0 1;
    }
    """

    def __init__(self, table_id: str, columns: tuple[ColumnSpec, ...], *,
                 empty: tuple[str, str] = ("Nothing here yet.", ""),
                 detail_title: str = "Details", **kwargs: Any) -> None:
        super().__init__(id=f"{table_id}-panel", **kwargs)
        self._table_id = table_id
        self._columns = columns
        self._empty = empty
        self._detail_title = detail_title
        self._rows: list[tuple[str, tuple[object, ...]]] = []
        self._group_first: frozenset[str] = frozenset()
        self._filter = ""
        self._sort_index: int | None = None
        self._sort_desc = False
        self._compact: bool | None = None

    # --- layout ----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Horizontal(id="dt-body"):
            with Vertical(classes="dt-main"):
                yield Input(placeholder="/ filter…", classes="table-filter",
                            id=f"{self._table_id}-filter")
                yield DataTable(id=self._table_id, zebra_stripes=True,
                                cursor_type="row")
                yield EmptyState(*self._empty, id=f"{self._table_id}-empty")
            detail = Static("", classes="table-detail",
                            id=f"{self._table_id}-detail")
            detail.border_title = self._detail_title
            detail.display = False
            yield detail

    def on_mount(self) -> None:
        self._compact = self._is_compact()
        self._rebuild()
        # The app stamps tier classes via call_after_refresh on push — the
        # class may not be on the screen yet while this widget mounts.
        self.call_after_refresh(self._check_tier)

    def on_resize(self) -> None:
        # The app stamps tier classes after the resize settles — re-check then.
        self.call_after_refresh(self._check_tier)

    def _check_tier(self) -> None:
        compact = self._is_compact()
        if compact != self._compact:
            self._compact = compact
        self._rebuild()

    def _is_compact(self) -> bool:
        screen = self.screen
        return screen is not None and screen.has_class("compact")

    def _is_wide(self) -> bool:
        screen = self.screen
        return screen is not None and screen.has_class("wide")

    # --- data ------------------------------------------------------------------

    def set_rows(self, rows: Sequence[tuple[str, tuple[object, ...]]], *,
                 empty: tuple[str, str] | None = None,
                 group_first: Sequence[str] = ()) -> None:
        """Replace the backing rows (presentation copy only), keeping the
        cursor on the same logical row when it survives the refresh.

        `group_first` names row keys that always sort ahead of the rest — the priority
        group (owned planets/ports, active contracts, WP-PR09). User column sorts and
        filtering apply *within* each group, so grouping never fights the chosen sort.
        """
        self._rows = list(rows)
        self._group_first = frozenset(group_first)
        if empty is not None:
            self._empty = empty
        if self.is_mounted:
            self._rebuild()

    def _visible_columns(self) -> list[tuple[int, ColumnSpec]]:
        compact = bool(self._compact)
        return [(i, c) for i, c in enumerate(self._columns)
                if not (compact and c.fold)]

    def _display_rows(self) -> list[tuple[str, tuple[object, ...]]]:
        rows = self._rows
        if self._filter:
            needle = self._filter.lower()
            rows = [r for r in rows
                    if any(needle in _plain(c).lower() for c in r[1])]
        if self._sort_index is not None:
            index = self._sort_index
            rows = sorted(rows, key=lambda r: _sort_value(r[1][index]),
                          reverse=self._sort_desc)
        if self._group_first:
            # Stable partition: priority-group rows first, column order preserved within each.
            rows = sorted(rows, key=lambda r: r[0] not in self._group_first)
        return rows

    def cursor_key(self) -> str | None:
        """The stable key of the highlighted row, or None."""
        table = self.query_one(DataTable)
        if not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return key.value

    def _header_label(self, index: int, spec: ColumnSpec) -> Text:
        label = spec.label
        if spec.sortable:
            marker = (" ▼" if self._sort_desc else " ▲") \
                if self._sort_index == index else " ↕"
            label += marker
        return Text(label, justify="right" if spec.right else "left")

    def _rebuild(self) -> None:
        table = self.query_one(DataTable)
        preserve = self.cursor_key()
        table.clear(columns=True)
        columns = self._visible_columns()
        for i, spec in columns:
            table.add_column(self._header_label(i, spec), key=str(i))
        shown = self._display_rows()
        for key, cells in shown:
            rendered = []
            for i, spec in columns:
                cell = cells[i]
                text = cell.copy() if isinstance(cell, Text) \
                    else Text.from_markup(str(cell))
                if spec.right:
                    text.justify = "right"
                rendered.append(text)
            table.add_row(*rendered, key=key)
        table.display = bool(shown)
        state = self.query_one(EmptyState)
        state.display = not shown
        if not shown:
            if self._rows:  # rows exist — the filter hid them all
                state.set_content("Nothing matches the filter.",
                                  "Esc clears it.")
            else:
                state.set_content(*self._empty)
        if preserve is not None and shown:
            for idx, (key, _) in enumerate(shown):
                if key == preserve:
                    table.move_cursor(row=idx, animate=False)
                    break
        self.query_one(f"#{self._table_id}-detail", Static).display = self._is_wide()
        self._update_detail()

    # --- detail ----------------------------------------------------------------

    def _detail_lines(self) -> list[str]:
        key = self.cursor_key()
        row = next((cells for k, cells in self._rows if k == key), None)
        if row is None:
            return ["[dim]no selection[/]"]
        return [f"[b]{spec.label}:[/] {_cell_markup(row[i])}"
                for i, spec in enumerate(self._columns) if _plain(row[i]).strip()]

    def _update_detail(self) -> None:
        self.query_one(f"#{self._table_id}-detail", Static).update(
            "\n".join(self._detail_lines()))

    @on(DataTable.RowHighlighted)
    def _on_highlight(self, event: DataTable.RowHighlighted) -> None:
        self._update_detail()

    @on(DataTable.RowSelected)
    def _on_selected(self, event: DataTable.RowSelected) -> None:
        # Compact folds columns away — Enter/click surfaces the full row.
        if self._compact and any(c.fold for c in self._columns):
            self.app.push_screen(DetailOverlay(self._detail_title,
                                               self._detail_lines()))

    # --- filtering ---------------------------------------------------------------

    def action_open_filter(self) -> None:
        self.query_one(Input).focus()

    @on(Input.Changed)
    def _on_filter_changed(self, event: Input.Changed) -> None:
        self._filter = event.value.strip()
        self._rebuild()

    @on(Input.Submitted)
    def _on_filter_submitted(self, event: Input.Submitted) -> None:
        self.query_one(DataTable).focus()

    def on_key(self, event: object) -> None:
        # Esc in the filter clears it and hands focus back to the table,
        # without bubbling on to the screen's own Esc (usually "back").
        if getattr(event, "key", None) != "escape":
            return
        field = self.query_one(Input)
        if self.app.focused is field:
            if field.value:
                field.value = ""  # Input.Changed refilters
            self.query_one(DataTable).focus()
            event.stop()  # type: ignore[attr-defined]

    # --- sorting -----------------------------------------------------------------

    def _set_sort(self, index: int | None, desc: bool = False) -> None:
        self._sort_index, self._sort_desc = index, desc
        self._rebuild()

    @on(DataTable.HeaderSelected)
    def _on_header(self, event: DataTable.HeaderSelected) -> None:
        index = int(event.column_key.value or 0)
        if not self._columns[index].sortable:
            return
        if self._sort_index == index:
            self._set_sort(index if not self._sort_desc else None,
                           desc=not self._sort_desc)
        else:
            self._set_sort(index)

    def action_cycle_sort(self) -> None:
        """Keyboard sort: unsorted → col₁▲ → col₁▼ → col₂▲ → … → unsorted."""
        order = [i for i, c in enumerate(self._columns) if c.sortable]
        if not order:
            return
        if self._sort_index is None:
            self._set_sort(order[0])
        elif not self._sort_desc:
            self._set_sort(self._sort_index, desc=True)
        else:
            at = order.index(self._sort_index)
            self._set_sort(order[at + 1] if at + 1 < len(order) else None)
