"""Procedural TV-"snow" static — a placeholder for an as-yet-unsurveyed sprite.

Unlike the other generators this paints no recognisable subject: it fills the
frame with random low-contrast noise so a not-yet-revealed discovery reads as an
unresolved sensor return rather than leaking what it is. Determinism comes from
the caller-supplied `rng` (same contract as the other generators), so a given
seed always yields the same snow.
"""

import random
from rich.text import Text

# Weighted noise glyphs: skewed toward the lighter/empty cells so the field reads
# as flickering static rather than a solid wall of blocks. (glyph, weight).
STATIC_CHARS: list[tuple[str, int]] = [
    (" ", 26),
    ("·", 18),
    (":", 12),
    ("░", 16),
    ("▒", 10),
    ("▓", 5),
    ("█", 2),
]

# Weighted greys for the snow — mostly dim, an occasional brighter speck so it
# shimmers. (rich_style_string, weight).
STATIC_COLORS: list[tuple[str, int]] = [
    ("grey23", 30),
    ("grey39", 24),
    ("bright_black", 20),
    ("grey58", 12),
    ("grey70", 6),
    ("white", 2),
]

# The lone subtype; kept as a tuple so `generate_sprite` / the CLI can enumerate it.
STATIC_SUBTYPES = ("snow",)


class StaticGenerator:
    """Generates a frame of random low-contrast static ("snow")."""

    def _pick_weighted(self, rng: random.Random, choices: list[tuple[str, int]]) -> str:
        total = sum(weight for _, weight in choices)
        r = rng.randint(0, total - 1)
        current = 0
        for item, weight in choices:
            current += weight
            if r < current:
                return item
        return choices[-1][0]

    def generate(self, rng: random.Random, subtype: str, width: int, height: int) -> Text:
        """Fill a `width` × `height` frame with weighted random noise glyphs.

        `subtype` is accepted for signature parity with the other generators; the
        only variation is "snow", so it doesn't branch on it.
        """
        out = Text()
        for y in range(height):
            for _ in range(width):
                char = self._pick_weighted(rng, STATIC_CHARS)
                if char == " ":
                    out.append(" ")
                else:
                    out.append(char, style=self._pick_weighted(rng, STATIC_COLORS))
            if y < height - 1:
                out.append("\n")
        return out
