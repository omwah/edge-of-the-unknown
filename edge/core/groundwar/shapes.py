"""City silhouettes (GW-WP28, D37): the one predicate the shared survey/assault
layout's footprint-membership test is built on.

`GroundPlace.inside`, `AssaultCity.inside`, and the survey `SurveySettlement` all
delegate to `shape_contains` — one function, three callers is the lockstep
guarantee the world/assault split needs: a survey and an assault of the same
place must never disagree about which cell is inside it.

Every family here is **closed-form and O(1)** — no cell set, no allocation. That
matters because `inside()` runs inside `assault.assault_landing`'s full-grid
sweeps (tens of thousands of cells, up to four cities, twice per generation).

Every family is also **star-shaped around the footprint's own centre** — any ray
from `(cx, cy)` crosses the boundary exactly once. That is a real constraint on
which shapes may be added here, not an incidental property: it is what lets
`groundwar.world.stamp_place` derive an ordered perimeter ring by sorting
boundary cells on angle around the centre rather than tracing a walk, which is
the simplification that keeps ring-based turret sampling simple and always
terminating (see `_ring_perimeter` there).

Pure `edge.core`: no I/O, stdlib only, no game RNG (G2/G5) — deterministic in
its arguments alone.
"""

from __future__ import annotations

from typing import Literal

Vec = tuple[int, int]

PlaceShape = Literal["rect", "chamfered", "ellipse", "stepped"]

# D37: rectangles stay the common case; the other three are variety, not chaos.
# Capitals bias toward `chamfered` (reads as planned and fortified); towns bias
# toward `ellipse`/`stepped` (reads as grown organically). Cross/star was
# considered and declined — a cross has roughly a dozen corners, which makes
# turret placement and the interior street grid fiddly for a shape that ends up
# reading more like a fortress than a city.
CAPITAL_SHAPE_WEIGHTS: tuple[tuple[PlaceShape, float], ...] = (
    ("rect", 0.40), ("chamfered", 0.35), ("ellipse", 0.15), ("stepped", 0.10),
)
TOWN_SHAPE_WEIGHTS: tuple[tuple[PlaceShape, float], ...] = (
    ("rect", 0.40), ("ellipse", 0.25), ("stepped", 0.20), ("chamfered", 0.15),
)


def chamfer_param(width: int, height: int) -> int:
    """The corner-cut size a chamfered footprint of this size should use.

    Derived from the footprint rather than rolled separately — one shape-family
    roll per place is enough entropy; the cut size scaling with size is what
    keeps a chamfered town and a chamfered capital reading as the same *kind*
    of corner, not a bigger or smaller one relative to the building.
    """
    return max(2, min(width, height) // 5)


def stepped_param(corner: int, width: int, height: int) -> int:
    """Pack a stepped (L) footprint's notch corner and depth into one int.

    `corner` (0-3: NW/NE/SW/SE) is the only thing that needs a roll; the notch
    depth is derived from size for the same reason `chamfer_param` derives its
    cut — proportion, not a second independent random choice.
    """
    notch = max(2, min(width, height) // 3)
    return (corner & 0b11) | (notch << 2)


def shape_contains(
    shape: PlaceShape, param: int, x0: int, y0: int, x1: int, y1: int, x: int, y: int,
) -> bool:
    """Whether `(x, y)` lies inside the footprint `(x0, y0)`-`(x1, y1)` cut to `shape`.

    Corners are inclusive, matching every existing bbox `inside()` this replaces.
    `"rect"` is the bounding box itself — every other family cuts cells *out* of
    it, never adds cells outside it, so a shaped footprint is always a subset of
    its own bounding box. That is what keeps the bbox-based math elsewhere
    (camera framing, `assault_landing` clearance, the survey keepout) valid
    without change: a bbox check is a conservative superset test for any shape.
    """
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    if shape == "rect":
        return True
    w, h = x1 - x0 + 1, y1 - y0 + 1
    u, v = x - x0, y - y0
    if shape == "chamfered":
        c = param
        if c <= 0:
            return True
        return not (
            u + v < c
            or (w - 1 - u) + v < c
            or u + (h - 1 - v) < c
            or (w - 1 - u) + (h - 1 - v) < c
        )
    if shape == "ellipse":
        rx, ry = (w - 1) / 2.0, (h - 1) / 2.0
        if rx <= 0 or ry <= 0:
            return True
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        dx, dy = (u - cx) / rx, (v - cy) / ry
        return dx * dx + dy * dy <= 1.0 + 1e-9
    if shape == "stepped":
        corner = param & 0b11
        notch = param >> 2
        if notch <= 0:
            return True
        near_w = u < notch
        near_e = u >= w - notch
        near_n = v < notch
        near_s = v >= h - notch
        if corner == 0:
            return not (near_w and near_n)
        if corner == 1:
            return not (near_e and near_n)
        if corner == 2:
            return not (near_w and near_s)
        return not (near_e and near_s)
    raise ValueError(f"unknown place shape {shape!r}")


def strictly_inside(
    shape: PlaceShape, param: int, x0: int, y0: int, x1: int, y1: int, x: int, y: int,
) -> bool:
    """A cell that is inside the footprint and **not touching its boundary**.

    For a rectangle this is exactly `x0 < x < x1 and y0 < y < y1` — the pre-WP28
    definition `SurveySettlement.inside` already used to exclude the wall ring
    from "standing in town" checks. Generalized here as "inside, and every
    4-neighbour is also inside", which reduces to that rectangle case (bbox
    membership is monotonic in each axis, so a cell one step from any edge always
    has an outside neighbour) and extends correctly to a cut corner or notch,
    whose new edge is exactly where a neighbour test also flips.
    """
    if not shape_contains(shape, param, x0, y0, x1, y1, x, y):
        return False
    return all(
        shape_contains(shape, param, x0, y0, x1, y1, nx, ny)
        for nx, ny in ((x, y - 1), (x, y + 1), (x + 1, y), (x - 1, y))
    )
