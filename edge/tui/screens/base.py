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

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static, TabbedContent, TabPane

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
from edge.tui.screens.confirm import ConfirmScreen

_STANDING_STYLE = {
    "yours": "[green]yours[/]",
    "open": "[cyan]open[/]",
    "hostile": "[red]hostile[/]",
    "derelict": "[yellow]derelict[/]",
}

# Station-tab slot glyphs — deliberately distinct from the engine room's [+]/[!]
# so a base panel never reads as your own ship.
_SLOT_GLYPH = {"filled": "[cyan]▣[/]", "knocked": "[red]▨[/]", "empty": "[dim]▢[/]"}


class BaseScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Leave base"),
        Binding("t", "trade", "Trade"),
        Binding("r", "repair", "Repair slot"),
        Binding("s", "salvage", "Salvage"),
        Binding("c", "claim", "Claim"),
        Binding("a", "assault", "Assault"),
        Binding("b", "buy", "Buy"),
        Binding("m", "buy_missiles", "Missile"),
        Binding("d", "deposit", "Deposit 1k"),
        Binding("w", "withdraw", "Withdraw 1k"),
    ]

    CSS = """
    BaseScreen #base-title {
        dock: top; height: 1; background: $warning; color: $background;
        text-style: bold; padding: 0 1;
    }
    BaseScreen TabPane { padding: 1 2; }
    BaseScreen DataTable { height: auto; max-height: 18; }
    BaseScreen .station-panel {
        height: auto; border: round $warning; padding: 0 1; margin: 0 1 1 0; width: 1fr;
    }
    BaseScreen #station-panels { height: auto; }
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
        yield Static(
            f"⌂ {v.name.upper()} · {v.planet_name} · Sector {v.sector_display} · "
            f"{v.owner} · {standing} · integrity {v.integrity_pct}%",
            id="base-title",
        )
        panes = list(self._panes(v))
        initial = self._initial_tab if self._initial_tab in [p.id for p in panes] else panes[0].id
        with TabbedContent(initial=initial or ""):
            yield from panes
        yield Footer()

    def _view(self) -> StarbaseDTO:
        return self._service.starbase_view(self._pid, self._base_id)

    def _panes(self, v: StarbaseDTO) -> list[TabPane]:
        panes: list[TabPane] = []
        if v.standing in ("derelict", "yours"):
            panes.append(TabPane("Station", self._station_pane(v), id="station"))
        if v.market_port_id is not None:
            panes.append(TabPane("Trade", self._trade_pane(v), id="trade"))
        if v.hardware:
            panes.append(TabPane("Hardware", self._hardware_pane(v), id="hardware"))
        if "banking" in v.services:
            panes.append(TabPane("Bank", self._bank_pane(v), id="bank"))
        if not panes or v.standing in ("open", "hostile"):
            panes.insert(0, TabPane("Status", self._status_pane(v), id="status"))
        return panes

    def _station_pane(self, v: StarbaseDTO) -> Vertical:
        panels: list[Static] = []
        for sub in v.subsystems:
            rows = []
            for slot in sub.slots:
                glyph = _SLOT_GLYPH.get(slot.state, "[dim]?[/]")
                label = slot.component or "[dim]____[/]"
                key = " [dim](keystone)[/]" if slot.keystone else ""
                rows.append(f" {glyph} {label}{key}")
            panel = Static("\n".join(rows), classes="station-panel")
            panel.border_title = sub.name
            panel.border_subtitle = f"→ {sub.derived}"
            panels.append(panel)
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
        return Vertical(Horizontal(*panels, id="station-panels"),
                        Static("\n".join(lines) or "[dim]All slots live.[/]", classes="note"))

    def _trade_pane(self, v: StarbaseDTO) -> Vertical:
        lines = [f"[b]{v.market_name}[/] — the base's trading post."]
        if v.market_open:
            lines.append("[green]Market open.[/]  [b]T[/] opens the trade desk.")
        else:
            lines.append(f"[red]Market closed[/] — {v.market_notice}.")
        if v.trade_cut_pct:
            who = "you" if v.standing == "yours" else v.owner
            lines.append(f"[dim]The owner ({who}) takes a {v.trade_cut_pct}% cut of outsider "
                         "trades from the port's purse.[/]")
        return Vertical(Static("\n".join(lines)))

    def _hardware_pane(self, v: StarbaseDTO) -> Vertical:
        table: DataTable = DataTable(id="base-hardware-table", cursor_type="row")
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
            self.notify(str(exc), severity="warning", timeout=3)
            return False
        self.notify(ok, timeout=2)
        return True

    def action_trade(self) -> None:
        v = self._view()
        if v.market_port_id is None:
            self.notify("No market at this base.", timeout=2)
            return
        if not v.market_open:
            self.notify(f"Market closed — {v.market_notice}.", severity="warning", timeout=3)
            return
        from edge.tui.screens.port import PortScreen
        self.app.push_screen(PortScreen(self._service, self._pid))

    def action_repair(self) -> None:
        """Install a carried component into the first open slot, keystone first (§4.2)."""
        v = self._view()
        if not v.empty_slots or v.standing not in ("derelict", "yours"):
            self.notify("No open base slot to repair here.", timeout=2)
            return
        from edge.tui.screens.engine_room import _parse_on_hand
        on_hand = self._service.engine_room_view(self._pid).on_hand
        if not on_hand:
            self.notify("No loose components aboard — buy or salvage parts first.", timeout=2)
            return
        subsystem, slot_index, _ = v.empty_slots[0]
        component, tier = _parse_on_hand(on_hand[0])
        if self._issue(RepairStarbase(v.starbase_id, Subsystem(subsystem), slot_index,
                                      component, tier),
                       f"Installed {component.value} ({tier.name}) into the {subsystem}."):
            self._reopen()

    def action_salvage(self) -> None:
        """Cannibalize one component from the base into the ship's hold (§4.2)."""
        v = self._view()
        if not v.salvage:
            self.notify("Nothing to salvage here.", timeout=2)
            return
        subsystem, slot_index, _ = v.salvage[0]
        if self._issue(Cannibalize(subsystem=Subsystem(subsystem), slot_index=slot_index,
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
