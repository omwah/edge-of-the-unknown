"""Shared character-grid canvas and band palette for baked map/nav views (§11).

Both the Computer → Map ego-graph (`mapgraph`) and the always-visible main-screen
nav rose (`navstrip`) bake their output as Rich-markup row strings drawn onto this
grid, which the TUI renders verbatim (the established baked-rows contract). Pure and
I/O-free, so both views reconstruct identically under `(seed, command log)`.
"""

from __future__ import annotations

# Distance-band → node tint, shared by the local map and the nav rose.
BAND_COLOR: dict[str, str] = {
    "Hub": "cyan",
    "Frontier": "green",
    "Deep": "magenta",
    "Void": "blue",
}
HERE_STYLE = "reverse bold cyan"  # the player's current sector


def esc(text: str) -> str:
    """Escape Rich-markup-significant characters in literal cell text."""
    return text.replace("[", r"\[")


class Canvas:
    """A character grid with a parallel per-cell style, emitted as markup rows."""

    def __init__(self, width: int, height: int) -> None:
        self.w = max(1, width)
        self.h = max(1, height)
        self._ch: list[list[str]] = [[" "] * self.w for _ in range(self.h)]
        self._st: list[list[str | None]] = [[None] * self.w for _ in range(self.h)]

    def put(self, y: int, x: int, text: str, style: str | None = None,
            *, protect: set[tuple[int, int]] | None = None) -> None:
        if not 0 <= y < self.h:
            return
        for i, char in enumerate(text):
            xx = x + i
            if 0 <= xx < self.w and not (protect and (y, xx) in protect):
                self._ch[y][xx] = char
                self._st[y][xx] = style

    def rows(self) -> list[str]:
        out: list[str] = []
        for y in range(self.h):
            chars, styles = self._ch[y], self._st[y]
            parts: list[str] = []
            i = 0
            while i < self.w:
                style = styles[i]
                j = i
                while j < self.w and styles[j] == style:
                    j += 1
                seg = esc("".join(chars[i:j]))
                parts.append(f"[{style}]{seg}[/]" if style else seg)
                i = j
            out.append("".join(parts).rstrip())
        while out and out[-1] == "":
            out.pop()
        return out
