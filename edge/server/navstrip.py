"""The main-screen nav rose — a bearing-placed compass of immediate warps (§11).

Bakes the always-visible navigation affordance that *replaces* the flat warp list:
a compact "open diagonals" compass with the player (`@`) centred, each outbound
warp placed in the octant matching its real `bearing` (from the seeded spatial
embedding, DESIGN §5.1), a fixed `Core` anchor on the frame edge in the
`core_bearing` direction (global orientation), and a recent-route breadcrumb. The
output is baked Rich-markup rows the TUI renders verbatim, plus clickable/focusable
`MapNodeDTO` cell boxes reusing the local-map contract.

Pure and I/O-free — a function of the projected `SectorDTO` only — so it is fully
unit-testable and reconstructs identically under `(seed, command log)`. When the
sector carries no embedding (hand-built/test states: every `bearing` is `0.0`), it
degrades to the `core_hops` gravity axis using each warp's `<<`/`>>`/`--` arrow.
"""

from __future__ import annotations

import math

from edge.core import dto
from edge.server.canvas import BAND_COLOR, HERE_STYLE, Canvas

_CORE_ANCHOR_STYLE = "bold cyan"
_VOID_ANCHOR_STYLE = "bold blue"
_UNEXPLORED_STYLE = "dim"
_SPOKE_STYLE = "dim"
_GAP = 4  # blank columns between a label column and the centre block (room for spokes)

# Octant index (round(bearing / 45°) mod 8) → (canvas row, column side).
# 0 E, 1 NE, 2 N, 3 NW, 4 W, 5 SW, 6 S, 7 SE — a clean 8-slot ring around `@`.
_SLOT: dict[int, tuple[int, str]] = {
    0: (2, "R"), 1: (0, "R"), 2: (0, "C"), 3: (0, "L"),
    4: (2, "L"), 5: (4, "L"), 6: (4, "C"), 7: (4, "R"),
}
_ROWS = 5
_HERE = "[ @ ]"

_ARROW_OCTANT = {"<<": 4, ">>": 0, "--": 2}  # gravity-axis fallback: coreward W, deeper E, level N

NAV_LEGEND = ""


def _octant(bearing: float) -> int:
    """Snap a bearing (radians, 0 = east, +y = north) to one of 8 compass octants."""
    return round(bearing / (math.pi / 4.0)) % 8


def _nearest_free(pref: int, used: set[int]) -> int:
    """The preferred octant, or the closest free one (deterministic +d before -d)."""
    order = [pref]
    for d in range(1, 5):
        order += [(pref + d) % 8, (pref - d) % 8]
    for octant in order:
        if octant not in used:
            return octant
    return pref  # all 8 taken — impossible with the ≤6 warp cap, but stay total


def _warp_label(warp: dto.WarpDTO) -> str:
    """The cell text: spatial id plus content codes once charted (fog masks codes)."""
    text = str(warp.display_id)
    if warp.codes:
        text += " " + "".join(warp.codes)
    return text


def _warp_style(warp: dto.WarpDTO) -> str | None:
    """Band tint for a charted warp; dim for an uncharted one (matches the local map)."""
    if not warp.explored:
        return _UNEXPLORED_STYLE
    return BAND_COLOR.get(warp.band)


def build_nav_strip(
    sector: dto.SectorDTO, *, core_anchor_side: str = "left"
) -> dto.NavStripDTO:
    """Bake the nav rose for `sector` — the sole main-screen warp affordance (§11).

    `core_anchor_side` (`"left"`/`"right"`, from `ui.nav_core_anchor_side`) pins the
    `Core` orientation anchor to a **fixed** frame edge, so it never jumps sides between
    sectors and always faces the same way. Warps are rotated so they align relative to
    the fixed Core anchor (Core is placed in the direction of the anchor).
    """
    warps = sector.warps
    has_embed = sector.core_bearing != 0.0 or any(w.bearing != 0.0 for w in warps)

    # If we have embedding, align the Coreward direction with the Core anchor.
    # To preserve the vertical axis (preventing top/bottom from flipping), we use
    # a horizontal reflection if the Core bearing faces the opposite horizontal side
    # of the configured anchor, rather than a full 2D rotation.
    reflect_horizontal = False
    if has_embed:
        anchor_left = core_anchor_side != "right"
        core_left = math.cos(sector.core_bearing) < 0.0
        if anchor_left != core_left:
            reflect_horizontal = True

    def _rot_bearing(w: dto.WarpDTO) -> float:
        if not has_embed:
            return 0.0
        if reflect_horizontal:
            return (math.pi - w.bearing) % (2.0 * math.pi)
        return w.bearing

    # Assign each warp an octant (bearing when embedded, else the gravity arrow),
    # spilling collisions to the nearest free slot so no two labels overlap.
    used: set[int] = set()
    placed: dict[int, dto.WarpDTO] = {}  # octant → warp
    for warp in sorted(warps, key=lambda w: (_octant(_rot_bearing(w)) if has_embed
                                             else _ARROW_OCTANT.get(w.arrow, 0), w.display_id)):
        pref = _octant(_rot_bearing(warp)) if has_embed else _ARROW_OCTANT.get(warp.arrow, 0)
        octant = _nearest_free(pref, used)
        used.add(octant)
        placed[octant] = warp

    labels = {o: _warp_label(w) for o, w in placed.items()}
    left_w = max((len(labels[o]) for o in placed if _SLOT[o][1] == "L"), default=0)
    right_w = max((len(labels[o]) for o in placed if _SLOT[o][1] == "R"), default=0)
    center_w = max([len(_HERE)] + [len(labels[o]) for o in placed if _SLOT[o][1] == "C"])

    # Orient the opposite Core and Void anchors to fixed frame edges (config, not bearing)
    # so they never jump sides between sectors.
    anchor_left = core_anchor_side != "right"
    left_anchor_text = "◄ Core" if anchor_left else "◄ Void"
    right_anchor_text = "Void ►" if anchor_left else "Core ►"
    left_margin = len(left_anchor_text) + 3
    right_margin = len(right_anchor_text) + 3

    x_left0 = left_margin
    x_center0 = x_left0 + left_w + _GAP
    x_right0 = x_center0 + center_w + _GAP
    width = x_right0 + right_w + right_margin

    canvas = Canvas(width, _ROWS)
    nodes: list[dto.MapNodeDTO] = []

    # `@` dead-centre, its glyph reverse-highlighted like the local map.
    here_x = x_center0 + (center_w - len(_HERE)) // 2
    canvas.put(2, here_x, _HERE)
    canvas.put(2, here_x + 2, "@", HERE_STYLE)

    def col_for(side: str, text: str) -> int:
        if side == "L":  # right-aligned toward the centre block
            return x_left0 + (left_w - len(text))
        if side == "R":  # left-aligned away from the centre block
            return x_right0
        return x_center0 + (center_w - len(text)) // 2  # centred

    for octant, warp in placed.items():
        row, side = _SLOT[octant]
        text = labels[octant]
        x = col_for(side, text)
        canvas.put(row, x, text, _warp_style(warp))
        nodes.append(dto.MapNodeDTO(
            sector_id=warp.sector_id, display_id=warp.display_id,
            row=row, col0=x, col1=x + len(text),
        ))

    # Diagonal spokes only where a corner slot is occupied (the "open diagonals" look).
    spoke_lx, spoke_rx = x_center0 - 2, x_center0 + center_w + 1
    if 3 in placed:  # NW
        canvas.put(1, spoke_lx, "╲", _SPOKE_STYLE)
    if 1 in placed:  # NE
        canvas.put(1, spoke_rx, "╱", _SPOKE_STYLE)
    if 5 in placed:  # SW
        canvas.put(3, spoke_lx, "╱", _SPOKE_STYLE)
    if 7 in placed:  # SE
        canvas.put(3, spoke_rx, "╲", _SPOKE_STYLE)

    canvas.put(2, 0, left_anchor_text, _CORE_ANCHOR_STYLE if anchor_left else _VOID_ANCHOR_STYLE)
    canvas.put(2, width - len(right_anchor_text), right_anchor_text,
               _VOID_ANCHOR_STYLE if anchor_left else _CORE_ANCHOR_STYLE)

    return dto.NavStripDTO(
        rows=canvas.rows(), legend=NAV_LEGEND, you_display=sector.display_id,
        core_bearing=sector.core_bearing, nodes=nodes, trail=list(sector.trail),
    )
