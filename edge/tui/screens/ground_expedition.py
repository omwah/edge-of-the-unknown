"""Live survey expedition over the service/DTO boundary (GW-WP07).

This is the production sibling of ``edge.groundwar.expedition_ui``.  It owns only
cursor/camera/overlay presentation state: every move, dig, talk, and extraction is an
authoritative command, and every rendered fact comes back in ``SurveyExpeditionDTO``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, RichLog, Static

from edge.art.terrain import BIOME_COLORS, FEATURES_REGISTRY, readable_fg
from edge.core.dto import GroundCellDTO, SurveyContactDTO, SurveyExpeditionDTO
from edge.core.enums import DiscoveryKind
from edge.core.events import SurveySiteExcavated
from edge.core.groundwar.terrain import BIOME_BANDS
from edge.core.movement import MovementError
from edge.core.rules import ExtractGroundOperation, GroundMove, SurveyDig, SurveyTalk
from edge.core.surface_finds import FIND_KINDS, surface_find_kind
from edge.groundwar.findart import generate_find_art
from edge.server.client import GameClient
from edge.tui import art_adapter
from edge.tui.chrome import EdgeScreen, notify_warning


_HEAT = ("", "red3", "dark_orange3", "grey46", "grey30")
_OVERLAYS = ("scanner", "range", "off")


@lru_cache(maxsize=None)
def _feature_style(ptype: str, feature: str) -> tuple[str, str]:
    """Resolve a stable glyph/style without the secret operation seed."""
    choices = FEATURES_REGISTRY.get(feature, [("?", 1)])
    visible = [char for char, _weight in choices if char != " "]
    char = visible[0] if visible else " "
    layout = BIOME_BANDS.get(ptype)
    colors = BIOME_COLORS.get(ptype, [])
    if layout is None:
        return char, "white"
    for index, (_threshold, name) in enumerate(layout.bands):
        if name == feature and index < len(colors):
            fg, bg = colors[index]
            return char, f"{readable_fg(fg, bg)} on {bg}"
    return char, "white"


class SurveyFindModal(ModalScreen[None]):
    """The excavated artifact card; all identity comes from the refreshed DTO."""

    BINDINGS = [Binding("escape", "close", "Close"), Binding("enter", "close", "Close")]
    CSS = """
    SurveyFindModal { align: center middle; background: $background 60%; }
    SurveyFindModal #find-box {
        width: 58; max-width: 100%; height: auto; max-height: 95%;
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
        with Vertical(id="find-box"):
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
        frame_key = id(view), self.host_screen.overlay
        if frame_key != self._frame_key:
            self._frame_key = frame_key
            self._frame = self._render_frame(view)
        assert self._frame is not None
        out = self._frame.copy()
        col = self.host_screen.cursor_x - view.viewport_x
        row = self.host_screen.cursor_y - view.viewport_y
        if 0 <= col < view.viewport_width and 0 <= row < view.viewport_height:
            offset = row * (view.viewport_width + 1) + col
            out.stylize("black on bright_white", offset, offset + 1)
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
        if (cell.x, cell.y) == (view.explorer_x, view.explorer_y):
            return "@", "black on bright_green"
        if cell.found_contact_id:
            return "✦", "bold gold1 on grey19"
        if cell.dug:
            return "◌", "black on dark_goldenrod"
        if cell.clue:
            return "∴", "black on dark_goldenrod"
        if cell.blocked:
            return "█", "grey62 on grey30"
        if cell.settlement_id:
            return ("◉", "bright_cyan on grey15") if self.host_screen.is_settlement_plaza(cell) \
                else ("⌂", "navajo_white3 on grey23")
        char, style = _feature_style(view.ptype, cell.feature)
        if cell.search_ring:
            return char, f"{style.split(' on ')[0]} on " \
                f"{'dark_green' if cell.search_ring == 'hinted' else 'grey35'}"
        if self.host_screen.overlay == "scanner" and cell.heat:
            heat = _HEAT[min(cell.heat, len(_HEAT) - 1)]
            return char, f"{style.split(' on ')[0]} on {heat}"
        if self.host_screen.overlay == "range" and cell.reachable:
            return char, f"{style.split(' on ')[0]} on grey27"
        return char, style

    async def _on_click(self, event: events.Click) -> None:
        view = self.host_screen.view
        if view is not None:
            await self.host_screen.set_cursor(
                view.viewport_x + event.x, view.viewport_y + event.y)


class GroundExpeditionScreen(EdgeScreen):
    """Walk, scan, excavate, and talk through authoritative survey commands."""

    BINDINGS = [
        Binding("escape", "extract", "Extract"),
        Binding("m", "march", "March"),
        Binding("enter", "march", "March", show=False),
        Binding("x", "dig", "Dig"),
        Binding("t", "talk", "Talk"),
        Binding("v", "view_find", "View find"),
        Binding("o", "overlay", "Overlay"),
    ]
    HELP_TITLE = "Survey expedition"
    HELP = """\
Move the cursor with arrows or [b]hjkl[/] (click also works); [b]HJKL[/] moves it
quickly and [b]wasd[/] pans the map with the cursor riding along. Then [b]M[/]/Enter
to march. Marches halt when disturbed ground comes into sight. Follow the scanner
glow and marked search circles; stand on your best guess and [b]X[/] to dig.
[b]T[/] talks while inside a settlement, replenishing supplies and narrowing a
contact. [b]O[/] cycles scanner/range/clear overlays. Extraction is always legal
and preserves position and hints; trenches and supplies reset on the next descent."""

    CSS = """
    GroundExpeditionScreen #survey-main { height: 1fr; layout: horizontal; }
    GroundExpeditionScreen #survey-map { width: 1fr; height: 1fr; overflow: hidden; }
    GroundExpeditionScreen #survey-side {
        width: 34; height: 1fr; padding: 0 1; border-left: solid $primary;
    }
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
        self.overlay = "scanner"

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
        log.write("[b]Survey deployed.[/] Follow the scanner and marked circles; ? opens help.")

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
            self.cursor_x, self.cursor_y = first.explorer_x, first.explorer_y
            self.camera_x = max(0, first.explorer_x - width // 2)
            self.camera_y = max(0, first.explorer_y - height // 2)
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
        out.append(f"local turn {v.local_turn} · main turns {v.turns_remaining}\n", "grey58")
        frac = v.supplies / v.supplies_max if v.supplies_max else 0
        filled = round(14 * frac)
        color = "green" if frac > 0.5 else "yellow" if frac > 0.2 else "red"
        out.append(f"SUPPLIES {'█' * filled}{'░' * (14 - filled)} {v.supplies}\n", color)
        out.append(f"SCANNER  {v.scanner}\n", "bold bright_cyan")
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
                out.append(f" ◇ {town.name[:25]}\n")
        if v.outcome is not None:
            out.append(f"\n{v.outcome.upper()} — extract to orbit\n", "bold yellow")
        return out

    def is_settlement_plaza(self, cell: GroundCellDTO) -> bool:
        # A deterministic sparse plaza marker; settlement legality comes from can_talk.
        return bool(cell.settlement_id and (cell.x + cell.y + cell.settlement_id) % 11 == 0)

    async def on_key(self, event: events.Key) -> None:
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
                log.write(line)
        return events_out

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
        events_out = await self._apply(SurveyDig(self.view.operation_id))
        if events_out is None:
            return
        excavated = next((e for e in events_out if isinstance(e, SurveySiteExcavated)), None)
        await self._load()
        if excavated is not None and self.view is not None:
            contact = next((c for c in self.view.contacts
                            if c.discovery_id == excavated.discovery_id), None)
            if contact is not None:
                self.app.push_screen(SurveyFindModal(contact, first=True))

    async def action_talk(self) -> None:
        if self.view is None or not self.view.can_talk:
            return
        if await self._apply(SurveyTalk(self.view.operation_id)) is not None:
            await self._load()

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

    def action_overlay(self) -> None:
        self.overlay = _OVERLAYS[(_OVERLAYS.index(self.overlay) + 1) % len(_OVERLAYS)]
        self._refresh_widgets()

    async def action_extract(self) -> None:
        if self.view is None:
            self.app.pop_screen()
            return
        if await self._apply(ExtractGroundOperation(self.view.operation_id)) is not None:
            self.app.pop_screen()
