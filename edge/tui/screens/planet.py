"""PlanetScreen — orbit view, wired to the live service (UI_MOCKUPS.md §3, §4.2).

Reads `planet_view` for the planet in the player's current sector: type, owner,
colony population, allocation, stores, starbase status. `C` claims/colonizes an
unowned colonizable world by landing the colonists aboard; `D` descends (WP6).
The planet screen is **colony matters only** (WP80): all starbase ops — assault,
repair, salvage, claim, and the base's market/services — live in the unified
`BaseScreen`; the base status line here is a click-through (`B` or click).
The stores and citadel blocks are widget panels: a stores DataTable (colony vs.
hold) with Unload/Load buttons, and a citadel panel whose art shows a different
structure per development stage (survey site → scaffolding → keep → keep + gun →
shielded fortress) with Build/treasury buttons. Hotkeys stay as accelerators.
With no service (screenshot harness) it shows a static sample.
"""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from edge.core.citadels import CitadelError
from edge.core.combat import CombatError
from edge.core.economy import EconomyError
from edge.core.dto import PlanetDTO
from edge.core.movement import MovementError
from edge.core.planets import pretty_planet_type
from edge.core.enums import Commodity
from edge.core.rules import (
    BuildCitadel, Colonize, DeployGenesis, Descend, InvadePlanet, PlanetDeposit,
    PlanetWithdraw, TransferCargo,
)
from edge.server.service import GameService
from edge.tui.chrome import notify_warning
from edge.tui import art_adapter
from edge.tui.screens.confirm import ConfirmScreen
from edge.tui.dummy import sample_surface
from edge.tui.screens.surface import SurfaceScreen
from edge.tui.widgets import ClickableEntry


# Citadel art, one structure per development stage (§4.2, WP54): an unbuilt survey
# site, construction scaffolding, the L1 treasury keep, the L2 keep + planetary gun,
# and the L3 siege fortress under its shield dome. Markup-safe (no '[' in the art).
_CITADEL_ART = {
    "site": ("[dim] ·    ·    ·  [/]\n"
             "[dim]   ▂▂▂▂▂▂▂▂   [/]\n"
             "[dim] ·    ·    ·  [/]"),
    "building": ("[yellow]       ┌─╴    [/]\n"
                 "[yellow]  ▒▒▒  │      [/]\n"
                 "[yellow]  ▒█▒▒▒▒▒     [/]\n"
                 "[dim]  ▔▔▔▔▔▔▔▔▔   [/]"),
    "l1": ("[cyan]     ▄█▄      [/]\n"
           "[cyan]    ▐███▌     [/]\n"
           "[dim]  ▔▔▔▔▔▔▔▔▔   [/]"),
    "l2": ("[cyan]     ▄█▄      [/]\n"
           "[cyan]    ▐███▌ ═╬► [/]\n"
           "[cyan]    █████     [/]\n"
           "[dim]  ▔▔▔▔▔▔▔▔▔   [/]"),
    "l3": ("[blue]  ⌒⌒⌒⌒⌒⌒⌒⌒⌒   [/]\n"
           "[cyan]    ▟███▙     [/]\n"
           "[cyan]   ▐█████▌═╬► [/]\n"
           "[cyan]   ███████    [/]"),
}
_STAGE_LABEL = {
    "site": "unbuilt site", "building": "under construction",
    "l1": "treasury keep (L1)", "l2": "planetary gun (L2)", "l3": "siege fortress (L3)",
}


def _citadel_stage(p: PlanetDTO) -> str:
    if p.citadel_build_target > 0:
        return "building"
    return {0: "site", 1: "l1", 2: "l2"}.get(p.citadel_level, "l3")


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
        Binding("c", "colonize", "Claim/Colonize"),
        Binding("g", "genesis", "Genesis"),
        Binding("k", "build_citadel", "Build citadel"),
        Binding("plus", "treasury_deposit", "Deposit"),
        Binding("minus", "treasury_withdraw", "Withdraw"),
        Binding("i", "invade", "Invade"),
        Binding("b", "enter_base", "Enter base"),
        Binding("t", "unload_cargo", "Unload cargo"),
        Binding("l", "load_cargo", "Load cargo"),
    ]
    # WP-UI06: both irreversibly commit troops / re-form the world — confirmed.
    ACTION_DANGER = {"invade": "destructive", "genesis": "destructive"}

    HELP_TITLE = "Planet orbit"
    HELP = """\
Colony matters live here; every starbase op (repair · salvage · claim · assault ·
market · services) is on the base screen — [b]B[/] or click the base line.
The Stores and Citadel panels are button-driven ([b]Tab[/] walks the buttons,
[b]Enter[/] fires): haul cargo between ship and stores, start builds, move the
treasury. Citadel builds draw equipment from [i]stores[/], so supply runs in
trips are the intended loop; the citadel art grows with its level."""

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
    PlanetScreen .orbit-panel {
        border: round $primary; padding: 0 1; height: auto; margin-top: 1;
    }
    PlanetScreen .orbit-panel:focus-within { border: round $accent; }
    PlanetScreen .orbit-panel DataTable { height: auto; max-height: 8; }
    PlanetScreen .orbit-panel .buttons { height: auto; margin-top: 1; }
    PlanetScreen .orbit-panel Button { margin-right: 1; }
    PlanetScreen .citadel-art { height: auto; }
    PlanetScreen .section-tight { margin-top: 1; }
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
                if p.owned_by_you:
                    alloc = "   ".join(f"{label} {pct}%" for label, pct in p.allocation)
                    if p.fighter_allocation_pct:
                        alloc += f"   Garrison {p.fighter_allocation_pct}%"
                    yield Static(f"Allocation   {alloc}", classes="section")
                yield self._stores_panel(p)
                if p.owned_by_you and (p.citadel_level > 0 or p.can_build_citadel
                                       or p.citadel_build_target > 0):
                    yield self._citadel_panel(p)
                if p.can_invade:
                    yield Static(f"[red]\\[I] Invade[/] — land {p.ship_fighters} fighters "
                                 f"against the garrison ({p.fighters}).", classes="section")
                elif p.invade_blocker:
                    yield Static(f"[dim]Invasion barred: {p.invade_blocker}.[/]", classes="section")
                if p.starbase:
                    colour = "yellow" if p.starbase_derelict else "green"
                    yield ClickableEntry(
                        f"[{colour}]#[/] Orbital starbase — {p.starbase}   "
                        f"[dim]\\[B] Enter base[/]",
                        dest="starbase", ref=p.starbase_id, classes="section")
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

    def _stores_panel(self, p: PlanetDTO) -> Vertical:
        """Colony stores vs. the ship's hold, tabular, with haul buttons (§4.2)."""
        aboard: dict[str, int] = {}
        if self._service is not None:
            ship = self._service.game_view(self._pid).ship
            aboard = {h.label: h.qty for h in ship.holds}
        table: DataTable = DataTable(id="stores-table", zebra_stripes=True, cursor_type="row")
        table.add_columns("Commodity", "In stores", "Aboard")
        for label, qty in p.stores:
            table.add_row(label, f"{qty:,}", f"{aboard.get(label, 0):,}")
        children: list[Static | DataTable | Horizontal] = [table]
        if p.owned_by_you:
            children.append(Horizontal(
                Button("Unload → stores…", id="btn-unload"),
                Button("Load aboard…", id="btn-load"),
                classes="buttons"))
            children.append(Static("[dim]Citadel builds draw equipment from stores — "
                                   "supply runs in trips are the loop.[/]"))
        panel = Vertical(*children, classes="orbit-panel")
        panel.border_title = "Stores"
        return panel

    def _citadel_panel(self, p: PlanetDTO) -> Vertical:
        """The citadel: staged art, status, and its build/treasury buttons (§4.2, WP54)."""
        stage = _citadel_stage(p)
        art = Static(Text.from_markup(_CITADEL_ART[stage]), classes="citadel-art")
        status = Static(
            f"Level [b]{p.citadel_level}[/]   treasury [yellow]{p.treasury:,}[/]   "
            f"garrison {p.fighters:,}", classes="section-tight")
        children: list[Static | Horizontal] = [art, status]
        if p.citadel_build_target > 0:
            done = max(1, p.citadel_build_pct // 10)
            bar = "█" * done + "░" * (10 - done)
            children.append(Static(
                f"[cyan]Building level {p.citadel_build_target}  {bar} "
                f"{p.citadel_build_pct}%[/]  [dim](colonist-days accrue daily)[/]"))
        buttons: list[Button] = []
        if p.citadel_build_target == 0 and p.can_build_citadel and p.citadel_next_cost is not None:
            eq, lat = p.citadel_next_cost
            buttons.append(Button(
                f"Build level {p.citadel_level + 1} — {eq} equ + {lat:,} latinum",
                id="btn-build", variant="primary"))
        if p.citadel_level >= 1:
            buttons.append(Button("Deposit 1k", id="btn-cit-dep"))
            buttons.append(Button("Withdraw 1k", id="btn-cit-wd"))
        if buttons:
            children.append(Horizontal(*buttons, classes="buttons"))
        panel = Vertical(*children, classes="orbit-panel")
        panel.border_title = f"Citadel — {_STAGE_LABEL[stage]}"
        return panel

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "btn-unload": self.action_unload_cargo, "btn-load": self.action_load_cargo,
            "btn-build": self.action_build_citadel,
            "btn-cit-dep": self.action_treasury_deposit,
            "btn-cit-wd": self.action_treasury_withdraw,
        }
        handler = actions.get(event.button.id or "")
        if handler is not None:
            handler()

    def action_build_citadel(self) -> None:
        if self._service is None:
            self.action_noop()
            return
        p = self._planet
        try:
            self._service.apply(self._pid, BuildCitadel(p.planet_id))
        except (EconomyError, CitadelError) as exc:
            notify_warning(self, str(exc))
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
            notify_warning(self, str(exc))
            return
        self.notify(ok, timeout=2)
        self._reopen()

    def _reopen(self) -> None:
        assert self._service is not None
        self.app.pop_screen()
        self.app.push_screen(PlanetScreen(
            self._service.planet_view(self._pid, self._planet.planet_id), self._service, self._pid))

    def action_invade(self) -> None:
        """Land all carried fighters in a ground assault on this world (§4.2, WP55)."""
        if self._service is None:
            self.action_noop()
            return
        p = self._planet
        if not p.can_invade:
            self.notify(p.invade_blocker or "Nothing to invade here.", timeout=2)
            return

        def _go(ok: bool | None) -> None:
            if not ok:
                return
            try:
                self._service.apply(self._pid, InvadePlanet(p.planet_id, p.ship_fighters))
            except (EconomyError, CombatError, CitadelError) as exc:
                notify_warning(self, str(exc))
                return
            self._reopen()

        self.app.push_screen(ConfirmScreen(
            f"Invade {p.name} with {p.ship_fighters} fighters?\n"
            "Committed troops do not come back."), _go)

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
            notify_warning(self, str(exc))
            return
        self.notify("Colony established!", timeout=2)
        self.app.pop_screen()
        self.app.push_screen(PlanetScreen(
            self._service.planet_view(self._pid, p.planet_id), self._service, self._pid))

    def action_enter_base(self) -> None:
        """Open the unified base view — all starbase ops live there (§4.2, WP80)."""
        if self._service is None:
            self.action_noop()
            return
        p = self._planet
        if p.starbase_id is None:
            self.notify("No orbital starbase here.", timeout=2)
            return
        from edge.tui.screens.base import BaseScreen
        self.app.push_screen(BaseScreen(self._service, self._pid, p.starbase_id))

    @on(ClickableEntry.Picked)
    def on_base_picked(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest == "starbase":
            self.action_enter_base()

    def action_genesis(self) -> None:
        """Deploy a Genesis torpedo to terraform this world (§4.2, WP10)."""
        if self._service is None:
            self.action_noop()
            return
        p = self._planet
        if not p.genesis_eligible or p.ship_genesis <= 0:
            self.notify("Can't deploy genesis here (need an eligible world + a torpedo).", timeout=2)
            return

        def _go(ok: bool | None) -> None:
            if not ok:
                return
            try:
                self._service.apply(self._pid, DeployGenesis(planet_id=p.planet_id))
            except (EconomyError, MovementError) as exc:
                notify_warning(self, str(exc))
                return
            self.notify("Genesis deployed — the world is re-forming!", timeout=2)
            self.app.pop_screen()
            self.app.push_screen(PlanetScreen(
                self._service.planet_view(self._pid, p.planet_id), self._service, self._pid))

        self.app.push_screen(ConfirmScreen(
            f"Fire a Genesis torpedo at {p.name}?\n"
            "The world is re-formed — this cannot be undone."), _go)

    def _transfer(self, *, to_planet: bool) -> None:
        """Pick a commodity + amount, then haul it (§4.2 — the colony-supply rail).

        The reducer clamps to what fits/is aboard, so a big number means "all"; this
        is how citadel equipment reaches a world (the build draws from stores).
        """
        if self._service is None:
            self.action_noop()
            return
        p = self._planet
        if not p.owned_by_you:
            self.notify("You can only transfer cargo at a world you own.", timeout=2)
            return

        def _amount(picked: int | str | None) -> None:
            if picked is None:
                return
            commodity = Commodity(str(picked))

            def _go(units: int | None) -> None:
                if not units:
                    return
                try:
                    self._service.apply(self._pid, TransferCargo(
                        p.planet_id, commodity, units, to_planet=to_planet))
                except EconomyError as exc:
                    notify_warning(self, str(exc))
                    return
                self._reopen()

            from edge.tui.screens.stardock import _AmountInput
            verb = "Unload" if to_planet else "Load"
            self.app.push_screen(
                _AmountInput(f"{verb} how many {commodity.value.replace('_', ' ')}? "
                             "(a big number = all)"), _go)

        from edge.tui.screens.picker import ListPicker
        self.app.push_screen(ListPicker(
            "Which commodity?",
            [(f"[b]{c.value.replace('_', ' ').title()}[/]", c.value) for c in Commodity],
            width=40), _amount)

    def action_unload_cargo(self) -> None:
        self._transfer(to_planet=True)

    def action_load_cargo(self) -> None:
        self._transfer(to_planet=False)

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
            notify_warning(self, str(exc))
            return
        self.app.push_screen(SurfaceScreen(
            self._service.surface_view(self._pid, p.planet_id), self._service, self._pid))

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
