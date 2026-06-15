"""EngineRoomScreen — subsystems & components (UI_MOCKUPS.md §8).

Phase-2 screen, stubbed here so the `E` key and StarDock's repair flow have
somewhere to go. The player ship's aspects are *derived* from four slotted
subsystems (spindrive / thrusters / screens / main_gun, DESIGN §4.1); each panel
shows its derived aspect and a slot grid (keystone / filled / knocked-out /
empty). Field-patch, install, cannibalize, and upgrade are stubbed.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.tui.dummy import EngineRoomDTO, Subsystem


class _SubsystemPanel(Static):
    """One subsystem's slot grid, derived aspect in the border title (§8)."""

    DEFAULT_CSS = """
    _SubsystemPanel {
        height: auto; border: round $primary; padding: 0 1; margin: 0 1 1 0;
    }
    """

    def __init__(self, system: Subsystem) -> None:
        super().__init__()
        self._system = system

    def on_mount(self) -> None:
        self.border_title = self._system.name
        self.border_subtitle = f"→ {self._system.derived}"
        self.update("\n".join(self._slot_line(i) for i in range(len(self._system.slots))))

    def _slot_line(self, idx: int) -> str:
        slot = self._system.slots[idx]
        key = " [dim](keystone)[/]" if slot.keystone else ""
        if slot.state == "filled":
            return f"[green][+][/] {slot.component}{key}"
        if slot.state == "knocked":
            return f"[red][!][/] {slot.component}  [red]knocked-out[/]"
        return "[dim][ ][/] [dim]____[/]"


class EngineRoomScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("p", "noop", "Field-patch"),
        Binding("i", "noop", "Install"),
        Binding("x", "noop", "Cannibalize"),
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

    def __init__(self, room: EngineRoomDTO) -> None:
        super().__init__()
        self._room = room

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
        on_hand = ", ".join(r.on_hand) or "nothing"
        yield Static(
            f"[green][+][/] healthy   [red][!][/] knocked-out   [dim][ ][/] empty slot\n"
            f"Repair-kits x{r.kits}   ·   On hand: {on_hand}\n"
            f"[b]P[/] Field-patch   [b]I[/] Install   [b]X[/] Cannibalize   "
            f"[b]U[/] Upgrade [dim](StarDock/base)[/]   [b]Esc[/] Back",
            id="engine-foot",
        )
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
