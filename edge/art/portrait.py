"""Species portrait rendering via chafa (image → Rich Text terminal art).

Not TUI-specific: like the rest of `edge.art`, this emits a Rich `Text` and never
imports Textual. A species' `roster_id` maps 1:1 to an image file in the repo
`images/` directory; `render_portrait` runs that image through the chafa Python
binding (`chafa.py`) to a configurable symbol set and decodes its ANSI output to a
Rich `Text` sized to a given character-cell box. The `chafa`/`PIL` imports are lazy
(inside the function) so importing this module never requires the binding to be
installed — callers handle the `ImportError`/render failure and fall back.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text

# `edge/art/portrait.py` → parents[2] is the repo root (parents: art, edge, root).
IMAGES_DIR = Path(__file__).resolve().parents[2] / "images"

# Extensions tried, in order, for a species' portrait (most species are .jpg; a few .png).
_PORTRAIT_EXTS = (".jpg", ".png", ".jpeg", ".webp")

# chafa's CLI `--symbols` selector syntax; the binding's SymbolMap.apply_selectors accepts it.
DEFAULT_SYMBOLS = "vhalf+quad+geometric"

# Terminal cell aspect (width / height) chafa uses to keep the image's true proportions when
# fitting it into a character-cell box. ~0.5 (cells twice as tall as wide) is typical, but it
# varies by terminal/font; a value too high renders too few columns and squashes the image
# horizontally, so it's a tunable (UIConfig.portrait_font_ratio) — lower it to widen.
DEFAULT_FONT_RATIO = 0.5


def resolve_portrait(roster_id: str) -> Path | None:
    """Return the portrait image path for a species `roster_id`, or None if none exists."""
    for ext in _PORTRAIT_EXTS:
        candidate = IMAGES_DIR / f"{roster_id}{ext}"
        if candidate.is_file():
            return candidate
    return None


def render_portrait(
    path: Path,
    cols: int,
    rows: int,
    symbols: str = DEFAULT_SYMBOLS,
    font_ratio: float = DEFAULT_FONT_RATIO,
) -> Text:
    """Render image `path` to a Rich `Text` fitted within a `cols`×`rows` character-cell box.

    The image's aspect ratio is preserved: chafa fits it inside the box (letterboxing
    the remaining cells) rather than stretching it to fill. `font_ratio` is the terminal's
    cell width/height — match it to the terminal so the image isn't squashed (lower widens).
    Drives the chafa binding with the given `symbols` selector. Raises on a missing file, a
    missing binding (`ImportError`), or any chafa/PIL error — the caller decides the fallback.
    """
    from chafa import Canvas, CanvasConfig, PixelType, SymbolMap
    from PIL import Image

    image = Image.open(path).convert("RGBA")

    symbol_map = SymbolMap()
    symbol_map.apply_selectors(symbols)

    config = CanvasConfig()
    config.width = max(1, cols)
    config.height = max(1, rows)
    # Shrink width/height to the largest aspect-preserving fit within the box (stretch=False),
    # scaling up to the box on its limiting axis (zoom=True) so the portrait fills as much as it can.
    config.calc_canvas_geometry(image.width, image.height, font_ratio, zoom=True)
    config.set_symbol_map(symbol_map)

    canvas = Canvas(config)
    canvas.draw_all_pixels(
        PixelType.CHAFA_PIXEL_RGBA8_UNASSOCIATED,
        image.tobytes(),
        image.width,
        image.height,
        image.width * 4,  # rowstride: 4 bytes/pixel (RGBA)
    )
    return Text.from_ansi(canvas.print().decode())
