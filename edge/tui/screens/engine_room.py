"""EngineRoomScreen — subsystems & components (UI_MOCKUPS.md §8).

The player ship's aspects are *derived* from four slotted subsystems (spindrive /
thrusters / screens / main_gun, DESIGN §4.1); each panel shows its derived aspect
and a slot grid (keystone / filled / knocked-out / empty). When a live
`GameService` is supplied the panels read `engine_room_view` and the install /
cannibalize actions issue real commands. `P` field-patches knocked-out components
(one repair-kit each, WP26 damage), `R` pays a dock/base to restore them
(`RepairAtDock`, service-point gated), and `U` swaps a selected loose component
into a selected filled slot (the upgrade path — the old part returns to the
hold). With no service (screenshot harness) it renders the passed sample DTO.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.enums import Component, ComponentTier, Subsystem as SubsystemKind
from edge.core.rules import Cannibalize, FieldPatch, InstallComponent, RepairAtDock, SwapComponent
from edge.server.service import GameService
from edge.tui import sprites
from edge.tui.dummy import EngineRoomDTO, Subsystem
from edge.tui.widgets import ClickableEntry

# Reverse of session._SUBSYSTEM_DISPLAY: panel title -> the Subsystem enum.
_DISPLAY_TO_KIND = {
    "SPINDRIVE": SubsystemKind.SPINDRIVE, "SCREENS": SubsystemKind.SCREENS,
    "THRUSTERS": SubsystemKind.THRUSTERS, "MAIN GUN": SubsystemKind.MAIN_GUN,
}


class _SubsystemPanel(Horizontal):
    """One subsystem: slot list on the left, a vertical icon down the right side;
    derived aspect in the border subtitle (§8)."""

    DEFAULT_CSS = """
    _SubsystemPanel {
        height: auto; border: round $primary; padding: 0 1; margin: 0 1 1 0;
    }
    _SubsystemPanel .slots { width: 1fr; height: auto; }
    _SubsystemPanel .icon { width: auto; height: auto; margin-left: 2; }
    """
    class TargetedSystem(Message, namespace="subsystem_panel"):
        def __init__(self, system: Subsystem) -> None:
            super().__init__()
            self.system = system

    def __init__(self, system: Subsystem) -> None:
        super().__init__()
        self._system = system
        # Slot indices the player has marked for cannibalization (filled,
        # non-keystone only). Reset whenever the screen reopens.
        self._selected_slots: set[int] = set()

    @property
    def system(self) -> Subsystem:
        return self._system

    @property
    def selected_slots(self) -> set[int]:
        return self._selected_slots

    def compose(self) -> ComposeResult:
        # One clickable line per slot so individual components can be selected.
        with Vertical(classes="slots"):
            for i in range(len(self._system.slots)):
                yield ClickableEntry(
                    self._slot_line(i), dest="slot", ref=i, classes="slot"
                )
        # Colour the icon via an inline style rather than wrapping the art in
        # markup, so the glyphs are rendered verbatim (no markup escaping).
        icon = Static("\n".join(sprites.pick_subsystem(self._system.name)), classes="icon")
        icon.styles.color = sprites.SUBSYSTEM_COLORS.get(self._system.name, "cyan")
        yield icon

    def on_mount(self) -> None:
        self.border_title = self._system.name
        self.border_subtitle = f"→ {self._system.derived}"

    def _is_selectable(self, idx: int) -> bool:
        slot = self._system.slots[idx]
        return slot.state == "filled" and not slot.keystone

    def _slot_line(self, idx: int) -> str:
        slot = self._system.slots[idx]
        key = " [dim](keystone)[/]" if slot.keystone else ""
        if slot.state == "filled":
            marker = "[white][✓][/]" if idx in self._selected_slots else "[green][+][/]"
            return f"{marker} {slot.component}{key}"
        if slot.state == "knocked":
            return f"[red][!][/] {slot.component}  [red]knocked-out[/]"
        return "[dim][ ][/] [dim]____[/]"

    @on(ClickableEntry.Picked)
    async def on_component_picked(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest != "slot":
            return

        idx = int(msg.ref)  # ref is the slot index
        if not self._is_selectable(idx):
            return  # only filled, non-keystone slots can be pulled

        # Toggle this slot's selection, then redraw its marker.
        self._selected_slots.symmetric_difference_update({idx})
        await self.recompose()

    def on_click(self) -> None:
        self.post_message(self.TargetedSystem(self._system))

class _ComponentsPickerPanel(Vertical):
    """
    Selects the component(s) that will be installed into a subsystem
    """

    DEFAULT_CSS = """
    _ComponentsPickerPanel {
        height: auto; border: round $primary; padding: 0 1 0 1; margin: 1 1 2 1;
    }
    _ComponentsPickerPanel .slots { width: 1fr; height: auto; }
    """

    def __init__(self, loose_components: list[str]) -> None:
        super().__init__()

        self._loose_components = loose_components
        # Labels the player has marked for installation. Reset on reopen.
        self._selected_components: set[str] = set()

    @property
    def selected_components(self) -> set[str]:
        return self._selected_components

    def compose(self) -> ComposeResult:

        for c in self._loose_components:
            yield self._component_line(c)

    def on_mount(self) -> None:
        self.border_title = "Loose Components"
        self.border_subtitle = "→ Select component(s), then subsystem"

    def _component_line(self, component_desc: str) -> ClickableEntry:

        if component_desc in self._selected_components:
            content = f"[white][✓][/] {component_desc}"
        else:
            content = f"[dim][ ][/] [dim]{component_desc}[/]"

        return ClickableEntry(
            content,
            dest="loose_component",
            ref=component_desc,
            classes="loose_components"
        )

    @on(ClickableEntry.Picked)
    async def on_component_picked(self, msg: ClickableEntry.Picked) -> None:

        if msg.dest != "loose_component":
            return

        # Toggle this component in/out of the selection, then redraw its marker.
        self._selected_components.symmetric_difference_update({msg.ref})

        await self.recompose()

class EngineRoomScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("p", "field_patch", "Field-patch"),
        Binding("x", "cannibalize", "Cannibalize"),
        Binding("u", "upgrade", "Upgrade"),
        Binding("r", "dock_repair", "Dock repair"),
    ]

    HELP_TITLE = "Engine room"
    HELP = """\
Click slots and loose components to select them; [b]U[/] swaps the selected part
into the selected slot (the old part returns to the hold). [b]P[/] spends carried
repair-kits; [b]R[/] pays a StarDock or your own base to restore knockouts."""

    CSS = """
    EngineRoomScreen #engine-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    EngineRoomScreen #engine-grid {
        grid-size: 2; grid-gutter: 0; height: auto; padding: 1 1 0 1;
    }
    EngineRoomScreen #engine-picker {
        height: 1fr;
    }
    EngineRoomScreen #engine-foot {
        height: auto; padding: 0 1; border-top: solid $primary; color: $text-muted;
    }
    """

    def __init__(self, room: EngineRoomDTO, service: GameService | None = None,
                 pid: int = 1) -> None:
        super().__init__()

        self._room = room
        self._service = service
        self._pid = pid

        self._component_picker = _ComponentsPickerPanel(self._room.on_hand)

    def _reopen(self) -> None:
        """Re-fetch the view and rebuild the screen after a state change."""
        if self._service is None:
            return
        self.app.pop_screen()
        self.app.push_screen(EngineRoomScreen(
            self._service.engine_room_view(self._pid), self._service, self._pid))

    def compose(self) -> ComposeResult:
        r = self._room

        yield Static(
            f"ENGINE ROOM · {r.ship}        "
            f"[dim]efficiency bonus:[/] [green]{r.efficiency_bonus}[/]",
            id="engine-title",
        )

        with Grid(id="engine-grid"):
            for system in r.subsystems:
                yield _SubsystemPanel(system)

        # Dedicated, always-present region for the picker so hiding it (when no
        # loose components are on hand) leaves empty space below the subsystems
        # rather than resizing the subsystem panels above.
        with Vertical(id="engine-picker"):
            if len(r.on_hand) > 0:
                yield self._component_picker

        yield Static(
            f"[green][+][/] healthy   [white][✓][/] selected   "
            f"[red][!][/] knocked-out   [dim][ ][/] empty slot\n"
            f"Repair-kits x{r.kits}\n"
            f"[b]P[/] Field-patch knocked-out   [b]R[/] Dock repair [dim](StarDock/base)[/]   "
            f"[b]X[/] Cannibalize   [b]U[/] Upgrade [dim](swap selected part into selected slot)[/]"
            f"   [b]Esc[/] Back",
            id="engine-foot",
        )
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)

    def _knocked_slots(self) -> list[tuple[SubsystemKind, int]]:
        """Every knocked-out slot across the panels, as (subsystem kind, slot index)."""
        targets: list[tuple[SubsystemKind, int]] = []
        for panel in self.query(_SubsystemPanel):
            kind = _DISPLAY_TO_KIND.get(panel.system.name)
            if kind is None:
                continue
            for idx, slot in enumerate(panel.system.slots):
                if slot.state == "knocked":
                    targets.append((kind, idx))
        return targets

    def action_field_patch(self) -> None:
        """Spend repair-kits to un-knock-out damaged components (§4.1, WP26)."""
        if self._service is None:
            self.action_noop()
            return
        targets = self._knocked_slots()
        if not targets:
            self.notify("Nothing is knocked out.", timeout=2)
            return
        patched = 0
        for kind, idx in targets:
            try:
                self._service.apply(self._pid, FieldPatch(kind, idx))
                patched += 1
            except (EngineRoomError, EconomyError) as exc:
                self.notify(str(exc), severity="warning", timeout=3)
                break
        if patched:
            self.notify(f"Patched {patched} component(s).", timeout=2)
            self._reopen()

    def action_dock_repair(self) -> None:
        """Pay the dock/base to restore knocked-out components (§4.1, §8 — WP71)."""
        if self._service is None:
            self.action_noop()
            return
        targets = self._knocked_slots()
        if not targets:
            self.notify("Nothing is knocked out.", timeout=2)
            return
        repaired = 0
        for kind, idx in targets:
            try:
                self._service.apply(self._pid, RepairAtDock(kind, idx))
                repaired += 1
            except (EngineRoomError, EconomyError) as exc:
                self.notify(str(exc), severity="warning", timeout=3)
                break
        if repaired:
            self.notify(f"Restored {repaired} component(s).", timeout=2)
            self._reopen()

    def action_upgrade(self) -> None:
        """Swap the selected loose component into the selected filled slot (§4.1).

        Needs exactly one loose component and one filled slot selected; the old part
        returns to the hold (`SwapComponent` conserves components).
        """
        if self._service is None:
            self.action_noop()
            return
        loose = sorted(self._component_picker.selected_components)
        slots = [
            (panel, idx)
            for panel in self.query(_SubsystemPanel)
            for idx in sorted(panel.selected_slots)
        ]
        if len(loose) != 1 or len(slots) != 1:
            self.notify("Select exactly one loose component and one filled slot to swap.",
                        timeout=3)
            return
        panel, idx = slots[0]
        kind = _DISPLAY_TO_KIND.get(panel.system.name)
        if kind is None:
            return
        component, tier = _parse_on_hand(loose[0])
        try:
            self._service.apply(self._pid, SwapComponent(kind, idx, component, tier))
        except (EngineRoomError, EconomyError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.notify(f"Swapped in {component.value} ({tier.name}).", timeout=2)
        self._reopen()

    def action_cannibalize(self) -> None:
        """Cannibalize every slot the player has selected across the subsystem
        panels, returning each pulled component to the loose on-hand hold."""
        if self._service is None:
            self.action_noop()
            return

        # Collect the (subsystem, slot) targets before issuing anything: each
        # cannibalize empties its slot in place (indices stay valid), so we can
        # apply them all and reopen the screen once at the end.
        targets = [
            (panel.system, idx)
            for panel in self.query(_SubsystemPanel)
            for idx in sorted(panel.selected_slots)
        ]
        if not targets:
            self.notify("Select a filled slot to cannibalize first.", timeout=2)
            return

        pulled = 0
        for system, idx in targets:
            try:
                self.cannibalize_component(system, idx)
                pulled += 1
            except Exception:  # core rejected this pull — skip it, keep going
                self.notify(f"Couldn't cannibalize slot {idx} of {system.name}.",
                            timeout=2)

        if pulled:
            self._reopen()

    def cannibalize_component(self, system: Subsystem, slot_index: int) -> None:
        """Pull the component in `system`'s slot `slot_index` back into the
        loose on-hand hold (does not reopen the screen — the caller does)."""
        assert self._service is not None
        kind = _DISPLAY_TO_KIND.get(system.name)
        if kind is None:
            return
        slot = system.slots[slot_index]
        if slot.state != "filled" or slot.keystone:
            return
        self._service.apply(self._pid, Cannibalize(kind, slot_index))  # type: ignore[arg-type]

    def install_component(self, label: str, system: Subsystem,
                          skip_slots: set[int]) -> int | None:
        """Install one loose component into the first legal empty slot of
        `system` not already in `skip_slots`. Returns the slot index used, or
        None if it couldn't be placed. Does not reopen — the caller does."""
        assert self._service is not None
        kind = _DISPLAY_TO_KIND.get(system.name)
        if kind is None:
            return None
        component, tier = _parse_on_hand(label)
        for idx, slot in enumerate(system.slots):
            if slot.state != "empty" or idx in skip_slots:
                continue
            try:
                self._service.apply(  # type: ignore[arg-type]
                    self._pid, InstallComponent(kind, idx, component, tier))
            except Exception:  # this slot rejects this part — try the next
                continue
            return idx
        return None

    async def on_subsystem_panel_targeted_system(
            self, msg: _SubsystemPanel.TargetedSystem) -> None:
        """Install every selected loose component into the targeted subsystem,
        each in its own empty slot, then reopen the screen once."""
        selected = self._component_picker.selected_components
        if not selected:
            return
        if self._service is None:
            self.action_noop()
            return

        used: set[int] = set()
        failed: list[str] = []
        for label in sorted(selected):
            idx = self.install_component(label, msg.system, used)
            if idx is None:
                failed.append(label)
            else:
                used.add(idx)

        if len(failed) == len(selected):
            self.notify(f"No legal empty slot in {msg.system.name} for the "
                        f"selected component(s).", timeout=2)
            return
        if failed:
            self.notify(f"No slot in {msg.system.name} for: "
                        f"{', '.join(failed)}", timeout=2)
        self._reopen()

    def _issue(self, command: object) -> None:
        assert self._service is not None
        self._service.apply(self._pid, command)  # type: ignore[arg-type]
        self._reopen()


def _parse_on_hand(label: str) -> tuple[Component, ComponentTier]:
    """Parse an on-hand label like "converter (II) x1" back to (Component, tier)."""
    name, _, rest = label.partition(" (")
    tier_name = rest.split(")", 1)[0]
    return Component(name), ComponentTier[tier_name]
