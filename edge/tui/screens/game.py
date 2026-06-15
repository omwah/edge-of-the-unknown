"""GameScreen — the primary screen (UI_MOCKUPS.md §1)."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, RichLog, Static

from edge.tui.dummy import GameState, SectorDTO, sample_port, sample_stardock_port
from edge.tui.screens.planet import PlanetScreen
from edge.tui.screens.port import PortScreen
from edge.tui.screens.stardock import StarDockScreen
from edge.tui.widgets import (
    ClickableEntry,
    SectorScene,
    StatusSidebar,
    WarpButton,
    WarpGrid,
)


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


class SectorView(Container):
    # An ASCII scene (planets/ports/ships) is drawn on the `scene` layer; the
    # interface text rides above it on the `content` layer. The content scroll is
    # transparent and its rows are narrow/left-aligned, so the scene shows through
    # the right-hand negative space without art and text ever sharing a cell.
    DEFAULT_CSS = """
    SectorView { width: 2fr; layers: scene content; background: transparent; }
    SectorView SectorScene { layer: scene; }
    SectorView #sector-text {
        layer: content; width: 60%; height: 1fr;
        padding: 0 1; overflow-x: hidden; background: transparent;
    }
    SectorView #sector-text > Static, SectorView #sector-text > ClickableEntry {
        width: auto; background: transparent;
    }
    SectorView #flavor { color: $text-muted; text-style: italic; }
    SectorView .heading { color: $secondary; text-style: bold; }
    SectorView .spacer { height: 1; }
    """

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        sec = self._state.sector
        yield SectorScene(sec)
        with VerticalScroll(id="sector-text"):
            yield from self._content(sec)

    def _content(self, sec: SectorDTO) -> ComposeResult:
        yield Static(f"[b cyan]{sec.region} - Sector {sec.sector_id}[/]", id="title")
        yield Static(f"░▒▓ {sec.flavor} ▓▒░", id="flavor")

        yield Static("", classes="spacer")
        yield Static("Planets", classes="heading")
        if sec.planets:
            for p in sec.planets:
                yield ClickableEntry(f"  [green]@[/] {p}", dest="planet")
        else:
            yield Static("  none")

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
        if sec.beacon:
            yield Static("Beacons", classes="heading")
            yield Static(f"  [yellow]![/] {sec.beacon}")
            yield Static("", classes="spacer")
        yield Static("Ships", classes="heading")
        if sec.ships:
            for s in sec.ships:
                yield Static(f"  [white]>[/] {s}")
        else:
            yield Static("  none")

        yield Static("", classes="spacer")
        yield Static("Warps", classes="heading")
        yield WarpGrid(sec.warps, sec.sector_id)


class GameScreen(Screen):
    BINDINGS = [
        Binding("p", "dock_port", "Dock"),
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
        # Clicking a port resolves to the same destination as the Dock hotkey, so
        # there is one way to reach a sector's trade UI (StarDock tab or plain port).
        match msg.dest:
            case "planet":
                self.app.push_screen(PlanetScreen("Terra Nova"))
            case _:
                self.action_dock_port()

    def action_dock_port(self) -> None:
        ports = self._state.sector.ports
        if not ports:
            self._tick("[dim]· No port to dock with in this sector.[/]")
            return
        # A StarDock opens the services hub (trading is its Commodities tab); a
        # plain commodities port opens the standalone trade screen.
        if "Stardock" in ports[0]:
            self.app.push_screen(StarDockScreen("Sol", sample_stardock_port()))
        else:
            self.app.push_screen(PortScreen(sample_port()))

    def action_redisplay(self) -> None:
        self._tick("[dim]· Redisplay.[/]")

    def action_computer(self) -> None:
        self._tick("[dim]· Ship computer — not wired in the skeleton.[/]")

    def action_map(self) -> None:
        self._tick("[dim]· Galactic map — not wired in the skeleton.[/]")
