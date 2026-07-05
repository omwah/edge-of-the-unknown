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
from textual.containers import Container, Horizontal
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.events import DiscoveryCollected, EncounterStarted, Event
from edge.core.movement import MovementError
from edge.core.rules import Dock, Hail, Salvage, TravelTo, Warp
from edge.server.service import GameService
from edge.tui.dummy import SectorDTO
from edge.tui.screens.computer import ComputerScreen
from edge.tui.screens.contact import AlienContactScreen
from edge.tui.screens.encounter import EncounterScreen
from edge.tui.screens.engine_room import EngineRoomScreen
from edge.tui.screens.help import HelpScreen
from edge.tui.screens.planet import PlanetScreen
from edge.tui.screens.travel import TravelPromptScreen
from edge.tui.screens.port import PortScreen
from edge.tui.screens.stardock import StarDockScreen
from edge.tui.widgets import (
    ClickableEntry,
    NavRose,
    SectionRule,
    SectorScene,
    StatusSidebar,
    Ticker,
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
    """The primary sector display (§1).

    A single composited `SectorScene` (starfield behind header / planet / port /
    ships) fills the upper area, and the interactive `NavRose` — the single,
    direction-aware warp affordance — fills the width at the bottom.
    """

    DEFAULT_CSS = """
    SectorView { width: 1fr; background: transparent; }
    SectorView #warp-area { width: 1fr; height: auto; align-horizontal: center; }
    """

    def __init__(self, sector: SectorDTO, nav: object = None) -> None:
        super().__init__()
        self._sector = sector
        self._nav = nav

    def compose(self) -> ComposeResult:
        sec = self._sector
        yield SectorScene(sec)
        yield SectionRule("Navigation", id="warp-rule")
        with Container(id="warp-area"):
            if self._nav is not None:
                yield NavRose(self._nav, sec.warps)
            else:  # defensive: a legacy view with no baked rose
                yield Static("[dim]no navigation data[/]")


class GameScreen(Screen):
    # The overlay layer hosts the expanded event ticker, so it draws over the sector
    # view instead of reflowing it (the ticker sets `layer: overlay` when expanded).
    DEFAULT_CSS = "GameScreen { layers: overlay; }"

    BINDINGS = [
        Binding("p", "dock_port", "Dock"),
        Binding("w", "travel", "Travel"),
        Binding("h", "hail", "Hail"),
        Binding("s", "survey_planet", "Survey Planet"),
        Binding("z", "scan", "Scan"),
        Binding("c", "computer", "Computer"),
        Binding("e", "engine_room", "Engine Room"),
        Binding("m", "map", "Map"),
        Binding("g", "messages", "Log"),
        Binding("question_mark", "help", "Help"),
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
        ui = getattr(self.app, "ui_config", None)
        sidebar_width = ui.sidebar_width if ui is not None else 33
        with Horizontal(id="body"):
            yield SectorView(view.sector, view.nav)
            sidebar = StatusSidebar(view.ship, view.sector.discoveries, sidebar_width, id="sidebar")
            sidebar.display = self._sidebar_visible()  # also re-evaluated on resize
            yield sidebar
        yield Ticker(self._ticker_lines())
        yield Footer()

    def _sidebar_visible(self) -> bool:
        """Whether the sidebar fits — hidden on narrow terminals so the sector view
        isn't squished (the threshold is configurable)."""
        ui = getattr(self.app, "ui_config", None)
        threshold = ui.sidebar_min_screen_width if ui is not None else 90
        return self.app.size.width >= threshold

    def on_resize(self) -> None:
        try:
            sidebar = self.query_one("#sidebar", StatusSidebar)
        except NoMatches:
            return
        sidebar.display = self._sidebar_visible()

    def _ticker_lines(self) -> list[str]:
        """The event-log lines, most recent last (a single fallback when empty)."""
        if self._log:
            return list(self._log)
        return ["[dim]· New game — dock at the StarDock to trade and upgrade, then explore.[/]"]

    async def on_screen_resume(self) -> None:
        # Rebuild from fresh state when this screen becomes active again (after a
        # pushed trade/map screen pops); skip the very first activation.
        if self._active:
            await self.recompose()
        else:
            self._active = True
        # A save quit mid-fight resumes engaged: reopen the encounter screen (§10) —
        # movement is blocked in core anyway, so the modal is the only way forward.
        if self._service.encounter_view(self._pid) is not None:
            self.app.push_screen(EncounterScreen(self._service, self._pid))

    # --- commands ------------------------------------------------------------

    async def on_nav_rose_picked(self, msg: NavRose.Picked) -> None:
        await self._warp(msg.sector_id)

    async def on_clickable_entry_picked(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest == "planet":
            self.action_survey_planet()
        elif msg.dest == "wormhole" and msg.ref is not None:
            await self._warp(int(msg.ref))  # the far side is a legal one-way warp
        elif msg.dest == "discovery" and msg.ref is not None:
            await self._salvage(msg.ref)
        elif msg.dest == "contact" and msg.ref is not None:
            self._hail_species(int(msg.ref))
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
        self._handle_encounter(events)

    def _handle_encounter(self, events: tuple[Event, ...]) -> None:
        """Route a movement interruption (§10, WP24): a violence opener pushes the
        encounter screen; a peaceful one opens the ordinary contact screen."""
        started = next((e for e in events if isinstance(e, EncounterStarted)), None)
        if started is None:
            return
        if started.hostile:
            self.app.push_screen(EncounterScreen(self._service, self._pid))
        else:
            self._hail_species(started.species_id)

    def action_travel(self) -> None:
        self.app.push_screen(TravelPromptScreen(), self._after_travel)

    def _after_travel(self, dest: int | None) -> None:
        if dest is None:
            return
        internal = self._service.resolve_display_id(dest)  # player typed a spatial id (§5.1)
        if internal is None:
            self.notify(f"No sector {dest}.", severity="warning", timeout=3)
            return
        try:
            events = self._service.apply(self._pid, TravelTo(to_sector=internal))
        except (MovementError, EconomyError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        if not events:
            self.notify("No move made.", timeout=2)
            return
        self._record(events)
        self.run_worker(self.recompose())
        self._handle_encounter(events)

    async def action_scan(self) -> None:
        # Scan logs the first unlogged visible find — the same action as clicking one.
        view = self._service.game_view(self._pid)
        target = next((d for d in view.sector.discoveries if d.salvageable), None)
        if target is None:
            self.notify("No unlogged discoveries in sensor range here.", timeout=2)
            return
        await self._salvage(target.discovery_id)

    async def _salvage(self, discovery_id: int) -> None:
        # Capture the find's kind before it's logged, so a wormhole scan can warn of
        # the one-way warp (covers both the sidebar row and the Z scan action).
        view = self._service.game_view(self._pid)
        target = next((d for d in view.sector.discoveries if d.discovery_id == discovery_id), None)
        try:
            events = self._service.apply(self._pid, Salvage(discovery_id=discovery_id))
        except (MovementError, EconomyError, EngineRoomError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self._record(events)
        collected = next((e for e in events if isinstance(e, DiscoveryCollected)), None)
        if collected is not None and collected.reward:
            self.notify(f"You discovered {collected.reward}.", title="Discovery", timeout=4)
        if target is not None and target.kind == "wormhole":
            self.notify("Sensor reading: one-way warp — no direct way back.",
                        severity="warning", timeout=3)
        await self.recompose()

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
        is_stardock = any(p.is_stardock for p in ports)
        screen = (
            StarDockScreen(self._service, self._pid)
            if is_stardock
            else PortScreen(self._service, self._pid)
        )
        self.app.push_screen(screen)

    # --- other screens (live: computer/map; sample: the Phase 2-3 ones) ------

    def action_computer(self) -> None:
        # Reopen on the tab last used (Map/Log have their own keys that jump explicitly).
        last_tab = getattr(self.app, "computer_tab", "trade")
        self.app.push_screen(ComputerScreen(self._service, self._pid, initial_tab=last_tab))

    def action_map(self) -> None:
        self.app.push_screen(ComputerScreen(self._service, self._pid, initial_tab="map"))

    def action_hail(self) -> None:
        """Hail the first friendly species in this sector (H is a shortcut; click a ship to pick)."""
        species_id = self._service.species_in_sector(self._pid)
        if species_id is None:
            self.notify("No alien contact in this sector.", timeout=2)
            return
        self._hail_species(species_id)

    def _hail_species(self, species_id: int) -> None:
        """Open contact with a specific species in this sector (§6, WP9).

        A hail can be refused — most notably the roaming Entity, whose contact is
        sensor-gated at Legendary difficulty (§7, WP35) — so a rejected hail notifies
        rather than opening the screen.
        """
        try:
            events = self._service.apply(self._pid, Hail(species_id))
        except (MovementError, EconomyError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self._record(events)
        self.app.push_screen(AlienContactScreen(
            self._service.contact_view(self._pid, species_id),
            self._service, self._pid, species_id))

    def action_survey_planet(self) -> None:
        planet = self._service.current_planet_view(self._pid)
        if planet is None:
            self.notify("No planet to survey here.", timeout=2)
            return
        self.app.push_screen(PlanetScreen(planet, self._service, self._pid))

    def action_engine_room(self) -> None:
        self.app.push_screen(EngineRoomScreen(
            self._service.engine_room_view(self._pid), self._service, self._pid))

    def action_messages(self) -> None:
        self.app.push_screen(ComputerScreen(self._service, self._pid, initial_tab="log"))

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    # --- event ticker --------------------------------------------------------

    def _record(self, events: tuple[Event, ...]) -> None:
        self._log.extend(line for line in map(self._service.describe_event, events) if line)
