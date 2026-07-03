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
        images_dir: str | None = None,
        variant: int | None = None,
        bloom: bool = False,
    ) -> None:
        super().__init__()
        self._roster_id = roster_id
        self._name = name or roster_id
        self._symbols = symbols
        self._font_ratio = font_ratio
        # The bodiless Entity (§7): when it has no portrait image, fill the slot with a
        # procedural nebular bloom rather than the bare name placeholder (WP35).
        self._bloom = bloom
        self._bloom_variant = variant or 0
        # Pick the image (and any variant) once, here — so resizes re-render the *same*
        # portrait rather than reshuffling variants on every layout change.
        self._path = art_portrait.resolve_portrait(roster_id, images_dir, variant)

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
        if self._bloom:
            return art_portrait.nebular_bloom(cols, rows, self._bloom_variant)
        return Text(self._name, style="dim")
