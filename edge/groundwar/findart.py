"""Procedural art for Expedition-mode archaeological finds.

New peaceful-mode art, deliberately *not* the main game's discovery generator:
these are ground-level field sketches — a dawn sky over a textured dig horizon
with the find rendered at the excavation. Deterministic from `(kind, seed)`.
"""

from __future__ import annotations

import random

from rich.text import Text

from edge.core.surface_finds import FIND_KINDS, site_name

__all__ = ["ART_H", "ART_W", "FIND_KINDS", "LORE_PLACEHOLDER", "generate_find_art", "site_name"]

ART_W = 48
ART_H = 15

Cell = tuple[str, str]
Canvas = list[list[Cell]]


LORE_PLACEHOLDER = (
    "Lore entry pending — the Institute's xenoarchaeologists are still "
    "translating what you found."
)

# --- canvas helpers ----------------------------------------------------------


def _blank(sky: list[str], ground_fg: str, ground_bg: str,
           rng: random.Random) -> Canvas:
    horizon = ART_H - 5
    canvas: Canvas = []
    for y in range(ART_H):
        row: list[Cell] = []
        for _x in range(ART_W):
            if y < horizon:
                band = sky[min(len(sky) - 1, y * len(sky) // horizon)]
                ch = " "
                if rng.random() < 0.02:
                    ch = rng.choice("·˙.")
                row.append((ch, f"grey58 on {band}"))
            else:
                ch = rng.choice("  .,'`   ▖▗  ")
                row.append((ch, f"{ground_fg} on {ground_bg}"))
        canvas.append(row)
    return canvas


def _put(canvas: Canvas, x: int, y: int, ch: str, style: str) -> None:
    if 0 <= y < ART_H and 0 <= x < ART_W:
        bg = canvas[y][x][1].split(" on ")[-1]
        canvas[y][x] = (ch, f"{style} on {bg}")


def _text(canvas: Canvas, x: int, y: int, s: str, style: str) -> None:
    for i, ch in enumerate(s):
        _put(canvas, x + i, y, ch, style)


def _pit(canvas: Canvas, rng: random.Random) -> None:
    """The excavation trench framing every find: stakes, cordline, spoil heaps."""
    y = ART_H - 5
    _text(canvas, 6, y, "┍" + "╌" * (ART_W - 14) + "┑", "grey54")
    for gx in (4, ART_W - 4):
        _put(canvas, gx, y + 1, "╻", "grey62")
    for _ in range(6):
        sx = rng.randint(3, ART_W - 4)
        _put(canvas, sx, ART_H - 1 - rng.randint(0, 1), rng.choice("▲▴"), "grey42")


# --- per-kind renders --------------------------------------------------------


def _draw_colonnade(canvas: Canvas, rng: random.Random, accent: str) -> None:
    base = ART_H - 5
    for i in range(5):
        x = 9 + i * 7 + rng.randint(-1, 1)
        h = rng.randint(3, 6)
        for dy in range(h):
            _put(canvas, x, base - 1 - dy, "║", accent)
        top = "╨" if h < 5 else "╥"
        _put(canvas, x, base - 1 - h, top, accent)
        if rng.random() < 0.6:  # the snapped-off capital, lying nearby
            _put(canvas, x + rng.choice((-2, 2)), base, "▬", "grey54")
    _text(canvas, 12, base, "▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁", "grey42")


def _draw_cache(canvas: Canvas, rng: random.Random, accent: str) -> None:
    base = ART_H - 4
    cx = ART_W // 2
    _text(canvas, cx - 7, base, "╲______________╱"[: 16], "grey54")
    for _ in range(7):
        x = cx + rng.randint(-5, 5)
        _put(canvas, x, base - rng.randint(0, 1), rng.choice("◫▣◰⌸"), accent)
    _put(canvas, cx, base - 2, "◉", f"bold {accent}")
    for dx in (-2, 2):
        _put(canvas, cx + dx, base - 3, "·", accent)  # a faint shimmer above the seal


def _draw_obelisk(canvas: Canvas, rng: random.Random, accent: str) -> None:
    base = ART_H - 5
    cx = ART_W // 2
    h = 8
    for dy in range(h):
        _put(canvas, cx - 1, base - dy, "▐", "grey66")
        _put(canvas, cx, base - dy, rng.choice("ᚔᚋᚚ᚜᚛ᚈ"), accent)
        _put(canvas, cx + 1, base - dy, "▌", "grey66")
    _put(canvas, cx, base - h, "▲", f"bold {accent}")
    _text(canvas, cx - 4, base + 1, "▄▄▄▄▄▄▄▄▄", "grey42")


def _draw_leviathan(canvas: Canvas, rng: random.Random, accent: str) -> None:
    base = ART_H - 4
    cx = ART_W // 2
    for i in range(6):
        off = 3 + i * 3
        h = 5 - abs(i - 2)
        for dy in range(max(2, h)):
            _put(canvas, cx - off, base - dy, "(", accent)
            _put(canvas, cx + off, base - dy, ")", accent)
    _text(canvas, cx - 10, base, "═" * 21, "grey58")  # the spine, half-buried
    _put(canvas, cx - 14, base - 1, "◔", f"bold {accent}")  # the skull's orbit
    for _ in range(4):
        _put(canvas, cx + rng.randint(-12, 12), base + 1, "∙", "grey46")


def _draw_beacon(canvas: Canvas, rng: random.Random, accent: str) -> None:
    base = ART_H - 5
    cx = ART_W // 2
    for dx in range(-4, 5):  # the dome
        h = 3 - abs(dx) // 2
        for dy in range(h):
            _put(canvas, cx + dx, base - dy, "▓" if abs(dx) < 3 else "▒", "grey62")
    for dy in range(4):  # the mast
        _put(canvas, cx, base - 3 - dy, "│", accent)
    _put(canvas, cx, base - 7, "✳", f"bold {accent}")
    for r, ch in ((2, "("), (4, "(")):  # the signal, still going out
        _put(canvas, cx - r, base - 7, ch, accent)
        _put(canvas, cx + r, base - 7, {"(": ")"}[ch], accent)
    if rng.random() < 0.5:
        _text(canvas, cx - 2, base + 1, "▔▔▔▔▔", "grey42")


_DRAW = {
    "colonnade": _draw_colonnade,
    "cache": _draw_cache,
    "obelisk": _draw_obelisk,
    "leviathan": _draw_leviathan,
    "beacon": _draw_beacon,
}

_SKY = ["grey7", "grey11", "grey15", "dark_slate_gray1"]
_SKIES = {  # per-kind dawn palettes, darkest band first
    "colonnade": ["grey7", "grey15", "orange4", "gold3"],
    "cache": ["grey7", "grey11", "purple4", "medium_orchid3"],
    "obelisk": ["grey7", "grey15", "deep_sky_blue4", "steel_blue"],
    "leviathan": ["grey7", "grey15", "grey30", "tan"],
    "beacon": ["grey7", "grey11", "dark_green", "green4"],
}


def generate_find_art(kind: str, seed: int) -> Text:
    """The field-sketch panel for the congratulations / field-notes modal."""
    rng = random.Random(f"findart|{kind}|{seed}")
    fk = FIND_KINDS[kind]
    canvas = _blank(_SKIES.get(kind, _SKY), "grey39", "grey19", rng)
    _pit(canvas, rng)
    _DRAW[kind](canvas, rng, fk.accent)
    out = Text(no_wrap=True)
    for y, row in enumerate(canvas):
        for ch, style in row:
            out.append(ch, style)
        if y < ART_H - 1:
            out.append("\n")
    return out
