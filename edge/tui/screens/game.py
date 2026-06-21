"""GameScreen — the primary screen, wired to the live GameService (UI_MOCKUPS.md §1).

Reads `service.game_view(player_id)` (the fog-of-war DTO) and issues commands
through `service.apply`; after a state change it recomposes from the fresh view.
Warps and docking are real commands (turn costs, persistence); the deferred
Phase 2-3 screens still open on sample data.
"""

from __future__ import annotations

import random

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.events import Event
from edge.core.movement import MovementError
from edge.core.rules import Dock, Hail, Salvage, TravelTo, Warp
from edge.server.service import GameService
from edge.tui import art_adapter
from edge.tui.dummy import SectorDTO
from edge.tui.screens.computer import ComputerScreen
from edge.tui.screens.contact import AlienContactScreen
from edge.tui.screens.engine_room import EngineRoomScreen
from edge.tui.screens.planet import PlanetScreen
from edge.tui.screens.travel import TravelPromptScreen
from edge.tui.screens.port import PortScreen
from edge.tui.screens.stardock import StarDockScreen
from edge.tui.widgets import (
    ClickableEntry,
    OrbitPanel,
    ShipPanel,
    Starfield,
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
    """The primary sector display: sprites co-located with their labels (§1).

    A starfield backdrop layer sits behind a content layer that stacks, top to
    bottom: a full-width header (sector + band), a two-column orbit row
    (planet | port, each sprite with its name beneath; discoveries under the
    planet), a ships row (up to `scene.max_ships_shown` sprites, the rest a
    clickable text list), and a centred warp grid pinned to the bottom.
    """

    DEFAULT_CSS = """
    SectorView { width: 2fr; layers: backdrop content; background: transparent; }
    SectorView Starfield { layer: backdrop; width: 100%; height: 100%; }
    SectorView #sector-stack {
        layer: content; width: 100%; height: 100%; padding: 0 1; background: transparent;
    }
    SectorView #sector-header { width: 1fr; height: auto; text-align: center; }
    SectorView #flavor { color: $text-muted; text-style: italic; }
    SectorView #orbit-row { height: auto; }
    SectorView .orbit-col { width: 1fr; height: auto; }
    SectorView .col-heading { width: 1fr; text-align: center; color: $secondary; text-style: bold; }
    SectorView .muted { color: $text-muted; }
    SectorView #ships-row { height: auto; }
    SectorView #ship-sprites { height: auto; }
    SectorView #scene-spacer { height: 1fr; }
    SectorView #warp-area { width: 1fr; height: auto; align-horizontal: center; }
    SectorView ClickableEntry { width: 1fr; background: transparent; }
    """

    def __init__(self, sector: SectorDTO) -> None:
        super().__init__()
        self._sector = sector

    def compose(self) -> ComposeResult:
        sec = self._sector
        yield Starfield(animate=not self.app.plain)
        with Vertical(id="sector-stack"):
            # Header — sector name + band, spanning all columns at the very top.
            title = f"[{sec.display_id}] {sec.region}"
            if sec.band:
                title += f" ({sec.band})"
            with Vertical(id="sector-header"):
                yield Static(f"[b cyan]{title}[/]", id="title")
                yield Static(f"░▒▓ {sec.flavor} ▓▒░", id="flavor")
                if sec.beacon:
                    yield Static(f"[yellow]![/] {sec.beacon}")

            # Orbit row — planet | port, each with its name beneath the sprite.
            with Horizontal(id="orbit-row"):
                with Vertical(classes="orbit-col"):
                    if sec.planets:
                        sub = art_adapter.planet_subtype_from_name(sec.planets[0])
                        yield OrbitPanel("planet", sub, sec.planets[0],
                                         sprite_seed=sec.sector_id, dest="planet")
                    else:
                        yield OrbitPanel("planet", None, "no planet",
                                         sprite_seed=sec.sector_id, dest="planet")
                    # Discoveries live with the planet column.
                    yield Static("Discoveries", classes="col-heading")
                    if sec.discoveries:
                        for d in sec.discoveries:
                            if d.collected:
                                yield Static(f"  [cyan]✦[/] {d.label} — logged")
                            else:
                                yield ClickableEntry(
                                    f"  [cyan]✦[/] {d.label} — unlogged (Scan)",
                                    dest="discovery", ref=d.discovery_id)
                    else:
                        yield Static("  none", classes="muted")
                with Vertical(classes="orbit-col"):
                    if sec.ports:
                        sub = art_adapter.port_subtype(sec.ports[0])
                        yield OrbitPanel("port", sub, sec.ports[0],
                                         sprite_seed=sec.sector_id, dest="port")
                    else:
                        yield OrbitPanel("port", None, "no port",
                                         sprite_seed=sec.sector_id, dest="port")

            # Ships — up to N sprites side by side, the rest a clickable list.
            yield from self._ships(sec)

            # Push the warp interface to the very bottom, centred across columns.
            yield Static("", id="scene-spacer")
            with Container(id="warp-area"):
                yield WarpGrid(sec.warps, sec.display_id)

    def _ships(self, sec: SectorDTO) -> ComposeResult:
        max_shown = self.app.scene_art.max_ships_shown
        flip_chance = self.app.scene_art.ship_face_inward_chance
        with Vertical(id="ships-row"):
            yield Static("Ships", classes="col-heading")
            if not sec.ships:
                yield Static("  none", classes="muted")
                return
            shown = sec.ships[:max_shown]
            # Deterministic facing (seeded by sector) so it never flickers on
            # recompose: the second of two ships may flip to face the first.
            rng = random.Random(sec.sector_id)
            with Horizontal(id="ship-sprites"):
                for i, name in enumerate(shown):
                    cid = sec.contact_ids[i] if i < len(sec.contact_ids) else None
                    facing = "left" if (i == 1 and rng.random() < flip_chance) else "right"
                    yield ShipPanel(name, sprite_seed=sec.sector_id * 16 + i,
                                    contact_id=cid, facing=facing)
            # Overflow beyond the sprite cap stays individually hailable as text.
            for i in range(max_shown, len(sec.ships)):
                name = sec.ships[i]
                cid = sec.contact_ids[i] if i < len(sec.contact_ids) else None
                if cid is None:
                    yield Static(f"  [white]>[/] {name}")
                else:
                    yield ClickableEntry(f"  [white]>[/] {name} [dim](Hail)[/]",
                                         dest="contact", ref=cid)


class GameScreen(Screen):
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

    async def action_scan(self) -> None:
        # Scan logs the first unlogged visible find — the same action as clicking one.
        view = self._service.game_view(self._pid)
        target = next((d for d in view.sector.discoveries if d.salvageable), None)
        if target is None:
            self.notify("No unlogged discoveries in sensor range here.", timeout=2)
            return
        await self._salvage(target.discovery_id)

    async def _salvage(self, discovery_id: int) -> None:
        try:
            events = self._service.apply(self._pid, Salvage(discovery_id=discovery_id))
        except (MovementError, EconomyError, EngineRoomError) as exc:
            self.notify(str(exc), severity="warning", timeout=3)
            return
        self._record(events)
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

    def action_hail(self) -> None:
        """Hail the first friendly species in this sector (H is a shortcut; click a ship to pick)."""
        species_id = self._service.species_in_sector(self._pid)
        if species_id is None:
            self.notify("No alien contact in this sector.", timeout=2)
            return
        self._hail_species(species_id)

    def _hail_species(self, species_id: int) -> None:
        """Open contact with a specific species in this sector (§6, WP9)."""
        self._record(self._service.apply(self._pid, Hail(species_id)))
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

    # --- event ticker --------------------------------------------------------

    def _record(self, events: tuple[Event, ...]) -> None:
        self._log.extend(line for line in map(self._service.describe_event, events) if line)
