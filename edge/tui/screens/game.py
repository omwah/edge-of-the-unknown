"""GameScreen — the primary screen, wired to the live GameService (UI_MOCKUPS.md §1).

Reads `service.game_view(player_id)` (the fog-of-war DTO) and issues commands
through `service.apply`; after a state change it recomposes from the fresh view.
Every screen it opens is wired to the live service (the last sample-data
skeletons were retired in the WP70–WP73 correction arc).
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core.combat import CombatError
from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.events import DiscoveryCollected, EncounterStarted, Event
from edge.core.movement import MovementError
from edge.core.rules import AttackPlayer, AttackSpecies, Dock, Hail, Salvage, TravelTo, Warp
from edge.server.service import GameService
from edge.tui.chrome import notify_warning
from edge.tui.design import LayoutTier, layout_tier
from edge.tui.dummy import NavStripDTO, SectorDTO
from edge.tui.onboarding import ObjectivesStrip, all_done
from edge.tui.screens.computer import ComputerScreen
from edge.tui.screens.confirm import ConfirmScreen
from edge.tui.screens.contact import AlienContactScreen
from edge.tui.screens.encounter import EncounterScreen
from edge.tui.screens.engine_room import EngineRoomScreen
from edge.tui.screens.help import HelpScreen
from edge.tui.screens.planet import PlanetScreen
from edge.tui.screens.travel import TravelPromptScreen
from edge.tui.screens.port import PortScreen
from edge.tui.screens.stardock import StarDockScreen
from edge.tui.screens.corp import CorpScreen
from edge.tui.screens.base import BaseScreen
from edge.tui.widgets import (
    ClickableEntry,
    NavRose,
    SectionRule,
    SectorObjectList,
    SectorScene,
    StatusSidebar,
    Ticker,
    force_lines,
)


def _presence_lines(sector: object) -> list[str]:
    """Sidebar lines for starbases + known forces here (§4.2/§10 — fog pre-applied)."""
    lines: list[str] = []
    for b in getattr(sector, "starbases", ()) or ():
        status = "[green]operational[/]" if b.operational else "[yellow]derelict[/]"
        lines.append(f"[cyan]#[/] {b.name} — {status}\n  [dim]{b.owner}[/]")
    lines.extend(force_lines(getattr(sector, "force", None)))
    return lines


class TopBar(Static):
    DEFAULT_CSS = """
    TopBar {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    """

    def __init__(self, turns: int, max_turns: int,
                 governor: str | None = None, core_status: str = "safe") -> None:
        super().__init__()
        self._turns = turns
        self._max = max_turns
        self._governor = governor
        self._core_status = core_status

    def render(self) -> Text:
        parts: list[tuple[str, str] | str] = [
            "EDGE OF THE UNKNOWN", ("  ", ""), f"turns {self._turns}/{self._max}"]
        if self._governor is not None:
            # Surface the Core's ruler and the player's standing in it (WP52) — a flip
            # is only legible if the banner is on screen. "safe" stays quiet.
            style = {"hunted": "bold red", "unwelcome": "yellow"}.get(self._core_status, "dim")
            parts += [("   ", ""), (f"Core: {self._governor} [{self._core_status}]", style)]
        return Text.assemble(*parts)


class SectorView(Container):
    """The primary sector display (§1).

    A single composited `SectorScene` (starfield behind header / planet / port /
    ships) fills the upper area, and the interactive `NavRose` — the single,
    direction-aware warp affordance — fills the width at the bottom. On the
    compact tier (WP-UI12) the art scene gives way to a location header plus a
    focusable object list — gameplay information wins over art — while the nav
    rose stays put as the visual anchor.
    """

    DEFAULT_CSS = """
    SectorView { width: 1fr; background: transparent; }
    SectorView #warp-area { width: 1fr; height: auto; align-horizontal: center; }
    SectorView #compact-header { width: 1fr; height: auto; text-align: center; }
    SectorView #compact-objects { width: 1fr; height: 1fr; }
    """

    def __init__(self, sector: SectorDTO, nav: NavStripDTO | None = None,
                 compact: bool = False) -> None:
        super().__init__()
        self._sector = sector
        self._nav = nav
        self._compact = compact

    def compose(self) -> ComposeResult:
        sec = self._sector
        if self._compact:
            yield Static(self._compact_header(), id="compact-header")
            with VerticalScroll(id="compact-objects"):
                yield SectionRule("Objects")
                yield SectorObjectList(sec)
        else:
            yield SectorScene(sec)
        yield SectionRule("Navigation", id="warp-rule")
        with Container(id="warp-area"):
            if self._nav is not None:
                yield NavRose(self._nav, sec.warps)
            else:  # defensive: a legacy view with no baked rose
                yield Static("[dim]no navigation data[/]")

    def _compact_header(self) -> str:
        """Location lines the compact tier keeps when the art scene is dropped."""
        sec = self._sector
        title = f"[{sec.display_id}] {sec.region}" + (f" ({sec.band})" if sec.band else "")
        lines = [f"[b cyan]{title}[/]", f"[i #8a8a8a]{sec.flavor}[/]"]
        if sec.beacon:
            lines.append(f"[yellow]![/] {sec.beacon}")
        return "\n".join(lines)


class GameScreen(Screen[None]):
    # The overlay layer hosts the expanded event ticker, so it draws over the sector
    # view instead of reflowing it (the ticker sets `layer: overlay` when expanded).
    DEFAULT_CSS = "GameScreen { layers: overlay; }"

    BINDINGS = [
        Binding("p", "dock_port", "Dock"),
        Binding("b", "base_services", "Base"),
        Binding("w", "travel", "Travel"),
        Binding("h", "hail", "Hail"),
        Binding("a", "attack", "Attack"),
        Binding("s", "survey_planet", "Survey Planet"),
        Binding("z", "scan", "Scan"),
        Binding("i", "status", "Status"),
        Binding("c", "computer", "Computer"),
        Binding("e", "engine_room", "Engine Room"),
        Binding("m", "map", "Map"),
        Binding("g", "messages", "Log"),
        Binding("t", "corp", "Corp"),
        Binding("d", "territory", "Deploy"),
        # Captain's objectives (WP-UI11): hide the onboarding strip; re-enable
        # in Options. Unadvertised — the strip itself carries the affordance.
        Binding("o", "dismiss_objectives", "Hide objectives", show=False),
        Binding("question_mark", "help", "Help"),
        Binding("ctrl+q", "quit", "Quit"),
    ]
    # WP-UI06: a first strike is a betrayal (D7) — _attack_target confirms it.
    ACTION_DANGER = {"attack": "destructive"}

    HELP_TITLE = "Sector view"
    HELP_LEGEND = True
    HELP = """\
Click the planet, base, port, or a ship for the same actions as the keys.
[b]B[/] opens the starbase here (station · trade · hardware · bank, by standing);
[b]P[/] docks at a free-standing port; a base's market is entered through the base.
The event ticker (bottom) expands on click; [b]Z[/] sweeps sensors for hidden finds.
[b]I[/] opens the status drawer — the full ship readout plus a keyboard-navigable
list of everything in the sector (the sidebar's stand-in on a compact terminal)."""

    def __init__(self, service: GameService, player_id: int) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id
        self._log: list[str] = []
        self._active = False
        self._composed_tier: LayoutTier | None = None

    def _current_tier(self) -> LayoutTier:
        """The live layout tier, computed from the app size directly (resize-event
        ordering between app and screen handlers is not guaranteed)."""
        return layout_tier(self.app.size.width, self.app.size.height)

    def compose(self) -> ComposeResult:
        view = self._service.game_view(self._pid)
        tier = self._current_tier()
        self._composed_tier = tier
        compact = tier is LayoutTier.COMPACT
        yield TopBar(view.turns, view.max_turns, view.governor, view.core_status)
        ui = getattr(self.app, "ui_config", None)
        sidebar_width = ui.sidebar_width if ui is not None else 33
        with Horizontal(id="body"):
            yield SectorView(view.sector, view.nav, compact=compact)
            # Compact drops the sidebar entirely — the I status drawer carries its
            # readout (WP-UI12). Wide enriches it with the objectives checklist and
            # anomaly detail.
            if not compact:
                settings = getattr(self.app, "ui_settings", None)
                wide = tier is LayoutTier.WIDE
                objectives = (settings.objectives_done
                              if wide and settings and settings.show_onboarding else None)
                sidebar = StatusSidebar(view.ship, view.sector.discoveries, sidebar_width,
                                        presence=_presence_lines(view.sector),
                                        detail=wide, objectives=objectives, id="sidebar")
                sidebar.display = self._sidebar_visible()  # also re-evaluated on resize
                yield sidebar
        settings = getattr(self.app, "ui_settings", None)
        if settings and settings.show_onboarding and not all_done(settings.objectives_done):
            yield ObjectivesStrip(settings.objectives_done, id="objectives")
        yield Ticker(self._ticker_lines())
        yield Footer()

    def _sidebar_visible(self) -> bool:
        """Whether the sidebar fits — hidden on narrow terminals so the sector view
        isn't squished (the threshold is configurable)."""
        ui = getattr(self.app, "ui_config", None)
        threshold = ui.sidebar_min_screen_width if ui is not None else 90
        return self.app.size.width >= threshold

    def on_resize(self) -> None:
        # Crossing a layout breakpoint swaps the sector presentation (art scene vs.
        # compact object list, sidebar detail), so recompose from fresh state.
        tier = self._current_tier()
        if (self._composed_tier is not None and tier is not self._composed_tier
                and tier is not LayoutTier.UNSUPPORTED):
            self.refresh(recompose=True)
            return
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
        # Guard against a duplicate: a confirm-modal dismiss resumes this screen in the
        # same tick its callback pushes the fight, and a second stale EncounterScreen
        # would strand the player once the top one pops at the encounter's end.
        if self._service.encounter_view(self._pid) is not None:
            self._push_encounter()

    def _push_encounter(self) -> None:
        """Open the fight screen, never a duplicate (WP-fix): a confirm-modal dismiss can
        resume this screen in the same tick its callback pushes the fight, and a second
        stale EncounterScreen would strand the player once the top one pops."""
        if not any(isinstance(s, EncounterScreen) for s in self.app.screen_stack):
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
            await self._salvage(int(msg.ref))
        elif msg.dest == "contact" and msg.ref is not None:
            self._hail_species(int(msg.ref))
        elif msg.dest == "player" and msg.ref is not None:
            self._attack_target(player_id=int(msg.ref))
        elif msg.dest == "starbase":
            self.action_base_services()
        else:
            await self._dock()

    async def _warp(self, sector_id: int) -> None:
        try:
            events = self._service.apply(self._pid, Warp(to_sector=sector_id))
        except (MovementError, EconomyError) as exc:
            notify_warning(self, str(exc))
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
            self._push_encounter()
        else:
            self._hail_species(started.species_id)

    def action_travel(self) -> None:
        self.app.push_screen(TravelPromptScreen(), self._after_travel)

    def _after_travel(self, dest: int | None) -> None:
        if dest is None:
            return
        internal = self._service.resolve_display_id(dest)  # player typed a spatial id (§5.1)
        if internal is None:
            notify_warning(self, f"No sector {dest}.")
            return
        try:
            events = self._service.apply(self._pid, TravelTo(to_sector=internal))
        except (MovementError, EconomyError) as exc:
            notify_warning(self, str(exc))
            return
        if not events:
            self.notify("No move made.", timeout=2)
            return
        self._record(events)
        self.run_worker(self.recompose())
        self._handle_encounter(events)

    async def action_scan(self) -> None:
        # Scan logs the first unlogged visible find — the same action as clicking one.
        self.app.mark_objective("scan")  # type: ignore[attr-defined]
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
            notify_warning(self, str(exc))
            return
        self._record(events)
        collected = next((e for e in events if isinstance(e, DiscoveryCollected)), None)
        if collected is not None:
            self.app.mark_objective("discover")  # type: ignore[attr-defined]
        if collected is not None and collected.reward:
            self.notify(f"You discovered {collected.reward}.", title="Discovery", timeout=4)
        if target is not None and target.kind == "wormhole":
            notify_warning(self, "Sensor reading: one-way warp — no direct way back.")
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
            notify_warning(self, str(exc))
            return
        is_stardock = any(p.is_stardock for p in ports)
        base = self._service.current_starbase_view(self._pid)
        screen: Screen[None]
        if is_stardock:
            screen = StarDockScreen(self._service, self._pid)
        elif base is not None:
            screen = BaseScreen(self._service, self._pid, base.starbase_id,
                                initial_tab="trade")
        else:
            screen = PortScreen(self._service, self._pid)
        self.app.mark_objective("dock")  # type: ignore[attr-defined]
        self.app.push_screen(screen)

    def action_base_services(self) -> None:
        """Open the unified base view for the starbase here, if any (§4.2, WP80)."""
        view = self._service.current_starbase_view(self._pid)
        if view is None:
            self.notify("No starbase to visit here.", timeout=2)
            return
        self.app.push_screen(BaseScreen(self._service, self._pid, view.starbase_id))

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

    def action_attack(self) -> None:
        """Open fire on the first ship in this sector (WP70; A is a shortcut — click a
        player's ship to pick it, or attack a specific alien from its contact screen)."""
        view = self._service.game_view(self._pid)
        target = next((s for s in view.sector.ships
                       if s.contact_id is not None or s.player_id is not None), None)
        if target is None:
            self.notify("No ship to engage in this sector.", timeout=2)
            return
        self._attack_target(species_id=target.contact_id, player_id=target.player_id,
                            name=target.name)

    def _attack_target(self, *, species_id: int | None = None, player_id: int | None = None,
                       name: str | None = None) -> None:
        """Confirm, then open first-strike combat (§10 WP70; D7 — attacks are deliberate)."""
        if name is None and player_id is not None:
            view = self._service.game_view(self._pid)
            named = next((s for s in view.sector.ships if s.player_id == player_id), None)
            name = named.name if named is not None else "that ship"
        message = (
            f"Open fire on {name}? Killing a lawful captain makes you an outlaw."
            if player_id is not None else
            f"Open fire on {name}? A first strike is a betrayal their kind will remember."
        )

        def _go(confirmed: bool | None) -> None:
            if not confirmed:
                return
            command = (AttackPlayer(player_id) if player_id is not None
                       else AttackSpecies(int(species_id)))  # type: ignore[arg-type]
            try:
                events = self._service.apply(self._pid, command)
            except (MovementError, EconomyError, CombatError) as exc:
                notify_warning(self, str(exc))
                return
            self._record(events)
            self._push_encounter()

        self.app.push_screen(ConfirmScreen(message, confirm_label="Attack"), _go)

    def _hail_species(self, species_id: int) -> None:
        """Open contact with a specific species in this sector (§6, WP9).

        A hail can be refused — most notably the roaming Entity, whose contact is
        sensor-gated at Legendary difficulty (§7, WP35) — so a rejected hail notifies
        rather than opening the screen.
        """
        try:
            events = self._service.apply(self._pid, Hail(species_id))
        except (MovementError, EconomyError) as exc:
            notify_warning(self, str(exc))
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

    def action_status(self) -> None:
        """Open the `I` status drawer (WP-UI12): the full ship readout plus a focusable
        list of every object here — the keyboard equivalent of the scene hotspots,
        and the compact tier's stand-in for the hidden sidebar."""
        from edge.tui.screens.status_drawer import StatusDrawerScreen
        view = self._service.game_view(self._pid)

        def _picked(result: tuple[str, int | str | None] | None) -> None:
            if result is not None:  # route through the one shared Picked handler
                self.post_message(ClickableEntry.Picked(*result))

        self.app.push_screen(
            StatusDrawerScreen(view, presence=_presence_lines(view.sector)), _picked)

    def action_engine_room(self) -> None:
        self.app.mark_objective("inspect")  # type: ignore[attr-defined]
        self.app.push_screen(EngineRoomScreen(
            self._service.engine_room_view(self._pid), self._service, self._pid))

    def action_territory(self) -> None:
        """Deploy fighters/mines/beacons and work the devices (§10/§14 — WP72)."""
        from edge.tui.screens.territory import TerritoryScreen
        self.app.push_screen(TerritoryScreen(self._service, self._pid))

    def action_messages(self) -> None:
        self.app.push_screen(ComputerScreen(self._service, self._pid, initial_tab="log"))

    def action_corp(self) -> None:
        self.app.push_screen(CorpScreen(self._service, self._pid))

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen(self))

    def action_dismiss_objectives(self) -> None:
        """Hide the Captain's-objectives strip (WP-UI11); Options re-enables it."""
        for strip in self.query(ObjectivesStrip):
            strip.remove()
        self.app.update_ui_settings(show_onboarding=False)  # type: ignore[attr-defined]
        self.notify("Objectives hidden — re-enable in Options (main menu).", timeout=3)

    # --- event ticker --------------------------------------------------------

    def _record(self, events: tuple[Event, ...]) -> None:
        self._log.extend(line for line in map(self._service.describe_event, events) if line)
