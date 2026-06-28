"""`SpeciesPortrait` — a resize-aware Textual widget that shows a species portrait.

A thin wrapper over `edge.art.portrait`: it owns the Textual sizing/lifecycle
(re-rendering chafa to the box's current cell dimensions on mount and resize) and
falls back to a dim name placeholder when the image is missing or the chafa binding
isn't installed — so the screenshot harness and chafa-less environments still work.
"""

from __future__ import annotations

from rich.text import Text
from textual.events import Resize
from textual.widgets import Static

from edge.art import portrait as art_portrait


class SpeciesPortrait(Static):
    """Render a species' portrait image (by `roster_id`) into its allotted cell box."""

    def __init__(
        self,
        roster_id: str,
        name: str = "",
        symbols: str = art_portrait.DEFAULT_SYMBOLS,
        font_ratio: float = art_portrait.DEFAULT_FONT_RATIO,
    ) -> None:
        super().__init__()
        self._roster_id = roster_id
        self._name = name or roster_id
        self._symbols = symbols
        self._font_ratio = font_ratio
        self._path = art_portrait.resolve_portrait(roster_id)

    def on_mount(self) -> None:
        self._render_to_box()

    def on_resize(self, _event: Resize) -> None:
        self._render_to_box()

    def _render_to_box(self) -> None:
        cols, rows = self.content_size
        if cols <= 0 or rows <= 0:
            return  # not laid out yet; a resize event will follow
        self.update(self._portrait(cols, rows))

    def _portrait(self, cols: int, rows: int) -> Text:
        if self._path is not None:
            try:
                return art_portrait.render_portrait(
                    self._path, cols, rows, self._symbols, self._font_ratio
                )
            except Exception:
                pass  # missing binding / decode error — fall through to placeholder
        return Text(self._name, style="dim")
