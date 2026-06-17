"""PlanetScreen — orbit view, wired to the live service (UI_MOCKUPS.md §3, §4.2).

Reads `planet_view` for the planet in the player's current sector: type, owner,
colony population, allocation, stores, starbase status. `C` claims/colonizes an
unowned colonizable world by landing the colonists aboard; `D` descends (WP6).
With no service (screenshot harness) it shows a static sample.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core.economy import EconomyError
from edge.core.dto import PlanetDTO
from edge.core.rules import Colonize
from edge.server.service import GameService
from edge.tui import sprites
from edge.tui.dummy import sample_surface
from edge.tui.screens.surface import SurfaceScreen


class PlanetScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Break orbit"),
        Binding("d", "descend", "Descend"),
        Binding("t", "noop", "Trade"),
        Binding("c", "colonize", "Claim/Colonize"),
    ]

    CSS = """
    PlanetScreen #orbit-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    PlanetScreen #orbit-main { height: 1fr; }
    PlanetScreen #orbit-body { width: 2fr; padding: 1 2; }
    PlanetScreen #orbit-art {
        width: 1fr; height: 1fr; content-align: center top; text-align: center;
        color: $primary; text-style: bold;
    }
    PlanetScreen .section { margin-top: 1; }
    """

    def __init__(self, planet: PlanetDTO, service: GameService | None = None, pid: int = 1) -> None:
        super().__init__()
        self._planet = planet
        self._service = service
        self._pid = pid

    def compose(self) -> ComposeResult:
        p = self._planet
        yield Static(f"ORBIT · {p.name} · {p.ptype}", id="orbit-title")
        with Horizontal(id="orbit-main"):
            with VerticalScroll(id="orbit-body"):
                yield Static(f"Owner    [cyan]{p.owner}[/]")
                cap = f"{p.habitability_cap:,}" if p.colonizable else "—"
                yield Static(f"Habitability cap  {cap}      Colonists  {p.colonists:,}")
                stores = "   ".join(f"{label} {qty:,}" for label, qty in p.stores)
                yield Static(f"Stores   {stores}", classes="section")
                if p.owned_by_you:
                    alloc = "   ".join(f"{label} {pct}%" for label, pct in p.allocation)
                    yield Static(f"Allocation   {alloc}", classes="section")
                if p.starbase:
                    yield Static(f"[green]#[/] Orbital starbase — {p.starbase}", classes="section")
                hint = self._claim_hint()
                if hint:
                    yield Static(hint, classes="section")
            yield Static("\n".join(sprites.pick_planet_large(p.ptype)), id="orbit-art")
        yield Footer()

    def _claim_hint(self) -> str:
        p = self._planet
        if p.owned_by_you:
            return "[dim]Your colony.[/]"
        if not p.colonizable:
            return "[dim]Uncolonizable — extraction only.[/]"
        if not p.claimable:
            return "[dim]Already claimed.[/]"
        if p.ship_colonists <= 0:
            return "[yellow]Unclaimed — recruit colonists at a StarDock first.[/]"
        return f"[green]\\[C] Colonize[/] — land {p.ship_colonists} colonists aboard."

    def action_colonize(self) -> None:
        if self._service is None:
            self.action_noop()
            return
        p = self._planet
        if not p.claimable or p.ship_colonists <= 0:
            self.notify("Nothing to colonize here (need colonists + an unclaimed world).", timeout=2)
            return
        try:
            self._service.apply(self._pid, Colonize(p.planet_id, p.ship_colonists))
        except EconomyError as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.notify("Colony established!", timeout=2)
        self.app.pop_screen()
        self.app.push_screen(PlanetScreen(
            self._service.planet_view(self._pid, p.planet_id), self._service, self._pid))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_descend(self) -> None:
        self.app.push_screen(SurfaceScreen(sample_surface()))

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
