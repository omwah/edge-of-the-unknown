"""Reusable widgets for the TUI skeleton: status sidebar and warp list."""

from __future__ import annotations

from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Static

from edge.tui.dummy import ShipDTO, WarpDTO


def bar(filled: int, total: int = 10) -> str:
    filled = max(0, min(total, filled))
    return "█" * filled + "░" * (total - filled)


def _scaled_bar(qty: int, capacity: int, width: int = 12) -> str:
    filled = round(qty / capacity * width) if capacity else 0
    return bar(filled, width)


class StatusSidebar(Static):
    """Right-hand status readout derived from a ShipDTO (UI_MOCKUPS.md §1)."""

    DEFAULT_CSS = """
    StatusSidebar { width: 1fr; padding: 0 1; border-left: solid $primary; }
    """

    def __init__(self, ship: ShipDTO, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._ship = ship

    def render(self) -> str:
        s = self._ship
        rule = "[dim]" + "─" * 30 + "[/]"
        lines: list[str] = [
            f"[b cyan]{s.name}[/]  [dim]({s.klass})[/]",
            rule,
        ]
        for a in s.aspects:
            lines.append(f"{a.label:<8}[yellow]{bar(a.filled)}[/]  {a.note}")
        lines += [
            f"[green]subsystems: {s.integrity}[/]",
            rule,
            f"Holds {s.holds_used}/{s.holds_total}",
        ]
        for h in s.holds:
            lines.append(f" {h.label:<5}[yellow]{_scaled_bar(h.qty, h.capacity)}[/] {h.qty:>3}")
        lines += [
            f"Gun [green]{s.gun}[/]  Missiles x{s.missiles}  Kits x{s.kits}",
            f"Latinum  [b yellow]{s.latinum:,}[/] gpl",
            f"Band {s.band}",
            "[dim]region:[/]",
        ]
        lines += [f"  {row}" for row in s.region_map]
        return "\n".join(lines)


class WarpButton(Button):
    """A single clickable warp affordance."""

    class Warp(Message):
        def __init__(self, sector_id: int) -> None:
            self.sector_id = sector_id
            super().__init__()

    def __init__(self, warp: WarpDTO) -> None:
        label = f"{warp.sector_id} {warp.arrow}"
        if warp.label:
            label += f" {warp.label}"
        super().__init__(label, variant="primary" if warp.explored else "default")
        self._warp = warp
        if not warp.explored:
            self.add_class("unexplored")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(self.Warp(self._warp.sector_id))


class WarpList(Horizontal):
    """Row of clickable outbound warps (unexplored ones dimmed)."""

    DEFAULT_CSS = """
    WarpList { height: auto; }
    WarpList WarpButton { min-width: 9; height: 3; margin: 0 1 0 0; }
    WarpList WarpButton.unexplored { color: $text-disabled; }
    """

    def __init__(self, warps: list[WarpDTO], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._warps = warps

    def compose(self):
        for w in self._warps:
            yield WarpButton(w)
