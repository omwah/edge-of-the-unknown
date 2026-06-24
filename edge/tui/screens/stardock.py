"""StarDockScreen — the services hub, wired to the live service (UI_MOCKUPS.md §5).

The Commodities tab reuses `PortScreen`'s `TradePanel` (so `T` trades there too);
the **Hardware** tab sells engine-room components by tier and the **Shipyard** tab
sells hulls (trade-in adjusted) — `B` buys the highlighted row of the active tab,
reading the fog-of-war `stardock_view` catalog (DESIGN §8, §11). Bank/Tavern remain
stubs. Buy a component here, then slot it in the Engine Room (`E`).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static, TabbedContent, TabPane

from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.enums import Component, ComponentTier
from edge.core.rules import BuyComponent, BuyGenesis, BuyShip, RecruitColonists
from edge.server.service import GameService
from edge.tui import art_adapter
from edge.tui.screens.engine_room import EngineRoomScreen
from edge.tui.screens.port import _haggle_highlighted, _trade_highlighted
from edge.tui.widgets import TradePanel


class StarDockScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Undock"),
        Binding("t", "trade", "Trade"),
        Binding("h", "haggle", "Haggle"),
        Binding("b", "buy", "Buy"),
        Binding("g", "buy_genesis", "Buy Genesis"),
        Binding("k", "recruit", "Recruit colonists"),
        Binding("e", "engine_room", "Engine room"),
        Binding("r", "noop", "Repair"),
    ]

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
    _BUY_TABLES = {"hardware": "#hardware-table", "shipyard": "#shipyard-table"}

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
        with TabbedContent(initial=self._initial_tab):
            with TabPane("Commodities", id="trade"):
                yield TradePanel(port, latinum=latinum, show_title=False)
            with TabPane("Shipyard", id="shipyard"):
                yield Static(
                    f"[b]SHIPYARD[/]        Latinum [b yellow]{latinum:,}[/] slips        "
                    "[dim]net price shown after trade-in[/]"
                )
                yield self._shipyard_table(dock)
                yield Static("[dim]B buys the highlighted hull (your parts return loose).[/]",
                             classes="note")
            with TabPane("Hardware", id="hardware"):
                yield Static(
                    f"[b]HARDWARE EMPORIUM[/]        Latinum [b yellow]{latinum:,}[/] slips"
                )
                yield self._hardware_table(dock)
                yield Static("[dim]B buys the highlighted part; slot it in the Engine Room (E). "
                             "Tier III is barter-only.[/]", classes="note")
            with TabPane("Bank", id="bank"):
                yield Static("[dim]Deposit / withdraw / interest — Phase 2.[/]")
            with TabPane("Tavern", id="tavern"):
                yield Static("[dim]Rumors & contracts — Phase 5.[/]")
        yield Footer()

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
        else:
            self.notify("Switch to the Hardware or Shipyard tab to buy.", timeout=2)

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
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.notify(ok, timeout=2)
        active = self.query_one(TabbedContent).active
        cursor = 0
        if active in self._BUY_TABLES:
            cursor = self.query_one(self._BUY_TABLES[active], DataTable).cursor_row
        self.app.pop_screen()
        self.app.push_screen(
            StarDockScreen(self._service, self._pid, initial_tab=active, initial_cursor=cursor))

    def action_engine_room(self) -> None:
        self.app.push_screen(EngineRoomScreen(
            self._service.engine_room_view(self._pid), self._service, self._pid))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
