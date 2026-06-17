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
from edge.core.rules import BuyComponent, BuyShip, RecruitColonists
from edge.server.service import GameService
from edge.tui.screens.engine_room import EngineRoomScreen
from edge.tui.screens.port import _trade_highlighted
from edge.tui.widgets import TradePanel


class StarDockScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Undock"),
        Binding("t", "trade", "Trade"),
        Binding("b", "buy", "Buy"),
        Binding("k", "recruit", "Recruit colonists"),
        Binding("e", "engine_room", "Engine room"),
        Binding("r", "noop", "Repair"),
    ]

    CSS = """
    StarDockScreen #dock-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    StarDockScreen TabPane { padding: 1 2; }
    StarDockScreen .note { color: $text-muted; margin-top: 1; }
    StarDockScreen DataTable { height: auto; max-height: 18; }
    """

    def __init__(self, service: GameService, player_id: int, initial_tab: str = "trade") -> None:
        super().__init__()
        self._service = service
        self._pid = player_id
        self._initial_tab = initial_tab

    def compose(self) -> ComposeResult:
        port = self._service.current_port_view(self._pid)
        if port is None:
            yield Static("No StarDock here.", id="dock-title")
            yield Footer()
            return
        dock = self._service.stardock_view(self._pid)
        latinum = dock.latinum
        yield Static(f"STARDOCK · Sector {dock.sector_display}", id="dock-title")
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
        self.app.pop_screen()
        self.app.push_screen(StarDockScreen(self._service, self._pid, initial_tab=active))

    def action_engine_room(self) -> None:
        self.app.push_screen(EngineRoomScreen(
            self._service.engine_room_view(self._pid), self._service, self._pid))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
