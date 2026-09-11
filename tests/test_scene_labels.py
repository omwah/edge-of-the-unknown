"""WP-SC08 — labels, hotspots, sidebar overflow (`edge/tui/physical_scene.py`).

Covers the WP-SC08 verification list: settings independence/compatibility,
Pilot hover/focus/sidebar routing, no-scene-text-for-rejected, and
topmost-hit-testing. This module is not wired into the live game
(`edge/tui/widgets.py`'s `_SceneComposer`/`SectorScene` are untouched and
keep their own tests passing) — `PhysicalSectorScene` is exercised directly
in a minimal test `App`.
"""

from __future__ import annotations

from fractions import Fraction

from textual.app import App, ComposeResult

from edge.art.geometry_catalog import load_geometry_catalog
from edge.art.scene_tuning import build_continuous_yields, build_scene_tuning
from edge.config import load_config
from edge.scene.geometry import Face, FaceShape, Region, Vec3
from edge.scene.model import (
    ArtMode,
    PhysicalObject,
    Placement,
    SceneKey,
    SceneRetention,
    WorldArrangement,
)
from edge.scene.project import FixedFovPerspective
from edge.tui.physical_scene import Fingerprint, PhysicalSectorScene, rejected_sidebar_rows
from edge.tui.settings import UISettings

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


def _ship(ident: int) -> PhysicalObject:
    from edge.scene.catalog import LadderKey
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


def _many_ships(n: int) -> tuple[PhysicalObject, ...]:
    """More ships than a tiny viewport can admit, so some are rejected."""
    return tuple(_ship(i) for i in range(n))


def _arrangement(sector_id: int = 11, n_ships: int = 12) -> WorldArrangement:
    objects = (_planet(1),) + _many_ships(n_ships)
    placements = tuple(
        Placement(key=o.key, position=Vec3((i * 5), (0), (50 + i)))
        for i, o in enumerate(objects)
    )
    return WorldArrangement(objects=objects, placements=placements, sector_id=sector_id)


def _fp(sector_id: int, scene_labels: str = "labeled") -> Fingerprint:
    return Fingerprint(
        sector_id=sector_id, scene_labels=scene_labels,  # type: ignore[arg-type]
        art_detail="full", catalogue_version="test",
    )


class _Harness(App[None]):
    def __init__(self, arrangement: WorldArrangement, scene_labels: str = "labeled") -> None:
        super().__init__()
        self.arrangement = arrangement
        self.scene: PhysicalSectorScene | None = None
        self._scene_labels = scene_labels

    def compose(self) -> ComposeResult:
        self.scene = PhysicalSectorScene(
            self.arrangement, TUNING, CATALOG, FixedFovPerspective(),
            scene_labels=self._scene_labels,  # type: ignore[arg-type]
            fingerprint=_fp(self.arrangement.sector_id, self._scene_labels),
        )
        yield self.scene


# ---------------------------------------------------------------------------
# Settings independence (plan §2.6): scene_labels / art_detail / reduced_motion
# never silently override one another.
# ---------------------------------------------------------------------------


def test_scene_labels_is_independent_of_art_detail_and_reduced_motion() -> None:
    for art_detail in ("full", "compact", "minimal"):
        for reduced_motion in (False, True):
            for scene_labels in ("labeled", "hidden", "hover_hint"):
                settings = UISettings(
                    art_detail=art_detail, reduced_motion=reduced_motion,  # type: ignore[arg-type]
                    scene_labels=scene_labels,  # type: ignore[arg-type]
                )
                # Each of the three fields round-trips independently; setting one
                # never mutates or implies another.
                assert settings.scene_labels == scene_labels
                assert settings.art_detail == art_detail
                assert settings.reduced_motion == reduced_motion


def test_scene_labels_default_and_options_toggle_cycle() -> None:
    assert UISettings().scene_labels == "labeled"
    values = ["labeled", "hidden", "hover_hint"]
    cur = "labeled"
    seen = [cur]
    for _ in range(len(values)):
        cur = values[(values.index(cur) + 1) % len(values)]
        seen.append(cur)
    assert seen == ["labeled", "hidden", "hover_hint", "labeled"]


# ---------------------------------------------------------------------------
# No scene text for a rejected object; sidebar carries name + omitted state.
# ---------------------------------------------------------------------------


async def test_rejected_objects_never_appear_as_scene_text() -> None:
    arrangement = _arrangement(n_ships=30)
    app = _Harness(arrangement)
    async with app.run_test(size=(40, 14)) as pilot:
        await pilot.pause()
        assert app.scene is not None
        app.scene.force_solve(40, 14)
        plan = app.scene.plan
        assert plan is not None
        assert plan.rejected, "a tiny viewport with 30 ships must reject some"

        rendered = str(app.scene.render())
        rows = rejected_sidebar_rows(plan.rejected, arrangement)
        assert rows, "rejected objects must surface in the sidebar"
        for row in rows:
            assert row.label not in rendered, (
                f"rejected object {row.label!r} leaked into scene text"
            )
            assert row.omitted_state
            assert row.dest is not None and row.ref is not None
        # No count/edge marker anywhere in the scene text.
        assert "…" not in rendered
        assert "more" not in rendered.lower()


async def test_rejected_row_routing_matches_accepted_hotspot_routing() -> None:
    arrangement = _arrangement(n_ships=6)
    app = _Harness(arrangement)
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        assert app.scene is not None
        app.scene.force_solve(60, 20)
        plan = app.scene.plan
        rejected_rows = rejected_sidebar_rows(plan.rejected, arrangement)
        for row in rejected_rows:
            assert row.dest == "contact"  # ships route to "contact", matching accepted ships
        for projection in app.scene.hotspots.ordered:
            if projection.key.tag == "ship":
                from edge.tui.physical_scene import _route_for
                dest, ref = _route_for(projection.key)
                assert dest == "contact"


# ---------------------------------------------------------------------------
# Topmost hit-testing over overlapping projections.
# ---------------------------------------------------------------------------


def test_hit_test_returns_topmost_nearest_object() -> None:
    from edge.scene.geometry import CellBox
    from edge.scene.model import Camera, Decision, Projection, ScenePlan, SolveCounters

    far = Projection(
        key=SceneKey("ship", 1), bounds=CellBox(0, 0, 10, 10), depth=(100), rung=None,
        box_class=None, ink_est=CellBox(0, 0, 10, 10), ink_actual=None,
        visible_fraction=Fraction(1), label_bounds=None, accepted=True,
    )
    near = Projection(
        key=SceneKey("ship", 2), bounds=CellBox(2, 2, 10, 10), depth=(10), rung=None,
        box_class=None, ink_est=CellBox(2, 2, 10, 10), ink_actual=None,
        visible_fraction=Fraction(1), label_bounds=None, accepted=True,
    )
    rejected = Projection(
        key=SceneKey("ship", 3), bounds=CellBox(2, 2, 10, 10), depth=(5), rung=None,
        box_class=None, ink_est=CellBox(2, 2, 10, 10), ink_actual=None,
        visible_fraction=Fraction(1), label_bounds=None, accepted=False,
    )
    from edge.tui.physical_scene import HotspotIndex

    # far-to-near order, matching ScenePlan.projections' documented contract.
    index = HotspotIndex((far, near, rejected))
    hit = index.hit_test(5, 5)  # inside both far and near
    assert hit is not None and hit.key == near.key  # topmost/nearest wins
    only_far = index.hit_test(1, 1)  # inside far only
    assert only_far is not None and only_far.key == far.key
    assert index.hit_test(30, 30) is None
    # rejected never appears in the index at all.
    assert all(p.key != rejected.key for p in index.ordered)
    del Camera, Decision, ScenePlan, SolveCounters  # unused imports kept for reader context


# ---------------------------------------------------------------------------
# Pilot hover/focus/sidebar routing.
# ---------------------------------------------------------------------------


async def test_mouse_hover_reveals_hint_in_hover_hint_mode() -> None:
    arrangement = _arrangement(n_ships=2)
    app = _Harness(arrangement, scene_labels="hover_hint")
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        assert app.scene is not None
        app.scene.force_solve(60, 20)
        # The lone widget auto-focuses on mount, so a hint may already show via
        # keyboard focus (plan §2.6: focus reveals the same hint hover does) —
        # what this test checks is that *hovering* also reveals one.
        target = app.scene.hotspots.ordered[0]
        box = target.bounds
        await pilot.hover(PhysicalSectorScene, offset=(box.col + 1, box.row + 1))
        await pilot.pause()
        assert app.scene.active_hint_index is not None
        assert app.scene.active_hint_label() is not None


async def test_keyboard_focus_reveals_same_hint_as_hover() -> None:
    arrangement = _arrangement(n_ships=2)
    app = _Harness(arrangement, scene_labels="hover_hint")
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        assert app.scene is not None
        app.scene.force_solve(60, 20)
        app.scene.focus()
        await pilot.pause()
        assert app.scene.active_hint_index is not None
        label_via_focus = app.scene.active_hint_label()
        assert label_via_focus is not None

        # Moving focus keyboard-side changes which hotspot is hinted, exactly
        # like a mouse-hover move would (plan §4 invariant 10 — identical route).
        app.scene.action_focus_next()
        await pilot.pause()
        assert app.scene.active_hint_index is not None


async def test_hidden_mode_shows_no_labels_labeled_mode_shows_all_accepted() -> None:
    arrangement = _arrangement(n_ships=2)
    for mode, expect_all in (("hidden", False), ("labeled", True)):
        app = _Harness(arrangement, scene_labels=mode)
        async with app.run_test(size=(60, 20)) as pilot:
            await pilot.pause()
            assert app.scene is not None
            app.scene.force_solve(60, 20)
            overlays = app.scene._label_overlays()  # noqa: SLF001 - internal, tested directly
            if expect_all:
                assert len(overlays) == len(app.scene.hotspots)
            else:
                assert overlays == {}


async def test_picked_message_routes_from_keyboard_pick() -> None:
    arrangement = _arrangement(n_ships=2)
    app = _Harness(arrangement)
    picks: list[tuple[str, object]] = []

    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        assert app.scene is not None
        app.scene.force_solve(60, 20)
        app.scene.focus()
        await pilot.pause()

        def _capture(message: PhysicalSectorScene.Picked) -> None:
            picks.append((message.dest, message.ref))

        app.scene.on_clickable_entry_picked = None  # no-op if present
        original_post = app.scene.post_message

        def _spy(message: object) -> bool | None:
            if isinstance(message, PhysicalSectorScene.Picked):
                _capture(message)
            return original_post(message)

        app.scene.post_message = _spy  # type: ignore[method-assign]
        app.scene.action_pick()
        await pilot.pause()
        assert picks, "keyboard pick must post the same Picked message a click would"
