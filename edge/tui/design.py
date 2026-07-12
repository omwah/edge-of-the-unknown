"""Shared presentation types and semantic Textual themes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Literal

from textual.binding import Binding
from textual.screen import Screen
from textual.theme import Theme


class LayoutTier(Enum):
    COMPACT = "compact"
    STANDARD = "standard"
    WIDE = "wide"
    UNSUPPORTED = "unsupported"


def layout_tier(width: int, height: int) -> LayoutTier:
    if width < 80 or height < 24:
        return LayoutTier.UNSUPPORTED
    if width < 100 or height < 30:
        return LayoutTier.COMPACT
    if width >= 120 and height >= 36:
        return LayoutTier.WIDE
    return LayoutTier.STANDARD


@dataclass(frozen=True)
class ActionDescriptor:
    id: str
    title: str
    help: str
    key: str | None
    enabled: bool = True
    disabled_reason: str | None = None
    danger: Literal["none", "caution", "destructive"] = "none"
    callback: Callable[[], object] | None = None
    action: str = ""


def screen_actions(screen: Screen[Any]) -> list[ActionDescriptor]:
    """Return the one canonical advertised-action list for a screen.

    Danger levels come from the screen's optional ``ACTION_DANGER`` class map
    (action name → "caution"/"destructive"). A destructive action's method must
    route through the shared `ConfirmScreen` — tests/test_ui_actions.py enforces
    it statically, so every entry point (key, `.` menu, palette) confirms.
    """
    dynamic = getattr(screen, "action_descriptors", None)
    if callable(dynamic):
        return list(dynamic())
    danger_map: dict[str, str] = getattr(type(screen), "ACTION_DANGER", {})
    actions: list[ActionDescriptor] = []
    for binding in getattr(type(screen), "BINDINGS", []):
        if isinstance(binding, Binding) and binding.show:
            actions.append(ActionDescriptor(
                id=binding.id or binding.action,
                title=binding.description or binding.action,
                help=binding.tooltip or binding.description or binding.action,
                key=binding.key,
                danger=danger_map.get(binding.action, "none"),  # type: ignore[arg-type]
                action=binding.action,
            ))
    return actions


EDGE_ANSI = Theme(
    name="edge-ansi", primary="#35d7d7", secondary="#f0d75f", accent="#e36de3",
    foreground="#e6e6e6", background="#000000", surface="#10171b", panel="#172127",
    success="#5fe05f", warning="#f0d75f", error="#ff6565", dark=True,
    variables={
        "edge-focus": "#ffffff", "edge-selection": "#407887",
        "edge-muted": "#a7b0b5", "edge-disabled": "#747d82",
        "footer-key-foreground": "#35d7d7",
    },
)

EDGE_HIGH_CONTRAST = Theme(
    name="edge-high-contrast", primary="#66ffff", secondary="#ffff66", accent="#ff7dff",
    foreground="#ffffff", background="#000000", surface="#080808", panel="#151515",
    success="#7dff7d", warning="#ffff66", error="#ff7d7d", dark=True,
    variables={
        "edge-focus": "#ffffff", "edge-selection": "#007da8",
        "edge-muted": "#d0d0d0", "edge-disabled": "#8a8a8a",
        "footer-key-foreground": "#66ffff",
    },
)

EDGE_MONOCHROME = Theme(
    name="edge-monochrome", primary="#ffffff", secondary="#d7d7d7", accent="#ffffff",
    foreground="#ffffff", background="#000000", surface="#101010", panel="#202020",
    success="#ffffff", warning="#ffffff", error="#ffffff", dark=True,
    variables={
        "edge-focus": "#ffffff", "edge-selection": "#6a6a6a",
        "edge-muted": "#bcbcbc", "edge-disabled": "#808080",
        "footer-key-foreground": "#ffffff",
    },
)

EDGE_THEMES = (EDGE_ANSI, EDGE_HIGH_CONTRAST, EDGE_MONOCHROME)
