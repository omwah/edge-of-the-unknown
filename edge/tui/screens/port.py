"""PortScreen — a plain commodities port, wired to the live service (UI_MOCKUPS.md §2).

Used when the docked port is *not* a StarDock (a StarDock hosts the same
`TradePanel` as its Commodities tab). Reads `service.current_port_view`; `T`
trades a chunk of the highlighted commodity in the port's natural direction
(quick-trade — the haggle panel is a visual stub in Phase 1).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from edge.core.economy import EconomyError
from edge.core.rules import Trade
from edge.server.service import GameService
from edge.tui.widgets import NAME_TO_COMMODITY, TradePanel

_CHUNK = 10  # units traded per keypress (clamped to what's affordable/available)


class PortScreen(Screen):
    BINDINGS = [
        Binding("escape", "leave", "Leave dock"),
        Binding("q", "leave", "Leave dock"),
        Binding("t", "trade", "Trade highlighted"),
    ]

    def __init__(self, service: GameService, player_id: int) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id

    def compose(self) -> ComposeResult:
        port = self._service.current_port_view(self._pid)
        if port is None:
            yield Static("No port to trade with here.", id="port-body")
            return
        latinum = self._service.game_view(self._pid).ship.latinum
        yield TradePanel(port, latinum=latinum, id="port-body")

    def action_trade(self) -> None:
        _trade_highlighted(self, self._service, self._pid)

    def action_leave(self) -> None:
        self.app.pop_screen()


def _trade_highlighted(screen: Screen, service: GameService, player_id: int) -> None:
    """Shared trade handler: buy/sell a clamped chunk of the highlighted row."""
    panels = list(screen.query(TradePanel))
    if not panels:  # empty port (no panel mounted)
        return
    panel = panels[0]
    name = panel.cursor_commodity()
    port = service.current_port_view(player_id)
    if name is None or port is None:
        return
    line = next(c for c in port.commodities if c.name == name)
    ship = service.game_view(player_id).ship
    holds_free = ship.holds_total - ship.holds_used
    if line.mode == "SELL":  # port sells -> player buys
        qty = min(_CHUNK, line.stock, holds_free, ship.latinum // max(1, line.price))
    else:  # port buys -> player sells
        qty = min(_CHUNK, line.player_qty, line.capacity - line.stock)
    if qty <= 0:
        screen.notify("Can't trade that here right now.", timeout=2)
        return
    try:
        service.apply(player_id, Trade(commodity=NAME_TO_COMMODITY[name], units=qty))
    except EconomyError as exc:
        screen.notify(str(exc), severity="warning", timeout=3)
        return
    new_port = service.current_port_view(player_id)
    new_latinum = service.game_view(player_id).ship.latinum
    if new_port is not None:
        panel.refresh_port(new_port, new_latinum)
    verb = "Bought" if line.mode == "SELL" else "Sold"
    screen.notify(f"{verb} {qty} {name}.", timeout=2)
