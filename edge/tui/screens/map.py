"""MapScreen — the galactic map (UI_MOCKUPS.md §10).

Phase-1 shell: a banded overview (Core → Hub → Frontier → Void) drawn from a
`MapDTO`, with neutral-lane connectors between alliance home clusters. Zoom,
search, and the per-sector inspector are stubbed; clicking a band notifies.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.server.service import GameService
from edge.tui.widgets import MapBandPanel, MapView


class MapScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("m", "back", "Back"),
        Binding("plus", "noop", "Zoom in"),
        Binding("minus", "noop", "Zoom out"),
        Binding("slash", "noop", "Search"),
    ]

    CSS = """
    MapScreen #map-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    MapScreen #map-legend {
        height: auto; padding: 0 1; border-top: solid $primary; color: $text-muted;
    }
    """

    _LEGEND = (
        "[reverse cyan]@[/] you   ─ warp   [yellow]~[/] neutral lane   "
        "[yellow]*[/] rumor   [green]o[/] planet   [magenta]P[/] port   "
        "[red]#[/] starbase   [red]?[/] unexplored"
    )

    def __init__(self, service: GameService, player_id: int) -> None:
        super().__init__()
        self._map = service.map_view(player_id)

    def compose(self) -> ComposeResult:
        m = self._map
        yield Static(
            f"GALACTIC MAP · you @ Sector {m.you_sector} · Band {m.you_band}",
            id="map-title",
        )
        yield MapView(self._map)
        yield Static(self._LEGEND, id="map-legend")
        yield Footer()

    def on_map_band_panel_picked(self, msg: MapBandPanel.Picked) -> None:
        self.notify(f"{msg.title} — sector inspector not wired in the skeleton.", timeout=2)

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
