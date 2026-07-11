"""ComputerScreen — the ship computer (UI_MOCKUPS.md §9).

Phase-1 core screen: a tabbed query console over the owned game engine. The
**Trade** tab is the pair-trade finder; the **Map** and **Log** tabs fold in the
galactic map and the durable event log (WP-B — they live *inside* the computer
but keep their direct `M`/`G` hotkeys on the game screen). Every tab is live:
Ports/Route (WP15/WP14), Codex/Dossier (WP11), Contracts (WP57/WP71),
Alliances (WP72), and Notes — captain's notes plus the route-planner avoid
list (WP73).

WP-UI20: the thirteen-tab strip is grouped into five categories (Navigation ·
Commerce · Exploration · Relations · Records), each holding its subviews as an
inner tab row. Every category remembers its last subview (app-level, so `[C]`
reopens where the player left off); direct hotkeys, plotted routes, codex and
contract links target subviews by their unchanged pane ids via
`show_subview()`. Compact terminals swap the category tab bar for a popup
selector (the subview row stays), per the UI_MOCKUPS wireframe.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static, TabbedContent, TabPane

from edge.core.dto import AllianceRowDTO, LocalMapDTO, RouteDTO
from edge.core.economy import EconomyError
from edge.core.movement import MovementError
from edge.core.rules import TravelTo
from edge.server.service import GameService
from edge.tui.chrome import notify_warning
from edge.tui.detail_table import ColumnSpec, DetailTable
from edge.tui.screens.confirm import ConfirmScreen
from edge.tui.screens.picker import ListPicker
from edge.tui.screens.travel import TravelPromptScreen
from edge.tui.widgets import LocalMapView, bar, preserve_cursor

# WP-UI20: the five-category information architecture. Every legacy tab id maps
# to exactly one category; pane ids are unchanged so hotkeys and links keep
# addressing subviews by the same names.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "navigation": ("map", "route"),
    "commerce": ("ports", "trade", "market"),
    "exploration": ("planets", "codex", "leads"),
    "relations": ("contracts", "alliances", "dossier"),
    "records": ("log", "notes"),
}
CATEGORY_LABELS = {
    "navigation": "Navigation", "commerce": "Commerce",
    "exploration": "Exploration", "relations": "Relations", "records": "Records",
}
SUBVIEW_LABELS = {
    "map": "Map", "route": "Route", "ports": "Ports", "trade": "Trade",
    "market": "Market", "planets": "Planets", "codex": "Codex", "leads": "Leads",
    "contracts": "Contracts", "alliances": "Alliances", "dossier": "Dossier",
    "log": "Log", "notes": "Notes",
}
_CATEGORY_OF = {sub: cat for cat, subs in CATEGORIES.items() for sub in subs}


class ComputerScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("c", "back", "Back"),
        Binding("p", "plot_route", "Plot route"),
        Binding("g", "engage", "Engage"),
        Binding("r", "route_prompt", "Route to…"),
        Binding("s", "seize_core", "Seize Core"),
        Binding("a", "add_note", "Add note"),
        Binding("v", "toggle_avoid", "Avoid sector"),
        Binding("d", "deliver_contract", "Deliver"),
        Binding("x", "abandon_contract", "Abandon"),
        Binding("j", "join_alliance", "Join/Resign"),
        Binding("t", "log_admission_task", "Log task"),
    ]
    # WP-UI06: seize_core flips Core governance (destructive, always confirmed);
    # engage confirms only over known hazards; join_alliance confirms the resign
    # branch. Enforced statically by tests/test_ui_actions.py.
    ACTION_DANGER = {"seize_core": "destructive", "engage": "caution",
                     "join_alliance": "caution"}

    HELP_TITLE = "Ship's computer"
    HELP = """\
Five categories — [b]Navigation[/] (Map · Route), [b]Commerce[/] (Ports · Trade ·
Market), [b]Exploration[/] (Planets · Codex · Leads), [b]Relations[/] (Contracts ·
Alliances · Dossier), [b]Records[/] (Log · Notes) — each remembers its last
subview. Keys act on the [b]active subview[/] ([b]X[/] abandons a contract or
removes a note, per subview). [b]J[/] joins/resigns a bloc; [b]V[/] toggles
avoiding the highlighted sector on plotted routes. In any table, [b]/[/]
focuses the filter, [b]O[/] cycles the sort (or click a ↕ header); Enter on a
row opens its full detail when columns are folded at 80×24."""

    CSS = """
    ComputerScreen #computer-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    ComputerScreen TabPane { padding: 1 2; }
    /* WP-UI20: the category panes are pure containers for the subview row —
       no padding of their own, so nesting costs no content columns. */
    ComputerScreen .cat-pane { padding: 0; }
    ComputerScreen DataTable { height: auto; max-height: 14; margin-top: 1; }
    ComputerScreen .note { color: $text-muted; margin-top: 1; }
    /* WP-UI20 compact: the category tab bar yields to the popup selector. */
    ComputerScreen #cat-strip { display: none; height: auto; padding: 0 1; }
    ComputerScreen #cat-strip Button { min-width: 24; }
    ComputerScreen.compact #cat-strip { display: block; }
    ComputerScreen.compact #cats > ContentTabs { display: none; }
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

    def _inner_initial(self, category: str) -> str:
        """The subview a category opens on: the requested target if it lives here,
        else the category's remembered last subview (WP-UI20), else its first."""
        if _CATEGORY_OF.get(self._initial_tab) == category:
            return self._initial_tab
        subviews: dict[str, str] = getattr(self.app, "computer_subviews", {})
        remembered = subviews.get(category)
        if remembered in CATEGORIES[category]:
            return remembered
        return CATEGORIES[category][0]

    def compose(self) -> ComposeResult:
        yield Static("SHIP COMPUTER", id="computer-title")
        initial_cat = _CATEGORY_OF.get(self._initial_tab, "commerce")
        # Compact tier: the category tab bar is hidden and this popup selector
        # stands in for it (UI_MOCKUPS wireframe); the subview row stays.
        with Horizontal(id="cat-strip"):
            yield Button(f"Category: {CATEGORY_LABELS[initial_cat]} ▾", id="cat-button")
        with TabbedContent(initial=f"cat-{initial_cat}", id="cats"):
            with TabPane("Navigation", id="cat-navigation", classes="cat-pane"):
                with TabbedContent(initial=self._inner_initial("navigation"),
                                   id="sub-navigation"):
                    with TabPane("Map", id="map"):
                        yield Static(
                            f"[b]LOCAL MAP[/]   [dim]you @ Sector {self._map.you_display} · "
                            f"Band {self._map.you_band}   ·   ↑↓←→ select · ↵ plot route[/]",
                            id="map-header",
                        )
                        yield LocalMapView(self._map, rebake=self._map_for_width, id="local-map")
                    with TabPane("Route", id="route"):
                        yield Static("[b]ROUTE PLANNER[/]        [dim]plot before you commit[/]")
                        yield DataTable(id="route-table", zebra_stripes=True, cursor_type="row")
                        yield Static("", id="route-summary", classes="note")
            with TabPane("Commerce", id="cat-commerce", classes="cat-pane"):
                with TabbedContent(initial=self._inner_initial("commerce"), id="sub-commerce"):
                    with TabPane("Ports", id="ports"):
                        yield Static("[b]PORTS DIRECTORY[/]        [dim]charted ports, nearest first[/]")
                        yield DetailTable("ports-table", (
                            ColumnSpec("Sector", sortable=True),
                            ColumnSpec("Port", sortable=True),
                            ColumnSpec("Class"),
                            ColumnSpec("Buys", fold=True),
                            ColumnSpec("Sells", fold=True),
                            ColumnSpec("Dist", sortable=True, right=True),
                        ), empty=("No ports discovered yet.", "Explore to chart them."),
                            detail_title="Port")
                        yield Static("[dim][b]P[/] Plot route to highlighted[/]", classes="note")
                    with TabPane("Trade", id="trade"):
                        yield Static("[b]PAIR-TRADE FINDER[/]        [dim]scored by profit / turn[/]")
                        yield DetailTable("finder", (
                            ColumnSpec("Pair"),
                            ColumnSpec("Goods", fold=True),
                            ColumnSpec("Dist", sortable=True, right=True),
                            ColumnSpec("Profit/rt", sortable=True, right=True),
                            ColumnSpec("Per-turn", sortable=True, right=True),
                        ), empty=("No profitable pair charted yet.",
                                  "Chart opposed-class ports to score pairs."),
                            detail_title="Trade pair")
                        yield Static(
                            f"selected: [cyan]{self._computer.selected}[/]   ·   "
                            "[b]P[/] Plot route   [b]A[/] Add note",
                            classes="note",
                        )
                    with TabPane("Market", id="market"):
                        yield Static(f"[b]ORDER BOOK[/]        [dim]{self._market.summary}[/]")
                        yield DetailTable("market-table", (
                            ColumnSpec("Sector", sortable=True),
                            ColumnSpec("Port"),
                            ColumnSpec("Commodity", sortable=True),
                            ColumnSpec("Side"),
                            ColumnSpec("Qty", sortable=True, right=True),
                            ColumnSpec("Limit", right=True, fold=True),
                        ), empty=self._market_empty_copy(), detail_title="Order")
                        yield Static(self._market_note(), classes="note")
            with TabPane("Exploration", id="cat-exploration", classes="cat-pane"):
                with TabbedContent(initial=self._inner_initial("exploration"),
                                   id="sub-exploration"):
                    with TabPane("Planets", id="planets"):
                        yield Static("[b]PLANETS DIRECTORY[/]        [dim]charted planets, nearest first[/]")
                        yield DetailTable("planets-table", (
                            ColumnSpec("Sector", sortable=True),
                            ColumnSpec("Planet", sortable=True),
                            ColumnSpec("Type"),
                            ColumnSpec("Claim", fold=True),
                            ColumnSpec("Pop", sortable=True, right=True, fold=True),
                            ColumnSpec("Species", fold=True),
                            ColumnSpec("Stores (F/O/E)", fold=True),
                            ColumnSpec("Dist", sortable=True, right=True),
                        ), empty=("No planets discovered yet.", "Explore to chart them."),
                            detail_title="Planet")
                        yield Static("[dim][b]P[/] Plot route to highlighted[/]", classes="note")
                    with TabPane("Codex", id="codex"):
                        yield Static("[b]DISCOVERY CODEX[/]        [dim]logged finds, richest first[/]")
                        yield DetailTable("codex-table", (
                            ColumnSpec("Find", sortable=True),
                            ColumnSpec("Location"),
                            ColumnSpec("Rarity", sortable=True),
                            ColumnSpec("Detail", fold=True),
                        ), empty=("No discoveries logged yet.",
                                  "Scan and survey the frontier to fill the codex."),
                            detail_title="Discovery")
                    with TabPane("Leads", id="leads"):
                        yield Static("[b]COORDINATE LEADS[/]        [dim]tips logged from contacts[/]")
                        yield DetailTable("leads-table", (
                            ColumnSpec("Tip"),
                            ColumnSpec("From", fold=True),
                            ColumnSpec("Location"),
                            ColumnSpec("Dist", sortable=True, right=True),
                            ColumnSpec("Turns", fold=True),
                        ), empty=("No leads yet.",
                                  "Ask a friendly species for coordinates."),
                            detail_title="Lead")
                        yield Static("[dim][b]P[/] Plot route to highlighted[/]", classes="note")
            with TabPane("Relations", id="cat-relations", classes="cat-pane"):
                with TabbedContent(initial=self._inner_initial("relations"), id="sub-relations"):
                    with TabPane("Contracts", id="contracts"):
                        yield Static("[b]FAVORS[/]        [dim]jobs accepted from aliens[/]")
                        yield DetailTable("contracts-table", (
                            ColumnSpec("#"),
                            ColumnSpec("Kind", sortable=True),
                            ColumnSpec("From", fold=True),
                            ColumnSpec("Task"),
                            ColumnSpec("Reward", sortable=True, right=True),
                            ColumnSpec("Due", fold=True),
                        ), empty=("No favors accepted.",
                                  "Ask a friendly species for work — accepted "
                                  "jobs appear here."),
                            detail_title="Favor")
                        yield Static("[dim][b]D[/] Deliver highlighted (dock at its target port first)"
                                     "   ·   [b]X[/] Abandon highlighted[/]", classes="note")
                    with TabPane("Alliances", id="alliances"):
                        yield Static("[b]ALLIANCES[/]        [dim]blocs, standings, admission — join one (§6.3)[/]")
                        yield DetailTable("alliances-table", (
                            ColumnSpec("Bloc", sortable=True),
                            ColumnSpec("Standing", sortable=True, right=True),
                            ColumnSpec("Gate", fold=True),
                            ColumnSpec("Fee", right=True, fold=True),
                            ColumnSpec("Admission", fold=True),
                            ColumnSpec(""),
                        ), empty=("No blocs in this universe.", ""),
                            detail_title="Alliance")
                        yield Static("[dim][b]J[/] Join highlighted (resigns any current bloc)   ·   "
                                     "[b]T[/] Log admission task   ·   [b]J[/] on your own bloc resigns[/]",
                                     classes="note")
                    with TabPane("Dossier", id="dossier"):
                        yield Static("[b]ALIEN DOSSIER[/]        [dim]species you have met[/]")
                        yield DetailTable("dossier-table", (
                            ColumnSpec("Species", sortable=True),
                            ColumnSpec("Alliance", fold=True),
                            ColumnSpec("Standing", sortable=True),
                            ColumnSpec("Last seen", fold=True),
                            ColumnSpec("Disp"),
                            ColumnSpec("Tech offers", fold=True),
                        ), empty=("No species met yet.",
                                  "Hail a passing ship to open a dossier."),
                            detail_title="Species")
                        yield Static(self._dossier_notes(), classes="note")
                        yield Static(self._governance_notes(), id="governance-panel", classes="note")
                        yield Static(self._seizure_notes(), id="seizure-panel", classes="note")
            with TabPane("Records", id="cat-records", classes="cat-pane"):
                with TabbedContent(initial=self._inner_initial("records"), id="sub-records"):
                    with TabPane("Log", id="log"):
                        yield Static("[b]EVENT LOG[/]        [dim]newest first[/]")
                        yield DetailTable("log-table", (
                            ColumnSpec("When"),
                            ColumnSpec("Event"),
                        ), empty=("No events yet.", "Your voyage writes the log."),
                            detail_title="Event")
                    with TabPane("Notes", id="notes"):
                        yield Static("[b]CAPTAIN'S NOTES[/]        [dim]personal log + avoid list[/]")
                        yield DetailTable("notes-table", (
                            ColumnSpec("#", right=True),
                            ColumnSpec("Note"),
                        ), empty=("No notes yet.", "[b]A[/] writes one."),
                            detail_title="Note")
                        avoid = (", ".join(f"S{d}" for d in self._computer.avoid)
                                 or "[dim]none[/]")
                        yield Static(f"[b]AVOID LIST[/] (route planner skips these): {avoid}",
                                     classes="note", id="avoid-line")
                        yield Static("[dim][b]A[/] Add note   ·   [b]X[/] Remove highlighted   ·   "
                                     "[b]V[/] Toggle a sector on the avoid list[/]", classes="note")
        yield Footer()

    def _dt(self, table_id: str) -> DetailTable:
        return self.query_one(f"#{table_id}-panel", DetailTable)

    def on_mount(self) -> None:
        """Provision every subview's DetailTable (WP-UI21): rows carry stable
        keys — a DTO id where one exists, else the index into the DTO list —
        so actions resolve the highlighted row after sorting or filtering."""
        self._dt("finder").set_rows([
            (str(i), (p.pair, p.goods, str(p.dist), str(p.profit_rt), str(p.per_turn)))
            for i, p in enumerate(self._computer.pairs)])

        self._dt("log-table").set_rows([
            (str(i), (Text(entry.when, style="dim"), Text.from_markup(entry.text)))
            for i, entry in enumerate(self._messages.events)])

        self._dt("codex-table").set_rows([
            (str(i), (c.name, c.location, c.rarity, c.detail))
            for i, c in enumerate(self._computer.codex)])

        lead_rows = []
        for i, ld in enumerate(self._computer.leads):
            # Off-origin + uncharted: point the player back to where the tip was obtained.
            turns = (str(ld.turn_cost) if ld.reachable
                     else f"plot from S{ld.origin_coords}" if not ld.at_origin
                     else "unreachable")
            # A roaming-Entity lead whose quarry has moved on reads as a cold trail (§7).
            summary = (Text.assemble(ld.summary, ("  · trail gone cold", "italic yellow"))
                       if ld.stale else Text(ld.summary))
            lead_rows.append((str(i), (summary, ld.source, f"S{ld.coords}",
                                       str(ld.distance) if ld.reachable else "—", turns)))
        self._dt("leads-table").set_rows(lead_rows)

        self._dt("contracts-table").set_rows([
            (str(c.contract_id), (str(c.contract_id), c.kind, c.issuer, c.summary,
                                  f"{c.reward:,}", f"day {c.deadline_day}"))
            for c in self._computer.contracts])

        self._dt("ports-table").set_rows([
            (str(i), (f"S{e.sector_display}", e.name, e.klass, e.buys, e.sells,
                      str(e.dist) if e.dist >= 0 else "—"))
            for i, e in enumerate(self._computer.ports)])

        self._dt("planets-table").set_rows([
            (str(i), (f"S{pl.sector_display}", pl.name, pl.ptype, pl.owner,
                      f"{pl.colonists:,}", pl.species, pl.stores,
                      str(pl.dist) if pl.dist >= 0 else "—"))
            for i, pl in enumerate(self._computer.planets)])

        # Market rows key on the logical order, so a refresh keeps the cursor
        # on the same sector/port/commodity/side even when quantities move.
        orders = self._market.orders if self._market.enabled else []
        self._dt("market-table").set_rows([
            (f"{o.sector_display}:{o.port_name}:{o.commodity}:{o.side}",
             (f"S{o.sector_display}", o.port_name, o.commodity,
              o.side, str(o.qty), str(o.limit)))
            for o in orders])

        route = self.query_one("#route-table", DataTable)
        route.add_columns("Hop", "Sector", "Notes")
        self._render_route()

        bloc_rows = []
        for a in self._computer.alliances:
            flags = "".join((
                "[green]⭐ sworn[/] " if a.member else "",
                "[cyan]⚑ governs Core[/] " if a.governs_core else "",
                "[yellow]covets Core[/]" if a.covets_core else "",
            ))
            progress = (f"{len(a.tasks_done)}/{len(a.tasks_needed)} "
                        f"({', '.join(a.tasks_done) or '—'})"
                        if a.tasks_needed else "open")
            bloc_rows.append((str(a.alliance_id),
                              (a.name, f"{a.standing:+.2f}", a.gate, f"{a.fee:,}",
                               progress, Text.from_markup(flags))))
        self._dt("alliances-table").set_rows(bloc_rows)

        self._dt("notes-table").set_rows([
            (str(i), (str(i + 1), text))
            for i, text in enumerate(self._computer.notes)])

        dossier_rows = []
        for i, d in enumerate(self._computer.dossier):
            # Show a bloc member's role (leader / aspirant) so an intrigue coup is legible (WP51).
            alliance = f"{d.alliance} · {d.role}" if d.role not in ("none", "member") else d.alliance
            dossier_rows.append((str(i), (d.species, alliance, d.standing, f"S{d.last_seen}",
                                          bar(d.disposition_filled, 5), d.offers)))
        self._dt("dossier-table").set_rows(dossier_rows)

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
            notify_warning(self, "No Core seizure is ready to petition.")
            return

        def _go(ok: bool | None) -> None:
            if not ok:
                return
            from edge.core.rules import PetitionCoreSeizure
            try:
                self._service.apply(self._pid, PetitionCoreSeizure(alliance_id=sz.alliance_id))
            except (EconomyError, MovementError) as exc:
                notify_warning(self, str(exc))
                return
            self.notify(f"The Core is seized — {sz.alliance_name} now governs.", timeout=5)
            self._computer = self._service.computer_view(self._pid)
            self.query_one("#seizure-panel", Static).update(self._seizure_notes())

        self.app.push_screen(ConfirmScreen(
            f"Petition {sz.alliance_name} to seize the Core?\n"
            "Core governance flips — the old governor's welcome ends."), _go)

    # --- Contracts (WP57 — surfaced WP71) -------------------------------------

    def _highlighted_contract(self) -> int | None:
        """The contract id under the cursor on the Contracts tab, or None."""
        if self._active_subview() != "contracts":
            self.notify("Switch to the Contracts tab first.", timeout=2)
            return None
        table = self.query_one("#contracts-table", DataTable)
        if not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return int(key.value) if key.value is not None else None

    def action_deliver_contract(self) -> None:
        """Fulfil the highlighted deliver favor at its destination port (§6.7, WP57)."""
        cid = self._highlighted_contract()
        if cid is None:
            return
        from edge.core.rules import DeliverContract
        try:
            self._service.apply(self._pid, DeliverContract(contract_id=cid))
        except EconomyError as exc:
            notify_warning(self, str(exc))
            return
        self.notify("Delivered — the reward is paid.", timeout=3)
        self._reopen_tab("contracts")

    def action_abandon_contract(self) -> None:
        """X: abandon the highlighted favor — or, on the Notes tab, remove a note."""
        if self._active_subview() == "notes":
            self._remove_note()
            return
        cid = self._highlighted_contract()
        if cid is None:
            return
        from edge.core.rules import AbandonContract
        try:
            self._service.apply(self._pid, AbandonContract(contract_id=cid))
        except EconomyError as exc:
            notify_warning(self, str(exc))
            return
        self.notify("Contract abandoned.", timeout=2)
        self._reopen_tab("contracts")

    # --- Notes + avoid list (§9 Notes tab — WP73) ------------------------------

    def action_add_note(self) -> None:
        """Write a captain's note (any tab; lands on the Notes tab)."""
        from edge.tui.screens.stardock import _NoticeInput

        def _go(text: str | None) -> None:
            if not text:
                return
            from edge.core.rules import AddNote
            try:
                self._service.apply(self._pid, AddNote(text=text))
            except EconomyError as exc:
                notify_warning(self, str(exc))
                return
            self._reopen_tab("notes")

        self.app.push_screen(_NoticeInput("Write a note"), _go)

    def _remove_note(self) -> None:
        table = self.query_one("#notes-table", DataTable)
        if not table.row_count:
            return
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if key.value is None:
            return
        from edge.core.rules import RemoveNote
        try:
            self._service.apply(self._pid, RemoveNote(index=int(key.value)))
        except EconomyError as exc:
            notify_warning(self, str(exc))
            return
        self._reopen_tab("notes")

    def action_toggle_avoid(self) -> None:
        """Toggle a sector on the route-planner avoid list (§9 — WP73)."""
        def _go(shown: int | None) -> None:
            if shown is None:
                return
            internal = self._service.resolve_display_id(shown)
            if internal is None:
                notify_warning(self, f"No sector {shown}.")
                return
            from edge.core.rules import ToggleAvoid
            try:
                self._service.apply(self._pid, ToggleAvoid(sector_id=internal))
            except EconomyError as exc:
                notify_warning(self, str(exc))
                return
            self._reopen_tab("notes")
        self.app.push_screen(TravelPromptScreen(), _go)

    def _reopen_tab(self, tab: str) -> None:
        """Rebuild the screen on the given tab after a state change."""
        self.app.pop_screen()
        self.app.push_screen(ComputerScreen(self._service, self._pid, initial_tab=tab))

    # --- Alliances (§6.3, WP38 — surfaced WP72) --------------------------------

    def _highlighted_alliance(self) -> AllianceRowDTO | None:
        """The AllianceRowDTO under the cursor on the Alliances tab, or None."""
        if self._active_subview() != "alliances":
            self.notify("Switch to the Alliances tab first.", timeout=2)
            return None
        table = self.query_one("#alliances-table", DataTable)
        if not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if key.value is None:
            return None
        aid = int(key.value)
        return next((a for a in self._computer.alliances if a.alliance_id == aid), None)

    def action_join_alliance(self) -> None:
        """Join the highlighted bloc — or resign your own (§6.3, WP38)."""
        row = self._highlighted_alliance()
        if row is None:
            return
        from edge.core.rules import JoinAlliance, ResignAlliance
        command = ResignAlliance() if row.member else JoinAlliance(row.alliance_id)

        def _go(ok: bool | None = True) -> None:
            if not ok:
                return
            try:
                self._service.apply(self._pid, command)
            except (EconomyError, MovementError) as exc:
                notify_warning(self, str(exc))
                return
            self.notify("Resigned — you stand apart again." if row.member
                        else f"Sworn to the {row.name}.", timeout=3)
            self._reopen_tab("alliances")

        if row.member:  # D7 (WP73): resigning resets standings — confirm it
            self.app.push_screen(ConfirmScreen(
                f"Resign from the {row.name}?\nYour standing with them resets."), _go)
        else:
            _go()

    def action_log_admission_task(self) -> None:
        """Record the next admission task for the highlighted bloc (§6.3, WP38).

        `AdvanceAdmission` is the seam gameplay will feed automatically; until those
        hooks land, the ledger is advanced here (one task per press, in price order).
        """
        row = self._highlighted_alliance()
        if row is None:
            return
        pending = [t for t in row.tasks_needed if t not in row.tasks_done]
        if not pending:
            self.notify("Their admission price is already met.", timeout=2)
            return
        from edge.core.rules import AdvanceAdmission
        try:
            self._service.apply(self._pid, AdvanceAdmission(row.alliance_id, pending[0]))
        except EconomyError as exc:
            notify_warning(self, str(exc))
            return
        self.notify(f"Recorded: {pending[0]}.", timeout=2)
        self._reopen_tab("alliances")

    def _market_empty_copy(self) -> tuple[str, str]:
        """The order book's empty-state copy (WP-UI19; rendered by DetailTable)."""
        if not self._market.enabled:
            return ("The order-book market is disabled.",
                    "The legacy port economy is running — there is no "
                    "order book to show.")
        return ("No open orders at charted ports.",
                "Dock somewhere to read its book.")

    def _market_note(self) -> str:
        if not self._market.enabled:
            return ""
        if not self._market.purses:
            return "[dim]Purses shown as of your last visit — dock to refresh a port's book.[/]"
        purses = "   ".join(f"S{d} {name} [cyan]{purse:,}[/]"
                            for d, name, purse in self._market.purses[:6])
        return f"[dim]Purses (as of last dock):[/]  {purses}"

    # --- WP-UI20: category + subview navigation --------------------------------

    def _active_category(self) -> str:
        return (self.query_one("#cats", TabbedContent).active or "cat-commerce")[len("cat-"):]

    def _active_subview(self) -> str:
        """The pane id of the visible subview (the unit every action keys on)."""
        category = self._active_category()
        return self.query_one(f"#sub-{category}", TabbedContent).active

    def show_subview(self, subview: str) -> None:
        """Open `subview` by its legacy pane id, switching category as needed."""
        category = _CATEGORY_OF[subview]
        self.query_one("#cats", TabbedContent).active = f"cat-{category}"
        self.query_one(f"#sub-{category}", TabbedContent).active = subview

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "cat-button":
            return

        def _picked(category: object) -> None:
            if category is not None:
                self.query_one("#cats", TabbedContent).active = f"cat-{category}"

        options: list[tuple[str, int | str]] = [(CATEGORY_LABELS[c] + "  [dim]" +
                    " · ".join(SUBVIEW_LABELS[s] for s in subs) + "[/]", c)
                   for c, subs in CATEGORIES.items()]
        self.app.push_screen(ListPicker("Computer category", options), _picked)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        source = event.tabbed_content
        if source.id == "cats":
            category = self._active_category()
            self.query_one("#cat-button", Button).label = (
                f"Category: {CATEGORY_LABELS[category]} ▾")
        elif source.id is not None and source.id.startswith("sub-"):
            # Each category remembers its last subview, app-wide (WP-UI20).
            subviews = getattr(self.app, "computer_subviews", None)
            if subviews is not None:
                subviews[source.id[len("sub-"):]] = source.active
        # Remember the visible subview across screens so [C] reopens there.
        active = self._active_subview()
        self.app.computer_tab = active
        if active == "map" and self._active_category() == "navigation":
            # The Map pane only has a real width once it is shown — fit + focus it now
            # so the arrow keys drive the sector cursor immediately.
            view = self.query_one("#local-map", LocalMapView)
            view._refit()
            self.call_after_refresh(view.focus)

    def _map_for_width(self, width: int) -> LocalMapDTO:
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
        self.show_subview("route")

    def _cursor_entry(self, table_id: str, items: list) -> object | None:  # type: ignore[type-arg]
        """The DTO under the highlighted row of `table_id`, or None.

        WP-UI21: resolved through the row's stable key (its index into the DTO
        list), never the cursor's visual position — sorting and filtering
        reorder the display but must not change what an action targets."""
        table = self.query_one(table_id, DataTable)
        if not items or not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        if key is None:
            return None
        try:
            return items[int(key)]
        except (ValueError, IndexError):
            return None

    def _current_sector(self) -> int:
        # Through the projection (not raw state) so it works over a remote client too (WP68).
        return self._service.game_view(self._pid).sector.sector_id

    def action_plot_route(self) -> None:
        active = self._active_subview()
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
            notify_warning(self, f"No sector {dest}.")
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
            notify_warning(self, dto.reason or "Cannot travel that route.")
            return
        if dto.hazards:  # known black holes / hostile forces / band interrupt risk (WP75)
            self.app.push_screen(
                ConfirmScreen(self._route_confirmation(dto), confirm_label="Engage"),
                self._engage_confirmed,
            )
            return
        self._engage_confirmed(True)

    @staticmethod
    def _route_confirmation(dto: RouteDTO) -> str:
        """Summarize the authoritative plotted DTO without duplicating route rules."""
        avoids = ", ".join(f"S{sid}" for sid in dto.avoids) or "none"
        hazards = "\n".join(f"• {item}" for item in dto.hazards) or "• none known"
        interruption = next((h for h in dto.hazards if "Encounter risk" in h), "none known")
        return (
            f"Route to S{dto.dest_display}\n"
            f"{len(dto.hops)} hops · {dto.turn_cost} turns\n"
            f"Avoid list honored: {avoids}\n"
            f"Interruption risk: {interruption}\n\n"
            f"Known hazards:\n{hazards}\n\nEngage route?"
        )

    def _engage_confirmed(self, ok: bool | None) -> None:
        if not ok or self._engage_target is None:
            return
        try:
            self._service.apply(self._pid, TravelTo(to_sector=self._engage_target))
        except (MovementError, EconomyError) as exc:
            notify_warning(self, str(exc))
            return
        self.app.pop_screen()  # back to the game screen, which recomposes on resume

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
