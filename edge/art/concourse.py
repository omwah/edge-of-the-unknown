"""Static StarDock service raster selection and ANSI rendering.

The source artwork and its accessibility variants live under ``images/ui``.  This
module stays in the presentation-only ``edge.art`` layer and reuses the portrait
renderer's Chafa seam; callers retain a text fallback for missing assets/bindings.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text

from edge.art.portrait import REPO_ROOT, render_portrait

_ASSET_DIR = REPO_ROOT / "images" / "ui" / "stardock"
STARDOCK_ART_TABS = frozenset({
    "commodities", "shipyard", "hardware", "devices", "concourse", "bank", "tavern",
})

_THEME_VARIANTS = {
    "edge-ansi": "source",
    "edge-high-contrast": "high_contrast",
    "edge-monochrome": "monochrome",
}


def stardock_asset(tab: str, theme: str, *, cinematic: bool) -> Path:
    """Return the tab, theme, and layout-specific crop."""
    if tab not in STARDOCK_ART_TABS:
        raise ValueError(f"unknown StarDock art tab: {tab}")
    variant = _THEME_VARIANTS.get(theme, _THEME_VARIANTS["edge-ansi"])
    layout = "wide" if cinematic else "standard"
    return _ASSET_DIR / f"stardock_{tab}_{variant}_{layout}.png"


def render_stardock_art(tab: str, theme: str, *, cinematic: bool) -> Text:
    """Render a responsive service panel: 72×12 wide, 56×8 standard."""
    cols, rows = (72, 12) if cinematic else (56, 8)
    return render_portrait(stardock_asset(tab, theme, cinematic=cinematic), cols, rows)


def concourse_asset(theme: str, *, cinematic: bool) -> Path:
    """Compatibility wrapper for the original PT-06 asset tests."""
    return stardock_asset("concourse", theme, cinematic=cinematic)


def render_concourse(theme: str, *, cinematic: bool) -> Text:
    """Compatibility wrapper for the original PT-06 renderer."""
    return render_stardock_art("concourse", theme, cinematic=cinematic)
