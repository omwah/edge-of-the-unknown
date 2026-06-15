"""PlanetScreen — orbit view (UI_MOCKUPS.md §3).

Phase-2 screen, stubbed here so the sector view's planet line has somewhere to
go. Content mirrors the §3 wireframe (Terra Nova, a Core world).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.tui import sprites
from edge.tui.dummy import sample_surface
from edge.tui.screens.surface import SurfaceScreen


class PlanetScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Break orbit"),
        Binding("d", "descend", "Descend"),
        Binding("t", "noop", "Trade"),
        Binding("c", "noop", "Claim"),
    ]

    CSS = """
    PlanetScreen #orbit-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    PlanetScreen #orbit-main { height: 1fr; }
    PlanetScreen #orbit-body { width: 2fr; padding: 1 2; }
    PlanetScreen #orbit-art {
        width: 1fr; height: 1fr; content-align: center top; text-align: center;
        color: $primary; text-style: bold;
    }
    PlanetScreen .section { margin-top: 1; }
    """

    _PTYPE = "terrestrial, warm"

    def __init__(self, planet_name: str) -> None:
        super().__init__()
        self._name = planet_name

    def compose(self) -> ComposeResult:
        yield Static(f"ORBIT · {self._name} · {self._PTYPE}", id="orbit-title")
        with Horizontal(id="orbit-main"):
            with VerticalScroll(id="orbit-body"):
                yield Static("Owner    [cyan]Federation[/] (Core world)        Citadel  Lv 2")
                yield Static(
                    "Habitability  [yellow]██████████░░[/] high     Colonists  1,240,000"
                )
                yield Static("Yield profile   Fuel (low)   Organics (high)   Equip (med)")
                yield Static(
                    "[green]#[/] Orbital starbase — OPERATIONAL  (defends for owner)\n"
                    "    reactor [+]  screens [+]  gun [+]",
                    classes="section",
                )
                yield Static(
                    "Stores   Ore 8,200   Org 31,400   Equ 5,100   Ftrs 900",
                    classes="section",
                )
                yield Static(
                    "Surface sites detected:  [magenta]*[/] 2   (1 hidden — sensors Tier II)",
                    classes="section",
                )
            yield Static("\n".join(sprites.pick_planet_large(self._PTYPE)), id="orbit-art")
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_descend(self) -> None:
        self.app.push_screen(SurfaceScreen(sample_surface()))

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
