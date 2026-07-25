"""Cloud City station-interior art (GW-WP15).

Styling for `edge.core.groundwar.interior.InteriorLayout` — the same core/art
split as `edge.art.terrain` (core owns feature names, this module owns
glyphs/colours; `edge.core` never imports this module). Floor features
(corridor/plaza/habitation/engineering/command_core/hazards/cover) reuse
`edge.art.terrain`'s per-cell weighted-glyph-pool pattern via
`resolve_feature_char` — that texture-only style already reads fine for flat
floors. `bulkhead`/`security_door` do not: an interior's rooms and corridors
only read as connected structure with **wall-aware** rendering, so those two
get a neighbor-bitmask box-drawing junction lookup instead (the interview
decision distinguishing this module from the planet-terrain style it borrows
everything else from).
"""

from __future__ import annotations

import random

from edge.art.terrain import resolve_feature_char
from edge.core.groundwar.interior import InteriorLayout, wall_neighbor_mask

Cell = tuple[str, str, str]  # (char, fg, bg)

# Per-feature weighted glyph pools (texture only — no neighbor awareness), same
# shape/convention as edge.art.terrain.FEATURES_REGISTRY. Every glyph here must be
# single-width per `rich.cells.cell_len` — a double-width pick (⚡/⌘-style symbols are
# common offenders) desyncs the fixed per-cell grid one column per occurrence, which
# then cascades through the rest of that row and misaligns whatever sits to its right
# (the sidebar's own border, in the live screens).
FEATURES_REGISTRY: dict[str, list[tuple[str, float]]] = {
    "corridor": [(" ", 6), (".", 1), ("·", 1)],
    "plaza": [(" ", 8), ("·", 1), ("˙", 1)],
    "habitation": [(" ", 5), ("≡", 1), ("⊟", 1)],
    "engineering": [(" ", 4), ("╬", 1), ("╫", 1), ("¤", 0.5)],
    "command_core": [(" ", 6), ("◈", 1), ("✦", 0.3)],
    "cover_strut": [("◘", 1), ("▤", 1), (" ", 2)],
    "vacuum": [("░", 2), ("·", 1), (" ", 3)],
    "fire": [("▓", 1), ("≈", 1), (" ", 2)],
    "electrical": [("⌁", 0.5), ("∴", 1), (" ", 4)],
}

# (fg, bg) per floor feature name.
FEATURE_COLORS: dict[str, tuple[str, str]] = {
    "corridor": ("grey62", "grey11"),
    "plaza": ("grey70", "grey15"),
    "habitation": ("wheat4", "grey15"),
    "engineering": ("grey58", "grey19"),
    "command_core": ("gold3", "grey19"),
    "cover_strut": ("grey54", "grey15"),
    "vacuum": ("bright_cyan", "grey7"),
    "fire": ("bright_red", "grey11"),
    "electrical": ("bright_yellow", "grey11"),
}

WALL_COLOR = ("grey78", "grey7")
DOOR_GLYPH = "◫"
DOOR_COLOR = ("bright_yellow", "grey7")
LIFT_GLYPH = "▲"
LIFT_COLOR = ("bright_magenta", "grey15")
OBJECTIVE_GLYPH = "✪"
OBJECTIVE_COLOR = ("bold gold3", "grey19")

# The standard 16-case wall-junction table, indexed by a 4-bit mask
# (N=1, S=2, E=4, W=8) of which orthogonal neighbours are themselves wall-like
# (`edge.core.groundwar.interior.wall_neighbor_mask`) — public so the live-screen
# per-cell resolver (a server-computed mask, not a whole-layout pass) can index it too.
WALL_GLYPHS = (
    "■", "╵", "╷", "│", "╶", "└", "┌", "├",
    "╴", "┘", "┐", "┤", "─", "┴", "┬", "┼",
)

# One canonical (glyph, label, fg, bg) legend row per feature name, for a
# preview/help panel — deliberately not randomized, unlike in-map rendering.
LEGEND: tuple[tuple[str, str, str, str], ...] = (
    ("■/─/┼", "bulkhead", *WALL_COLOR),
    (DOOR_GLYPH, "security door (breachable)", *DOOR_COLOR),
    (" ", "corridor", *FEATURE_COLORS["corridor"]),
    (" ", "plaza (open space)", *FEATURE_COLORS["plaza"]),
    ("≡", "habitation", *FEATURE_COLORS["habitation"]),
    ("╬", "engineering", *FEATURE_COLORS["engineering"]),
    (OBJECTIVE_GLYPH, "command core (objective)", *OBJECTIVE_COLOR),
    ("◘", "cover strut", *FEATURE_COLORS["cover_strut"]),
    (LIFT_GLYPH, "lift (teleport link)", *LIFT_COLOR),
    ("░", "vacuum hazard", *FEATURE_COLORS["vacuum"]),
    ("▓", "fire hazard", *FEATURE_COLORS["fire"]),
    ("⌁", "electrical hazard", *FEATURE_COLORS["electrical"]),
)


def _wall_glyph(grid: list[list[str]], x: int, y: int, width: int, height: int) -> str:
    """The junction glyph for a wall-like cell (shares its mask math with the
    live-screen per-cell resolver via `wall_neighbor_mask`, so a whole-layout bake
    here and a server-computed mask there always agree)."""
    mask = wall_neighbor_mask(lambda nx, ny: grid[ny][nx], x, y, width, height)
    return WALL_GLYPHS[mask]


def style_interior(rng: random.Random, layout: InteriorLayout) -> list[list[Cell]]:
    """A styled (char, fg, bg) grid aligned cell-for-cell with `layout.feature_grid`.

    `bulkhead` renders as a neighbor-aware box-drawing junction; `security_door`
    and `lift` always render as their own fixed glyph (a door or lift is a target/
    landmark, not texture); the single `layout.objective` cell gets a marker glyph
    layered over its `command_core` floor. Every other feature resolves through
    the same weighted-glyph-pool style `edge.art.terrain` uses for planet biomes.
    """
    grid = [list(row) for row in layout.feature_grid]
    width, height = layout.width, layout.height
    out: list[list[Cell]] = []
    lift_cells = {p for pair in layout.lift_links for p in pair}
    for y in range(height):
        row: list[Cell] = []
        for x in range(width):
            feature = grid[y][x]
            if (x, y) == layout.objective:
                row.append((OBJECTIVE_GLYPH, *OBJECTIVE_COLOR))
            elif feature == "bulkhead":
                row.append((_wall_glyph(grid, x, y, width, height), *WALL_COLOR))
            elif feature == "security_door":
                row.append((DOOR_GLYPH, *DOOR_COLOR))
            elif (x, y) in lift_cells:
                row.append((LIFT_GLYPH, *LIFT_COLOR))
            else:
                fg, bg = FEATURE_COLORS.get(feature, ("grey50", "grey11"))
                ch = resolve_feature_char(rng, feature, FEATURES_REGISTRY)
                row.append((ch, fg, bg))
        out.append(row)
    return out
