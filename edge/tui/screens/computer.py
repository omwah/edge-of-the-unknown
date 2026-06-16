"""ComputerScreen — the ship computer (UI_MOCKUPS.md §9).

Phase-1 core screen: a tabbed query console over the owned game engine. The
**Trade** tab is the pair-trade finder; the **Map** and **Log** tabs fold in the
galactic map and the durable event log (WP-B — they live *inside* the computer
but keep their direct `M`/`G` hotkeys on the game screen). Ports, Route, Codex,
Dossier, and Notes grow through Phase 2.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static, TabbedContent, TabPane

from edge.server.service import GameService
from edge.tui.widgets import MapBandPanel, MapView


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
    ComputerScreen DataTable { height: auto; max-height: 14; margin-top: 1; }
    ComputerScreen .note { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, service: GameService, player_id: int, *, initial_tab: str = "trade") -> None:
        super().__init__()
        self._computer = service.computer_view(player_id)
        self._map = service.map_view(player_id)
        self._messages = service.messages_view(player_id)
        self._initial_tab = initial_tab

    def compose(self) -> ComposeResult:
        yield Static("SHIP COMPUTER", id="computer-title")
        with TabbedContent(initial=self._initial_tab):
            with TabPane("Map", id="map"):
                yield Static(
                    f"[b]GALACTIC MAP[/]   [dim]you @ Sector {self._map.you_sector} · "
                    f"Band {self._map.you_band}[/]"
                )
                yield MapView(self._map)
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
            with TabPane("Log", id="log"):
                yield Static("[b]EVENT LOG[/]        [dim]newest first[/]")
                yield DataTable(id="log-table", zebra_stripes=True, cursor_type="row")
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
        finder = self.query_one("#finder", DataTable)
        finder.add_columns("Pair", "Goods", "Dist", "Profit/rt", "Per-turn")
        for p in self._computer.pairs:
            finder.add_row(p.pair, p.goods, str(p.dist), str(p.profit_rt), f"{p.per_turn} ▾")

        log = self.query_one("#log-table", DataTable)
        log.add_columns("When", "Event")
        if self._messages.events:
            for entry in self._messages.events:
                log.add_row(Text(entry.when, style="dim"), Text.from_markup(entry.text))
        else:
            log.add_row(Text(""), Text("no events yet", style="dim"))

    def on_map_band_panel_picked(self, msg: MapBandPanel.Picked) -> None:
        self.notify(f"{msg.title} — sector inspector not wired in the skeleton.", timeout=2)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
