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
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core.citadels import CitadelError
from edge.core.economy import EconomyError
from edge.core.dto import PlanetDTO
from edge.core.engine_room import EngineRoomError
from edge.core.enums import Subsystem
from edge.core.movement import MovementError
from edge.core.planets import pretty_planet_type
from edge.core.rules import (
    BuildCitadel, Cannibalize, Colonize, DeployGenesis, Descend, PlanetDeposit, PlanetWithdraw,
)
from edge.server.service import GameService
from edge.tui import art_adapter
from edge.tui.dummy import sample_surface
from edge.tui.screens.surface import SurfaceScreen


class PlanetSprite(Static):
    """The orbit planet sprite — clicking it descends to the surface (like pressing D)."""

    class Descend(Message):
        pass

    def on_click(self) -> None:
        self.post_message(self.Descend())


class PlanetScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Break orbit"),
        Binding("d", "descend", "Descend"),
        Binding("t", "noop", "Trade"),
        Binding("c", "colonize", "Claim/Colonize"),
        Binding("s", "salvage", "Salvage"),
        Binding("g", "genesis", "Genesis"),
        Binding("k", "build_citadel", "Build citadel"),
        Binding("plus", "treasury_deposit", "Deposit"),
        Binding("minus", "treasury_withdraw", "Withdraw"),
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
        yield Static(f"ORBIT · {p.name} · {pretty_planet_type(p.ptype)}", id="orbit-title")
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
                    colour = "yellow" if p.starbase_derelict else "green"
                    yield Static(f"[{colour}]#[/] Orbital starbase — {p.starbase}", classes="section")
                    if p.salvage:
                        parts = ", ".join(f"{label}" for _, _, label in p.salvage)
                        yield Static(f"[yellow]\\[S] Salvage[/] — {len(p.salvage)} components: {parts}")
                if p.owned_by_you and (p.citadel_level > 0 or p.can_build_citadel
                                       or p.citadel_build_target > 0):
                    yield Static(self._citadel_lines(), classes="section")
                hint = self._claim_hint()
                if hint:
                    yield Static(hint, classes="section")
                if p.genesis_eligible and p.ship_genesis > 0:
                    yield Static(f"[green]\\[G] Genesis[/] — re-form this world (torpedoes: {p.ship_genesis})")
            detail = self.app.scene_art.planet_detail
            art = PlanetSprite(
                art_adapter.sprite(
                    "planet", art_adapter.planet_subtype(p.ptype),
                    seed=p.planet_id, width=detail.max_width, height=detail.max_height,
                ),
                id="orbit-art",
            )
            art.tooltip = "Click to descend to the surface"
            yield art
        yield Footer()

    def on_planet_sprite_descend(self, msg: PlanetSprite.Descend) -> None:
        self.action_descend()

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

    def _citadel_lines(self) -> str:
        """The citadel status + build affordance block (§4.2, WP54)."""
        p = self._planet
        rows = [f"[b]Citadel[/] level {p.citadel_level}   "
                f"treasury [yellow]{p.treasury:,}[/]   garrison {p.fighters:,}"]
        if p.citadel_build_target > 0:
            rows.append(f"[cyan]Building level {p.citadel_build_target} — {p.citadel_build_pct}%[/]")
        elif p.can_build_citadel and p.citadel_next_cost is not None:
            eq, lat = p.citadel_next_cost
            rows.append(f"[green]\\[K] Build level {p.citadel_level + 1}[/] — "
                        f"{eq} equipment + {lat:,} latinum")
        if p.citadel_level >= 1:
            rows.append("[dim]\\[+]/[-] deposit / withdraw 1,000 to the treasury[/]")
        return "\n".join(rows)

    def action_build_citadel(self) -> None:
        if self._service is None:
            self.action_noop()
            return
        p = self._planet
        try:
            self._service.apply(self._pid, BuildCitadel(p.planet_id))
        except (EconomyError, CitadelError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.notify("Citadel construction begun.", timeout=2)
        self._reopen()

    def action_treasury_deposit(self) -> None:
        self._treasury(PlanetDeposit(self._planet.planet_id, 1_000), "Deposited to treasury")

    def action_treasury_withdraw(self) -> None:
        self._treasury(PlanetWithdraw(self._planet.planet_id, 1_000), "Withdrew from treasury")

    def _treasury(self, command: object, ok: str) -> None:
        if self._service is None:
            self.action_noop()
            return
        try:
            self._service.apply(self._pid, command)  # type: ignore[arg-type]
        except (EconomyError, CitadelError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.notify(ok, timeout=2)
        self._reopen()

    def _reopen(self) -> None:
        assert self._service is not None
        self.app.pop_screen()
        self.app.push_screen(PlanetScreen(
            self._service.planet_view(self._pid, self._planet.planet_id), self._service, self._pid))

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

    def action_salvage(self) -> None:
        """Cannibalize one component from the orbital base into the ship's hold (§4.2)."""
        if self._service is None:
            self.action_noop()
            return
        p = self._planet
        if p.starbase_id is None or not p.salvage:
            self.notify("Nothing to salvage here.", timeout=2)
            return
        subsystem, slot_index, _ = p.salvage[0]
        try:
            self._service.apply(self._pid, Cannibalize(
                subsystem=Subsystem(subsystem), slot_index=slot_index, starbase_id=p.starbase_id))
        except (EngineRoomError, EconomyError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.notify("Component salvaged.", timeout=2)
        self.app.pop_screen()
        self.app.push_screen(PlanetScreen(
            self._service.planet_view(self._pid, p.planet_id), self._service, self._pid))

    def action_genesis(self) -> None:
        """Deploy a Genesis torpedo to terraform this world (§4.2, WP10)."""
        if self._service is None:
            self.action_noop()
            return
        p = self._planet
        if not p.genesis_eligible or p.ship_genesis <= 0:
            self.notify("Can't deploy genesis here (need an eligible world + a torpedo).", timeout=2)
            return
        try:
            self._service.apply(self._pid, DeployGenesis(planet_id=p.planet_id))
        except (EconomyError, MovementError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.notify("Genesis deployed — the world is re-forming!", timeout=2)
        self.app.pop_screen()
        self.app.push_screen(PlanetScreen(
            self._service.planet_view(self._pid, p.planet_id), self._service, self._pid))

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_descend(self) -> None:
        if self._service is None:
            self.app.push_screen(SurfaceScreen(sample_surface()))  # screenshot harness
            return
        p = self._planet
        try:
            self._service.apply(self._pid, Descend(planet_id=p.planet_id))
        except (EconomyError, MovementError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.app.push_screen(SurfaceScreen(
            self._service.surface_view(self._pid, p.planet_id), self._service, self._pid))

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
