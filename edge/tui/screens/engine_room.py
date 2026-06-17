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
from textual.containers import Grid, Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core.enums import Component, ComponentTier, Subsystem as SubsystemKind
from edge.core.rules import Cannibalize, InstallComponent
from edge.server.service import GameService
from edge.tui import sprites
from edge.tui.dummy import EngineRoomDTO, Subsystem

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

    def __init__(self, system: Subsystem) -> None:
        super().__init__()
        self._system = system

    def compose(self) -> ComposeResult:
        slots = "\n".join(self._slot_line(i) for i in range(len(self._system.slots)))
        yield Static(slots, classes="slots")
        # Colour the icon via an inline style rather than wrapping the art in
        # markup, so the glyphs are rendered verbatim (no markup escaping).
        icon = Static("\n".join(sprites.pick_subsystem(self._system.name)), classes="icon")
        icon.styles.color = sprites.SUBSYSTEM_COLORS.get(self._system.name, "cyan")
        yield icon

    def on_mount(self) -> None:
        self.border_title = self._system.name
        self.border_subtitle = f"→ {self._system.derived}"

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
        Binding("i", "install", "Install"),
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

    def action_cannibalize(self) -> None:
        """Pull the first filled non-keystone component into the loose-part hold."""
        if self._service is None:
            self.action_noop()
            return
        for system in self._room.subsystems:
            kind = _DISPLAY_TO_KIND.get(system.name)
            if kind is None:
                continue
            for idx, slot in enumerate(system.slots):
                if slot.state == "filled" and not slot.keystone:
                    self._issue(Cannibalize(kind, idx), f"Cannibalized {slot.component}")
                    return
        self.notify("Nothing safe to cannibalize.", timeout=2)

    def action_install(self) -> None:
        """Install the first on-hand component into the first slot that accepts it."""
        if self._service is None:
            self.action_noop()
            return
        if not self._room.on_hand:
            self.notify("No loose components on hand.", timeout=2)
            return
        component, tier = _parse_on_hand(self._room.on_hand[0])
        for system in self._room.subsystems:
            kind = _DISPLAY_TO_KIND.get(system.name)
            if kind is None:
                continue
            for idx, slot in enumerate(system.slots):
                if slot.state != "empty":
                    continue
                try:
                    self._issue(InstallComponent(kind, idx, component, tier),
                                f"Installed {component.value}")
                    return
                except Exception:  # illegal slot for this part — try the next
                    continue
        self.notify(f"No legal empty slot for {component.value}.", timeout=2)

    def _issue(self, command: object, ok: str) -> None:
        assert self._service is not None
        self._service.apply(self._pid, command)  # type: ignore[arg-type]
        self.notify(ok, timeout=2)
        self._reopen()


def _parse_on_hand(label: str) -> tuple[Component, ComponentTier]:
    """Parse an on-hand label like "converter (II) x1" back to (Component, tier)."""
    name, _, rest = label.partition(" (")
    tier_name = rest.split(")", 1)[0]
    return Component(name), ComponentTier[tier_name]
