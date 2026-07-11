"""TransferWorkbenchScreen — one legible editor for ship↔colony logistics (WP-PR07, PT-10/11).

Replaces the old commodity-picker-then-amount prompts with a single form: a row per
commodity showing what is aboard vs. in the colony's stores, a `−`/`+` stepper (by 10) and
an editable exact-amount field, and per-row Load/Unload actions — plus Load All / Unload All.
An owned colonizable world also gets a **colonist** row that *settles* people from the ship's
berth into the colony (people are never loaded back aboard here, and never touch cargo holds).

Every action goes straight to the service (`TransferCargo` / `SettleColonists`), which clamps
to what fits, is aboard, or the world's remaining habitability — so the form can never
over-commit, and the readouts refresh from fresh state after each move.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from edge.core.economy import EconomyError
from edge.core.enums import Commodity
from edge.core.rules import SettleColonists, TransferCargo
from edge.server.service import GameService
from edge.tui.chrome import notify_warning

_STEP = 10
_COLONIST_ROW = "colonists"


class TransferWorkbenchScreen(ModalScreen[None]):
    """A modal transfer editor for the player-owned world in the current sector."""

    DEFAULT_CSS = """
    TransferWorkbenchScreen { align: center middle; }
    TransferWorkbenchScreen #panel {
        width: 74; max-width: 96%; height: auto; max-height: 90%;
        border: round $accent; background: $surface; padding: 1 2;
    }
    TransferWorkbenchScreen .row { height: auto; margin-bottom: 1; }
    TransferWorkbenchScreen .row-head { width: 1fr; }
    TransferWorkbenchScreen Input { width: 11; }
    TransferWorkbenchScreen .step { width: 5; min-width: 5; }
    TransferWorkbenchScreen .act { width: 10; min-width: 8; }
    TransferWorkbenchScreen #foot { height: auto; margin-top: 1; }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("ctrl+u", "unload_all", "Unload all"),
        Binding("ctrl+l", "load_all", "Load all"),
    ]

    def __init__(self, service: GameService, pid: int, planet_id: int) -> None:
        super().__init__()
        self._service = service
        self._pid = pid
        self._planet_id = planet_id

    # --- data -----------------------------------------------------------------

    def _planet(self):
        return self._service.planet_view(self._pid, self._planet_id)

    def _aboard(self) -> dict[str, int]:
        ship = self._service.game_view(self._pid).ship
        return {h.label: h.qty for h in ship.holds}

    # --- layout ---------------------------------------------------------------

    def compose(self) -> ComposeResult:
        p = self._planet()
        aboard = self._aboard()
        stores = dict(p.stores)
        with VerticalScroll(id="panel"):
            yield Static(f"[b]Transfer · {p.name}[/]", id="title")
            yield Static("[dim]Aboard ↔ colony stores. Steps of 10, or type an exact amount.[/]")
            for c in Commodity:
                label = c.value.replace("_", " ").title()
                a, s = aboard.get(label, 0), stores.get(label, 0)
                yield Horizontal(
                    Static(f"[b]{label}[/]\n[dim]aboard {a:,} · stores {s:,}[/]", classes="row-head"),
                    Button("−", id=f"dec-{c.value}", classes="step"),
                    Input(value="0", id=f"amt-{c.value}", type="integer"),
                    Button("+", id=f"inc-{c.value}", classes="step"),
                    Button("Load", id=f"load-{c.value}", classes="act"),
                    Button("Unload", id=f"unload-{c.value}", classes="act"),
                    classes="row",
                )
            # Colonists: settle from the berth into an owned colony (never loaded back here).
            if p.owned_by_you and p.colonizable:
                room = max(0, p.habitability_cap - p.colonists)
                yield Horizontal(
                    Static(f"[b]Colonists[/]\n[dim]berth {p.ship_colonists:,} · colony {p.colonists:,} "
                           f"· room {room:,}[/]", classes="row-head"),
                    Button("−", id=f"dec-{_COLONIST_ROW}", classes="step"),
                    Input(value="0", id=f"amt-{_COLONIST_ROW}", type="integer"),
                    Button("+", id=f"inc-{_COLONIST_ROW}", classes="step"),
                    Static("", classes="act"),
                    Button("Settle", id=f"unload-{_COLONIST_ROW}", classes="act"),
                    classes="row",
                )
            yield Horizontal(
                Button("Load all", id="load-all"),
                Button("Unload all", id="unload-all"),
                Button("Close", id="close", variant="primary"),
                id="foot",
            )

    # --- helpers --------------------------------------------------------------

    def _amount(self, key: str) -> int:
        try:
            return max(0, int(self.query_one(f"#amt-{key}", Input).value or "0"))
        except ValueError:
            return 0

    def _set_amount(self, key: str, value: int) -> None:
        self.query_one(f"#amt-{key}", Input).value = str(max(0, value))

    def _refresh(self) -> None:
        self.refresh(recompose=True)

    def _apply(self, command: object, *, refresh: bool = True) -> bool:
        try:
            self._service.apply(self._pid, command)  # type: ignore[arg-type]
        except EconomyError as exc:
            notify_warning(self, str(exc))
            return False
        if refresh:
            self._refresh()
        return True

    # --- events ---------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "close":
            self.dismiss(None)
        elif bid == "load-all":
            self.action_load_all()
        elif bid == "unload-all":
            self.action_unload_all()
        elif bid.startswith("dec-"):
            key = bid[4:]
            self._set_amount(key, self._amount(key) - _STEP)
        elif bid.startswith("inc-"):
            key = bid[4:]
            self._set_amount(key, self._amount(key) + _STEP)
        elif bid.startswith("load-"):
            self._do_row(bid[5:], to_planet=False)
        elif bid.startswith("unload-"):
            self._do_row(bid[7:], to_planet=True)

    def _do_row(self, key: str, *, to_planet: bool) -> None:
        amount = self._amount(key)
        if amount <= 0:
            self.notify("Enter an amount above zero.", timeout=2)
            return
        if key == _COLONIST_ROW:
            self._apply(SettleColonists(self._planet_id, amount))
            return
        self._apply(TransferCargo(self._planet_id, Commodity(key), amount, to_planet=to_planet))

    # --- bulk actions ---------------------------------------------------------

    def action_close(self) -> None:
        self.dismiss(None)

    def action_load_all(self) -> None:
        # A large number means "all" — the reducer clamps to free holds / available stores.
        moved = any(self._apply(TransferCargo(self._planet_id, c, 10**9, to_planet=False),
                                 refresh=False) for c in Commodity)
        if moved:
            self._refresh()

    def action_unload_all(self) -> None:
        moved = any(self._apply(TransferCargo(self._planet_id, c, 10**9, to_planet=True),
                                refresh=False) for c in Commodity)
        if moved:
            self._refresh()
