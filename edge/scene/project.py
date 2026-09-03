"""The projection-strategy interface (plan §9.3, §9.5).

Only the typed `Protocol` lands in WP-SC02. Fixed-FOV perspective and
depth-layered anchor projection are implemented and compared behind it in
WP-SC03/WP-SC04; the losing strategy is removed once the calibration gate
approves a winner.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from edge.scene.geometry import CellBox, Vec3
from edge.scene.model import Camera, PhysicalObject, SceneKey, SceneTuning, WorldArrangement


class ProjectionStrategy(Protocol):
    """One camera/projection algorithm, compared under identical inputs."""

    name: str

    def frame(
        self,
        arrangement: WorldArrangement,
        anchor: SceneKey,
        viewport: CellBox,
        cfg: SceneTuning,
    ) -> Camera: ...

    def candidates(
        self,
        camera: Camera,
        anchor: PhysicalObject,
        viewport: CellBox,
        cfg: SceneTuning,
    ) -> Iterator[Camera]: ...

    def project(
        self,
        camera: Camera,
        obj: PhysicalObject,
        at: Vec3,
        viewport: CellBox,
    ) -> CellBox: ...
