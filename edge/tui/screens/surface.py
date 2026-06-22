"""SurfaceScreen — planet descent & site exploration, wired to the live service (§7, WP6).

A full-width top-down terrain panel sits over a bordered two-column panel: the site
list on the left drives the detail on the right via row highlighting. `E` surveys the
next site (sensor-gated for Rare+ sites), `L` logs the highlighted revealed site to the
codex, `Esc` ascends to orbit. With no service (screenshot harness) it shows a static
sample. The terrain art is composited in the TUI so the site markers ([1]/[2]/[?]) are
stamped back over the procedural map (the art engine doesn't carry those overlays).
"""

from __future__ import annotations

import random

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from edge.core.economy import EconomyError
from edge.core.dto import SurfaceDTO, SurfaceSite
from edge.core.engine_room import EngineRoomError
from edge.core.movement import MovementError
from edge.core.rules import Explore, Salvage
from edge.server.service import GameService
from edge.tui import art_adapter

# Site markers ride a solid light "plate" with dark text, so they read as labels on top
# of the terrain instead of fighting its colours (a dark plate blends with dark terrain).
_LABEL_BG = "grey85"
_MARKER_FG = "grey11"       # revealed-site marker, e.g. "[1]"
_MARKER_MASKED_FG = "red3"  # unsurveyed hidden site, "[?]"
_LABEL_FG = "blue3"         # the slug label text


def _stamp_site_markers(grid: list[list[tuple[str, Style | None]]],
                        sites: list[SurfaceSite], planet_id: int) -> None:
    """Stamp each site's marker (and a slug label, once revealed) onto the terrain grid.

    The art-engine terrain carries no site overlays, so we re-stamp them here over the
    composited map. Positions are seeded by `planet_id` (cosmetic, so exact replay isn't
    required) with a per-row keep-out so markers don't collide.
    """
    h = len(grid)
    w = len(grid[0]) if h else 0
    if not h or not w:
        return
    rng = random.Random(f"{planet_id}|surface-markers")
    placed: list[tuple[int, int, int]] = []  # (row, x0, x1) keep-out boxes

    def free(y: int, x0: int, x1: int) -> bool:
        return all(not (y == ry and x0 <= rx1 + 1 and rx0 - 1 <= x1) for ry, rx0, rx1 in placed)

    def stamp(y: int, x: int, text: str, fg: str) -> None:
        # A solid light plate behind every glyph, so dark marker/label text reads as a
        # label on top of the terrain instead of fighting its colours.
        st = Style.parse(fg) + Style(bold=True, bgcolor=_LABEL_BG)
        for i, ch in enumerate(text):
            if 0 <= x + i < w:
                grid[y][x + i] = (ch, st)

    for site in sites:
        masked = site.marker.strip() == "[?]"
        marker_fg = _MARKER_MASKED_FG if masked else _MARKER_FG
        revealed = not masked and site.status != "unexplored"
        label = site.name.strip().lower().replace(" ", "-") if revealed else ""
        full = site.marker + (" " + label if label else "")
        for _ in range(60):
            y = rng.randint(0, h - 1)
            x = rng.randint(1, max(1, w - len(full) - 1))
            if free(y, x, x + len(full) - 1):
                stamp(y, x, site.marker, marker_fg)
                if label:  # include the separator space so the plate is continuous
                    stamp(y, x + len(site.marker), " " + label, _LABEL_FG)
                placed.append((y, x, x + len(full) - 1))
                break


class SurfaceTerrain(Static):
    """The descent terrain map: procedural art terrain with site markers composited over it.

    Renders to the panel's live size, so the map fills the full width and the configured
    height. When `ptype` is empty (screenshot harness) it falls back to the DTO's
    pre-rendered rows, which already carry the server-side markers.
    """

    def __init__(self, surface: SurfaceDTO, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._s = surface

    def on_resize(self) -> None:
        self.refresh()

    def render(self) -> Text:
        s = self._s
        w, h = self.size.width, self.size.height
        if w < 4 or h < 1:
            return Text("")
        if s.ptype:
            art = art_adapter.sprite("terrain", s.ptype, seed=s.planet_id, width=w, height=h)
            # Terrain is opaque — keep space-glyph backgrounds (the colour lives there),
            # unlike the starfield-transparent SectorScene composite.
            cells = art_adapter.text_to_cells(art, keep_space_style=True)
        else:  # fallback rows already include the server-stamped markers — show as-is
            return Text.from_markup("\n".join(s.terrain))
        grid: list[list[tuple[str, Style | None]]] = [[(" ", None)] * w for _ in range(h)]
        for y in range(min(h, len(cells))):
            for x in range(min(w, len(cells[y]))):
                grid[y][x] = cells[y][x]
        _stamp_site_markers(grid, s.sites, s.planet_id)
        out = Text()
        for y in range(h):
            for ch, style in grid[y]:
                out.append(ch, style=style)
            if y < h - 1:
                out.append("\n")
        return out


class SurfaceScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Ascend to orbit"),
        Binding("e", "explore", "Survey site"),
        Binding("l", "log", "Log to codex"),
    ]

    CSS = """
    SurfaceScreen #surface-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    SurfaceScreen #terrain {
        width: 1fr; border: round $primary; padding: 0 1;
    }
    /* The site list + detail share one bordered panel under the terrain. */
    SurfaceScreen #sites-panel { height: 1fr; border: round $secondary; }
    SurfaceScreen #sites-row { height: 1fr; }
    SurfaceScreen #sites { width: 2fr; height: 1fr; }
    SurfaceScreen #site-detail {
        width: 1fr; height: 1fr; padding: 0 1; border-left: solid $secondary;
    }
    """

    def __init__(self, surface: SurfaceDTO, service: GameService | None = None, pid: int = 1) -> None:
        super().__init__()
        self._surface = surface
        self._service = service
        self._pid = pid

    def compose(self) -> ComposeResult:
        s = self._surface
        yield Static(
            f"SURFACE · {s.planet}        [dim]descent fuel: {s.descent_fuel}[/]",
            id="surface-title",
        )
        ui = getattr(self.app, "ui_config", None)
        terrain = SurfaceTerrain(s, id="terrain")
        terrain.styles.height = ui.surface_terrain_height if ui is not None else 12
        terrain.border_title = f"terrain · {s.terrain_blurb}" if s.terrain_blurb else "terrain"
        yield terrain
        with Container(id="sites-panel"):
            with Horizontal(id="sites-row"):
                yield DataTable(id="sites", cursor_type="row")
                detail = Static(id="site-detail")
                detail.border_title = "site"
                yield detail
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#sites", DataTable)
        table.add_columns("", "Site", "Rarity", "Status")
        for site in self._surface.sites:
            table.add_row(site.marker, site.name, site.rarity, site.status)
        if self._surface.sites:
            self._show_site(self._surface.sites[0])

    def _show_site(self, site: SurfaceSite) -> None:
        detail = self.query_one("#site-detail", Static)
        lines = [
            f"[b]{site.marker} {site.name}[/]",
            f"rarity  {site.rarity}",
            f"status  {site.status}",
            "",
            "Payload" + ("" if site.status == "logged" else " (on log)"),
            *[f"  - {line}" for line in site.payload],
        ]
        if site.salvageable:
            lines += ["", "[green]\\[L][/] log to codex"]
        detail.update("\n".join(lines))

    def on_data_table_row_highlighted(self, msg: DataTable.RowHighlighted) -> None:
        if 0 <= msg.cursor_row < len(self._surface.sites):
            self._show_site(self._surface.sites[msg.cursor_row])

    def _highlighted(self) -> SurfaceSite | None:
        row = self.query_one("#sites", DataTable).cursor_row
        if 0 <= row < len(self._surface.sites):
            return self._surface.sites[row]
        return None

    def action_explore(self) -> None:
        if self._service is None:
            self.notify("Not wired in the skeleton.", timeout=2)
            return
        try:
            self._service.apply(self._pid, Explore(planet_id=self._surface.planet_id))
        except (EconomyError, MovementError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.notify("Site surveyed.", timeout=2)
        self._reload()

    def action_log(self) -> None:
        if self._service is None:
            self.notify("Not wired in the skeleton.", timeout=2)
            return
        site = self._highlighted()
        if site is None or not site.salvageable:
            self.notify("Survey a site first, then log it.", timeout=2)
            return
        try:
            self._service.apply(self._pid, Salvage(discovery_id=site.discovery_id))
        except (EconomyError, EngineRoomError, MovementError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self.notify(f"Logged {site.name} to the codex.", timeout=2)
        self._reload()

    def _reload(self) -> None:
        """Re-open the screen on a fresh surface view after a survey/log."""
        assert self._service is not None
        self.app.pop_screen()
        self.app.push_screen(
            SurfaceScreen(self._service.surface_view(self._pid, self._surface.planet_id),
                          self._service, self._pid))

    def action_back(self) -> None:
        self.app.pop_screen()
