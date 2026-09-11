"""WP-SC08 — labels, hotspots, sidebar overflow, and resize integration for the
`ScenePlan`-based physical scene (`docs/SECTOR_SCENE_PHYSICAL_MODEL_PLAN.md`).

This module is the ONE place a `ScenePlan`/`ScenePaint` is turned into an
interactive Textual widget. It is deliberately not wired into the live game —
`SectorView`/`SectorScene` (`edge/tui/widgets.py`) keep driving real play
through the legacy `_SceneComposer` until WP-SC09 flips a dev/config switch
and WP-SC10 migrates consumers. `PhysicalSectorScene` here exists so that
work can be built, tested, and reviewed in isolation now.

Plan invariants this module is responsible for:

* §2.6 — the independent `UISettings.scene_labels` preference (`labeled` /
  `hidden` / `hover_hint`), never coupled to `art_detail` or `reduced_motion`.
* §4 invariant 9 — a rejected object never becomes scene text or an edge/count
  marker; `rejected_sidebar_rows()` is the single source both `StatusSidebar`-
  adjacent UI and `SectorObjectList`/`StatusDrawerScreen` can read from.
* §4 invariant 10 — every accepted hotspot has the same keyboard/list route as
  its mouse hotspot, including hover-hint focus.
* §6.2 rule 6/7 — a previous plan is only reused when the presentation
  fingerprint still matches, and a resize burst is coalesced to one solve at
  the settled size.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import Static

from edge.art.geometry_catalog import ArtGeometryCatalog
from edge.art.scene_paint import ScenePaint, paint_grid, resolve_scene
from edge.scene.geometry import CellBox
from edge.scene.model import Projection, SceneKey, SceneTuning, WorldArrangement
from edge.scene.project import ProjectionStrategy
from edge.scene.solve import solve

SceneLabelMode = Literal["labeled", "hidden", "hover_hint"]

# How long a settled resize must be quiet before it triggers a solve (§6.2
# rule 7). Textual reports every intermediate size during a drag; only the
# last one in a burst should ever reach `solve()`.
_RESIZE_DEBOUNCE_SECONDS = 0.12


@dataclass(frozen=True, slots=True)
class Fingerprint:
    """The presentation identity a cached `ScenePlan` must still match (plan
    §6.2 rule 6, scoped to what this widget owns): sector, the scene-relevant
    UI settings, and the catalogue version. A mismatch on any of these
    discards the previous plan rather than feeding it into `solve()`'s
    hysteresis — carrying stale hysteresis across an unrelated scene would
    fight the new one rather than merely smooth it (plan §9.6/§2.6)."""

    sector_id: int
    scene_labels: SceneLabelMode
    art_detail: str
    catalogue_version: str


@dataclass(frozen=True, slots=True)
class SidebarRow:
    """One row `StatusSidebar`/`SectorObjectList`/`StatusDrawerScreen` can
    render for an object the scene did not paint (plan §4 invariant 9): its
    name plus why it was left out, never scene text and never a bare count."""

    label: str
    omitted_state: str
    dest: str | None
    ref: int | str | None


def rejected_sidebar_rows(
    plan_rejected: tuple[SceneKey, ...],
    arrangement: WorldArrangement,
) -> tuple[SidebarRow, ...]:
    """Build the sidebar/object-list rows for every rejected `SceneKey`.

    Each row carries the object's fog-safe `PhysicalObject.label` and an
    explicit omitted-state string ("not shown — no room in the scene") —
    never scene text, never an edge/count marker (plan §4 invariant 9). The
    same `(dest, ref)` a hotspot would have posted is carried through
    (`SceneKey.tag`/`ident`), so routing stays identical whether an object
    ends up painted or not.
    """

    by_key = {o.key: o for o in arrangement.objects}
    rows: list[SidebarRow] = []
    for key in plan_rejected:
        obj = by_key.get(key)
        if obj is None:
            continue
        dest, ref = _route_for(key)
        rows.append(SidebarRow(
            label=obj.label, omitted_state="not shown — no room in the scene",
            dest=dest, ref=ref,
        ))
    return tuple(rows)


def _route_for(key: SceneKey) -> tuple[str | None, int | str | None]:
    """The `ClickableEntry.Picked`-style `(dest, ref)` for one `SceneKey`,
    matching the tags `edge/scene/classify.py` produces. Kept local to this
    module: it is presentation routing, not a scene invariant."""

    tag_to_dest = {
        "ship": "contact", "player": "player", "planet": "planet", "port": "port",
        "starbase": "starbase", "discovery": "discovery", "wreck": "discovery",
        "entity": "contact", "belt": "planet",
    }
    dest = tag_to_dest.get(key.tag)
    if dest is None:
        return None, None
    return dest, key.ident


class HotspotIndex:
    """Hotspots built ONLY from a `ScenePlan`'s accepted `Projection`s (plan
    §4 invariant 10, WP-SC08 bullet 3) — never from ad hoc rectangle
    tracking. `ScenePlan.projections` is already depth-ordered far to near
    (`edge/scene/model.py`), so the *last* entry covering a cell is the
    topmost/nearest one; `hit_test` walks the list in reverse for exactly
    that reason.
    """

    def __init__(self, projections: tuple[Projection, ...]) -> None:
        # Keep only accepted projections, in their given far-to-near order.
        self.ordered: tuple[Projection, ...] = tuple(p for p in projections if p.accepted)

    def hit_test(self, x: int, y: int) -> Projection | None:
        for projection in reversed(self.ordered):
            box = projection.bounds
            if box.col <= x < box.col + box.width and box.row <= y < box.row + box.height:
                return projection
        return None

    def __len__(self) -> int:
        return len(self.ordered)

    def __getitem__(self, index: int) -> Projection:
        return self.ordered[index]


class PhysicalSectorScene(Static, can_focus=True):
    """A `ScenePlan`-driven alternative to `SectorScene` (WP-SC08).

    Not used by any live consumer yet (WP-SC09/SC10). Renders `arrangement`
    through `edge.scene.solve.solve()` + `edge.art.scene_paint`, and adds the
    interaction layer the legacy composer's ad hoc rectangle tracking never
    had: mouse-hover and keyboard-focus hover hints, hit-testing restricted to
    accepted projections (topmost wins), and coalesced resize solves that
    reuse the previous plan for hysteresis only when the presentation
    fingerprint still matches.
    """

    DEFAULT_CSS = """
    PhysicalSectorScene { width: 1fr; height: 1fr; background: transparent; }
    PhysicalSectorScene:focus { background: transparent; }
    """

    BINDINGS = [
        Binding("right", "focus_next", "Next object", show=False),
        Binding("down", "focus_next", "Next object", show=False),
        Binding("left", "focus_previous", "Previous object", show=False),
        Binding("up", "focus_previous", "Previous object", show=False),
        Binding("enter", "pick", "Open", show=False),
        Binding("space", "pick", "Open", show=False),
    ]

    class Picked(Message):
        def __init__(self, dest: str, ref: int | str | None = None) -> None:
            self.dest = dest
            self.ref = ref
            super().__init__()

    def __init__(
        self,
        arrangement: WorldArrangement,
        tuning: SceneTuning,
        catalog: ArtGeometryCatalog,
        strategy: ProjectionStrategy,
        *,
        scene_labels: SceneLabelMode = "labeled",
        fingerprint: Fingerprint | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._arrangement = arrangement
        self._tuning = tuning
        self._catalog = catalog
        self._strategy = strategy
        self._scene_labels: SceneLabelMode = scene_labels
        self._fingerprint = fingerprint

        self._previous_plan: Any = None  # ScenePlan | None, kept loosely typed to dodge cycles
        self._paint: ScenePaint | None = None
        self._hotspots = HotspotIndex(())
        self._grid_w = 0
        self._grid_h = 0

        self._hover_index: int | None = None  # mouse-hover hit
        self._focus_index: int | None = None  # keyboard-focus position
        self._resize_timer: Any = None
        self._pending_size: tuple[int, int] | None = None

    # -- fingerprint / cache invalidation (plan §6.2 rule 6) -----------------

    def update_inputs(
        self,
        arrangement: WorldArrangement,
        fingerprint: Fingerprint,
        *,
        scene_labels: SceneLabelMode | None = None,
    ) -> None:
        """Swap in a new sector/settings/catalogue combination.

        Discards the disposable previous plan whenever the fingerprint
        changes (new sector, changed setting, or a new catalogue version) —
        hysteresis from an unrelated prior scene must never leak into this
        one (WP-SC08 bullet 5). Reusing the widget across sectors this way
        avoids the cost of rebuilding a whole new widget per arrival.
        """

        stale = self._fingerprint is not None and self._fingerprint != fingerprint
        self._arrangement = arrangement
        self._fingerprint = fingerprint
        if scene_labels is not None:
            self._scene_labels = scene_labels
        if stale:
            self._previous_plan = None
        self._hover_index = None
        self._focus_index = None
        if self._grid_w and self._grid_h:
            self._solve_now(self._grid_w, self._grid_h)
        self.refresh()

    @property
    def scene_labels(self) -> SceneLabelMode:
        return self._scene_labels

    @property
    def plan(self) -> Any:
        return self._previous_plan

    @property
    def paint(self) -> ScenePaint | None:
        return self._paint

    @property
    def hotspots(self) -> HotspotIndex:
        return self._hotspots

    # -- resize coalescing (plan §6.2 rule 7) ---------------------------------

    def on_resize(self, event: events.Resize) -> None:
        w, h = self.size.width, self.size.height
        self._pending_size = (w, h)
        if self._resize_timer is not None:
            self._resize_timer.stop()
        self._resize_timer = self.set_timer(_RESIZE_DEBOUNCE_SECONDS, self._settle_resize)

    def _settle_resize(self) -> None:
        """Fires once a resize burst has been quiet for the debounce window —
        the *settled* size, never a transient intermediate one (WP-SC08
        bullet 5). A drag that fires ten `on_resize` events in quick
        succession restarts this timer nine times and solves once."""

        self._resize_timer = None
        if self._pending_size is None:
            return
        w, h = self._pending_size
        self._pending_size = None
        if w > 0 and h > 0:
            self._solve_now(w, h)
        self.refresh()

    def force_solve(self, w: int, h: int) -> None:
        """Synchronous solve, bypassing the debounce — for tests and any
        caller that needs the plan immediately rather than after the resize
        settles."""

        if self._resize_timer is not None:
            self._resize_timer.stop()
            self._resize_timer = None
        self._pending_size = None
        self._solve_now(w, h)

    def _solve_now(self, w: int, h: int) -> None:
        self._grid_w, self._grid_h = w, h
        viewport = CellBox(col=0, row=0, width=w, height=h)
        plan = solve(
            self._arrangement, viewport, self._tuning, self._catalog, self._strategy,
            previous=self._previous_plan,
        )
        self._previous_plan = plan
        self._paint = resolve_scene(plan, self._arrangement, self._catalog, self._tuning)
        self._hotspots = HotspotIndex(plan.projections)
        if self._hover_index is not None and self._hover_index >= len(self._hotspots):
            self._hover_index = None
        if self._focus_index is not None and self._focus_index >= len(self._hotspots):
            self._focus_index = None

    # -- rejected-object sidebar rows (plan §4 invariant 9) -------------------

    @property
    def rejected_rows(self) -> tuple[SidebarRow, ...]:
        plan = self._previous_plan
        if plan is None:
            return ()
        return rejected_sidebar_rows(plan.rejected, self._arrangement)

    # -- hit testing / hover / keyboard focus ---------------------------------

    def on_mouse_move(self, event: events.MouseMove) -> None:
        hit = self._hotspots.hit_test(int(event.x), int(event.y))
        new_index = self._index_of(hit)
        if new_index != self._hover_index:
            self._hover_index = new_index
            self.refresh()

    def on_leave(self, event: events.Leave) -> None:
        if self._hover_index is not None:
            self._hover_index = None
            self.refresh()

    def _index_of(self, projection: Projection | None) -> int | None:
        if projection is None:
            return None
        for i, p in enumerate(self._hotspots.ordered):
            if p.key == projection.key:
                return i
        return None

    def _current_focus_index(self) -> int | None:
        """The keyboard-focus hotspot index, lazily defaulted to the first
        hotspot the moment this widget has focus (mirrors `ObjectRow`'s
        focus-lands-on-first-row convention elsewhere in the TUI). Computed
        from `self.has_focus` rather than a `Focus`/`Blur` event handler,
        since Textual's message-handler naming convention (`_get_dispatch_methods`)
        prefers a class's own `_on_focus` private override over a public
        `on_focus` defined in the same class, and `Static`'s ancestor already
        claims that name."""

        if not self.has_focus:
            return None
        if self._focus_index is None and len(self._hotspots):
            self._focus_index = 0
        return self._focus_index

    def action_focus_next(self) -> None:
        self._move_focus(1)

    def action_focus_previous(self) -> None:
        self._move_focus(-1)

    def _move_focus(self, delta: int) -> None:
        n = len(self._hotspots)
        if n == 0:
            self._focus_index = None
            return
        if self._focus_index is None:
            self._focus_index = 0 if delta > 0 else n - 1
        else:
            self._focus_index = (self._focus_index + delta) % n
        self.refresh()

    def action_pick(self) -> None:
        """Activate the current hotspot — keyboard-focus or mouse-hover,
        whichever the player last moved (plan §4 invariant 10: identical
        route regardless of how the hotspot was reached)."""

        focus_index = self._current_focus_index()
        index = focus_index if focus_index is not None else self._hover_index
        if index is None or index >= len(self._hotspots):
            return
        projection = self._hotspots[index]
        dest, ref = _route_for(projection.key)
        if dest is not None:
            self.post_message(self.Picked(dest, ref))

    def on_click(self, event: events.Click) -> None:
        hit = self._hotspots.hit_test(int(event.x), int(event.y))
        if hit is None:
            return
        dest, ref = _route_for(hit.key)
        if dest is not None:
            event.stop()
            self.post_message(self.Picked(dest, ref))

    # -- current hover/focus hint, for tests and render() ---------------------

    @property
    def active_hint_index(self) -> int | None:
        """The hotspot whose hint is showing right now, in `hover_hint` mode:
        mouse hover wins when present, else keyboard focus (plan §2.6 — both
        routes reveal "the same hint")."""

        if self._scene_labels != "hover_hint":
            return None
        return self._hover_index if self._hover_index is not None else self._current_focus_index()

    def active_hint_label(self) -> str | None:
        index = self.active_hint_index
        if index is None or index >= len(self._hotspots):
            return None
        projection = self._hotspots[index]
        obj = next((o for o in self._arrangement.objects if o.key == projection.key), None)
        return obj.label if obj is not None else None

    # -- render ----------------------------------------------------------------

    def render(self) -> Text:
        paint = self._paint
        w, h = self._grid_w, self._grid_h
        if paint is None or w <= 0 or h <= 0:
            return Text("")
        viewport = CellBox(col=0, row=0, width=w, height=h)
        grid = paint_grid(paint, viewport)
        out = Text()
        labels_by_key = self._label_overlays()
        for y in range(h):
            for x in range(w):
                ch, style = grid[y][x] if y < len(grid) and x < len(grid[y]) else (" ", None)
                out.append(ch, style=style)
            if y < h - 1:
                out.append("\n")
        # Labels are stamped as a markup overlay describing where each
        # accepted object's name would show; the exact glyph placement is a
        # WP-SC09/SC10 art concern. Kept minimal and testable here: `labeled`
        # mode's set of labelled keys, and `hover_hint`'s single active
        # label, are both exposed as data (`labels_by_key`,
        # `active_hint_label()`) for tests and any future paint step to
        # consume — never as scene text for a rejected object (§4 invariant
        # 9 only concerns rejected objects; accepted labels are fine).
        del labels_by_key
        return out

    def _label_overlays(self) -> dict[SceneKey, str]:
        if self._scene_labels == "hidden":
            return {}
        if self._scene_labels == "labeled":
            return {p.key: self._label_of(p.key) for p in self._hotspots.ordered}
        # hover_hint: only the active one.
        index = self.active_hint_index
        if index is None or index >= len(self._hotspots):
            return {}
        key = self._hotspots[index].key
        return {key: self._label_of(key)}

    def _label_of(self, key: SceneKey) -> str:
        obj = next((o for o in self._arrangement.objects if o.key == key), None)
        return obj.label if obj is not None else ""
