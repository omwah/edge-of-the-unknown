"""Reusable widgets for the TUI skeleton: starfield, status sidebar, warp list."""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
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

from edge.art import sprites as art_sprites
from edge.core.config import SceneArtConfig
from edge.core.dto import SectorDiscovery, SectorPlanetDTO, SectorShipDTO
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
        "• [b]↩[/] Backtrack / the sector just left   • [b]⇢[/] One-way exit (destination hidden until taken)\n"
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
        # The find's identity stays hidden until scanned — pre-scan it reads generic. A **wreck**
        # is the exception: a hulk is plainly a hulk, and the one you just shot down still wears
        # its ship's name (PT-49), so naming it costs no fog and makes the kill legible.
        if d.collected:
            kind = f" · {d.kind}" if detail else ""
            return f"[cyan]✦[/] {d.label} [dim]— logged{kind}[/]"
        if d.kind == "wreck":
            of = f" of the {d.name}" if d.name else ""
            return f"[yellow]⚙[/] Wreckage{of} [dim](Salvage)[/]"
        return "[cyan]✦[/] Anomaly detected [dim](Scan)[/]"

    def on_click(self) -> None:
        if self._scan:
            self.post_message(ClickableEntry.Picked("discovery", self._discovery_id))


class ContactRow(Static):
    """A clickable ship row in the sidebar 'Ships' list.

    The scene tags ships by name alone; the verb lives here — clicking (or the
    `(Hail)`/`(Engage)` affordance) posts the same `ClickableEntry.Picked` the
    scene's ship hotspots post, so the GameScreen handler is untouched.
    """

    DEFAULT_CSS = """
    ContactRow { height: 1; }
    ContactRow.pick:hover { background: $boost; text-style: bold; }
    """

    def __init__(self, vessel: SectorShipDTO, **kwargs: Any) -> None:
        cid = vessel.contact_id
        pid = getattr(vessel, "player_id", None)
        self._dest: str | None
        self._ref: int | None
        if cid is not None:
            self._dest, self._ref, verb = "contact", cid, " [dim](Hail)[/]"
        elif pid is not None:
            self._dest, self._ref, verb = "player", pid, " [dim](Engage)[/]"
        else:
            self._dest, self._ref, verb = None, None, ""
        super().__init__(f"[white]▸[/] {vessel.name}{verb}", **kwargs)
        if self._dest is not None:
            self.add_class("pick")

    def on_click(self) -> None:
        if self._dest is not None:
            self.post_message(ClickableEntry.Picked(self._dest, self._ref))


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
                 contacts: list[SectorShipDTO] | None = None,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._ship = ship
        self._discoveries = discoveries
        self._width = width
        self._presence = presence or []
        self._detail = detail
        self._objectives = objectives
        self._contacts = contacts or []

    def on_mount(self) -> None:
        self.styles.width = self._width

    def compose(self) -> ComposeResult:
        yield Static(self._stats_markup())
        if self._presence:  # starbases + known forces here (§4.2/§10, fog-applied)
            yield Static("[b yellow]Presence[/]")
            for line in self._presence:
                yield Static(line)
        if self._contacts:  # every vessel here, individually hailable/engageable
            yield Static("[b yellow]Ships[/]")
            for vessel in self._contacts:
                yield ContactRow(vessel)
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
        ]
        # The ground force only takes a line once there is one to report (GW-WP08) —
        # an empty barracks is not news on every sector view.
        if s.recruits or s.suits_carried:
            lines.append(f"Marines   {s.recruits:,} in {s.suits_carried:,} suits"
                         f" · {s.ground_missiles:,} msl")
        lines += [
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


# The disc and the traffic share one width budget: ships ride the sky *left* of the
# primary, so every row the planet gains costs two columns there. These two numbers
# keep a growing planet from squeezing that sky below a whole ship rung — see
# `_paint_planet` and docs/SECTOR_SCENE_COMPOSITION.md §3.
_SHIP_SKY_RESERVE = 42        # ship's middle rung (36 cols) + the 6 `_paint_ships` insets
_SHIP_SKY_MIN_RUNG_ROWS = 5   # that rung is 36x5, and ship height scales off the planet

# Where the primary body's centre sits, as a fraction of scene width. Pushed well
# right of centre so the sky that ships and tags live in is one wide, coherent
# region rather than a sliver — the disc is expected to run off the right edge,
# like a world filling a viewport. `_PRIMARY_MIN_VISIBLE` is the counterweight:
# enough of the disc must stay on screen that it still reads as a world.
_PRIMARY_CENTRE = 0.78
_PRIMARY_MIN_VISIBLE = 0.7

# How far down the primary's limb a station berths, as a fraction of its height.
_STATION_LIMB = 0.72

# Traffic depth. Ships in one scene must not all draw the same rung: two hulls at
# identical scale read as a formation on a flat backdrop, and at the top of the
# ladder they also overpower the station they are visiting (both reported
# repeatedly in the 2026-08-16 gallery pass — "one ship smaller gives a sense of
# depth", "ships overpower port", "ships right on top of each other"). Ships are
# banded down the sky by index, so the band index *is* the depth cue: the higher a
# ship sits, the further away it reads, and the further one steps down the art
# ladder. `_SHIP_DEPTH_MAX_STEPS` caps that at two rungs so a third ship still
# draws as a ship rather than a speck.
_SHIP_DEPTH_MAX_STEPS = 2

# Clearance a ship keeps from anything already placed, before the fallbacks relax
# it. The 1-cell occupancy pad is enough to stop an overlap but not enough to stop
# two hulls — or a hull and a station — from reading as one crowded mass. Tried
# widest-first; a scene with no room for the standoff falls back to the pad.
_SHIP_STANDOFF: tuple[tuple[int, int], ...] = ((6, 2), (3, 1), (1, 1))
# Rows held clear between one ship's band and the next, so the jitter inside a band
# can never seat two ships flush against each other.
_SHIP_BAND_GAP = 3
# How many extra rungs a ship may drop below its depth's rung to find a berth. The
# ladder — not a shifted berth — is how the scene absorbs "not enough room", because
# moving the ship instead breaks the depth ordering the rung was chosen for.
_SHIP_FIT_STEPS = 3

# A space find that is the scene's primary takes this share of the body budget.
# Compact phenomena still read as smaller than a world (which takes 0.9) without
# shrinking to a token — at 0.6 a wormhole rendered 15 rows in a 25-row sky.
_FIND_PRIMARY = 0.82
# Rows a *secondary* find (the wreck slot beside a world) may reach. It scales with
# the scene rather than sitting at a fixed 6, but stays capped well below a primary
# so it never competes with the body it is parked next to.
_FIND_SECONDARY_MAX = 10


@dataclass(frozen=True)
class SpriteRender:
    """One sprite the composer drew, with everything that determined how it looks.

    The scene is built from many `generate_sprite` calls whose result depends on
    subtype, seed, archetype, facing, and — most consequentially — the *box* the
    scene asked for, which the library then quantises to an authored tier. When a
    sprite comes out the wrong size, `box` vs `drawn` is the whole diagnosis: equal-
    ish means the scene asked for the wrong thing, wildly different means the ladder
    stepped somewhere the scene did not expect.

    `ref` is the stable, greppable identifier — the same sprite in the same sector
    produces the same string every run, so it can be quoted in a bug report and
    reproduced with `scene_gallery`/`scene_preview`.
    """

    entity: str
    subtype: str
    seed: int
    box: tuple[int, int]      # what the scene requested
    drawn: tuple[int, int]    # what was inked, after the tier pick and the crop
    facing: str = "right"
    archetype_id: str | None = None

    @property
    def ref(self) -> str:
        arch = f"/{self.archetype_id}" if self.archetype_id else ""
        face = f":{self.facing}" if self.entity == "ship" else ""
        return (f"{self.entity}:{self.subtype}{arch}{face}"
                f"@{self.box[0]}x{self.box[1]}"
                f"->{self.drawn[0]}x{self.drawn[1]}#{self.seed}")


def primary_body_height(cfg: SceneArtConfig, w: int, body_h: int, *,
                        belt: bool = False) -> int:
    """Rows the primary disc takes in a `w`-wide scene — the head of the scale chain.

    Everything else in the scene derives from this number (DESIGN of the chain is in
    docs/SECTOR_SCENE_COMPOSITION.md §2), so it is a module function rather than
    inline arithmetic: the responsiveness tests sweep it over hundreds of viewports
    and must exercise the same code the composer runs, not a copy that can drift.

    Three bounds apply, tightest wins:

    - the configured cap, `planet.max_height`;
    - the height budget, 90% of the scene body;
    - how far the disc may run off the right edge. The disc is *not* required to fit
      whole — it is anchored at `_PRIMARY_CENTRE` and allowed to clip, because a
      world filling the window reads as bigger rather than broken, and the width it
      gives back is the sky ships ride in. `_PRIMARY_MIN_VISIBLE` keeps enough of it
      on screen to still read as a world; solving that for the radius gives the
      `visible_cap` below.

    A last pass hands back just enough width to hold one whole ship rung. Without it
    a mid-width scene grows the disc until the sky can no longer fit the 36-column
    rung and the ladder drops traffic to its 17-column stub — *smaller* than before
    the planet was allowed to grow at all. The gate tests the **rung, not the
    width**: ship height also scales off the planet, so trimming the disc shrinks
    the very ship the columns were freed for; below ~23 rows the trade buys a wide
    berth for a ship only tall enough to draw the narrow rung, so it is declined and
    stepping the ship down stays the intended behaviour (§2). Belts are exempt —
    they anchor to the right edge and size from their own sprawl.
    """
    visible_cap = int(w * (1.0 - _PRIMARY_CENTRE) / (2.0 * _PRIMARY_MIN_VISIBLE - 1.0))
    ph = max(cfg.planet.min_height,
             min(cfg.planet.max_height, int(body_h * 0.9), visible_cap))
    if not belt and int(w * _PRIMARY_CENTRE) - ph < _SHIP_SKY_RESERVE:
        trimmed = int(w * _PRIMARY_CENTRE) - _SHIP_SKY_RESERVE
        if round(trimmed * cfg.ship_scale) >= _SHIP_SKY_MIN_RUNG_ROWS:
            ph = max(cfg.planet.min_height, trimmed)
    return ph


class _SceneComposer:
    """Composites one sector as an *arrival view* (UI_MOCKUPS.md §1, PT-36/PT-44).

    Instead of partitioning the canvas into reserved bands (planet half / port
    half / ships row), the scene is composed like a viewport on the sector: the
    largest body present — the planet, else a space find, else the station —
    anchors toward the right edge at the biggest size that fits (its disc may
    crop slightly, like a world filling the window); a port/starbase hovers at
    its lower limb at roughly half its scale; ships ride the open sky smaller
    still; deployed fighters/mines are single-glyph presence marks whose counts
    live in the sidebar. Names float as short tags stamped into free sky beside
    their sprite, so no object reserves a caption row of its own.

    The scale hierarchy derives from `SceneArtConfig`: the primary body fills
    most of the free height. Port, Stardock, and starbase use their own configured
    sprite heights (shared with their docked screens), while `ship_scale` sizes
    ships relative to the primary. All placement randomness is seeded off the
    sector id, so a sector always composes the same way.

    Pure presentation: consumes only the `SectorDTO`, emits a `rich.Text` plus
    the hotspot rects `SectorScene.on_click` routes. Usable without a running
    app (see `edge.tui.scene_preview`).
    """

    def __init__(self, sector: SectorDTO, cfg: SceneArtConfig) -> None:
        self.sec = sector
        self.cfg = cfg
        # (x0, y0, x1, y1, dest, ref) — the click targets, in paint order.
        self.hotspots: list[tuple[int, int, int, int, str, int | str | None]] = []
        self._grid: list[list[tuple[str, Style | None]]] = []
        # Rects already holding a sprite/tag; tags and scattered glyphs steer clear.
        self._occupied: list[tuple[int, int, int, int]] = []
        # Objects that found no free sky degrade to text rows (still clickable).
        self._deferred: list[tuple[str, str | None, int | str | None]] = []
        # Every sprite drawn this compose, in draw order (see `SpriteRender`).
        self.render_log: list[SpriteRender] = []
        # (kind, x0, y0, x1, y1) for each placed sprite — the exact footprint the
        # scene gave it. Debug tooling draws these as bounds; nothing in the game
        # path reads them (`hotspots` is what routes clicks, and it omits objects
        # that carry no destination).
        self.sprite_rects: list[tuple[str, int, int, int, int]] = []
        self.station_reference: tuple[int | None, int] | None = None
        # True when the primary body drawn was an asteroid belt — a field traffic
        # flies through rather than a body it must keep clear of (`_paint_planet`).
        self._belt_primary = False
        self._w = 0
        self._h = 0

    # --- grid primitives ------------------------------------------------------

    def _starfield(self, w: int, h: int) -> list[list[tuple[str, Style | None]]]:
        """Base grid from the procedural `edge.art` starfield (seeded per sector)."""
        cells = art_adapter.text_to_cells(art_adapter.sprite(
            "starfield", "standard", seed=self.sec.sector_id ^ 0x5EED, width=w, height=h))
        grid: list[list[tuple[str, Style | None]]] = [[(" ", None)] * w for _ in range(h)]
        for y in range(min(h, len(cells))):
            for x in range(min(w, len(cells[y]))):
                ch, style = cells[y][x]
                if ch != " ":
                    grid[y][x] = (ch, style)
        return grid

    def _paint(self, rows: list[list[tuple[str, Style | None]]], top: int, left: int) -> None:
        for r, row in enumerate(rows):
            y = top + r
            if not 0 <= y < self._h:
                continue
            for c, (ch, style) in enumerate(row):
                x = left + c
                if ch != " " and 0 <= x < self._w:  # spaces stay transparent -> stars show
                    self._grid[y][x] = (ch, style)

    def _clear(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Blank the starfield in a region (an asteroid belt's rocks would otherwise
        interleave with the stars into one indistinguishable speckle)."""
        for y in range(max(0, y0), min(self._h, y1)):
            for x in range(max(0, x0), min(self._w, x1)):
                self._grid[y][x] = (" ", None)

    def _stamp_at(self, markup: str, row: int, x0: int) -> None:
        """Stamp one markup line at an exact position (blanks overwrite stars, so a
        star can't bleed through a space *inside* a word)."""
        if not 0 <= row < self._h:
            return
        line = art_adapter.text_to_cells(Text.from_markup(markup))[0:1]
        for c, (ch, style) in enumerate(line[0] if line else []):
            x = x0 + c
            if 0 <= x < self._w:
                self._grid[row][x] = (ch, style)

    def _stamp_center(self, markup: str, row: int, x0: int, span: int) -> None:
        """Stamp one markup line centred within the horizontal span [x0, x0+span)."""
        n = Text.from_markup(markup).cell_len
        self._stamp_at(markup, row, x0 + max(0, (span - n) // 2))

    def _sprite_cells(self, entity: str, subtype: str, *, seed: int, sw: int, sh: int,
                      facing: str = "right",
                      archetype_id: str | None = None,
                      treatment: str = "",
                      depletion: float = 0.0,
                      cloud_city: int = 0) -> list[list[tuple[str, Style | None]]]:
        art = art_adapter.sprite(
            entity, subtype, seed=seed, width=sw, height=sh, facing=facing,
            archetype_id=archetype_id, depletion=depletion, cloud_city=cloud_city)
        if treatment == "derelict":
            art.stylize("dim")
        elif treatment == "hostile":
            art.stylize("on dark_red")
        cells = self._crop(art_adapter.text_to_cells(art))
        # Every sprite the scene draws is logged with the box it was asked for and
        # the size it came back as — the pair that diagnoses a mis-scaled sprite.
        self.render_log.append(SpriteRender(
            entity=entity, subtype=subtype, seed=seed, box=(sw, sh),
            drawn=self._dims(cells), facing=facing, archetype_id=archetype_id))
        return cells

    @staticmethod
    def _crop(cells: list[list[tuple[str, Style | None]]]
              ) -> list[list[tuple[str, Style | None]]]:
        """Crop a sprite to its inked bounding box. Grammars render into the
        requested box with transparent padding around a possibly smaller drawing;
        placing and reserving that padding would fence off empty sky and starve
        later placements."""
        inked = [(y, x) for y, row in enumerate(cells)
                 for x, (ch, _) in enumerate(row) if ch != " "]
        if not inked:
            return []
        y0, y1 = min(y for y, _ in inked), max(y for y, _ in inked)
        x0, x1 = min(x for _, x in inked), max(x for _, x in inked)
        return [row[x0:x1 + 1] for row in cells[y0:y1 + 1]]

    @staticmethod
    def _dims(cells: list[list[tuple[str, Style | None]]]) -> tuple[int, int]:
        return max((len(r) for r in cells), default=0), len(cells)

    # --- free-sky bookkeeping ---------------------------------------------------

    def _reserve(self, x0: int, y0: int, x1: int, y1: int) -> None:
        self._occupied.append((x0, y0, x1, y1))

    def _is_free(self, x0: int, y0: int, x1: int, y1: int) -> bool:
        """True when the rect lies on-canvas and overlaps nothing already placed."""
        if x0 < 0 or y0 < 0 or x1 > self._w or y1 > self._h:
            return False
        return not any(x0 < ox1 and ox0 < x1 and y0 < oy1 and oy0 < y1
                       for ox0, oy0, ox1, oy1 in self._occupied)

    def _has_clearance(self, x0: int, y0: int, x1: int, y1: int,
                       pad_x: int, pad_y: int) -> bool:
        """`_is_free`, plus a standoff that is *clipped* at the canvas edge.

        Merely not overlapping is a weak test: two hulls a cell apart, or a ship
        alongside a station, still read as one crowded mass rather than two objects
        at different distances. Callers ask for real clearance and relax it only if
        the scene has no pocket that holds it.

        The standoff is clamped rather than required to fit, because the rect that
        must stay on-canvas is the *sprite's* — demanding six free columns to the
        left of a ship berthed against the screen edge would refuse the one place
        traffic reliably rides.
        """
        if not self._is_free(x0, y0, x1, y1):
            return False
        px0, py0 = max(0, x0 - pad_x), max(0, y0 - pad_y)
        px1, py1 = min(self._w, x1 + pad_x), min(self._h, y1 + pad_y)
        return not any(px0 < ox1 and ox0 < px1 and py0 < oy1 and oy0 < py1
                       for ox0, oy0, ox1, oy1 in self._occupied)

    def _tag(self, markup: str, rect: tuple[int, int, int, int],
             dest: str | None = None, ref: int | str | None = None) -> None:
        """Float a name tag in free sky against `rect`: centred just below first
        (the caption position the eye expects), then centred above, then beside —
        first fit wins; a crowded scene falls back to below-left, clipped. Tags
        carry the object's *name* only — status/ownership details live in the
        sidebar, not the scene."""
        n = Text.from_markup(markup).cell_len
        x0, y0, x1, y1 = rect
        cy = (y0 + y1) // 2
        below = min(max(0, (x0 + x1 - n) // 2), max(0, self._w - n))
        candidates = (
            (below, y1 + 1), (below, y0 - 1),
            (x1 + 2, cy), (x0 - n - 2, cy),
            (x0, y1 + 1),
        )
        for tx, ty in candidates:
            if self._is_free(tx - 1, ty, tx + n + 1, ty + 1):
                break
        else:
            tx = min(max(0, x0), max(0, self._w - n))
            ty = min(y1, self._h - 1)
        self._stamp_at(markup, ty, tx)
        self._reserve(tx, ty, tx + n, ty + 1)
        if dest is not None:
            self.hotspots.append((tx, ty, tx + n, ty + 1, dest, ref))

    def _scatter(self, glyph: str, style: Style, count: int,
                 rng: random.Random, top: int) -> None:
        """Sprinkle single glyphs through free sky (padded a cell so they never hug
        a sprite); each landing is reserved so later drops keep their distance."""
        placed = 0
        for _ in range(300):
            if placed >= count or self._w < 4 or self._h - top < 2:
                break
            x = rng.randrange(1, self._w - 1)
            y = rng.randrange(top, self._h - 1)
            if self._is_free(x - 1, y, x + 2, y + 1):
                self._grid[y][x] = (glyph, style)
                self._reserve(x, y, x + 1, y + 1)
                placed += 1

    # --- the scene ---------------------------------------------------------------

    def compose(self, w: int, h: int) -> Text:
        sec = self.sec
        self._w, self._h = w, h
        self.hotspots = []
        self._occupied = []
        self._deferred = []
        self.render_log = []
        self.sprite_rects = []
        self.station_reference = None
        self._belt_primary = False
        self._grid = self._starfield(w, h)

        # Header — sector + band, flavor, beacon; centred across the full width.
        title = f"[{sec.display_id}] {sec.region}" + (f" ({sec.band})" if sec.band else "")
        self._stamp_center(f"[b cyan]{title}[/]", 0, 0, w)
        self._stamp_center(f"[i #8a8a8a]░▒▓ {sec.flavor} ▓▒░[/]", 1, 0, w)
        row = 2
        if sec.beacon:
            self._stamp_center(f"[yellow]![/] {sec.beacon}", row, 0, w)
            row += 1
        hdr = row + 1  # one blank line under the header
        self._reserve(0, 0, w, hdr)
        body_h = h - hdr - 1

        # A sector with a visible discovery usually has no planet (bigbang keeps
        # space finds off planet sectors) — but a combat wreck can share a sector
        # with one, so a find beside a planet takes the secondary slot (PT-44).
        disc = None
        if sec.discoveries:
            disc = next((d for d in sec.discoveries if d.kind == "wormhole"),
                        sec.discoveries[0])

        # The scale chain keys off the *body budget* — the height a world would take
        # in this scene — not off whichever object happens to be primary. Keying off
        # the primary collapsed the whole scene whenever that primary was small: a
        # port-only sector scaled its ships to 20% of an 11-row station and drew them
        # at the 3-row stub, and a port beside a wormhole asked for a 4-row box and
        # got the bare mast. When a planet *is* present the two are the same number,
        # so the everyday arrival is unchanged.
        ref_h = primary_body_height(self.cfg, w, body_h)
        primary: tuple[int, int, int, int] | None = None
        planet_primary = False
        if sec.planets:
            primary = self._paint_planet(sec.planets[0], hdr, body_h)
            planet_primary = True
        elif disc is not None:
            primary = self._paint_discovery(disc, hdr, body_h, as_primary=True)
            disc = None
        # A *body* (planet or space find) owns the right of the scene, so traffic is
        # confined to the sky on its left. A station does not: it is small, and
        # confining ships to its left stranded them in a sliver with the rest of the
        # canvas empty ("ships shouldn't be on the same side with empty space on the
        # right", playtest 2026-08-15). With no body, ships get the whole width and
        # the occupancy map keeps them off the station. A belt is a field rather than
        # a body, so it behaves like the station case: traffic flies *through* it and
        # gets the whole canvas (`_paint_planet`).
        body = None if self._belt_primary else primary
        station = self._paint_station(primary if planet_primary else None,
                                      hdr, body_h, sky_left=primary)
        if primary is None:
            primary = station
        # The secondary find berths *before* the traffic. It is the one object with no
        # ladder to step down and only one shore it may take (`_paint_discovery`), so
        # placing it after the ships let three hulls occupy the left edge and drop the
        # wreck out of the picture into a text row. Going first also states the rule
        # the wreck's standoff exists for: live traffic keeps its distance from a
        # hulk, not the other way round.
        if disc is not None:
            self._paint_discovery(disc, hdr, body_h, as_primary=False)
        self._paint_ships(body, hdr, ref_h)
        self._paint_text_rows()
        self._paint_forces(hdr)

        out = Text()
        for y in range(h):
            for ch, style in self._grid[y]:
                out.append(ch, style=style)
            if y < h - 1:
                out.append("\n")
        return out

    def _paint_planet(self, planet: SectorPlanetDTO, hdr: int,
                      body_h: int) -> tuple[int, int, int, int]:
        """The world you've arrived at: a big disc anchored toward the right edge,
        allowed to crop a little rather than shrink to fit a layout box."""
        cfg, w, h = self.cfg, self._w, self._h
        sub = art_adapter.planet_subtype(planet.ptype)
        belt = sub in ("asteroid_belt", "asteroid")
        ph = primary_body_height(cfg, w, body_h, belt=belt)
        if belt:
            # A belt is a field, not a body: let it sprawl wide across the sky.
            pw = min(ph * 3, w - int(w * 0.3) - 1)
            left = max(int(w * 0.3), w - pw - 2)
        else:
            pw = ph * 2  # width locked to 2*height so the disc reads round
            # The disc rides well right of centre and is allowed to run off the
            # right edge — the world is the scene's subject, not a wing decoration,
            # and the sky to its left is one wide region where ships and the
            # station's tag breathe rather than two slivers.
            left = max(2, int(w * _PRIMARY_CENTRE) - pw // 2)
        top = hdr + max(0, (body_h - ph) // 3)
        # A worked belt visibly empties in the sector view too (PT-52) — same
        # sprite the orbit view draws, same rocks, fewer of them.
        mined = (1.0 - planet.ore_reserve / planet.ore_reserve_max
                 if planet.ore_reserve_max > 0 else 0.0)
        if belt:
            self._clear(left - 1, top, left + pw + 1, top + ph)
        # Seed off the planet's own id (not the sector's) so this sprite matches
        # the PlanetScreen orbit view — same planet, same art. A staged gas giant
        # flies its city (PT-54).
        self._paint(self._sprite_cells("planet", sub, seed=planet.planet_id,
                                       sw=pw, sh=ph, depletion=mined,
                                       cloud_city=planet.cloud_city_size), top, left)
        rect = (left, top, min(w, left + pw), min(h, top + ph))
        # A belt is a *field*, not a body: it is loose rock spread across the sky,
        # and things fly through it. Reserving its rect fenced off the two-thirds of
        # a wide canvas it sprawls over and crushed the port and both ships into the
        # strip beside it — every belt scene in the 2026-08-16 gallery pass came back
        # at the bottom of the ratings for exactly that ("use more of the space by
        # overlapping the asteroid field"). Only a solid body reserves; ships and the
        # port paint over the rocks, which is what flying through a belt looks like.
        # `_belt_primary` tells `compose` not to confine traffic to its left either.
        self._belt_primary = belt
        if not belt:
            self._reserve(*rect)
        self.sprite_rects.append(("belt" if belt else "planet", *rect))
        self._tag(f"[b yellow]{planet.name}[/]", rect, "planet", None)
        self.hotspots.append((*rect, "planet", None))
        return rect

    def _paint_station(self, primary: tuple[int, int, int, int] | None, hdr: int,
                       body_h: int, *,
                       sky_left: tuple[int, int, int, int] | None = None,
                       ) -> tuple[int, int, int, int] | None:
        """The port — or the starbase that takes its slot (§4.2, WP80). Beside a
        planet it hovers at the lower limb at ~half scale, overlapping the disc's
        bounding box a little so it reads as *at* the world; alone it is the scene's
        primary body and anchors right like a planet would.

        `primary` is the *scaling* anchor and is passed only for a planet: a station
        orbits a world, so it takes its size from one. Beside a space find it is on
        its own and sizes as a lone station — scaling it off a compact phenomenon
        asked for a 4-row box and drew the bare mast. `sky_left` is the *placement*
        anchor, which is any rendered primary including a find, so the station still
        berths beside whatever is actually there.
        """
        sec, cfg, w, h = self.sec, self.cfg, self._w, self._h
        bases = list(getattr(sec, "starbases", ()) or ())
        if not bases and not sec.ports:
            return None
        primary_height = ((primary[3] - primary[1]) if primary is not None else None)
        if bases:
            sw, sh = cfg.station_dimensions(
                "starbase", primary_height=primary_height, body_height=body_h)
        elif sec.ports[0].is_stardock:
            sw, sh = cfg.station_dimensions(
                "stardock", primary_height=primary_height, body_height=body_h)
        else:
            sw, sh = cfg.station_dimensions(
                "port", primary_height=primary_height, body_height=body_h)
        self.station_reference = (primary_height, body_h)
        if bases:
            b = bases[0]
            cells = self._sprite_cells("port", "starbase", seed=b.starbase_id,
                                       sw=sw, sh=sh, archetype_id=b.archetype_id,
                                       treatment=b.condition)
        else:
            port = sec.ports[0]
            # `is_stardock` is the authority, not the display label. The box above
            # is already chosen from the flag, so deriving the *art* from a
            # substring of `klass` lets the two disagree — and the failure is silent
            # and one-directional: the scene requests the 38x16 Stardock box, gets
            # `trading_port` (which tops out at 11x12), and the flagship reads as an
            # ordinary port. `port_subtype` still covers everything else.
            sub = ("stardock" if port.is_stardock
                   else art_adapter.port_subtype(port.klass))
            # The controlling species' palette (`archetype_id`) styles the sprite.
            cells = self._sprite_cells("port", sub,
                                       seed=sec.sector_id, sw=sw, sh=sh,
                                       archetype_id=port.archetype_id)
        cw, chh = self._dims(cells)
        berth = sky_left if sky_left is not None else primary
        if berth is not None:
            px0, py0, _px1, py1 = berth
            ph = py1 - py0
            # Low on the limb, not halfway up it: at 0.55 the station sat across the
            # body's middle and read as pinned to its face rather than orbiting
            # beneath it (playtest 2026-08-15, four scenes at standard tier).
            top = min(py0 + int(ph * _STATION_LIMB), h - chh - 1)
            left = max(1, px0 - cw + max(2, cw // 3))
        else:
            # A lone station has no world to pin it, so its berth varies from
            # sector to sector (seeded — the same sector always finds it in the
            # same place), instead of every empty port hanging at centre-right.
            prng = random.Random(sec.sector_id ^ 0x570A)
            left = prng.randint(max(2, w // 8), max(2, max(2, w - cw - 4)))
            top = prng.randint(hdr + 1, max(hdr + 1, h - chh - 3))
        self._paint(cells, top, left)
        rect = (left, top, min(w, left + cw), min(h, top + chh))
        self._reserve(*rect)
        self.sprite_rects.append(
            ("starbase" if bases else
             "stardock" if sec.ports[0].is_stardock else "port", *rect))
        if bases:
            b = bases[0]
            # Name only — status/owner/market live in the sidebar caption. Click
            # routes to the unified base view (§4.2, WP80): station, market,
            # services, assault/repair/claim all live there.
            self._tag(f"[b cyan]{b.name}[/]", rect, "starbase", b.starbase_id)
            self.hotspots.append((*rect, "starbase", b.starbase_id))
        else:
            self._tag(f"[b yellow]{sec.ports[0].name}[/]", rect, "port", None)
            self.hotspots.append((*rect, "port", None))
        return rect

    def _berths(self, i: int, n: int, cw: int, chh: int, sky_r: int, hdr: int,
                rng: random.Random, *, ceiling: int,
                confine: bool = True) -> Iterator[tuple[int, int]]:
        """Candidate anchorages for ship `i` of `n`, best first.

        The old rule was "first free row from the top wins", which is why a pair of
        ships always arrived stacked in the same column with the rest of the sky
        empty — ship 2 simply took the row under ship 1. Instead each ship gets its
        own **horizontal band** of the sky and its own **column offset**, jittered
        inside them, and only widens the search from there. Two ships therefore
        occupy different heights *and* different columns by construction, and a lone
        ship still drifts rather than sitting at a fixed mark.

        Yields positions outward from the assigned berth so a crowded scene
        degrades to "near where it wanted to be" instead of "top-left".

        The band is sized off the *whole* sky and the jitter is kept `_SHIP_BAND_GAP`
        rows clear of the next band's start. Jittering across the full band let two
        ships land on adjacent rows whenever one drew near the bottom of its band and
        the next near the top of its own — which is how a 52-row scene came back with
        the station and both hulls sharing four rows and forty rows of empty sky
        ("everything appears in one line horizontally", gallery pass 2026-08-16). The
        band also runs to the bottom of the scene rather than stopping a ship-height
        short of it, so the lowest berth actually reaches the lower canvas.

        `ceiling` is the row this ship must stay above — the top of the nearer ship
        already placed, since `_paint_ships` works nearest-first up the sky. It is what
        makes the vertical order *monotonic*, and the vertical order is what carries
        depth: the band index is also the ship's depth (§2.1), so a ship sized as the
        far one and then allowed to drift down past a nearer one renders the cue
        backwards — a big hull below a small one, which is what a crowded 87-column
        scene produced.

        `confine` additionally bars the search from leaving the band. It is relaxed by
        the caller as a last resort, because the station berthed at the primary's lower
        limb sits squarely in the near ship's band and pinning that ship inside the
        band merely shrank it; giving up the band still keeps the ceiling, so a
        wrong-band berth never costs the depth ordering.
        """
        w, h = self._w, self._h
        top0, bot0 = hdr + 1, h - 2
        span_x = max(1, min(sky_r, w - 1) - cw - 2)
        # Alternate outward/inward across the sky so consecutive ships never share a
        # column, then jitter within the ship's own slice of the width.
        frac = ((i * 2 + 1) % (2 * n)) / (2 * n)
        cx = 2 + int(span_x * frac) + rng.randrange(0, max(1, span_x // (2 * n) + 1))
        cx = max(2, min(2 + span_x, cx))
        span_y = max(1, bot0 - top0)
        # The lowest row this ship may start on: the canvas floor, or the nearer ship's
        # top less the band gap, whichever binds first.
        deck = max(top0, min(bot0, ceiling - _SHIP_BAND_GAP) - chh)
        lo = min(deck, top0 + span_y * i // n)
        # The last row the jitter may take and still leave the gap before the band
        # below it — and, for the lowest band, still clear `deck`.
        hi = min(deck, top0 + span_y * (i + 1) // n - _SHIP_BAND_GAP - chh)
        cy = lo + rng.randrange(0, max(1, hi - lo + 1))
        cy = max(top0, min(deck, cy))
        lim_lo, lim_hi = (lo if confine else top0), deck
        # Coarse offsets first — they keep a crowded scene from degenerating into a
        # row of near-identical berths — then a full fine sweep, because the coarse
        # list alone can step straight over the one pocket that fits. A third ship
        # squeezed between a port and a planet had exactly two candidate columns, both
        # under the port, and dropped out of the picture to a text row with clear sky
        # three columns to its left.
        offsets = (0, -3, 3, -8, 8, -15, 15, -24, 24,
                   *(d for k in range(1, span_x + 1) for d in (-k, k)))
        seen: set[tuple[int, int]] = set()
        for dy in range(0, span_y + 1):
            for sy in ((cy + dy, cy - dy) if dy else (cy,)):
                if not lim_lo <= sy <= lim_hi:
                    continue
                for dx in offsets:
                    sx = cx + dx
                    if not 2 <= sx <= 2 + span_x or (sx, sy) in seen:
                        continue
                    seen.add((sx, sy))
                    yield sx, sy

    def _paint_ships(self, primary: tuple[int, int, int, int] | None, hdr: int,
                     ref_h: int) -> None:
        """Up to N ships riding the open sky left of the primary body, each given its
        own berth rather than stacked at the first free row. Ships face the world
        they've arrived at; with nothing to face, the 2nd of a pair may face the 1st.

        `ref_h` is the scene's body budget (`primary_body_height`), not the primary's
        own height: traffic is traffic whatever it is parked next to, and scaling it
        off a small station or a compact find drew every ship at the 3-row stub.

        Ships are *not* all drawn at the same rung. `_berths` bands them down the sky
        by index, so the index doubles as a depth cue: the topmost ship is the
        furthest one and steps down the art ladder, the lowest draws the richest tier
        the sky allows. That is what stops a pair of hulls reading as a formation
        pasted on a flat backdrop, and it is also the only lever that keeps traffic
        from overpowering a station — station art tops out at 11–15 columns while a
        ship's top rung is 46, so scale parity has to come from the ship's side.

        Placement therefore runs **nearest-first, bottom-up**. The near hull claims the
        richest rung and the best berth; each further ship is then bounded on both
        axes of the cue at once — never lower than the ship below it (`ceiling`) and
        never wider than it (`cap_w`) — so the picture cannot come out with a big hull
        under a small one. Going far-first inverted it whenever the near ship had to
        step further down the ladder than the far one to fit at all.
        """
        sec, cfg, w, h = self.sec, self.cfg, self._w, self._h
        shown = sec.ships[:cfg.max_ships_shown]
        if not shown:
            return
        sh = max(cfg.ship.min_height, min(cfg.ship.max_height, round(ref_h * cfg.ship_scale)))
        sky_r = (primary[0] - 2) if primary is not None else w - 2
        # The height comes off the scale hierarchy; the *width* is whatever sky is
        # left, not a fixed aspect. Ship art composes along its length at roughly
        # 6:1, so imposing an aspect here picked a tier far wider than the box and
        # the library cropped the prow and drive off it. `generate_sprite` resolves
        # this box down to the richest tier that fits inside it — a narrow sky steps
        # a ship down a rung instead of shaving columns off the one above.
        sw = max(cfg.ship.min_width, min(cfg.ship.max_width, sky_r - 4))
        rng = random.Random(sec.sector_id)
        n = len(shown)
        # Bounds carried up the sky from the nearest ship: `ceiling` is the top row of
        # the last one placed, `cap_w` its drawn width. Together they hold the depth
        # cue — each further ship berths above and draws no wider.
        ceiling, cap_w = h, cfg.ship.max_width
        # Deferrals are collected rather than appended, so the text rows still read in
        # traffic order even though placement runs backwards.
        dropped: list[tuple[str, str | None, int | str | None]] = []
        for i in reversed(range(n)):
            vessel = shown[i]
            entity, sub = art_adapter.ship_entity(vessel.role, vessel.art_subtype)
            facing = "right"
            if primary is None and i == 1 and rng.random() < cfg.ship_face_inward_chance:
                facing = "left"
            # Depth: band 0 is the top of the sky and the furthest away, so it steps
            # the most rungs down; the lowest band keeps the full sky. A single ship
            # is never stepped — there is nothing for it to read as further *than*.
            steps = min(_SHIP_DEPTH_MAX_STEPS, n - 1 - i)
            # Only the sprite finally drawn stays in the render log, so the log keeps
            # describing the picture rather than every rung considered.
            log_mark = len(self.render_log)
            cells: list[list[tuple[str, Style | None]]] = []
            cw = chh = 0
            spot = None
            # Rungs, then clearance, then the band. A ship that will not fit its band
            # at the rung its depth calls for steps *further* down and tries the same
            # band again — the ladder is the mechanism for "not enough room", and
            # stepping down never breaks the cue because it only shrinks a ship that
            # is already above and no wider than its neighbour.
            for extra in range(_SHIP_FIT_STEPS):
                box_w, box_h = art_sprites.rung_below(
                    entity, sub, max_width=min(sw, cap_w), max_height=sh,
                    steps=steps + extra,
                    archetype_id=vessel.archetype_id, facing=facing)
                if box_w < cfg.ship.min_width:
                    continue
                del self.render_log[log_mark:]
                cells = self._sprite_cells(entity, sub, seed=sec.sector_id * 16 + i,
                                           sw=box_w, sh=box_h, facing=facing,
                                           archetype_id=vessel.archetype_id)
                cw, chh = self._dims(cells)
                # Widest standoff first: a ship that merely *fits* beside another
                # hull or a station still reads as crowding it. Relax only when the
                # scene has no pocket that holds the clearance.
                spot = next(
                    (p for pad_x, pad_y in _SHIP_STANDOFF
                     for p in self._berths(i, n, cw, chh, sky_r, hdr, rng,
                                           ceiling=ceiling)
                     if self._has_clearance(p[0], p[1], p[0] + cw, p[1] + chh,
                                            pad_x, pad_y)),
                    None)
                if spot is not None:
                    break
            if spot is None and cells:
                # Every rung failed inside the band. A berth in the wrong band still
                # beats dropping the ship out of the picture into a text row, so the
                # last pass gives up the band — but never the ceiling, so the depth
                # ordering survives even here.
                spot = next(
                    (p for pad_x, pad_y in _SHIP_STANDOFF
                     for p in self._berths(i, n, cw, chh, sky_r, hdr, rng,
                                           ceiling=ceiling, confine=False)
                     if self._has_clearance(p[0], p[1], p[0] + cw, p[1] + chh,
                                            pad_x, pad_y)),
                    None)
            cid = vessel.contact_id
            pid = getattr(vessel, "player_id", None)  # another player's ship (WP70)
            dest, ref = (("contact", cid) if cid is not None
                         else ("player", pid) if pid is not None else (None, None))
            if spot is None:
                # No free sky: the ship degrades to a text row rather than paint
                # over something already placed. It stays hailable either way.
                dropped.append((f"[white]>[/] {vessel.name}", dest, ref))
                continue
            left, top = spot
            self._paint(cells, top, left)
            rect = (left, top, min(w, left + cw), min(h, top + chh))
            ceiling, cap_w = top, cw
            self._reserve(*rect)
            self.sprite_rects.append(("ship", *rect))
            self._tag(vessel.name, rect, dest, ref)
            if dest is not None:
                self.hotspots.append((*rect, dest, ref))
        self._deferred.extend(reversed(dropped))

    def _paint_discovery(self, disc: SectorDiscovery, hdr: int, body_h: int, *,
                         as_primary: bool) -> tuple[int, int, int, int] | None:
        """A space find: the scene's primary body when the sector has no planet,
        else a small sprite in free sky beside the world — the wreck slot (PT-44)."""
        sec, cfg, w, h = self.sec, self.cfg, self._w, self._h
        if as_primary:
            if disc.kind == "nebula":
                # A nebula dwarfs a planet. Its soft SDF rim thins to nothing well
                # inside the requested box (the crop then trims the blank margin),
                # so the box is oversized well past the body for the *visible* cloud
                # to land at planet scale; the paint clips to the canvas. The height
                # multiplier drives how much cloud survives the crop — at 1.4 the
                # visible band came back squat ("nebula too flat", playtest
                # 2026-08-15), because the rim faded within a box only half again
                # the body.
                dh = max(6, int(body_h * 1.9))
                dw = min(dh * 3, w + w // 3)
            else:
                # A compact phenomenon is still the thing you came to look at, so it
                # takes most of the body budget — under a planet's 0.9, not the 0.6
                # that left a wormhole 15 rows tall in a 25-row sky.
                dh = max(4, min(cfg.planet.max_height,
                                int(primary_body_height(cfg, w, body_h) * _FIND_PRIMARY)))
                dw = dh * 2
        else:
            # A secondary find grows with the scene like everything else — a hulk
            # pinned at six rows read as a token on a 52-row canvas ("the wreck could
            # be larger", gallery pass 2026-08-16). The cap keeps it well under the
            # world it is parked beside, so the §1 ordering is untouched.
            dh = max(3, min(_FIND_SECONDARY_MAX, body_h // 4))
            dw = dh * 2 + 2
        cells = self._sprite_cells("discovery", disc.kind, seed=sec.sector_id,
                                   sw=dw, sh=dh)
        cw, chh = self._dims(cells)
        if disc.kind == "wormhole" and disc.warp_to is not None:
            dest: str = "wormhole"
            ref: int | str | None = disc.warp_to  # click warps to the far side
        else:
            dest, ref = "discovery", disc.discovery_id  # click scans/salvages
        # No caption until scanned — a sensor sweep (sidebar/Z) reveals the
        # identity; a hulk is plainly a hulk, so a wreck wears its name (PT-49).
        named = disc.collected or disc.kind == "wreck"
        if as_primary:
            # Same anchor as a planet primary: well right of centre, free to run
            # off the edge, so the sky it leaves is one coherent region.
            left = max(2, int(w * _PRIMARY_CENTRE) - cw // 2)
            top = hdr + max(0, (body_h - chh) // 3)
        else:
            # A wreck is something bases and ships keep their distance from: it
            # berths hard against the screen's left edge, as low as it can, with as
            # wide a standoff as that berth allows.
            #
            # The **row is the primary key** and the standoff the tiebreak. Searching
            # standoff-first instead put the hulk wherever the widest clearance
            # happened to be — mid-height on a crowded 67-column scene, which both
            # reads wrong (§3: the hulk gets the lower shore) and eats the middle
            # band the traffic needs. The wide standoff also matters less than it did:
            # ships now enforce their own clearance from everything (`_SHIP_STANDOFF`),
            # so keeping traffic off the hulk no longer rests on the hulk's rect alone.
            spot = None
            for t in range(h - chh - 2, hdr, -1):
                for padx, pady in ((14, 5), (8, 3), (4, 2), (1, 1)):
                    if self._is_free(0, max(0, t - pady),
                                     min(w, 1 + cw + padx),
                                     min(h, t + chh + pady)):
                        spot = (1, t)
                        break
                if spot is not None:
                    break
            if spot is None:
                # No free sky beside the planet: the find degrades to a text row.
                label = (disc.name or disc.label) if named else "unresolved anomaly"
                self._deferred.append((f"[b cyan]◦ {label}[/]", dest, ref))
                return None
            left, top = spot
        self._paint(cells, top, left)
        rect = (left, top, min(w, left + cw), min(h, top + chh))
        self._reserve(*rect)
        self.sprite_rects.append(("discovery", *rect))
        if named:
            # Name only (kind/rarity are the sidebar's story; the sprite shows
            # what it is) — falling back to the label for a nameless legacy row.
            self._tag(f"[b cyan]{disc.name or disc.label}[/]", rect, dest, ref)
        self.hotspots.append((*rect, dest, ref))
        return rect

    def _paint_text_rows(self) -> None:
        """Overflow ships beyond the sprite cap (still hailable) and the roaming
        Entity's presence hint (§7, WP35 — hailable only once sensors resolve it,
        fog-safe: never named), as text rows filled upward from the bottom."""
        sec, cfg, w, h = self.sec, self.cfg, self._w, self._h
        lines: list[tuple[str, str | None, int | str | None]] = list(self._deferred)
        for vessel in sec.ships[cfg.max_ships_shown:]:
            cid = vessel.contact_id
            pid = getattr(vessel, "player_id", None)
            dest, ref = (("contact", cid) if cid is not None
                         else ("player", pid) if pid is not None else (None, None))
            lines.append((f"[white]>[/] {vessel.name}", dest, ref))
        anomaly = getattr(sec, "anomaly", None)
        if anomaly is not None:
            # Presence only — whether it can be hailed is the sidebar's story.
            style = "b gold1" if anomaly.contactable else "gold3"
            lines.append((f"[{style}]✶ {anomaly.label}[/]",
                          "contact" if anomaly.contactable else None,
                          anomaly.contact_id if anomaly.contactable else None))
        row = h - 1
        for markup, dest, ref in lines:
            n = min(w, Text.from_markup(markup).cell_len + 2)
            while row > 0 and not self._is_free(0, row, n, row + 1):
                row -= 1
            if row <= 0:
                break
            self._stamp_at(markup, row, 1)
            self._reserve(0, row, n, row + 1)
            if dest is not None:
                self.hotspots.append((0, row, n, row + 1, dest, ref))
            row -= 1

    def _paint_forces(self, hdr: int) -> None:
        """Deployed forces as glyph-scale presence marks — fighters flying patrol
        through the open sky, mines seeded near the bodies. Counts, mode, and toll
        live in the sidebar; here density alone hints at strength (capped). The
        projection already applied classic-TW fog: fighters are public, foreign
        mines arrived zeroed."""
        force = getattr(self.sec, "force", None)
        if force is None:
            return
        if force.fighters > 0:
            style = Style.parse("bold green" if force.yours else "bold red")
            self._scatter("▴", style, min(6, 1 + force.fighters // 25),
                          random.Random(self.sec.sector_id ^ 0xF167), hdr)
        if force.armid_mines or force.limpet_mines:  # own eyes only (fog)
            self._scatter("✺", Style.parse("bold orange3"),
                          min(5, 1 + (force.armid_mines + force.limpet_mines) // 8),
                          random.Random(self.sec.sector_id ^ 0x313E5), hdr)


class SectorScene(Static):
    """The whole sector composited into one grid as an arrival view (UI_MOCKUPS.md §1).

    One Static because a terminal cell holds a single glyph and Textual does not
    blend overlapping widgets/layers — compositing everything over the starfield
    here is the only way to show stars *behind* the sprites (their negative-space
    cells stay transparent). The layout itself lives in `_SceneComposer`; this
    widget feeds it the widget size and routes its hotspot rects as
    ``ClickableEntry.Picked`` (mirroring the keys).
    """

    DEFAULT_CSS = """
    SectorScene { width: 1fr; height: 1fr; background: transparent; }
    """

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

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 8 or h < 6:
            self._hotspots = []
            return Text("")
        composer = _SceneComposer(self._sector, self._scene_cfg())
        out = composer.compose(w, h)
        self._hotspots = composer.hotspots
        if composer.station_reference is not None:
            primary_height, body_height = composer.station_reference
            self.app.sector_station_reference = (  # type: ignore[attr-defined]
                self._sector.sector_id, primary_height, body_height)
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

    @property
    def selected_sector(self) -> int | None:
        """Internal id of the keyboard-highlighted sector, or None when empty."""
        return self._hits[self._idx].sector_id if self._hits else None

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
        """5 right-aligned trail lines: header, up to 3 history entries, you.

        Each crumb's id is tinted by its distance band with the same `BAND_COLOR` the
        rose cells use (PT-55), so the trail and the rose read as one palette; an unknown
        band falls back to dim.
        """
        col: list[Text] = [Text() for _ in range(5)]
        col[0] = Text("trail", style="dim")
        # Last ≤3 trail entries fill rows 1–3, packed toward the bottom.
        recent = self._nav.trail[-3:]
        start = 4 - len(recent)
        for i, crumb in enumerate(recent):
            col[start + i] = Text(str(crumb.display_id), style=BAND_COLOR.get(crumb.band) or "dim")
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
        # A one-way warp to an uncharted sector masks its destination id as `S?????` (PT-48)
        # — you know there's a one-way exit, not where it leads until you take it.
        addr = warp.address_label if warp is not None else str(node.display_id)
        hdr.append(addr, style="bold")
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
