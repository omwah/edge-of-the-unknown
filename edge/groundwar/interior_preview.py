"""Cloud City station-interior preview (GW-WP15).

A **read-only** dev screen for reviewing `edge.core.groundwar.interior`
generation and `edge.art.interior` styling. There is no reducer to drive yet —
`edge.core.groundwar.access.ground_access` still routes every Cloud City to
`OrbitalOnly` until `groundwar.cloud_city_assault_enabled` opens in GW-WP16 — so
this screen calls the generator and art module directly and renders the result
plus a glyph legend. No `GameService`/`LocalClient`/command dispatch is
involved, unlike `SetupScreen`'s assault/expedition modes, since nothing
consumes this state yet.
"""

from __future__ import annotations

import random as _random

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Static

from edge.art.interior import LEGEND, style_interior
from edge.core.config import GameConfig
from edge.core.groundwar.interior import generate_interior


class CloudCityPreviewScreen(Screen[None]):
    """Renders one generated interior layout; `[`/`]` resize the city, `r` rerolls."""

    DEFAULT_CSS = """
    CloudCityPreviewScreen { layout: horizontal; }
    #cc-map-scroll { width: 1fr; }
    #cc-legend { width: 34; border-left: solid $primary; padding: 0 1; }
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("r", "reroll", "Reroll seed"),
        Binding("bracketleft", "smaller", "Smaller city"),
        Binding("bracketright", "bigger", "Bigger city"),
    ]

    def __init__(self, config: GameConfig, city_size: int, seed: int) -> None:
        super().__init__()
        self.config = config
        assert config.groundwar is not None
        self.city_size = city_size
        self.seed = seed

    def compose(self) -> ComposeResult:
        with Horizontal():
            with VerticalScroll(id="cc-map-scroll"):
                yield Static(id="cc-map")
            with VerticalScroll(id="cc-legend"):
                yield Static(id="cc-legend-body")

    def on_mount(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        assert self.config.groundwar is not None
        layout = generate_interior(self.seed, self.city_size, self.config.groundwar.cloud_city)
        rng = _random.Random(f"cloud-city-preview|{self.seed}|{self.city_size}")
        grid = style_interior(rng, layout)
        text = Text(no_wrap=True)
        for y, row in enumerate(grid):
            for ch, fg, bg in row:
                text.append(ch, f"{fg} on {bg}")
            if y < len(grid) - 1:
                text.append("\n")
        self.query_one("#cc-map", Static).update(text)

        legend = Text()
        legend.append(f"Cloud City size {self.city_size} · seed {self.seed}\n\n", "bold")
        for glyph, label, fg, bg in LEGEND:
            legend.append(f"{glyph:6} ", f"{fg} on {bg}")
            legend.append(f"{label}\n", "grey70")
        legend.append(
            "\n[ / ] size · r reroll seed · esc back\n"
            f"{len(layout.deployment_zones)} deployment zones · "
            f"{len(layout.defender_slots)} defender slots · "
            f"{len(layout.lift_links)} lift pair(s)\n",
            "grey54")
        self.query_one("#cc-legend-body", Static).update(legend)

    def action_reroll(self) -> None:
        self.seed = _random.randrange(1 << 31)
        self._refresh()

    def action_smaller(self) -> None:
        self.city_size = max(1, self.city_size - 1)
        self._refresh()

    def action_bigger(self) -> None:
        assert self.config.groundwar is not None
        self.city_size = self.city_size + 1  # generation has no upper bound of its own
        self._refresh()
