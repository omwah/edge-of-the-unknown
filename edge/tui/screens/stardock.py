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

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Static, TabbedContent

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


class StarDockScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Undock"),
        Binding("t", "trade", "Trade"),
        Binding("h", "haggle", "Haggle"),
        Binding("b", "buy", "Buy"),
        Binding("g", "buy_genesis", "Buy Genesis"),
        Binding("i", "buy_missiles", "Buy missile"),
        Binding("k", "recruit", "Recruit colonists"),
        Binding("e", "engine_room", "Engine room"),
        Binding("r", "buy_rumor", "Rumor"),
        Binding("n", "post_notice", "Notice"),
        Binding("d", "deposit", "Deposit"),
        Binding("w", "withdraw", "Withdraw"),
        Binding("f", "buy_fighters", "Buy fighters"),
        Binding("m", "buy_mines", "Buy mines"),
    ]

    HELP_TITLE = "StarDock"
    HELP = """\
[b]B[/] buys from the active tab (hardware · shipyard · devices). The bank pays
daily interest; deposits ride the same account everywhere."""

    CSS = """
    StarDockScreen #dock-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    StarDockScreen #dock-art { height: auto; content-align: center top; }
    StarDockScreen TabPane { padding: 1 2; }
    StarDockScreen .note { color: $text-muted; margin-top: 1; }
    StarDockScreen DataTable { height: auto; max-height: 18; }
    """

    # Buy tabs whose table cursor we preserve across a screen rebuild.
    _BUY_TABLES = {"hardware": "#hardware-table", "shipyard": "#shipyard-table",
                   "devices": "#devices-table"}

    def __init__(self, service: GameService, player_id: int, initial_tab: str = "trade",
                 initial_cursor: int = 0) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id
        self._initial_tab = initial_tab
        self._initial_cursor = initial_cursor

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
                Static(f"[b]DEVICE BAY[/]        Latinum [b yellow]{latinum:,}[/] slips"),
                self._devices_table(dock),
                Static("[dim]B buys the highlighted device (probe / interdictor / "
                       "mine-deflector); F/M buy sector fighters / mines. Work them "
                       "from the game screen's Deploy (D).[/]", classes="note"))
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
            ("Devices", "devices", devices, None),
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
            board = DataTable(id="bounty-table", cursor_type="row")
            board.add_columns("Notice")
            for line in tav.bounties:
                board.add_row(line)
            yield board
        else:
            yield EmptyState("The board is quiet.",
                             "Bounties post here when raids put a price on someone.")
        yield Static("[b]NOTICEBOARD[/]")
        if tav.notices:
            notices = DataTable(id="notices-table", cursor_type="row")
            notices.add_columns("Day", "By", "Notice")
            for n in tav.notices:
                notices.add_row(f"d{n.day}", n.author, n.text)
            yield notices
        else:
            yield EmptyState("Nothing pinned yet.",
                             "[b]N[/] posts a notice every visitor will read.")

    def on_mount(self) -> None:
        # Restore the highlighted row on the buy tab we rebuilt from (see _issue),
        # so repeated purchases of the same hull/component don't reset to the top.
        table_id = self._BUY_TABLES.get(self._initial_tab)
        if table_id is None or self._initial_cursor <= 0:
            return
        table = self.query_one(table_id, DataTable)
        if table.row_count:
            table.move_cursor(
                row=min(self._initial_cursor, table.row_count - 1), animate=False)

    def _hardware_table(self, dock: object) -> DataTable:
        table: DataTable = DataTable(id="hardware-table", cursor_type="row")
        table.add_columns("Component", "Tier", "Price", "")
        for item in dock.hardware:  # type: ignore[attr-defined]
            mark = "" if item.affordable else "[red]✗[/]"
            table.add_row(item.component, item.tier, f"{item.price:,}", mark,
                          key=f"{item.component}:{item.tier}")
        return table

    def _devices_table(self, dock: object) -> DataTable:
        table: DataTable = DataTable(id="devices-table", cursor_type="row")
        table.add_columns("Device", "Price", "")
        for device_id, price, affordable in dock.devices:  # type: ignore[attr-defined]
            mark = "" if affordable else "[red]✗[/]"
            table.add_row(device_id, f"{price:,}", mark, key=device_id)
        return table

    def _shipyard_table(self, dock: object) -> DataTable:
        table: DataTable = DataTable(id="shipyard-table", cursor_type="row")
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
            self._buy_device()
        else:
            self.notify("Switch to the Hardware, Shipyard, or Devices tab to buy.", timeout=2)

    def _buy_component(self) -> None:
        table = self.query_one("#hardware-table", DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key.value is None:
            return
        component, tier = row_key.value.split(":")
        self._issue(BuyComponent(Component(component), ComponentTier[tier]), f"Bought {component}")

    def action_recruit(self) -> None:
        """Enlist colonists into the ship's free berths (the reducer clamps to capacity)."""
        self._issue(RecruitColonists(count=10**9), "Recruited colonists")

    def action_buy_genesis(self) -> None:
        """Buy one Genesis torpedo (§4.2, WP10)."""
        self._issue(BuyGenesis(), "Bought a genesis torpedo")

    def action_buy_missiles(self) -> None:
        """Buy a homing missile at the hardware emporium (§10, WP25)."""
        self._issue(BuyMissiles(count=1), "Bought a homing missile")

    def _buy_device(self) -> None:
        table = self.query_one("#devices-table", DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key.value is None:
            return
        self._issue(BuyDevice(row_key.value), f"Bought {row_key.value}")

    def _buy_ship(self) -> None:
        table = self.query_one("#shipyard-table", DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key.value is None:
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
        cursor = 0
        if active in self._BUY_TABLES:
            cursor = self.query_one(self._BUY_TABLES[active], DataTable).cursor_row
        self.app.pop_screen()
        self.app.push_screen(
            StarDockScreen(self._service, self._pid, initial_tab=active, initial_cursor=cursor))

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

    def action_buy_fighters(self) -> None:
        """Buy sector-fighter stock (§10, WP41 — surfaced WP72)."""
        def _go(count: int | None) -> None:
            if count:
                self._issue(BuyFighters(count=count), f"Bought {count} fighters")
        self.app.push_screen(_AmountInput("Buy how many fighters?"), _go)

    def action_buy_mines(self) -> None:
        """Buy space-mine stock (§10, WP41 — surfaced WP72)."""
        def _go(count: int | None) -> None:
            if count:
                self._issue(BuyMines(count=count), f"Bought {count} mines")
        self.app.push_screen(_AmountInput("Buy how many mines?"), _go)

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
