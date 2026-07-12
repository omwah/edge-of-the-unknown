"""WP-UI03 — numerical WCAG contrast gates for every supported semantic theme."""

from __future__ import annotations

import pytest
from textual.theme import Theme

from edge.tui.design import EDGE_THEMES

_BACKGROUNDS = ("background", "surface", "panel")
_TEXT_TOKENS = (
    "foreground", "primary", "secondary", "accent", "success", "warning", "error",
    "edge-muted", "footer-key-foreground",
)
_CONTROL_TOKENS = ("edge-focus", "edge-selection", "edge-disabled")


def _luminance(hex_color: str) -> float:
    """WCAG 2 relative luminance for a six-digit sRGB hex color."""
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [value / 12.92 if value <= 0.04045
              else ((value + 0.055) / 1.055) ** 2.4 for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def _color(theme: Theme, token: str) -> str:
    value = theme.variables.get(token) if token.startswith("edge-") or token.startswith("footer-") \
        else getattr(theme, token)
    assert isinstance(value, str) and value.startswith("#"), f"{theme.name}.{token} is not hex"
    return value


@pytest.mark.parametrize("theme", EDGE_THEMES, ids=lambda theme: theme.name)
def test_semantic_text_tokens_meet_wcag_aa(theme: Theme) -> None:
    """Normal and muted semantic text stays at or above 4.5:1 on every theme surface."""
    for token in _TEXT_TOKENS:
        for background in _BACKGROUNDS:
            ratio = _contrast(_color(theme, token), _color(theme, background))
            assert ratio >= 4.5, f"{theme.name}.{token} on {background}: {ratio:.2f}:1"


@pytest.mark.parametrize("theme", EDGE_THEMES, ids=lambda theme: theme.name)
def test_control_indicators_meet_contrast_floor(theme: Theme) -> None:
    """Focus, selection, and disabled-state indicators remain at least 3:1 on all surfaces."""
    for token in _CONTROL_TOKENS:
        for background in _BACKGROUNDS:
            ratio = _contrast(_color(theme, token), _color(theme, background))
            assert ratio >= 3.0, f"{theme.name}.{token} on {background}: {ratio:.2f}:1"
