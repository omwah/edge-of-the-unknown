"""Ship component operations rendered by the shared ComponentWorkbench."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer

from edge.core.dto import EngineRoomDTO
from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.enums import Component, ComponentTier, Subsystem as SubsystemKind
from edge.core.rules import Cannibalize, FieldPatch, InstallComponent, RepairAtDock, SwapComponent
from edge.server.service import GameService
from edge.tui.chrome import ContextStrip, TitleBar, notify_warning
from edge.tui.component_workbench import (
    ComponentWorkbench,
    SHIP_WORKBENCH_PROFILE,
    WorkbenchCapabilities,
)


_DISPLAY_TO_KIND = {
    "SPINDRIVE": SubsystemKind.SPINDRIVE,
    "SCREENS": SubsystemKind.SCREENS,
    "THRUSTERS": SubsystemKind.THRUSTERS,
    "MAIN GUN": SubsystemKind.MAIN_GUN,
}


class EngineRoomScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("p", "field_patch", "Field-patch"),
        Binding("x", "cannibalize", "Cannibalize"),
        Binding("u", "upgrade", "Install / swap"),
        Binding("r", "dock_repair", "Dock repair"),
    ]

    HELP_TITLE = "Engine room"
    HELP = """\
The same component workbench is used for ships and starbases. Select a carried
part and an empty or filled non-keystone slot, then [b]U[/] installs or swaps it.
[b]P[/] spends repair kits; [b]R[/] pays a service point; [b]X[/] pulls selected parts."""

    def __init__(self, room: EngineRoomDTO, service: GameService | None = None,
                 pid: int = 1) -> None:
        super().__init__()
        self._room = room
        self._service = service
        self._pid = pid

    def compose(self) -> ComposeResult:
        room = self._room
        yield TitleBar(f"ENGINE ROOM · {room.ship}",
                       f"efficiency bonus: {room.efficiency_bonus}", id="engine-title")
        yield ComponentWorkbench(
            room.subsystems,
            room.on_hand,
            SHIP_WORKBENCH_PROFILE,
            WorkbenchCapabilities(
                install=True, swap=True, field_patch=True, full_repair=True, salvage=True
            ),
            id="component-workbench",
        )
        yield ContextStrip(
            f"Repair kits: {room.kits}  ·  [+] healthy  [!] knocked-out  [ ] empty  [✓] selected",
            id="engine-foot",
        )
        yield Footer(compact=True)

    @property
    def _workbench(self) -> ComponentWorkbench:
        return self.query_one(ComponentWorkbench)

    async def _refresh(self) -> None:
        if self._service is not None:
            self._room = self._service.engine_room_view(self._pid)
            await self.recompose()

    def action_back(self) -> None:
        self.app.pop_screen()

    def _knocked_slots(self) -> list[tuple[SubsystemKind, int]]:
        targets: list[tuple[SubsystemKind, int]] = []
        for subsystem in self._room.subsystems:
            kind = _DISPLAY_TO_KIND.get(subsystem.name)
            if kind is None:
                continue
            targets.extend(
                (kind, index) for index, slot in enumerate(subsystem.slots)
                if slot.state == "knocked"
            )
        return targets

    async def action_field_patch(self) -> None:
        if self._service is None:
            self.notify("Preview only.", timeout=2)
            return
        targets = self._knocked_slots()
        if not targets:
            self.notify("Nothing is knocked out.", timeout=2)
            return
        patched = 0
        for kind, index in targets:
            try:
                self._service.apply(self._pid, FieldPatch(kind, index))
                patched += 1
            except (EngineRoomError, EconomyError) as exc:
                notify_warning(self, str(exc))
                break
        if patched:
            self.notify(f"Patched {patched} component(s).", timeout=2)
            await self._refresh()

    async def action_dock_repair(self) -> None:
        if self._service is None:
            self.notify("Preview only.", timeout=2)
            return
        targets = self._knocked_slots()
        if not targets:
            self.notify("Nothing is knocked out.", timeout=2)
            return
        repaired = 0
        for kind, index in targets:
            try:
                self._service.apply(self._pid, RepairAtDock(kind, index))
                repaired += 1
            except (EngineRoomError, EconomyError) as exc:
                notify_warning(self, str(exc))
                break
        if repaired:
            self.notify(f"Restored {repaired} component(s).", timeout=2)
            await self._refresh()

    def _slot(self, name: str, index: int):
        subsystem = next(system for system in self._room.subsystems if system.name == name)
        return subsystem.slots[index]

    async def action_upgrade(self) -> None:
        if self._service is None:
            self.notify("Preview only.", timeout=2)
            return
        selection = self._workbench.selection
        if len(selection.loose_components) != 1 or len(selection.slots) != 1:
            self.notify("Select one carried component and one destination slot.", timeout=3)
            return
        name, index = selection.slots[0]
        kind = _DISPLAY_TO_KIND.get(name)
        if kind is None:
            return
        component, tier = _parse_on_hand(selection.loose_components[0])
        slot = self._slot(name, index)
        command = (InstallComponent(kind, index, component, tier) if slot.state == "empty"
                   else SwapComponent(kind, index, component, tier))
        try:
            self._service.apply(self._pid, command)
        except (EngineRoomError, EconomyError) as exc:
            notify_warning(self, str(exc))
            return
        verb = "Installed" if slot.state == "empty" else "Swapped in"
        self.notify(f"{verb} {component.value} ({tier.name}).", timeout=2)
        await self._refresh()

    async def action_cannibalize(self) -> None:
        if self._service is None:
            self.notify("Preview only.", timeout=2)
            return
        selection = self._workbench.selection
        targets = []
        for name, index in selection.slots:
            kind = _DISPLAY_TO_KIND.get(name)
            slot = self._slot(name, index)
            if kind is not None and slot.state == "filled" and not slot.keystone:
                targets.append((kind, index))
        if not targets:
            self.notify("Select at least one removable installed component.", timeout=2)
            return
        pulled = 0
        for kind, index in targets:
            try:
                self._service.apply(self._pid, Cannibalize(kind, index))
                pulled += 1
            except (EngineRoomError, EconomyError) as exc:
                notify_warning(self, str(exc))
                break
        if pulled:
            self.notify(f"Cannibalized {pulled} component(s).", timeout=2)
            await self._refresh()


def _parse_on_hand(label: str) -> tuple[Component, ComponentTier]:
    """Parse an inventory label like ``converter (II) x1``."""
    name, _, rest = label.partition(" (")
    tier_name = rest.split(")", 1)[0]
    return Component(name), ComponentTier[tier_name]
