"""The constraint-solver entry point (plan §9.3, §9.6).

Only the typed signature lands in WP-SC02, to fix the contract the strategies
(WP-SC03) and the bounded search (WP-SC06) are built against. The algorithm
itself — candidate generation, the pass loop, hard-rule checks, hysteresis —
is out of scope here and raises `NotImplementedError` until WP-SC06 lands it.
"""

from __future__ import annotations

from edge.scene.catalog import ArtGeometryCatalog
from edge.scene.geometry import CellBox
from edge.scene.model import SceneTuning, ScenePlan, WorldArrangement
from edge.scene.project import ProjectionStrategy


def solve(
    arrangement: WorldArrangement,
    viewport: CellBox,
    cfg: SceneTuning,
    catalog: ArtGeometryCatalog,
    strategy: ProjectionStrategy,
    previous: ScenePlan | None = None,
    *,
    trace_prose: bool = False,
) -> ScenePlan:
    raise NotImplementedError("the solver lands in WP-SC06")
