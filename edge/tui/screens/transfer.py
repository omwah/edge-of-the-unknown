"""TransferWorkbenchScreen — one legible editor for ship↔colony logistics (WP-PR07, PT-10/11).

Replaces the old commodity-picker-then-amount prompts with a single form: a row per
commodity showing what is aboard vs. in the colony's stores, a `−`/`+` stepper (by 10) and
an editable exact-amount field, and per-row Load/Unload actions — plus Load All / Unload All.
An owned colonizable world also gets a **colonist** row that *settles* people from the ship's
berth into the colony (people are never loaded back aboard here, and never touch cargo holds).

Every action goes straight to the service (`TransferCargo`, `SettleColonists`, or atomic
aggregate `BatchTransferCargo`), which clamps to what fits, is aboard, or the world's
remaining habitability — so the form cannot over-commit, and readouts refresh after each move.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from edge.core.economy import EconomyError
from edge.core.dto import PlanetDTO
from edge.core.enums import Commodity
from edge.core.rules import BatchTransferCargo, SettleColonists, TransferCargo
from edge.server.service import GameService
from edge.tui.amount_stepper import AmountStepper
from edge.tui.chrome import notify_warning

_STEP = 10
_COLONIST_ROW = "colonists"


class TransferWorkbenchScreen(ModalScreen[None]):
    """A modal transfer editor for the player-owned world in the current sector."""

    # `CSS`, not `DEFAULT_CSS`: the scrim must outrank the base `ModalScreen:ansi
    # { background: transparent }` and app.tcss's `Screen { background }`, which a
    # lowest-priority DEFAULT_CSS rule loses to (so the overlay came out opaque). This
    # matches the other overlay modals (ConfirmScreen / RumorModal / AmountPrompt).
    CSS = """
    TransferWorkbenchScreen { align: center middle; background: $background 60%; }
    TransferWorkbenchScreen #panel {
        width: 74; max-width: 96%; height: auto; max-height: 90%;
        border: round $accent; background: $surface; padding: 1 2;
    }
    TransferWorkbenchScreen .row { height: auto; margin-bottom: 1; }
    TransferWorkbenchScreen .row-head { width: 1fr; }
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

    def _planet(self) -> PlanetDTO:
        return self._service.planet_view(self._pid, self._planet_id)

    # --- layout ---------------------------------------------------------------

    def compose(self) -> ComposeResult:
        p = self._planet()
        ship = self._service.game_view(self._pid).ship
        # The ship's holds DTO is built one-per-commodity in `Commodity` order (session
        # `_ship_dto`), but its `label` is an abbreviation ("Fuel"/"Org"/"Equ"), so key the
        # amounts by commodity here rather than by that display label.
        aboard = {c: h.qty for c, h in zip(Commodity, ship.holds)}
        free_holds = max(0, ship.holds_total - ship.holds_used)
        stores = dict(p.stores)
        with VerticalScroll(id="panel"):
            yield Static(f"[b]Transfer · {p.name}[/]", id="title")
            yield Static("[dim]Aboard ↔ colony stores. Steps of 10, or type an exact amount.[/]")
            for c in Commodity:
                label = c.value.replace("_", " ").title()  # matches session `_FULL`, the stores key
                a, s = aboard.get(c, 0), stores.get(label, 0)
                # Mirror the reducer's clamp (rules._transfer_cargo) so a greyed button and a
                # rejected command never disagree: loading stops at free holds *and* stores,
                # unloading at what is aboard (colony stores are unbounded). The shared field
                # is capped at the larger direction — neither action can be over-typed.
                load_cap = min(s, free_holds)
                unload_cap = a
                yield Horizontal(
                    Static(f"[b]{label}[/]\n[dim]aboard {a:,} · stores {s:,}[/]", classes="row-head"),
                    AmountStepper(c.value, step=_STEP, maximum=max(load_cap, unload_cap)),
                    Button("Load", id=f"load-{c.value}", classes="act", disabled=load_cap == 0),
                    Button("Unload", id=f"unload-{c.value}", classes="act", disabled=unload_cap == 0),
                    classes="row",
                )
            # Colonists: settle from the berth into an owned colony (never loaded back here).
            if p.owned_by_you and p.colonizable:
                room = max(0, p.habitability_cap - p.colonists)
                settle_cap = min(p.ship_colonists, room)  # rules._settle_colonists clamp
                yield Horizontal(
                    Static(f"[b]Colonists[/]\n[dim]berth {p.ship_colonists:,} · colony {p.colonists:,} "
                           f"· room {room:,}[/]", classes="row-head"),
                    AmountStepper(_COLONIST_ROW, step=_STEP, maximum=settle_cap),
                    Button("Settle", id=f"unload-{_COLONIST_ROW}", classes="act",
                           disabled=settle_cap == 0),
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
        return self.query_one(f"#stepper-{key}", AmountStepper).amount

    def _set_amount(self, key: str, value: int) -> None:
        self.query_one(f"#stepper-{key}", AmountStepper).set_amount(value)

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
        elif bid.startswith("load-"):
            self._do_row(bid[5:], to_planet=False)
        elif bid.startswith("unload-"):
            self._do_row(bid[7:], to_planet=True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in a row's amount field submits that row in the colony-supply direction
        (unload goods to stores / settle colonists) — the dominant loop (WP-PR07)."""
        iid = event.input.id or ""
        if iid.startswith("amt-"):
            self._do_row(iid[4:], to_planet=True)

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
        self._apply(BatchTransferCargo(
            self._planet_id, {c.value: 10**9 for c in Commodity}, to_planet=False))

    def action_unload_all(self) -> None:
        self._apply(BatchTransferCargo(
            self._planet_id, {c.value: 10**9 for c in Commodity}, to_planet=True))
