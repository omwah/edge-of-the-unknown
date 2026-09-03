"""Pure, presentation-only physical scene model (`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md`).

This package holds the deterministic geometry catalogue types, the immutable
scene model, the projection-strategy interface, and the constraint-solver
entry point that together replace the direct paint-as-you-decide
`_SceneComposer`. It is a strict layer: no I/O, no async, no Textual/Rich
imports, no game-state mutation, and no game RNG. Everything numeric it needs
is injected by the caller (the art/TUI seam) as plain immutable records — this
package never reads a config file or an asset from disk.

Module layout (construction brief: plan §9.3; field names there are binding,
this layout is not):

- `geometry.py` — units and shapes (`Su`, `Face`, `Vec3`, `Region`, `CellBox`).
- `catalog.py` — the injected `ArtGeometryCatalog` protocol and its plain
  ladder/continuous records.
- `model.py` — the immutable scene model (`PhysicalObject`, `WorldArrangement`,
  `Camera`, `Projection`, `Decision`, `ScenePlan`, ...) and the as-yet-unpopulated
  `SceneTuning` bundle (WP-SC05 gives it fields; WP-SC02 only defines it exists).
- `project.py` — the `ProjectionStrategy` protocol (implementations land in
  WP-SC03).
- `solve.py` — the solver entry point (the algorithm lands in WP-SC06).

Where this package and `docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md` §4 disagree,
§4 wins.
"""

from __future__ import annotations
