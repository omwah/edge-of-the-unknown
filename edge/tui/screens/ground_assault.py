"""Live tactical planetary assault over the authoritative client/DTO seam (GW-WP12).

This is the production adaptation of ``edge.groundwar.app.BattleScreen``.  It keeps
only cursor, camera, squad-composition, placement, radar, log, and flash state; every
legal-action set comes from ``AssaultExpeditionDTO`` and every mutation is a logged
``GameClient.apply`` command.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Footer, RichLog, Static

from edge.core.dto import AssaultCellDTO, AssaultExpeditionDTO, AssaultTrooperDTO
from edge.core.combat import CombatError
from edge.core.economy import EconomyError
from edge.core.events import GroundAssaultSettled
from edge.core.movement import MovementError
from edge.core.rules import (
    EndGroundTurn,
    ExtractGroundOperation,
    GroundBroadcast,
    GroundDrop,
    GroundFire,
    GroundJump,
    GroundMove,
)
from edge.groundwar.widgets import (
    AA_THREAT_BG,
    BUILDING_GLYPHS,
    EVENT_FLASH,
    EVENT_STYLES,
    GROUND_THREAT_BG,
    RUBBLE_ART,
    STRUCTURE_ART,
)
from edge.server.client import GameClient
from edge.tui.chrome import EdgeScreen
from edge.tui.composer import PlatoonComposer, SuitOption
from edge.tui.screens._ground_shared import (
    CURSOR_MOVES,
    FAST_MOVE_SCALE,
    PAN_MOVES,
    CroppedMapView,
    FlashTrackerMixin,
    LandingAnimationMixin,
    LandingFrame,
    clamp_camera,
    feature_colors as _feature_colors,
    feature_glyph as _feature_glyph,
    follow_camera,
    landing_frames,
    pan_camera,
    styled as _styled,
    toggle_log_height,
    viewport_size,
    warn,
)
from edge.tui.screens.confirm import ConfirmScreen

_FLASH_SECONDS = 0.5
_LOG_COLLAPSED_H = 3
_LOG_EXPANDED_H = 12


@dataclass(frozen=True)
class _DropSlot:
    suit_id: str
    number: int


_RESULT_TITLES: dict[str, tuple[str, str]] = {
    "surrender": ("bold bright_green", "🏳 SURRENDER"),
    "wiped": ("bold red", "☠ WIPED OUT"),
    "casualties": ("bold red", "⚠ MISSION ABORTED"),
    "retrieval": ("bold yellow", "⏱ RETRIEVAL"),
}


def _result_headline(planet: str, settled: GroundAssaultSettled) -> str:
    if settled.control == "protectorate":
        return f"{planet} yields — it is now your protectorate."
    if settled.control == "conquest":
        return f"{planet} is conquered and annexed to your holdings."
    if settled.outcome == "wiped":
        return f"The platoon is gone. {planet} remains unbowed."
    if settled.outcome == "casualties":
        return (f"Casualties passed the doctrine ceiling — survivors recalled. "
                f"{planet}'s defenses remain intact.")
    if settled.outcome == "retrieval":
        return f"The retrieval boat lifted with {planet} unbowed."
    return f"The assault on {planet} has ended ({settled.outcome})."


class AssaultResultModal(ModalScreen[None]):
    """The settled outcome of an assault that has already resolved (win or loss).

    Replaces the "Abort and retrieve the survivors?" confirm framing once there is
    nothing left to fight for — that confirm exists to protect mid-fight losses, which
    no longer apply once `outcome` is set (GW-WP12-FU2)."""

    BINDINGS = [Binding("escape", "close", "Close"), Binding("enter", "close", "Close")]
    CSS = """
    AssaultResultModal { align: center middle; background: $background 60%; }
    AssaultResultModal #result-box {
        width: 58; max-width: 100%; height: auto; padding: 1 2;
        border: round $secondary; background: $surface;
    }
    AssaultResultModal #result-stats { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, planet: str, settled: GroundAssaultSettled) -> None:
        super().__init__()
        self._planet = planet
        self._settled = settled

    def compose(self) -> ComposeResult:
        style, title = _RESULT_TITLES.get(self._settled.outcome, ("bold", "OPERATION ENDED"))
        stats = (f"{self._settled.attacker_losses} troopers lost · "
                 f"{self._settled.defender_losses} defenders eliminated")
        if self._settled.loot:
            stats += f" · {self._settled.loot:,} slips looted"
        with Vertical(id="result-box", classes="modal-box"):
            yield Static(f"[{style}]{title}[/]")
            yield Static(_result_headline(self._planet, self._settled))
            yield Static(stats, id="result-stats")
            yield Static("[dim]Esc or Enter to return to orbit[/]")

    def action_close(self) -> None:
        self.dismiss(None)


class AssaultMapView(CroppedMapView):
    """Cropped DTO viewport with mouse cursor selection and transient command FX."""

    def __init__(self, host: GroundAssaultScreen) -> None:
        super().__init__(host, "assault-map", "Loading assault…")
        self._cells: dict[tuple[int, int], AssaultCellDTO] = {}
        self._troopers: dict[int, AssaultTrooperDTO] = {}
        self._garrison: dict[int, Any] = {}

    def _index_view(self, view: AssaultExpeditionDTO) -> None:
        self._cells = {(cell.x, cell.y): cell for cell in view.cells}
        self._troopers = {t.trooper_id: t for t in view.troopers}
        self._garrison = {u.unit_id: u for u in view.garrison}

    def _extra_frame_key(self, view: AssaultExpeditionDTO) -> tuple[Any, ...]:
        # Placements are pure client-side state (no server round trip until the drop
        # commits), so they must invalidate the cache themselves; show_threat likewise,
        # since it repaints backgrounds the cached frame already baked in. The descent
        # animation replaces glyphs, not just styles, so its step counter invalidates
        # too — the DTO itself doesn't change mid-animation (`GroundDrop` already
        # landed the troopers server-side before the capsules visually finish falling).
        return (self.host_screen.show_threat, tuple(self.host_screen.placements),
                self.host_screen.anim_step)

    def _render_frame(self, view: AssaultExpeditionDTO) -> Text:
        """Build the immutable viewport once; cursor moves only restyle a copied cell."""
        placements = {position: slot for slot, position in self.host_screen.placements}
        out = Text(no_wrap=True)
        for row in range(view.viewport_height):
            y = view.viewport_y + row
            for col in range(view.viewport_width):
                x = view.viewport_x + col
                cell = self._cells.get((x, y))
                if cell is None:
                    out.append(" ")
                    continue
                char, style = self._cell(cell, view)
                slot = placements.get((x, y))
                if slot is not None:
                    option = next(
                        (o for o in view.loadout.options if o.suit_id == slot.suit_id),
                        None,
                    ) if view.loadout is not None else None
                    char = option.label[:1].upper() if option is not None else "▼"
                    style = "black on bright_green"
                out.append(char, style)
            if row < view.viewport_height - 1:
                out.append("\n")
        return out

    def _cell(self, cell: AssaultCellDTO, view: AssaultExpeditionDTO) -> tuple[str, str]:
        animated = self.host_screen.anim_cells.get((cell.x, cell.y))
        if animated is not None:
            return animated
        if cell.trooper_id:
            trooper = self._troopers[cell.trooper_id]
            selected = trooper.trooper_id == view.selected_actor_id
            return trooper.glyph, ("black on bright_green" if selected
                                   else "black on yellow" if trooper.detected
                                   else "black on green")
        if cell.garrison_id:
            unit = self._garrison[cell.garrison_id]
            return ("T" if unit.kind == "armor" else "i"), "white on dark_red"
        if cell.structure_id:
            if cell.structure_hp <= 0:
                char, fg, bg = RUBBLE_ART
            else:
                char, fg, bg = STRUCTURE_ART.get(cell.structure_kind, ("?", "white", "black"))
                # GW-WP27: a multi-cell footprint draws as a connected floorplan outline
                # — the kind glyph (▪/⌂/⊕/✸) marks only its one visual-centre cell, chosen
                # server-side (`AssaultMap.marker_cells`) so every client agrees on which
                # cell that is even at a viewport's edge. `building_mask == 0` covers both
                # an ordinary 1x1 structure and a footprint's isolated corner, and both
                # fall back to the kind glyph correctly.
                if cell.building_mask and not cell.structure_marker:
                    char = BUILDING_GLYPHS[cell.building_mask]
                if cell.structure_hp < cell.structure_hp_max:
                    fg = "orange1"
            return char, f"{fg} on {bg}"
        fg, bg = _feature_colors(view.ptype, cell.feature)
        char = _feature_glyph(view.planet_id, cell.feature, cell.x, cell.y, cell.wall_mask)
        if cell.move_reachable:
            bg = "grey27"
        if self.host_screen.show_threat:
            if cell.aa_threat:
                return char, f"{fg} {AA_THREAT_BG}"
            if cell.ground_threat:
                return char, f"{fg} {GROUND_THREAT_BG}"
        return char, _styled(fg, bg)


class GroundAssaultScreen(FlashTrackerMixin, LandingAnimationMixin, EdgeScreen):
    """Compose, deploy, command, and extract one authoritative planetary assault."""

    BINDINGS = [
        Binding("escape", "extract", "Extract"),
        Binding("enter", "confirm", "Place / Move"),
        Binding("m", "move", "Move"),
        Binding("g", "jump", "Jump"),
        Binding("f", "fire", "Fire"),
        Binding("i", "missile", "Missile"),
        Binding("b", "broadcast", "Terms"),
        Binding("space", "end_turn", "End turn"),
        Binding("y", "radar", "Radar"),
        Binding("r", "recenter", "Recenter"),
        Binding("u", "undo", "Undo drop"),
        Binding("z", "log_expand", "Expand log"),
    ]
    ACTION_DANGER = {"extract": "destructive"}
    HELP_TITLE = "Planetary assault"
    _HELP = """\
The objective is [b]surrender[/], not extermination. Military targets, cowed cities,
and a Command suit's [b]B[/]roadcast drain Resolve; civilian destruction and your own
casualties harden it. The server highlights only legal actions for the selected trooper
and reveals enemies only when your surviving suits see them.

A city's buildings can span several cells — a kind glyph ([indian_red]▪[/]/[grey74]⌂[/]/…)
marks only its footprint's one visual-centre cell; the rest of that same building draws
as a connected outline in the same colour, so treat the whole coloured cluster as one
structure, not several.

Compose a platoon, then place each capsule with arrows or the mouse and [b]Enter[/].
After touchdown [b]Tab[/] selects a ready trooper; [b]M[/] moves, [b]G[/] jumps through
terrain (drawing AA fire), [b]F[/] fires, [b]I[/] spends a missile, and [b]Space[/]
runs the planet's turn. [b]Y[/] shows weapon ranges only for defenses you can see.

A Scout's sensor jamming keeps your platoon undetected — an undetected trooper's first
shot lands with a bonus, and firing reveals you. The clock runs both ways: sorties
launch and defender accuracy escalates the longer a fight drags on, so don't dawdle.
Losses past the sidebar's abort threshold force a doctrine recall, survivors only.

Extraction always works; mid-fight it confirms because tactical losses and damage
settle, and once the assault is decided it settles straight away with the result."""
    _HELP_BOT_ADDENDUM = """

Watching a bot: [b]Ctrl+S[/] runs or pauses it, [b]Ctrl+N[/] steps one action at a time,
[b]Ctrl+D[/]/[b]Ctrl+U[/] slow it down or speed it up. Your own cursor and pan keys
still work; using them suspends the camera's auto-follow so the bot stops dragging the
view back, until [b]R[/] recentres and resumes it."""
    HELP_LEGEND_ROWS = [
        ("[black on green]M[/] [black on green]S[/] [black on green]C[/]", "your powered suits"),
        ("[white on dark_red]i[/] [white on dark_red]T[/]", "visible infantry / armor"),
        ("[bright_red on grey30]╬[/] [orange1 on grey23]⊕[/]", "turret / anti-air battery"),
        ("[bright_cyan on grey23]⍑[/] [bright_magenta on grey30]✸[/]", "sensor / citadel gun"),
        ("[indian_red on grey23]▪[/] [grey74 on grey23]⌂[/]",
         "[indian_red]military[/] / [grey74]civilian[/] block"),
        ("[white on grey27] [/]", "legal walking destination for the selected trooper"),
    ]

    @property
    def HELP(self) -> str:  # noqa: N802 — HelpScreen reads this like the class constant it replaces
        """Bot-piloting controls only belong here while a bot is actually flying this
        operation (`GroundwarApp.bot`, duck-typed to avoid an upward import into
        `edge.groundwar` — see AGENTS.md's layering rule)."""
        if getattr(self.app, "bot", None) is not None:
            return self._HELP + self._HELP_BOT_ADDENDUM
        return self._HELP

    CSS = """
    GroundAssaultScreen #assault-main { height: 1fr; layout: horizontal; }
    GroundAssaultScreen #assault-map { width: 1fr; height: 1fr; overflow: hidden; }
    GroundAssaultScreen #assault-side {
        width: 36; height: 1fr; padding: 0 1; border-left: solid $primary;
    }
    GroundAssaultScreen #assault-log { dock: bottom; height: 3; border-top: solid $primary; }
    GroundAssaultScreen #assault-compose { width: 76; max-width: 100%; height: auto;
        padding: 1 2; border: round $primary; }
    GroundAssaultScreen.compact #assault-main { layout: vertical; }
    GroundAssaultScreen.compact #assault-side {
        width: 1fr; height: 10; border-left: none; border-top: solid $primary;
    }
    GroundAssaultScreen.wide #assault-side { width: 42; }
    """

    def __init__(self, client: GameClient) -> None:
        super().__init__()
        self._client = client
        self.view: AssaultExpeditionDTO | None = None
        self.cursor_x = 0
        self.cursor_y = 0
        self.camera_x = 0
        self.camera_y = 0
        self.selected_actor_id: int | None = None
        self._loadout: dict[str, int] | None = None
        self._slots: list[_DropSlot] = []
        self.placements: list[tuple[_DropSlot, tuple[int, int]]] = []
        self.show_threat = False
        self.log_expanded = False
        self._flashes: dict[tuple[int, int], tuple[str, float]] = {}
        self.anim_cells: dict[tuple[int, int], tuple[str, str]] = {}
        self.anim_step = 0
        self._anim_frames: list[LandingFrame] = []
        self._anim_timer: Timer | None = None
        self._extracting = False
        # GW bot-pilot spectating: a bot's `observe(..., follow=True)` hard-recentres the
        # camera on the active trooper every step, which fights any manual pan/cursor move
        # you make while watching. One of those keys sets this, which `observe` then reads
        # to skip its own recentre until `action_recenter` (R) explicitly resumes it.
        self._auto_follow_suspended = False

    def compose(self) -> ComposeResult:
        if self.view is None:
            yield Static("Connecting to the drop ship…")
            return
        if not self.view.dropped and self._loadout is None:
            force = self.view.loadout
            assert force is not None
            with Vertical(id="assault-compose"):
                yield Static(f"[b]ASSAULT · {self.view.planet}[/]\n"
                             "Choose which of your ship's owned suits ride this drop — buy "
                             "more at Stardock's Marines tab. Casualties lose both the "
                             "recruit and suit permanently.")
                yield PlatoonComposer(
                    [SuitOption.from_dto(option) for option in force.options],
                    max_troopers=force.max_troopers, drop_label="PLACE CAPSULES",
                )
            yield Footer()
            return
        with Container(id="assault-main"):
            yield AssaultMapView(self)
            with Vertical(id="assault-side"):
                yield Static(id="assault-status")
        yield RichLog(id="assault-log", markup=True, wrap=True)
        yield Footer()

    async def on_mount(self) -> None:
        await self._load(center=True)
        await self.recompose()
        self.call_after_refresh(self._settle_viewport, center=True)
        self._focus_map()

    async def _settle_viewport(self, *, center: bool) -> None:
        """Refetch once the compositor has actually laid out `AssaultMapView`.

        The very first `_load` of a run is always fetched before the map widget has
        been mounted (`compose` shows the squad chooser, or nothing, until then), so
        `_viewport_size`'s no-widget fallback stands in for it. If the widget's actual
        size differs, that first frame renders fewer/more cells than the widget is wide
        or tall, leaving blank space at its bottom/right edge until an incidental resize
        happens to correct it. Scheduled via `call_after_refresh` rather than run
        straight after `recompose` — immediately after mounting, `AssaultMapView.size`
        is still its pre-layout `(0, 0)` (Textual only resolves it during the next
        compositor pass), so an inline refetch would just settle on a *different* wrong
        size instead of the real one. `center=True` also re-centres using that now-correct
        size — the prior centering pass ran against the same too-small guess, so it can
        leave the camera short of the map's edge even once the size itself is fixed.
        """
        if self.query(AssaultMapView):
            await self._load(center=center)

    async def on_screen_resume(self) -> None:
        # Skip once extraction has started: _extract() owns returning to the screen
        # beneath this one, and this resume-triggered _load() can otherwise race it
        # (both see the operation gone and pop — the second pop lands one screen too
        # deep, past wherever _extract()'s own pop already landed).
        if self._extracting:
            return
        if self.view is not None:
            await self._load()

    async def on_resize(self) -> None:
        if self.view is not None and (self.view.dropped or self._loadout is not None):
            await self._load()

    def _focus_map(self) -> None:
        maps = self.query(AssaultMapView)
        if maps:
            maps.first().focus()
            logs = self.query("#assault-log")
            if logs:
                logs.first().can_focus = False

    def _viewport_size(self) -> tuple[int, int]:
        maps = self.query(AssaultMapView)
        if not maps:
            return 80, 30
        return viewport_size(maps.first())

    async def _load(self, *, center: bool = False) -> None:
        width, height = self._viewport_size()
        view = await self._client.ground_operation_view(
            viewport_x=self.camera_x, viewport_y=self.camera_y,
            viewport_width=width, viewport_height=height,
            selected_actor_id=self.selected_actor_id,
        )
        if view is None or not isinstance(view, AssaultExpeditionDTO):
            self.app.pop_screen()
            return
        previous_outcome = self.view.outcome if self.view is not None else None
        self.view = view
        if view.outcome is not None and previous_outcome is None:
            self._announce_outcome(view.outcome)
        if view.dropped and self.selected_actor_id is None:
            living = next((trooper for trooper in view.troopers
                           if trooper.alive and trooper.actions > 0), None)
            if living is not None:
                self.selected_actor_id = living.trooper_id
                await self._load(center=center)
                return
        if center:
            if view.troopers:
                living = next((t for t in view.troopers if t.alive), None)
                if living is not None:
                    self.cursor_x, self.cursor_y = living.x, living.y
            else:
                first = next((c for c in view.cells if c.landable), view.cells[0])
                self.cursor_x, self.cursor_y = first.x, first.y
            # Clamped against the map's far edges too (not just 0 on the near ones): a
            # drop point near the right/bottom of a map otherwise leaves the camera
            # pointed partway off it, and the server can only return however much of
            # the requested viewport is still on the map — the rest of the widget
            # renders blank even though real terrain sits just to the left/above.
            self.camera_x, self.camera_y = clamp_camera(
                self.cursor_x - width // 2, self.cursor_y - height // 2,
                width, height, view.map_width, view.map_height)
            if (self.camera_x, self.camera_y) != (view.viewport_x, view.viewport_y):
                await self._load()
                return
        self.camera_x, self.camera_y = view.viewport_x, view.viewport_y
        self._refresh_widgets()

    async def _follow_cursor(self) -> None:
        view = self.view
        if view is None:
            return
        nx, ny = follow_camera(
            self.cursor_x, self.cursor_y, self.camera_x, self.camera_y,
            view.viewport_width, view.viewport_height, view.map_width, view.map_height)
        if (nx, ny) != (self.camera_x, self.camera_y):
            self.camera_x, self.camera_y = nx, ny
            await self._load()

    async def _pan(self, dx: int, dy: int) -> None:
        view = self.view
        if view is None:
            return
        moved = pan_camera(
            self.camera_x, self.camera_y, self.cursor_x, self.cursor_y, dx, dy,
            view.viewport_width, view.viewport_height, view.map_width, view.map_height)
        if moved is None:
            return
        self.camera_x, self.camera_y, self.cursor_x, self.cursor_y = moved
        await self._load()

    async def set_cursor(self, x: int, y: int) -> None:
        if self.view is None:
            return
        self.cursor_x = max(0, min(self.view.map_width - 1, x))
        self.cursor_y = max(0, min(self.view.map_height - 1, y))
        await self._follow_cursor()
        self._refresh_widgets()

    def _cell_here(self) -> AssaultCellDTO | None:
        if self.view is None:
            return None
        return next((cell for cell in self.view.cells
                     if (cell.x, cell.y) == (self.cursor_x, self.cursor_y)), None)

    def cursor_is_legal(self) -> bool:
        """`CroppedMapView`'s cursor-highlight hook: landable pre-drop, else a legal
        move/jump/fire/missile target for the selected trooper."""
        cell = self._cell_here()
        if cell is None:
            return False
        if self.view is not None and not self.view.dropped:
            return cell.landable and (cell.x, cell.y) not in {p for _, p in self.placements}
        return any((cell.move_reachable, cell.jump_reachable,
                    cell.fire_target, cell.missile_target))

    async def on_platoon_composer_dropped(self, event: PlatoonComposer.Dropped) -> None:
        self._loadout = event.loadout
        self._slots = [
            _DropSlot(suit_id, number)
            for suit_id, count in event.loadout.items() for number in range(1, count + 1)
        ]
        await self.recompose()
        self.call_after_refresh(self._settle_viewport, center=True)
        self._focus_map()
        self._refresh_widgets()

    async def on_key(self, event: events.Key) -> None:
        if self._landing_playing:  # any key skips the descent
            self._end_landing()
            event.stop()
            return
        if self.view is None:
            return
        if event.key in CURSOR_MOVES:
            dx, dy = CURSOR_MOVES[event.key]
            self._auto_follow_suspended = True
            await self.set_cursor(self.cursor_x + dx, self.cursor_y + dy)
            event.stop()
            return
        if event.key in ("H", "J", "K", "L"):
            dx, dy = CURSOR_MOVES[event.key.lower()]
            scale_x, scale_y = FAST_MOVE_SCALE
            self._auto_follow_suspended = True
            await self.set_cursor(self.cursor_x + dx * scale_x, self.cursor_y + dy * scale_y)
            event.stop()
            return
        if event.key in PAN_MOVES:
            self._auto_follow_suspended = True
            await self._pan(*PAN_MOVES[event.key])
            event.stop()
            return
        if event.key in ("tab", "shift+tab") and self.view.dropped:
            await self._select(1 if event.key == "tab" else -1)
            event.stop()

    async def _select(self, step: int) -> None:
        if self.view is None:
            return
        ready = [t for t in self.view.troopers if t.alive and t.actions > 0]
        if not ready:
            return
        ids = [t.trooper_id for t in ready]
        try:
            index = ids.index(self.selected_actor_id or -1)
        except ValueError:
            index = -1 if step > 0 else 0
        selected = ready[(index + step) % len(ready)]
        self.selected_actor_id = selected.trooper_id
        self.cursor_x, self.cursor_y = selected.x, selected.y
        await self._load()
        await self._follow_cursor()

    async def action_confirm(self) -> None:
        if self.view is None:
            return
        if not self.view.dropped:
            await self._place_or_drop()
        else:
            await self.action_move()

    async def _place_or_drop(self) -> None:
        if self.view is None or self._loadout is None or len(self.placements) >= len(self._slots):
            return
        if not self.cursor_is_legal():
            warn(self, "#assault-log", "That capsule cannot land there.")
            return
        slot = self._slots[len(self.placements)]
        self.placements.append((slot, (self.cursor_x, self.cursor_y)))
        if len(self.placements) < len(self._slots):
            self._refresh_widgets()
            return
        dropped_at = [pos for _, pos in self.placements]
        placements = tuple((s.suit_id, x, y) for s, (x, y) in self.placements)
        if await self._apply(GroundDrop(self.view.operation_id, placements)) is None:
            self.placements.pop()
            return
        self.placements = []  # spent — the capsule markers give way to the real troopers
        await self._load()
        first = next((t for t in self.view.troopers if t.alive and t.actions > 0), None)
        if first is not None:
            self.selected_actor_id = first.trooper_id
            self.cursor_x, self.cursor_y = first.x, first.y
            await self._load()
        if self.view is not None:
            troopers_at = {(t.x, t.y): t for t in self.view.troopers}
            touchdowns = [((x, y), troopers_at[(x, y)].glyph, "black on green")
                         for (x, y) in dropped_at if (x, y) in troopers_at]
            if touchdowns:
                self._play_landing(landing_frames(touchdowns))

    def action_undo(self) -> None:
        if self.view is None or self.view.dropped:
            return
        if not self.placements:
            warn(self, "#assault-log", "No capsule placements to undo yet.")
            return
        self.placements.pop()
        self._refresh_widgets()

    def note(self, text: str) -> None:
        """Write one markup line into the battle log.

        Public because the spectator (`edge.groundwar.spectate`) narrates the bot's
        *decisions* alongside the events they produce — the log is the only place on
        this screen that carries prose.
        """
        logs = self.query("#assault-log")
        if logs:
            logs.first().write(Text.from_markup(text))

    def _landing_log(self, text: str) -> None:
        self.note(text)

    async def _apply(self, command: Any) -> tuple[Any, ...] | None:
        try:
            events_out = await self._client.apply(command)
        except (MovementError, CombatError, EconomyError) as exc:
            warn(self, "#assault-log", str(exc))
            return None
        await self._narrate(events_out)
        return events_out

    async def _narrate(self, events_out: Sequence[Any]) -> None:
        """Write `events_out` to the battle log and flash the cells they name."""
        logs = self.query("#assault-log")
        log = logs.first() if logs else None
        until = time.monotonic() + _FLASH_SECONDS
        for event in events_out:
            name = type(event).__name__
            line = await self._client.describe_event(event)
            if line and log is not None:
                log.write(Text.from_markup(line, style=EVENT_STYLES.get(name, "white")))
            x, y = getattr(event, "x", -1), getattr(event, "y", -1)
            if x >= 0 and name in EVENT_FLASH:
                self._flashes[(x, y)] = (EVENT_FLASH[name], until)
        if self._flashes:
            self.set_timer(_FLASH_SECONDS + 0.05, self._refresh_widgets)

    async def observe(self, events_out: Sequence[Any], *, follow: bool = False) -> None:
        """Narrate events applied to the service by *someone else*, then re-pull the view.

        `_apply` is the player's path — submit a command, narrate what comes back. A bot
        (`edge.groundwar.spectate`) drives the same `GameService` directly, so its events
        never pass through this screen and neither the log nor the map would ever move.
        This is that same narrate-and-reload tail with the submit removed, which is what
        lets an unmodified assault screen act as a spectator view.

        Recomposes when the platoon lands, because `compose` serves a completely
        different tree before the drop (the squad chooser) than after it (the map), and
        a bot's `GroundDrop` crosses that boundary without the screen's own placement
        flow ever running.

        `follow` asks to recentre the camera on the action, but a manual pan/cursor move
        (`on_key`) suspends that until `action_recenter` (R) turns it back on — otherwise
        every bot step would drag your view straight back to where it wants to look.
        """
        if self._extracting or self.view is None:
            return
        was_dropped = self.view.dropped
        should_center = follow and not self._auto_follow_suspended
        await self._narrate(events_out)
        await self._load(center=should_center)
        if self.view is not None and self.view.dropped and not was_dropped:
            await self.recompose()
            self.call_after_refresh(self._settle_viewport, center=should_center)
            self._focus_map()

    def _selected_trooper(self) -> AssaultTrooperDTO | None:
        if self.view is None or self.selected_actor_id is None:
            return None
        return next((t for t in self.view.troopers if t.trooper_id == self.selected_actor_id), None)

    def _ready_trooper_or_warn(self) -> AssaultTrooperDTO | None:
        """The selected trooper if it can still act this round, else `None` after
        logging exactly why — the operation already resolved, no trooper selected,
        dead, or out of actions. Checking the resolved case first matters: once
        `outcome` is set the server reports every cell unreachable/untargetable
        (§ tactical_projection), so without this every action would otherwise warn
        a misleading "out of range" instead of "the assault is over"."""
        if self.view is not None and self.view.outcome is not None:
            warn(self, "#assault-log",
                f"This assault is over ({self.view.outcome}) — Esc settles to orbit.")
            return None
        trooper = self._selected_trooper()
        if trooper is None:
            warn(self, "#assault-log", "Select a ready trooper first (Tab).")
            return None
        if not trooper.alive:
            warn(self, "#assault-log", f"{trooper.name} is down and cannot act.")
            return None
        if trooper.actions <= 0:
            warn(self, "#assault-log", f"{trooper.name} has no actions left this round.")
            return None
        return trooper

    async def action_move(self) -> None:
        trooper = self._ready_trooper_or_warn()
        if trooper is None:
            return
        cell = self._cell_here()
        if cell is None or not cell.move_reachable:
            warn(self, "#assault-log", "Not a legal move there — out of range, blocked, or no path.")
            return
        if await self._apply(GroundMove(
            self.view.operation_id, cell.x, cell.y, trooper.trooper_id)) is not None:  # type: ignore[union-attr]
            await self._load()
            await self._maybe_auto_end_turn()

    async def action_jump(self) -> None:
        trooper = self._ready_trooper_or_warn()
        if trooper is None:
            return
        if trooper.jump_charges <= 0:
            warn(self, "#assault-log", f"{trooper.name} has no jump charges left.")
            return
        cell = self._cell_here()
        if cell is None or not cell.jump_reachable:
            warn(self, "#assault-log", "Can't jump there — out of jump range or the spot is occupied.")
            return
        if await self._apply(GroundJump(
            self.view.operation_id, trooper.trooper_id, cell.x, cell.y)) is not None:  # type: ignore[union-attr]
            await self._load()
            await self._maybe_auto_end_turn()

    async def _fire(self, missile: bool) -> None:
        trooper = self._ready_trooper_or_warn()
        if trooper is None:
            return
        if missile and trooper.missiles <= 0:
            warn(self, "#assault-log", f"{trooper.name} is out of missiles.")
            return
        cell = self._cell_here()
        legal = cell.missile_target if cell is not None and missile else (
            cell.fire_target if cell is not None else False)
        if cell is None or not legal:
            kind = "missile" if missile else "weapon"
            warn(self, "#assault-log", f"No target there — out of {kind} range or no line of sight.")
            return
        if await self._apply(GroundFire(
            self.view.operation_id, trooper.trooper_id, cell.x, cell.y, missile)) is not None:  # type: ignore[union-attr]
            await self._load()
            await self._maybe_auto_end_turn()

    async def action_fire(self) -> None:
        await self._fire(False)

    async def action_missile(self) -> None:
        await self._fire(True)

    async def action_broadcast(self) -> None:
        trooper = self._ready_trooper_or_warn()
        if trooper is None:
            return
        if not self.view.can_broadcast:  # type: ignore[union-attr]
            warn(self, "#assault-log",
                "No cowed city is in range of a Command suit's broadcast yet.")
            return
        if await self._apply(GroundBroadcast(
            self.view.operation_id, trooper.trooper_id)) is not None:  # type: ignore[union-attr]
            await self._load()
            await self._maybe_auto_end_turn()

    async def _maybe_auto_end_turn(self) -> None:
        """QoL for a one-trooper platoon: once its actions run out there is nothing
        else to command this round, so an opted-in player can skip pressing Space.
        Gated on `can_end_turn` so this never fires the "out of turns" warning on
        its own — only a manual Space press does that."""
        view = self.view
        if view is None or not view.dropped or view.outcome is not None or not view.can_end_turn:
            return
        settings = getattr(self.app, "ui_settings", None)
        if settings is None or not getattr(settings, "auto_end_turn_solo", False):
            return
        if len(view.troopers) != 1:
            return
        solo = view.troopers[0]
        if solo.alive and solo.actions <= 0:
            await self.action_end_turn()

    async def action_end_turn(self) -> None:
        if self.view is None:
            return
        if self.view.outcome is not None:
            warn(self, "#assault-log",
                f"This assault is over ({self.view.outcome}) — Esc settles to orbit.")
            return
        if not self.view.dropped:
            warn(self, "#assault-log", "Place your platoon before ending a round.")
            return
        if self.view.turns_remaining < self.view.next_turn_cost:
            warn(self, "#assault-log",
                "Out of main-game turns — you cannot end another round. Extract to "
                "return to orbit (Esc).")
            return
        if not self.view.can_end_turn:
            warn(self, "#assault-log", "Cannot end the round right now.")
            return
        if await self._apply(EndGroundTurn(self.view.operation_id)) is None:
            return
        self.selected_actor_id = None
        await self._load()
        await self._select(1)

    def action_radar(self) -> None:
        self.show_threat = not self.show_threat
        self._refresh_widgets()

    async def action_recenter(self) -> None:
        """Resume auto-follow (if a bot suspended it) and jump the camera back now."""
        self._auto_follow_suspended = False
        await self._load(center=True)

    def action_log_expand(self) -> None:
        self.log_expanded = not self.log_expanded
        toggle_log_height(self, "#assault-log", expanded=self.log_expanded,
                          collapsed_h=_LOG_COLLAPSED_H, expanded_h=_LOG_EXPANDED_H)

    def action_extract(self) -> None:
        if self.view is None:
            self.app.pop_screen()
            return
        if self.view.outcome is not None:
            # The operation already resolved (win or loss) — nothing left to lose by
            # extracting, so skip the destructive-abort confirm entirely.
            self._start_extract()
            return

        message = ("Abort this assault and retrieve the survivors? All casualties, spent "
                   "ordnance, defender losses, and structural damage will settle.")
        self.app.push_screen(
            ConfirmScreen(message, confirm_label="Extract survivors", deny_label="Keep fighting"),
            self._extract_confirmed,
        )

    def _extract_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self._start_extract()

    def _start_extract(self) -> None:
        # Set synchronously, before scheduling the worker: on_screen_resume can fire
        # (e.g. once ConfirmScreen or AssaultResultModal pops) before the worker below
        # gets a turn on the event loop, and it must see this screen is already leaving
        # to skip its own _load()-triggered self-pop (see on_screen_resume).
        self._extracting = True
        self.run_worker(self._extract())

    async def _extract(self) -> None:
        if self.view is None:
            self._extracting = False
            return
        planet, resolved = self.view.planet, self.view.outcome is not None
        events_out = await self._apply(ExtractGroundOperation(self.view.operation_id))
        if events_out is None:
            self._extracting = False
            return
        if resolved:
            settled = next((e for e in events_out if isinstance(e, GroundAssaultSettled)), None)
            if settled is not None:
                await self.app.push_screen(
                    AssaultResultModal(planet, settled), wait_for_dismiss=True)
                self.app.pop_screen()
                return
        self.app.pop_screen()

    _OUTCOME_LINES: dict[str, tuple[str, str]] = {
        "surrender": ("bold bright_green", "🏳 SURRENDER — the planetary government yields."),
        "wiped": ("bold red", "☠ WIPED OUT — the platoon is gone."),
        "casualties": ("bold red",
                       "⚠ MISSION ABORTED — casualties passed the doctrine ceiling."),
        "retrieval": ("bold yellow",
                      "⏱ RETRIEVAL — the boat lifts with the planet unbowed."),
    }

    def _announce_outcome(self, outcome: str) -> None:
        """The operation just resolved — say so loudly in the log, once, the moment it
        happens, instead of leaving it to the sidebar's passive status line (easy to
        miss) while every further action quietly refuses with no explanation."""
        style, text = self._OUTCOME_LINES.get(
            outcome, ("bold", f"OPERATION ENDED — {outcome.upper()}"))
        logs = self.query("#assault-log")
        if logs:
            logs.first().write(Text.from_markup(f"{text} Esc settles to orbit.", style=style))

    def _refresh_widgets(self) -> None:
        if self.view is None or not self.query(AssaultMapView):
            return
        self.query_one(AssaultMapView).refresh()
        self.query_one("#assault-status", Static).update(self._status())

    def _status(self) -> Text:
        assert self.view is not None
        view = self.view
        out = Text()
        out.append(f"ASSAULT · {view.planet}\n", "bold")
        if not view.dropped:
            out.append("\nPLACE CAPSULES\n", "bold bright_green")
            for index, slot in enumerate(self._slots):
                placed = index < len(self.placements)
                mark = "✓" if placed else "▶" if index == len(self.placements) else " "
                out.append(f" {mark} {slot.suit_id} {slot.number}\n",
                           "grey42" if placed else "bright_green" if mark == "▶" else "white")
            out.append("\nEnter place · U undo · mouse works\n", "grey66")
            return out
        left = max(0, view.retrieval_turn - view.local_turn)
        out.append(f"round {view.local_turn + 1} · retrieval in {left}\n", "bold red" if left <= 3 else "grey70")
        frac = min(1.0, view.resolve / max(1, view.resolve_start))
        fill = round(14 * frac)
        out.append(f"RESOLVE {'█' * fill}{'░' * (14 - fill)} {view.resolve}\n", "yellow")
        out.append(f"surrender at ≤ {view.surrender_threshold} · KIA "
                   f"{view.casualties}/{view.initial_strength} "
                   f"(abort past {view.casualty_ceiling:.0%})\n", "grey66")
        out_of_turns = view.turns_remaining < view.next_turn_cost
        out.append(f"main turns {view.turns_remaining} · next round costs {view.next_turn_cost}\n",
                   "bold red" if out_of_turns else "grey66")
        if out_of_turns and view.outcome is None:
            out.append("⚠ OUT OF TURNS — extract to return to orbit (Esc)\n", "bold red")
        out.append("\nPLATOON\n", "bold")
        for trooper in view.troopers:
            if not trooper.alive:
                out.append(f" ✝ {trooper.name}\n", "grey42")
                continue
            mark = "▶" if trooper.trooper_id == view.selected_actor_id else " "
            style = "bright_green" if mark == "▶" else "grey42" if not trooper.actions else "white"
            out.append(f" {mark}{trooper.glyph} {trooper.name:<10} {trooper.hp:>3}hp "
                       f"{'●' * trooper.actions}{' !' if trooper.detected else ''}\n", style)
        selected = next((t for t in view.troopers
                         if t.trooper_id == view.selected_actor_id), None)
        if selected is not None:
            out.append(f"\n{selected.suit_label}: missiles {selected.missiles} · "
                       f"jumps {selected.jump_charges}\n", "bright_cyan")
        out.append("\nCITIES\n", "bold")
        for city in view.cities:
            state = "terms" if city.broadcast_done else "cowed" if city.cowed else "resisting"
            out.append(f" {'⭑' if city.is_citadel else ' '} {city.name[:18]:<18} {state}\n",
                       "green" if city.cowed else "white")
        if view.outcome is not None:
            out.append(f"\n{view.outcome.upper()} — Esc settles to orbit\n",
                       "bold bright_green" if view.outcome == "surrender" else "bold red")
        else:
            out.append(f"\nY radar {'ON' if self.show_threat else 'off'} · Tab select\n", "grey66")
            out.append("M move · G jump · F/I fire · B terms\n", "grey66")
            out.append("Space planet turn · Esc extract\n", "grey66")
        return out
