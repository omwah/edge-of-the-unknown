"""GameScreen — the primary screen (UI_MOCKUPS.md §1)."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static

from edge.tui.dummy import GameState
from edge.tui.widgets import StatusSidebar, WarpButton, WarpList


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
    """

    def __init__(self, state: GameState) -> None:
        super().__init__()
        self._state = state

    def compose(self) -> ComposeResult:
        sec = self._state.sector
        yield Static(f"[b cyan]{sec.region} - Sector {sec.sector_id}[/]", id="title")
        yield Static(f"░▒▓ {sec.flavor} ▓▒░", id="flavor")

        body: list[str] = []
        body.append("[b]Ports[/]")
        body += [f"  [magenta]P[/] {p}" for p in sec.ports] or ["  none"]
        body.append("[b]Planets[/]")
        body += [f"  [green]@[/] {p}" for p in sec.planets] or ["  none"]
        body.append(f"[b]Ships[/]    {', '.join(sec.ships) or 'none'}")
        if sec.beacon:
            body.append(f"[b]Beacons[/]  [yellow]![/] {sec.beacon}")
        yield Static("\n".join(body), id="contents")

        yield Static("Warps", classes="heading")
        yield WarpList(sec.warps)


class GameScreen(Screen):
    BINDINGS = [
        Binding("p", "dock_port", "Port"),
        Binding("c", "noop", "Computer"),
        Binding("g", "noop", "Map"),
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
        with Vertical(id="bottom"):
            yield Input(placeholder="command…", id="command")
            yield RichLog(id="ticker", max_lines=200, markup=True)

    def on_mount(self) -> None:
        log = self.query_one("#ticker", RichLog)
        log.write("[dim]· You arrive in Sector 7.  · Stardock detected.  · 287 turns left.[/]")

    def _tick(self, msg: str) -> None:
        self.query_one("#ticker", RichLog).write(msg)

    def on_warp_button_warp(self, msg: WarpButton.Warp) -> None:
        self._tick(f"[cyan]» Plotting warp to Sector {msg.sector_id}…[/]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._tick(f"> {event.value}")
        event.input.clear()

    def action_dock_port(self) -> None:
        self.app.push_screen("port")

    def action_redisplay(self) -> None:
        self._tick("[dim]· Redisplay.[/]")

    def action_noop(self) -> None:
        self._tick("[dim](not wired in the skeleton)[/]")
