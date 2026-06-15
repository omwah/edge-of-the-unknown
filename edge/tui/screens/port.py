"""PortScreen — a plain commodities port (UI_MOCKUPS.md §2).

Used only when the sector's port is *not* a StarDock; a StarDock hosts the same
trade UI as its **Commodities** tab instead (see `StarDockScreen`). Both reuse
the `TradePanel` widget so the trade experience is identical either way.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from edge.tui.dummy import PortDTO
from edge.tui.widgets import TradePanel


class PortScreen(Screen):
    BINDINGS = [
        Binding("escape", "leave", "Leave dock"),
        Binding("q", "leave", "Leave dock"),
    ]

    def __init__(self, port: PortDTO) -> None:
        super().__init__()
        self._port = port

    def compose(self) -> ComposeResult:
        yield TradePanel(self._port, id="port-body")

    def action_leave(self) -> None:
        self.app.pop_screen()
