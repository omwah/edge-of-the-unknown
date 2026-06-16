"""GameScreen — the primary screen, wired to the live GameService (UI_MOCKUPS.md §1).

Reads `service.game_view(player_id)` (the fog-of-war DTO) and issues commands
through `service.apply`; after a state change it recomposes from the fresh view.
Warps and docking are real commands (turn costs, persistence); the deferred
Phase 2-3 screens still open on sample data.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core.economy import EconomyError
from edge.core.events import Event
from edge.core.movement import MovementError
from edge.core.rules import Dock, TravelTo, Warp
from edge.server.service import GameService
from edge.server.session import format_event
from edge.tui.dummy import SectorDTO, sample_engine_room
from edge.tui.screens.computer import ComputerScreen
from edge.tui.screens.engine_room import EngineRoomScreen
from edge.tui.screens.planet import PlanetScreen
from edge.tui.screens.travel import TravelPromptScreen
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

    def __init__(self, turns: int, max_turns: int) -> None:
        super().__init__()
        self._turns = turns
        self._max = max_turns

    def render(self) -> Text:
        return Text.assemble("EDGE OF THE UNKNOWN", ("  ", ""), f"turns {self._turns}/{self._max}")


class SectorView(Container):
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

    def __init__(self, sector: SectorDTO) -> None:
        super().__init__()
        self._sector = sector

    def compose(self) -> ComposeResult:
        yield SectorScene(self._sector)
        with VerticalScroll(id="sector-text"):
            yield from self._content(self._sector)

    def _content(self, sec: SectorDTO) -> ComposeResult:
        title = f"[{sec.sector_id}] {sec.region}"
        if sec.band:
            title += f" ({sec.band})"
        yield Static(f"[b cyan]{title}[/]", id="title")
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
                yield ClickableEntry(f"  [magenta]P[/] {p}", dest="port")
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
        Binding("w", "travel", "Travel"),
        Binding("s", "survey_planet", "Survey Planet"),
        Binding("c", "computer", "Computer"),
        Binding("e", "engine_room", "Engine Room"),
        Binding("m", "map", "Map"),
        Binding("g", "messages", "Log"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, service: GameService, player_id: int) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id
        self._log: list[str] = []
        self._active = False

    def compose(self) -> ComposeResult:
        view = self._service.game_view(self._pid)
        yield TopBar(view.turns, view.max_turns)
        with Horizontal(id="body"):
            yield SectorView(view.sector)
            yield StatusSidebar(view.ship, id="sidebar")
        yield Static(self._ticker_text(), id="ticker")
        yield Footer()

    def _ticker_text(self) -> str:
        if self._log:
            return "\n".join(self._log[-3:])
        signpost = self._service.intro_line(self._pid)
        if signpost is not None:
            return f"[yellow]· {signpost}[/]"
        return "[dim]· New game — find a port and start trading.[/]"

    async def on_screen_resume(self) -> None:
        # Rebuild from fresh state when this screen becomes active again (after a
        # pushed trade/map screen pops); skip the very first activation.
        if self._active:
            await self.recompose()
        else:
            self._active = True

    # --- commands ------------------------------------------------------------

    async def on_warp_button_warp(self, msg: WarpButton.Warp) -> None:
        await self._warp(msg.sector_id)

    async def on_clickable_entry_picked(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest == "planet":
            self.action_survey_planet()
        else:
            await self._dock()

    async def _warp(self, sector_id: int) -> None:
        try:
            events = self._service.apply(self._pid, Warp(to_sector=sector_id))
        except (MovementError, EconomyError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self._record(events)
        await self.recompose()

    def action_travel(self) -> None:
        self.app.push_screen(TravelPromptScreen(), self._after_travel)

    def _after_travel(self, dest: int | None) -> None:
        if dest is None:
            return
        try:
            events = self._service.apply(self._pid, TravelTo(to_sector=dest))
        except (MovementError, EconomyError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        if not events:
            self.notify("No move made.", timeout=2)
            return
        self._record(events)
        self.run_worker(self.recompose())

    async def action_dock_port(self) -> None:
        await self._dock()

    async def _dock(self) -> None:
        view = self._service.game_view(self._pid)
        ports = view.sector.ports
        if not ports:
            self.notify("No port to dock with here.", timeout=2)
            return
        try:
            self._record(self._service.apply(self._pid, Dock()))
        except MovementError as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        is_stardock = any("stardock" in p.lower() for p in ports)
        screen = (
            StarDockScreen(self._service, self._pid)
            if is_stardock
            else PortScreen(self._service, self._pid)
        )
        self.app.push_screen(screen)

    # --- other screens (live: computer/map; sample: the Phase 2-3 ones) ------

    def action_computer(self) -> None:
        self.app.push_screen(ComputerScreen(self._service, self._pid))

    def action_map(self) -> None:
        self.app.push_screen(ComputerScreen(self._service, self._pid, initial_tab="map"))

    def action_survey_planet(self) -> None:
        planets = self._service.game_view(self._pid).sector.planets
        if not planets:
            self.notify("No planet to survey here.", timeout=2)
            return
        self.app.push_screen(PlanetScreen(planets[0].split("  ")[0].strip()))

    def action_engine_room(self) -> None:
        self.app.push_screen(EngineRoomScreen(sample_engine_room()))

    def action_messages(self) -> None:
        self.app.push_screen(ComputerScreen(self._service, self._pid, initial_tab="log"))

    # --- event ticker --------------------------------------------------------

    def _record(self, events: tuple[Event, ...]) -> None:
        self._log.extend(line for line in map(format_event, events) if line)
