"""StarbaseServicesScreen — a player-owned base as a working home (§4.2, WP53).

The forward-foothold counterpart of the StarDock screen: a repaired, claimed orbital
base offers a config-gated subset of dock services (component purchase, munitions
resupply, banking) at a frontier markup. This screen is composition over the StarDock
panes — it reuses the same hardware DataTable idiom and issues the *same* commands
(`BuyComponent`, `BuyMissiles`, `Deposit`, `Withdraw`), which resolve through the shared
service-point seam, so there is one code path and two providers.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static, TabbedContent, TabPane

from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.enums import Component, ComponentTier
from edge.core.rules import BuyComponent, BuyMissiles, Deposit, Withdraw
from edge.server.service import GameService


class StarbaseServicesScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Leave base"),
        Binding("b", "buy", "Buy"),
        Binding("m", "buy_missiles", "Resupply missile"),
        Binding("d", "deposit", "Deposit 1k"),
        Binding("y", "withdraw", "Withdraw 1k"),
    ]

    CSS = """
    StarbaseServicesScreen #base-title {
        dock: top; height: 1; background: $success; color: $background;
        text-style: bold; padding: 0 1;
    }
    StarbaseServicesScreen TabPane { padding: 1 2; }
    StarbaseServicesScreen DataTable { height: auto; max-height: 18; }
    """

    def __init__(self, service: GameService, player_id: int, initial_tab: str = "hardware") -> None:
        super().__init__()
        self._service = service
        self._pid = player_id
        self._initial_tab = initial_tab

    def compose(self) -> ComposeResult:
        view = self._service.starbase_services_view(self._pid)
        if view is None:
            yield Static("No base of yours here.", id="base-title")
            yield Footer()
            return
        yield Static(
            f"⌂ YOUR BASE · Sector {view.sector_display} · "
            f"services: {', '.join(view.services)} · markup ×{view.fee_frac:g}",
            id="base-title",
        )
        with TabbedContent(initial=self._initial_tab):
            with TabPane("Hardware", id="hardware"):
                yield Static(f"[b]HARDWARE[/]  Latinum [b yellow]{view.latinum:,}[/] slips  "
                             f"[dim](frontier prices ×{view.fee_frac:g})[/]")
                yield self._hardware_table(view)
                yield Static("[dim]B buys the highlighted part; M resupplies a missile.[/]",
                             classes="note")
            with TabPane("Bank", id="bank"):
                yield Static(f"[b]BASE VAULT[/]  cash [b yellow]{view.latinum:,}[/]  "
                             f"banked [b green]{view.bank_balance:,}[/]")
                yield Static("[dim]D deposits 1,000; Y withdraws 1,000 (interest-free — §4.2).[/]",
                             classes="note")
        yield Footer()

    def _hardware_table(self, view: object) -> DataTable:
        table: DataTable = DataTable(id="base-hardware-table", cursor_type="row")
        table.add_columns("Component", "Tier", "Price", "")
        for item in view.hardware:  # type: ignore[attr-defined]
            mark = "" if item.affordable else "[red]✗[/]"
            table.add_row(item.component, item.tier, f"{item.price:,}", mark,
                          key=f"{item.component}:{item.tier}")
        return table

    def action_buy(self) -> None:
        if self.query_one(TabbedContent).active != "hardware":
            self.notify("Switch to the Hardware tab to buy.", timeout=2)
            return
        table = self.query_one("#base-hardware-table", DataTable)
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key.value is None:
            return
        component, tier = row_key.value.split(":")
        self._issue(BuyComponent(Component(component), ComponentTier[tier]), f"Bought {component}")

    def action_buy_missiles(self) -> None:
        self._issue(BuyMissiles(count=1), "Resupplied a homing missile")

    def action_deposit(self) -> None:
        self._issue(Deposit(amount=1_000), "Deposited 1,000 slips")

    def action_withdraw(self) -> None:
        self._issue(Withdraw(amount=1_000), "Withdrew 1,000 slips")

    def _issue(self, command: object, ok: str) -> None:
        try:
            self._service.apply(self._pid, command)  # type: ignore[arg-type]
        except (EconomyError, EngineRoomError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.notify(ok, timeout=2)
        active = self.query_one(TabbedContent).active
        self.app.pop_screen()
        self.app.push_screen(StarbaseServicesScreen(self._service, self._pid, initial_tab=active))

    def action_back(self) -> None:
        self.app.pop_screen()
