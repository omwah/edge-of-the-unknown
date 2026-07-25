"""Cloud City station-interior art (GW-WP15).

Styling for `edge.core.groundwar.interior.InteriorLayout` — the same core/art
split as `edge.art.terrain` (core owns feature names, this module owns
glyphs/colours; `edge.core` never imports this module). Floor features
(corridor/plaza/habitation/engineering/command_core/bar/store/promenade/
hazards/cover) reuse `edge.art.terrain`'s per-cell weighted-glyph-pool pattern
via `resolve_feature_char`, but every ambient pool is a single blank glyph —
even a sparse random pick still reads as scattered noise with no pattern
(interview notes: "too busy", then "still looks chaotic" once merely thinned).
`bulkhead`/`security_door` do not blank out: an interior's rooms and corridors
only read as connected structure with **wall-aware** rendering, so those two
get a neighbor-bitmask box-drawing junction lookup instead (the interview
decision distinguishing this module from the planet-terrain style it borrows
everything else from). All the room's visual interest instead comes from
`edge.core.groundwar.interior._place_landmarks`: fixed-glyph furniture, styled
here like `lift` (not texture), composed two-plus feature names per object (a
jet vs. a basin ring, a counter body vs. its end caps, a shelf run vs. its end
posts) so a fountain/bar counter/shelf run reads as a small drawn object, and
placed at a **regular stride** for `bed`/`console`/`table` — a bunk row, a
console bank, a grid of dining tables — the way a real deck plan repeats
identical cabins and tables rather than scattering single set pieces.
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
    # Blank floors — no per-cell texture roll at all. A room's own bg colour,
    # `_place_landmarks`'s one bold centrepiece, and `_sprinkle`'s clustered hazard/
    # cover patch (edge.core.groundwar.interior) now carry all the visual interest;
    # per-cell random glyphs, however sparse, still read as scattered noise with no
    # pattern to it (the "still chaotic" interview note) — order comes from *removing*
    # randomness from the ambient floor, not merely thinning it out.
    "corridor": [(" ", 1)],
    "plaza": [(" ", 1)],
    "habitation": [(" ", 1)],
    "engineering": [(" ", 1)],
    "command_core": [(" ", 1)],
    "bar": [(" ", 1)],
    "store": [(" ", 1)],
    "promenade": [(" ", 1)],
    # Hazard/cover cells are placed as one contiguous patch per room (`_sprinkle`),
    # not independent per-cell rolls, so a single glyph each stays a solid, legible
    # shape instead of gaining holes from a mixed-in blank option.
    "cover_strut": [("▤", 1)],
    "vacuum": [("░", 1)],
    "fire": [("▓", 1)],
    "electrical": [("⌁", 1)],
    # Landmarks (edge.core.groundwar.interior._place_landmarks): each a fixed glyph,
    # not texture, like `lift` — two per object (a centre/body vs. its ring/end caps)
    # so it draws as a small composed object rather than one repeated glyph.
    "fountain_jet": [("◉", 1)],
    "fountain_basin": [("○", 1)],
    "bar_counter": [("─", 1)],
    "bar_counter_end": [("●", 1)],
    "shelf": [("▦", 1)],
    "shelf_end": [("│", 1)],
    # Lattice furniture (`_place_row`/`_place_grid`): a repeated single-cell object at
    # a fixed stride, e.g. a row of bunks or a grid of dining tables — regularity, not
    # density, is what should read as "designed" here.
    "bed": [("⊟", 1)],
    "console": [("▧", 1)],
    "table": [("□", 1)],
}

# (fg, bg) per floor feature name — a light, blueprint-on-white hull rather than
# a dark one: every bg sits in the grey82-grey100 band, with fg colours darkened
# to match (a straight light/dark swap of the old dark-hull palette would have
# left former dark-on-dark accents unreadable against paper-white floors).
FEATURE_COLORS: dict[str, tuple[str, str]] = {
    "corridor": ("grey54", "grey100"),
    "plaza": ("grey58", "grey93"),
    "habitation": ("orange4", "grey89"),
    "engineering": ("steel_blue", "grey85"),
    "command_core": ("dark_goldenrod", "grey89"),
    "bar": ("dark_red", "grey89"),
    "store": ("green4", "grey89"),
    "promenade": ("cadet_blue", "grey100"),
    "cover_strut": ("grey42", "grey85"),
    "vacuum": ("dark_cyan", "#eaf6f6"),
    "fire": ("red3", "#fbe9e9"),
    "electrical": ("dark_goldenrod", "#fdf6d9"),
    "fountain_jet": ("deep_sky_blue4", "grey93"),
    "fountain_basin": ("steel_blue3", "grey93"),
    "bar_counter": ("orange4", "grey89"),
    "bar_counter_end": ("dark_red", "grey89"),
    "shelf": ("green4", "grey89"),
    "shelf_end": ("dark_green", "grey89"),
    "bed": ("slate_blue3", "grey89"),
    "console": ("dodger_blue3", "grey85"),
    "table": ("dark_sea_green4", "grey93"),
}

WALL_COLOR = ("grey19", "grey82")
DOOR_GLYPH = "◫"
DOOR_COLOR = ("dark_orange3", "grey85")
LIFT_GLYPH = "▲"
LIFT_COLOR = ("purple4", "grey89")
OBJECTIVE_GLYPH = "✪"
OBJECTIVE_COLOR = ("bold dark_goldenrod", "grey89")

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
    ("◉/○", "fountain", *FEATURE_COLORS["fountain_jet"]),
    ("⊟", "habitation (sleeping quarters, bunk row)", *FEATURE_COLORS["bed"]),
    ("▧", "engineering (maintenance, console row)", *FEATURE_COLORS["console"]),
    ("─/●", "bar counter", *FEATURE_COLORS["bar_counter"]),
    ("□", "bar / restaurant (tables)", *FEATURE_COLORS["table"]),
    ("▦/│", "shelving", *FEATURE_COLORS["shelf"]),
    (" ", "store", *FEATURE_COLORS["store"]),
    ("□", "promenade (dining tables)", *FEATURE_COLORS["table"]),
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
                fg, bg = FEATURE_COLORS.get(feature, ("grey50", "grey93"))
                ch = resolve_feature_char(rng, feature, FEATURES_REGISTRY)
                row.append((ch, fg, bg))
        out.append(row)
    return out
