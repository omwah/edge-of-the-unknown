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

from edge.core.dto import RouteDTO
from edge.core.economy import EconomyError
from edge.core.movement import MovementError
from edge.core.rules import TravelTo
from edge.server.service import GameService
from edge.tui.screens.confirm import ConfirmScreen
from edge.tui.screens.travel import TravelPromptScreen
from edge.tui.widgets import MapBandPanel, MapView, bar


class ComputerScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("c", "back", "Back"),
        Binding("p", "plot_route", "Plot route"),
        Binding("g", "engage", "Engage"),
        Binding("r", "route_prompt", "Route to…"),
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
        self._service = service
        self._pid = player_id
        self._computer = service.computer_view(player_id)
        self._map = service.map_view(player_id)
        self._messages = service.messages_view(player_id)
        self._initial_tab = initial_tab
        self._route: RouteDTO | None = None  # the plotted route (per-interaction)
        self._engage_target: int | None = None  # internal sector [G] travels to

    def compose(self) -> ComposeResult:
        yield Static("SHIP COMPUTER", id="computer-title")
        with TabbedContent(initial=self._initial_tab):
            with TabPane("Map", id="map"):
                yield Static(
                    f"[b]GALACTIC MAP[/]   [dim]you @ Sector {self._map.you_display} · "
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
                yield Static("[b]ROUTE PLANNER[/]        [dim]plot before you commit[/]")
                yield DataTable(id="route-table", zebra_stripes=True, cursor_type="row")
                yield Static("", id="route-summary", classes="note")
            with TabPane("Codex", id="codex"):
                yield Static("[b]DISCOVERY CODEX[/]        [dim]logged finds, richest first[/]")
                yield DataTable(id="codex-table", zebra_stripes=True, cursor_type="row")
            with TabPane("Dossier", id="dossier"):
                yield Static("[b]ALIEN DOSSIER[/]        [dim]species you have met[/]")
                yield DataTable(id="dossier-table", zebra_stripes=True, cursor_type="row")
                yield Static(self._dossier_notes(), classes="note")
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

        codex = self.query_one("#codex-table", DataTable)
        codex.add_columns("Find", "Location", "Rarity", "Detail")
        if self._computer.codex:
            for c in self._computer.codex:
                codex.add_row(c.name, c.location, c.rarity, c.detail)
        else:
            codex.add_row(Text("no discoveries logged yet", style="dim"), Text(""), Text(""), Text(""))

        route = self.query_one("#route-table", DataTable)
        route.add_columns("Hop", "Sector", "Notes")
        self._render_route()

        dossier = self.query_one("#dossier-table", DataTable)
        dossier.add_columns("Species", "Alliance", "Standing", "Last seen", "Disp", "Tech offers")
        if self._computer.dossier:
            for d in self._computer.dossier:
                dossier.add_row(d.species, d.alliance, d.standing, f"S{d.last_seen}",
                                bar(d.disposition_filled, 5), d.offers)
        else:
            dossier.add_row(*(Text("no species met yet", style="dim"), *(Text(""),) * 5))

    def _dossier_notes(self) -> str:
        if not self._computer.dossier:
            return "[dim]Hail a friendly species to begin a dossier.[/]"
        return "\n".join(f"[cyan]{d.species}:[/] [dim]{d.note}[/]" for d in self._computer.dossier)

    def on_map_band_panel_picked(self, msg: MapBandPanel.Picked) -> None:
        self.notify(f"{msg.title} — sector inspector not wired in the skeleton.", timeout=2)

    # --- Route planner (WP14) ------------------------------------------------

    def _render_route(self) -> None:
        """Repaint the Route tab from the plotted `RouteDTO` (or the empty state)."""
        table = self.query_one("#route-table", DataTable)
        table.clear()
        summary = self.query_one("#route-summary", Static)
        dto = self._route
        if dto is None:
            summary.update(
                "[dim]Plot a route from the Trade or Codex tab, "
                "or press R to enter a destination.[/]"
            )
            return
        for i, hop in enumerate(dto.hops, 1):
            note = Text("one-way ⚠", style="yellow") if hop.one_way else Text("")
            table.add_row(str(i), hop.label, note)
        head = f"[b]{dto.origin_display} → {dto.dest_display}[/]   [dim]{dto.summary}[/]"
        if dto.reachable and dto.affordable:
            summary.update(f"{head}   ·   [green]G Engage[/]")
        else:
            summary.update(f"{head}   ·   [red]{dto.reason}[/]")

    def _show_route(self) -> None:
        self._render_route()
        self.query_one(TabbedContent).active = "route"

    def _cursor_entry(self, table_id: str, items: list) -> object | None:  # type: ignore[type-arg]
        """The DTO under the highlighted row of `table_id`, or None."""
        row = self.query_one(table_id, DataTable).cursor_row
        if not items or row is None or row >= len(items):
            return None
        return items[row]

    def _current_sector(self) -> int:
        state = self._service.state
        player = state.players[self._pid]
        return state.ships[player.ship_id].sector_id

    def action_plot_route(self) -> None:
        active = self.query_one(TabbedContent).active
        if active == "trade":
            pair = self._cursor_entry("#finder", self._computer.pairs)
            if pair is None:
                self.notify("No trade pair selected.", timeout=2)
                return
            self._route = self._service.route_legs_view(
                self._pid, [pair.buy_sector, pair.sell_sector])  # type: ignore[attr-defined]
            # [G] engages the first leg (§ WP14); skip a leg already standing on.
            here = self._current_sector()
            self._engage_target = next(
                (w for w in (pair.buy_sector, pair.sell_sector) if w != here), None)  # type: ignore[attr-defined]
            self._show_route()
        elif active == "codex":
            entry = self._cursor_entry("#codex-table", self._computer.codex)
            if entry is None or entry.sector_id < 0:  # type: ignore[attr-defined]
                self.notify("No charted find selected.", timeout=2)
                return
            self._route = self._service.route_view(self._pid, entry.sector_id)  # type: ignore[attr-defined]
            self._engage_target = entry.sector_id  # type: ignore[attr-defined]
            self._show_route()
        else:
            self.notify("Plot a route from the Trade or Codex tab.", timeout=2)

    def action_route_prompt(self) -> None:
        self.app.push_screen(TravelPromptScreen(), self._after_route_prompt)

    def _after_route_prompt(self, dest: int | None) -> None:
        if dest is None:
            return
        internal = self._service.resolve_display_id(dest)  # player typed a spatial id (§5.1)
        if internal is None:
            self.notify(f"No sector {dest}.", severity="warning", timeout=3)
            return
        self._route = self._service.route_view(self._pid, internal)
        self._engage_target = internal
        self._show_route()

    def action_engage(self) -> None:
        dto = self._route
        if dto is None:
            self.notify("No route plotted.", timeout=2)
            return
        if not dto.reachable or not dto.affordable:
            self.notify(dto.reason or "Cannot travel that route.", severity="warning", timeout=3)
            return
        if dto.hazards:  # Phase-3 seam: empty in Phase 2, so the confirm never appears yet
            self.app.push_screen(
                ConfirmScreen("Hazards on route:\n" + "\n".join(dto.hazards) + "\n\nProceed?"),
                self._engage_confirmed,
            )
            return
        self._engage_confirmed(True)

    def _engage_confirmed(self, ok: bool | None) -> None:
        if not ok or self._engage_target is None:
            return
        try:
            self._service.apply(self._pid, TravelTo(to_sector=self._engage_target))
        except (MovementError, EconomyError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.app.pop_screen()  # back to the game screen, which recomposes on resume

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
