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
from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import Button, DataTable, Footer, Static, TabbedContent
from textual.widgets.data_table import RowDoesNotExist

from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.enums import Component, ComponentTier
from edge.core.rules import (
    BuyComponent, BuyDevice, BuyFighters, BuyGenesis, BuyMines, BuyMissiles, BuyRumor,
    BuyShip, Deposit, PostNotice, RecruitColonists, Withdraw,
)
from edge.server.service import GameService
from edge.tui import art_adapter
from edge.tui.chrome import AmountPrompt, EmptyState, TextPrompt, notify_warning
from edge.tui.screens.engine_room import EngineRoomScreen
from edge.tui.screens.port import _haggle_highlighted, _trade_highlighted
from edge.tui.widgets import ServiceHub, TradePanel


# Placeholder station-concourse banner for the Colonists tab (PT-06). A bespoke
# DS9-style raster run through the image→ANSI pipeline is a deferred art follow-up;
# this compact ASCII stand-in keeps the tab operable at 80x24 in the meantime.
_CONCOURSE_ART = (
    "[dim]╭──────────────── ORBITAL CONCOURSE ────────────────╮[/]\n"
    "[dim]│[/]  [cyan]▟▙[/]   [cyan]▟▙[/]    [yellow]☺ ☺  ☺[/]   [cyan]▟▙[/]   [cyan]▟▙[/]  [dim]│[/]\n"
    "[dim]│[/]  [cyan]██[/]   [cyan]██[/]   [yellow]☺  ☺ ☺ ☺[/]  [cyan]██[/]   [cyan]██[/]  [dim]│[/]\n"
    "[dim]╰────────  colonists throng the promenade  ─────────╯[/]"
)


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
    ]

    HELP_TITLE = "StarDock"
    HELP = """\
[b]B[/] buys the highlighted row of the active buy tab (Hardware · Shipyard ·
Devices & Armaments — munitions there prompt for a quantity). Tab-scoped keys only
work on their tab: [b]K[/] recruits on Colonists, [b]D[/]/[b]W[/] bank on Bank,
[b]R[/]/[b]N[/] buy rumours / post notices on the Tavern. The bank pays daily interest."""

    CSS = """
    StarDockScreen #dock-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    StarDockScreen #dock-art { height: auto; content-align: center top; }
    StarDockScreen TabPane { padding: 1 2; }
    StarDockScreen .note { color: $text-muted; margin-top: 1; }
    StarDockScreen DataTable { height: auto; max-height: 18; }
    StarDockScreen #concourse-art { height: auto; margin-bottom: 1; }
    StarDockScreen Button { margin-top: 1; margin-right: 1; }
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
        size = self.app.scene_art.port  # one canonical port footprint, shared with SectorView
        yield Static(
            art_adapter.sprite(
                "port", "stardock", seed=port.sector_id,
                width=size.max_width, height=size.max_height,
                archetype_id=port.archetype_id,
            ),
            id="dock-art",
        )
        trade = TradePanel(port, latinum=latinum, show_title=False)
        shipyard = Vertical(
                Static(
                    f"[b]SHIPYARD[/]        Latinum [b yellow]{latinum:,}[/] slips        "
                    "[dim]net price shown after trade-in[/]"
                ), self._shipyard_table(dock),
                Static("[dim]B buys the highlighted hull (your parts return loose).[/]",
                       classes="note"))
        hardware = Vertical(
                Static(
                    f"[b]HARDWARE EMPORIUM[/]        Latinum [b yellow]{latinum:,}[/] slips"
                ), self._hardware_table(dock),
                Static("[dim]B buys the highlighted part; slot it in the Engine Room (E). "
                       "Tier III is barter-only.[/]", classes="note"))
        devices = Vertical(
                Static(f"[b]DEVICES & ARMAMENTS[/]        Latinum [b yellow]{latinum:,}[/] slips"),
                self._devices_table(dock),
                Static("[dim]B buys the highlighted row — munitions (missiles / fighters / "
                       "mines) prompt for a quantity; devices and the Genesis torpedo buy one. "
                       "Deploy them from the game screen's Deploy (D).[/]", classes="note"))
        colonists = Vertical(*list(self._colonist_panels(dock)))
        rate = dock.interest_per_day * 100
        bank = Vertical(
                Static(
                    f"[b]BANK OF THE CORE[/]\n\n"
                    f"On hand   [b yellow]{latinum:,}[/] slips\n"
                    f"Banked    [b green]{dock.bank_balance:,}[/] slips\n\n"
                    f"[dim]Interest: {rate:.2g}%/day, compounded on the daily clock.[/]"
                ),
                Static("[dim][b]D[/] Deposit an amount   ·   [b]W[/] Withdraw an amount[/]",
                       classes="note"))
        tavern = Vertical(*list(self._tavern_panels()))
        entries = [
            ("Commodities", "trade", trade, None),
            ("Shipyard", "shipyard", shipyard, None),
            ("Hardware", "hardware", hardware, None),
            ("Devices & Armaments", "devices", devices, None),
            ("Colonists", "colonists", colonists, None),
            ("Bank", "bank", bank, None),
            ("Tavern", "tavern", tavern, None),
        ]
        yield ServiceHub(entries, initial=self._initial_tab, id="stardock-services")
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

    def _colonist_panels(self, dock: object) -> ComposeResult:
        """The recruitment office (§4.2, WP-PR08 / PT-06): berth occupancy + a recruit control."""
        d = dock  # type: ignore[assignment]
        free = max(0, d.ship_colonist_capacity - d.ship_colonists)  # type: ignore[attr-defined]
        # NOTE: a bespoke DS9-style station-concourse raster (run through the image→ANSI
        # pipeline) is a deferred art follow-up; this text banner stands in for now (PT-06).
        yield Static(_CONCOURSE_ART, id="concourse-art")
        yield Static(
            f"[b]RECRUITMENT OFFICE[/]        Latinum [b yellow]{d.latinum:,}[/] slips\n\n"  # type: ignore[attr-defined]
            f"Berths    [b]{d.ship_colonists:,}[/] / {d.ship_colonist_capacity:,}  "  # type: ignore[attr-defined]
            f"([green]{free:,}[/] free)\n"
            f"Incentive [yellow]{d.colonist_incentive:,}[/] slips per head\n"  # type: ignore[attr-defined]
            f"Afford    up to [b]{d.colonists_recruitable:,}[/] more right now")  # type: ignore[attr-defined]
        yield Static("[dim]Colonists are recruited, not bought — they ride their own berths, "
                     "not cargo holds. Settle them onto a world you own from its orbit view.[/]",
                     classes="note")
        yield Button(f"Recruit up to {d.colonists_recruitable:,}", id="btn-recruit-all",  # type: ignore[attr-defined]
                     variant="primary")
        yield Button("Recruit an amount…", id="btn-recruit-some")

    def _shipyard_table(self, dock: object) -> DataTable[Any]:
        table: DataTable[Any] = DataTable(id="shipyard-table", cursor_type="row")
        table.add_columns("Hull", "Role", "Holds", "Shld", "Wrp", "Cbt", "Net", "")
        for item in dock.shipyard:  # type: ignore[attr-defined]
            flag = "[green]flown[/]" if item.owned else ("" if item.affordable else "[red]✗[/]")
            table.add_row(item.name, item.role, str(item.holds), str(item.shields),
                          str(item.warp), str(item.combat), f"{item.net_price:,}", flag,
                          key=item.class_id)
        return table

    # --- actions -------------------------------------------------------------

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
        elif event.button.id == "btn-recruit-some":
            self.action_recruit()

    def action_recruit(self) -> None:
        """Prompt for a number of colonists to enlist into the ship's free berths."""
        recruitable = self._service.stardock_view(self._pid).colonists_recruitable
        if recruitable <= 0:
            self.notify("No free berths or not enough latinum to recruit.", timeout=2)
            return

        def _go(count: int | None) -> None:
            if count:
                self._recruit_up_to(count)
        self.app.push_screen(_AmountInput(f"Recruit how many colonists? (up to {recruitable:,})"), _go)

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
