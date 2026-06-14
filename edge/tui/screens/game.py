"""GameScreen — the primary screen (UI_MOCKUPS.md §1)."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, RichLog, Static

from edge.tui.dummy import GameState
from edge.tui.screens.planet import PlanetScreen
from edge.tui.screens.stardock import StarDockScreen
from edge.tui.widgets import ClickableEntry, StatusSidebar, WarpButton, WarpGrid


class TopBar(Static):
    DEFAULT_CSS = """
    TopBar {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    """

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self._state = state

    def render(self) -> Text:
        s = self._state
        left = "EDGE OF THE UNKNOWN"
        right = f"turns {s.turns}/{s.max_turns}"
        return Text.assemble(left, ("  ", ""), right)


class SectorView(VerticalScroll):
    DEFAULT_CSS = """
    SectorView { width: 2fr; padding: 0 1; }
    SectorView #flavor { color: $text-muted; text-style: italic; }
    SectorView #contents { margin: 1 0; }
    SectorView .heading { color: $secondary; text-style: bold; }
    SectorView .spacer { height: 1; }
    """

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        sec = self._state.sector
        yield Static(f"[b cyan]{sec.region} - Sector {sec.sector_id}[/]", id="title")
        yield Static(f"░▒▓ {sec.flavor} ▓▒░", id="flavor")

        yield Static("", classes="spacer")
        yield Static("Ports", classes="heading")
        if sec.ports:
            for p in sec.ports:
                # "Stardock" ports open the StarDock services screen; the rest trade.
                dest = "stardock" if "Stardock" in p else "port"
                yield ClickableEntry(f"  [magenta]P[/] {p}", dest=dest)
        else:
            yield Static("  none")

        yield Static("", classes="spacer")
        yield Static("Planets", classes="heading")
        if sec.planets:
            for p in sec.planets:
                yield ClickableEntry(f"  [green]@[/] {p}", dest="planet")
        else:
            yield Static("  none")

        yield Static("", classes="spacer")
        if sec.beacon:
            yield Static("Beacons", classes="heading")
            yield Static(f"  [yellow]![/] {sec.beacon}")
            yield Static("", classes="spacer")
        yield Static("Ships", classes="heading")
        yield Static(f"  {', '.join(sec.ships) or 'none'}")

        yield Static("", classes="spacer")
        yield Static("Warps", classes="heading")
        yield WarpGrid(sec.warps, sec.sector_id)


class GameScreen(Screen):
    BINDINGS = [
        Binding("p", "dock_port", "Port"),
        Binding("c", "computer", "Computer"),
        Binding("g", "map", "Map"),
        Binding("d", "redisplay", "Redisplay"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        yield TopBar(self._state)
        with Horizontal(id="body"):
            yield SectorView(self._state)
            yield StatusSidebar(self._state.ship, id="sidebar")
        yield RichLog(id="ticker", max_lines=200, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one("#ticker", RichLog)
        log.write("[dim]· You arrive in Sector 7.  · Stardock detected.  · 287 turns left.[/]")

    def _tick(self, msg: str) -> None:
        self.query_one("#ticker", RichLog).write(msg)

    def on_warp_button_warp(self, msg: WarpButton.Warp) -> None:
        self._tick(f"[cyan]» Plotting warp to Sector {msg.sector_id}…[/]")

    def on_clickable_entry_picked(self, msg: ClickableEntry.Picked) -> None:
        match msg.dest:
            case "stardock":
                self.app.push_screen(StarDockScreen("Sol"))
            case "planet":
                self.app.push_screen(PlanetScreen("Terra Nova"))
            case _:
                self.app.push_screen("port")

    def action_dock_port(self) -> None:
        self.app.push_screen("port")

    def action_redisplay(self) -> None:
        self._tick("[dim]· Redisplay.[/]")

    def action_computer(self) -> None:
        self._tick("[dim]· Ship computer — not wired in the skeleton.[/]")

    def action_map(self) -> None:
        self._tick("[dim]· Galactic map — not wired in the skeleton.[/]")
