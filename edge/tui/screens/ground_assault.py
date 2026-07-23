"""Live tactical planetary assault over the authoritative client/DTO seam (GW-WP12).

This is the production adaptation of ``edge.groundwar.app.BattleScreen``.  It keeps
only cursor, camera, squad-composition, placement, radar, log, and flash state; every
legal-action set comes from ``AssaultExpeditionDTO`` and every mutation is a logged
``GameClient.apply`` command.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, RichLog, Static

from edge.core.dto import AssaultCellDTO, AssaultExpeditionDTO, AssaultTrooperDTO
from edge.core.combat import CombatError
from edge.core.economy import EconomyError
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
    EVENT_FLASH,
    EVENT_STYLES,
    GROUND_THREAT_BG,
    RUBBLE_ART,
    STRUCTURE_ART,
)
from edge.server.client import GameClient
from edge.tui.chrome import EdgeScreen, notify_warning
from edge.tui.composer import PlatoonComposer, SuitOption
from edge.tui.screens.confirm import ConfirmScreen
from edge.tui.screens.ground_expedition import _feature_colors, _feature_glyph, _styled

_FLASH_SECONDS = 0.5
_LOG_COLLAPSED_H = 3
_LOG_EXPANDED_H = 12


@dataclass(frozen=True)
class _DropSlot:
    suit_id: str
    number: int


class AssaultMapView(Static, can_focus=True):
    """Cropped DTO viewport with mouse cursor selection and transient command FX."""

    def __init__(self, host: GroundAssaultScreen) -> None:
        super().__init__(id="assault-map")
        self.host_screen = host

    def render(self) -> Text:
        host = self.host_screen
        view = host.view
        if view is None:
            return Text("Loading assault…", style="dim")
        cells = {(cell.x, cell.y): cell for cell in view.cells}
        troopers = {trooper.trooper_id: trooper for trooper in view.troopers}
        garrison = {unit.unit_id: unit for unit in view.garrison}
        out = Text(no_wrap=True)
        flashes = host.live_flashes()
        placements = {position: slot for slot, position in host.placements}
        for row in range(view.viewport_height):
            y = view.viewport_y + row
            for col in range(view.viewport_width):
                x = view.viewport_x + col
                cell = cells.get((x, y))
                if cell is None:
                    out.append(" ")
                    continue
                char, style = self._cell(cell, view, troopers, garrison)
                slot = placements.get((x, y))
                if slot is not None:
                    option = next(
                        (o for o in view.loadout.options if o.suit_id == slot.suit_id),
                        None,
                    ) if view.loadout is not None else None
                    char = option.label[:1].upper() if option is not None else "▼"
                    style = "black on bright_green"
                if (x, y) in flashes:
                    style = f"{style.split(' on ')[0]} {flashes[(x, y)][0]}"
                if (x, y) == (host.cursor_x, host.cursor_y):
                    style = "black on bright_white" if host.cursor_legal() else "bright_white on red3"
                out.append(char, style)
            if row < view.viewport_height - 1:
                out.append("\n")
        return out

    def _cell(
        self, cell: AssaultCellDTO, view: AssaultExpeditionDTO,
        troopers: dict[int, AssaultTrooperDTO], garrison: dict[int, Any],
    ) -> tuple[str, str]:
        if cell.trooper_id:
            trooper = troopers[cell.trooper_id]
            selected = trooper.trooper_id == view.selected_actor_id
            return trooper.glyph, ("black on bright_green" if selected
                                   else "black on yellow" if trooper.detected
                                   else "black on green")
        if cell.garrison_id:
            unit = garrison[cell.garrison_id]
            return ("T" if unit.kind == "armor" else "i"), "white on dark_red"
        if cell.structure_id:
            if cell.structure_hp <= 0:
                char, fg, bg = RUBBLE_ART
            else:
                char, fg, bg = STRUCTURE_ART.get(cell.structure_kind, ("?", "white", "black"))
                if cell.structure_hp < cell.structure_hp_max:
                    fg = "orange1"
            return char, f"{fg} on {bg}"
        fg, bg = _feature_colors(view.ptype, cell.feature)
        char = _feature_glyph(view.planet_id, cell.feature, cell.x, cell.y)
        if cell.move_reachable:
            bg = "grey27"
        if self.host_screen.show_threat:
            if cell.aa_threat:
                return char, f"{fg} {AA_THREAT_BG}"
            if cell.ground_threat:
                return char, f"{fg} {GROUND_THREAT_BG}"
        return char, _styled(fg, bg)

    async def _on_click(self, event: events.Click) -> None:
        view = self.host_screen.view
        if view is not None:
            await self.host_screen.set_cursor(
                view.viewport_x + event.x, view.viewport_y + event.y)


class GroundAssaultScreen(EdgeScreen):
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
        Binding("u", "undo", "Undo drop"),
        Binding("z", "log_expand", "Expand log"),
    ]
    ACTION_DANGER = {"extract": "destructive"}
    HELP_TITLE = "Planetary assault"
    HELP = """\
The objective is [b]surrender[/], not extermination. Military targets, cowed cities,
and a Command suit's [b]B[/]roadcast drain Resolve; civilian destruction and your own
casualties harden it. The server highlights only legal actions for the selected trooper
and reveals enemies only when your surviving suits see them.

Compose a platoon, then place each capsule with arrows or the mouse and [b]Enter[/].
After touchdown [b]Tab[/] selects a ready trooper; [b]M[/] moves, [b]G[/] jumps through
terrain (drawing AA fire), [b]F[/] fires, [b]I[/] spends a missile, and [b]Space[/]
runs the planet's turn. [b]Y[/] shows weapon ranges only for defenses you can see.
Extraction always works, but it confirms because all tactical losses and damage settle."""
    HELP_LEGEND_ROWS = [
        ("[black on green]M[/] [black on green]S[/] [black on green]C[/]", "your powered suits"),
        ("[white on dark_red]i[/] [white on dark_red]T[/]", "visible infantry / armor"),
        ("[bright_red on grey30]╬[/] [orange1 on grey23]⊕[/]", "turret / anti-air battery"),
        ("[bright_cyan on grey23]⍑[/] [bright_magenta on grey30]✸[/]", "sensor / citadel gun"),
        ("[indian_red on grey23]▪[/] [grey74 on grey23]⌂[/]", "military / civilian block"),
        ("[white on grey27] [/]", "legal walking destination for the selected trooper"),
    ]

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

    def compose(self) -> ComposeResult:
        if self.view is None:
            yield Static("Connecting to the drop ship…")
            return
        if not self.view.dropped and self._loadout is None:
            force = self.view.loadout
            assert force is not None
            with Vertical(id="assault-compose"):
                yield Static(f"[b]ASSAULT · {self.view.planet}[/]\n"
                             "Choose carried suits for this drop. Casualties lose both "
                             "the recruit and suit permanently.")
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
        self._focus_map()

    async def on_screen_resume(self) -> None:
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
        widget = maps.first()
        return max(20, widget.size.width), max(8, widget.size.height)

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
        self.view = view
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
            self.camera_x = max(0, self.cursor_x - width // 2)
            self.camera_y = max(0, self.cursor_y - height // 2)
            if (self.camera_x, self.camera_y) != (view.viewport_x, view.viewport_y):
                await self._load()
                return
        self.camera_x, self.camera_y = view.viewport_x, view.viewport_y
        self._refresh_widgets()

    async def _follow_cursor(self) -> None:
        view = self.view
        if view is None:
            return
        mx, my = min(8, view.viewport_width // 3), min(3, view.viewport_height // 3)
        nx, ny = self.camera_x, self.camera_y
        if self.cursor_x < nx + mx:
            nx = self.cursor_x - mx
        elif self.cursor_x >= nx + view.viewport_width - mx:
            nx = self.cursor_x - view.viewport_width + mx + 1
        if self.cursor_y < ny + my:
            ny = self.cursor_y - my
        elif self.cursor_y >= ny + view.viewport_height - my:
            ny = self.cursor_y - view.viewport_height + my + 1
        nx = max(0, min(view.map_width - view.viewport_width, nx))
        ny = max(0, min(view.map_height - view.viewport_height, ny))
        if (nx, ny) != (self.camera_x, self.camera_y):
            self.camera_x, self.camera_y = nx, ny
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

    def cursor_legal(self) -> bool:
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
        self._focus_map()
        self._refresh_widgets()

    async def on_key(self, event: events.Key) -> None:
        moves = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
                 "k": (0, -1), "j": (0, 1), "h": (-1, 0), "l": (1, 0)}
        if event.key in moves and self.view is not None:
            dx, dy = moves[event.key]
            await self.set_cursor(self.cursor_x + dx, self.cursor_y + dy)
            event.stop()
            return
        if event.key in ("tab", "shift+tab") and self.view is not None and self.view.dropped:
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
        if not self.cursor_legal():
            notify_warning(self, "That capsule cannot land there.")
            return
        slot = self._slots[len(self.placements)]
        self.placements.append((slot, (self.cursor_x, self.cursor_y)))
        if len(self.placements) < len(self._slots):
            self._refresh_widgets()
            return
        placements = tuple((s.suit_id, x, y) for s, (x, y) in self.placements)
        if await self._apply(GroundDrop(self.view.operation_id, placements)) is None:
            self.placements.pop()
            return
        await self._load()
        first = next((t for t in self.view.troopers if t.alive and t.actions > 0), None)
        if first is not None:
            self.selected_actor_id = first.trooper_id
            self.cursor_x, self.cursor_y = first.x, first.y
            await self._load()

    def action_undo(self) -> None:
        if self.view is not None and not self.view.dropped and self.placements:
            self.placements.pop()
            self._refresh_widgets()

    async def _apply(self, command: Any) -> tuple[Any, ...] | None:
        try:
            events_out = await self._client.apply(command)
        except (MovementError, CombatError, EconomyError) as exc:
            notify_warning(self, str(exc))
            return None
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
        return events_out

    async def action_move(self) -> None:
        cell = self._cell_here()
        if self.view is None or cell is None or not cell.move_reachable or not self.selected_actor_id:
            return
        if await self._apply(GroundMove(
            self.view.operation_id, cell.x, cell.y, self.selected_actor_id)) is not None:
            await self._load()

    async def action_jump(self) -> None:
        cell = self._cell_here()
        if self.view is None or cell is None or not cell.jump_reachable or not self.selected_actor_id:
            return
        if await self._apply(GroundJump(
            self.view.operation_id, self.selected_actor_id, cell.x, cell.y)) is not None:
            await self._load()

    async def _fire(self, missile: bool) -> None:
        cell = self._cell_here()
        legal = cell.missile_target if cell is not None and missile else (
            cell.fire_target if cell is not None else False)
        if self.view is None or cell is None or not legal or not self.selected_actor_id:
            return
        if await self._apply(GroundFire(
            self.view.operation_id, self.selected_actor_id, cell.x, cell.y, missile)) is not None:
            await self._load()

    async def action_fire(self) -> None:
        await self._fire(False)

    async def action_missile(self) -> None:
        await self._fire(True)

    async def action_broadcast(self) -> None:
        if self.view is None or not self.view.can_broadcast or not self.selected_actor_id:
            return
        if await self._apply(GroundBroadcast(
            self.view.operation_id, self.selected_actor_id)) is not None:
            await self._load()

    async def action_end_turn(self) -> None:
        if self.view is None or not self.view.can_end_turn:
            return
        if await self._apply(EndGroundTurn(self.view.operation_id)) is None:
            return
        self.selected_actor_id = None
        await self._load()
        await self._select(1)

    def action_radar(self) -> None:
        self.show_threat = not self.show_threat
        self._refresh_widgets()

    def action_log_expand(self) -> None:
        self.log_expanded = not self.log_expanded
        logs = self.query("#assault-log")
        if logs:
            logs.first().styles.height = _LOG_EXPANDED_H if self.log_expanded else _LOG_COLLAPSED_H

    def action_extract(self) -> None:
        if self.view is None:
            self.app.pop_screen()
            return
        message = ("Abort this assault and retrieve the survivors? All casualties, spent "
                   "ordnance, defender losses, and structural damage will settle.")
        self.app.push_screen(
            ConfirmScreen(message, confirm_label="Extract survivors", deny_label="Keep fighting"),
            self._extract_confirmed,
        )

    def _extract_confirmed(self, confirmed: bool | None) -> None:
        if confirmed:
            self.run_worker(self._extract())

    async def _extract(self) -> None:
        if self.view is not None and await self._apply(
            ExtractGroundOperation(self.view.operation_id)) is not None:
            self.app.pop_screen()

    def live_flashes(self) -> dict[tuple[int, int], tuple[str, float]]:
        now = time.monotonic()
        self._flashes = {cell: flash for cell, flash in self._flashes.items() if flash[1] > now}
        return self._flashes

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
                   f"{view.casualties}/{view.initial_strength}\n", "grey66")
        out.append(f"main turns {view.turns_remaining} · next round costs {view.next_turn_cost}\n", "grey66")
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
