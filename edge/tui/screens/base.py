"""BaseScreen — the unified orbital-starbase view (§4.2, WP80).

One screen for every base, its tabs gated by `StarbaseDTO.standing`:

- **yours**    → Station (slots / repair / salvage) + Trade + Hardware + Bank
- **derelict** → Station (salvage + keystone-first repair) and Claim once live
- **open**     → Trade (another owner's market, tolerated) — Assault stays legal
- **hostile**  → status only; Assault is the door

The Station tab reuses the engine-room slot idiom with base colours/icons; the
Trade tab fronts the WP78 base-hosted market (the standard port screen does the
actual trading); Hardware/Bank are the WP53 forward-base services, present only
when the service-point resolver grants them, so the tabs shown and what the
reducers accept never drift.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Static, TabbedContent

from edge.core.combat import CombatError
from edge.core.dto import StarbaseDTO
from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.enums import Component, ComponentTier, Subsystem
from edge.core.movement import MovementError
from edge.core.rules import (
    AssaultStarbase, BuyComponent, BuyMissiles, Cannibalize, ClaimStarbase, Deposit,
    RepairStarbase, Withdraw,
)
from edge.server.service import GameService
from edge.tui.chrome import EdgeScreen, TitleBar, notify_success, notify_warning
from edge.tui.screens.confirm import ConfirmScreen
from edge.tui.screens.port import _haggle_highlighted, _trade_highlighted
from edge.tui.component_workbench import (
    ComponentWorkbench,
    STARBASE_WORKBENCH_PROFILE,
    WorkbenchCapabilities,
)
from edge.tui.station_art import StationArtHeader
from edge.tui.widgets import ServiceHub, TradePanel

_STANDING_STYLE = {
    "yours": "[green]yours[/]",
    "open": "[cyan]open[/]",
    "hostile": "[red]hostile[/]",
    "derelict": "[yellow]derelict[/]",
}

_DISPLAY_TO_KIND = {
    "FUSION REACTOR": Subsystem.FUSION_REACTOR,
    "SCREENS": Subsystem.SCREENS,
    "MAIN GUN": Subsystem.MAIN_GUN,
}

class BaseScreen(EdgeScreen):
    BINDINGS = [
        Binding("escape", "back", "Leave base"),
        Binding("t", "trade", "Trade highlighted"),
        # `G`, as on the Port and Stardock — this screen hosts the same `TradePanel`, so
        # the verb cannot answer to a different key depending on the route in (PT-32).
        Binding("g", "haggle", "Haggle highlighted"),
        Binding("r", "repair", "Repair slot"),
        Binding("s", "salvage", "Salvage"),
        Binding("c", "claim", "Claim"),
        Binding("a", "assault", "Assault"),
        Binding("b", "buy", "Buy"),
        Binding("m", "buy_missiles", "Missile"),
        Binding("d", "deposit", "Deposit 1k"),
        Binding("w", "withdraw", "Withdraw 1k"),
        # Tab-focus accelerators (WP-PR2-01 / PT-32): jump to a tab + focus its content.
        # Hardware shares its only free in-title letter ('e') with Trade, so it stays
        # arrow/Enter-reachable rather than colliding.
        Binding("u", "focus_tab('status')", "Status", show=False),
        Binding("o", "focus_tab('station')", "Station", show=False),
        Binding("e", "focus_tab('trade')", "Trade", show=False),
        Binding("k", "focus_tab('bank')", "Bank", show=False),
    ]

    # entry_id -> the letter emphasised in its tab title (WP-PR2-01 / PT-32).
    _TAB_ACCEL = {"status": "u", "station": "o", "trade": "e", "bank": "k"}
    ACTION_DANGER = {"assault": "destructive"}  # WP-UI06: confirms before firing

    HELP_TITLE = "Starbase"
    HELP = """\
Tabs follow your standing with the base (yours · open · hostile · derelict).
Repair fills the [b]reactor keystone first[/] — waking a derelict also opens its
market; a player-owned host earns a cut of outsider trades.

Jump to a tab and focus its contents with the [b]underlined letter[/] in each tab
title (Stat[b]u[/]s · Stati[b]o[/]n · Trad[b]e[/] · Ban[b]k[/]); Enter on the tab rail
does the same for the active tab."""

    CSS = """
    BaseScreen #base-title { background: $warning; }
    BaseScreen TabPane { padding: 1 2; }
    BaseScreen DataTable { height: auto; max-height: 18; }
    BaseScreen .note { margin-top: 1; color: $text-muted; }
    """

    def __init__(self, service: GameService, player_id: int, starbase_id: int,
                 initial_tab: str | None = None) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id
        self._base_id = starbase_id
        self._initial_tab = initial_tab

    # --- layout ---------------------------------------------------------------

    def compose(self) -> ComposeResult:
        v = self._view()
        standing = _STANDING_STYLE.get(v.standing, v.standing)
        yield TitleBar(
            f"⌂ {v.name.upper()} · {v.planet_name} · Sector {v.sector_display}",
            f"{v.owner} · {standing} · integrity {v.integrity_pct}%",
            id="base-title",
        )
        entries = self._services(v)
        preferred = ("station" if v.standing in ("derelict", "yours") else
                     "trade" if v.market_port_id is not None and v.market_open else "status")
        initial = self._initial_tab or preferred
        yield ServiceHub(entries, initial=initial, accelerators=self._TAB_ACCEL,
                         id="base-services")
        yield Footer()

    def _view(self) -> StarbaseDTO:
        return self._service.starbase_view(self._pid, self._base_id)

    def _services(self, v: StarbaseDTO) -> list[tuple[str, str, Widget, str | None]]:
        station_reason = (None if v.standing in ("derelict", "yours") else
                          "Station access requires an unowned derelict or a base you own.")
        trade_reason = (None if v.market_port_id is not None and v.market_open else
                        v.market_notice or "This base has no operational market.")
        # A powered but battered base withholds services until repaired above the gate (WP-PR04).
        gate_reason = (f"Repair the base above {v.service_integrity_min_pct}% integrity to reopen "
                       f"services (currently {v.integrity_pct}%)."
                       if v.operational and not v.services_operational else None)
        hardware_reason = (None if v.hardware else gate_reason or
                           "Component service requires an operational, friendly base.")
        bank_reason = (None if "banking" in v.services else gate_reason or
                       "Banking requires a player-owned operational base with vault service.")
        return [
            ("Status", "status", self._art_pane(v, "status", self._status_pane(v)), None),
            ("Station", "station", self._art_pane(v, "station", self._station_pane(v)), station_reason),
            ("Trade", "trade", self._art_pane(v, "trade", self._trade_pane(v)), trade_reason),
            ("Hardware", "hardware", self._art_pane(v, "hardware", self._hardware_pane(v)), hardware_reason),
            ("Bank", "bank", self._art_pane(v, "bank", self._bank_pane(v)), bank_reason),
        ]

    @staticmethod
    def _art_pane(v: StarbaseDTO, service: str, content: Widget) -> Vertical:
        condition = v.standing if v.standing in ("derelict", "hostile") else "open"
        return Vertical(
            StationArtHeader(
                "starbase", v.archetype_id or "humanoid_diplomat", service,
                identity=v.starbase_id, condition=condition),
            content,
        )

    def _station_pane(self, v: StarbaseDTO) -> Vertical:
        on_hand = self._service.engine_room_view(self._pid).on_hand
        workbench = ComponentWorkbench(
            v.subsystems,
            on_hand,
            STARBASE_WORKBENCH_PROFILE,
            WorkbenchCapabilities(install=True, full_repair=True, salvage=True),
            id="base-component-workbench",
        )
        lines = []
        if v.empty_slots:
            keystone = sum(1 for _, _, k in v.empty_slots if k)
            note = " (incl. the reactor keystone)" if keystone else ""
            lines.append(f"[cyan]\\[R] Repair[/] — {len(v.empty_slots)} empty slot(s){note}; "
                         "installs a carried component, keystone first.")
        if v.salvage:
            parts = ", ".join(label for _, _, label in v.salvage)
            lines.append(f"[yellow]\\[S] Salvage[/] — {len(v.salvage)} component(s): {parts}")
        if v.claimable:
            lines.append(f"[green]\\[C] Claim[/] — take this base as a forward foothold "
                         f"for {v.claim_cost:,} latinum.")
        if not v.operational:
            lines.append("[dim]The base is dark — fill the reactor keystone to wake it "
                         "(and its market).[/]")
        return Vertical(workbench,
                        Static("\n".join(lines) or "[dim]All installations live.[/]",
                               classes="note"))

    def _trade_pane(self, v: StarbaseDTO) -> Vertical:
        lines: list[str] = []
        children: list[object] = []
        port = self._service.current_port_view(self._pid)
        if v.market_open and port is not None:
            children.append(TradePanel(port, latinum=v.latinum, show_title=True,
                                       id="base-trade-panel"))
            lines.append("[dim]T trades the highlighted row · G haggles.[/]")
        else:
            lines.append(f"[red]Market closed[/] — {v.market_notice}.")
        if v.trade_cut_pct:
            who = "you" if v.standing == "yours" else v.owner
            lines.append(f"[dim]The owner ({who}) takes a {v.trade_cut_pct}% cut of outsider "
                         "trades from the port's purse.[/]")
        children.append(Static("\n".join(lines), classes="note"))
        return Vertical(*children)  # type: ignore[arg-type]

    def _hardware_pane(self, v: StarbaseDTO) -> Vertical:
        table: DataTable[Any] = DataTable(id="base-hardware-table", cursor_type="row")
        table.add_columns("Component", "Tier", "Price", "")
        for item in v.hardware:
            mark = "" if item.affordable else "[red]✗[/]"
            table.add_row(item.component, item.tier, f"{item.price:,}", mark,
                          key=f"{item.component}:{item.tier}")
        head = Static(f"[b]HARDWARE[/]  Latinum [b yellow]{v.latinum:,}[/] slips  "
                      f"[dim](frontier prices ×{v.fee_frac:g})[/]")
        note = Static("[dim]B buys the highlighted part; M resupplies a missile"
                      + (f" ({v.missile_price:,}).[/]" if v.missile_price else ".[/]"),
                      classes="note")
        return Vertical(head, table, note)

    def _bank_pane(self, v: StarbaseDTO) -> Vertical:
        return Vertical(
            Static(f"[b]BASE VAULT[/]  cash [b yellow]{v.latinum:,}[/]  "
                   f"banked [b green]{v.bank_balance:,}[/]"),
            Static("[dim]D deposits 1,000; W withdraws 1,000 (interest-free — §4.2).[/]",
                   classes="note"),
        )

    def _status_pane(self, v: StarbaseDTO) -> VerticalScroll:
        lines = [f"Owner  [cyan]{v.owner}[/]",
                 f"Standing  {_STANDING_STYLE.get(v.standing, v.standing)}",
                 f"Integrity  {v.integrity_pct}%"]
        if v.standing == "hostile":
            lines.append("\n[red]The base's guns track your ship — its market and services "
                         "are closed to you.[/]")
        if v.assaultable:
            lines.append("[red]\\[A] Assault[/] — engage the base's defenses; victory razes it.")
        return VerticalScroll(Static("\n".join(lines)))

    # --- actions ----------------------------------------------------------------

    def action_focus_tab(self, entry_id: str) -> None:
        """Jump to a service tab and focus its primary content (WP-PR2-01 / PT-32)."""
        self.query_one(ServiceHub).activate_and_focus(entry_id)

    def _reopen(self) -> None:
        try:
            active = self.query_one(TabbedContent).active
        except Exception:
            active = None
        self.app.pop_screen()
        self.app.push_screen(BaseScreen(self._service, self._pid, self._base_id,
                                        initial_tab=active))

    def _issue(self, command: object, ok: str) -> bool:
        try:
            self._service.apply(self._pid, command)  # type: ignore[arg-type]
        except (EconomyError, EngineRoomError, MovementError, CombatError) as exc:
            notify_warning(self, str(exc))
            return False
        notify_success(self, ok)
        return True

    def action_trade(self) -> None:
        if self.query_one(TabbedContent).active != "trade":
            self.notify("Switch to the Trade tab to trade.", timeout=2)
            return
        _trade_highlighted(self, self._service, self._pid)

    def action_haggle(self) -> None:
        if self.query_one(TabbedContent).active != "trade":
            self.notify("Switch to the Trade tab to haggle.", timeout=2)
            return
        _haggle_highlighted(self, self._service, self._pid)

    def action_repair(self) -> None:
        """Install the selected carried component into the selected open base slot."""
        v = self._view()
        if not v.empty_slots or v.standing not in ("derelict", "yours"):
            self.notify("No open base slot to repair here.", timeout=2)
            return
        from edge.tui.screens.engine_room import _parse_on_hand
        try:
            selection = self.query_one(ComponentWorkbench).selection
        except Exception:
            self.notify("Open the Station tab to repair installations.", timeout=2)
            return
        if len(selection.loose_components) != 1 or len(selection.slots) != 1:
            self.notify("Select one carried component and one empty installation slot.", timeout=3)
            return
        subsystem, slot_index = selection.slots[0]
        slot = next(s for s in v.subsystems if s.name == subsystem).slots[slot_index]
        if slot.state != "empty":
            self.notify("The selected installation slot is not empty.", timeout=2)
            return
        component, tier = _parse_on_hand(selection.loose_components[0])
        kind = _DISPLAY_TO_KIND[subsystem]
        if self._issue(RepairStarbase(v.starbase_id, kind, slot_index,
                                      component, tier),
                       f"Installed {component.value} ({tier.name}) into the {subsystem}."):
            self._reopen()

    def action_salvage(self) -> None:
        """Cannibalize one component from the base into the ship's hold (§4.2)."""
        v = self._view()
        if not v.salvage:
            self.notify("Nothing to salvage here.", timeout=2)
            return
        try:
            selection = self.query_one(ComponentWorkbench).selection
        except Exception:
            self.notify("Open the Station tab to salvage components.", timeout=2)
            return
        if len(selection.slots) != 1:
            self.notify("Select one removable installation component.", timeout=2)
            return
        subsystem, slot_index = selection.slots[0]
        kind = _DISPLAY_TO_KIND[subsystem]
        allowed = {(name, index) for name, index, _ in v.salvage}
        if (kind.value, slot_index) not in allowed:
            self.notify("That installation cannot be salvaged.", timeout=2)
            return
        if self._issue(Cannibalize(subsystem=kind, slot_index=slot_index,
                                   starbase_id=v.starbase_id),
                       "Component salvaged."):
            self._reopen()

    def action_claim(self) -> None:
        v = self._view()
        if not v.claimable:
            self.notify("No claimable base here (it must be operational and unowned).", timeout=2)
            return
        if self._issue(ClaimStarbase(v.starbase_id),
                       "The base answers to you now — a forward foothold."):
            self._reopen()

    def action_assault(self) -> None:
        v = self._view()
        if not v.assaultable:
            self.notify("Nothing to assault here.", timeout=2)
            return

        def _go(ok: bool | None) -> None:
            if not ok:
                return
            if self._issue(AssaultStarbase(v.starbase_id), "Assault under way!"):
                # Back to the game screen — it opens the encounter screen on resume.
                self.app.pop_screen()

        self.app.push_screen(ConfirmScreen(
            f"Assault {v.name} ({v.owner})?\nIts guns will answer."), _go)

    def action_buy(self) -> None:
        try:
            table = self.query_one("#base-hardware-table", DataTable)
        except Exception:
            self.notify("No hardware for sale here.", timeout=2)
            return
        if self.query_one(TabbedContent).active != "hardware":
            self.notify("Switch to the Hardware tab to buy.", timeout=2)
            return
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if row_key.value is None:
            return
        component, tier = row_key.value.split(":")
        if self._issue(BuyComponent(Component(component), ComponentTier[tier]),
                       f"Bought {component}"):
            self._reopen()

    def action_buy_missiles(self) -> None:
        v = self._view()
        if "munitions" not in v.services:
            self.notify("This base offers no munitions.", timeout=2)
            return
        if self._issue(BuyMissiles(count=1), "Resupplied a homing missile"):
            self._reopen()

    def action_deposit(self) -> None:
        if self._issue(Deposit(amount=1_000), "Deposited 1,000 slips"):
            self._reopen()

    def action_withdraw(self) -> None:
        if self._issue(Withdraw(amount=1_000), "Withdrew 1,000 slips"):
            self._reopen()

    def action_back(self) -> None:
        self.app.pop_screen()
