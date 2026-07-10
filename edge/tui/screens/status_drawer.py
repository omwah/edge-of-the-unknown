"""StatusDrawerScreen — the `I` status drawer (UI_UX_OVERHAUL_PLAN.md WP-UI12).

A right-docked overlay carrying the full status readout the compact tier hides
(the sidebar's ship stats, presence, and anomalies) plus a focusable "Objects
here" list — the keyboard/list equivalent of every sector-scene click hotspot.
Picking an object dismisses the drawer with `(dest, ref)`; the GameScreen
forwards it through its one `ClickableEntry.Picked` routing. Presentation only:
it reads the fog-safe game view it was handed and issues no commands itself.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from edge.core import dto
from edge.tui.widgets import ClickableEntry, SectionRule, SectorObjectList, StatusSidebar

DrawerPick = tuple[str, int | str | None]


class StatusDrawerScreen(ModalScreen[DrawerPick | None]):
    BINDINGS = [
        Binding("i", "close", "Close", show=False),
        Binding("escape", "close", "Close"),
    ]

    DEFAULT_CSS = """
    StatusDrawerScreen { align: right middle; background: $background 40%; }
    StatusDrawerScreen #drawer-box {
        dock: right; width: 42; max-width: 100%; height: 100%;
        background: $surface; border-left: heavy $primary; padding: 0 1;
    }
    StatusDrawerScreen #drawer-title { height: 1; color: $primary; text-style: bold; }
    StatusDrawerScreen StatusSidebar { width: 1fr; height: auto; border-left: none; padding: 0; }
    """

    def __init__(self, view: dto.GameState, presence: list[str] | None = None) -> None:
        super().__init__()
        self._view = view
        self._presence = presence or []

    def compose(self) -> ComposeResult:
        view = self._view
        with VerticalScroll(id="drawer-box"):
            yield Static(f"SHIP STATUS · turns {view.turns}/{view.max_turns}"
                         "  [dim]I/Esc closes[/]", id="drawer-title")
            yield StatusSidebar(view.ship, view.sector.discoveries, width=40,
                                presence=self._presence)
            yield SectionRule("Objects here")
            yield SectorObjectList(view.sector)

    def on_mount(self) -> None:
        # Land focus on the first object row so Enter works immediately (falls
        # back to the scroll container in an empty sector).
        rows = self.query("SectorObjectList ObjectRow")
        if rows:
            rows.first().focus()

    def on_clickable_entry_picked(self, msg: ClickableEntry.Picked) -> None:
        msg.stop()
        self.dismiss((msg.dest, msg.ref))

    def action_close(self) -> None:
        self.dismiss(None)
