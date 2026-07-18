"""BaseScreen — the unified orbital-starbase view (§4.2, WP80).

One screen for every base, its tabs gated by `StarbaseDTO.standing`:

- **yours**    → Station (slots / repair / salvage) + Commodities + Hardware + Bank
- **derelict** → Station (salvage + keystone-first repair) and Claim once live
- **open**     → Commodities (another owner's market, tolerated) — Assault stays legal
- **hostile**  → Station's status panel only; Assault is the door

The **Station** tab reuses the engine-room slot idiom with base colours/icons and leads
with a bordered one-line **Status** panel (owner · standing · integrity): status is what
you read *while* you act, so it rides this tab instead of costing one of its own. Station
is therefore the only tab never withheld — a hostile base shows nothing else. The
**Commodities** tab fronts the WP78 base-hosted market (the standard port screen does the
actual trading); Hardware/Bank are the WP53 forward-base services, present only when the
service-point resolver grants them, so the tabs shown and what the reducers accept never
drift.

Keyboard model is PT-32 — **a tab owns its keys** (see `PANE_BINDINGS`), as on the
Computer and Stardock. A withheld tab carries no keys at all, and a verb this base cannot
honour is dropped from its tab (`_pane_actions`) — so the footer physically cannot offer
an action the reducers would refuse.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.css.query import NoMatches
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
from edge.tui.design import ActionDescriptor
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
    # Screen-wide keys only: leaving, and the tab accelerators. Every *verb* lives on its
    # own pane in PANE_BINDINGS below — never here — so the footer advertises exactly what
    # the visible tab can do. Back leads the footer on every screen (chrome.EdgeScreen).
    BINDINGS = [
        Binding("escape", "back", "Leave base"),
        # Tab-focus accelerators (WP-PR2-01 / PT-32): jump to a tab and focus its content
        # in one step. Underlined in the tab titles, kept off the footer — navigation, not
        # verbs. Moving the verbs onto the panes freed `H`, so Hardware finally has a
        # letter (it had none), and `H`/`B` now name the same services they do at the
        # Stardock.
        Binding("s", "focus_tab('station')", "Station", show=False),
        Binding("c", "focus_tab('trade')", "Commodities", show=False),
        Binding("h", "focus_tab('hardware')", "Hardware", show=False),
        Binding("b", "focus_tab('bank')", "Bank", show=False),
    ]

    # tab id -> the (key, action, description) triples that tab owns (PT-32). `ServiceHub`
    # binds each onto the tab's `ActionPane` in the `screen.` namespace, so the handlers
    # below stay on the screen while the keys live on the tab and follow focus. A tab that
    # is *unavailable* (gated by standing / service integrity) is given no keys at all, and
    # `_pane_actions` further drops any single verb this base cannot honour (you cannot
    # assault or claim a base you already hold), so the footer can never offer a verb the
    # reducers would refuse.
    #
    # `A` is Assault on Station and Deposit on Bank: one key, two verbs, two panes — the
    # reuse this model exists to allow. Keys match their meaning elsewhere: `T`/`G` trade
    # and haggle as on the Port and Stardock (this screen hosts the same `TradePanel`), and
    # `P` purchases as it does at the Stardock. Salvage is `V` and Claim is `L` because the
    # tab accelerators claimed `S` and `C` — a pane key may never shadow one of those.
    PANE_BINDINGS: dict[str, tuple[tuple[str, str, str], ...]] = {
        "station": (("r", "repair", "Repair slot"), ("v", "salvage", "Salvage"),
                    ("l", "claim", "Claim"), ("a", "assault", "Assault")),
        "trade": (("t", "trade", "Trade"), ("g", "haggle", "Haggle")),
        "hardware": (("p", "buy", "Purchase"), ("m", "buy_missiles", "Missile")),
        "bank": (("a", "deposit", "Deposit 1k"), ("w", "withdraw", "Withdraw 1k")),
    }

    # tab id -> the letter underlined in its tab title (WP-PR2-01 / PT-32). The `trade` id
    # is unchanged — only its *label* is Commodities now, matching the Stardock — so deep
    # links and `initial_tab` keep addressing it by the same name.
    _TAB_ACCEL = {"station": "s", "trade": "c", "hardware": "h", "bank": "b"}
    ACTION_DANGER = {"assault": "destructive"}  # WP-UI06: confirms before firing

    HELP_TITLE = "Starbase"
    HELP = """\
Tabs follow your standing with the base (yours · open · hostile · derelict).
Repair fills the [b]reactor keystone first[/] — waking a derelict also opens its
market; a player-owned host earns a cut of outsider trades.

Jump to a tab and focus its contents with the [b]underlined letter[/] in each tab
title ([b]S[/]tation · [b]C[/]ommodities · [b]H[/]ardware · [b]B[/]ank); Enter on the tab
rail does the same for the active tab. The base's [b]Status[/] rides the Station tab as a
one-line panel — it is what you read while you act, not a place you go.

Every action key [b]belongs to its tab[/], so the footer only offers what the tab you are
looking at can do — and a tab the base withholds offers nothing at all. On Station,
[b]R[/] repairs, [b]V[/] salvages, [b]L[/] claims and [b]A[/] assaults. [b]T[/] trades and
[b]G[/] haggles on Commodities; [b]P[/] purchases the highlighted part and [b]M[/]
resupplies a missile on Hardware; [b]A[/]/[b]W[/] bank 1,000 slips at a time."""

    CSS = """
    BaseScreen #base-title { background: $warning; }
    BaseScreen TabPane { padding: 1 2; }
    BaseScreen DataTable { height: auto; max-height: 18; }
    BaseScreen .note { margin-top: 1; color: $text-muted; }
    BaseScreen .service-unavailable { padding: 1 0; color: $text-muted; }

    /* The Station tab is a stack of bordered rows — Status, the subsystem bays, the
       loose-component panel. They are authored by three different widgets, so their
       insets have to be reconciled here or the borders step in and out down the screen:
       give every row the same left/right margin of 1, replace the bays' right margin with
       a grid gutter (a margin would shorten only the right-hand column), and drop the
       grid's top padding so Status sits directly on the bays. Scoped to BaseScreen — the
       ship's Engine Room hosts the same workbench and keeps its own spacing. */
    BaseScreen .status-panel {
        height: 3; border: round $primary; padding: 0 1; margin: 0 1;
    }
    /* Uniform grid rows + bays that fill them: every bay is the height of the tallest
       (the reactor's four slots plus its frame), so the rack reads as identical modules
       rather than a ragged skyline. Sizing the *row* rather than the bay is what makes a
       lone bay on the last row match its neighbours above. */
    BaseScreen ComponentWorkbench #workbench-grid,
    BaseScreen.compact ComponentWorkbench #workbench-grid {
        padding: 0 1; grid-gutter: 1; grid-rows: 6;
    }
    BaseScreen .starbase-bay { margin: 0; height: 100%; }
    /* Height auto, not 1fr: inside the scrolling Station body the rack must take the room
       it needs and let the body scroll, rather than being squeezed until a border is cut. */
    BaseScreen ComponentWorkbench { height: auto; }
    BaseScreen ComponentWorkbench #workbench-loose { margin: 0 1 1 1; }
    """

    def __init__(self, service: GameService, player_id: int, starbase_id: int,
                 initial_tab: str | None = None) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id
        self._base_id = starbase_id
        self._initial_tab = initial_tab
        self._withheld: set[str] = set()  # tabs the base gates shut (filled in compose)
        # PANE_BINDINGS minus the verbs this base cannot honour (filled in compose).
        self._live_actions: dict[str, tuple[tuple[str, str, str], ...]] = {}

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
        self._withheld = {entry_id for _label, entry_id, _content, reason in entries
                          if reason is not None}
        self._live_actions = self._pane_actions(v)
        preferred = ("station" if v.standing in ("derelict", "yours") else
                     "trade" if v.market_port_id is not None and v.market_open else "station")
        initial = self._initial_tab or preferred
        yield ServiceHub(entries, initial=initial, accelerators=self._TAB_ACCEL,
                         actions=self._live_actions, id="base-services")
        yield Footer()

    def _pane_actions(self, v: StarbaseDTO) -> dict[str, tuple[tuple[str, str, str], ...]]:
        """`PANE_BINDINGS` minus the verbs *this* base cannot honour right now.

        The same rule that withholds a whole tab, applied one level down to a single verb:
        a key that would only ever answer "nothing to assault here" should not be a key.
        You cannot assault a base you already hold, claim one that is not claimable, repair
        a full rack, salvage an empty one, or buy munitions a base does not sell — so none
        of those reach the footer, and the guards left in the handlers are belt-and-braces.
        """
        able = {
            "assault": v.assaultable,
            "claim": v.claimable,
            "repair": bool(v.empty_slots),
            "salvage": bool(v.salvage),
            "buy_missiles": "munitions" in v.services,
        }
        return {tab: tuple(t for t in triples if able.get(t[1], True))
                for tab, triples in self.PANE_BINDINGS.items()}

    def _active_tab(self) -> str:
        """The visible service tab's id (the unit every action keys on)."""
        return self.query_one(TabbedContent).active

    def action_descriptors(self) -> list[ActionDescriptor]:
        """The `.` menu / `?` help / palette list, scoped exactly like the footer (PT-32).

        Assembled from the *active* tab, because this screen's verbs live on its panes.
        Parity with the footer is proven in tests/test_ui_base_keys.py.
        """
        danger: dict[str, str] = self.ACTION_DANGER
        shown = [b for b in self.BINDINGS if isinstance(b, Binding) and b.show]
        out = [ActionDescriptor(id=b.action, title=b.description, help=b.description,
                                key=b.key, action=b.action) for b in shown]
        try:
            tab = self._active_tab()
        except NoMatches:  # before mount — the tab rail is not up yet
            return out
        # A withheld tab keeps none of its keys, and neither does a verb this base cannot
        # honour — so neither is advertised. Read from the same table the panes were built
        # from, or the menu would offer what the footer does not.
        pane_actions = () if self._unavailable(tab) else self._live_actions.get(tab, ())
        out += [ActionDescriptor(id=action, title=description, help=description, key=key,
                                 danger=danger.get(action, "none"),  # type: ignore[arg-type]
                                 action=action)
                for key, action, description in pane_actions]
        return out

    def _unavailable(self, tab: str) -> bool:
        """Tabs the base withholds (standing / service-integrity gated) — recorded once at
        compose time, since `_services` builds widgets and must not be re-run to answer a
        question about keys."""
        return tab in self._withheld

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
        # Station is *never* withheld: it carries the Status panel, which is the one thing
        # every base owes you — a hostile base shows nothing else. The installation half
        # explains itself instead (`station_reason`), so the tab stays a readable door.
        return [
            ("Station", "station",
             self._art_pane(v, "station", self._station_pane(v, station_reason)), None),
            ("Commodities", "trade", self._art_pane(v, "trade", self._trade_pane(v)), trade_reason),
            ("Hardware", "hardware", self._art_pane(v, "hardware", self._hardware_pane(v)), hardware_reason),
            ("Bank", "bank", self._art_pane(v, "bank", self._bank_pane(v)), bank_reason),
        ]

    @staticmethod
    def _art_pane(v: StarbaseDTO, service: str, content: Widget) -> Vertical:
        condition = v.standing if v.standing in ("derelict", "hostile") else "open"
        return Vertical(
            # No `expect_sector` guard here: StarbaseDTO carries only the display id
            # (`sector_display`), not the internal sector id the Sector composer
            # publishes, so this header trusts the docking-flow invariant unchecked.
            StationArtHeader(
                "starbase", v.archetype_id or "humanoid_diplomat", service,
                identity=v.starbase_id, condition=condition),
            content,
        )

    def _status_panel(self, v: StarbaseDTO) -> Static:
        """The base's standing, on one line, in a bordered panel above the installations.

        Status is not a place you go — it is what you need on screen while you act, so it
        rides the Station tab rather than costing a tab (and a hotkey) of its own."""
        panel = Static(
            f"Owner [cyan]{v.owner}[/]   ·   {_STANDING_STYLE.get(v.standing, v.standing)}"
            f"   ·   integrity [b]{v.integrity_pct}%[/]"
            + ("   ·   [red]its guns track you — market and services closed[/]"
               if v.standing == "hostile" else ""),
            id="base-status-panel", classes="status-panel",
        )
        panel.border_title = "Status"
        return panel

    def _station_pane(self, v: StarbaseDTO, withheld: str | None) -> Vertical:
        lines = []
        if withheld is None:
            if v.empty_slots:
                keystone = sum(1 for _, _, k in v.empty_slots if k)
                note = " (incl. the reactor keystone)" if keystone else ""
                lines.append(f"[cyan]\\[R] Repair[/] — {len(v.empty_slots)} empty slot(s){note}; "
                             "installs a carried component, keystone first.")
            if v.salvage:
                parts = ", ".join(label for _, _, label in v.salvage)
                lines.append(f"[yellow]\\[V] Salvage[/] — {len(v.salvage)} component(s): {parts}")
            if v.claimable:
                lines.append(f"[green]\\[L] Claim[/] — take this base as a forward foothold "
                             f"for {v.claim_cost:,} latinum.")
            if not v.operational:
                lines.append("[dim]The base is dark — fill the reactor keystone to wake it "
                             "(and its market).[/]")
        if v.assaultable:
            lines.append("[red]\\[A] Assault[/] — engage the base's defenses; victory razes it.")

        body: list[Widget] = [self._status_panel(v)]
        if withheld is None:
            body.append(ComponentWorkbench(
                v.subsystems,
                self._service.engine_room_view(self._pid).on_hand,
                STARBASE_WORKBENCH_PROFILE,
                WorkbenchCapabilities(install=True, full_repair=True, salvage=True),
                id="base-component-workbench",
            ))
        else:
            body.append(Static(f"[dim]{withheld}[/]", classes="service-unavailable"))
        body.append(Static("\n".join(lines) or "[dim]All installations live.[/]",
                           classes="note"))
        # Scrolls: the equal-height bay rack is taller than the tab at 80×24, and a
        # clipped panel loses its bottom border (and the notes under it) silently.
        return VerticalScroll(*body)

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
        note = Static("[dim]P purchases the highlighted part; M resupplies a missile"
                      + (f" ({v.missile_price:,}).[/]" if v.missile_price else ".[/]"),
                      classes="note")
        return Vertical(head, table, note)

    def _bank_pane(self, v: StarbaseDTO) -> Vertical:
        return Vertical(
            Static(f"[b]BASE VAULT[/]  cash [b yellow]{v.latinum:,}[/]  "
                   f"banked [b green]{v.bank_balance:,}[/]"),
            Static("[dim]A deposits 1,000; W withdraws 1,000 (interest-free — §4.2).[/]",
                   classes="note"),
        )

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
        _trade_highlighted(self, self._service, self._pid)

    def action_haggle(self) -> None:
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
        except NoMatches:
            self.notify("No hardware for sale here.", timeout=2)
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
