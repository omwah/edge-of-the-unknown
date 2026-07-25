"""Presentation plumbing shared by the survey and assault ground-operation screens.

Both ``ground_expedition.GroundExpeditionScreen`` (GW-WP07) and
``ground_assault.GroundAssaultScreen`` (GW-WP12) render a server-projected,
DTO-cropped viewport onto a terrain grid with a moving camera, a fading
per-cell flash overlay, and a collapsible event log. This module holds the
parts of that machinery that are identical between the two screens — the
terrain colour/glyph pipeline, viewport sizing, camera-follow geometry, and
the flash/log-height bookkeeping — so a fix or tuning change made here reaches
both screens instead of drifting between two copies.

Also shared: ``CroppedMapView``, the base widget behind both screens' map — cache the
built grid per server ``view``, restyle a copy for a bare cursor move or flash instead
of rebuilding it. What stays screen-local, as subclass overrides: each screen's own
mechanics (survey's landing animation and drop-site darkening have no assault
equivalent; assault's threat overlays and capsule placement have no survey
equivalent), its own ``_render_frame``/``_cell`` composition, and its own event-style
registry (the two screens narrate different event types).
"""

from __future__ import annotations

import time
from binascii import crc32
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from rich.color import Color
from rich.text import Text
from textual import events
from textual.timer import Timer
from textual.widgets import Static

from edge.art.interior import DOOR_COLOR, DOOR_GLYPH, LIFT_COLOR, LIFT_GLYPH, WALL_COLOR, WALL_GLYPHS
from edge.art.interior import FEATURE_COLORS as _INTERIOR_FEATURE_COLORS
from edge.art.interior import FEATURES_REGISTRY as _INTERIOR_FEATURES_REGISTRY
from edge.art.terrain import BIOME_COLORS, FEATURES_REGISTRY, readable_fg
from edge.core.groundwar.terrain import BIOME_BANDS

# Cursor movement shared by both screens' `on_key`: arrows plus vim hjkl.
CURSOR_MOVES: dict[str, tuple[int, int]] = {
    "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
    "k": (0, -1), "j": (0, 1), "h": (-1, 0), "l": (1, 0),
}

# Shift+hjkl (as capitals): a longer cursor jump without moving the camera frame.
FAST_MOVE_SCALE: tuple[int, int] = (8, 4)

# wasd: pan the camera without moving the cursor relative to the map.
PAN_MOVES: dict[str, tuple[int, int]] = {
    "w": (0, -4), "s": (0, 4), "a": (-8, 0), "d": (8, 0),
}


def viewport_size(widget: Static) -> tuple[int, int]:
    """The map widget's current size, floored so a just-mounted 0x0 widget still renders."""
    return max(20, widget.size.width), max(8, widget.size.height)


def clamp_camera(
    x: int, y: int, viewport_width: int, viewport_height: int,
    map_width: int, map_height: int,
) -> tuple[int, int]:
    return (
        max(0, min(map_width - viewport_width, x)),
        max(0, min(map_height - viewport_height, y)),
    )


def follow_camera(
    cursor_x: int, cursor_y: int, camera_x: int, camera_y: int,
    viewport_width: int, viewport_height: int, map_width: int, map_height: int,
) -> tuple[int, int]:
    """Slide the camera by the minimum amount that keeps the cursor inside its margin.

    The margin shrinks with the viewport so a tiny (e.g. compact-layout) map still has
    room to scroll; sequential (not `elif`) edge checks so a camera correction from the
    x-axis check never masks a needed y-axis one, and vice versa.
    """
    margin_x = min(8, viewport_width // 3)
    margin_y = min(3, viewport_height // 3)
    nx, ny = camera_x, camera_y
    if cursor_x < nx + margin_x:
        nx = cursor_x - margin_x
    if cursor_x > nx + viewport_width - margin_x:
        nx = cursor_x - viewport_width + margin_x
    if cursor_y < ny + margin_y:
        ny = cursor_y - margin_y
    if cursor_y > ny + viewport_height - margin_y:
        ny = cursor_y - viewport_height + margin_y
    return clamp_camera(nx, ny, viewport_width, viewport_height, map_width, map_height)


def pan_camera(
    camera_x: int, camera_y: int, cursor_x: int, cursor_y: int, dx: int, dy: int,
    viewport_width: int, viewport_height: int, map_width: int, map_height: int,
) -> tuple[int, int, int, int] | None:
    """Move the camera by `(dx, dy)`, carrying the cursor along with it.

    Returns the new `(camera_x, camera_y, cursor_x, cursor_y)`, or `None` if the camera
    was already at that edge of the map and nothing moved.
    """
    new_camera_x, new_camera_y = clamp_camera(
        camera_x + dx, camera_y + dy, viewport_width, viewport_height, map_width, map_height)
    moved_x, moved_y = new_camera_x - camera_x, new_camera_y - camera_y
    if not (moved_x or moved_y):
        return None
    new_cursor_x = max(0, min(map_width - 1, cursor_x + moved_x))
    new_cursor_y = max(0, min(map_height - 1, cursor_y + moved_y))
    return new_camera_x, new_camera_y, new_cursor_x, new_cursor_y


@lru_cache(maxsize=None)
def feature_colors(ptype: str, feature: str) -> tuple[str, str]:
    """The band's authored (fg, bg) for a feature name — deliberately *not* yet
    contrast-corrected, because the background a cell finally renders on is not
    always its own (see `styled`).

    Station-interior feature names (GW-WP15/16) are a disjoint namespace from any
    planet biome's, so they're checked first and never consult `ptype` — one
    Cloud City interior looks the same regardless of which jovian it floats over.
    """
    if feature == "bulkhead":
        return WALL_COLOR
    if feature == "security_door":
        return DOOR_COLOR
    if feature == "lift":
        return LIFT_COLOR
    if feature in _INTERIOR_FEATURE_COLORS:
        return _INTERIOR_FEATURE_COLORS[feature]
    layout = BIOME_BANDS.get(ptype)
    colors = BIOME_COLORS.get(ptype, [])
    if layout is not None:
        for index, (_threshold, name) in enumerate(layout.bands):
            if name == feature and index < len(colors):
                return colors[index]
    return "white", ""


@lru_cache(maxsize=None)
def hex_color(color: str) -> str:
    """Pin a colour to concrete truecolor, so the terminal cannot theme it away.

    Named ANSI colours are *theme-dependent*: `readable_fg` measures contrast against
    rich's nominal 4-bit palette, but the terminal paints its own. Where a band's fg and
    bg are the same colour family — `terrestrial_cool` forest is `bright_green` on
    `green`, and water_shallow/sand/dust/snow are alike — the nominal gap clears the
    correction threshold while the *rendered* pair collapses into one colour, leaving
    trees visible only when the cursor passes over them. Emitting hex makes what we
    measured and what gets painted the same thing.
    """
    try:
        rgb = Color.parse(color).get_truecolor()
    except Exception:  # unknown name — leave it for the terminal to resolve
        return color
    return f"#{rgb.red:02x}{rgb.green:02x}{rgb.blue:02x}"


@lru_cache(maxsize=None)
def styled(fg: str, bg: str) -> str:
    """A rich style whose foreground is legible against the background it actually gets.

    Two corrections happen here. First, overlays (search rings, scanner heat, walk range,
    threat bands) repaint the backdrop while keeping the terrain's foreground, so contrast
    is checked against the *winning* background — correcting against the terrain's own and
    then swapping the background out defeated it (`water_deep` on the `dark_orange3` heat
    band measured a 0.002 luminance gap). Second, the result is pinned to hex (see
    `hex_color`).
    """
    if not bg:
        return hex_color(fg)
    return f"{hex_color(readable_fg(fg, bg))} on {hex_color(bg)}"


@lru_cache(maxsize=None)
def dim_color(color: str, factor: float) -> str:
    """Push a colour toward black, keeping its hue."""
    try:
        rgb = Color.parse(color).get_truecolor()
    except Exception:
        return color
    return (f"#{round(rgb.red * factor):02x}"
            f"{round(rgb.green * factor):02x}{round(rgb.blue * factor):02x}")


@lru_cache(maxsize=None)
def glyph_ramp(feature: str) -> tuple[tuple[str, ...], tuple[float, ...], float]:
    """The feature's glyphs with cumulative weights (authored weights may be fractional).

    Checks the interior registry (GW-WP15/16) before the biome one — the two feature-name
    sets are disjoint (validated by `GroundwarConfig`), so this never shadows a planet
    texture, and a Cloud City's rooms/corridors get their own weighted pool the same way.
    """
    choices = _INTERIOR_FEATURES_REGISTRY.get(feature) or FEATURES_REGISTRY.get(feature, [("?", 1)])
    chars: list[str] = []
    cumulative: list[float] = []
    running = 0.0
    for char, weight in choices:
        running += float(weight)
        chars.append(char)
        cumulative.append(running)
    return tuple(chars), tuple(cumulative), running


def feature_glyph(planet_id: int, feature: str, x: int, y: int, wall_mask: int = 0) -> str:
    """Draw this cell's glyph against the authored weights, deterministically.

    A per-cell random draw is what makes a forest read as scattered trees over clearings
    (its blank entry carries most of the weight) instead of a solid wall of one repeated
    glyph. The client has no operation seed and must never receive one (G5), but a glyph
    only needs a *stable* key — and the feature name, the cell's coordinates, and
    `planet_id` are all already public in the DTO, so texture costs nothing in fog of war.
    CRC32 rather than `hash()`: string hashing is salted per process, and snapshot tests
    need the same map to render identically every run.

    `bulkhead`/`security_door`/`lift` are station-interior landmarks, not texture (GW-WP15/16):
    a wall reads as connected structure only via its neighbor-junction glyph, keyed off the
    server-computed `wall_mask` (`AssaultCellDTO`/`GroundCellDTO.wall_mask`) since a client
    holding only a cropped viewport cannot always see a wall cell's true neighbours itself
    (`edge.core.groundwar.interior.wall_neighbor_mask`); a door or lift is a fixed landmark,
    never randomized texture.
    """
    if feature == "bulkhead":
        return WALL_GLYPHS[wall_mask]
    if feature == "security_door":
        return DOOR_GLYPH
    if feature == "lift":
        return LIFT_GLYPH
    chars, cumulative, total = glyph_ramp(feature)
    if total <= 0:
        return chars[0]
    roll = crc32(f"{planet_id}|{feature}|{x}|{y}".encode()) / 2**32 * total
    for char, edge in zip(chars, cumulative):
        if roll < edge:
            return char
    return chars[-1]


class CroppedMapView(Static, can_focus=True):
    """Base widget for a server-cropped, DTO-projected viewport with a moving camera.

    Both survey (`GroundExpeditionScreen`) and assault (`GroundAssaultScreen`) render a
    fog-safe grid the same way: build the visible cells into a `Text` once per `view`
    object (a fresh one only arrives on a genuine server refresh), then on every later
    render — most often a bare cursor move — copy that cached frame and restyle just
    the handful of cells that changed (a flash, the cursor) instead of rebuilding the
    whole grid. Skipping that cache is what made assault's scrolling feel stiffer than
    survey's: both screens used to implement this caching independently, and assault's
    `AssaultMapView` hadn't been given it, so every keystroke re-walked the entire
    viewport.

    Subclasses provide `_index_view` (rebuild per-cell lookup dicts when `view`
    changes), `_extra_frame_key` (screen-specific state that must also invalidate the
    cached frame — an overlay toggle, in-progress capsule placements, an animation
    step, …), and `_render_frame` (build the full grid). The host screen must expose
    `view`, `cursor_x`/`cursor_y`, `live_flashes()`, `cursor_is_legal()`, and
    `set_cursor()`.
    """

    def __init__(self, host: Any, widget_id: str, loading_text: str) -> None:
        super().__init__(id=widget_id)
        self.host_screen = host
        self._loading_text = loading_text
        self._cells_view: Any = None
        self._frame_key: tuple[Any, ...] | None = None
        self._frame: Text | None = None

    def _index_view(self, view: Any) -> None:
        """Rebuild per-cell lookup dicts; called once whenever `view`'s identity changes."""
        raise NotImplementedError

    def _extra_frame_key(self, view: Any) -> tuple[Any, ...]:
        """Screen-specific components beyond `id(view)` that must also force a rebuild."""
        return ()

    def _render_frame(self, view: Any) -> Text:
        raise NotImplementedError

    def render(self) -> Text:
        view = self.host_screen.view
        if view is None:
            return Text(self._loading_text, style="dim")
        if view is not self._cells_view:
            self._cells_view = view
            self._index_view(view)
        frame_key = (id(view), *self._extra_frame_key(view))
        if frame_key != self._frame_key:
            self._frame_key = frame_key
            self._frame = self._render_frame(view)
        assert self._frame is not None
        out = self._frame.copy()

        def restyle(x: int, y: int, style: str) -> None:
            col = x - view.viewport_x
            row = y - view.viewport_y
            if 0 <= col < view.viewport_width and 0 <= row < view.viewport_height:
                offset = row * (view.viewport_width + 1) + col
                out.stylize(style, offset, offset + 1)

        # A style like "on orange3" only sets the background; Rich combines a later,
        # smaller span with the frame's own per-character style at render time, so the
        # cached foreground shows through untouched — no need to re-derive it here.
        for (fx, fy), (style, _until) in self.host_screen.live_flashes().items():
            restyle(fx, fy, style)
        # A fixed "black on bright_white" legal-cursor swatch reads fine against dark
        # planet terrain but disappears into a light Cloud City floor (GW-WP15/17 station
        # interiors, edge.art.interior, moved to a near-white palette) — "reverse" instead
        # inverts whatever fg/bg the cell already has, so it stays high-contrast against
        # any tile without needing to know the underlying theme (verified against
        # Textual's SVG snapshot export, which resolves `reverse` into swapped fill
        # colours rather than leaving it as an unswapped terminal attribute).
        cursor_style = "reverse" if self.host_screen.cursor_is_legal() else "bright_white on red3"
        restyle(self.host_screen.cursor_x, self.host_screen.cursor_y, cursor_style)
        return out

    async def _on_click(self, event: events.Click) -> None:
        view = self.host_screen.view
        if view is not None:
            await self.host_screen.set_cursor(
                view.viewport_x + event.x, view.viewport_y + event.y)


class _FlashHost(Protocol):
    """What `FlashTrackerMixin` needs from the `Screen` it is mixed into."""

    _flashes: dict[tuple[int, int], tuple[str, float]]

    def set_timer(self, delay: float, callback: object) -> Timer: ...
    def _refresh_widgets(self) -> None: ...


class FlashTrackerMixin:
    """Transient per-cell style overlays that fade a fixed time after the event they mark.

    Both screens flash a cell — a shot landing, a dig turning up dirt, a capsule
    touching down — the same way: record a `(style, expiry)` against the cell, let
    `render()` read `live_flashes()` each frame, and let expired entries drop out on
    their own the next time anything asks.
    """

    _flashes: dict[tuple[int, int], tuple[str, float]]

    def live_flashes(self) -> dict[tuple[int, int], tuple[str, float]]:
        now = time.monotonic()
        self._flashes = {cell: flash for cell, flash in self._flashes.items() if flash[1] > now}
        return self._flashes

    def flash_cells(self: _FlashHost, cells: Iterable[tuple[int, int]], style: str, seconds: float) -> None:
        until = time.monotonic() + seconds
        for cell in cells:
            self._flashes[cell] = (style, until)
        if self._flashes:
            self.set_timer(seconds + 0.05, self._refresh_widgets)


def toggle_log_height(screen: object, selector: str, *, expanded: bool, collapsed_h: int, expanded_h: int) -> None:
    """Flip a docked `RichLog`'s height between its peek and expanded sizes."""
    logs = screen.query(selector)  # type: ignore[attr-defined]
    if logs:
        logs.first().styles.height = expanded_h if expanded else collapsed_h


def warn(screen: object, selector: str, message: str) -> None:
    """Surface a blocked-action or rejected-command reason as a persistent log line.

    A corner toast fades in a few seconds and leaves no record of *why* a keypress
    did nothing — confusing when the reason (no line of sight, no actions left, out
    of main-game turns…) is tactically relevant and the player wants to look back at
    it. Both screens' event logs already narrate what happened; this makes "why
    didn't that work" equally visible there instead of a popup that vanishes.
    """
    logs = screen.query(selector)  # type: ignore[attr-defined]
    if logs:
        logs.first().write(Text.from_markup(message, style="yellow"))


@dataclass(frozen=True)
class LandingFrame:
    """One tick of a touchdown animation: glyph overrides plus an optional log beat."""

    cells: dict[tuple[int, int], tuple[str, str]]
    log: str = ""


LANDING_TICK = 0.17  # seconds per frame; the whole descent runs a bit over a second


class LandingAnimationMixin:
    """Plays a scripted sequence of glyph-override frames over the map, one tick at a
    time, then clears itself.

    Shared by survey's single-explorer touchdown and assault's multi-capsule drop —
    the same falling-shuttle-then-figure choreography, just built from a different
    number of touchdown points (`landing_frames` below takes a list, so one caller
    covers both). Host screens provide `anim_cells`/`anim_step` (read by the map
    view's `_cell` override to substitute glyphs mid-animation) and `_refresh_widgets`
    (both screens already have it), and implement `_landing_log` to narrate a frame's
    beat into their own log widget.
    """

    anim_cells: dict[tuple[int, int], tuple[str, str]]
    anim_step: int
    _anim_frames: list[LandingFrame]
    _anim_timer: Timer | None

    def _landing_log(self, text: str) -> None:
        raise NotImplementedError

    def _play_landing(self: Any, frames: list[LandingFrame]) -> None:
        self._anim_frames = list(frames)
        self._advance_landing()

    def _advance_landing(self: Any) -> None:
        if not self._anim_frames:
            self._end_landing()
            return
        frame = self._anim_frames.pop(0)
        self.anim_cells = frame.cells
        self.anim_step += 1
        if frame.log:
            self._landing_log(frame.log)
        self._refresh_widgets()
        self._anim_timer = self.set_timer(LANDING_TICK, self._advance_landing)

    def _end_landing(self: Any) -> None:
        """Clear the overlay and stop the clock — also the skip path, so a keypress
        during the descent lands immediately rather than replaying the rest."""
        if self._anim_timer is not None:
            self._anim_timer.stop()
            self._anim_timer = None
        self._anim_frames = []
        if self.anim_cells:
            self.anim_cells = {}
            self.anim_step += 1
        self._refresh_widgets()

    @property
    def _landing_playing(self) -> bool:
        return bool(self._anim_frames or self.anim_cells)


def landing_frames(
    touchdowns: Iterable[tuple[tuple[int, int], str, str]],
) -> list[LandingFrame]:
    """One synchronized descent for every `((x, y), glyph, style)` touchdown — a lone
    explorer for survey, one row of capsules for assault.

    Coordinates above a target are clamped by the renderer (cells off the viewport
    simply do not draw), so a drop site near the top edge just shows a shorter fall.
    """
    points = list(touchdowns)
    shuttle = "bold bright_white on grey15"
    plume = "bold wheat1 on dark_goldenrod"
    plural = len(points) > 1
    frames = [
        LandingFrame({(x, y - 4): ("╱▲╲"[1], shuttle) for (x, y), _, _ in points},
                    "[b]Capsules away.[/]" if plural else "[b]Shuttle away.[/]"),
        LandingFrame({(x, y - 3): ("▲", shuttle) for (x, y), _, _ in points}),
        LandingFrame({(x, y - 2): ("▲", shuttle) for (x, y), _, _ in points},
                    "Entering atmosphere…"),
        LandingFrame({(x, y - 1): ("▼", shuttle) for (x, y), _, _ in points}),
    ]

    def ring(x: int, y: int) -> list[tuple[int, int]]:
        return [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]

    def wide(x: int, y: int) -> list[tuple[int, int]]:
        return [(x - 2, y), (x + 2, y), (x - 1, y - 1), (x + 1, y - 1),
                (x - 1, y + 1), (x + 1, y + 1)]

    plume_ring = {c: ("░", plume) for (x, y), _, _ in points for c in ring(x, y)}
    frames.append(LandingFrame(
        {**{(x, y): ("▼", shuttle) for (x, y), _, _ in points}, **plume_ring}))
    settle = {**{c: ("░", plume) for (x, y), _, _ in points for c in wide(x, y)},
             **{c: ("▒", plume) for (x, y), _, _ in points for c in ring(x, y)},
             **{(x, y): (glyph, style) for (x, y), glyph, style in points}}
    frames.append(LandingFrame(
        settle, "[b]Touchdown[/] — deployed." if plural else "[b]Touchdown[/] — survey deployed."))
    tail = {**{c: ("░", plume) for (x, y), _, _ in points for c in ring(x, y)},
           **{(x, y): (glyph, style) for (x, y), glyph, style in points}}
    frames.append(LandingFrame(tail))
    return frames
