"""ComputerScreen — the ship computer (UI_MOCKUPS.md §9).

Phase-1 core screen: a tabbed query console over the owned game engine. Only the
**Trade** tab (the pair-trade finder) is populated in the skeleton; Map, Ports,
Route, Codex, Dossier, and Notes are stubbed tabs that grow through Phase 2. The
finder scores opposed-class port pairs by round-trip profit per turn (DESIGN §8).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static, TabbedContent, TabPane

from edge.server.service import GameService


class ComputerScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("c", "back", "Back"),
        Binding("p", "noop", "Plot route"),
        Binding("a", "noop", "Add note"),
    ]

    CSS = """
    ComputerScreen #computer-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    ComputerScreen TabPane { padding: 1 2; }
    ComputerScreen DataTable { height: auto; max-height: 12; margin-top: 1; }
    ComputerScreen .note { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, service: GameService, player_id: int) -> None:
        super().__init__()
        self._computer = service.computer_view(player_id)

    def compose(self) -> ComposeResult:
        yield Static("SHIP COMPUTER", id="computer-title")
        with TabbedContent(initial="trade"):
            with TabPane("Map", id="map"):
                yield Static("[dim]Explored-universe tree — Phase 2.[/]")
            with TabPane("Ports", id="ports"):
                yield Static("[dim]Port directory (last-seen stock + class) — Phase 2.[/]")
            with TabPane("Trade", id="trade"):
                yield Static("[b]PAIR-TRADE FINDER[/]        [dim]scored by profit / turn[/]")
                yield DataTable(id="finder", zebra_stripes=True, cursor_type="row")
                yield Static(
                    f"selected: [cyan]{self._computer.selected}[/]   ·   "
                    "[b]P[/] Plot route   [b]A[/] Add note",
                    classes="note",
                )
            with TabPane("Route", id="route"):
                yield Static("[dim]Shortest path + hazard confirm — Phase 2.[/]")
            with TabPane("Codex", id="codex"):
                yield Static("[dim]Discoveries & lore — Phase 2.[/]")
            with TabPane("Dossier", id="dossier"):
                yield Static("[dim]Species standing & grudges — Phase 3.[/]")
            with TabPane("Notes", id="notes"):
                yield Static("[dim]Avoid lists & player notes — Phase 2.[/]")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#finder", DataTable)
        table.add_columns("Pair", "Goods", "Dist", "Profit/rt", "Per-turn")
        for p in self._computer.pairs:
            table.add_row(p.pair, p.goods, str(p.dist), str(p.profit_rt), f"{p.per_turn} ▾")

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
