"""TerritoryScreen — deploy forces & work the devices (§10, §14 — WP72).

Visual-first: what is already deployed in this sector sits in a DataTable at the
top (fighters with mode/toll, mines, beacon, interdictor — classic-TW fogged by
the projection), and each deployable is a **card** in a grid below: a small art
sprite, the carried stock, a one-line purpose, and its Deploy button. Buttons
are Textual-focusable, so Tab/Shift-Tab walks the cards and Enter fires the
focused one — the hotkeys stay as accelerators only. Stock is bought at the
StarDock (Devices tab / `F`/`M`); deployment is barred in the Core.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Input, Static

from edge.core.economy import EconomyError
from edge.core.movement import MovementError
from edge.core.rules import (
    DeployBeacon, DeployFighters, DeployMines, LaunchProbe, RemoveLimpets,
    ToggleInterdictor,
)
from edge.server.service import GameService
from edge.tui import art_adapter
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


# Hand glyph art for the deployables that have no procedural sprite. Kept tiny
# (3 rows) so a card never dominates its grid cell.
_GLYPH_ART = {
    "armid": "[red] ✺     ✺ [/]\n[red]    ✺    [/]\n[red] ✺     ✺ [/]",
    "limpet": "[magenta] ⌾   ⌾ [/]\n[magenta]   ⌾   [/]\n[magenta] ⌾   ⌾ [/]",
    "beacon": "[cyan]   ▲   [/]\n[cyan]  ╱│╲  [/]\n[cyan]~ ═╧═ ~[/]",
    "probe": "[yellow]    ◦ ▶[/]\n[yellow]  ◦╱   [/]\n[yellow] ◦     [/]",
    "interdictor": "[red] ╲ │ ╱ [/]\n[red] ─ ◉ ─ [/]\n[red] ╱ │ ╲ [/]",
    "strip": "[green] ✂  ⌾  [/]\n[green]  ⌾  ✂ [/]\n[green] ✂  ⌾  [/]",
}


class _DeployCard(Vertical):
    """One deployable: art, carried stock, a one-line purpose, and its button."""

    DEFAULT_CSS = """
    _DeployCard {
        border: round $primary; padding: 0 1; height: auto; margin: 0 1 1 0;
    }
    _DeployCard:focus-within { border: round $accent; background: $boost; }
    _DeployCard .card-art { height: 3; content-align: center middle; text-align: center; }
    _DeployCard .card-stock { text-style: bold; }
    _DeployCard .card-desc { color: $text-muted; height: auto; }
    _DeployCard Button { margin-top: 1; width: 100%; }
    """

    def __init__(self, *, card_id: str, title: str, art: Text | str, stock: str,
                 desc: str, button: str, enabled: bool = True) -> None:
        super().__init__(classes="deploy-card")
        self._card_id = card_id
        self._title = title
        self._art = art
        self._stock = stock
        self._desc = desc
        self._button = button
        self._enabled = enabled

    def compose(self) -> ComposeResult:
        yield Static(self._art, classes="card-art")
        yield Static(self._stock, classes="card-stock")
        yield Static(self._desc, classes="card-desc")
        yield Button(self._button, id=f"go-{self._card_id}", disabled=not self._enabled)

    def on_mount(self) -> None:
        self.border_title = self._title


class TerritoryScreen(Screen):
    # Accelerators only — every deployable is a focusable card with a button.
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
Each deployable is a card: [b]Tab[/]/[b]Shift-Tab[/] walk the cards and [b]Enter[/]
fires the focused button (the keys above are accelerators for the same cards).
The table shows what is already deployed here — foreign mines stay invisible.
Deployment is barred in Core Space; toll fighters levy latinum on entrants;
limpet mines tag passing hulls so their owner can track them."""

    CSS = """
    TerritoryScreen #territory-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    TerritoryScreen #territory-body { padding: 1 2 0 2; }
    TerritoryScreen #deployed-panel {
        border: round $secondary; height: auto; padding: 0 1; margin-bottom: 1;
    }
    TerritoryScreen #deployed-panel DataTable { height: auto; max-height: 8; }
    TerritoryScreen #deploy-grid { grid-size: 3; grid-gutter: 0 1; height: auto; }
    TerritoryScreen .warn { color: $warning; margin-bottom: 1; }
    """

    def __init__(self, service: GameService, pid: int = 1) -> None:
        super().__init__()
        self._service = service
        self._pid = pid

    # --- layout ----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        t = self._service.territory_view(self._pid)
        sector = self._service.game_view(self._pid).sector
        yield Static(f"TERRITORY & DEVICES · Sector {t.sector_display}", id="territory-title")
        with VerticalScroll(id="territory-body"):
            yield self._deployed_panel(t, sector)
            if t.in_core:
                yield Static("Deployment is barred in Core Space.", classes="warn")
            with Grid(id="deploy-grid"):
                yield from self._cards(t)
        yield Footer()

    def _deployed_panel(self, t: object, sector: object) -> Vertical:
        """What already sits in this sector, tabular (fog pre-applied upstream)."""
        rows: list[tuple[str, str, str]] = []
        force = getattr(sector, "force", None)
        if force is not None and force.fighters > 0:
            toll = f", toll {force.toll:,}" if force.mode == "toll" else ""
            who = "[green]you[/]" if force.yours else f"[red]{force.owner}[/]"
            rows.append(("Fighters", f"{force.fighters:,} ({force.mode}{toll})", who))
        if force is not None and force.armid_mines > 0:
            rows.append(("Armid mines", f"{force.armid_mines:,}", "[green]you[/]"))
        if force is not None and force.limpet_mines > 0:
            rows.append(("Limpet mines", f"{force.limpet_mines:,}", "[green]you[/]"))
        beacon = getattr(sector, "beacon", None)
        if beacon:
            rows.append(("Beacon", f"“{beacon}”", "—"))
        if t.interdictor_active:  # type: ignore[attr-defined]
            rows.append(("Interdictor", "engaged — flight pinned (daily turn tax)",
                         "[green]you[/]"))
        if t.limpets:  # type: ignore[attr-defined]
            rows.append(("Limpets on your hull",
                         f"{t.limpets} attached",  # type: ignore[attr-defined]
                         "[red]a rival[/]"))
        children: list[Static | DataTable]
        if rows:
            table: DataTable = DataTable(id="deployed-table", zebra_stripes=True,
                                         cursor_type="row")
            table.add_columns("Asset", "Details", "Owner")
            for asset, details, owner in rows:
                table.add_row(asset, details, owner)
            children = [table]
        else:
            children = [Static("[dim]Nothing deployed in this sector.[/]")]
        panel = Vertical(*children, id="deployed-panel")
        panel.border_title = "Deployed in this sector"
        return panel

    def _cards(self, t: object) -> list[_DeployCard]:
        fighter_art = art_adapter.sprite("ship", "fighter", seed=11, width=12, height=3)
        cards = [
            _DeployCard(
                card_id="fighters", title="Fighters", art=fighter_art,
                stock=f"aboard: {t.fighters:,}",  # type: ignore[attr-defined]
                desc="Garrison the sector: defend it, deny it, or levy a toll on entrants.",
                button="Deploy fighters…", enabled=t.fighters > 0),  # type: ignore[attr-defined]
            _DeployCard(
                card_id="armid", title="Armid mines",
                art=Text.from_markup(_GLYPH_ART["armid"]),
                stock=f"aboard: {t.mines:,} mines",  # type: ignore[attr-defined]
                desc="Detonate against hostile hulls on entry — shields absorb, mines spend.",
                button="Lay armid mines…", enabled=t.mines > 0),  # type: ignore[attr-defined]
            _DeployCard(
                card_id="limpet", title="Limpet mines",
                art=Text.from_markup(_GLYPH_ART["limpet"]),
                stock=f"aboard: {t.mines:,} mines",  # type: ignore[attr-defined]
                desc="Cling to passing hulls and betray their position to you.",
                button="Lay limpet mines…", enabled=t.mines > 0),  # type: ignore[attr-defined]
            _DeployCard(
                card_id="beacon", title="Comms beacon",
                art=Text.from_markup(_GLYPH_ART["beacon"]),
                stock="one message per sector",
                desc="Plant a short message every visitor to this sector will read.",
                button="Plant beacon…"),
            _DeployCard(
                card_id="probe", title="Probe",
                art=Text.from_markup(_GLYPH_ART["probe"]),
                stock=f"aboard: {t.probes}",  # type: ignore[attr-defined]
                desc="Fire at a charted sector for a one-shot recon report.",
                button="Launch probe…", enabled=t.probes > 0),  # type: ignore[attr-defined]
            _DeployCard(
                card_id="interdictor", title="Interdictor",
                art=Text.from_markup(_GLYPH_ART["interdictor"]),
                stock=("engaged" if t.interdictor_active else  # type: ignore[attr-defined]
                       ("idle" if t.interdictor_owned else "not installed")),  # type: ignore[attr-defined]
                desc="Pin this sector while engaged — nothing flees it (daily turn tax).",
                button=("Disengage" if t.interdictor_active else "Engage"),  # type: ignore[attr-defined]
                enabled=t.interdictor_owned),  # type: ignore[attr-defined]
        ]
        if t.limpets:  # type: ignore[attr-defined]
            where = ("here" if t.at_service_point  # type: ignore[attr-defined]
                     else "at a StarDock or your own base")
            cards.append(_DeployCard(
                card_id="strip", title="Strip limpets",
                art=Text.from_markup(_GLYPH_ART["strip"]),
                stock=f"fee: {t.limpet_removal_fee:,} latinum",  # type: ignore[attr-defined]
                desc=f"Pay the yard to scrape off attached limpets — removable {where}.",
                button="Strip limpets", enabled=t.at_service_point))  # type: ignore[attr-defined]
        return cards

    # --- helpers ---------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "go-fighters": self.action_deploy_fighters, "go-armid": self.action_deploy_armid,
            "go-limpet": self.action_deploy_limpets, "go-beacon": self.action_beacon,
            "go-probe": self.action_probe, "go-interdictor": self.action_interdictor,
            "go-strip": self.action_remove_limpets,
        }
        handler = actions.get(event.button.id or "")
        if handler is not None:
            handler()

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
