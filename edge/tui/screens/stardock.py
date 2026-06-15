"""StarDockScreen — services hub (UI_MOCKUPS.md §5).

Phase-1 shell: the tabs exist; only Commodities and Hardware are populated.
Trading lives in the **Commodities** tab (the default), which reuses the same
`TradePanel` as the standalone `PortScreen` — so docking at a StarDock reaches
the trade UI through a tab rather than a separate screen. The component list
mirrors the §5 wireframe and the §8 economy constants.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static, TabbedContent, TabPane

from edge.tui.dummy import PortDTO
from edge.tui.widgets import TradePanel


class StarDockScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Undock"),
        Binding("e", "noop", "Engine room"),
        Binding("r", "noop", "Repair"),
    ]

    CSS = """
    StarDockScreen #dock-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    StarDockScreen TabPane { padding: 1 2; }
    StarDockScreen DataTable { height: auto; max-height: 10; margin-top: 1; }
    StarDockScreen .note { color: $text-muted; margin-top: 1; }
    """

    _COMPONENTS = [
        ("accelerator", "I", "2,000", "[Install]"),
        ("converter", "I", "2,000", "[Install]"),
        ("turbine", "II", "8,000*", "[Barter]"),
        ("navigator (keystone)", "I", "2,000", "[Install]"),
    ]

    def __init__(self, location: str, port: PortDTO) -> None:
        super().__init__()
        self._location = location
        self._port = port

    def compose(self) -> ComposeResult:
        yield Static(f"STARDOCK · {self._location}", id="dock-title")
        with TabbedContent(initial="trade"):
            with TabPane("Commodities", id="trade"):
                yield TradePanel(self._port, show_title=False)
            with TabPane("Shipyard", id="shipyard"):
                yield Static("[dim]Hull sales — not wired in the skeleton.[/]")
            with TabPane("Hardware", id="hardware"):
                yield Static(
                    "[b]HARDWARE EMPORIUM[/]        Latinum [b yellow]14,250[/] gpl"
                )
                yield DataTable(id="hardware-table", cursor_type="row")
                yield Static(
                    "[dim]* Tier II = latinum + artifact barter[/]", classes="note"
                )
            with TabPane("Bank", id="bank"):
                yield Static("[dim]Deposit / withdraw / interest — Phase 2.[/]")
            with TabPane("Tavern", id="tavern"):
                yield Static("[dim]Rumors & contracts — Phase 5.[/]")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#hardware-table", DataTable)
        table.add_columns("Component", "Tier", "Price", "Action")
        for row in self._COMPONENTS:
            table.add_row(*row)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
