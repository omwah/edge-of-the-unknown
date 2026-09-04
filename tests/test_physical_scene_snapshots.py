"""WP-SC09 — isolated UI snapshots for the new-pipeline `PhysicalSectorScene`.

Deliberately NOT wired into `tests/test_ui_snapshots.py`: these snapshots live
behind the dev switch (`edge/tui/scene_gallery.py` defaults to the legacy
composer) and must never share a baseline directory with the shipped legacy
composer's snapshots. pytest-textual-snapshot names a test's snapshot
directory after the test *file*, so this file alone gives every snapshot here
its own `tests/__snapshots__/test_physical_scene_snapshots/` directory —
nothing under `tests/__snapshots__/test_ui_snapshots/` (or any other existing
snapshot directory) is read or written by this file.

Regenerate accepted baselines with `pytest --snapshot-update
tests/test_physical_scene_snapshots.py`.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from edge.art.geometry_catalog import load_geometry_catalog
from edge.art.scene_tuning import build_continuous_yields, build_scene_tuning
from edge.config import load_config
from edge.scene.catalog import LadderKey
from edge.scene.geometry import Face, FaceShape, Region, Vec3
from edge.scene.model import (
    ArtMode,
    PhysicalObject,
    Placement,
    SceneKey,
    SceneRetention,
    WorldArrangement,
)
from edge.scene.project import DepthLayeredAnchorProjection, FixedFovPerspective, ProjectionStrategy
from edge.tui.physical_scene import Fingerprint, PhysicalSectorScene

_CFG = load_config("config/default.yaml")
_PM = _CFG.scene.physical_model
TUNING = build_scene_tuning(_PM)
CATALOG = load_geometry_catalog(build_continuous_yields(_PM))

STRATEGIES: dict[str, ProjectionStrategy] = {
    "fixed_fov_perspective": FixedFovPerspective(),
    "depth_layered_anchor": DepthLayeredAnchorProjection(),
}


def _region() -> Region:
    return Region(x_min=-200, x_max=200, y_min=-100, y_max=100, z_min=1, z_max=300)


def _planet(ident: int) -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("planet", ident), parent=None,
        face=Face(shape=FaceShape.CIRCLE, width_su=60, height_su=30),
        scale_class="anchor", art_mode=ArtMode.CONTINUOUS, ladder_key=None,
        continuous_kind="terrestrial_warm", archetype_id=None,
        retention=SceneRetention.ANCHOR, hostility_ordinal=0, threat_rank=0,
        region=_region(), flexible=False, occludes=True,
        label=f"Planet {ident}", destination="planet",
    )


def _ship(ident: int) -> PhysicalObject:
    return PhysicalObject(
        key=SceneKey("ship", ident), parent=None,
        face=Face(shape=FaceShape.RECT, width_su=40, height_su=10),
        scale_class="ship", art_mode=ArtMode.LADDER,
        ladder_key=LadderKey(kind="ship", subtype="fighter", axis="horizontal",
                              archetype_id="amorous_imp"),
        continuous_kind=None, archetype_id=None,
        retention=SceneRetention.NEUTRAL_SHIP, hostility_ordinal=5, threat_rank=1,
        region=_region(), flexible=True, occludes=True,
        label=f"Ship {ident}", destination="contact",
    )


def _arrangement(sector_id: int = 21, n_ships: int = 3) -> WorldArrangement:
    objects = (_planet(1),) + tuple(_ship(i) for i in range(n_ships))
    placements = tuple(
        Placement(key=o.key, position=Vec3(i * 5, 0, 50 + i))
        for i, o in enumerate(objects)
    )
    return WorldArrangement(objects=objects, placements=placements, sector_id=sector_id)


def _fp(sector_id: int) -> Fingerprint:
    return Fingerprint(sector_id=sector_id, scene_labels="labeled", art_detail="full",
                       catalogue_version="test")


class _Harness(App[None]):
    def __init__(self, strategy: ProjectionStrategy) -> None:
        super().__init__()
        self._strategy = strategy
        self.scene: PhysicalSectorScene | None = None

    def compose(self) -> ComposeResult:
        arrangement = _arrangement()
        self.scene = PhysicalSectorScene(
            arrangement, TUNING, CATALOG, self._strategy,
            fingerprint=_fp(arrangement.sector_id),
        )
        yield self.scene


@pytest.mark.parametrize("strategy_name", sorted(STRATEGIES))
def test_physical_scene_snapshot(snap_compare, strategy_name: str) -> None:
    """WP-SC09: a first, isolated human-reviewed diff for each new-pipeline
    strategy — never touches the shipped legacy-composer baseline."""

    assert snap_compare(_Harness(STRATEGIES[strategy_name]), terminal_size=(100, 34))
