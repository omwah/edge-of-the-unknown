"""Live survey expedition over the service/DTO boundary (GW-WP07).

This is the production sibling of ``edge.groundwar.expedition_ui``.  It owns only
cursor/camera/overlay presentation state: every move, dig, talk, and extraction is an
authoritative command, and every rendered fact comes back in ``SurveyExpeditionDTO``.
"""

from __future__ import annotations

import time
from binascii import crc32
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from rich.color import Color
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Footer, RichLog, Static

from edge.art.terrain import BIOME_COLORS, FEATURES_REGISTRY, readable_fg
from edge.core.dto import GroundCellDTO, SurveyContactDTO, SurveyExpeditionDTO
from edge.core.enums import DiscoveryKind
from edge.core.events import (
    GroundMoved,
    SurveyDug,
    SurveyLanded,
    SurveySiteExcavated,
    SurveyTalked,
)
from edge.core.groundwar.terrain import BIOME_BANDS
from edge.core.movement import MovementError
from edge.core.rules import (
    ExtractGroundOperation,
    GroundMove,
    SurveyDig,
    SurveyLand,
    SurveyTalk,
)
from edge.core.surface_finds import FIND_KINDS, surface_find_kind
from edge.groundwar.findart import generate_find_art
from edge.server.client import GameClient
from edge.tui import art_adapter
from edge.tui.chrome import EdgeScreen, notify_warning


_HEAT = ("", "red3", "dark_orange3", "grey46", "grey30")
_OVERLAYS = ("scanner", "range", "off")

# The log is a peek by default so the map keeps the room; `z` opens it up (the POC
# battle screen's convention, ported here).
_LOG_COLLAPSED_H = 3
_LOG_EXPANDED_H = 14

# How long a cell stays tinted after the event that touched it.
_FLASH_SECONDS = 0.5

# The surveyor. Cyrillic big yus reads as a figure with arms and legs out, and unlike the
# obvious pictographic candidates it is single-cell everywhere: emoji-presentation glyphs
# (⛑, ♟, ☺ in some fonts) and East-Asian-ambiguous ones (Ω, ∩ under a CJK width setting)
# render double-width and would shear the map grid.
_EXPLORER = "Ѫ"
_EXPLORER_STYLE = "black on bright_green"


@dataclass(frozen=True)
class _LandingFrame:
    """One tick of the touchdown animation: glyph overrides plus an optional log beat."""

    cells: dict[tuple[int, int], tuple[str, str]]
    log: str = ""


_LANDING_TICK = 0.17  # seconds per frame; the whole descent runs a bit over a second


def _landing_frames(x: int, y: int) -> list[_LandingFrame]:
    """The shuttle falling onto `(x, y)`: descent, plume, then the explorer standing there.

    Coordinates above the target are clamped by the renderer (cells off the viewport simply
    do not draw), so a drop site near the top edge just shows a shorter fall.
    """
    shuttle = "bold bright_white on grey15"
    frames = [
        _LandingFrame({(x, y - 4): ("╱▲╲"[1], shuttle)}, "[b]Shuttle away.[/]"),
        _LandingFrame({(x, y - 3): ("▲", shuttle)}),
        _LandingFrame({(x, y - 2): ("▲", shuttle)}, "Entering atmosphere…"),
        _LandingFrame({(x, y - 1): ("▼", shuttle)}),
    ]
    plume = "bold wheat1 on dark_goldenrod"
    ring = [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)]
    wide = [(x - 2, y), (x + 2, y), (x - 1, y - 1), (x + 1, y - 1),
            (x - 1, y + 1), (x + 1, y + 1)]
    frames.append(_LandingFrame(
        {(x, y): ("▼", shuttle), **{c: ("░", plume) for c in ring}}))
    frames.append(_LandingFrame(
        {(x, y): (_EXPLORER, _EXPLORER_STYLE),
         **{c: ("▒", plume) for c in ring},
         **{c: ("░", plume) for c in wide}},
        "[b]Touchdown[/] — survey deployed."))
    frames.append(_LandingFrame(
        {(x, y): (_EXPLORER, _EXPLORER_STYLE), **{c: ("░", plume) for c in ring}}))
    return frames


# Log emphasis by event type — a find must not read like a dry hole.
_EVENT_STYLES: dict[type, str] = {
    SurveySiteExcavated: "bold bright_yellow",
    SurveyDug: "wheat1",
    SurveyTalked: "bold bright_cyan",
    GroundMoved: "grey66",
    SurveyLanded: "bold bright_green",
}


@lru_cache(maxsize=None)
def _feature_colors(ptype: str, feature: str) -> tuple[str, str]:
    """The band's authored (fg, bg) for a feature name — deliberately *not* yet
    contrast-corrected, because the background a cell finally renders on is not
    always its own (see `_styled`)."""
    layout = BIOME_BANDS.get(ptype)
    colors = BIOME_COLORS.get(ptype, [])
    if layout is not None:
        for index, (_threshold, name) in enumerate(layout.bands):
            if name == feature and index < len(colors):
                return colors[index]
    return "white", ""


@lru_cache(maxsize=None)
def _hex(color: str) -> str:
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
def _styled(fg: str, bg: str) -> str:
    """A rich style whose foreground is legible against the background it actually gets.

    Two corrections happen here. First, overlays (search rings, scanner heat, walk range)
    repaint the backdrop while keeping the terrain's foreground, so contrast is checked
    against the *winning* background — correcting against the terrain's own and then
    swapping the background out defeated it (`water_deep` on the `dark_orange3` heat band
    measured a 0.002 luminance gap). Second, the result is pinned to hex (see `_hex`).
    """
    if not bg:
        return _hex(fg)
    return f"{_hex(readable_fg(fg, bg))} on {_hex(bg)}"


@lru_cache(maxsize=None)
def _dim(color: str, factor: float) -> str:
    """Push a colour toward black, keeping its hue."""
    try:
        rgb = Color.parse(color).get_truecolor()
    except Exception:
        return color
    return (f"#{round(rgb.red * factor):02x}"
            f"{round(rgb.green * factor):02x}{round(rgb.blue * factor):02x}")


@lru_cache(maxsize=None)
def _styled_excluded(fg: str, bg: str) -> str:
    """Terrain the shuttle cannot set down on, while inbound.

    The same colours as the real terrain, dimmed toward black — so the map still reads as
    a map (water is still blue, peaks still grey) while the unusable ground plainly sits
    behind the ground you can pick.

    Contrast is re-checked *after* dimming rather than assumed: the two factors differ, so
    on a band whose foreground is already darker than its background (`sand` is
    `yellow on bright_yellow`) dimming alone drives the pair together — it measured a 0.063
    luminance gap before this correction.
    """
    lit = _styled(fg, bg)
    if " on " not in lit:
        return _dim(lit, 0.55)
    front, back = lit.split(" on ")
    front, back = _dim(front, 0.62), _dim(back, 0.38)
    return f"{_hex(readable_fg(front, back))} on {back}"


@lru_cache(maxsize=None)
def _glyph_ramp(feature: str) -> tuple[tuple[str, ...], tuple[float, ...], float]:
    """The feature's glyphs with cumulative weights (authored weights may be fractional)."""
    choices = FEATURES_REGISTRY.get(feature, [("?", 1)])
    chars: list[str] = []
    cumulative: list[float] = []
    running = 0.0
    for char, weight in choices:
        running += float(weight)
        chars.append(char)
        cumulative.append(running)
    return tuple(chars), tuple(cumulative), running


def _feature_glyph(planet_id: int, feature: str, x: int, y: int) -> str:
    """Draw this cell's glyph against the authored weights, deterministically.

    The POC drew per cell from the map RNG, which is what makes a forest read as
    scattered trees over clearings (its blank entry carries 40 of 89 parts) instead of
    a solid wall of one repeated glyph. The client has no operation seed and must never
    receive one (G5), but a glyph only needs a *stable* key — and the feature name, the
    cell's coordinates, and `planet_id` are all already public in the DTO, so texture
    costs nothing in fog of war. CRC32 rather than `hash()`: string hashing is salted
    per process, and snapshot tests need the same map to render identically every run.
    """
    chars, cumulative, total = _glyph_ramp(feature)
    if total <= 0:
        return chars[0]
    roll = crc32(f"{planet_id}|{feature}|{x}|{y}".encode()) / 2**32 * total
    for char, edge in zip(chars, cumulative):
        if roll < edge:
            return char
    return chars[-1]


class SurveyFindModal(ModalScreen[None]):
    """The excavated artifact card; all identity comes from the refreshed DTO."""

    BINDINGS = [Binding("escape", "close", "Close"), Binding("enter", "close", "Close")]
    CSS = """
    SurveyFindModal { align: center middle; background: $background 60%; }
    SurveyFindModal #find-box {
        width: 58; max-width: 100%; height: auto; max-height: 95%; overflow-y: auto;
        padding: 1 2; border: round $secondary; background: $surface;
    }
    SurveyFindModal #find-title { text-style: bold; color: $warning; }
    SurveyFindModal #find-art { height: auto; margin: 1 0; text-align: center; }
    SurveyFindModal #find-meta { color: $text-muted; }
    SurveyFindModal #find-blurb { color: $text-muted; margin-bottom: 1; }
    """

    def __init__(self, contact: SurveyContactDTO, *, first: bool) -> None:
        super().__init__()
        self._contact = contact
        self._first = first

    def compose(self) -> ComposeResult:
        c = self._contact
        title = "A DISCOVERY — artifact and lore recorded" if self._first else "FIELD NOTES"
        try:
            find_kind = surface_find_kind(DiscoveryKind(c.kind), c.discovery_id)
        except ValueError:
            find_kind = None
        if find_kind is None:
            art = art_adapter.sprite(
                "discovery", c.kind, seed=c.discovery_id, width=44, height=10)
            label = c.kind.replace("_", " ")
            blurb = ""
        else:
            identity = FIND_KINDS[find_kind]
            art = generate_find_art(find_kind, c.discovery_id)
            label = identity.label
            blurb = identity.blurb
        with VerticalScroll(id="find-box"):
            yield Static(title, id="find-title")
            yield Static(art, id="find-art")
            yield Static(f"[b]{c.name}[/]")
            yield Static(f"{label} · {c.rarity.lower()}", id="find-meta")
            if blurb:
                yield Static(blurb, id="find-blurb")
            yield Static("[dim]Esc or Enter to close[/]")

    def action_close(self) -> None:
        self.dismiss(None)


class SurveyMapView(Static, can_focus=True):
    """Scrolling server-projected viewport with mouse cursor selection."""

    def __init__(self, host: GroundExpeditionScreen) -> None:
        super().__init__(id="survey-map")
        self.host_screen = host
        self._cells_view: SurveyExpeditionDTO | None = None
        self._cells: dict[tuple[int, int], GroundCellDTO] = {}
        self._frame_key: tuple[int, str] | None = None
        self._frame: Text | None = None

    def render(self) -> Text:
        view = self.host_screen.view
        if view is None:
            return Text("Loading survey…", style="dim")
        if view is not self._cells_view:
            self._cells_view = view
            self._cells = {(cell.x, cell.y): cell for cell in view.cells}
        # The landing animation replaces glyphs, not just styles, so it has to invalidate
        # the cached frame — hence the step counter in the key.
        frame_key = id(view), self.host_screen.overlay, self.host_screen.anim_step
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

        for (fx, fy), (style, _until) in self.host_screen.live_flashes().items():
            restyle(fx, fy, style)
        # While inbound the cursor is a drop-site picker, so it has to say whether the cell
        # under it is one — a white cursor over open water would read as a legal choice.
        cursor = "black on bright_white"
        if view.can_land and not self.host_screen.cursor_is_landable():
            cursor = "bright_white on red3"
        restyle(self.host_screen.cursor_x, self.host_screen.cursor_y, cursor)
        return out

    def _render_frame(self, view: SurveyExpeditionDTO) -> Text:
        """Build the immutable viewport once; cursor moves only restyle a copied cell."""
        out = Text(no_wrap=True)
        for row in range(view.viewport_height):
            y = view.viewport_y + row
            for col in range(view.viewport_width):
                x = view.viewport_x + col
                cell = self._cells.get((x, y))
                if cell is None:
                    out.append(" ")
                    continue
                char, style = self._cell(cell, view)
                out.append(char, style)
            if row < view.viewport_height - 1:
                out.append("\n")
        return out

    def _cell(self, cell: GroundCellDTO, view: SurveyExpeditionDTO) -> tuple[str, str]:
        animated = self.host_screen.anim_cells.get((cell.x, cell.y))
        if animated is not None:
            return animated
        # No explorer on the map until the shuttle is down — `explorer_*` is only the
        # suggested cursor rest while inbound.
        if view.landed and (cell.x, cell.y) == (view.explorer_x, view.explorer_y):
            return _EXPLORER, _EXPLORER_STYLE
        if cell.found_contact_id:
            return "✦", "bold gold1 on grey19"
        if cell.dug:
            return "◌", "black on dark_goldenrod"
        if cell.clue:
            return "∴", "black on dark_goldenrod"
        if cell.gate:
            return "▒", "gold3 on grey30"
        if cell.blocked:
            return "█", "grey62 on grey30"
        if cell.settlement_id:
            return ("◉", "bright_cyan on grey15") if self.host_screen.is_settlement_plaza(cell) \
                else ("⌂", "navajo_white3 on grey23")
        fg, bg = _feature_colors(view.ptype, cell.feature)
        char = _feature_glyph(view.planet_id, cell.feature, cell.x, cell.y)
        # Overlays keep the terrain's foreground and repaint the backdrop; `_styled` then
        # re-checks legibility against that new backdrop rather than the terrain's own.
        if view.can_land:
            # Inbound, you are reading terrain to choose a spot, so terrain keeps its own
            # colours; the ground the shuttle cannot use recedes instead. (Painting the
            # legal cells was backwards — they are the majority, and a flat wash over them
            # hid the very biome detail the choice depends on.) The scanner/range overlays
            # stay off until there is an explorer to centre them on.
            return char, _styled(fg, bg) if cell.landing_site else _styled_excluded(fg, bg)
        if cell.search_ring:
            bg = "dark_green" if cell.search_ring == "hinted" else "grey35"
        elif self.host_screen.overlay == "scanner" and cell.heat:
            bg = _HEAT[min(cell.heat, len(_HEAT) - 1)]
        elif self.host_screen.overlay == "range" and cell.reachable:
            bg = "grey27"
        return char, _styled(fg, bg)

    async def _on_click(self, event: events.Click) -> None:
        view = self.host_screen.view
        if view is not None:
            await self.host_screen.set_cursor(
                view.viewport_x + event.x, view.viewport_y + event.y)


class GroundExpeditionScreen(EdgeScreen):
    """Walk, scan, excavate, and talk through authoritative survey commands."""

    BINDINGS = [
        Binding("escape", "extract", "Extract"),
        # No letter key for landing: `l` is vim-right in `on_key`, which stops the event
        # before bindings run. Enter commits the cursor in both phases.
        Binding("enter", "confirm", "Land / March"),
        Binding("m", "march", "March"),
        Binding("x", "dig", "Dig"),
        Binding("t", "talk", "Talk"),
        Binding("v", "view_find", "View find"),
        Binding("o", "overlay", "Overlay"),
        Binding("z", "log_expand", "Expand log"),
    ]
    HELP_TITLE = "Survey expedition"
    HELP = """\
A [b]peaceful survey[/], not a raid: orbital sensors marked each [b]search circle[/] \
before you descended — a buried site lies somewhere [i]inside[/] one, but the circle \
is not centred on it.

[b]Choosing where to land[/] — you arrive in the upper atmosphere, and the first thing \
you do is pick a drop site. Terrain reads in its normal colours; ground the shuttle will \
[b]not[/] take is [b]darkened[/]. What is left is open, level terrain inside the region \
that holds every contact, so a landing can never strand you across water from your own \
sites. Open water, mountain peaks and ice are refused, and the cursor turns \
[bright_white on red3] red [/] over anything it cannot take. \
Put the cursor on your chosen spot and press [b]Enter[/]. You choose afresh on every \
descent — a returning survey starts the cursor where you left off, but nothing stops \
you setting down on the far side of the map instead.

[b]Finding a site[/] — march toward a circle and watch the sidebar [b]SCANNER[/]: it \
reads hotter as you close on the nearest unfound site. As you close in, the \
[b]scanner glow[/] tints the ground inside your sweep — warmer means nearer. Once the \
readout saturates the scanner can do no more; now read the ground itself. \
[b]Disturbed earth[/] [black on dark_goldenrod]∴[/] only appears once you are close \
enough to notice it, and clusters within a few cells of the truth. Stand on your best \
guess and [b]X[/] to dig: that opens a trench a couple of cells wide, and a site \
anywhere inside it pays off. A dry trench costs supplies and leaves spent ground \
[black on dark_goldenrod]◌[/], so you never dig the same hole twice.

[b]Marching[/] — put the cursor on any walkable cell and press [b]M[/] or Enter. Near \
cells are a single local turn; distant ones are a multi-turn march that periodically \
charges main-game turns. A march [b]halts itself[/] the moment unseen disturbed ground \
comes into sight, so you will not tramp past the prize.

[b]Supplies[/] — every turn of marching and every dig spends one. At zero the shuttle \
recalls you, but anything found stays found: the planet remembers your position and \
your narrowed circles across descents, while trenches and supplies reset.

[b]Settlements[/] — on inhabited worlds, walk in through a [b]gate[/] and press [b]T[/]: \
the townsfolk refill your packs, and while any circle is still wide an elder's memory \
[green]tightens one of them[/].

[b]The payoff[/] — a found site is marked [gold1]✦[/] on the chart. Put the cursor on it \
and press [b]V[/] any time to revisit the find and its notes. [b]O[/] cycles the map \
overlay and [b]Z[/] expands the log when you want the full narration."""

    HELP_LEGEND_ROWS = [
        ("[#4a4a4a on #1a1a1a]░[/]",
         "darkened ground — the shuttle will not set down (inbound view only)"),
        (f"[{_EXPLORER_STYLE}]{_EXPLORER}[/]", "you, the surveyor"),
        ("[white on grey35] [/]", "sensor search circle — a site lies somewhere inside"),
        ("[white on dark_green] [/]", "narrowed circle (an elder's hint tightened it)"),
        ("[black on dark_goldenrod]∴[/]",
         "disturbed ground — the dig spot is within a few cells"),
        ("[black on dark_goldenrod]◌[/]", "ground you already dug (nothing there)"),
        ("[bold gold1 on grey19]✦[/]", "found site (press V on it to revisit the find)"),
        ("[white on grey46] [/][white on dark_orange3] [/][white on red3] [/]",
         "scanner glow — ground in your sweep, warmer = nearer a buried site"),
        ("[white on grey27] [/]", "one turn's walking range (O cycles the overlays)"),
        ("[grey62 on grey30]█[/] [gold3 on grey30]▒[/]",
         "settlement wall / gate — walk in through a gate"),
        ("[navajo_white3 on grey23]⌂[/] [bright_cyan on grey15]◉[/]",
         "homes / the plaza well — talk (T) anywhere inside a town"),
    ]

    CSS = """
    GroundExpeditionScreen #survey-main { height: 1fr; layout: horizontal; }
    GroundExpeditionScreen #survey-map { width: 1fr; height: 1fr; overflow: hidden; }
    GroundExpeditionScreen #survey-side {
        width: 34; height: 1fr; padding: 0 1; border-left: solid $primary;
    }
    /* Height is also set imperatively by `z` (see action_log_expand). */
    GroundExpeditionScreen #survey-log { dock: bottom; height: 3; border-top: solid $primary; }
    GroundExpeditionScreen.compact #survey-main { layout: vertical; }
    GroundExpeditionScreen.compact #survey-side {
        width: 1fr; height: 9; border-left: none; border-top: solid $primary;
    }
    GroundExpeditionScreen.compact #survey-log { height: 3; }
    GroundExpeditionScreen.wide #survey-side { width: 40; }
    """

    def __init__(self, client: GameClient) -> None:
        super().__init__()
        self._client = client
        self.view: SurveyExpeditionDTO | None = None
        self.cursor_x = 0
        self.cursor_y = 0
        self.camera_x = 0
        self.camera_y = 0
        # Off by default: the glow tints a wide sweep of ground, and the sidebar readout
        # already carries the signal. `O` cycles it on when you want it.
        self.overlay = "off"
        self.log_expanded = False
        self._flashes: dict[tuple[int, int], tuple[str, float]] = {}
        self.anim_cells: dict[tuple[int, int], tuple[str, str]] = {}
        self.anim_step = 0
        self._anim_frames: list[_LandingFrame] = []
        self._anim_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Container(id="survey-main"):
            yield SurveyMapView(self)
            with Vertical(id="survey-side"):
                yield Static(id="survey-status")
        yield RichLog(id="survey-log", markup=True, wrap=True)
        yield Footer()

    async def on_mount(self) -> None:
        await self._load(center=True)
        self.query_one(SurveyMapView).focus()
        log = self.query_one("#survey-log", RichLog)
        log.can_focus = False
        if self.view is not None and self.view.can_land:
            log.write("[b]Approach.[/] Pick a drop site — darkened ground is refused; "
                      "[b]Enter[/] sets down, ? opens help.")
        else:
            log.write("[b]Survey deployed.[/] Follow the scanner and marked circles; "
                      "? opens help.")

    async def on_resize(self) -> None:
        if self.view is not None:
            await self._load()

    def _viewport_size(self) -> tuple[int, int]:
        map_widget = self.query_one(SurveyMapView)
        return max(20, map_widget.size.width), max(8, map_widget.size.height)

    async def _load(self, *, center: bool = False, cursor_to_explorer: bool = False) -> None:
        width, height = self._viewport_size()
        if center and self.view is None:
            first = await self._client.ground_operation_view(
                viewport_width=width, viewport_height=height)
            if first is None:
                self.app.pop_screen()
                return
            # Inbound, the cursor rests on the suggested drop site (a remembered position
            # when it is still legal); once landed it starts on the explorer.
            start_x, start_y = (
                (first.suggested_landing_x, first.suggested_landing_y)
                if first.can_land else (first.explorer_x, first.explorer_y)
            )
            self.cursor_x, self.cursor_y = start_x, start_y
            self.camera_x = max(0, start_x - width // 2)
            self.camera_y = max(0, start_y - height // 2)
        view = await self._client.ground_operation_view(
            viewport_x=self.camera_x, viewport_y=self.camera_y,
            viewport_width=width, viewport_height=height)
        if view is None:
            self.app.pop_screen()
            return
        self.view = view
        self.camera_x, self.camera_y = view.viewport_x, view.viewport_y
        if cursor_to_explorer:
            self.cursor_x, self.cursor_y = view.explorer_x, view.explorer_y
        await self._follow_cursor()
        self._refresh_widgets()

    async def _follow_cursor(self) -> None:
        view = self.view
        if view is None:
            return
        margin_x, margin_y = min(8, view.viewport_width // 3), min(3, view.viewport_height // 3)
        nx, ny = self.camera_x, self.camera_y
        if self.cursor_x < nx + margin_x:
            nx = self.cursor_x - margin_x
        if self.cursor_x > nx + view.viewport_width - margin_x:
            nx = self.cursor_x - view.viewport_width + margin_x
        if self.cursor_y < ny + margin_y:
            ny = self.cursor_y - margin_y
        if self.cursor_y > ny + view.viewport_height - margin_y:
            ny = self.cursor_y - view.viewport_height + margin_y
        nx = max(0, min(view.map_width - view.viewport_width, nx))
        ny = max(0, min(view.map_height - view.viewport_height, ny))
        if (nx, ny) != (self.camera_x, self.camera_y):
            self.camera_x, self.camera_y = nx, ny
            width, height = self._viewport_size()
            refreshed = await self._client.ground_operation_view(
                viewport_x=nx, viewport_y=ny,
                viewport_width=width, viewport_height=height)
            if refreshed is not None:
                self.view = refreshed

    async def set_cursor(self, x: int, y: int) -> None:
        if self.view is None:
            return
        self.cursor_x = max(0, min(self.view.map_width - 1, x))
        self.cursor_y = max(0, min(self.view.map_height - 1, y))
        await self._follow_cursor()
        self.query_one(SurveyMapView).refresh()

    async def _pan(self, dx: int, dy: int) -> None:
        """POC camera pan: the cursor rides with the viewport."""
        if self.view is None:
            return
        old_x, old_y = self.camera_x, self.camera_y
        self.camera_x = max(
            0, min(self.view.map_width - self.view.viewport_width, old_x + dx))
        self.camera_y = max(
            0, min(self.view.map_height - self.view.viewport_height, old_y + dy))
        moved_x, moved_y = self.camera_x - old_x, self.camera_y - old_y
        if not (moved_x or moved_y):
            return
        self.cursor_x = max(0, min(self.view.map_width - 1, self.cursor_x + moved_x))
        self.cursor_y = max(0, min(self.view.map_height - 1, self.cursor_y + moved_y))
        await self._load()

    def _refresh_widgets(self) -> None:
        view = self.view
        if view is None:
            return
        self.query_one(SurveyMapView).refresh()
        self.query_one("#survey-status", Static).update(self._status())

    def _status(self) -> Text:
        assert self.view is not None
        v = self.view
        out = Text()
        out.append(f"SURVEY · {v.planet}\n", "bold")
        if v.can_land:
            out.append("\nSELECT DROP SITE\n", "bold bright_yellow")
            out.append("Darkened ground is refused — water, peaks, ice, or cut off from\n"
                       "the contacts. Anything in normal colour will take the shuttle.\n",
                       "grey70")
            here = "this cell will do" if self.cursor_is_landable() else "not here"
            out.append(f"cursor: {here}\n",
                       "bright_green" if self.cursor_is_landable() else "red")
            out.append("\nEnter to set down · Esc aborts to orbit\n", "grey66")
            return out
        out.append(f"local turn {v.local_turn} · main turns {v.turns_remaining}\n", "grey58")
        frac = v.supplies / v.supplies_max if v.supplies_max else 0
        filled = round(14 * frac)
        color = "green" if frac > 0.5 else "yellow" if frac > 0.2 else "red"
        out.append(f"SUPPLIES {'█' * filled}{'░' * (14 - filled)} {v.supplies}\n", color)
        # Band 1 is saturated — the moment the scanner has nothing left to add and the
        # player should start reading the ground instead. It has to shout.
        scanner_style = ("bold bright_yellow" if v.scanner_band == 1
                         else "bold bright_cyan" if v.scanner_band else "grey58")
        out.append(f"SCANNER  {v.scanner}\n", scanner_style)
        out.append(f"overlay {self.overlay} · next {v.main_turn_cost}-turn charge at local "
                   f"turn {v.next_main_turn_at}\n", "grey58")
        out.append("\nCONTACTS\n", "bold")
        for contact in v.contacts:
            if contact.found:
                out.append(f" ✦ {contact.name[:25]}\n", "gold1")
            else:
                suffix = " — narrowed" if contact.hinted else " — area marked"
                out.append(f" ? contact {contact.contact_id}{suffix}\n",
                           "bright_cyan" if contact.hinted else "grey70")
        if v.settlements:
            out.append("\nSETTLEMENTS\n", "bold")
            for town in v.settlements:
                tag = "will share" if town.hint_available else "nothing left to tell"
                out.append(f" ◇ {town.name[:16]:<16} {tag}\n",
                           "white" if town.hint_available else "grey42")
        out.append("\n")
        if v.outcome is not None:
            done = v.outcome == "complete"
            resolved = sum(1 for c in v.contacts if c.found)
            out.append("═" * 26 + "\n", "bold")
            out.append("SURVEY COMPLETE\n" if done else "RECALLED — SUPPLIES SPENT\n",
                       "bold bright_green" if done else "bold yellow")
            out.append(f"{resolved}/{len(v.contacts)} contacts resolved\n", "grey70")
            out.append("V on a ✦ revisits it\n", "grey66")
            out.append("Esc extracts to orbit\n", "grey66")
        else:
            out.append("M march · X dig · T talk\n", "grey66")
            out.append("V view find · Z log · ? help\n", "grey66")
        return out

    def is_settlement_plaza(self, cell: GroundCellDTO) -> bool:
        """The town's real open centre, as projected — not a guess (the old heuristic
        scattered plaza wells across the streets)."""
        if not cell.settlement_id or self.view is None:
            return False
        town = next((t for t in self.view.settlements
                     if t.settlement_id == cell.settlement_id), None)
        return town is not None and (cell.x, cell.y) == (town.plaza_x, town.plaza_y)

    async def on_key(self, event: events.Key) -> None:
        if self._landing_playing:  # any key skips the descent
            self._end_landing()
            event.stop()
            return
        moves = {
            "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
            "k": (0, -1), "j": (0, 1), "h": (-1, 0), "l": (1, 0),
        }
        if event.key in moves:
            dx, dy = moves[event.key]
            await self.set_cursor(self.cursor_x + dx, self.cursor_y + dy)
            event.stop()
            return
        if event.key in ("H", "J", "K", "L"):
            dx, dy = moves[event.key.lower()]
            await self.set_cursor(self.cursor_x + dx * 8, self.cursor_y + dy * 4)
            event.stop()
            return
        pans = {"w": (0, -4), "s": (0, 4), "a": (-8, 0), "d": (8, 0)}
        if event.key in pans:
            await self._pan(*pans[event.key])
            event.stop()

    async def _apply(self, command: Any) -> tuple[Any, ...] | None:
        try:
            events_out = await self._client.apply(command)
        except MovementError as exc:
            notify_warning(self, str(exc))
            return None
        log = self.query_one("#survey-log", RichLog)
        for event in events_out:
            line = await self._client.describe_event(event)
            if line:
                # from_markup, not Text(): the log is a markup log and describe_event
                # lines may carry their own emphasis.
                log.write(Text.from_markup(
                    line, style=_EVENT_STYLES.get(type(event), "white")))
        return events_out

    async def action_confirm(self) -> None:
        """Enter means "commit the cursor": set down while inbound, march once landed."""
        if self.view is not None and self.view.can_land:
            await self.action_land()
            return
        await self.action_march()

    async def action_march(self) -> None:
        if self.view is None or not self.view.can_move:
            return
        if await self._apply(
            GroundMove(self.view.operation_id, self.cursor_x, self.cursor_y)
        ) is None:
            return
        await self._load(cursor_to_explorer=True)

    async def action_dig(self) -> None:
        if self.view is None or not self.view.can_dig:
            return
        before = {(c.x, c.y) for c in self.view.cells if c.dug}
        events_out = await self._apply(SurveyDig(self.view.operation_id))
        if events_out is None:
            return
        excavated = next((e for e in events_out if isinstance(e, SurveySiteExcavated)), None)
        await self._load()
        # The trench radius is a server-side rule, so light up whatever ground actually
        # turned over rather than re-deriving the shape from config.
        if self.view is not None:
            trench = {(c.x, c.y) for c in self.view.cells if c.dug} - before
            self._flash(trench, "on orange3")
            found = {(c.x, c.y) for c in self.view.cells if c.found_contact_id}
            if excavated is not None:
                self._flash(found, "on yellow")
        if excavated is not None and self.view is not None:
            contact = next((c for c in self.view.contacts
                            if c.discovery_id == excavated.discovery_id), None)
            if contact is not None:
                self.app.push_screen(SurveyFindModal(contact, first=True))

    async def action_talk(self) -> None:
        if self.view is None or not self.view.can_talk:
            return
        events_out = await self._apply(SurveyTalk(self.view.operation_id))
        if events_out is None:
            return
        await self._load()
        # A narrowed circle is a quiet change on a busy map — mark where it was earned.
        hinted = any(isinstance(e, SurveyTalked) and e.hinted_id >= 0 for e in events_out)
        if hinted and self.view is not None:
            self._flash({(self.view.explorer_x, self.view.explorer_y)}, "on yellow")

    def action_view_find(self) -> None:
        if self.view is None:
            return
        cell = next((c for c in self.view.cells
                     if (c.x, c.y) == (self.cursor_x, self.cursor_y)), None)
        if cell is None or not cell.found_contact_id:
            self.notify("No excavated site under the cursor.", timeout=2)
            return
        contact = next((c for c in self.view.contacts
                        if c.contact_id == cell.found_contact_id), None)
        if contact is not None:
            self.app.push_screen(SurveyFindModal(contact, first=False))

    def live_flashes(self) -> dict[tuple[int, int], tuple[str, float]]:
        """Drop expired flashes and return what is still lit."""
        now = time.monotonic()
        self._flashes = {k: v for k, v in self._flashes.items() if v[1] > now}
        return self._flashes

    def _flash(self, cells: Iterable[tuple[int, int]], style: str) -> None:
        until = time.monotonic() + _FLASH_SECONDS
        for cell in cells:
            self._flashes[cell] = (style, until)
        if self._flashes:
            self.set_timer(_FLASH_SECONDS + 0.05, self._refresh_widgets)

    def cursor_is_landable(self) -> bool:
        """Whether the cell under the cursor is an advertised drop site."""
        if self.view is None:
            return False
        cell = next((c for c in self.view.cells
                     if (c.x, c.y) == (self.cursor_x, self.cursor_y)), None)
        return cell is not None and cell.landing_site

    async def action_land(self) -> None:
        if self.view is None or not self.view.can_land:
            return
        if not self.cursor_is_landable():
            notify_warning(self, "The shuttle cannot set down there — pick open, level ground.")
            return
        target = (self.cursor_x, self.cursor_y)
        if await self._apply(
            SurveyLand(self.view.operation_id, *target)
        ) is None:
            return
        await self._load(cursor_to_explorer=True)
        self._play_landing(*target)

    def _play_landing(self, x: int, y: int) -> None:
        self._anim_frames = _landing_frames(x, y)
        self._advance_landing()

    def _advance_landing(self) -> None:
        if not self._anim_frames:
            self._end_landing()
            return
        frame = self._anim_frames.pop(0)
        self.anim_cells = frame.cells
        self.anim_step += 1
        if frame.log:
            self.query_one("#survey-log", RichLog).write(Text.from_markup(frame.log))
        self.query_one(SurveyMapView).refresh()
        self._anim_timer = self.set_timer(_LANDING_TICK, self._advance_landing)

    def _end_landing(self) -> None:
        """Clear the overlay and stop the clock — also the skip path, so a keypress during
        the descent lands you immediately rather than replaying the rest."""
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

    def action_log_expand(self) -> None:
        self.log_expanded = not self.log_expanded
        self.query_one("#survey-log", RichLog).styles.height = (
            _LOG_EXPANDED_H if self.log_expanded else _LOG_COLLAPSED_H)

    def action_overlay(self) -> None:
        self.overlay = _OVERLAYS[(_OVERLAYS.index(self.overlay) + 1) % len(_OVERLAYS)]
        self._refresh_widgets()

    async def action_extract(self) -> None:
        if self.view is None:
            self.app.pop_screen()
            return
        if await self._apply(ExtractGroundOperation(self.view.operation_id)) is not None:
            self.app.pop_screen()
