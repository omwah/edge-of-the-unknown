"""ComputerScreen — the ship computer (UI_MOCKUPS.md §9).

Phase-1 core screen: a tabbed query console over the owned game engine. The
**Trade** tab is the pair-trade finder; the **Map** and **Log** tabs fold in the
galactic map and the durable event log (WP-B — they live *inside* the computer
but keep their direct `M`/`G` hotkeys on the game screen). The **Ports** directory
(WP15) and **Route** planner (WP14) are live; **Codex** and **Dossier** ship in
WP11; **Notes** is the last Phase-2 stub.
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
from edge.tui.widgets import LocalMapView, bar, preserve_cursor


class ComputerScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("c", "back", "Back"),
        Binding("p", "plot_route", "Plot route"),
        Binding("g", "engage", "Engage"),
        Binding("r", "route_prompt", "Route to…"),
        Binding("s", "seize_core", "Seize Core"),
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
        self._market = service.market_view(player_id)
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
                    f"[b]LOCAL MAP[/]   [dim]you @ Sector {self._map.you_display} · "
                    f"Band {self._map.you_band}   ·   ↑↓←→ select · ↵ plot route[/]",
                    id="map-header",
                )
                yield LocalMapView(self._map, rebake=self._map_for_width, id="local-map")
            with TabPane("Ports", id="ports"):
                yield Static("[b]PORTS DIRECTORY[/]        [dim]charted ports, nearest first[/]")
                yield DataTable(id="ports-table", zebra_stripes=True, cursor_type="row")
                yield Static("[dim][b]P[/] Plot route to highlighted[/]", classes="note")
            with TabPane("Planets", id="planets"):
                yield Static("[b]PLANETS DIRECTORY[/]        [dim]charted planets, nearest first[/]")
                yield DataTable(id="planets-table", zebra_stripes=True, cursor_type="row")
                yield Static("[dim][b]P[/] Plot route to highlighted[/]", classes="note")
            with TabPane("Trade", id="trade"):
                yield Static("[b]PAIR-TRADE FINDER[/]        [dim]scored by profit / turn[/]")
                yield DataTable(id="finder", zebra_stripes=True, cursor_type="row")
                yield Static(
                    f"selected: [cyan]{self._computer.selected}[/]   ·   "
                    "[b]P[/] Plot route   [b]A[/] Add note",
                    classes="note",
                )
            with TabPane("Market", id="market"):
                yield Static(f"[b]ORDER BOOK[/]        [dim]{self._market.summary}[/]")
                yield DataTable(id="market-table", zebra_stripes=True, cursor_type="row")
                yield Static(self._market_note(), classes="note")
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
            with TabPane("Leads", id="leads"):
                yield Static("[b]COORDINATE LEADS[/]        [dim]tips logged from contacts[/]")
                yield DataTable(id="leads-table", zebra_stripes=True, cursor_type="row")
                yield Static("[dim][b]P[/] Plot route to highlighted[/]", classes="note")
            with TabPane("Contracts", id="contracts"):
                yield Static("[b]FAVORS[/]        [dim]jobs accepted from aliens[/]")
                yield DataTable(id="contracts-table", zebra_stripes=True, cursor_type="row")
            with TabPane("Dossier", id="dossier"):
                yield Static("[b]ALIEN DOSSIER[/]        [dim]species you have met[/]")
                yield DataTable(id="dossier-table", zebra_stripes=True, cursor_type="row")
                yield Static(self._dossier_notes(), classes="note")
                yield Static(self._governance_notes(), id="governance-panel", classes="note")
                yield Static(self._seizure_notes(), id="seizure-panel", classes="note")
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

        leads = self.query_one("#leads-table", DataTable)
        leads.add_columns("Tip", "From", "Location", "Dist", "Turns")
        if self._computer.leads:
            for ld in self._computer.leads:
                # Off-origin + uncharted: point the player back to where the tip was obtained.
                turns = (str(ld.turn_cost) if ld.reachable
                         else f"plot from S{ld.origin_coords}" if not ld.at_origin
                         else "unreachable")
                # A roaming-Entity lead whose quarry has moved on reads as a cold trail (§7).
                summary = (Text.assemble(ld.summary, ("  · trail gone cold", "italic yellow"))
                           if ld.stale else ld.summary)
                leads.add_row(summary, ld.source, f"S{ld.coords}",
                              str(ld.distance) if ld.reachable else "—", turns)
        else:
            leads.add_row(
                Text("No leads yet — ask a friendly species for coordinates.", style="dim"),
                *(Text(""),) * 4)

        jobs = self.query_one("#contracts-table", DataTable)
        jobs.add_columns("#", "Kind", "From", "Task", "Reward", "Due")
        if self._computer.contracts:
            for c in self._computer.contracts:
                jobs.add_row(str(c.contract_id), c.kind, c.issuer, c.summary,
                             f"{c.reward:,}", f"day {c.deadline_day}")
        else:
            jobs.add_row(
                Text("No favors accepted — ask a friendly species for work.", style="dim"),
                *(Text(""),) * 5)

        ports = self.query_one("#ports-table", DataTable)
        ports.add_columns("Sector", "Port", "Class", "Buys", "Sells", "Dist")
        if self._computer.ports:
            for e in self._computer.ports:
                ports.add_row(f"S{e.sector_display}", e.name, e.klass, e.buys, e.sells,
                              str(e.dist) if e.dist >= 0 else "—")
        else:
            ports.add_row(
                Text("No ports discovered yet — explore to chart them.", style="dim"),
                *(Text(""),) * 5)

        planets = self.query_one("#planets-table", DataTable)
        planets.add_columns("Sector", "Planet", "Type", "Claim", "Pop", "Species", "Stores (F/O/E)", "Dist")
        if self._computer.planets:
            for pl in self._computer.planets:
                planets.add_row(
                    f"S{pl.sector_display}", pl.name, pl.ptype, pl.owner,
                    f"{pl.colonists:,}", pl.species, pl.stores,
                    str(pl.dist) if pl.dist >= 0 else "—")
        else:
            planets.add_row(
                Text("No planets discovered yet — explore to chart them.", style="dim"),
                *(Text(""),) * 7)

        market = self.query_one("#market-table", DataTable)
        market.add_columns("Sector", "Port", "Commodity", "Side", "Qty", "Limit")
        if not self._market.enabled:
            market.add_row(Text("The order-book market is disabled.", style="dim"),
                           *(Text(""),) * 5)
        elif self._market.orders:
            for o in self._market.orders:
                market.add_row(f"S{o.sector_display}", o.port_name, o.commodity,
                               o.side, str(o.qty), str(o.limit))
        else:
            market.add_row(
                Text("No open orders at charted ports — dock somewhere to read its book.",
                     style="dim"),
                *(Text(""),) * 5)

        route = self.query_one("#route-table", DataTable)
        route.add_columns("Hop", "Sector", "Notes")
        self._render_route()

        dossier = self.query_one("#dossier-table", DataTable)
        dossier.add_columns("Species", "Alliance", "Standing", "Last seen", "Disp", "Tech offers")
        if self._computer.dossier:
            for d in self._computer.dossier:
                # Show a bloc member's role (leader / aspirant) so an intrigue coup is legible (WP51).
                alliance = f"{d.alliance} · {d.role}" if d.role not in ("none", "member") else d.alliance
                dossier.add_row(d.species, alliance, d.standing, f"S{d.last_seen}",
                                bar(d.disposition_filled, 5), d.offers)
        else:
            dossier.add_row(*(Text("no species met yet", style="dim"), *(Text(""),) * 5))

    def _dossier_notes(self) -> str:
        if not self._computer.dossier:
            return "[dim]Hail a friendly species to begin a dossier.[/]"
        return "\n".join(f"[cyan]{d.species}:[/] [dim]{d.note}[/]" for d in self._computer.dossier)

    def _governance_notes(self) -> str:
        """Standing Core-governance intel (§6.3, WP52) — governor, status, coveters."""
        intel = self._computer.governance_intel
        if not intel:
            return ""
        body = "\n".join(f"[dim]{line}[/]" for line in intel)
        return f"[b]CORE GOVERNANCE[/]\n{body}"

    def _seizure_notes(self) -> str:
        """The Core-seizure checklist for a championed covets_core bloc (§6.3, WP50)."""
        sz = self._computer.seizure
        if sz is None:
            return ""
        if sz.already_governs:
            return f"[green]⚑ {sz.alliance_name} governs the Core.[/]"

        def check(done: bool) -> str:
            return "[green]✔[/]" if done else "[red]✗[/]"

        tasks = ", ".join(sz.tasks_needed) or "—"
        lines = [
            f"[b]SEIZE THE CORE — {sz.alliance_name}[/]",
            f"  {check(sz.tasks_met)} tasks: {', '.join(sz.tasks_done) or 'none'} of {tasks}",
            f"  {check(sz.bases_met)} razed {sz.bases_razed}/{sz.bases_needed} Core bases",
            f"  {check(sz.fee_affordable)} fee: {sz.fee:,} slips",
        ]
        if sz.ready:
            lines.append("  [b][green]S[/] Petition to seize the Core[/]")
        return "\n".join(lines)

    def action_seize_core(self) -> None:
        """Petition to flip the Core to the championed bloc (§6.3, WP50)."""
        sz = self._computer.seizure
        if sz is None or not sz.ready:
            self.notify("No Core seizure is ready to petition.", severity="warning", timeout=3)
            return
        from edge.core.rules import PetitionCoreSeizure
        try:
            self._service.apply(self._pid, PetitionCoreSeizure(alliance_id=sz.alliance_id))
        except (EconomyError, MovementError) as exc:
            self.notify(str(exc), severity="warning", timeout=4)
            return
        self.notify(f"The Core is seized — {sz.alliance_name} now governs.", timeout=5)
        self._computer = self._service.computer_view(self._pid)
        self.query_one("#seizure-panel", Static).update(self._seizure_notes())

    def _market_note(self) -> str:
        if not self._market.enabled:
            return "[dim]The legacy port economy is running — no order book to show.[/]"
        if not self._market.purses:
            return "[dim]Purses shown as of your last visit — dock to refresh a port's book.[/]"
        purses = "   ".join(f"S{d} {name} [cyan]{purse:,}[/]"
                            for d, name, purse in self._market.purses[:6])
        return f"[dim]Purses (as of last dock):[/]  {purses}"

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        # Remember the tab across screens so [C] reopens where the player left off.
        active = self.query_one(TabbedContent).active
        self.app.computer_tab = active
        if active == "map":
            # The Map pane only has a real width once it is shown — fit + focus it now
            # so the arrow keys drive the sector cursor immediately.
            view = self.query_one("#local-map", LocalMapView)
            view._refit()
            self.call_after_refresh(view.focus)

    def _map_for_width(self, width: int) -> object:
        """Bake the local map to fit `width`, overlaying the active route (§6.7/§11).

        full_graph=True is safe for any target: map_view only opens the full graph for a
        destination the player actually holds a lead for (and at its origin).
        """
        return self._service.map_view(
            self._pid, route_dest=self._engage_target, full_graph=True, fit_width=width)

    def _refresh_map(self) -> None:
        """Re-bake the local map (fit to width) with the active route overlaid (§6.7/§11)."""
        self.query_one("#local-map", LocalMapView)._refit()

    def on_local_map_view_picked(self, msg: LocalMapView.Picked) -> None:
        """Clicking a sector on the Map plots a route to it (and shows the Route tab)."""
        self._route = self._service.route_view(self._pid, msg.sector_id)
        self._engage_target = msg.sector_id
        self._show_route()

    # --- Route planner (WP14) ------------------------------------------------

    def _render_route(self) -> None:
        """Repaint the Route tab from the plotted `RouteDTO` (or the empty state)."""
        table = self.query_one("#route-table", DataTable)
        summary = self.query_one("#route-summary", Static)
        dto = self._route
        with preserve_cursor(table):
            table.clear()
            if dto is not None:
                for i, hop in enumerate(dto.hops, 1):
                    note = Text("one-way ⚠", style="yellow") if hop.one_way else Text("")
                    table.add_row(str(i), hop.label, note)
        if dto is None:
            summary.update(
                "[dim]Plot a route from the Trade or Codex tab, "
                "or press R to enter a destination.[/]"
            )
            return
        head = f"[b]{dto.origin_display} → {dto.dest_display}[/]   [dim]{dto.summary}[/]"
        if dto.reachable and dto.affordable:
            summary.update(f"{head}   ·   [green]G Engage[/]")
        else:
            summary.update(f"{head}   ·   [red]{dto.reason}[/]")

    def _show_route(self) -> None:
        self._render_route()
        self._refresh_map()  # overlay the plotted course on the Map tab too
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
        elif active == "ports":
            entry = self._cursor_entry("#ports-table", self._computer.ports)
            if entry is None:
                self.notify("No port selected.", timeout=2)
                return
            self._route = self._service.route_view(self._pid, entry.sector_id)  # type: ignore[attr-defined]
            self._engage_target = entry.sector_id  # type: ignore[attr-defined]
            self._show_route()
        elif active == "planets":
            entry = self._cursor_entry("#planets-table", self._computer.planets)
            if entry is None:
                self.notify("No planet selected.", timeout=2)
                return
            self._route = self._service.route_view(self._pid, entry.sector_id)  # type: ignore[attr-defined]
            self._engage_target = entry.sector_id  # type: ignore[attr-defined]
            self._show_route()
        elif active == "leads":
            entry = self._cursor_entry("#leads-table", self._computer.leads)
            if entry is None or entry.sector_id < 0:  # type: ignore[attr-defined]
                self.notify("No lead selected.", timeout=2)
                return
            # A lead points somewhere unvisited — plot over the full graph (the tip is the map).
            self._route = self._service.route_view(
                self._pid, entry.sector_id, full_graph=True)  # type: ignore[attr-defined]
            self._engage_target = entry.sector_id  # type: ignore[attr-defined]
            self._show_route()
        else:
            self.notify("Plot a route from the Trade, Codex, Leads, Ports or Planets tab.", timeout=2)

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
