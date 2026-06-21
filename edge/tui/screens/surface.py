"""SurfaceScreen — planet descent & site exploration, wired to the live service (§7, WP6).

A top-down terrain panel sits beside a detail panel for the highlighted site; the
site list below drives the detail via row highlighting. `E` surveys the next site
(sensor-gated for Rare+ sites), `L` logs the highlighted revealed site to the codex,
`Esc` ascends to orbit. With no service (screenshot harness) it shows a static sample.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from edge.core.economy import EconomyError
from edge.core.dto import SurfaceDTO, SurfaceSite
from edge.core.engine_room import EngineRoomError
from edge.core.movement import MovementError
from edge.core.rules import Explore, Salvage
from edge.server.service import GameService
from edge.tui import art_adapter


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
    SurfaceScreen #surface-top { height: 12; padding: 1 1; }
    SurfaceScreen #terrain {
        width: 3fr; height: 1fr; border: round $primary; padding: 0 1;
    }
    SurfaceScreen #site-detail {
        width: 2fr; height: 1fr; border: round $secondary; padding: 0 1;
        margin-left: 1;
    }
    SurfaceScreen #sites { height: auto; max-height: 8; margin: 0 1; }
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
        with Horizontal(id="surface-top"):
            # Procedural terrain from the art engine when the planet type is known;
            # fall back to the DTO's pre-rendered rows (screenshot harness / legacy).
            if s.ptype:
                body = art_adapter.sprite(
                    "terrain", s.ptype, seed=s.planet_id, width=52, height=8,
                )
            else:
                body = "\n".join(s.terrain)
            terrain = Static(body, id="terrain")
            terrain.border_title = f"terrain · {s.terrain_blurb}" if s.terrain_blurb else "terrain"
            yield terrain
            detail = Static(id="site-detail")
            detail.border_title = "site"
            yield detail
        yield DataTable(id="sites", cursor_type="row")
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
        detail.border_title = f"site {site.marker}"
        lines = [
            f"[b]{site.name}[/]",
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
