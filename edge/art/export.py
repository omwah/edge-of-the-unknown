"""Vector export for the procedural sprites (dev-only sprite sheets).

Lays every rendered sprite out on a single black contact sheet and writes it to
SVG and/or PDF. matplotlib is imported lazily (headless ``Agg`` backend) so the
rest of ``edge.art`` stays free of it, mirroring ``edge/bigbang/render.py``.

Each rich ``Text`` sprite is decomposed into coloured character cells; cells are
drawn as monospace glyphs over per-cell background rectangles, so the vector
output reproduces the terminal look (hull shading, beacon/glow, facet patches)
and stays crisp at any zoom. Cell geometry is ~1:1.8 (width:height) to match a
terminal cell.
"""

from __future__ import annotations

from math import ceil, sqrt
from pathlib import Path

from rich.console import Console
from rich.text import Text

# Inches per character cell and the matching monospace font size (pt). Chosen so a
# monospace glyph's advance (~0.6 * size) tiles the cell width exactly:
#   cell width  0.10in = 7.2pt  ~= 0.6 * 12pt
#   cell height 0.18in = 13.0pt  > 12pt font  (a little leading)
_CELL_W_IN = 0.10
_CELL_H_IN = 0.18
_FONT_PT = 12.0

# A wide off-screen console so sprite lines are never wrapped when we walk their
# rendered segments to recover per-character colours.
_RENDER_WIDTH = 1000


def _sprite_cells(
    console: Console, sprite: Text
) -> list[list[tuple[str, str | None, str | None]]]:
    """Decompose a sprite into rows of ``(char, fg_hex, bg_hex)`` cells, where a
    hex is ``None`` when that channel is unstyled (drawn as the black void)."""
    rows: list[list[tuple[str, str | None, str | None]]] = [[]]
    for segment in console.render(sprite, console.options):
        if segment.control:
            continue
        style = segment.style
        fg = bg = None
        if style is not None:
            if style.color is not None:
                fg = style.color.get_truecolor().hex
            if style.bgcolor is not None:
                bg = style.bgcolor.get_truecolor().hex
        for ch in segment.text:
            if ch == "\n":
                rows.append([])
            else:
                rows[-1].append((ch, fg, bg))
    if rows and not rows[-1]:
        rows.pop()
    return rows


def _draw_sprite(
    ax: object,
    cells: list[list[tuple[str, str | None, str | None]]],
    label: str,
    *,
    ox: float,
    oy: float,
    tile_w: int,
) -> None:
    """Draw one sprite (title + cells) into ``ax`` at tile origin ``(ox, oy)``."""
    from matplotlib.patches import Rectangle

    ncols = max((len(row) for row in cells), default=0)
    # Centre the sprite horizontally in its tile; the title sits on the top row.
    x0 = ox + (tile_w - ncols) / 2.0
    y0 = oy + 1.0

    # Title, scaled down if it would overrun the tile width.
    if label:
        fit = tile_w * 12.0 / max(len(label), 1)
        ax.text(  # type: ignore[attr-defined]
            ox + tile_w / 2.0, oy + 0.5, label,
            color="white", ha="center", va="center",
            family="monospace", fontsize=max(4.0, min(9.0, fit)),
        )

    for r, row in enumerate(cells):
        for c, (ch, fg, bg) in enumerate(row):
            if bg is not None and bg != "#000000":
                ax.add_patch(  # type: ignore[attr-defined]
                    Rectangle((x0 + c, y0 + r), 1, 1, color=bg, linewidth=0, zorder=0)
                )
            if ch != " " and fg is not None:
                ax.text(  # type: ignore[attr-defined]
                    x0 + c + 0.5, y0 + r + 0.5, ch,
                    color=fg, ha="center", va="center",
                    family="monospace", fontsize=_FONT_PT, zorder=1,
                )


def export_sprite_sheet(
    sprites: list[tuple[str, Text]],
    out_path: str | Path,
    *,
    cols: int | None = None,
) -> list[Path]:
    """Render ``sprites`` (``(label, Text)`` pairs) onto one contact sheet and
    write it to vector files.

    ``out_path`` selects the format(s): a ``.svg`` or ``.pdf`` suffix writes just
    that format; any other path writes both ``<path>.svg`` and ``<path>.pdf``.
    ``cols`` sets the grid column count (defaults to a near-square layout).
    Returns the paths written.
    """
    import matplotlib

    matplotlib.use("Agg")  # headless: no display needed
    import matplotlib.pyplot as plt

    if not sprites:
        raise ValueError("no sprites to export")

    console = Console(
        width=_RENDER_WIDTH, force_terminal=True, color_system="truecolor"
    )
    cells = [_sprite_cells(console, sprite) for _, sprite in sprites]

    n = len(sprites)
    cols = cols or max(1, round(sqrt(n)))
    rows = ceil(n / cols)
    # Uniform tiles sized to the largest sprite, with room for a title + a gap.
    tile_w = max((max((len(r) for r in c), default=0) for c in cells), default=1) + 2
    tile_h = max((len(c) for c in cells), default=1) + 2

    sheet_cols = cols * tile_w
    sheet_rows = rows * tile_h
    fig = plt.figure(figsize=(sheet_cols * _CELL_W_IN, sheet_rows * _CELL_H_IN))
    fig.patch.set_facecolor("black")
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_facecolor("black")
    ax.set_xlim(0, sheet_cols)
    ax.set_ylim(0, sheet_rows)
    ax.invert_yaxis()  # row 0 at the top
    ax.axis("off")

    for idx, ((label, _), cell_rows) in enumerate(zip(sprites, cells)):
        ox = (idx % cols) * tile_w
        oy = (idx // cols) * tile_h
        _draw_sprite(ax, cell_rows, label, ox=ox, oy=oy, tile_w=tile_w)

    base = Path(out_path)
    if base.suffix.lower() in (".svg", ".pdf"):
        targets = [base]
    else:
        targets = [base.with_suffix(".svg"), base.with_suffix(".pdf")]

    for target in targets:
        fig.savefig(target, facecolor="black")
    plt.close(fig)
    return targets
