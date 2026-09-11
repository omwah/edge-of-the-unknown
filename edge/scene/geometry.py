"""Units and camera-facing shapes shared by the catalogue, model, and solver.

Definitions and units: `docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §9.1. All
positions, radii, depths, and face extents are integers in scene units (su);
there is no world-space float. The su-to-cell relationship is established
only by projection (WP-SC03), so `Su` has no fixed cell size here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

type Su = int
"""The integer unit of the world arrangement."""


class FaceShape(StrEnum):
    """The camera-facing billboard shape of one physical object (plan §2.5)."""

    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    RECT = "rect"
    FIELD = "field"


@dataclass(frozen=True, slots=True)
class Face:
    """A camera-facing billboard's nominal shape and extent, in scene units.

    Nominal face area supplies physical scale (plan §2.5); it is never a
    measure of rendered ink.
    """

    shape: FaceShape
    width_su: Su
    height_su: Su

    @property
    def area_su(self) -> int:
        """`width_su * height_su`, exact — including for circles and ellipses.

        Bounding-box area rather than the shape's own true area (e.g. `pi * a
        * b` for an ellipse) keeps the scale-class comparison exact and
        changes no ordering, because a class's shape is fixed per kind
        (plan §9.1).
        """
        return self.width_su * self.height_su


@dataclass(frozen=True, slots=True)
class Vec3:
    """A point or offset in scene units. `+x` right, `+y` up, `+z` away from
    the viewer (plan §9.2)."""

    x: Su
    y: Su
    z: Su


@dataclass(frozen=True, slots=True)
class Region:
    """The scene-unit box an object may be moved within, and the depths it
    may take (plan §9.3)."""

    x_min: Su
    x_max: Su
    y_min: Su
    y_max: Su
    z_min: Su
    z_max: Su


@dataclass(frozen=True, slots=True)
class CellBox:
    """An integer terminal-cell rectangle; the unit of quantised output.

    Used both as a request/container box (`col`/`row` meaningful) and, in the
    geometry catalogue, as a bare `(width, height)` pair with `col`/`row`
    conventionally `0`.
    """

    col: int
    row: int
    width: int
    height: int
