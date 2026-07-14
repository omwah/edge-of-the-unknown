"""Reusable widgets for the TUI skeleton: starfield, status sidebar, warp list."""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any
from contextlib import contextmanager

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Vertical, Horizontal
from textual.css.query import NoMatches
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Input, Select, Static, TabbedContent, TabPane, Tabs

from rich.style import Style

from edge.core.config import SceneArtConfig
from edge.core.dto import SectorDiscovery
from edge.core.enums import Commodity
from edge.core.planets import pretty_planet_type

from edge.tui import art_adapter
from edge.tui.dummy import LocalMapDTO, NavStripDTO, PortDTO, SectorDTO, ShipDTO, WarpDTO
from edge.server.canvas import BAND_COLOR


class Starfield(Static):
    """A sparse twinkling starfield (UI_MOCKUPS.md §0 / §11 aesthetics).

    Seeded so screenshots are reproducible. `animate=False` (the `--plain` path)
    renders a static field with no twinkle timer.
    """

    DEFAULT_CSS = "Starfield { width: 1fr; height: 1fr; color: $primary; }"
    _CHARS = (".", ".", ".", "·", "*", "+")

    def __init__(self, animate: bool = True, density: float = 0.03, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._animate = animate
        self._density = density
        self._rng = random.Random(7)
        self._stars: dict[tuple[int, int], str] = {}

    def on_mount(self) -> None:
        self._populate()
        if self._animate:
            self.set_interval(0.6, self._twinkle)

    def on_resize(self) -> None:
        self._populate()

    def _populate(self) -> None:
        w, h = self.size.width, self.size.height
        self._stars = {}
        if not w or not h:
            return
        for _ in range(int(w * h * self._density)):
            x, y = self._rng.randrange(w), self._rng.randrange(h)
            self._stars[(x, y)] = self._rng.choice(self._CHARS)
        self.refresh()

    def _twinkle(self) -> None:
        if not self._stars:
            return
        keys = list(self._stars)
        for _ in range(max(1, len(keys) // 8)):
            self._stars[self._rng.choice(keys)] = self._rng.choice((*self._CHARS, " "))
        self.refresh()

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if not w or not h:
            return Text("")
        grid = [[" "] * w for _ in range(h)]
        for (x, y), ch in self._stars.items():
            if 0 <= x < w and 0 <= y < h:
                grid[y][x] = ch
        return Text("\n".join("".join(row) for row in grid), style="dim cyan")


def bar(filled: int, total: int = 10) -> str:
    filled = max(0, min(total, filled))
    return "█" * filled + "░" * (total - filled)


def _scaled_bar(qty: int, capacity: int, width: int = 12) -> str:
    filled = round(qty / capacity * width) if capacity else 0
    return bar(filled, width)


# Map the public commodity *display* names back to the core enum, so a trade
# screen can turn the highlighted row into a Trade command.
NAME_TO_COMMODITY = {
    "Fuel Ore": Commodity.FUEL_ORE,
    "Organics": Commodity.ORGANICS,
    "Equipment": Commodity.EQUIPMENT,
}

# One quick-trade keypress requests this many units. The panel estimate and shared
# port handler consume the same presentation constant so their previews cannot drift.
TRADE_CHUNK = 10


@contextmanager
def preserve_cursor(table: DataTable[Any]) -> Iterator[None]:
    """Keep the highlighted row stable across a clear()+repopulate refresh.

    Textual's ``DataTable.clear()`` resets the cursor to the top, so repeated
    same-row actions (trading one commodity, surveying one site) would force a
    re-select each time. Save the row index, run the refill, then restore it
    clamped to the new row count.
    """
    saved = table.cursor_row
    yield
    if table.row_count:
        table.move_cursor(row=min(max(saved, 0), table.row_count - 1), animate=False)


class TradePanel(Vertical):
    """The commodities trade UI: a live pricing table over the docked port.

    Reusable as the body of the standalone `PortScreen` (a plain commodities
    port) or as the **Commodities** tab of a `StardockScreen` — so docking at a
    port reaches one trade UI regardless of whether the port is a Stardock
    (UI_MOCKUPS.md §2/§5). `show_title` is suppressed inside the Stardock tab,
    where the screen already carries a banner. `refresh_port` re-renders it after
    a trade; `cursor_commodity` is the highlighted row's commodity name.
    """

    DEFAULT_CSS = """
    TradePanel { height: auto; }
    TradePanel #trade-detail { height: auto; min-height: 2; padding: 0 1; }
    """

    def __init__(self, port: PortDTO, *, latinum: int = 0, show_title: bool = True,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._port = port
        self._latinum = latinum
        self._show_title = show_title
        self._compact = False

    def compose(self) -> ComposeResult:
        p = self._port
        if self._show_title:
            yield Static(
                f"[b cyan]TRADEPORT · {p.name} · {p.klass}[/]"
                f"      [dim]Sector {p.display_id}[/]",
                id="port-title",
            )
        yield DataTable(id="commodities", zebra_stripes=True, cursor_type="row")
        yield Static("", id="trade-detail")
        yield Static(self._footer_text(), id="port-footer")

    def on_mount(self) -> None:
        self._configure_table()

    def _is_compact(self) -> bool:
        return getattr(getattr(self.app, "layout_tier", None), "value", "standard") == "compact"

    def _configure_table(self) -> None:
        """Rebuild responsive columns while preserving the logical commodity selection."""
        table = self.query_one("#commodities", DataTable)
        selected = self.cursor_commodity()
        self._compact = self._is_compact()
        table.clear(columns=True)
        if self._compact:
            table.add_columns("Commodity", "Port", "Action")
        else:
            table.add_columns(
                "Commodity", "Port", "Stock / capacity", "Unit price", "Aboard", "Action")
        self._fill_rows(selected)

    def _fill_rows(self, selected: str | None = None) -> None:
        table = self.query_one("#commodities", DataTable)
        with preserve_cursor(table):
            table.clear()
            for c in self._port.commodities:
                posture = "Buys" if c.mode == "BUY" else "Sells"
                action = "You sell" if c.mode == "BUY" else "You buy"
                if self._compact:
                    table.add_row(c.name, posture, action, key=c.name)
                else:
                    table.add_row(
                        c.name, posture, f"{c.stock:,} / {c.capacity:,}",
                        f"{c.price:,} {c.trend}", f"{c.player_qty:,}", action, key=c.name)
        if selected is not None:
            row = next((i for i, c in enumerate(self._port.commodities) if c.name == selected), 0)
            table.move_cursor(row=row, animate=False)
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        detail = self.query_one("#trade-detail", Static)
        line = next((c for c in self._port.commodities
                     if c.name == self.cursor_commodity()), None)
        if line is None:
            detail.update("[dim]No commodity selected.[/]")
            return
        free = max(0, self._port.holds_total - self._port.holds_used)
        if line.mode == "SELL":
            qty = min(TRADE_CHUNK, line.stock, free,
                      self._latinum // max(1, line.price))
            impact = f"holds {self._port.holds_used} → {self._port.holds_used + qty}"
            limit = "hold/latinum limited" if qty < TRADE_CHUNK else "within limits"
        else:
            purse_qty = (self._port.purse // max(1, line.price)
                         if self._port.purse_enabled else TRADE_CHUNK)
            qty = min(TRADE_CHUNK, line.player_qty,
                      max(0, line.capacity - line.stock), purse_qty)
            impact = f"holds {self._port.holds_used} → {self._port.holds_used - qty}"
            if not self._port.purse_enabled:
                limit = "port purse not limiting"
            elif purse_qty < min(TRADE_CHUNK, line.player_qty):
                limit = f"purse caps payment ({self._port.purse:,} available)"
            else:
                limit = f"purse {self._port.purse:,} · within limits"
        verb = "Port sells / you buy" if line.mode == "SELL" else "Port buys / you sell"
        detail.update(
            f"[b]{verb}[/]  ·  stock [b]{line.stock:,}/{line.capacity:,}[/]  ·  "
            f"unit [yellow]{line.price:,}[/]  ·  est. {qty} units = "
            f"[yellow]{qty * line.price:,}[/]  ·  {impact}  ·  [dim]{limit}[/]"
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id == "commodities":
            self._refresh_detail()

    def on_resize(self) -> None:
        compact = self._is_compact()
        if self.is_mounted and compact != self._compact:
            self._configure_table()

    def _footer_text(self) -> str:
        return (
            "[dim]^ port buys from you (you SELL)   v port sells to you (you BUY)[/]\n"
            f"Latinum [yellow]{self._latinum:,}[/]   ·   [b]T[/]rade highlighted   ·   "
            "[b]G[/] Haggle   ·   [b]Esc[/] leave dock"
        )

    def refresh_port(self, port: PortDTO, latinum: int) -> None:
        selected = self.cursor_commodity()
        self._port = port
        self._latinum = latinum
        self._fill_rows(selected)
        self.query_one("#port-footer", Static).update(self._footer_text())

    def cursor_commodity(self) -> str | None:
        row = self.query_one("#commodities", DataTable).cursor_row
        if 0 <= row < len(self._port.commodities):
            return self._port.commodities[row].name
        return None


def first_focusable(node: Widget) -> Widget | None:
    """The primary focusable control of `node` (WP-PR2-01: jump-to-tab focus target).

    Used to drop keyboard focus straight onto a tab's primary control (its table,
    list, or form field) after a tab accelerator or Enter, so reaching a control is
    one step, not two.

    A widget may nominate itself with the `focus-first` class, which wins outright.
    Otherwise the first focusable widget in DOM order is taken — **except a text
    `Input`**, which is never chosen automatically. A focused text field takes every
    letter key as typing: the tab's action letters stop firing *and* Textual drops them
    from the footer, so auto-focusing a filter box or an amount field silently disarms
    the screen — it even swallows the accelerators that would let you leave the tab.
    Nominate the field with `focus-first` if a tab really should open ready to type."""
    for query in (".focus-first", "*"):
        for widget in node.query(query):
            if widget.focusable and not (query == "*" and isinstance(widget, Input)):
                return widget
    return None


def focus_content(node: Widget) -> None:
    """Put keyboard focus on `node`'s primary control (see `first_focusable`).

    When nothing inside can take focus — an `ActionPane` of pure text, like the
    Stardock's Bank — the pane takes focus itself. It has to: a pane's keys are live only
    while focus is inside it, so a pane that cannot hold focus could never fire its own
    verbs (Deposit / Withdraw would be advertised in the footer but be dead keys).
    """
    target = first_focusable(node)
    if target is None:
        node.can_focus = True
        target = node
    target.focus()


def accel_title(label: str, letter: str | None) -> str:
    """A tab title (Textual markup) with its accelerator letter emphasised (WP-PR2-01).

    The first case-insensitive occurrence of `letter` is bold-underlined so the
    hotkey reads from the title itself — legible without colour (monochrome-safe),
    which is why the tab-focus keys stay out of the crowded footer. Returns a markup
    string because a `TabPane` title must be markup/Content, not a Rich `Text`."""
    if letter:
        idx = label.lower().find(letter.lower())
        if idx >= 0:
            return f"{label[:idx]}[bold underline]{label[idx]}[/]{label[idx + 1:]}"
    return label


class ActionPane(TabPane):
    """A tab pane that owns the action keys belonging to its tab (PT-32).

    Textual builds the binding chain outward from the focused widget, so bindings
    declared here are live — and advertised in the footer — only while focus rests
    inside this pane. That is the whole point: a tabbed screen keeps *no* global
    binding for a per-tab verb, so the footer can never advertise an action that
    would misfire on the tab you are looking at, and two tabs may reuse one letter
    for different verbs without a `check_action` maze.

    `actions` are `(key, action, description)` triples shown in the footer; `hidden` has
    the same shape but stays off it — that is where a pane's *navigation* keys go (a
    category pane's sub-tab numbers), which would otherwise crowd the verbs out of the
    footer. Each is dispatched into the `screen.` namespace, so handlers stay on the
    owning screen while the *keys* belong to the tab.
    """

    def __init__(self, title: str, *,
                 actions: Sequence[tuple[str, str, str]] = (),
                 hidden: Sequence[tuple[str, str, str]] = (), **kwargs: Any) -> None:
        super().__init__(title, **kwargs)
        for key, action, description in actions:
            self._bindings.bind(key, f"screen.{action}", description)
        for key, action, description in hidden:
            self._bindings.bind(key, f"screen.{action}", description, show=False)


class ServiceHub(Vertical):
    """Shared responsive service navigation for Stardock and orbital bases.

    Standard/wide layouts expose Textual tabs. Compact replaces their overflowing tab
    rail with a keyboard/mouse Select; unavailable entries remain selectable and explain
    the prerequisite in their pane instead of disappearing. Hosts still issue commands
    through their reducers, which remain the eligibility authority.

    Hosts may pass `accelerators` (entry_id → letter). Each is emphasised in the tab
    title; the host binds the letter to `activate_and_focus`, which switches to the tab
    and focuses its primary content in one step (WP-PR2-01). Enter while the tab rail is
    focused does the same for the active tab.

    PT-32 — **a tab owns its keys.** Hosts pass `actions` (entry_id → `(key, action,
    description)` triples), which are bound onto that entry's `ActionPane` rather than
    onto the screen, so each key is live (and in the footer) only while focus rests
    inside its tab. The hub keeps focus inside the visible pane for that to hold: it
    lands focus on the initial tab's content at mount, follows the tab on every switch,
    and blurs *before* switching — Textual re-activates whichever pane holds focus
    (`TabbedContent._on_tab_pane_focused`), so focus left behind in the old pane would
    silently drag the tab back.
    """

    BINDINGS = [Binding("enter", "focus_active_content", "Enter tab", show=False)]

    DEFAULT_CSS = """
    ServiceHub { height: 1fr; }
    ServiceHub #service-selector { display: none; width: 1fr; margin: 0 1; }
    .compact ServiceHub #service-selector, ServiceHub.compact #service-selector { display: block; }
    .compact ServiceHub Tabs, ServiceHub.compact Tabs { display: none; }
    ServiceHub TabPane { padding: 1 2; }
    ServiceHub .service-unavailable { padding: 1 2; color: $text-muted; }
    """

    def __init__(
        self,
        entries: Sequence[tuple[str, str, Widget, str | None]],
        *,
        initial: str,
        accelerators: Mapping[str, str] | None = None,
        actions: Mapping[str, Sequence[tuple[str, str, str]]] | None = None,
        hidden: Mapping[str, Sequence[tuple[str, str, str]]] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._entries = list(entries)
        ids = {entry_id for _, entry_id, _, _ in entries}
        self._initial = initial if initial in ids else entries[0][1]
        self._accel = dict(accelerators or {})
        self._actions = dict(actions or {})
        self._hidden = dict(hidden or {})  # same shape, kept off the footer
        self._syncing = False

    def compose(self) -> ComposeResult:
        options = [
            (f"{label}{' — unavailable' if reason else ''}", entry_id)
            for label, entry_id, _, reason in self._entries
        ]
        yield Select[str](options, value=self._initial, allow_blank=False,
                          id="service-selector")
        with TabbedContent(initial=self._initial):
            for label, entry_id, content, reason in self._entries:
                # An unavailable entry explains itself instead of acting, so it keeps
                # none of its keys — the footer must not offer a verb that cannot fire.
                unavailable = reason is not None
                actions = () if unavailable else self._actions.get(entry_id, ())
                hidden = () if unavailable else self._hidden.get(entry_id, ())
                with ActionPane(accel_title(label, self._accel.get(entry_id)),
                                id=entry_id, actions=actions, hidden=hidden):
                    if reason is not None:
                        yield Static(
                            f"[b]{label} unavailable[/]\n\n{reason}",
                            classes="service-unavailable",
                        )
                    else:
                        yield content

    def activate_and_focus(self, entry_id: str) -> None:
        """Switch to `entry_id` and focus its primary content (tab accelerator target)."""
        try:
            self._blur_stale_pane()
            self.query_one(TabbedContent).active = entry_id
        except NoMatches:
            return
        self.call_after_refresh(self._focus_content, entry_id)

    def _blur_stale_pane(self) -> None:
        """Drop focus before a programmatic tab switch (see the class docstring)."""
        screen = self.screen
        if screen.focused is not None and not isinstance(screen.focused, Tabs):
            screen.set_focus(None)

    def _follow_focus_to_visible_pane(self) -> None:
        """Never strand focus in a tab that is no longer showing — its keys would stay
        in the footer. Focus resting on the tab rail is left alone (that is a player
        arrowing along the tabs; stealing it would make the rail unusable)."""
        focused = self.screen.focused
        if focused is None or isinstance(focused, Tabs):
            return
        try:
            active = self.query_one(TabbedContent).active
            pane = self.query_one(f"#{active}", TabPane)
        except NoMatches:
            return
        if pane not in focused.ancestors_with_self:
            self.screen.set_focus(None)
            self.call_after_refresh(self._focus_content, active)

    def _focus_content(self, entry_id: str) -> None:
        try:
            pane = self.query_one(f"#{entry_id}", TabPane)
        except NoMatches:
            return
        focus_content(pane)

    def action_focus_active_content(self) -> None:
        """Enter on the tab rail drops focus onto the active tab's primary content."""
        try:
            active = self.query_one(TabbedContent).active
        except NoMatches:
            return
        if active:
            self._focus_content(active)

    def on_mount(self) -> None:
        self._sync_tier_class()
        # Open with focus already in the visible tab's content, so the footer advertises
        # that tab's verbs from the first frame (PT-32).
        self.call_after_refresh(self._focus_content, self._initial)

    def on_resize(self) -> None:
        self._sync_tier_class()

    def _sync_tier_class(self) -> None:
        self.set_class(
            getattr(getattr(self.app, "layout_tier", None), "value", "standard") == "compact",
            "compact",
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "service-selector" or self._syncing:
            return
        value = event.value
        if isinstance(value, str):
            self.activate_and_focus(value)

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        self._follow_focus_to_visible_pane()
        selector = self.query_one("#service-selector", Select)
        if selector.value == event.pane.id:
            return
        self._syncing = True
        selector.value = event.pane.id
        self._syncing = False


_CODE_STYLE = {"S": "b magenta", "P": "magenta", "@": "green"}


def _code_markup(codes: list[str]) -> str:
    """Render content tokens (S/P Stardock-port, @ planet) colour-coded by type."""
    return " ".join(f"[{_CODE_STYLE.get(c, 'white')}]{c}[/]" for c in codes)


def warp_legend_markup(core_anchor_side: str) -> str:
    """The warp colour and navigation guide — shown in the Help modal."""
    anchor_left = core_anchor_side != "right"
    if anchor_left:
        core_line = "• [bold cyan]◄ Core[/]: Points towards Core Space (Sectors 1-10) and its current governor."
        void_line = "• [bold blue]Void ►[/]: Points towards the outer boundary of the universe, pointing away from the Core."
        directions = f"{core_line}\n{void_line}"
    else:
        void_line = "• [bold blue]◄ Void[/]: Points towards the outer boundary of the universe, pointing away from the Core."
        core_line = "• [bold cyan]Core ►[/]: Points towards Core Space (Sectors 1-10) and its current governor."
        directions = f"{void_line}\n{core_line}"

    return (
        "[bold cyan]Navigation (Nav Rose)[/]\n"
        "The Nav Rose at the bottom of the main screen is centered on you ( [reverse bold cyan]@[/] ).\n"
        "• [bold]Mouse & Keyboard[/]: Click any warp label to travel directly, or use the\n"
        "  [bold]Arrow keys[/] to select a warp and press [bold]Enter[/] / [bold]Space[/] to travel.\n"
        f"{directions}\n\n"
        "[bold cyan]Warp Symbols[/]\n"
        "• [b]<<[/] Coreward (closer)   • [b]>>[/] Outward (deeper)   "
        "• [b]--[/] Cross-band (level)\n"
        "• [b]↩[/] Backtrack / the sector just left   • [b]⇢[/] One-way exit\n"
        "• [b yellow]⊘[/] Avoided by route plotting   • [b yellow]⚠[/] Known hazard\n"
        "• [dim]?[/] Unexplored destination (name and contents remain hidden)\n\n"
        "[bold cyan]Warp Color (Distance Bands)[/]\n"
        "Colors represent the distance band of the target sector from the Core:\n"
        "• [cyan]■[/] Hub          • [green]■[/] Frontier\n"
        "• [magenta]■[/] Deep         • [blue]■[/] Void\n"
        "• [dim]■[/] Uncharted (unexplored)\n\n"
        "[bold cyan]Sector Codes[/]\n"
        "Discovered entities are shown as trailing symbols on warp labels:\n"
        "• [green]@[/]   Planet       • [magenta]S[/]   Stardock       • [magenta]P[/]   Trade Port"
    )


class AnomalyRow(Static):
    """A clickable discovery row in the sidebar 'Anomalies' list (§7).

    An unlogged find can be scanned/collected; clicking reuses the existing
    `ClickableEntry.Picked("discovery", id)` the scene used, so the GameScreen
    handler is untouched. A logged find is a plain, non-clickable line.
    `detail` (the wide tier, WP-UI12) appends the find's kind to logged rows.
    """

    DEFAULT_CSS = """
    AnomalyRow { height: 1; }
    AnomalyRow.scan:hover { background: $boost; text-style: bold; }
    """

    def __init__(self, discovery: SectorDiscovery, detail: bool = False,
                 **kwargs: Any) -> None:
        super().__init__(self._markup(discovery, detail), **kwargs)
        self._discovery_id = discovery.discovery_id
        self._scan = not discovery.collected
        if self._scan:
            self.add_class("scan")

    @staticmethod
    def _markup(d: SectorDiscovery, detail: bool = False) -> str:
        # The find's identity stays hidden until scanned — pre-scan it reads generic.
        if d.collected:
            kind = f" · {d.kind}" if detail else ""
            return f"[cyan]✦[/] {d.label} [dim]— logged{kind}[/]"
        if d.kind == "wreck":
            return "[yellow]⚙[/] Wreckage [dim](Salvage)[/]"
        return "[cyan]✦[/] Anomaly detected [dim](Scan)[/]"

    def on_click(self) -> None:
        if self._scan:
            self.post_message(ClickableEntry.Picked("discovery", self._discovery_id))


def force_lines(force: object) -> list[str]:
    """Hazard captions for deployed forces here (§10 — classic-TW fog pre-applied)."""
    lines: list[str] = []
    if force is None:
        return lines
    fighters = getattr(force, "fighters", 0)
    if fighters > 0:
        toll = f", toll {force.toll}" if force.mode == "toll" else ""  # type: ignore[attr-defined]
        who = ("[green]yours[/]" if getattr(force, "yours", False)
               else f"[red]{force.owner}[/]")  # type: ignore[attr-defined]
        lines.append(f"[red]×[/] {fighters} fighters ({force.mode}{toll}) — {who}")  # type: ignore[attr-defined]
    armid = getattr(force, "armid_mines", 0)
    limpet = getattr(force, "limpet_mines", 0)
    if armid or limpet:
        kinds = ([f"{armid} armid"] if armid else []) + ([f"{limpet} limpet"] if limpet else [])
        lines.append(f"[red]✺[/] {' + '.join(kinds)} mines — [green]yours[/]")
    return lines


class StatusSidebar(Vertical):
    """Right-hand status readout: ship stats + the sector's Anomalies (UI_MOCKUPS.md §1).

    A container (not a single Static) so each anomaly row is an individually
    clickable scan affordance. The warp quick-reference that used to live here is
    folded into the sector warp grid; the warp legend moved to the Help modal.
    On the wide tier (WP-UI12) `detail=True` enriches anomaly rows and an
    `objectives` tuple appends the Captain's-objectives checklist.
    """

    DEFAULT_CSS = """
    StatusSidebar { width: 33; padding: 0 1; border-left: solid $primary; }
    StatusSidebar > Static { height: auto; }
    """

    def __init__(self, ship: ShipDTO, discoveries: list[SectorDiscovery],
                 width: int = 33, presence: list[str] | None = None,
                 detail: bool = False, objectives: tuple[str, ...] | None = None,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ship = ship
        self._discoveries = discoveries
        self._width = width
        self._presence = presence or []
        self._detail = detail
        self._objectives = objectives

    def on_mount(self) -> None:
        self.styles.width = self._width

    def compose(self) -> ComposeResult:
        yield Static(self._stats_markup())
        if self._presence:  # starbases + known forces here (§4.2/§10, fog-applied)
            yield Static("[b yellow]Presence[/]")
            for line in self._presence:
                yield Static(line)
        yield Static("[b yellow]Anomalies[/]")
        if self._discoveries:
            for discovery in self._discoveries:
                yield AnomalyRow(discovery, detail=self._detail)
        else:
            yield Static("[#8a8a8a]-----[/]")
        if self._objectives is not None:  # wide tier: the checklist in full (WP-UI12)
            from edge.tui.onboarding import OBJECTIVES
            yield Static("[b yellow]Objectives[/]")
            for obj_id, label, hint in OBJECTIVES:
                if obj_id in self._objectives:
                    yield Static(f"[green]✓ {label}[/]")
                else:
                    yield Static(f"[dim]○ {label} — {hint}[/]")

    def _stats_markup(self) -> str:
        s = self._ship
        # Divider spans the panel's content width (width minus the left border + padding),
        # so it tracks the configured sidebar width instead of a hardcoded 30.
        rule = "[dim]" + "─" * max(8, self._width - 3) + "[/]"
        lines: list[str] = [
            f"[b cyan]{s.name}[/]  [dim]({s.klass})[/]",
            rule,
        ]
        for a in s.aspects:
            lines.append(f"{a.label:<8}[yellow]{bar(a.filled)}[/]  {a.note}")
        lines += [
            f"[green]subsystems: {s.integrity}[/]",
            rule,
            f"Gun [green]{s.gun}[/]  Missiles x{s.missiles}",
            f"Kits x{s.kits}",
            rule,
            f"Holds {s.holds_used}/{s.holds_total}",
        ]
        for h in s.holds:
            lines.append(f" {h.label:<5}[yellow]{_scaled_bar(h.qty, h.capacity)}[/] {h.qty:>3}")
        lines += [
            f"Colonists {s.colonists:,}/{s.colonist_capacity:,}",
            f"Latinum  [b yellow]{s.latinum:,}[/] slips",
            rule,
        ]
        return "\n".join(lines)


class _TickerDivider(Static):
    """The ticker's top divider — a horizontal rule with a right-aligned expand/collapse
    toggle (▲ to expand up to 5 lines, ▼ to shrink back to one). Clicking it toggles."""

    DEFAULT_CSS = "_TickerDivider { height: 1; color: $primary; }"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._expanded = False

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.refresh()

    def render(self) -> Text:
        width = max(1, self.size.width)
        glyph = "∨∨" if self._expanded else "∧∧"
        rule = "─" * (width - 3) + glyph + "─"
        return Text(rule, style="dim")

    def on_click(self, event: events.Click) -> None:
        event.stop()
        self.post_message(Ticker.Toggle())


class Ticker(Vertical):
    """The bottom event ticker (UI_MOCKUPS.md §1).

    Collapsed it shows only the most recent log line under a divider; clicking the
    divider's ▲ indicator expands it to overlay the screen with the last five lines
    (▼ shrinks it back). It rides a higher layer when expanded, so growing upward
    draws *over* the sector view rather than reflowing it.
    """

    class Toggle(Message):
        pass

    DEFAULT_CSS = """
    Ticker { height: 2; background: $surface; padding: 0 1; }
    /* Expanded, it rides the overlay layer docked to the bottom, so it grows upward
       *over* the sector view instead of reflowing it (the screen declares the layer). */
    Ticker.expanded { height: 6; layer: overlay; dock: bottom; }
    Ticker #ticker-body { height: 1fr; color: $text; }
    """

    def __init__(self, lines: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._lines = lines
        self._expanded = False

    def compose(self) -> ComposeResult:
        yield _TickerDivider(id="ticker-divider")
        yield Static(self._body_text(), id="ticker-body")

    def _body_text(self) -> str:
        count = 5 if self._expanded else 1
        return "\n".join(self._lines[-count:])

    def on_ticker_toggle(self, msg: Ticker.Toggle) -> None:
        msg.stop()
        self._expanded = not self._expanded
        self.set_class(self._expanded, "expanded")
        self.query_one("#ticker-divider", _TickerDivider).set_expanded(self._expanded)
        self.query_one("#ticker-body", Static).update(self._body_text())


class SectorScene(Static):
    """The whole sector scene composited into one grid (UI_MOCKUPS.md §1).

    A starfield base with the header, planet/port (port vertically centred against
    the taller planet), ship sprites, and the discoveries list stamped over it. It
    is one Static because a terminal cell holds a single glyph and Textual does not
    blend overlapping widgets/layers — so the only way to show the starfield
    *behind* the sprites and text is to composite them together here. Sprites'
    negative-space cells are left transparent, so stars show through their gaps.

    Planet / port / ship / unlogged-discovery click targets are recorded as
    ``_hotspots`` and routed as ``ClickableEntry.Picked`` (mirroring the keys).
    """

    DEFAULT_CSS = """
    SectorScene { width: 1fr; height: 1fr; background: transparent; }
    """

    _ORBIT_MARGIN = 3  # blank rows between the planet/port band and the ships row

    def __init__(self, sector: SectorDTO, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sector = sector
        # (x0, y0, x1, y1, dest, ref) recorded each render; on_click maps a hit to
        # the same ClickableEntry.Picked the keyboard/text affordances post.
        self._hotspots: list[tuple[int, int, int, int, str, int | str | None]] = []

    def on_resize(self) -> None:
        self.refresh()

    def _scene_cfg(self) -> SceneArtConfig:
        return getattr(self.app, "scene_art", None) or SceneArtConfig()

    # --- grid helpers --------------------------------------------------------

    def _starfield(self, w: int, h: int) -> list[list[tuple[str, Style | None]]]:
        """Base grid from the procedural `edge.art` starfield (seeded per sector)."""
        cells = art_adapter.text_to_cells(art_adapter.sprite(
            "starfield", "standard", seed=self._sector.sector_id ^ 0x5EED, width=w, height=h))
        grid: list[list[tuple[str, Style | None]]] = [[(" ", None)] * w for _ in range(h)]
        for y in range(min(h, len(cells))):
            for x in range(min(w, len(cells[y]))):
                ch, style = cells[y][x]
                if ch != " ":
                    grid[y][x] = (ch, style)
        return grid

    @staticmethod
    def _paint(grid: list[list[tuple[str, Style | None]]],
               rows: list[list[tuple[str, Style | None]]], top: int, left: int) -> None:
        h, w = len(grid), len(grid[0])
        for r, row in enumerate(rows):
            y = top + r
            if not 0 <= y < h:
                continue
            for c, (ch, style) in enumerate(row):
                x = left + c
                if ch != " " and 0 <= x < w:  # spaces stay transparent -> stars show
                    grid[y][x] = (ch, style)

    def _stamp_line(self, grid: list[list[tuple[str, Style | None]]], markup: str,
                    row: int, x0: int, span: int) -> None:
        """Stamp one markup line centred within the horizontal span [x0, x0+span).

        Unlike sprites, a text line clears the stars within its own extent (so a
        star can't bleed through a space *inside* a word); stars still show in the
        centring margins to either side.
        """
        line = art_adapter.text_to_cells(Text.from_markup(markup))[0:1]
        cells = line[0] if line else []
        if not (0 <= row < len(grid)):
            return
        w = len(grid[0])
        left = x0 + max(0, (span - len(cells)) // 2)
        for c, (ch, style) in enumerate(cells):
            x = left + c
            if 0 <= x < w:
                grid[row][x] = (ch, style)  # blanks included -> overwrite stars

    def _sprite_cells(self, entity: str, subtype: str, *, seed: int, sw: int, sh: int,
                      facing: str = "right",
                      archetype_id: str | None = None,
                      treatment: str = "") -> list[list[tuple[str, Style | None]]]:
        art = art_adapter.sprite(
            entity, subtype, seed=seed, width=sw, height=sh, facing=facing,
            archetype_id=archetype_id)
        if treatment == "derelict":
            art.stylize("dim")
        elif treatment == "hostile":
            art.stylize("on dark_red")
        return art_adapter.text_to_cells(art)

    # --- render --------------------------------------------------------------

    def render(self) -> Text:
        self._hotspots = []
        w, h = self.size.width, self.size.height
        if w < 8 or h < 6:
            return Text("")
        sec = self._sector
        cfg = self._scene_cfg()
        grid = self._starfield(w, h)
        half = w // 2
        row = 0

        # Header — sector + band, flavor, beacon; centred across the full width.
        title = f"[{sec.display_id}] {sec.region}" + (f" ({sec.band})" if sec.band else "")
        self._stamp_line(grid, f"[b cyan]{title}[/]", row, 0, w)
        row += 1
        self._stamp_line(grid, f"[i #8a8a8a]░▒▓ {sec.flavor} ▓▒░[/]", row, 0, w)
        row += 1
        if sec.beacon:
            self._stamp_line(grid, f"[yellow]![/] {sec.beacon}", row, 0, w)
            row += 1
        row += 1  # blank

        # Orbit band — planet (left half) | port (right half). Sizes from config,
        # clamped to the space left below `row` for the margin + ships + discoveries.
        reserved = self._ORBIT_MARGIN + (cfg.ship.max_height + 1) + 3
        ph = max(cfg.planet.min_height,
                 min(cfg.planet.max_height, (half - 2) // 2, h - row - reserved))
        pw = ph * 2  # width locked to 2*height so the disc reads round
        portw = max(cfg.port.min_width, min(cfg.port.max_width, half - 2))
        porth = max(cfg.port.min_height, min(cfg.port.max_height, ph))
        band_h = max(ph, porth)
        lcx, rcx = half // 2, half + half // 2  # column centres
        # A sector with a visible discovery has no planet (bigbang keeps space finds
        # off planet sectors), so the find takes the planet slot. A wormhole is the
        # preferred primary — it's the navigable one. Centre it across the whole view
        # when there's no port; otherwise keep it in the left (planet) half.
        disc = None
        if sec.discoveries and not sec.planets:
            disc = next((d for d in sec.discoveries if d.kind == "wormhole"), sec.discoveries[0])
        disc_centered = disc is not None and not sec.ports
        # Planet (or placeholder), top-aligned in the band.
        if sec.planets:
            planet = sec.planets[0]
            sub = art_adapter.planet_subtype(planet.ptype)
            # Seed off the planet's own id (not the sector's) so this sprite matches the
            # PlanetScreen orbit view, which seeds with planet_id — same planet, same art.
            self._paint(grid, self._sprite_cells("planet", sub, seed=planet.planet_id, sw=pw, sh=ph),
                        row, lcx - pw // 2)
        elif disc is not None:
            dleft = (w // 2 - pw // 2) if disc_centered else (lcx - pw // 2)
            self._paint(grid, self._sprite_cells("discovery", disc.kind, seed=sec.sector_id, sw=pw, sh=ph),
                        row, dleft)

        # Port (or placeholder), vertically centred against the taller planet. The
        # controlling species' palette (`archetype_id`) styles the port sprite. A
        # starbase **takes the place of a port** (§4.2, WP80): where a base orbits, the
        # base sprite holds the slot and its market is entered through the base view.
        bases = list(getattr(sec, "starbases", ()) or ())
        base_in_orbit = bool(bases)
        if base_in_orbit:
            self._paint(grid, self._sprite_cells("port", "starbase",
                                                 seed=bases[0].starbase_id,
                                                 sw=portw, sh=porth,
                                                 archetype_id=bases[0].archetype_id,
                                                 treatment=bases[0].condition),
                        row + (band_h - porth) // 2, rcx - portw // 2)
        elif sec.ports:
            port = sec.ports[0]
            sub = art_adapter.port_subtype(port.klass)
            archetype = port.archetype_id
            self._paint(grid, self._sprite_cells("port", sub, seed=sec.sector_id, sw=portw,
                                                 sh=porth, archetype_id=archetype),
                        row + (band_h - porth) // 2, rcx - portw // 2)

        name_row = row + band_h
        if sec.planets:
            self._stamp_line(grid, f"[b yellow]{sec.planets[0].name}[/]", name_row, 0, half)
            self._hotspots.append((0, row, half, name_row + 1, "planet", None))
        elif disc is not None:
            # No caption until scanned — a sensor sweep (sidebar/Z) reveals the identity.
            span = w if disc_centered else half
            if disc.collected or disc.kind == "wreck":
                self._stamp_line(grid, f"[b cyan]{disc.label}[/]", name_row, 0, span)
            if disc.kind == "wormhole" and disc.warp_to is not None:
                dest, ref = "wormhole", disc.warp_to  # click warps to the far side
            else:
                dest, ref = "discovery", disc.discovery_id  # click scans/salvages
            self._hotspots.append((0, row, span, name_row + 1, dest, ref))
        if base_in_orbit:
            b = bases[0]
            status = "[green]operational[/]" if b.operational else "[yellow]derelict[/]"
            market = f" · [yellow]{sec.ports[0].name}[/]" if sec.ports else ""
            self._stamp_line(grid, f"[b cyan]{b.name}[/] {status}{market} [dim]· {b.owner}[/]",
                             name_row, half, half)
            # Click-through to the unified base view (§4.2, WP80) — station, market,
            # services, assault/repair/claim all live there.
            self._hotspots.append((half, row, w, name_row + 1, "starbase", b.starbase_id))
        elif sec.ports:
            self._stamp_line(grid, f"[b yellow]{sec.ports[0].name}[/]", name_row, half, half)
            self._hotspots.append((half, row, w, name_row + 1, "port", None))
        row = name_row + 1 + self._ORBIT_MARGIN

        # Ships — up to N sprites side by side (no heading), names beneath. The 2nd
        # of a pair may face left so the two face inward (deterministic per sector).
        shown = sec.ships[:cfg.max_ships_shown]
        if shown:
            n = len(shown)
            sw = max(cfg.ship.min_width, min(cfg.ship.max_width, (w - 2) // max(1, n) - 2))
            # Ship height isn't space-clamped (the layout reserves max_height), so it
            # sits at max_height -- but never below the configured min.
            sh = max(cfg.ship.min_height, cfg.ship.max_height)
            col_w = w / n  # one equal-width column per ship
            frng = random.Random(sec.sector_id)
            for i, vessel in enumerate(shown):
                entity, sub = art_adapter.ship_entity(vessel.role)
                facing = "left" if (i == 1 and frng.random() < cfg.ship_face_inward_chance) else "right"
                # Centre each ship within its own column, so a pair sits at the middle of
                # its half rather than clustering against the other in the centre.
                left = max(0, int(i * col_w + (col_w - sw) / 2))
                self._paint(grid, self._sprite_cells(entity, sub, seed=sec.sector_id * 16 + i,
                                                     sw=sw, sh=sh, facing=facing,
                                                     archetype_id=vessel.archetype_id), row, left)
                cid = vessel.contact_id
                pid = getattr(vessel, "player_id", None)  # another player's ship (WP70)
                tag = (" [dim](Hail)[/]" if cid is not None
                       else " [dim](Engage)[/]" if pid is not None else "")
                self._stamp_line(grid, f"{vessel.name}{tag}", row + sh, left, sw)
                if cid is not None:
                    self._hotspots.append((left, row, left + sw, row + sh + 1, "contact", cid))
                elif pid is not None:
                    self._hotspots.append((left, row, left + sw, row + sh + 1, "player", pid))
            row += sh + 1
        # Overflow ships beyond the sprite cap stay hailable as centred text rows.
        for i in range(cfg.max_ships_shown, len(sec.ships)):
            vessel = sec.ships[i]
            cid = vessel.contact_id
            pid = getattr(vessel, "player_id", None)
            tag = (" [dim](Hail)[/]" if cid is not None
                   else " [dim](Engage)[/]" if pid is not None else "")
            self._stamp_line(grid, f"[white]>[/] {vessel.name}{tag}", row, 0, w)
            if cid is not None:
                self._hotspots.append((0, row, w, row + 1, "contact", cid))
            elif pid is not None:
                self._hotspots.append((0, row, w, row + 1, "player", pid))
            row += 1

        # The roaming Entity's presence hint (§7, WP35): always shown when it is here, but
        # hailable only once sensors resolve it (Legendary gate). Fog-safe — never named.
        anomaly = getattr(sec, "anomaly", None)
        if anomaly is not None:
            if anomaly.contactable:
                self._stamp_line(grid, f"[b gold1]✶ {anomaly.label}[/] [dim](Hail)[/]", row, 0, w)
                self._hotspots.append((0, row, w, row + 1, "contact", anomaly.contact_id))
            else:
                self._stamp_line(
                    grid, f"[gold3]✶ {anomaly.label}[/] [dim](beyond sensor resolution)[/]",
                    row, 0, w)
            row += 1

        # Presence band (§10/§4.2 — WP interview): deployed forces and a port-crowded
        # starbase, as small sprites with captions (caption-only on a short terminal).
        # The projection already applies classic-TW fog: fighters are public, foreign
        # mines were zeroed, a mines-only foreign force never arrives here at all.
        force = getattr(sec, "force", None)
        entries: list[tuple[str, str, int, str, str, int | str | None]] = []
        if force is not None and force.fighters > 0:
            toll = f", toll {force.toll}" if force.mode == "toll" else ""
            who = "[green]yours[/]" if force.yours else f"[red]{force.owner}[/]"
            entries.append(("ship", "fighter", sec.sector_id * 31,
                            f"[b]{force.fighters} fighters[/] [dim]({force.mode}{toll})[/] · {who}",
                            "", None))
        if force is not None and (force.armid_mines or force.limpet_mines):
            kinds = []
            if force.armid_mines:
                kinds.append(f"{force.armid_mines} armid")
            if force.limpet_mines:
                kinds.append(f"{force.limpet_mines} limpet")
            entries.append(("__mines__", "", sec.sector_id,
                            f"[b]{' + '.join(kinds)} mines[/] · [green]yours[/]",
                            "", None))
        if entries:
            sprite_h = 4 if h - row >= 6 else 0  # caption-only on a short terminal
            col_w = w / len(entries)
            for i, (entity, sub, seed, caption, fdest, fref) in enumerate(entries):
                left = max(0, int(i * col_w))
                span = max(8, int(col_w))
                if sprite_h:
                    if entity == "__mines__":
                        cells = art_adapter.text_to_cells(Text.from_markup(
                            "[red] ✺     ✺ [/]\n[red]    ✺    [/]\n[red] ✺     ✺ [/]"))
                    else:
                        sw = min(14, span - 2)
                        cells = self._sprite_cells(entity, sub, seed=int(seed),
                                                   sw=sw, sh=sprite_h)
                    cw = max((len(r) for r in cells), default=0)
                    self._paint(grid, cells, row, left + max(0, (span - cw) // 2))
                self._stamp_line(grid, caption, row + sprite_h, left, span)
                if fdest:
                    self._hotspots.append((left, row, left + span,
                                           row + sprite_h + 1, fdest, fref))
            row += sprite_h + 1

        # (Discoveries are listed in the sidebar's "Anomalies" panel, not the scene.)

        out = Text()
        for y in range(h):
            for ch, style in grid[y]:
                out.append(ch, style=style)
            if y < h - 1:
                out.append("\n")
        return out

    def on_click(self, event: events.Click) -> None:
        x, y = int(event.x), int(event.y)
        for x0, y0, x1, y1, dest, ref in self._hotspots:
            if x0 <= x < x1 and y0 <= y < y1:
                event.stop()
                self.post_message(ClickableEntry.Picked(dest, ref))
                return


def _nearest_node(hits: list, idx: int, dx: int, dy: int) -> int | None:  # type: ignore[type-arg]
    """Index of the node to move to from `hits[idx]` in the pressed direction, or None.

    Navigation follows the on-screen layout, not insertion order. The map lays nodes out in
    **gravity columns** (each column left-aligned to a fixed x), so the two axes are treated
    differently — matching how the eye reads the graph:

    * **Left / Right** steps to the node in the **nearest adjacent column** on that side,
      picking the one **closest by row**. A candidate whose cell *horizontally overlaps* the
      current node is in the *same* column (stacked directly above/below), so it is never a
      left/right target — this is what stops a straight-down node counting as "left" and lets
      the staggered off-row sectors be reached. On an exact tie (same column-distance and row-
      distance, one just above and one just below) the **warp-linked** candidate wins; failing
      that (or where no adjacency is known, e.g. the nav rose) the **upper** one wins.
    * **Up / Down** keeps to the column: a candidate whose column span **overlaps** the current
      node's is *in beam*, and in-beam candidates are preferred, nearest-in-travel first — so
      you step to the sector just above/below rather than jumping to a far, off-column one.

    Shared by the nav rose and the local map.
    """
    if not hits or idx >= len(hits):
        return None
    cur = hits[idx]
    cx = (cur.col0 + cur.col1) / 2
    scored: list[tuple[bool, float, float, tuple[int, int], int]] = []
    for j, n in enumerate(hits):
        if j == idx:
            continue
        if dy:  # vertical move — beam is the overlapping column span (stay in the column)
            major = (n.row - cur.row) * dy
            if major <= 0:
                continue  # not in the pressed direction (or level with it)
            in_beam = cur.col0 < n.col1 and n.col0 < cur.col1
            minor = abs((n.col0 + n.col1) / 2 - cx)
            scored.append((not in_beam, major, minor, (0, 0), j))  # in-beam, nearest, aligned
        else:  # horizontal move — step to the adjacent column, nearest by row
            if cur.col0 < n.col1 and n.col0 < cur.col1:
                continue  # spans overlap ⇒ same column (stacked): not a left/right neighbour
            if (n.col0 > cur.col0) != (dx > 0):
                continue  # the node's column is on the wrong side of the pressed direction
            linked = n.sector_id in cur.neighbors or cur.sector_id in n.neighbors
            # column-distance, then row-distance, then: warp-linked wins, else prefer the upper.
            tie = (0 if linked else 1, n.row)
            scored.append((False, abs(n.col0 - cur.col0), abs(n.row - cur.row), tie, j))
    return min(scored)[4] if scored else None


class LocalMapView(Static):
    """The local sector ego-graph (Computer/Map screen → §10, §11).

    A node-and-edge graph of the player's surrounding sectors, centered on the
    current sector and laid out in gravity columns (toward-Core left, deeper
    right). The rows + legend are baked server-side (`session.map_view`); this
    widget renders them and highlights the keyboard-selected sector (a style span
    over its baked cell, like the nav rose). **Arrow keys** move the selection to the
    nearest sector in that direction; **Enter/Space** (or a click) posts
    `Picked(sector_id)` so the screen can plot a route to it.

    When a `rebake` callback is supplied, the map **grows to fit the widget's width**:
    on resize the widget re-requests a map sized to its current character width, so it
    shows as many sectors as the screen allows.
    """

    can_focus = True

    DEFAULT_CSS = """
    LocalMapView { height: auto; padding: 1 2; }
    """

    BINDINGS = [
        Binding("left", "move(-1, 0)", show=False),
        Binding("right", "move(1, 0)", show=False),
        Binding("up", "move(0, -1)", show=False),
        Binding("down", "move(0, 1)", show=False),
        Binding("enter", "pick", "Plot route", show=False),
        Binding("space", "pick", "Plot route", show=False),
    ]

    class Picked(Message):
        def __init__(self, sector_id: int) -> None:
            self.sector_id = sector_id  # internal id of the chosen sector
            super().__init__()

    def __init__(
        self, gmap: LocalMapDTO,
        rebake: Callable[[int], LocalMapDTO] | None = None, **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._map = gmap
        self._rebake = rebake  # (width) -> a map sized to fit; None ⇒ fixed reach
        self._hits = self._order(gmap)
        self._idx = 0

    @staticmethod
    def _order(gmap: LocalMapDTO) -> list:  # type: ignore[type-arg]
        """Selectable sector nodes, top-to-bottom then left-to-right (cursor home order)."""
        return sorted(gmap.nodes, key=lambda n: (n.row, n.col0))

    def on_mount(self) -> None:
        self._refit()

    def on_resize(self, event: events.Resize) -> None:
        self._refit()

    def _refit(self) -> None:
        """Re-bake the map to the current widget width (no-op without a rebake hook)."""
        if self._rebake is None:
            return
        width = self.content_size.width
        if width <= 0:
            return
        keep = self._hits[self._idx].sector_id if self._hits else None
        self.update_map(self._rebake(width), keep_sector=keep)

    def render(self) -> Text:
        focus = self._hits[self._idx] if self._hits else None
        body = self._map.rows or ["[dim]no charted neighbours[/]"]
        lines: list[Text] = []
        for i, row in enumerate(body):
            line = Text.from_markup(row)
            if focus is not None and self.has_focus and focus.row == i:
                line.stylize("reverse bold", focus.col0, focus.col1)
            lines.append(line)
        out = Text("\n").join(lines)
        if self._map.legend:
            out.append("\n\n")
            out.append_text(Text.from_markup(self._map.legend))
        return out

    def update_map(self, gmap: LocalMapDTO, *, keep_sector: int | None = None) -> None:
        """Swap in a freshly baked map, preserving the selected sector where possible."""
        self._map = gmap
        self._hits = self._order(gmap)
        self._idx = next((i for i, n in enumerate(self._hits) if n.sector_id == keep_sector), 0)
        self.refresh()

    def action_move(self, dx: int, dy: int) -> None:
        """Move the selection to the nearest node in the pressed screen direction."""
        j = _nearest_node(self._hits, self._idx, dx, dy)
        if j is not None:
            self._idx = j
            self.refresh()

    def action_pick(self) -> None:
        if self._hits:
            self.post_message(self.Picked(self._hits[self._idx].sector_id))

    def on_click(self, event: events.Click) -> None:
        # Click coords are relative to the widget box; shift past the padding to land
        # in the baked `rows` grid, then hit-test the node label boxes.
        pad = self.styles.padding
        col, row = int(event.x) - pad.left, int(event.y) - pad.top
        for i, node in enumerate(self._hits):
            if node.row == row and node.col0 <= col < node.col1:
                event.stop()
                self._idx = i
                self.refresh()
                self.post_message(self.Picked(node.sector_id))
                return

    def on_focus(self) -> None:
        self.refresh()

    def on_blur(self) -> None:
        self.refresh()


class ClickableEntry(Static):
    """A clickable line in the sector view (a port or planet) that navigates."""

    DEFAULT_CSS = """
    ClickableEntry { height: 1; }
    ClickableEntry:hover { background: $boost; text-style: bold; }
    """

    class Picked(Message):
        def __init__(self, dest: str, ref: int | str | None = None) -> None:
            self.dest = dest
            self.ref = ref  # an optional target id (e.g. a discovery to salvage)
            super().__init__()

    def __init__(self, markup: str, dest: str, ref: int | str | None = None, **kwargs: Any) -> None:
        super().__init__(markup, **kwargs)
        self._dest = dest
        self._ref = ref

    @property
    def dest(self) -> str:
        """What this row points at — readable so a keyboard caller can act on the focused row."""
        return self._dest

    def on_click(self) -> None:
        self.post_message(self.Picked(self._dest, self._ref))


class ObjectRow(ClickableEntry, can_focus=True):
    """A focusable object row — the keyboard equivalent of a scene hotspot (WP-UI12).

    Tab/arrow focus + Enter/Space post the same `ClickableEntry.Picked` a click
    (or the scene hotspot) posts, so the GameScreen routing is shared verbatim.
    """

    BINDINGS = [
        Binding("enter", "pick", "Open", show=False),
        Binding("space", "pick", "Open", show=False),
    ]

    DEFAULT_CSS = """
    ObjectRow { height: 1; padding: 0 1; }
    ObjectRow:focus { background: $primary 30%; text-style: bold; }
    """

    def action_pick(self) -> None:
        self.post_message(self.Picked(self._dest, self._ref))


class SectorObjectList(Vertical):
    """Everything in the sector as a focusable list (WP-UI12).

    The keyboard/list equivalent of the `SectorScene` click hotspots: each
    interactable row is an `ObjectRow` posting the identical
    `ClickableEntry.Picked`, so planet/port/base/ship/anomaly/discovery routing
    stays in one GameScreen handler. Informational lines (unhailable ships,
    deployed-force hazards) render as plain text. Shown inline on the compact
    tier — where the scene art is hidden — and inside the `I` status drawer on
    every tier.
    """

    DEFAULT_CSS = "SectorObjectList { height: auto; } SectorObjectList > Static { height: 1; }"

    def __init__(self, sector: SectorDTO, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sector = sector

    def compose(self) -> ComposeResult:
        sec = self._sector
        empty = True
        for planet in sec.planets:
            empty = False
            # Belts are spatial features, not landable colonies — label the type and use
            # "Orbit" rather than "Survey" so the row never implies a descent (§4.2, WP-PR06).
            if planet.ptype == "asteroid_belt":
                yield ObjectRow(
                    f"[green]@[/] {planet.name} [dim]— {pretty_planet_type(planet.ptype)} (Orbit)[/]",
                    "planet")
            else:
                yield ObjectRow(f"[green]@[/] {planet.name} [dim](Survey)[/]", "planet")
        for b in getattr(sec, "starbases", ()) or ():
            empty = False
            status = "[green]operational[/]" if b.operational else "[yellow]derelict[/]"
            yield ObjectRow(f"[cyan]#[/] {b.name} — {status} [dim]· {b.owner} (Visit)[/]",
                            "starbase", b.starbase_id)
        # A base's market is entered through the base (§4.2, WP80) — mirror the scene,
        # which lists the free-standing port only when no base holds the orbit slot.
        if sec.ports and not (getattr(sec, "starbases", ()) or ()):
            port = sec.ports[0]
            code = "S" if port.is_stardock else "P"
            yield ObjectRow(f"[magenta]{code}[/] {port.name} [dim](Dock)[/]", "port")
            empty = False
        for vessel in sec.ships:
            empty = False
            if vessel.contact_id is not None:
                yield ObjectRow(f"[white]>[/] {vessel.name} [dim](Hail)[/]",
                                "contact", vessel.contact_id)
            elif getattr(vessel, "player_id", None) is not None:
                yield ObjectRow(f"[white]>[/] {vessel.name} [dim](Engage)[/]",
                                "player", vessel.player_id)
            else:
                yield Static(f"[white]>[/] {vessel.name}")
        anomaly = getattr(sec, "anomaly", None)
        if anomaly is not None:  # the Entity's fog-safe presence hint (§7, WP35)
            empty = False
            if anomaly.contactable:
                yield ObjectRow(f"[b gold1]✶ {anomaly.label}[/] [dim](Hail)[/]",
                                "contact", anomaly.contact_id)
            else:
                yield Static(f"[gold3]✶ {anomaly.label}[/] [dim](beyond sensor resolution)[/]")
        for d in sec.discoveries:
            empty = False
            label = d.label if d.collected else "Anomaly detected"
            if d.kind == "wormhole" and d.warp_to is not None:
                # Same routing as the scene hotspot: entering IS the interaction.
                yield ObjectRow(f"[cyan]✦[/] {label} [dim](Enter — one-way)[/]",
                                "wormhole", d.warp_to)
            elif not d.collected:
                yield ObjectRow("[cyan]✦[/] Anomaly detected [dim](Scan)[/]",
                                "discovery", d.discovery_id)
            else:
                yield Static(f"[cyan]✦[/] {label} [dim]— logged[/]")
        for line in force_lines(getattr(sec, "force", None)):  # hazards, info-only
            empty = False
            yield Static(line)
        if empty:
            yield Static("[dim]Nothing but empty space.[/]")


class WarpCell(Static):
    """One outbound warp — the single, information-rich warp affordance (§5.1).

    Focusable (arrow-key navigable) and clickable. Renders, left-justified, the
    spatial id, the gravity arrow as the separator, and the region name + band;
    the port/planet `codes` are right-justified against the cell's right edge.
    Colour follows `kind` (visited / came-from / unmapped) via CSS classes.
    """

    can_focus = True

    class Warp(Message):
        def __init__(self, sector_id: int) -> None:
            self.sector_id = sector_id
            super().__init__()

    # Enter/Space activate the focused cell (it's a Static, not a Button, so it needs
    # its own keys — the arrow keys that move focus are bound on the parent grid).
    BINDINGS = [
        Binding("enter", "warp", "Warp", show=False),
        Binding("space", "warp", "Warp", show=False),
    ]

    DEFAULT_CSS = """
    WarpCell { width: 1fr; height: 1; padding: 0 1; color: $primary; }
    WarpCell.unexplored { color: $text-disabled; }
    WarpCell.backtrack { color: $accent; }
    WarpCell:hover { background: $boost; }
    """

    def __init__(self, warp: WarpDTO, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._warp = warp
        if warp.kind == "unexplored":
            self.add_class("unexplored")
        elif warp.kind == "backtrack":
            self.add_class("backtrack")

    def render(self) -> Text:
        w = self._warp
        name = w.label or "—"
        left = Text.from_markup(f"{w.display_id} {w.arrow} {name}")
        if w.band:
            # Drop the band's dim when focused, else `reverse` turns it into a darker
            # background shade than the rest of the label (uneven highlight).
            left.append(f" ({w.band})", style="" if self.has_focus else "dim")
        if self.has_focus:
            left.stylize("reverse bold")  # invert just the warp text, not the whole grid cell
        codes = _code_markup(w.codes)
        right = Text.from_markup(codes) if codes else Text("")
        # Left-justify the warp text, right-justify the codes; pad between to fill the
        # printable cell width (account for the 1-cell horizontal padding each side).
        width = max(0, self.size.width - 2)
        gap = width - left.cell_len - right.cell_len
        if gap < 1:  # no room for the codes — drop them rather than overflow/wrap
            left.truncate(width, overflow="ellipsis")
            return left
        left.append(" " * gap)
        left.append_text(right)
        return left

    def on_click(self) -> None:
        self.action_warp()

    def on_focus(self) -> None:
        self.refresh()  # repaint so the focused-text inversion in render() applies

    def on_blur(self) -> None:
        self.refresh()

    def action_warp(self) -> None:
        self.post_message(self.Warp(self._warp.sector_id))


class SectionRule(Static):
    """A full-width horizontal rule with a centred caption laid over the line."""

    DEFAULT_CSS = "SectionRule { height: 1; color: $primary; }"

    def __init__(self, label: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._label = label

    def render(self) -> Text:
        width = max(1, self.size.width)
        cap = f" {self._label} "
        dashes = max(0, width - len(cap))
        left = dashes // 2
        out = Text()
        out.append("─" * left, style="dim")
        out.append(cap, style="bold")
        out.append("─" * (dashes - left), style="dim")
        return out


class WarpGrid(Grid):
    """Outbound warps laid out in a configurable-width grid (§5.1, §11).

    Cells fill the printable area and wrap into rows (`columns` wide); TW2002 sectors
    warp to at most `max_warps_per_sector` others. There is no current-sector cell —
    the warps *are* the grid. The grid reserves `min_rows` rows (= ceil(max warps /
    columns)) so its height is the same in every sector regardless of warp count.
    Keyboard focus lands on a cell chosen by `focus_default` (first / came-from /
    first unexplored); arrow keys step between cells, Enter/Space activates the focus.
    """

    # Arrow keys move focus between warp cells by their on-screen grid position
    # (Up = the cell rendered above, etc.). They fire while a cell is focused (the keys
    # bubble up to the grid) and are hidden from the footer.
    BINDINGS = [
        Binding("up", "move(-1, 0)", show=False),
        Binding("down", "move(1, 0)", show=False),
        Binding("left", "move(0, -1)", show=False),
        Binding("right", "move(0, 1)", show=False),
    ]

    DEFAULT_CSS = """
    WarpGrid {
        grid-rows: 1;
        grid-gutter: 0 1;
        height: auto;
        width: 1fr;  /* full warp-area width; cell size derives from columns (§5.1) */
    }
    """

    def __init__(
        self, warps: list[WarpDTO], columns: int = 3, focus_default: str = "first",
        min_rows: int = 1, **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._warps = warps
        self._columns = max(1, columns)
        self._focus_default = focus_default
        self._min_rows = max(1, min_rows)

    def compose(self) -> ComposeResult:
        for warp in self._warps:
            yield WarpCell(warp)

    def on_mount(self) -> None:
        self.styles.grid_size_columns = self._columns
        # Reserve a consistent height: the rows the full warp cap would need, so the
        # grid (and thus the sector scene above it) doesn't resize per sector. Each row
        # is 1 tall with no row gutter, so height in cells == row count.
        used_rows = -(-len(self._warps) // self._columns)  # ceil
        self.styles.height = max(self._min_rows, used_rows)
        # Anchor focus as soon as the grid appears, so arrow keys drive selection
        # immediately (no priming Tab). The grid is remounted on every recompose, so
        # focus re-homes each time the sector view refreshes.
        self.call_after_refresh(self._focus_anchor)

    def _focus_anchor(self) -> None:
        cells = [c for c in self.children if isinstance(c, WarpCell)]
        if not cells:
            return
        target = cells[0]
        if self._focus_default == "backtrack":
            target = next((c for c in cells if c._warp.kind == "backtrack"), cells[0])
        elif self._focus_default == "unexplored":
            target = next((c for c in cells if c._warp.kind == "unexplored"), cells[0])
        target.focus()

    def action_move(self, drow: int, dcol: int) -> None:
        """Move focus to the next warp cell in the (drow, dcol) screen direction.

        Children flow into the fixed-column grid in order, so child index i sits at
        (i // columns, i % columns). We step one cell at a time from the focused cell
        until we land on another warp cell or walk off the grid.
        """
        children = list(self.children)
        grid = {(i // self._columns, i % self._columns): c for i, c in enumerate(children)}
        pos = {c: rc for rc, c in grid.items()}
        focused = self.app.focused
        if focused not in pos:  # focus drifted off the grid — re-anchor
            self._focus_anchor()
            return
        row, col = pos[focused]
        max_row = (len(children) - 1) // self._columns
        row, col = row + drow, col + dcol
        while 0 <= row <= max_row and 0 <= col < self._columns:
            target = grid.get((row, col))
            if isinstance(target, WarpCell):
                target.focus()
                return
            row, col = row + drow, col + dcol


class RoseTrail(Static):
    """The breadcrumb trail display on the left side of the nav rose."""

    @property
    def rose(self) -> NavRose:
        node = self.parent
        while node is not None:
            if isinstance(node, NavRose):
                return node
            node = node.parent
        raise RuntimeError("NavRose parent not found")

    def render(self) -> Text:
        col = self.rose._trail_column()
        out = Text()
        for i, line in enumerate(col):
            if i > 0:
                out.append("\n")
            out.append_text(line)
        return out


class RoseCompass(Static):
    """The central compass rose display widget."""

    @property
    def rose(self) -> NavRose:
        node = self.parent
        while node is not None:
            if isinstance(node, NavRose):
                return node
            node = node.parent
        raise RuntimeError("NavRose parent not found")

    def render(self) -> Text:
        rose_widget = self.rose
        focus_node = rose_widget._hits[rose_widget._idx] if rose_widget._hits else None

        # Parse the baked rose rows and pad to the full 5-row compass.
        rose: list[Text] = [Text.from_markup(r) for r in rose_widget._nav.rows]
        while len(rose) < 5:
            rose.append(Text())

        out = Text()
        for i in range(5):
            if i > 0:
                out.append("\n")
            rl = rose[i]
            if focus_node is not None and rose_widget.has_focus and focus_node.row == i:
                rl = rl.copy()
                rl.stylize("reverse bold", focus_node.col0, focus_node.col1)
            out.append_text(rl)
        return out

    def on_click(self, event: events.Click) -> None:
        parent = self.rose
        event.stop()
        for i, node in enumerate(parent._hits):
            if node.row == event.y and node.col0 <= event.x < node.col1:
                parent._idx = i
                self.refresh()
                parent.query_one("#rose-detail", RoseDetail).refresh()
                parent.post_message(parent.Picked(node.sector_id))
                return


class RoseDetail(Static):
    """The selected warp detail display on the right side of the nav rose."""

    @property
    def rose(self) -> NavRose:
        node = self.parent
        while node is not None:
            if isinstance(node, NavRose):
                return node
            node = node.parent
        raise RuntimeError("NavRose parent not found")

    def render(self) -> Text:
        rose_widget = self.rose
        focus_node = rose_widget._hits[rose_widget._idx] if rose_widget._hits else None
        col = rose_widget._detail_column(focus_node)

        # Calculate available width dynamically based on NavRose width
        # Subtract padding (2) and separators/margins
        content_w = max(0, rose_widget.size.width - 2)
        rose_w = max((Text.from_markup(r).cell_len for r in rose_widget._nav.rows), default=0)
        detail_avail = max(0, (content_w - 6 - rose_w) // 2)

        out = Text()
        for i, line in enumerate(col):
            if i > 0:
                out.append("\n")
            if line.cell_len > detail_avail:
                line = line.copy()
                line.truncate(detail_avail, overflow="ellipsis")
            out.append_text(line)
        return out


class NavRose(Vertical):
    """The always-visible nav rose — the sole main-screen warp affordance (§11).

    A compact bearing-placed compass baked server-side (`session.game_view` →
    `navstrip.build_nav_strip`): the player (`@`) centred, each outbound warp in the
    octant of its real bearing, a fixed `Core` anchor for global orientation.  The
    baked rose rows are flanked by a **trail column** (left, recent-route breadcrumb)
    and a **detail column** (right, selected-warp info), so all navigation context
    fits in 5 rows with no stacked lines below.  Highlights the keyboard-selected
    warp, and warps on click or Enter.
    """

    can_focus = True

    class Picked(Message):
        def __init__(self, sector_id: int) -> None:
            self.sector_id = sector_id  # internal id of the chosen warp target
            super().__init__()

    BINDINGS = [
        Binding("up", "move(0, -1)", show=False),
        Binding("down", "move(0, 1)", show=False),
        Binding("left", "move(-1, 0)", show=False),
        Binding("right", "move(1, 0)", show=False),
        Binding("enter", "warp", "Warp", show=False),
        Binding("space", "warp", "Warp", show=False),
    ]

    DEFAULT_CSS = """
    NavRose {
        height: auto;
        width: 1fr;
        padding: 0 1;
    }
    NavRose > #rose-row {
        layout: horizontal;
        height: 5;
        width: 1fr;
    }
    NavRose #rose-trail {
        width: 1fr;
        text-align: right;
    }
    NavRose #rose-sep-left {
        width: auto;
        color: $primary;
        opacity: 0.5;
    }
    NavRose #rose-compass {
        width: auto;
    }
    NavRose #rose-sep-right {
        width: auto;
        color: $primary;
        opacity: 0.5;
    }
    NavRose #rose-detail {
        width: 1fr;
        text-align: left;
    }
    NavRose > #rose-legend {
        text-align: center;
        width: 1fr;
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, nav: NavStripDTO, warps: list[WarpDTO], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._nav = nav
        self._warps = {w.sector_id: w for w in warps}
        # Home selection is the top-left node; arrow keys then move by on-screen layout.
        self._hits = sorted(nav.nodes, key=lambda n: (n.row, n.col0))
        self._idx = 0

    def on_mount(self) -> None:
        # Grab focus as the rose appears so arrow keys drive selection immediately
        # (no priming Tab); re-homes on each recompose, as the old warp grid did.
        if self._hits:
            focus_default = getattr(getattr(self.app, "ui_config", None),
                                    "warp_focus_default", "backtrack")
            if focus_default == "backtrack":
                self._idx = next(
                    (i for i, node in enumerate(self._hits)
                     if self._warps.get(node.sector_id) is not None
                     and self._warps[node.sector_id].kind == "backtrack"),
                    0,
                )
            elif focus_default == "unexplored":
                self._idx = next(
                    (i for i, node in enumerate(self._hits)
                     if self._warps.get(node.sector_id) is not None
                     and self._warps[node.sector_id].kind == "unexplored"),
                    0,
                )
            self.call_after_refresh(self.focus)

    def compose(self) -> ComposeResult:
        with Horizontal(id="rose-row"):
            yield RoseTrail(id="rose-trail")
            yield Static("│\n│\n│\n│\n│", id="rose-sep-left")
            yield RoseCompass(id="rose-compass")
            yield Static("│\n│\n│\n│\n│", id="rose-sep-right")
            yield RoseDetail(id="rose-detail")
        if self._nav.legend:
            yield Static(self._nav.legend, id="rose-legend")

    def _trail_column(self) -> list[Text]:
        """5 right-aligned trail lines: header, up to 3 history entries, you."""
        col: list[Text] = [Text() for _ in range(5)]
        col[0] = Text("trail", style="dim")
        # Last ≤3 trail entries fill rows 1–3, packed toward the bottom.
        recent = self._nav.trail[-3:]
        start = 4 - len(recent)
        for i, sid in enumerate(recent):
            col[start + i] = Text(str(sid), style="dim")
        col[4] = Text(str(self._nav.you_display), style="bold cyan")
        return col

    def _detail_column(self, focus_node: object) -> list[Text]:
        """5 detail lines for the keyboard-selected warp target."""
        col: list[Text] = [Text() for _ in range(5)]
        if focus_node is None:
            col[2] = Text("no warps", style="dim")
            return col
        node = self._hits[self._idx]
        warp = self._warps.get(node.sector_id)
        hdr = Text("▶ ", style="bold")
        hdr.append(str(node.display_id), style="bold")
        direction = {"<<": "Coreward", ">>": "Outward", "--": "Cross-band"}.get(
            warp.arrow if warp is not None else "", "Warp")
        col[0] = hdr
        if warp is None or not warp.explored:
            col[1] = Text("? uncharted", style="dim")
        else:
            col[1] = Text(warp.label or "—")
        state_bits = [direction, f"{warp.turn_cost if warp else 1} turn"]
        if warp is not None and warp.kind == "backtrack":
            state_bits.append("↩ backtrack")
        if warp is not None and warp.one_way:
            state_bits.append("⇢ one-way")
        col[2] = Text(" · ".join(state_bits), style="yellow" if warp and warp.one_way else "")
        if warp is not None and warp.band:
            band = Text(f"Band {warp.band}", style=BAND_COLOR.get(warp.band, ""))
            if warp.avoided:
                band.append(" · ⊘ avoided", style="yellow")
            col[3] = band
        if warp is not None:
            tail = ", ".join(warp.hazards)
            if tail:
                col[4] = Text("⚠ " + tail, style="yellow")
            elif warp.codes:
                col[4] = Text.from_markup(_code_markup(warp.codes))
        return col

    def action_move(self, dx: int, dy: int) -> None:
        """Move the selection to the nearest warp in the pressed screen direction."""
        j = _nearest_node(self._hits, self._idx, dx, dy)
        if j is not None:
            self._idx = j
            self.query_one("#rose-compass", RoseCompass).refresh()
            self.query_one("#rose-detail", RoseDetail).refresh()

    def action_warp(self) -> None:
        if self._hits:
            self.post_message(self.Picked(self._hits[self._idx].sector_id))



    def on_focus(self) -> None:
        try:
            self.query_one("#rose-compass", RoseCompass).refresh()
        except NoMatches:
            pass

    def on_blur(self) -> None:
        try:
            self.query_one("#rose-compass", RoseCompass).refresh()
        except NoMatches:
            pass
