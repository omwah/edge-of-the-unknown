"""ComputerScreen — the ship computer (UI_MOCKUPS.md §9).

Phase-1 core screen: a tabbed query console over the owned game engine. The
**Trade** tab is the pair-trade finder; the **Map** and **Log** tabs fold in the
galactic map and the durable event log (WP-B — they live *inside* the computer
but keep their direct `M`/`G` hotkeys on the game screen). Every tab is live:
Ports/Route (WP15/WP14), Codex/Dossier (WP11), Contracts (WP57/WP71),
Alliances (WP72), **Corp** (§4/WP66 — the corporation is a relationship, so it sits
with contracts, alliances and the dossier under Relations rather than behind a
game-screen hotkey of its own), and Notes — captain's notes plus the route-planner
avoid list (WP73).

WP-UI20: the thirteen-tab strip is grouped into five categories (Navigation ·
Commerce · Exploration · Relations · Logbook), each holding its subviews as an
inner tab row. Every category remembers its last subview (app-level, so `[C]`
reopens where the player left off); direct hotkeys, plotted routes, codex and
contract links target subviews by their unchanged pane ids via
`show_subview()`. Compact terminals swap the category tab bar for a popup
selector (the subview row stays), per the UI_MOCKUPS wireframe.

PT-32 keyboard model — **a tab owns its keys.** The screen binds only what is
screen-wide (Back, and the category accelerators — the underlined letter of each
category title: **N**avigation, **C**ommerce, e**X**ploration, **R**elations,
Log**b**ook). Every *tab* verb is declared in `PANE_BINDINGS` and bound onto that
subview's `ActionPane`; each category pane likewise owns its **sub-tab numbers**
(`1`..`N`, shown leading each sub-tab title). Both are live only while focus is inside
that pane. Three things follow, and they are the point: the footer (and the `.` menu,
`?` help and palette, via `action_descriptors`) advertise exactly the visible tab's
verbs and nothing else — navigation keys stay off it; a key may mean two things on two
tabs (Delete abandons a favor on Contracts, removes a note on Notes; `2` means a
different tab in each category) with no `check_action` scoping maze; and focus is kept
inside the visible pane — accelerators, numbers, Enter-on-the-rail, `show_subview()`
and mount all land it on the tab's primary control.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.widgets import (
    Button, DataTable, Footer, Static, TabbedContent, TabPane, Tabs,
)

from edge.core.dto import AllianceRowDTO, LocalMapDTO, RouteDTO
from edge.core.economy import EconomyError
from edge.core.movement import MovementError
from edge.core.rules import ToggleAvoid, TravelTo
from edge.server.service import GameService
from edge.tui.chrome import EdgeScreen, notify_warning
from edge.tui.design import ActionDescriptor
from edge.tui.detail_table import ColumnSpec, DetailTable
from edge.tui.screens.confirm import ConfirmScreen
from edge.tui.screens.corp import CorpActions, CorpPanels
from edge.tui.screens.picker import ListPicker
from edge.tui.screens.travel import TravelPromptScreen
from edge.tui.widgets import (
    ActionPane, LocalMapView, accel_title, bar, focus_content, preserve_cursor,
)

# WP-UI20: the five-category information architecture. Every legacy tab id maps
# to exactly one category; pane ids are unchanged so hotkeys and links keep
# addressing subviews by the same names.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "navigation": ("map", "route"),
    "commerce": ("ports", "trade", "market"),
    "exploration": ("planets", "codex", "leads"),
    "relations": ("contracts", "alliances", "dossier", "corp"),
    "records": ("log", "notes"),
}
CATEGORY_LABELS = {
    "navigation": "Navigation", "commerce": "Commerce",
    "exploration": "Exploration", "relations": "Relations", "records": "Logbook",
}
SUBVIEW_LABELS = {
    "map": "Map", "route": "Route", "ports": "Ports", "trade": "Trade",
    "market": "Market", "planets": "Planets", "codex": "Codex", "leads": "Leads",
    "contracts": "Contracts", "alliances": "Alliances", "dossier": "Dossier",
    "corp": "Corp", "log": "Log", "notes": "Notes",
}
_CATEGORY_OF = {sub: cat for cat, subs in CATEGORIES.items() for sub in subs}


class ComputerScreen(CorpActions, EdgeScreen):
    # Screen-wide keys only: leaving, and reaching a category. Every *tab* verb lives on
    # its own pane in PANE_BINDINGS below — never here — so the footer advertises exactly
    # what the tab you are looking at can do. Back leads the footer on every screen
    # (chrome.EdgeScreen), so it is first here too.
    BINDINGS = [
        Binding("escape", "back", "Back"),
        # Category-focus accelerators (WP-PR2-01 / PT-32): jump to a category and focus
        # its active subview's content in one step. Letters are underlined in the tab
        # titles and kept off the footer (show=False). Enter on the tab rail focuses the
        # active subview's content too.
        Binding("n", "focus_category('navigation')", "Navigation", show=False),
        Binding("c", "focus_category('commerce')", "Commerce", show=False),
        Binding("x", "focus_category('exploration')", "Exploration", show=False),
        Binding("r", "focus_category('relations')", "Relations", show=False),
        Binding("b", "focus_category('records')", "Logbook", show=False),
        Binding("enter", "focus_active_content", "Enter tab", show=False),
    ]

    # subview pane id -> the (key, action, description) triples that pane owns (PT-32).
    # `ActionPane` binds each into the `screen.` namespace, so the handlers below stay
    # on the screen while the keys live on the tab and follow focus. Keys may repeat
    # across panes (Delete abandons a favor on Contracts, removes a note on Notes)
    # because only one pane is ever in the focus chain. Nothing here may collide with a
    # screen binding above or with DetailTable's own table keys (`/` filter, `O` sort) —
    # tests/test_ui_computer_keys.py enforces both. `W` is "route to…" here for the same
    # reason it is on the sector view: one key, one meaning, across screens.
    PANE_BINDINGS: dict[str, tuple[tuple[str, str, str], ...]] = {
        "map": (("p", "plot_route", "Plot route"), ("g", "engage", "Engage"),
                ("w", "route_prompt", "Route to…")),
        "route": (("g", "engage", "Engage"), ("w", "route_prompt", "Route to…"),
                  ("v", "toggle_avoid", "Avoid sector")),
        "ports": (("p", "plot_route", "Plot route"), ("v", "toggle_avoid", "Avoid sector")),
        "trade": (("p", "plot_route", "Plot route"),),
        "market": (),
        "planets": (("p", "plot_route", "Plot route"), ("v", "toggle_avoid", "Avoid sector")),
        "codex": (("p", "plot_route", "Plot route"),),
        "leads": (("p", "plot_route", "Plot route"),),
        "contracts": (("d", "deliver_contract", "Deliver"),
                      ("delete", "abandon_contract", "Abandon")),
        "alliances": (("j", "join_alliance", "Join/Resign"),
                      ("t", "log_admission_task", "Log task")),
        "dossier": (("s", "seize_core", "Seize Core"),),
        # The corp is a relationship, so it lives here beside contracts, alliances and the
        # dossier rather than behind a game-screen hotkey of its own. Its keys are pure
        # accelerators — every verb is also a button on its panel — and they are free to
        # reuse letters the other tabs spend (D deposits here, delivers on Contracts; W
        # withdraws here, routes on Map) because only one pane is ever in the focus chain.
        # `X` and `O` are avoided: `X` is a category accelerator and `O` belongs to a
        # focused table, so Expel is `K` and "world → CEO" is `U` (un-assign).
        "corp": (("f", "form", "Charter"), ("d", "deposit", "Deposit 1k"),
                 ("w", "withdraw", "Withdraw 1k"), ("l", "leave", "Leave corp"),
                 ("i", "invite", "Invite"), ("a", "accept_invite", "Accept invite"),
                 ("k", "expel", "Expel"), ("g", "declare_war", "Declare war"),
                 ("e", "end_war", "End war"), ("p", "planet_to_corp", "World → corp"),
                 ("u", "planet_from_corp", "World → CEO")),
        "log": (),
        "notes": (("a", "add_note", "Add note"), ("delete", "remove_note", "Remove note"),
                  ("v", "toggle_avoid", "Avoid sector")),
    }

    # category -> the letter underlined in its tab title (WP-PR2-01 / PT-32).
    _CAT_ACCEL = {"navigation": "n", "commerce": "c", "exploration": "x",
                  "relations": "r", "records": "b"}
    # WP-UI06: seize_core flips Core governance (destructive, always confirmed);
    # engage confirms only over known hazards; join_alliance confirms the resign
    # branch. Enforced statically by tests/test_ui_actions.py.
    ACTION_DANGER = {"seize_core": "destructive", "engage": "caution",
                     "join_alliance": "caution"}

    HELP_TITLE = "Ship's computer"
    HELP = """\
Five categories — [b]N[/]avigation (Map · Route), [b]C[/]ommerce (Ports · Trade ·
Market), e[b]X[/]ploration (Planets · Codex · Leads), [b]R[/]elations (Contracts ·
Alliances · Dossier · Corp), Log[b]b[/]ook (Log · Notes) — each remembers its last subview.
The [b]underlined letter[/] jumps to a category and focuses its contents in one step.
Inside a category, its sub-tabs are [b]numbered[/]: press [b]1[/]…[b]N[/] for the tab
whose title carries that number. Enter on the tab rail focuses the active subview's
contents.

Every action key [b]belongs to its tab[/]: the footer only offers what the tab you are
looking at can do, so a key is free to mean two things in two places — [b]Del[/]
abandons a favor on Contracts and removes a note on Notes. [b]P[/] plots a route from
Ports, Planets, Trade, Codex or Leads; [b]G[/] engages the plotted route and [b]W[/]
routes to a typed sector (Map, Route — [b]W[/] is the sector view's key for the same
thing); [b]V[/] toggles the highlighted row's sector on the avoid list (Ports, Planets,
Route) or prompts for one on Notes, which also lists every avoided sector; [b]D[/]
delivers a favor; [b]J[/] joins or resigns a bloc and [b]T[/] logs an admission task;
[b]S[/] petitions to seize the Core from the Dossier. The [b]Corp[/] tab is button-first —
every verb there is a button on its panel, and its keys ([b]F[/] charter, [b]D[/]/[b]W[/]
bank, [b]I[/] invite, [b]K[/] expel, [b]G[/]/[b]E[/] war, [b]L[/] leave) are accelerators
for them. Only [b]Esc[/] (back) is screen-wide, and it always leads the footer.

Your own worlds and base-hosted ports sort to the top of Planets/Ports (★ / ⚓);
finished contracts stay listed but dim. In any table, [b]/[/] focuses the filter,
[b]O[/] cycles the sort (or click a ↕ header); Enter on a row opens its full detail
when columns are folded at 80×24."""

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

    def _pane(self, subview: str) -> ActionPane:
        """A subview pane carrying its own action keys (PT-32) — the one place a
        pane id, its label and its bindings are paired, so they cannot drift.

        The title leads with the sub-tab's number, which is its hotkey inside the
        category (bound on the category pane by `_category_pane`)."""
        number = CATEGORIES[_CATEGORY_OF[subview]].index(subview) + 1
        return ActionPane(f"[bold underline]{number}[/] {SUBVIEW_LABELS[subview]}",
                          id=subview, actions=self.PANE_BINDINGS[subview])

    def _category_pane(self, category: str) -> ActionPane:
        """A category pane. It owns the sub-tab **numbers** (1..N) for its own subviews.

        They live here, not on the screen, for the PT-32 reason everything else does: a
        category pane is in the binding chain only while you are inside that category, so
        `2` means "this category's second tab" and cannot reach into another's. They are
        hidden from the footer — navigation, not verbs."""
        numbers = tuple((str(i), f"focus_subview('{sub}')", SUBVIEW_LABELS[sub])
                        for i, sub in enumerate(CATEGORIES[category], 1))
        return ActionPane(accel_title(CATEGORY_LABELS[category], self._CAT_ACCEL[category]),
                          id=f"cat-{category}", classes="cat-pane", hidden=numbers)

    def compose(self) -> ComposeResult:
        yield Static("SHIP COMPUTER", id="computer-title")
        initial_cat = _CATEGORY_OF.get(self._initial_tab, "commerce")
        # Compact tier: the category tab bar is hidden and this popup selector
        # stands in for it (UI_MOCKUPS wireframe); the subview row stays.
        with Horizontal(id="cat-strip"):
            yield Button(f"Category: {CATEGORY_LABELS[initial_cat]} ▾", id="cat-button")
        with TabbedContent(initial=f"cat-{initial_cat}", id="cats"):
            with self._category_pane("navigation"):
                with TabbedContent(initial=self._inner_initial("navigation"),
                                   id="sub-navigation"):
                    with self._pane("map"):
                        yield Static(
                            f"[b]LOCAL MAP[/]   [dim]you @ Sector {self._map.you_display} · "
                            f"Band {self._map.you_band}   ·   ↑↓←→ select · ↵/P plot route[/]",
                            id="map-header",
                        )
                        yield LocalMapView(self._map, rebake=self._map_for_width, id="local-map")
                    with self._pane("route"):
                        yield Static("[b]ROUTE PLANNER[/]        [dim]plot before you commit[/]")
                        yield DataTable(id="route-table", zebra_stripes=True, cursor_type="row")
                        yield Static("", id="route-summary", classes="note")
            with self._category_pane("commerce"):
                with TabbedContent(initial=self._inner_initial("commerce"), id="sub-commerce"):
                    with self._pane("ports"):
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
                        yield Static("[dim][b]P[/] Plot route   ·   [b]V[/] Toggle highlighted sector avoid[/]",
                                     classes="note")
                    with self._pane("trade"):
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
                            "[b]P[/] Plot route",
                            classes="note",
                        )
                    with self._pane("market"):
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
            with self._category_pane("exploration"):
                with TabbedContent(initial=self._inner_initial("exploration"),
                                   id="sub-exploration"):
                    with self._pane("planets"):
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
                        yield Static("[dim][b]P[/] Plot route   ·   [b]V[/] Toggle highlighted sector avoid[/]",
                                     classes="note")
                    with self._pane("codex"):
                        yield Static("[b]DISCOVERY CODEX[/]        [dim]logged finds, richest first[/]")
                        yield DetailTable("codex-table", (
                            ColumnSpec("Find", sortable=True),
                            ColumnSpec("Kind", fold=True),
                            ColumnSpec("Location"),
                            ColumnSpec("Rarity", sortable=True),
                            ColumnSpec("Detail", fold=True),
                        ), empty=("No discoveries logged yet.",
                                  "Scan and survey the frontier to fill the codex."),
                            detail_title="Discovery")
                    with self._pane("leads"):
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
            with self._category_pane("relations"):
                with TabbedContent(initial=self._inner_initial("relations"), id="sub-relations"):
                    with self._pane("contracts"):
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
                                     "   ·   [b]Del[/] Abandon highlighted[/]", classes="note")
                    with self._pane("alliances"):
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
                    with self._pane("dossier"):
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
                    with self._pane("corp"):
                        yield CorpPanels(self._service.corp_view(self._pid), id="corp-body")
            with self._category_pane("records"):
                with TabbedContent(initial=self._inner_initial("records"), id="sub-records"):
                    with self._pane("log"):
                        yield Static("[b]EVENT LOG[/]        [dim]newest first[/]")
                        yield DetailTable("log-table", (
                            ColumnSpec("When"),
                            ColumnSpec("Event"),
                        ), empty=("No events yet.", "Your voyage writes the log."),
                            detail_title="Event")
                    with self._pane("notes"):
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
                        yield Button("Add / remove a sector on the avoid list…", id="avoid-add")
                        yield Static("[dim][b]A[/] Add note   ·   [b]Del[/] Remove highlighted   ·   "
                                     "[b]V[/] Toggle a sector on the avoid list[/]", classes="note")
        yield Footer()

    def _dt(self, table_id: str) -> DetailTable:
        return self.query_one(f"#{table_id}-panel", DetailTable)

    @staticmethod
    def _port_name_cell(e: object) -> "str | Text":
        """A port row's name, marked with ⚓ when it carries a base — with market status (PT-09)."""
        name = e.name  # type: ignore[attr-defined]
        market = "market open" if e.starbase_market_open else "market dark"  # type: ignore[attr-defined]
        if e.starbase_yours:  # type: ignore[attr-defined]
            return Text.from_markup(f"[cyan]⚓[/] {name}  [dim]your base · {market}[/]")
        if e.starbase_status:  # type: ignore[attr-defined]
            return Text.from_markup(f"{name}  [dim]⚓ {e.starbase_status} · {market}[/]")  # type: ignore[attr-defined]
        return name

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
            (str(i), (c.name, c.kind, c.location, c.rarity, c.detail))
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

        # Contracts (PT-27): active first, finished ones dim with their status in the Due cell.
        contract_rows = []
        for c in self._computer.contracts:
            done = c.status != "active"
            def _c(text: str, _done: bool = done) -> "str | Text":
                return Text.from_markup(f"[dim]{text}[/]") if _done else text
            due = ({"done": "[green]✓ done[/]", "failed": "[red]✗ failed[/]"}.get(c.status)
                   or f"day {c.deadline_day}")
            contract_rows.append((str(c.contract_id), (
                _c(str(c.contract_id)), _c(c.kind), _c(c.issuer), _c(c.summary),
                _c(f"{c.reward:,}"), Text.from_markup(due))))
        self._dt("contracts-table").set_rows(
            contract_rows,
            group_first=[str(c.contract_id) for c in self._computer.contracts if c.status == "active"])

        # Ports (PT-09): a player-owned base's port floats to the top with a ⚓ marker.
        self._dt("ports-table").set_rows([
            (str(i), (f"S{e.sector_display}", self._port_name_cell(e), e.klass, e.buys, e.sells,
                      str(e.dist) if e.dist >= 0 else "—"))
            for i, e in enumerate(self._computer.ports)],
            group_first=[str(i) for i, e in enumerate(self._computer.ports) if e.starbase_yours])

        # Planets (PT-08): your worlds float to the top with a ★ marker.
        self._dt("planets-table").set_rows([
            (str(i), (f"S{pl.sector_display}",
                      Text.from_markup(f"[b yellow]★[/] {pl.name}") if pl.owned_by_you else pl.name,
                      pl.ptype, pl.owner, f"{pl.colonists:,}", pl.species, pl.stores,
                      str(pl.dist) if pl.dist >= 0 else "—"))
            for i, pl in enumerate(self._computer.planets)],
            group_first=[str(i) for i, pl in enumerate(self._computer.planets) if pl.owned_by_you])

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

        # Open with focus already in the visible subview's content (PT-32): the footer
        # then advertises that tab's verbs from the first frame, and the arrow keys drive
        # its table rather than the tab rail.
        self.call_after_refresh(self._focus_subview_content, self._active_category())

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
        """The *active* contract id under the cursor on the Contracts tab, or None.

        A finished (done/failed) favor is a record only — its actions are disabled (PT-27),
        so selecting one explains why instead of issuing a doomed command."""
        if self._active_subview() != "contracts":
            self.notify("Switch to the Contracts tab first.", timeout=2)
            return None
        table = self.query_one("#contracts-table", DataTable)
        if not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if key.value is None:
            return None
        cid = int(key.value)
        contract = next((c for c in self._computer.contracts if c.contract_id == cid), None)
        if contract is not None and contract.status != "active":
            self.notify("That favor is finished — it stays on the board as a record only.",
                        timeout=3)
            return None
        return cid

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
        """X on Contracts: abandon the highlighted favor.

        The Notes tab binds its own X to `remove_note` (PT-32) — the two verbs share a
        letter because each lives on its own pane, never on the screen."""
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
        """A on Notes: write a captain's note."""
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

    def action_remove_note(self) -> None:
        """X on Notes: strike the highlighted note."""
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
        """Toggle the highlighted directory/route row, falling back to a prompt (PT-23)."""
        sector = self._highlighted_avoid_sector()
        if sector is not None:
            self._toggle_avoid_sector(sector)
            return

        def _go(shown: int | None) -> None:
            if shown is None:
                return
            internal = self._service.resolve_display_id(shown)
            if internal is None:
                notify_warning(self, f"No sector {shown}.")
                return
            self._toggle_avoid_sector(internal, reopen="notes")
        self.app.push_screen(TravelPromptScreen(), _go)

    def _highlighted_avoid_sector(self) -> int | None:
        """Internal sector id under an avoid-capable highlighted row, if any."""
        active = self._active_subview()
        if active == "ports":
            entry = self._cursor_entry("#ports-table", self._computer.ports)
            return None if entry is None else entry.sector_id  # type: ignore[attr-defined]
        if active == "planets":
            entry = self._cursor_entry("#planets-table", self._computer.planets)
            return None if entry is None else entry.sector_id  # type: ignore[attr-defined]
        if active == "route":
            table = self.query_one("#route-table", DataTable)
            if not table.row_count:
                return None
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            return int(key) if key is not None else None
        return None

    def _toggle_avoid_sector(self, sector_id: int, *, reopen: str | None = None) -> None:
        try:
            self._service.apply(self._pid, ToggleAvoid(sector_id=sector_id))
        except EconomyError as exc:
            notify_warning(self, str(exc))
            return
        if reopen is not None:
            self._reopen_tab(reopen)
            return
        self._computer = self._service.computer_view(self._pid)
        avoided = any(self._service.resolve_display_id(shown) == sector_id
                      for shown in self._computer.avoid)
        state = "added to" if avoided else "removed from"
        self.notify(f"Highlighted sector {state} the avoid list.", timeout=2)

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
        """Open `subview` by its legacy pane id, switching category as needed.

        Focus follows the tab into its content (PT-32). It has to: a pane's action keys
        are only live while focus is inside it, so leaving focus behind in the pane we
        just navigated away from would keep the *old* tab's verbs in the footer."""
        category = _CATEGORY_OF[subview]
        self._blur_stale_pane()
        self.query_one("#cats", TabbedContent).active = f"cat-{category}"
        self.query_one(f"#sub-{category}", TabbedContent).active = subview
        self.call_after_refresh(self._focus_subview_content, category)

    # --- WP-PR2-01 / PT-32: category accelerators + Enter-to-content ------------

    def action_focus_category(self, category: str) -> None:
        """Jump to a category and focus its active subview's primary content."""
        self._blur_stale_pane()
        self.query_one("#cats", TabbedContent).active = f"cat-{category}"
        self.call_after_refresh(self._focus_subview_content, category)

    def _blur_stale_pane(self) -> None:
        """Drop focus *before* switching tabs.

        Textual re-activates whichever `TabPane` contains the focused widget
        (`TabbedContent._on_tab_pane_focused`), so focus left behind in the pane we are
        leaving drags the tab straight back — the switch silently reverts. Blurring first
        lets the new tab stick; `_focus_subview_content` then puts focus in its content,
        which re-activates the same (correct) pane harmlessly."""
        if self.focused is not None and not isinstance(self.focused, Tabs):
            self.set_focus(None)

    def _focus_subview_content(self, category: str) -> None:
        try:
            sub = self.query_one(f"#sub-{category}", TabbedContent)
            pane = self.query_one(f"#{sub.active}", TabPane)
        except NoMatches:
            return
        focus_content(pane)

    def action_focus_subview(self, subview: str) -> None:
        """A sub-tab number key: open that subview and focus its content."""
        self.show_subview(subview)

    def action_focus_active_content(self) -> None:
        """Enter on the tab rail focuses the active subview's content (reaches it in one step)."""
        self._focus_subview_content(self._active_category())

    def _follow_focus_to_visible_pane(self) -> None:
        """Never strand focus in a pane that is no longer showing (PT-32).

        A pane's action keys are in the footer — and fire — only while focus sits inside
        it, so focus left behind in the tab you just navigated away from would advertise
        the wrong verbs. Focus resting on a tab rail is left alone: that is a player
        arrowing along the tabs, and stealing it would make the rail unusable."""
        focused = self.focused
        if focused is None or isinstance(focused, Tabs):
            return
        try:
            pane = self.query_one(f"#{self._active_subview()}", TabPane)
        except NoMatches:
            return
        if pane not in focused.ancestors_with_self:
            self.set_focus(None)  # see _blur_stale_pane: a stale focus would revert the tab
            self.call_after_refresh(self._focus_subview_content, self._active_category())

    def action_descriptors(self) -> list[ActionDescriptor]:
        """The `.` menu / `?` help / palette list, scoped exactly like the footer (PT-32).

        The default list is derived from a screen's class `BINDINGS`; this screen keeps
        its tab verbs on the panes instead, so it assembles the same thing from the
        active subview. One source of truth, so the four surfaces cannot disagree —
        parity is proven in tests/test_ui_computer_keys.py.
        """
        danger: dict[str, str] = self.ACTION_DANGER
        shown = [b for b in self.BINDINGS if isinstance(b, Binding) and b.show]
        out = [ActionDescriptor(id=b.action, title=b.description, help=b.description,
                                key=b.key, action=b.action) for b in shown]
        try:
            pane_actions = self.PANE_BINDINGS[self._active_subview()]
        except NoMatches:  # before mount — the tab rail is not up yet
            pane_actions = ()
        out += [ActionDescriptor(id=action, title=description, help=description, key=key,
                                 danger=danger.get(action, "none"),  # type: ignore[arg-type]
                                 action=action)
                for key, action, description in pane_actions]
        return out

    def _reopen_corp(self) -> None:
        """CorpActions rebuild hook — reopen the Computer on the Corp subview."""
        self._reopen_tab("corp")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # The Corp panels are button-first, so give them the press before anything else.
        if self.handle_corp_button(event.button.id or ""):
            return
        if event.button.id == "avoid-add":
            self.action_toggle_avoid()
            return
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
        self._follow_focus_to_visible_pane()
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
        """Clicking (or Enter/P on) a Map sector plots a route to it and shows Route."""
        self._plot_map_sector(msg.sector_id)

    def _plot_map_sector(self, sector_id: int) -> None:
        self._route = self._service.route_view(self._pid, sector_id)
        self._engage_target = sector_id
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
                    internal = self._service.resolve_display_id(hop.display_id)
                    table.add_row(str(i), hop.label, note,
                                  key=str(internal if internal is not None else hop.display_id))
        if dto is None:
            summary.update(
                "[dim]Plot a route from the Trade or Codex tab, "
                "or press R to enter a destination.[/]"
            )
            return
        head = f"[b]{dto.origin_display} → {dto.dest_display}[/]   [dim]{dto.summary}[/]"
        avoid_hint = "   ·   [dim][b]V[/] toggle highlighted sector avoid[/]"
        if dto.reachable and dto.affordable:
            summary.update(f"{head}   ·   [green]G Engage[/]{avoid_hint}")
        else:
            summary.update(f"{head}   ·   [red]{dto.reason}[/]{avoid_hint}")

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
        if active == "map":
            sid = self.query_one("#local-map", LocalMapView).selected_sector
            if sid is None:
                self.notify("No sector selected.", timeout=2)
                return
            self._plot_map_sector(sid)
        elif active == "trade":
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
