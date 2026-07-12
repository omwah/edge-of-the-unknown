"""StarDockScreen — the services hub, wired to the live service (UI_MOCKUPS.md §5).

The Commodities tab reuses `PortScreen`'s `TradePanel` (so `T` trades there too);
the **Hardware** tab sells engine-room components by tier and the **Shipyard** tab
sells hulls (trade-in adjusted) — `B` buys the highlighted row of the active tab,
reading the fog-of-war `stardock_view` catalog (DESIGN §8, §11). The **Bank** tab
deposits/withdraws by typed amount (`D`/`W`; interest accrues on the daily cron)
and the **Tavern** sells rumours and hosts the noticeboard (WP58). Buy a
component here, then slot it in the Engine Room (`E`).
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.events import Resize
from textual.screen import Screen
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Input, Static, TabbedContent
from textual.widgets.data_table import RowDoesNotExist

from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.enums import Component, ComponentTier
from edge.core.rules import (
    BuyComponent, BuyDevice, BuyFighters, BuyGenesis, BuyMines, BuyMissiles, BuyRumor,
    BuyShip, Deposit, PostNotice, RecruitColonists, Withdraw,
)
from edge.art.concourse import render_stardock_art
from edge.server.service import GameService
from edge.tui import art_adapter
from edge.tui.amount_stepper import AmountStepper
from edge.tui.chrome import AmountPrompt, EmptyState, TextPrompt, notify_warning
from edge.tui.screens.engine_room import EngineRoomScreen
from edge.tui.screens.port import _haggle_highlighted, _trade_highlighted
from edge.tui.widgets import ServiceHub, TradePanel


# Text-only failure fallback for missing assets or Chafa. The generated raster is
# normally converted through edge.art.concourse; compact 80×24 hides decorative art.
_CONCOURSE_ART = (
    "[dim]╭──────────────── ORBITAL CONCOURSE ────────────────╮[/]\n"
    "[dim]│[/]  [cyan]▟▙[/]   [cyan]▟▙[/]    [yellow]☺ ☺  ☺[/]   [cyan]▟▙[/]   [cyan]▟▙[/]  [dim]│[/]\n"
    "[dim]│[/]  [cyan]██[/]   [cyan]██[/]   [yellow]☺  ☺ ☺ ☺[/]  [cyan]██[/]   [cyan]██[/]  [dim]│[/]\n"
    "[dim]╰────────  colonists throng the promenade  ─────────╯[/]"
)


class _StarDockServiceArt(Static):
    """Theme- and breakpoint-aware Chafa panel with a text-only fallback."""

    def __init__(self, tab: str) -> None:
        super().__init__(_CONCOURSE_ART, classes="service-art")
        self._tab = tab

    def on_mount(self) -> None:
        self.app.theme_changed_signal.subscribe(self, lambda _theme: self._refresh_art())
        self._refresh_art()

    def on_resize(self, _event: Resize) -> None:
        self._refresh_art()

    def _refresh_art(self) -> None:
        cinematic = getattr(getattr(self.app, "layout_tier", None), "value", "standard") == "wide"
        try:
            self.update(render_stardock_art(self._tab, str(self.app.theme), cinematic=cinematic))
        except (ImportError, OSError, ValueError):
            self.update(_CONCOURSE_ART)


class _DockStructureArt(Static):
    """Responsive StarDock silhouette paired with each service banner."""

    def __init__(self, sector_id: int, archetype_id: str | None) -> None:
        super().__init__(classes="dock-structure-art")
        self._sector_id = sector_id
        self._archetype_id = archetype_id

    def on_mount(self) -> None:
        self._refresh_art()

    def on_resize(self, _event: Resize) -> None:
        self._refresh_art()

    def _refresh_art(self) -> None:
        wide = getattr(getattr(self.app, "layout_tier", None), "value", "standard") == "wide"
        width, height = (36, 12) if wide else (24, 8)
        self.update(art_adapter.sprite(
            "port", "stardock", seed=self._sector_id, width=width, height=height,
            archetype_id=self._archetype_id,
        ))


class StarDockScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "back", "Undock"),
        Binding("t", "trade", "Trade"),
        Binding("h", "haggle", "Haggle"),
        Binding("b", "buy", "Buy"),
        Binding("e", "engine_room", "Engine room"),
        # Tab-scoped actions (WP-PR08 / PT-04/05): `check_action` hides each unless its
        # tab is active, so a footer hint never implies an action on the wrong tab.
        Binding("k", "recruit", "Recruit"),
        Binding("r", "buy_rumor", "Rumor"),
        Binding("n", "post_notice", "Notice"),
        Binding("d", "deposit", "Deposit"),
        Binding("w", "withdraw", "Withdraw"),
        # Tab-focus accelerators (WP-PR2-01 / PT-32): jump to a tab and focus its
        # primary content in one step. Letters are emphasised in the tab titles and
        # kept off the footer (show=False). Bank has no free in-title letter under the
        # action bindings above, so it stays arrow/Enter-reachable.
        Binding("c", "focus_tab('trade')", "Commodities", show=False),
        Binding("s", "focus_tab('shipyard')", "Shipyard", show=False),
        Binding("a", "focus_tab('hardware')", "Hardware", show=False),
        Binding("m", "focus_tab('devices')", "Devices", show=False),
        Binding("o", "focus_tab('colonists')", "Colonists", show=False),
        Binding("v", "focus_tab('tavern')", "Tavern", show=False),
    ]

    # entry_id -> the letter emphasised in its tab title (WP-PR2-01 / PT-32).
    _TAB_ACCEL = {"trade": "c", "shipyard": "s", "hardware": "a",
                  "devices": "m", "colonists": "o", "tavern": "v"}

    HELP_TITLE = "StarDock"
    HELP = """\
[b]B[/] buys the highlighted row of the active buy tab (Hardware · Shipyard ·
Devices & Armaments — munitions there prompt for a quantity). Tab-scoped keys only
work on their tab: [b]K[/] recruits on Colonists, [b]D[/]/[b]W[/] bank on Bank,
[b]R[/]/[b]N[/] buy rumours / post notices on the Tavern. The bank pays daily interest.

Jump to a tab and focus its contents with the [b]underlined letter[/] in each tab
title ([b]C[/]ommodities · [b]S[/]hipyard · H[b]a[/]rdware · Devices & Ar[b]m[/]aments ·
C[b]o[/]lonists · Ta[b]v[/]ern); Enter on the tab rail does the same for the active tab."""

    CSS = """
    StarDockScreen #dock-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    StarDockScreen .service-art-header {
        height: 8; margin-bottom: 1; content-align: left top;
    }
    StarDockScreen .dock-structure-art {
        width: 24; height: 8; margin-right: 1; content-align: left top;
    }
    StarDockScreen TabPane { padding: 1 2; }
    StarDockScreen .note { color: $text-muted; margin-top: 1; }
    StarDockScreen DataTable { height: auto; max-height: 18; }
    StarDockScreen .service-art { width: 56; height: 8; content-align: left top; }
    StarDockScreen Button { margin-top: 1; margin-right: 1; }
    StarDockScreen .recruit-row { height: auto; margin-top: 1; }
    StarDockScreen .recruit-row Button { margin-top: 0; }
    StarDockScreen.compact .service-art-header { display: none; }
    StarDockScreen.compact TabPane { padding: 0 1; }
    StarDockScreen.compact DataTable { max-height: 10; }
    StarDockScreen.wide .service-art-header { height: 12; }
    StarDockScreen.wide .dock-structure-art { width: 36; height: 12; }
    StarDockScreen.wide .service-art { width: 72; height: 12; }
    """

    # Buy tabs whose table cursor we preserve across a screen rebuild.
    _BUY_TABLES = {"hardware": "#hardware-table", "shipyard": "#shipyard-table",
                   "devices": "#devices-table"}

    def __init__(self, service: GameService, player_id: int, initial_tab: str = "trade",
                 initial_key: str | None = None) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id
        self._initial_tab = initial_tab
        self._initial_key = initial_key  # stable row key to re-highlight (WP-PR08), not an index

    def compose(self) -> ComposeResult:
        port = self._service.current_port_view(self._pid)
        if port is None:
            yield Static("No StarDock here.", id="dock-title")
            yield Footer()
            return
        dock = self._service.stardock_view(self._pid)
        latinum = dock.latinum
        yield Static(f"STARDOCK · Sector {dock.sector_display}", id="dock-title")
        trade = Vertical(
                self._service_art_header("commodities", port),
                TradePanel(port, latinum=latinum, show_title=False))
        shipyard = Vertical(
                self._service_art_header("shipyard", port),
                Static(
                    f"[b]SHIPYARD[/]        Latinum [b yellow]{latinum:,}[/] slips        "
                    "[dim]net price shown after trade-in[/]"
                ), self._shipyard_table(dock),
                Static("[dim]B buys the highlighted hull (your parts return loose).[/]",
                       classes="note"))
        hardware = Vertical(
                self._service_art_header("hardware", port),
                Static(
                    f"[b]HARDWARE EMPORIUM[/]        Latinum [b yellow]{latinum:,}[/] slips"
                ), self._hardware_table(dock),
                Static("[dim]B buys the highlighted part; slot it in the Engine Room (E). "
                       "Tier III is barter-only.[/]", classes="note"))
        devices = Vertical(
                self._service_art_header("devices", port),
                Static(f"[b]DEVICES & ARMAMENTS[/]        Latinum [b yellow]{latinum:,}[/] slips"),
                self._devices_table(dock),
                Static("[dim]B buys the highlighted row — munitions (missiles / fighters / "
                       "mines) prompt for a quantity; devices and the Genesis torpedo buy one. "
                       "Deploy them from the game screen's Deploy (D).[/]", classes="note"))
        colonists = Vertical(*list(self._colonist_panels(dock, port)))
        rate = dock.interest_per_day * 100
        bank = Vertical(
                self._service_art_header("bank", port),
                Static(
                    f"[b]BANK OF THE CORE[/]\n\n"
                    f"On hand   [b yellow]{latinum:,}[/] slips\n"
                    f"Banked    [b green]{dock.bank_balance:,}[/] slips\n\n"
                    f"[dim]Interest: {rate:.2g}%/day, compounded on the daily clock.[/]"
                ),
                Static("[dim][b]D[/] Deposit an amount   ·   [b]W[/] Withdraw an amount[/]",
                       classes="note"))
        tavern = Vertical(self._service_art_header("tavern", port), *list(self._tavern_panels()))
        entries = [
            ("Commodities", "trade", trade, None),
            ("Shipyard", "shipyard", shipyard, None),
            ("Hardware", "hardware", hardware, None),
            ("Devices & Armaments", "devices", devices, None),
            ("Colonists", "colonists", colonists, None),
            ("Bank", "bank", bank, None),
            ("Tavern", "tavern", tavern, None),
        ]
        yield ServiceHub(entries, initial=self._initial_tab, accelerators=self._TAB_ACCEL,
                         id="stardock-services")
        yield Footer()

    def _tavern_panels(self) -> ComposeResult:
        """Rumors, the bounty board, and the noticeboard (§14, WP58)."""
        tav = self._service.tavern_view(self._pid)
        buyable = ("[green]a fresh rumour is on offer[/]" if tav.rumor_available
                   else "[dim]no fresh rumours right now[/]")
        yield Static(f"[b]TAVERN[/]        rumour: [yellow]{tav.rumor_price:,}[/] slips — {buyable}")
        yield Static("[dim]R buys a rumour (logs a lead).  N posts a notice.[/]", classes="note")
        yield Static("[b]BOUNTY BOARD[/]")
        if tav.bounties:
            board: DataTable[Any] = DataTable(id="bounty-table", cursor_type="row")
            board.add_columns("Target", "Type", "Reward / threat", "Where")
            for b in tav.bounties:
                icon = {"open": "[green]●[/]", "danger": "[red]▲[/]", "info": "[cyan]◆[/]"}.get(b.status, "")
                kind = {"kill": "Bounty", "hunts_you": "Hunts you", "governance": "Notice"}.get(b.kind, b.kind)
                where = f"({b.sector_display})" if b.sector_display is not None else "—"
                board.add_row(f"{icon} {b.target}", kind, b.reward or b.detail, where,
                              key=f"bounty:{b.target}:{b.kind}")
            yield board
            # Full prose for the highlighted bounty (WP-PR08): the structured rows scan fast,
            # the detail panel keeps the voiced line that a single-column list used to carry.
            first = tav.bounties[0]
            yield Static(f"[dim]{first.detail}[/]", id="bounty-detail", classes="note")
            yield Static("[dim]● bounty to collect   ▲ danger to you   ◆ notice[/]", classes="note")
        else:
            yield EmptyState("The board is quiet.",
                             "Bounties post here when raids put a price on someone.")
        yield Static("[b]NOTICEBOARD[/]")
        if tav.notices:
            notices: DataTable[Any] = DataTable(id="notices-table", cursor_type="row")
            notices.add_columns("Day", "By", "Notice")
            for n in tav.notices:
                notices.add_row(f"d{n.day}", n.author, n.text)
            yield notices
        else:
            yield EmptyState("Nothing pinned yet.",
                             "[b]N[/] posts a notice every visitor will read.")

    def on_mount(self) -> None:
        # Restore the highlighted row on the buy tab we rebuilt from (see _issue) by its
        # *stable key* (WP-PR08), so repeated purchases keep the same item highlighted even
        # if the catalog reorders — never by a bare row index.
        table_id = self._BUY_TABLES.get(self._initial_tab)
        if table_id is None or self._initial_key is None:
            return
        table = self.query_one(table_id, DataTable)
        try:
            index = table.get_row_index(self._initial_key)
        except RowDoesNotExist:  # row gone (e.g. hull now owned / last of stock)
            return
        table.move_cursor(row=index, animate=False)
        # Return keyboard focus to the table too, not just its cursor — otherwise a
        # rebuild after a purchase leaves focus on the tab rail (PT-33). Deferred so it
        # wins over the screen's default initial focus.
        self.call_after_refresh(table.focus)

    def _hardware_table(self, dock: object) -> DataTable[Any]:
        table: DataTable[Any] = DataTable(id="hardware-table", cursor_type="row")
        table.add_columns("Component", "Tier", "Price", "")
        for item in dock.hardware:  # type: ignore[attr-defined]
            mark = "" if item.affordable else "[red]✗[/]"
            table.add_row(item.component, item.tier, f"{item.price:,}", mark,
                          key=f"{item.component}:{item.tier}")
        return table

    def _devices_table(self, dock: object) -> DataTable[Any]:
        table: DataTable[Any] = DataTable(id="devices-table", cursor_type="row")
        table.add_columns("Item", "Carried", "Price", "")
        for item in dock.armaments:  # type: ignore[attr-defined]
            mark = "" if item.affordable else "[red]✗[/]"
            unit = " ea" if item.amount_based else ""
            table.add_row(item.label, f"{item.carried:,}", f"{item.price:,}{unit}", mark, key=item.id)
        return table

    def _service_art_header(self, tab: str, port: object) -> Horizontal:
        """Left-aligned StarDock silhouette + the active service's ANSI banner."""
        return Horizontal(
            _DockStructureArt(port.sector_id, port.archetype_id),  # type: ignore[attr-defined]
            _StarDockServiceArt(tab),
            classes="service-art-header",
        )

    def _colonist_panels(self, dock: object, port: object) -> ComposeResult:
        """The recruitment office (§4.2, WP-PR08 / PT-06): berth occupancy + a recruit control."""
        d = dock
        free = max(0, d.ship_colonist_capacity - d.ship_colonists)  # type: ignore[attr-defined]
        yield self._service_art_header("concourse", port)
        yield Static(
            f"[b]RECRUITMENT OFFICE[/]        Latinum [b yellow]{d.latinum:,}[/] slips\n\n"  # type: ignore[attr-defined]
            f"Berths    [b]{d.ship_colonists:,}[/] / {d.ship_colonist_capacity:,}  "  # type: ignore[attr-defined]
            f"([green]{free:,}[/] free)\n"
            f"Incentive [yellow]{d.colonist_incentive:,}[/] slips per head\n"  # type: ignore[attr-defined]
            f"Afford    up to [b]{d.colonists_recruitable:,}[/] more right now")  # type: ignore[attr-defined]
        yield Static("[dim]Colonists are recruited, not bought — they ride their own berths, "
                     "not cargo holds. Settle them onto a world you own from its orbit view.[/]",
                     classes="note")
        yield Horizontal(
            AmountStepper("recruit", step=10, maximum=d.colonists_recruitable),  # type: ignore[attr-defined]
            Button("Recruit", id="btn-recruit", variant="primary"),
            Button("Recruit all", id="btn-recruit-all"),
            classes="recruit-row",
        )

    def _shipyard_table(self, dock: object) -> DataTable[Any]:
        table: DataTable[Any] = DataTable(id="shipyard-table", cursor_type="row")
        table.add_columns("Hull", "Role", "Holds", "Shld", "Wrp", "Cbt", "Net", "")
        for item in dock.shipyard:  # type: ignore[attr-defined]
            # "Flying" = the hull you occupy now; "Flown" = one you flew and traded away
            # (PT-34). Neither is purchasable; the rest show affordability.
            if item.owned:
                flag = "[green]Flying[/]"
            elif item.flown:
                flag = "[cyan]Flown[/]"
            else:
                flag = "" if item.affordable else "[red]✗[/]"
            table.add_row(item.name, item.role, str(item.holds), str(item.shields),
                          str(item.warp), str(item.combat), f"{item.net_price:,}", flag,
                          key=item.class_id)
        return table

    # --- actions -------------------------------------------------------------

    def action_focus_tab(self, entry_id: str) -> None:
        """Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)."""
        self.query_one(ServiceHub).activate_and_focus(entry_id)

    def action_trade(self) -> None:
        _trade_highlighted(self, self._service, self._pid)

    def action_haggle(self) -> None:
        _haggle_highlighted(self, self._service, self._pid)

    def action_buy(self) -> None:
        active = self.query_one(TabbedContent).active
        if active == "hardware":
            self._buy_component()
        elif active == "shipyard":
            self._buy_ship()
        elif active == "devices":
            self._buy_armament()
        else:
            self.notify("Switch to the Hardware, Shipyard, or Devices & Armaments tab to buy.",
                        timeout=2)

    # --- tab scoping (PT-04/05): footer + bindings track the active tab ----------

    _TAB_SCOPED = {
        "buy_rumor": "tavern", "post_notice": "tavern",
        "deposit": "bank", "withdraw": "bank", "recruit": "colonists",
    }

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        want = self._TAB_SCOPED.get(action)
        if want is None:
            return True
        try:
            return self.query_one(TabbedContent).active == want
        except NoMatches:
            return True  # before mount — keep the binding until the tab is known

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        # Re-evaluate the scoped bindings so the footer only advertises what this tab allows.
        self.refresh_bindings()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # Mirror the highlighted bounty's full prose into the detail panel (WP-PR08).
        if event.data_table.id != "bounty-table":
            return
        key = event.row_key.value or ""
        bounty = next((b for b in self._service.tavern_view(self._pid).bounties
                       if f"bounty:{b.target}:{b.kind}" == key), None)
        if bounty is not None:
            try:
                self.query_one("#bounty-detail", Static).update(f"[dim]{bounty.detail}[/]")
            except NoMatches:
                pass

    def _buy_component(self) -> None:
        table = self.query_one("#hardware-table", DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key.value is None:
            return
        component, tier = row_key.value.split(":")
        self._issue(BuyComponent(Component(component), ComponentTier[tier]), f"Bought {component}")

    # --- Colonists tab (PT-06) ---------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-recruit-all":
            self._recruit_up_to(self._service.stardock_view(self._pid).colonists_recruitable)
        elif event.button.id == "btn-recruit":
            self._recruit_entered_amount()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "amt-recruit":
            self._recruit_entered_amount()

    def action_recruit(self) -> None:
        """Focus the inline exact-amount recruitment editor."""
        recruitable = self._service.stardock_view(self._pid).colonists_recruitable
        if recruitable <= 0:
            self.notify("No free berths or not enough latinum to recruit.", timeout=2)
            return

        self.query_one("#amt-recruit", Input).focus()

    def _recruit_entered_amount(self) -> None:
        count = self.query_one("#stepper-recruit", AmountStepper).amount
        self._recruit_up_to(count)

    def _recruit_up_to(self, count: int) -> None:
        if count <= 0:
            self.notify("No free berths or not enough latinum to recruit.", timeout=2)
            return
        self._issue(RecruitColonists(count=count), f"Recruited {count:,} colonists")

    # --- Devices & Armaments tab (PT-02) -----------------------------------------

    def _buy_armament(self) -> None:
        """Buy the highlighted armament/device row; amount-based rows prompt for a quantity."""
        table = self.query_one("#devices-table", DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key.value is None:
            return
        item = next((a for a in self._service.stardock_view(self._pid).armaments
                     if a.id == row_key.value), None)
        if item is None:
            return
        if not item.amount_based:
            command = BuyGenesis() if item.kind == "genesis" else BuyDevice(item.id)
            self._issue(command, f"Bought {item.label.lower()}")
            return

        def _go(count: int | None) -> None:
            if not count:
                return
            cmd = {"missile": BuyMissiles, "fighter": BuyFighters, "mine": BuyMines}[item.kind](count=count)
            self._issue(cmd, f"Bought {count:,} {item.label.lower()}")
        self.app.push_screen(_AmountInput(f"Buy how many {item.label.lower()}?"), _go)

    def _buy_ship(self) -> None:
        table = self.query_one("#shipyard-table", DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key.value is None:
            return
        # PT-29: the currently flown hull is shown for comparison but cannot be bought —
        # explain here without rebuilding the screen (the reducer also rejects it).
        item = next((s for s in self._service.stardock_view(self._pid).shipyard
                     if s.class_id == row_key.value), None)
        if item is not None and item.owned:
            self.notify("You already fly this hull.", timeout=2)
            return
        self._issue(BuyShip(row_key.value), f"Acquired {row_key.value}")

    def _issue(self, command: object, ok: str) -> None:
        try:
            self._service.apply(self._pid, command)  # type: ignore[arg-type]
        except (EconomyError, EngineRoomError) as exc:
            notify_warning(self, str(exc))
            return
        self.notify(ok, timeout=2)
        active = self.query_one(TabbedContent).active
        key: str | None = None
        if active in self._BUY_TABLES:
            table = self.query_one(self._BUY_TABLES[active], DataTable)
            if table.row_count:
                key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        self.app.pop_screen()
        self.app.push_screen(
            StarDockScreen(self._service, self._pid, initial_tab=active, initial_key=key))

    def action_deposit(self) -> None:
        """Prompt for an amount and bank it (§8 — surfaced WP71)."""
        def _go(amount: int | None) -> None:
            if amount:
                self._issue(Deposit(amount=amount), f"Deposited {amount:,} slips")
        self.app.push_screen(_AmountInput("Deposit how many slips?"), _go)

    def action_withdraw(self) -> None:
        """Prompt for an amount and withdraw it from the bank (§8 — surfaced WP71)."""
        def _go(amount: int | None) -> None:
            if amount:
                self._issue(Withdraw(amount=amount), f"Withdrew {amount:,} slips")
        self.app.push_screen(_AmountInput("Withdraw how many slips?"), _go)

    def action_buy_rumor(self) -> None:
        """Buy a rumour at the tavern — logs a coordinate lead (§14, WP58)."""
        self._issue(BuyRumor(), "A rumour points the way — lead logged")

    def action_post_notice(self) -> None:
        """Prompt for a noticeboard message and pin it (§14, WP58)."""
        def _post(text: str | None) -> None:
            if text:
                self._issue(PostNotice(text=text), "Notice pinned")
        self.app.push_screen(_NoticeInput(), _post)

    def action_engine_room(self) -> None:
        self.app.push_screen(EngineRoomScreen(
            self._service.engine_room_view(self._pid), self._service, self._pid))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)


class _AmountInput(AmountPrompt):
    """A one-line numeric prompt for a latinum amount (§8 — the WP71 bank tab).

    WP-UI07: a shared `FieldPrompt` — invalid amounts hold the form open with an
    inline reason instead of silently dismissing with None.
    """


class _NoticeInput(TextPrompt):
    """A one-line text prompt (noticeboard §14 WP58; reused for captain's notes, WP73)."""

    def __init__(self, prompt: str = "Post a notice") -> None:
        super().__init__(prompt, placeholder="your message…")
