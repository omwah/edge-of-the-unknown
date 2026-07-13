"""PortScreen — a plain commodities port, wired to the live service (UI_MOCKUPS.md §2).

Used when the docked port is *not* a Stardock (a Stardock hosts the same
`TradePanel` as its Commodities tab). Reads `service.current_port_view`; `T`
trades a chunk of the highlighted commodity in the port's natural direction
(quick-trade), and `G` opens a counter-offer haggle on it (§8). `D` delivers any
active deliver favor targeting this port (§6.7, WP57 — surfaced WP71).

Haggle is `G`, not `H`: the Stardock hosts this same panel on its Commodities tab, where
`H` names the Hardware tab (PT-32), and a verb should not answer to two keys depending
on which screen you reached it from.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core.dto import CommodityLine, PortDTO, ShipDTO
from edge.core.economy import EconomyError
from edge.core.rules import Trade
from edge.server.service import GameService
from edge.tui.chrome import EdgeScreen, notify_warning
from edge.tui.station_art import StationArtHeader
from edge.tui.screens.haggle import HaggleScreen
from edge.tui.widgets import NAME_TO_COMMODITY, TRADE_CHUNK, TradePanel


class PortScreen(EdgeScreen):
    BINDINGS = [
        Binding("escape", "leave", "Leave dock"),
        Binding("t", "trade", "Trade highlighted"),
        Binding("g", "haggle", "Haggle highlighted"),
        Binding("d", "deliver", "Deliver favor"),
    ]

    HELP_TITLE = "Trade port"
    HELP = """\
Trading acts on the [b]highlighted[/] commodity row. Haggling wears the port's
patience — too many rejected offers close negotiation for the day."""

    # Mirror Stardock's icon + service-banner header, then the shared trade panel.
    CSS = """
    PortScreen #port-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    PortScreen.compact #port-body { height: 1fr; }
    """

    def __init__(self, service: GameService, player_id: int) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id

    def compose(self) -> ComposeResult:
        port = self._service.current_port_view(self._pid)
        if port is None:
            yield Static("No port to trade with here.", id="port-title")
            yield Footer()
            return
        latinum = self._service.game_view(self._pid).ship.latinum
        yield Static(
            f"TRADEPORT · {port.name} · {port.klass}        Sector {port.display_id}",
            id="port-title",
        )
        yield StationArtHeader(
            "port", port.archetype_id or "humanoid_diplomat", "trade",
            identity=port.sector_id,
        )
        yield TradePanel(port, latinum=latinum, show_title=False, id="port-body")
        yield Footer()

    def action_trade(self) -> None:
        _trade_highlighted(self, self._service, self._pid)

    def action_haggle(self) -> None:
        _haggle_highlighted(self, self._service, self._pid)

    def action_deliver(self) -> None:
        """Fulfil the first active deliver favor targeting this dock (§6.7, WP57)."""
        from edge.core.rules import DeliverContract
        jobs = [c for c in self._service.computer_view(self._pid).contracts
                if c.kind == "deliver"]
        if not jobs:
            self.notify("No active delivery to fulfil.", timeout=2)
            return
        errors: list[str] = []
        for job in jobs:
            try:
                self._service.apply(self._pid, DeliverContract(contract_id=job.contract_id))
            except EconomyError as exc:
                errors.append(str(exc))
                continue
            self.notify(f"Delivered — {job.reward:,} slips paid.", timeout=3)
            return
        notify_warning(self, errors[0])

    def action_leave(self) -> None:
        self.app.pop_screen()


def _highlighted_line(
    screen: Screen[Any], service: GameService, player_id: int,
) -> "tuple[TradePanel | None, CommodityLine | None, PortDTO | None]":
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


def _chunk_qty(line: CommodityLine, ship: ShipDTO) -> int:
    """A clamped trade chunk for the highlighted row (the port's natural direction)."""
    holds_free = ship.holds_total - ship.holds_used
    if line.mode == "SELL":  # port sells -> player buys
        return min(TRADE_CHUNK, line.stock, holds_free, ship.latinum // max(1, line.price))
    return min(TRADE_CHUNK, line.player_qty, line.capacity - line.stock)  # port buys -> player sells


def _trade_highlighted(screen: Screen[Any], service: GameService, player_id: int) -> None:
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
        notify_warning(screen, str(exc))
        return
    _refresh(panel, service, player_id)
    screen.app.mark_objective("trade")  # type: ignore[attr-defined]
    verb = "Bought" if line.mode == "SELL" else "Sold"
    screen.notify(f"{verb} {qty} {line.name}.", timeout=2)


def _haggle_highlighted(screen: Screen[Any], service: GameService, player_id: int) -> None:
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
        if _traded:
            screen.app.mark_objective("trade")  # type: ignore[attr-defined]
        _refresh(panel, service, player_id)

    screen.app.push_screen(
        HaggleScreen(service, player_id, commodity, line.name, line.mode, line.price, qty), _after)


def _refresh(panel: TradePanel, service: GameService, player_id: int) -> None:
    """Re-render the trade panel from fresh state after a trade/haggle."""
    new_port = service.current_port_view(player_id)
    new_latinum = service.game_view(player_id).ship.latinum
    if new_port is not None:
        panel.refresh_port(new_port, new_latinum)
