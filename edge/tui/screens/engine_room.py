"""EngineRoomScreen — subsystems & components (UI_MOCKUPS.md §8).

The player ship's aspects are *derived* from four slotted subsystems (spindrive /
thrusters / screens / main_gun, DESIGN §4.1); each panel shows its derived aspect
and a slot grid (keystone / filled / knocked-out / empty). When a live
`GameService` is supplied the panels read `engine_room_view` and the install /
cannibalize actions issue real commands; field-patch is present but inert in
Phase 2 (nothing is knocked out yet). With no service (screenshot harness) it
renders the passed sample DTO.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core.enums import Component, ComponentTier, Subsystem as SubsystemKind
from edge.core.rules import Cannibalize, InstallComponent
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
            marker = "[green][✓][/]" if idx in self._selected_slots else "[green][+][/]"
            return f"{marker} {slot.component}{key}"
        if slot.state == "knocked":
            return f"[red][!][/] {slot.component}  [red]knocked-out[/]"
        return "[dim][ ][/] [dim]____[/]"

    async def on_clickable_entry_picked(self, msg: ClickableEntry.Picked) -> None:
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
    Selects the component that will be installed into a subsystem
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
        self._selected_component = None

    def compose(self) -> ComposeResult:

        for c in self._loose_components:
            yield self._component_line(c)

    def on_mount(self) -> None:
        self.border_title = "Loose Components"
        self.border_subtitle = f"→ Select component, then subsystem"

    def _component_line(self, component_desc: str) -> ClickableEntry:

        if component_desc == self._selected_component:
            content = f"[green][✓][/] {component_desc}"
        else:
            content = f"[dim][ ][/] [dim]{component_desc}[/]"

        return ClickableEntry(
            content,
            dest="loose_component",
            ref=component_desc,
            classes="loose_components"
        )

    async def on_clickable_entry_picked(self, msg: ClickableEntry.Picked) -> None:

        if msg.dest != "loose_component":
            return

        # Re-clicking the current selection clears it; clicking any other
        # entry switches the selection to it.
        self._selected_component = None if self._selected_component == msg.ref else msg.ref

        await self.recompose()

class EngineRoomScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("p", "noop", "Field-patch"),
        Binding("x", "cannibalize", "Cannibalize"),
        Binding("u", "noop", "Upgrade"),
    ]

    CSS = """
    EngineRoomScreen #engine-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    EngineRoomScreen #engine-grid {
        grid-size: 2; grid-gutter: 0; height: 1fr; padding: 1 1 0 1;
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

        if len(r.on_hand) > 0:
            with Grid():
                # _ComponentsPickerPanel
                yield self._component_picker

        yield Static(
            f"[green][+][/] healthy   [green][✓][/] selected   "
            f"[red][!][/] knocked-out   [dim][ ][/] empty slot\n"
            f"Repair-kits x{r.kits}\n"
            f"[b]P[/] Field-patch   [b]X[/] Cannibalize   "
            f"[b]U[/] Upgrade [dim](StarDock/base)[/]   [b]Esc[/] Back",
            id="engine-foot",
        )
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)

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

    def install(self, on_hand: str, system: Subsystem) -> None:
        """Install the selected loose component into the subystem targetd by clicking on it"""

        from textual import log

        if self._service is None:
            self.action_noop()
            return

        kind = _DISPLAY_TO_KIND.get(system.name)
        component, tier = _parse_on_hand(on_hand)

        if kind is None:
            return

        for idx, slot in enumerate(system.slots):
            if slot.state != "empty":
                continue
            try:
                self._issue(InstallComponent(kind, idx, component, tier))
                return
            except Exception:  # illegal slot for this part
                self.notify(f"That component can not be installed there", timeout=2)
                return

        self.notify(f"No legal empty slot for {component.value}.", timeout=2)

    async def on_subsystem_panel_targeted_system(self, msg: _SubsystemPanel.TargetedSystem) -> None:

        if self._component_picker._selected_component is None:
            return

        self.install(self._component_picker._selected_component, msg.system)

    def _issue(self, command: object) -> None:
        assert self._service is not None
        self._service.apply(self._pid, command)  # type: ignore[arg-type]
        self._reopen()


def _parse_on_hand(label: str) -> tuple[Component, ComponentTier]:
    """Parse an on-hand label like "converter (II) x1" back to (Component, tier)."""
    name, _, rest = label.partition(" (")
    tier_name = rest.split(")", 1)[0]
    return Component(name), ComponentTier[tier_name]
