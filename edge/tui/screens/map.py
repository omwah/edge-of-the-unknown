"""MapScreen — the galactic map (UI_MOCKUPS.md §10).

Phase-2 shell: the local sector ego-graph centered on the player's current
sector, drawn from a `LocalMapDTO` (gravity columns, fog of war, route overlay).
Zoom and search are stubbed.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.server.service import GameService
from edge.tui.widgets import LocalMapView


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
    """

    def __init__(self, service: GameService, player_id: int) -> None:
        super().__init__()
        self._map = service.map_view(player_id)

    def compose(self) -> ComposeResult:
        m = self._map
        yield Static(
            f"LOCAL MAP · you @ Sector {m.you_display} · Band {m.you_band}",
            id="map-title",
        )
        yield LocalMapView(self._map)
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
