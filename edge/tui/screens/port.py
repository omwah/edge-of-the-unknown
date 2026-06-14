"""PortScreen — trading + a stub haggle panel (UI_MOCKUPS.md §2)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Static

from edge.tui.dummy import PortDTO
from edge.tui.widgets import bar


class HagglePanel(Static):
    DEFAULT_CSS = """
    HagglePanel {
        border: round $secondary; padding: 0 1; margin: 1 0; height: auto;
    }
    """

    def render(self) -> str:
        return (
            "[b]Haggle: Sell Fuel Ore[/]\n"
            "Quote:  13/u  x  20 units  =  [yellow]260 gpl[/]\n"
            "Your counter: ( [b]15[/] )/u    fair ~ 13    [green]likely[/]\n"
            'Round 1 of 2   · "Hah, 14 and not a slip more."\n'
            "[b]\\[A][/]ccept quote   [b]\\[O][/]ffer counter   [b]\\[Esc][/] walk away"
        )


class PortScreen(Screen):
    BINDINGS = [
        Binding("escape", "leave", "Leave dock"),
        Binding("q", "leave", "Leave dock"),
    ]

    def __init__(self, port: PortDTO) -> None:
        super().__init__()
        self._port = port

    def compose(self) -> ComposeResult:
        p = self._port
        with Vertical(id="port-body"):
            yield Static(
                f"[b cyan]TRADEPORT · {p.name} · {p.klass}[/]"
                f"      [dim]Sector {p.sector_id}[/]",
                id="port-title",
            )
            yield DataTable(id="commodities", zebra_stripes=True, cursor_type="row")
            yield HagglePanel()
            yield Static(
                "[dim]^ port buys from you (you SELL)   v port sells to you (you BUY)[/]\n"
                "Latinum [yellow]14,250[/]   ·   [b]Q[/]uick-trade off   ·   [b]Esc[/] leave dock",
                id="port-footer",
            )

    def on_mount(self) -> None:
        table = self.query_one("#commodities", DataTable)
        table.add_columns("Commodity", "They", "Stock", "Price/u", "You", "Action")
        for c in self._port.commodities:
            stock = f"{bar(round(c.stock_ratio * 9), 9)} {round(c.stock_ratio * 100):>2}%"
            action = "[b]Sell[/]" if c.mode == "BUY" else "[b]Buy[/]"
            table.add_row(
                c.name, c.mode, stock, f"{c.price} {c.trend}", str(c.player_qty), action
            )

    def action_leave(self) -> None:
        self.app.pop_screen()
