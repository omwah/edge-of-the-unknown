"""TerritoryScreen — deploy forces & work the devices (§10, §14 — WP72).

The sector-territory game (WP41) and the WP56 devices, surfaced: deploy carried
fighters (defensive / offensive / toll), lay armid or limpet mines, plant a comms
beacon, launch a probe at a charted (or lead-known) sector, toggle the interdictor,
and strip attached limpets at a service point. Reads `territory_view`; stock is
bought at the StarDock (Devices tab / `F`/`M`). Deployment is barred in the Core.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Input, Static

from edge.core.economy import EconomyError
from edge.core.movement import MovementError
from edge.core.rules import (
    DeployBeacon, DeployFighters, DeployMines, LaunchProbe, RemoveLimpets,
    ToggleInterdictor,
)
from edge.server.service import GameService
from edge.tui.screens.picker import ListPicker
from edge.tui.screens.stardock import _AmountInput
from edge.tui.screens.travel import TravelPromptScreen


class _ModePicker(ListPicker):
    """Pick a fighter-garrison mode (§10, WP41)."""

    def __init__(self) -> None:
        super().__init__("Garrison mode?", [
            ("[b]Defensive[/] — engage hostile entrants", "defensive"),
            ("[b]Offensive[/] — engage any non-owner", "offensive"),
            ("[b]Toll[/] — levy latinum on entrants", "toll"),
        ], width=48)


class TerritoryScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("f", "deploy_fighters", "Deploy fighters"),
        Binding("m", "deploy_armid", "Lay armid mines"),
        Binding("l", "deploy_limpets", "Lay limpet mines"),
        Binding("b", "beacon", "Beacon"),
        Binding("p", "probe", "Launch probe"),
        Binding("i", "interdictor", "Interdictor"),
        Binding("r", "remove_limpets", "Strip limpets"),
    ]

    HELP_TITLE = "Territory & devices"
    HELP = """\
Deployment is barred in Core Space. Toll fighters levy latinum on entrants;
limpet mines tag passing hulls so their owner can track them."""

    CSS = """
    TerritoryScreen #territory-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    TerritoryScreen #territory-body { padding: 1 2; }
    TerritoryScreen .section { margin-top: 1; }
    """

    def __init__(self, service: GameService, pid: int = 1) -> None:
        super().__init__()
        self._service = service
        self._pid = pid

    def compose(self) -> ComposeResult:
        t = self._service.territory_view(self._pid)
        yield Static(f"TERRITORY & DEVICES · Sector {t.sector_display}", id="territory-title")
        with VerticalScroll(id="territory-body"):
            yield Static(f"Carried   fighters [b]{t.fighters:,}[/]   mines [b]{t.mines:,}[/]   "
                         f"probes [b]{t.probes}[/]")
            if t.devices:
                yield Static("Devices   " + "   ".join(f"{d} x{n}" for d, n in t.devices))
            if t.in_core:
                yield Static("[yellow]Deployment is barred in Core Space.[/]", classes="section")
            if t.force_line:
                yield Static(f"Your force here   [green]{t.force_line}[/]", classes="section")
            if t.beacon_text:
                yield Static(f"Beacon   [cyan]“{t.beacon_text}”[/]", classes="section")
            if t.interdictor_owned:
                status = "[green]engaged[/]" if t.interdictor_active else "[dim]idle[/]"
                yield Static(f"Interdictor   {status}   [dim](daily turn tax while engaged)[/]",
                             classes="section")
            if t.limpets:
                where = ("[I] strip here" if t.at_service_point
                         else "removable at a StarDock or your own base")
                yield Static(f"[red]{t.limpets} limpet(s) attached[/] — fee "
                             f"{t.limpet_removal_fee:,}; {where}", classes="section")
            yield Static(
                "[dim][b]F[/] Deploy fighters   [b]M[/] Armid mines   [b]L[/] Limpet mines   "
                "[b]B[/] Beacon   [b]P[/] Probe   [b]I[/] Interdictor   [b]R[/] Strip limpets[/]",
                classes="section")
        yield Footer()

    # --- helpers ---------------------------------------------------------------

    def _issue(self, command: object, ok: str) -> None:
        try:
            self._service.apply(self._pid, command)  # type: ignore[arg-type]
        except (EconomyError, MovementError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.notify(ok, timeout=2)
        self._reopen()

    def _reopen(self) -> None:
        self.app.pop_screen()
        self.app.push_screen(TerritoryScreen(self._service, self._pid))

    def action_back(self) -> None:
        self.app.pop_screen()

    # --- deploy ---------------------------------------------------------------

    def action_deploy_fighters(self) -> None:
        def _mode(count: int, mode: str | None) -> None:
            if mode is None:
                return
            if mode == "toll":
                self.app.push_screen(
                    _AmountInput("Toll per entrant?"),
                    lambda toll: toll and self._issue(
                        DeployFighters(count=count, mode="toll", toll=toll),
                        f"Deployed {count} fighters (toll {toll})"))
                return
            self._issue(DeployFighters(count=count, mode=mode),
                        f"Deployed {count} fighters ({mode})")

        def _count(count: int | None) -> None:
            if count:
                self.app.push_screen(_ModePicker(), lambda m: _mode(count, m))

        self.app.push_screen(_AmountInput("Deploy how many fighters?"), _count)

    def _deploy_mines(self, kind: str) -> None:
        def _go(count: int | None) -> None:
            if count:
                self._issue(DeployMines(count=count, kind=kind),
                            f"Laid {count} {kind} mine(s)")
        self.app.push_screen(_AmountInput(f"Lay how many {kind} mines?"), _go)

    def action_deploy_armid(self) -> None:
        self._deploy_mines("armid")

    def action_deploy_limpets(self) -> None:
        self._deploy_mines("limpet")

    def action_beacon(self) -> None:
        def _go(text: str | None) -> None:
            if text:
                self._issue(DeployBeacon(text=text), "Beacon planted")
        self.app.push_screen(_BeaconInput(), _go)

    # --- devices ---------------------------------------------------------------

    def action_probe(self) -> None:
        def _go(dest: int | None) -> None:
            if dest is None:
                return
            internal = self._service.resolve_display_id(dest)
            if internal is None:
                self.notify(f"No sector {dest}.", severity="warning", timeout=3)
                return
            self._issue(LaunchProbe(dest_sector=internal), "Probe away")
        self.app.push_screen(TravelPromptScreen(), _go)

    def action_interdictor(self) -> None:
        self._issue(ToggleInterdictor(), "Interdictor toggled")

    def action_remove_limpets(self) -> None:
        self._issue(RemoveLimpets(), "Limpets stripped")


class _BeaconInput(ModalScreen[str | None]):
    """A one-line prompt for the beacon text (§10, WP41)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]
    CSS = """
    _BeaconInput { align: center middle; background: $background 60%; }
    _BeaconInput Input { width: 60; }
    """

    def compose(self) -> ComposeResult:
        yield Static("[b]Beacon text[/]  (Enter to plant, Esc to cancel)")
        yield Input(placeholder="marker message…", id="beacon-input")

    def on_mount(self) -> None:
        self.query_one("#beacon-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def action_cancel(self) -> None:
        self.dismiss(None)
