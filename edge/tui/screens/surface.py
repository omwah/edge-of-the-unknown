"""SurfaceScreen — planet descent & site exploration (UI_MOCKUPS.md §4).

Phase-2 screen, stubbed here so PlanetScreen's Descend action has somewhere to
go. A top-down terrain panel sits beside a detail panel for the highlighted
site; the site list below drives the detail via row highlighting. Explore,
sensor sweep, and codex logging are stubbed.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from edge.tui.dummy import SurfaceDTO, SurfaceSite


class SurfaceScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Ascend to orbit"),
        Binding("e", "noop", "Explore"),
        Binding("s", "noop", "Sensor sweep"),
        Binding("l", "noop", "Log to codex"),
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

    def __init__(self, surface: SurfaceDTO) -> None:
        super().__init__()
        self._surface = surface

    def compose(self) -> ComposeResult:
        s = self._surface
        yield Static(
            f"SURFACE · {s.planet}        [dim]descent fuel: {s.descent_fuel}[/]",
            id="surface-title",
        )
        with Horizontal(id="surface-top"):
            terrain = Static("\n".join(s.terrain), id="terrain")
            terrain.border_title = "terrain"
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
            "Payload (on explore)",
            *[f"  - {line}" for line in site.payload],
        ]
        detail.update("\n".join(lines))

    def on_data_table_row_highlighted(self, msg: DataTable.RowHighlighted) -> None:
        self._show_site(self._surface.sites[msg.cursor_row])

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
