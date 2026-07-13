"""WP-UI21 — standardized Computer tables: filtering, sorting, folding, detail.

`DetailTable` must filter and sort purely presentationally (stable row keys,
source data untouched), fold low-priority columns at the compact tier with a
row-detail overlay, show a persistent detail pane at the wide tier, and keep
the cursor on the same logical row across refreshes and reorderings. Actions
on the ComputerScreen must target the row the player sees, not a raw index.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Input

from edge.tui.chrome import EmptyState
from edge.tui.detail_table import ColumnSpec, DetailOverlay, DetailTable

_ROWS = [
    ("a", ("alpha", "3", "x-alpha")),
    ("b", ("beta", "1", "x-beta")),
    ("c", ("gamma", "2", "x-gamma")),
]


class _TableApp(App):
    def compose(self) -> ComposeResult:
        yield DetailTable("t-table", (
            ColumnSpec("Name", sortable=True),
            ColumnSpec("Qty", sortable=True, right=True),
            ColumnSpec("Extra", fold=True),
        ), empty=("Nothing here.", "a hint"), detail_title="Row")


def _first_key(table: DataTable) -> str | None:
    return table.coordinate_to_cell_key((0, 0)).row_key.value


async def test_filter_narrows_display_without_touching_source() -> None:
    app = _TableApp()
    async with app.run_test(size=(100, 34)) as pilot:
        dt = app.query_one(DetailTable)
        source = list(_ROWS)
        dt.set_rows(source)
        await pilot.pause()
        table = app.query_one(DataTable)
        assert table.row_count == 3
        app.query_one(Input).value = "bet"
        await pilot.pause()
        assert table.row_count == 1
        assert _first_key(table) == "b"
        assert source == _ROWS  # presentation only — the source list is untouched
        # Esc in the filter clears it and restores every row.
        app.query_one(Input).focus()
        await pilot.press("escape")
        await pilot.pause()
        assert table.row_count == 3


async def test_filter_to_nothing_shows_no_match_empty_state() -> None:
    app = _TableApp()
    async with app.run_test(size=(100, 34)) as pilot:
        dt = app.query_one(DetailTable)
        dt.set_rows(list(_ROWS))
        await pilot.pause()
        app.query_one(Input).value = "zzz"
        await pilot.pause()
        table = app.query_one(DataTable)
        assert not table.display
        state = app.query_one(EmptyState)
        assert state.display
        assert "matches" in str(state.render())


async def test_sort_cycles_and_preserves_cursor_by_key() -> None:
    app = _TableApp()
    async with app.run_test(size=(100, 34)) as pilot:
        dt = app.query_one(DetailTable)
        dt.set_rows(list(_ROWS))
        await pilot.pause()
        table = app.query_one(DataTable)
        table.focus()
        table.move_cursor(row=1, animate=False)  # key "b"
        await pilot.press("o")  # Name ascending (alpha, beta, gamma)
        await pilot.pause()
        assert _first_key(table) == "a"
        assert dt.cursor_key() == "b"  # cursor follows the logical row
        await pilot.press("o")  # Name descending
        await pilot.pause()
        assert _first_key(table) == "c"
        assert dt.cursor_key() == "b"
        await pilot.press("o")  # next column: Qty ascending (numeric-aware)
        await pilot.pause()
        assert _first_key(table) == "b"  # qty 1 first
        await pilot.press("o", "o")  # Qty descending → unsorted again
        await pilot.pause()
        assert _first_key(table) == "a"  # original DTO order restored


async def test_compact_folds_columns_and_enter_opens_detail_overlay() -> None:
    app = _TableApp()
    async with app.run_test(size=(100, 34)) as pilot:
        dt = app.query_one(DetailTable)
        app.screen.add_class("compact")
        dt.set_rows(list(_ROWS))
        dt._check_tier()
        await pilot.pause()
        table = app.query_one(DataTable)
        assert len(table.columns) == 2  # "Extra" folded away
        table.focus()
        table.move_cursor(row=2, animate=False)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DetailOverlay)
        body = " ".join(str(s.render()) for s in app.screen.query("Static"))
        assert "x-gamma" in body  # the folded column surfaces in the detail
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, DetailOverlay)


async def test_wide_tier_shows_persistent_detail_pane() -> None:
    app = _TableApp()
    async with app.run_test(size=(126, 44)) as pilot:
        dt = app.query_one(DetailTable)
        app.screen.add_class("wide")
        dt.set_rows(list(_ROWS))
        await pilot.pause()
        pane = app.query_one("#t-table-detail")
        assert pane.display
        table = app.query_one(DataTable)
        table.focus()
        table.move_cursor(row=1, animate=False)
        await pilot.pause()
        assert "x-beta" in str(pane.render())  # follows the highlighted row


async def test_refresh_preserves_cursor_by_logical_key() -> None:
    app = _TableApp()
    async with app.run_test(size=(100, 34)) as pilot:
        dt = app.query_one(DetailTable)
        dt.set_rows(list(_ROWS))
        await pilot.pause()
        table = app.query_one(DataTable)
        table.move_cursor(row=2, animate=False)  # key "c"
        # A refresh arrives reordered with changed cells (a market tick).
        dt.set_rows([
            ("c", ("gamma", "9", "x-gamma")),
            ("a", ("alpha", "4", "x-alpha")),
            ("b", ("beta", "1", "x-beta")),
        ])
        await pilot.pause()
        assert dt.cursor_key() == "c"  # same logical row, new position


async def test_note_removal_targets_the_filtered_row() -> None:
    """ComputerScreen actions resolve rows by key: filtering the notes table
    down to one note and pressing Del removes that note, not index zero."""
    from edge.core.rules import AddNote
    from edge.tui.app import EdgeApp
    from edge.tui.screens.computer import ComputerScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        for text in ("alpha note", "beta note", "gamma note"):
            svc.apply(1, AddNote(text=text))
        await pilot.press("c")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ComputerScreen)
        screen.show_subview("notes")
        await pilot.pause()
        screen.query_one("#notes-table-filter", Input).value = "beta"
        await pilot.pause()
        table = screen.query_one("#notes-table", DataTable)
        assert table.row_count == 1
        table.focus()
        await pilot.press("delete")  # remove highlighted note
        await pilot.pause()
        notes = svc.computer_view(1).notes
        assert notes == ["alpha note", "gamma note"]  # beta gone, others intact
