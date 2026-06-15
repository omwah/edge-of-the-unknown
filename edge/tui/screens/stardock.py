"""StarDockScreen — the services hub, wired to the live service (UI_MOCKUPS.md §5).

The Commodities tab reuses the same `TradePanel` as `PortScreen` (so `T` trades
there too); the Hardware tab sells the Phase-1 flat-aspect "first upgrade" via
`U` (BuyUpgrade, PHASE1_PLAN §2). Shipyard/Bank/Tavern remain stubs.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static, TabbedContent, TabPane

from edge.core.economy import EconomyError
from edge.core.rules import BuyUpgrade
from edge.server.service import GameService
from edge.tui.screens.port import _trade_highlighted
from edge.tui.widgets import TradePanel


class StarDockScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Undock"),
        Binding("t", "trade", "Trade"),
        Binding("u", "buy_upgrade", "Buy upgrade"),
        Binding("e", "noop", "Engine room"),
        Binding("r", "noop", "Repair"),
    ]

    CSS = """
    StarDockScreen #dock-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    StarDockScreen TabPane { padding: 1 2; }
    StarDockScreen .note { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, service: GameService, player_id: int) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id

    def compose(self) -> ComposeResult:
        port = self._service.current_port_view(self._pid)
        if port is None:
            yield Static("No StarDock here.", id="dock-title")
            yield Footer()
            return
        latinum = self._service.game_view(self._pid).ship.latinum
        econ = self._service.config.economy
        yield Static(f"STARDOCK · Sector {port.sector_id}", id="dock-title")
        with TabbedContent(initial="trade"):
            with TabPane("Commodities", id="trade"):
                yield TradePanel(port, latinum=latinum, show_title=False)
            with TabPane("Shipyard", id="shipyard"):
                yield Static("[dim]Hull sales — not wired in the skeleton.[/]")
            with TabPane("Hardware", id="hardware"):
                yield Static(
                    f"[b]HARDWARE EMPORIUM[/]        Latinum [b yellow]{latinum:,}[/] slips",
                    id="hardware-latinum",
                )
                yield Static(
                    f"  {econ.first_upgrade_aspect} +{econ.first_upgrade_amount}"
                    f"        {econ.first_upgrade_latinum:,} slips        [b]\\[U][/] Install"
                )
                yield Static(
                    "[dim]* full engine-room slot upgrades arrive in Phase 2 (§4.1)[/]",
                    classes="note",
                )
            with TabPane("Bank", id="bank"):
                yield Static("[dim]Deposit / withdraw / interest — Phase 2.[/]")
            with TabPane("Tavern", id="tavern"):
                yield Static("[dim]Rumors & contracts — Phase 5.[/]")
        yield Footer()

    def action_trade(self) -> None:
        _trade_highlighted(self, self._service, self._pid)

    def action_buy_upgrade(self) -> None:
        try:
            self._service.apply(self._pid, BuyUpgrade())
        except EconomyError as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        latinum = self._service.game_view(self._pid).ship.latinum
        self.notify("Upgrade installed!", timeout=2)
        self.query_one("#hardware-latinum", Static).update(
            f"[b]HARDWARE EMPORIUM[/]        Latinum [b yellow]{latinum:,}[/] slips"
        )
        port = self._service.current_port_view(self._pid)
        if port is not None:
            self.query_one(TradePanel).refresh_port(port, latinum)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
