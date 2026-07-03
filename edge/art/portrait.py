"""Species portrait rendering via chafa (image → Rich Text terminal art).

Not TUI-specific: like the rest of `edge.art`, this emits a Rich `Text` and never
imports Textual. A species' `roster_id` maps to one or more image files in a
configurable image directory; `render_portrait` runs a chosen image through the chafa
Python binding (`chafa.py`) to a configurable symbol set and decodes its ANSI output to a
Rich `Text` sized to a given character-cell box. The `chafa`/`PIL` imports are lazy
(inside the function) so importing this module never requires the binding to be
installed — callers handle the `ImportError`/render failure and fall back.

A species may have **variant** images: alongside the bare `<roster_id>.<ext>`, any file
named `<roster_id>_<digits>.<ext>` (e.g. `vesk_1.jpg`, `vesk_01.png`, `vesk_001.png`) is a
further portrait of that species. `resolve_portrait` collects all of them and picks one
(deterministically by `variant`, else at random), so different individuals of a species
can wear different faces.
"""

from __future__ import annotations

import math
import random
import re
from functools import lru_cache
from pathlib import Path

from rich.text import Text

# `edge/art/portrait.py` → parents[2] is the repo root (parents: art, edge, root). Relative
# `portrait_dir` config values resolve against this; absolute values are used as-is.
REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGES_DIR = REPO_ROOT / "images"  # default portrait directory

# Extensions recognised for a species' portrait (most species are .jpg; a few .png).
_PORTRAIT_EXTS = (".jpg", ".jpeg", ".png", ".webp")

# chafa's CLI `--symbols` selector syntax; the binding's SymbolMap.apply_selectors accepts it.
DEFAULT_SYMBOLS = "vhalf+quad+geometric"

# Terminal cell aspect (width / height) chafa uses to keep the image's true proportions when
# fitting it into a character-cell box. ~0.5 (cells twice as tall as wide) is typical, but it
# varies by terminal/font; a value too high renders too few columns and squashes the image
# horizontally, so it's a tunable (UIConfig.portrait_font_ratio) — lower it to widen.
DEFAULT_FONT_RATIO = 0.5


def portraits_dir(images_dir: str | Path | None = None) -> Path:
    """Resolve the portrait directory: the default, an absolute path, or repo-root-relative."""
    if images_dir is None:
        return IMAGES_DIR
    path = Path(images_dir)
    return path if path.is_absolute() else REPO_ROOT / path


def list_portraits(roster_id: str, images_dir: str | Path | None = None) -> list[Path]:
    """All portrait files for `roster_id`: the bare `<id>.<ext>` plus `<id>_<digits>.<ext>`
    variants, sorted by name (so a variant index is stable). Empty if none exist."""
    base = portraits_dir(images_dir)
    if not base.is_dir():
        return []
    pattern = re.compile(rf"{re.escape(roster_id)}(_\d+)?$")
    return sorted(
        p
        for p in base.iterdir()
        if p.is_file()
        and p.suffix.lower() in _PORTRAIT_EXTS
        and pattern.fullmatch(p.stem)
    )


def resolve_portrait(
    roster_id: str,
    images_dir: str | Path | None = None,
    variant: int | None = None,
) -> Path | None:
    """Pick one portrait file for `roster_id`, or None if the species has none.

    With several variants available, `variant` selects one deterministically (modulo the
    count, so any stable per-individual key works); when it is None a variant is chosen at
    random. A single bare `<id>.<ext>` is just the one-element case.
    """
    candidates = list_portraits(roster_id, images_dir)
    if not candidates:
        return None
    if variant is None:
        return random.choice(candidates)
    return candidates[variant % len(candidates)]


# chafa rendering is expensive, so its ANSI output is memoised. The key includes `cols`/`rows`
# (already box-clamped) and the file's mtime, so re-rendering the *same* portrait at a *different*
# size is a cache miss that gets stored as its own entry (a resize is cached, not a collision), and
# regenerating the image file on disk invalidates the stale entry. Capping at 256 entries bounds the
# memory for a roster's worth of portraits across the handful of box sizes the UI actually uses.
@lru_cache(maxsize=256)
def _render_portrait_ansi(
    path: str,
    cols: int,
    rows: int,
    symbols: str,
    font_ratio: float,
    _mtime_ns: int,
) -> str:
    """Run image `path` through chafa and return its decoded ANSI string (the cached unit)."""
    from chafa import Canvas, CanvasConfig, PixelType, SymbolMap
    from PIL import Image

    image = Image.open(path).convert("RGBA")

    symbol_map = SymbolMap()
    symbol_map.apply_selectors(symbols)

    config = CanvasConfig()
    config.width = cols
    config.height = rows
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
    return canvas.print().decode()


# The roaming Entity has no body to photograph (§7): a bodiless luminous arbiter. When no
# portrait image is available (chafa-less terminal, missing asset) its contact-screen slot
# fills with a procedural gold **nebular bloom** instead of the bare name placeholder — the
# `cosmic_arbiter` palette (pale gold, luminous). Deterministic from `variant` so it stays
# stable across resizes/rebuilds.
_BLOOM_PALETTE = ("khaki1", "gold1", "gold3", "dark_goldenrod")
_BLOOM_RAMP = " ·:+░▒▓█"  # low → high intensity


def nebular_bloom(cols: int, rows: int, variant: int = 0) -> Text:
    """A full-slot procedural gold nebular bloom for the bodiless Entity (§7, WP35).

    A soft radial glow with seeded low-harmonic turbulence and a scatter of sparkles,
    coloured up the `cosmic_arbiter` gold ramp — no external assets or bindings, so it
    renders anywhere. `variant` seeds the turbulence phases and grain deterministically.
    """
    cols, rows = max(1, cols), max(1, rows)
    rng = random.Random(f"bloom|{variant}")
    cx, cy = (cols - 1) / 2.0, (rows - 1) / 2.0
    rx, ry = max(1.0, cols / 2.0), max(1.0, rows / 2.0)
    # A handful of low harmonics + phases give the cloud its lumpy, off-centre bloom.
    ph = [rng.uniform(0.0, math.tau) for _ in range(3)]
    n_pal, n_ramp = len(_BLOOM_PALETTE), len(_BLOOM_RAMP)

    text = Text()
    for y in range(rows):
        for x in range(cols):
            dx, dy = (x - cx) / rx, (y - cy) / ry
            r = math.hypot(dx, dy)
            angle = math.atan2(dy, dx)
            turb = (0.16 * math.sin(3 * angle + ph[0])
                    + 0.10 * math.sin(2 * angle + 5 * r + ph[1])
                    + 0.07 * math.sin(5 * angle + ph[2]))
            intensity = (1.0 - r) + turb + rng.uniform(-0.05, 0.05)
            if intensity <= 0.05:
                text.append(" ")
                continue
            t = max(0.0, min(1.0, intensity))
            char = _BLOOM_RAMP[min(n_ramp - 1, int(t * n_ramp))]
            # A rare sparkle in the mid-body, brightest hue.
            if 0.35 < t < 0.85 and rng.random() < 0.03:
                text.append(rng.choice("✦✧·"), style=f"bold {_BLOOM_PALETTE[0]}")
                continue
            hue = _BLOOM_PALETTE[min(n_pal - 1, int((1.0 - t) * n_pal))]
            text.append(char, style=hue)
        if y < rows - 1:
            text.append("\n")
    return text


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

    The chafa render is memoised per (path, size, symbols, font_ratio, mtime), so repeat
    requests — including the same portrait re-rendered at a different box size — are served from
    cache. A fresh `Text` is rebuilt from the cached ANSI each call so callers may mutate it
    freely without corrupting the shared cache.
    """
    cols = max(1, cols)
    rows = max(1, rows)
    ansi = _render_portrait_ansi(
        str(path), cols, rows, symbols, font_ratio, Path(path).stat().st_mtime_ns
    )
    return Text.from_ansi(ansi)
