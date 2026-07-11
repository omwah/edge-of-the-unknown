"""SurfaceScreen — planet descent & site exploration, wired to the live service (§7, WP6).

A full-width top-down terrain panel sits over a bordered two-column panel: the site
list (all the text, including each site's find) on the left drives the selected site's
entity art on the right via row highlighting. A site's name, rarity, and sprite stay
obscured (static "snow") until surveyed. `E` surveys the next site (sensor-gated for
Rare+ sites) — which logs it to the codex and uncovers its find — and `T` then takes
that find aboard (optional: leave it for the next person), `Esc` ascends to orbit. With
no service (screenshot harness) it shows a static sample. The terrain art is composited in
the TUI so the site markers ([1]/[2]/[?]) are stamped back over the procedural map (the art
engine doesn't carry those overlays).
"""

from __future__ import annotations

import random
from typing import Any

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Static

from edge.core.economy import EconomyError
from edge.core.dto import SurfaceDTO, SurfaceSite
from edge.core.engine_room import EngineRoomError
from edge.core.movement import MovementError
from edge.core.events import DiscoveryCollected, SiteExplored
from edge.core.rules import Explore, Salvage
from edge.server.service import GameService
from edge.tui.chrome import notify_warning
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

    def __init__(self, surface: SurfaceDTO, **kwargs: Any) -> None:
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


# Display labels for the raw DTO status strings (kept stable for the core/tests); the
# screen relabels them to match the survey-logs / take-is-optional flow.
_STATUS_LABEL = {"unexplored": "unsurveyed", "explored": "surveyed", "logged": "surveyed"}


class SiteArt(Static):
    """The right-hand panel: procedural entity art for the highlighted surface site.

    Until a site is surveyed it renders as TV-"snow" static (the art engine's
    `static` sprite) so its identity isn't given away; once surveyed it renders the
    `discovery` sprite for the site's kind, sized live to the panel.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._kind = ""
        self._seed = 0
        self._surveyed = False

    def show(self, kind: str, seed: int, surveyed: bool) -> None:
        self._kind, self._seed, self._surveyed = kind, seed, surveyed
        self.refresh()

    def on_resize(self) -> None:
        self.refresh()

    def render(self) -> Text:
        w, h = self.size.width, self.size.height
        if w < 4 or h < 1:
            return Text("")
        if not self._surveyed:  # withhold the sprite — show static until surveyed
            return art_adapter.sprite("static", "snow", seed=self._seed, width=w, height=h)
        if not self._kind:
            return Text("unsurveyed\nrun a sensor sweep", style="dim", justify="center")
        return art_adapter.sprite("discovery", self._kind, seed=self._seed, width=w, height=h)


class SurfaceScreen(Screen[None]):
    BINDINGS = [
        Binding("escape", "back", "Ascend to orbit"),
        Binding("e", "explore", "Survey site"),
        Binding("t", "take", "Take find"),
    ]

    HELP_TITLE = "Planet surface"

    CSS = """
    SurfaceScreen #surface-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    SurfaceScreen #terrain {
        width: 1fr; border: round $primary; padding: 0 1;
    }
    /* The site list (all the text) sits left; the selected site's art fills the right. */
    SurfaceScreen #sites-panel { height: 1fr; border: round $secondary; }
    SurfaceScreen #sites-row { height: 1fr; }
    SurfaceScreen #sites { width: 3fr; height: 1fr; }
    SurfaceScreen #site-detail-column { width: 2fr; height: 1fr; }
    SurfaceScreen #site-art {
        width: 1fr; height: 1fr; padding: 0 1; border-left: solid $secondary;
        content-align: center middle;
    }
    SurfaceScreen #site-detail { height: auto; min-height: 5; padding: 0 1; }
    SurfaceScreen #site-actions { height: auto; padding: 0 1; }
    SurfaceScreen #site-actions Button { margin-right: 1; }
    SurfaceScreen.compact #terrain { display: none; }
    SurfaceScreen.compact #sites { width: 1fr; height: 1fr; }
    SurfaceScreen.compact #sites-row { layout: vertical; }
    SurfaceScreen.compact #site-detail-column { width: 1fr; height: auto; }
    SurfaceScreen.compact #site-art { display: none; }
    SurfaceScreen.compact #site-detail { min-height: 4; border-top: solid $secondary; }
    SurfaceScreen.compact #site-actions { padding: 0; }
    SurfaceScreen.wide #sites { width: 4fr; }
    SurfaceScreen.wide #site-detail-column { width: 3fr; }
    """

    def __init__(self, surface: SurfaceDTO, service: GameService | None = None, pid: int = 1,
                 cursor: int = 0) -> None:
        super().__init__()
        self._surface = surface
        self._service = service
        self._pid = pid
        self._cursor = cursor

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
                with Vertical(id="site-detail-column"):
                    yield Static("Select a site.", id="site-detail")
                    with Horizontal(id="site-actions"):
                        yield Button("Survey next [E]", id="btn-survey", variant="primary")
                        yield Button("Collect [T]", id="btn-collect")
                    art = SiteArt(id="site-art")
                    art.border_title = "site"
                    yield art
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#sites", DataTable)
        table.add_columns("", "Site", "Rarity", "Status", "Find")
        for site in self._surface.sites:
            surveyed = site.status != "unexplored"
            if not surveyed:
                find: Text = Text("hidden", style="dim")
            elif site.status == "logged":  # the taken indicator lives in the Find column now
                find = Text("taken", style="dim")
            else:
                find = Text.from_markup("; ".join(site.payload))
            table.add_row(
                site.marker,
                site.name if surveyed else "(unsurveyed)",  # withhold name until surveyed
                site.rarity if surveyed else "?",            # withhold rarity until surveyed
                _STATUS_LABEL.get(site.status, site.status),
                find,
            )
        if self._surface.sites:
            row = min(max(self._cursor, 0), len(self._surface.sites) - 1)
            table.move_cursor(row=row, animate=False)
            self._show_site(self._surface.sites[row])
        else:
            self.query_one("#btn-survey", Button).disabled = True
            self.query_one("#btn-collect", Button).disabled = True

    def _show_site(self, site: SurfaceSite) -> None:
        self.query_one("#site-art", SiteArt).show(
            site.kind, site.discovery_id, site.status != "unexplored")
        surveyed = site.status != "unexplored"
        name = site.name if surveyed else "Unsurveyed site"
        rarity = site.rarity if surveyed else "unknown"
        status = _STATUS_LABEL.get(site.status, site.status)
        if not surveyed:
            required = "Survey this site to identify it and reveal its find."
            reward = "Reward  hidden until surveyed"
        elif site.salvageable:
            required = "Survey complete · collect the find or leave it in place."
            reward = "Reward  " + ("; ".join(site.payload) or "none")
        else:
            required = "Survey complete · find already collected."
            reward = "Reward  collected"
        self.query_one("#site-detail", Static).update(
            f"[b]{site.marker} {name}[/]\nRarity  {rarity}   Status  {status}\n"
            f"{required}\n{reward}"
        )
        self.query_one("#btn-survey", Button).disabled = not self._surface.explorable
        self.query_one("#btn-collect", Button).disabled = not site.salvageable

    def on_data_table_row_highlighted(self, msg: DataTable.RowHighlighted) -> None:
        if 0 <= msg.cursor_row < len(self._surface.sites):
            self._show_site(self._surface.sites[msg.cursor_row])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-survey":
            self.action_explore()
        elif event.button.id == "btn-collect":
            self.action_take()

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
            events = self._service.apply(self._pid, Explore(planet_id=self._surface.planet_id))
        except (EconomyError, MovementError) as exc:
            notify_warning(self, str(exc))
            return
        # The survey logs the find to the codex and uncovers it; find the freshly
        # revealed site in the reloaded view to name what's there to take (or leave).
        revealed = next((e for e in events if isinstance(e, SiteExplored)), None)
        find = ""
        if revealed is not None:
            site = next((s for s in self._service.surface_view(self._pid, self._surface.planet_id).sites
                         if s.discovery_id == revealed.discovery_id), None)
            if site is not None:
                find = "; ".join(Text.from_markup(p).plain for p in site.payload)
        self.notify(f"Surveyed and logged{f' — find: {find}' if find else ''}.", timeout=4)
        self._reload()

    def action_take(self) -> None:
        if self._service is None:
            self.notify("Not wired in the skeleton.", timeout=2)
            return
        site = self._highlighted()
        if site is None or not site.salvageable:
            self.notify("Survey a site first, then take its find.", timeout=2)
            return
        try:
            events = self._service.apply(self._pid, Salvage(discovery_id=site.discovery_id))
        except (EconomyError, EngineRoomError, MovementError) as exc:
            notify_warning(self, str(exc))
            return
        collected = next((e for e in events if isinstance(e, DiscoveryCollected)), None)
        gain = f" — you took {collected.reward}" if collected is not None and collected.reward else ""
        self.notify(f"Collected {site.name}{gain}.", timeout=4)
        self._reload()

    def _reload(self) -> None:
        """Re-open the screen on a fresh surface view after a survey/log."""
        assert self._service is not None
        cursor = self.query_one("#sites", DataTable).cursor_row
        self.app.pop_screen()
        self.app.push_screen(
            SurfaceScreen(self._service.surface_view(self._pid, self._surface.planet_id),
                          self._service, self._pid, cursor=cursor))

    def action_back(self) -> None:
        self.app.pop_screen()
