"""PlanetScreen — orbit view, wired to the live service (UI_MOCKUPS.md §3, §4.2).

Reads `planet_view` for the planet in the player's current sector: type, owner,
colony population, allocation, stores, starbase status. `C` claims/colonizes an
unowned colonizable world by landing the colonists aboard; `D` descends (WP6).
The planet screen is **colony matters only** (WP80): all starbase ops — assault,
repair, salvage, claim, and the base's market/services — live in the unified
`BaseScreen`; the base status line here is a click-through (`B` or click).
The stores and citadel blocks are widget panels: a stores DataTable (colony vs.
hold) with a Transfer… button (the unified goods/colonist editor), and a citadel panel whose art shows a different
structure per development stage (survey site → scaffolding → keep → keep + gun →
shielded fortress) with Build/treasury buttons. Hotkeys stay as accelerators.
With no service (screenshot harness) it shows a static sample.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, DataTable, Footer, Static

from edge.core.citadels import CitadelError
from edge.core.combat import CombatError
from edge.core.economy import EconomyError
from edge.core.dto import PlanetDTO
from edge.core.movement import MovementError
from edge.core.planets import pretty_planet_type
from edge.core.rules import (
    BuildCitadel, Colonize, DeployGenesis, Descend, InvadePlanet, MineBelt, PlanetDeposit,
    PlanetWithdraw,
)
from edge.server.service import GameService
from edge.tui.chrome import EdgeScreen, notify_warning
from edge.tui import art_adapter
from edge.tui.screens.amount import AmountPrompt
from edge.tui.screens.confirm import ConfirmScreen
from edge.tui.dummy import sample_surface
from edge.tui.screens.surface import SurfaceScreen
from edge.tui.widgets import ClickableEntry


# Citadel art, one structure per development stage (§4.2, WP54): an unbuilt survey
# site, construction scaffolding, the L1 treasury keep, the L2 keep + planetary gun,
# How much one −/+ press moves the invasion wing. Wings run to the hundreds, so stepping by one
# would be useless; the exact figure is still typeable, and `[A]` commits the lot.
_INVADE_STEP = 10

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


class PlanetScreen(EdgeScreen):
    BINDINGS = [
        Binding("escape", "back", "Break orbit"),
        Binding("d", "descend", "Descend"),
        Binding("c", "colonize", "Claim/Colonize"),
        Binding("g", "genesis", "Genesis"),
        Binding("m", "mine", "Mine belt"),
        Binding("k", "build_citadel", "Build citadel"),
        Binding("plus", "treasury_deposit", "Deposit"),
        Binding("minus", "treasury_withdraw", "Withdraw"),
        Binding("i", "invade", "Invade"),
        # `P` boards the base here too, as it does on the sector view — the verb keeps
        # one key everywhere (a base *is* the port where it orbits, §4.2/WP80).
        Binding("p", "enter_base", "Enter base"),
        Binding("t", "unload_cargo", "Unload cargo"),
        Binding("l", "load_cargo", "Load cargo"),
    ]
    # WP-UI06: both irreversibly commit troops / re-form the world — confirmed.
    ACTION_DANGER = {"invade": "destructive", "genesis": "destructive"}

    HELP_TITLE = "Planet orbit"
    HELP = """\
Colony matters live here; every starbase op (repair · salvage · claim · assault ·
market · services) is on the base screen — [b]P[/] or click the base line.
The Stores and Citadel panels are button-driven ([b]Tab[/] walks the buttons,
[b]Enter[/] fires): [b]Transfer…[/] opens one editor to haul cargo between ship and
stores and to settle colonists onto the colony; start builds and move the treasury
from the citadel panel. Citadel builds draw equipment from [i]stores[/], so supply
runs in trips are the intended loop; the citadel art grows with its level.
[b]I[/] invades a hostile world once its defences are down, and asks how many of your
fighters to land ([b]A[/] commits them all) — troops you hold back stay aboard."""

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
    PlanetScreen #identity-panel { margin-top: 0; }
    PlanetScreen.compact #orbit-body { width: 1fr; padding: 0 1; }
    PlanetScreen.compact #orbit-art { display: none; }
    PlanetScreen.compact .citadel-art { display: none; }
    PlanetScreen.compact .orbit-panel { margin-top: 0; padding: 0 1; }
    PlanetScreen.compact .orbit-panel DataTable { max-height: 5; }
    PlanetScreen.compact .buttons { margin-top: 0; }
    PlanetScreen.wide #orbit-body { width: 3fr; }
    PlanetScreen.wide #orbit-art { width: 2fr; }
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
                yield self._identity_panel(p)
                # A belt is a spatial feature, not a colony: no descent, no colony stores
                # or citadel — only its orbital scan/mining note (§4.2, WP-PR06).
                if not p.landable:
                    yield self._orbital_panel(p)
                else:
                    yield self._stores_panel(p)
                if p.landable and p.owned_by_you and (p.citadel_level > 0 or p.can_build_citadel
                                       or p.citadel_build_target > 0):
                    yield self._citadel_panel(p)
                if p.can_invade:
                    yield Static(f"[red]\\[I] Invade[/] — land some or all of your "
                                 f"{p.ship_fighters:,} fighters against the garrison "
                                 f"({p.fighters:,}).", classes="section")
                elif p.invade_blocker:
                    yield Static(f"[dim]Invasion barred: {p.invade_blocker}.[/]", classes="section")
                if p.starbase:
                    colour = "yellow" if p.starbase_derelict else "green"
                    yield ClickableEntry(
                        f"[{colour}]#[/] Orbital starbase — {p.starbase}   "
                        f"[dim]\\[P] Enter base[/]",
                        dest="starbase", ref=p.starbase_id, classes="section")
                if not p.genesis_blocker:
                    yield Static(f"[green]\\[G] Genesis[/] — re-form this world (torpedoes: {p.ship_genesis})")
                elif p.genesis_has_device:
                    # A torpedo aboard but this world can't take it — name the reason.
                    yield Static(f"[dim]Genesis barred: {p.genesis_blocker}.[/]")
            detail = self.app.scene_art.planet_detail
            art = PlanetSprite(
                art_adapter.sprite(
                    "planet", art_adapter.planet_subtype(p.ptype),
                    seed=p.planet_id, width=detail.max_width, height=detail.max_height,
                ),
                id="orbit-art",
            )
            art.tooltip = ("Scan for finds in orbit" if not p.landable
                           else "Click to descend to the surface")
            yield art
        yield Footer()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # A belt has no surface — hide the Descend affordance (and its footer hint) so the
        # control never implies a landing that the reducer would reject (§4.2, WP-PR06).
        if action == "descend" and not self._planet.landable:
            return False
        # Mining is belt-only (PT-30): hide the affordance/footer hint elsewhere so it never
        # implies an extraction the reducer would reject.
        if action == "mine" and self._planet.mine_yield <= 0:
            return False
        return True

    def _identity_panel(self, p: PlanetDTO) -> Vertical:
        """Keep identity, ownership, habitability, and colony state together."""
        cap = f"{p.habitability_cap:,}" if p.colonizable else "not colonizable"
        children: list[Static] = [
            Static(f"Type  [b]{pretty_planet_type(p.ptype)}[/]   Owner  [cyan]{p.owner}[/]"),
            Static(f"Habitability  {cap}   Population  {p.colonists:,}"),
        ]
        if p.owned_by_you:
            alloc = "   ".join(f"{label} {pct}%" for label, pct in p.allocation)
            if p.fighter_allocation_pct:
                alloc += f"   Garrison {p.fighter_allocation_pct}%"
            children.append(Static(f"Production  {alloc}"))
        hint = self._claim_hint()
        if hint:
            children.append(Static(hint))
        panel = Vertical(*children, id="identity-panel", classes="orbit-panel")
        panel.border_title = "World & colony"
        return panel

    def on_planet_sprite_descend(self, msg: PlanetSprite.Descend) -> None:
        if not self._planet.landable:
            self.notify("No surface to land on — scan for finds in orbit instead.", timeout=3)
            return
        self.action_descend()

    def _orbital_panel(self, p: PlanetDTO) -> Vertical:
        """A belt's orbital readout (§4.2, WP-PR06): a spatial feature, scanned/mined, not landed on."""
        lines = [
            "[dim]A spatial feature, not a colony world — it cannot be landed on, "
            "colonized, or given a citadel.[/]",
            "[cyan]Scan[/] the sector for finds; anything logged appears in your codex.",
        ]
        if p.mine_yield > 0:
            lines.append(f"[green]\\[M] Mine belt[/] — haul up to {p.mine_yield} equipment aboard "
                         "(costs a turn).")
        elif p.extractable:
            lines.append("[dim]Raw ore drifts here for the taking — orbital mining.[/]")
        panel = Vertical(*(Static(t) for t in lines), id="orbital-panel", classes="orbit-panel")
        panel.border_title = "Orbit"
        return panel

    def _claim_hint(self) -> str:
        p = self._planet
        if p.owned_by_you:
            return "[dim]Your colony.[/]"
        if not p.landable:
            return ""  # the orbital panel explains a belt; no colony hint applies
        if not p.colonizable:
            return "[dim]Uncolonizable — extraction only.[/]"
        if not p.claimable:
            return "[dim]Already claimed.[/]"
        if p.ship_colonists <= 0:
            return "[yellow]Unclaimed — recruit colonists at a Stardock first.[/]"
        return f"[green]\\[C] Colonize[/] — land {p.ship_colonists} colonists aboard."

    def _stores_panel(self, p: PlanetDTO) -> Vertical:
        """Colony stores vs. the ship's hold, tabular, with haul buttons (§4.2)."""
        aboard: dict[str, int] = {}
        if self._service is not None:
            ship = self._service.game_view(self._pid).ship
            aboard = {h.label: h.qty for h in ship.holds}
        table: DataTable[Any] = DataTable(id="stores-table", zebra_stripes=True, cursor_type="row")
        table.add_columns("Commodity", "In stores", "Aboard")
        for label, qty in p.stores:
            table.add_row(label, f"{qty:,}", f"{aboard.get(label, 0):,}")
        children: list[Static | DataTable[Any] | Horizontal] = [table]
        if p.owned_by_you:
            children.append(Horizontal(
                Button("Transfer…", id="btn-transfer", variant="primary"),
                classes="buttons"))
            hint = ("[dim]Open the transfer editor to haul goods and settle colonists.[/]"
                    if p.colonizable else
                    "[dim]Citadel builds draw equipment from stores — supply runs in trips are the loop.[/]")
            children.append(Static(hint))
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
            "btn-transfer": self.action_transfer,
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
        """Land a chosen number of carried fighters in a ground assault (§4.2, WP55).

        The reducer has always taken an amount; the screen used to commit the whole wing, so a
        failed assault cost every fighter aboard (PT-53). The prompt defaults to all — the
        common case — but you may hold a reserve back, clamped to `1..ship_fighters`.
        """
        if self._service is None:
            self.action_noop()
            return
        service = self._service
        p = self._planet
        if not p.can_invade:
            self.notify(p.invade_blocker or "Nothing to invade here.", timeout=2)
            return

        def _go(fighters: int | None) -> None:
            if not fighters:
                return
            try:
                service.apply(self._pid, InvadePlanet(p.planet_id, fighters))
            except (EconomyError, CombatError, CitadelError) as exc:
                notify_warning(self, str(exc))
                return
            self._reopen()

        self.app.push_screen(AmountPrompt(
            f"Invade {p.name}?\n"
            f"Garrison {p.fighters:,} · you carry {p.ship_fighters:,} fighters.\n"
            "How many do you land? Committed troops do not come back.",
            maximum=p.ship_fighters, step=_INVADE_STEP, commit_label="Invade",
            dangerous=True), _go)

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
        service = self._service
        p = self._planet
        if p.genesis_blocker:
            self.notify(f"Can't deploy Genesis: {p.genesis_blocker}.", timeout=2)
            return

        def _go(ok: bool | None) -> None:
            if not ok:
                return
            try:
                service.apply(self._pid, DeployGenesis(planet_id=p.planet_id))
            except (EconomyError, MovementError) as exc:
                notify_warning(self, str(exc))
                return
            self.notify("Genesis deployed — the world is re-forming!", timeout=2)
            self.app.pop_screen()
            self.app.push_screen(PlanetScreen(
                service.planet_view(self._pid, p.planet_id), service, self._pid))

        self.app.push_screen(ConfirmScreen(
            f"Fire a Genesis torpedo at {p.name}?\n"
            "The world is re-formed — this cannot be undone."), _go)

    def action_transfer(self) -> None:
        """Open the unified transfer editor: haul goods and settle colonists (WP-PR07)."""
        if self._service is None:
            self.action_noop()
            return
        p = self._planet
        if not p.owned_by_you:
            self.notify("You can only transfer cargo at a world you own.", timeout=2)
            return
        from edge.tui.screens.transfer import TransferWorkbenchScreen
        # Reopen the orbit view on close so colony numbers reflect what was moved.
        self.app.push_screen(
            TransferWorkbenchScreen(self._service, self._pid, p.planet_id),
            lambda _=None: self._reopen())

    # Back-compat accelerators (T/L): both open the one transfer editor now.
    def action_unload_cargo(self) -> None:
        self.action_transfer()

    def action_load_cargo(self) -> None:
        self.action_transfer()

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

    def action_mine(self) -> None:
        """Hand-mine an asteroid belt, taking raw goods aboard (§4.2, PT-30)."""
        if self._service is None:
            self.action_noop()
            return
        p = self._planet
        if p.mine_yield <= 0:
            self.notify("There's nothing to mine here.", timeout=2)
            return
        service = self._service
        try:
            service.apply(self._pid, MineBelt(planet_id=p.planet_id))
        except (EconomyError, MovementError) as exc:
            notify_warning(self, str(exc))
            return
        self.notify("Mined the belt — raw goods stowed aboard.", timeout=2)
        self.app.pop_screen()
        self.app.push_screen(PlanetScreen(
            service.planet_view(self._pid, p.planet_id), service, self._pid))

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
