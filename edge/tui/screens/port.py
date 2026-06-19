"""PortScreen — a plain commodities port, wired to the live service (UI_MOCKUPS.md §2).

Used when the docked port is *not* a StarDock (a StarDock hosts the same
`TradePanel` as its Commodities tab). Reads `service.current_port_view`; `T`
trades a chunk of the highlighted commodity in the port's natural direction
(quick-trade), and `H` opens a counter-offer haggle on it (§8).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static

from edge.core.economy import EconomyError
from edge.core.rules import Trade
from edge.server.service import GameService
from edge.tui.screens.haggle import HaggleScreen
from edge.tui.widgets import NAME_TO_COMMODITY, TradePanel

_CHUNK = 10  # units traded per keypress (clamped to what's affordable/available)


class PortScreen(Screen):
    BINDINGS = [
        Binding("escape", "leave", "Leave dock"),
        Binding("q", "leave", "Leave dock"),
        Binding("t", "trade", "Trade highlighted"),
        Binding("h", "haggle", "Haggle highlighted"),
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

    def action_haggle(self) -> None:
        _haggle_highlighted(self, self._service, self._pid)

    def action_leave(self) -> None:
        self.app.pop_screen()


def _highlighted_line(screen: Screen, service: GameService, player_id: int):  # type: ignore[no-untyped-def]
    """The (TradePanel, highlighted CommodityLine, port) trio, or (None, None, None)."""
    panels = list(screen.query(TradePanel))
    if not panels:  # empty port (no panel mounted)
        return None, None, None
    panel = panels[0]
    name = panel.cursor_commodity()
    port = service.current_port_view(player_id)
    if name is None or port is None:
        return panel, None, None
    line = next(c for c in port.commodities if c.name == name)
    return panel, line, port


def _chunk_qty(line, ship) -> int:  # type: ignore[no-untyped-def]
    """A clamped trade chunk for the highlighted row (the port's natural direction)."""
    holds_free = ship.holds_total - ship.holds_used
    if line.mode == "SELL":  # port sells -> player buys
        return min(_CHUNK, line.stock, holds_free, ship.latinum // max(1, line.price))
    return min(_CHUNK, line.player_qty, line.capacity - line.stock)  # port buys -> player sells


def _trade_highlighted(screen: Screen, service: GameService, player_id: int) -> None:
    """Shared trade handler: buy/sell a clamped chunk of the highlighted row."""
    panel, line, _ = _highlighted_line(screen, service, player_id)
    if panel is None or line is None:
        return
    qty = _chunk_qty(line, service.game_view(player_id).ship)
    if qty <= 0:
        screen.notify("Can't trade that here right now.", timeout=2)
        return
    try:
        service.apply(player_id, Trade(commodity=NAME_TO_COMMODITY[line.name], units=qty))
    except EconomyError as exc:
        screen.notify(str(exc), severity="warning", timeout=3)
        return
    _refresh(panel, service, player_id)
    verb = "Bought" if line.mode == "SELL" else "Sold"
    screen.notify(f"{verb} {qty} {line.name}.", timeout=2)


def _haggle_highlighted(screen: Screen, service: GameService, player_id: int) -> None:
    """Open a counter-offer haggle on the highlighted row (§8); commit on submit."""
    panel, line, _ = _highlighted_line(screen, service, player_id)
    if panel is None or line is None:
        return
    qty = _chunk_qty(line, service.game_view(player_id).ship)
    if qty <= 0:
        screen.notify("Nothing to haggle over here right now.", timeout=2)
        return
    commodity = NAME_TO_COMMODITY[line.name]

    def _after(_traded: bool | None) -> None:
        # The multi-round screen issues the offers itself and self-notifies each round;
        # we only refresh the panel from the resulting state when it closes (§8, WP13).
        _refresh(panel, service, player_id)

    screen.app.push_screen(
        HaggleScreen(service, player_id, commodity, line.name, line.mode, line.price, qty), _after)


def _refresh(panel: TradePanel, service: GameService, player_id: int) -> None:
    """Re-render the trade panel from fresh state after a trade/haggle."""
    new_port = service.current_port_view(player_id)
    new_latinum = service.game_view(player_id).ship.latinum
    if new_port is not None:
        panel.refresh_port(new_port, new_latinum)
