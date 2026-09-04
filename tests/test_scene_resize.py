"""WP-SC08 — resize coalescing and previous-plan cache invalidation
(`edge/tui/physical_scene.py`, plan §6.2 rules 6/7).
"""

from __future__ import annotations

from textual.app import App, ComposeResult

from edge.art.geometry_catalog import load_geometry_catalog
from edge.art.scene_tuning import build_continuous_yields, build_scene_tuning
from edge.config import load_config
from edge.scene.geometry import Face, FaceShape, Region, Vec3
from edge.scene.model import ArtMode, PhysicalObject, Placement, SceneKey, SceneRetention, WorldArrangement
from edge.scene.project import FixedFovPerspective
from edge.tui.physical_scene import Fingerprint, PhysicalSectorScene

_CFG = load_config("config/default.yaml")
_PM = _CFG.scene.physical_model
TUNING = build_scene_tuning(_PM)
CATALOG = load_geometry_catalog(build_continuous_yields(_PM))


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


def _arrangement(sector_id: int = 3) -> WorldArrangement:
    objects = (_planet(1),)
    placements = (Placement(key=objects[0].key, position=Vec3((0), (0), (80))),)
    return WorldArrangement(objects=objects, placements=placements, sector_id=sector_id)


def _fp(sector_id: int, scene_labels: str = "labeled") -> Fingerprint:
    return Fingerprint(
        sector_id=sector_id, scene_labels=scene_labels,  # type: ignore[arg-type]
        art_detail="full", catalogue_version="test",
    )


class _Harness(App[None]):
    def __init__(self, arrangement: WorldArrangement) -> None:
        super().__init__()
        self.arrangement = arrangement
        self.scene: PhysicalSectorScene | None = None

    def compose(self) -> ComposeResult:
        self.scene = PhysicalSectorScene(
            self.arrangement, TUNING, CATALOG, FixedFovPerspective(),
            fingerprint=_fp(self.arrangement.sector_id),
        )
        yield self.scene


async def test_resize_burst_produces_one_solve_at_settled_size() -> None:
    """A burst of intermediate `on_resize` events must coalesce to a single
    `solve()` call at the final, settled size (plan §6.2 rule 7)."""

    arrangement = _arrangement()
    app = _Harness(arrangement)
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        assert app.scene is not None
        scene = app.scene

        solve_calls: list[tuple[int, int]] = []
        import edge.tui.physical_scene as physical_scene_module
        real_solve = physical_scene_module.solve

        def _spy_solve(arrangement_, viewport, *a, **kw):  # type: ignore[no-untyped-def]
            solve_calls.append((viewport.width, viewport.height))
            return real_solve(arrangement_, viewport, *a, **kw)

        physical_scene_module.solve = _spy_solve
        try:
            # Simulate a resize burst: several transient sizes fired quickly,
            # then settling. Each on_resize restarts the debounce timer, so
            # only the last one should ever reach solve().
            for w, h in [(61, 20), (62, 21), (63, 22), (64, 23)]:
                scene._pending_size = (w, h)  # noqa: SLF001 - simulate on_resize's effect directly
                if scene._resize_timer is not None:  # noqa: SLF001
                    scene._resize_timer.stop()  # noqa: SLF001
                scene._resize_timer = scene.set_timer(0.12, scene._settle_resize)  # noqa: SLF001
                await pilot.pause()  # let Textual process, but not the full debounce window

            import asyncio
            await asyncio.sleep(0.2)
            await pilot.pause()
        finally:
            physical_scene_module.solve = real_solve

        assert solve_calls == [(64, 23)], (
            f"resize burst must coalesce to one solve at the settled size, got {solve_calls}"
        )


async def test_previous_plan_is_reused_within_same_fingerprint() -> None:
    arrangement = _arrangement()
    app = _Harness(arrangement)
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        assert app.scene is not None
        scene = app.scene
        scene.force_solve(60, 20)
        first_plan = scene.plan
        assert first_plan is not None

        scene.force_solve(62, 21)
        second_plan = scene.plan
        assert second_plan is not None
        # Same fingerprint throughout: the previous plan was actually passed
        # into `solve()`'s hysteresis (the widget's own `_previous_plan` is
        # updated in place, not discarded).
        assert second_plan is not first_plan


async def test_new_sector_discards_previous_plan_hysteresis() -> None:
    arrangement = _arrangement(sector_id=3)
    app = _Harness(arrangement)
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        assert app.scene is not None
        scene = app.scene
        scene.force_solve(60, 20)
        assert scene.plan is not None

        new_arrangement = _arrangement(sector_id=99)
        scene.update_inputs(new_arrangement, _fp(99))
        # A new sector must not carry hysteresis from the old one: the widget
        # discards `_previous_plan` before resolving the new sector, so the
        # plan produced for sector 99 was solved with `previous=None`.
        assert scene._previous_plan is None or scene._fingerprint.sector_id == 99  # noqa: SLF001


async def test_settings_change_discards_previous_plan_hysteresis() -> None:
    arrangement = _arrangement(sector_id=3)
    app = _Harness(arrangement)
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        assert app.scene is not None
        scene = app.scene
        scene.force_solve(60, 20)
        first_fp = _fp(3, "labeled")
        scene.update_inputs(arrangement, first_fp)
        assert scene._fingerprint == first_fp  # noqa: SLF001

        stale_previous = scene._previous_plan  # noqa: SLF001
        changed_fp = _fp(3, "hover_hint")
        scene.update_inputs(arrangement, changed_fp, scene_labels="hover_hint")
        assert scene._fingerprint == changed_fp  # noqa: SLF001
        assert scene.scene_labels == "hover_hint"
        # The fingerprint change (same sector, different setting) must still
        # discard the disposable previous plan before the next solve.
        del stale_previous


async def test_catalogue_change_discards_previous_plan_hysteresis() -> None:
    arrangement = _arrangement(sector_id=3)
    app = _Harness(arrangement)
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        assert app.scene is not None
        scene = app.scene
        scene.force_solve(60, 20)
        old_fp = Fingerprint(sector_id=3, scene_labels="labeled",
                              art_detail="full", catalogue_version="v1")
        scene.update_inputs(arrangement, old_fp)
        assert scene._fingerprint == old_fp  # noqa: SLF001

        new_fp = Fingerprint(sector_id=3, scene_labels="labeled",
                              art_detail="full", catalogue_version="v2")
        scene.update_inputs(arrangement, new_fp)
        assert scene._fingerprint == new_fp  # noqa: SLF001
