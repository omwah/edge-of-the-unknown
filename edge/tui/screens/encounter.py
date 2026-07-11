"""EncounterScreen — the live fight/flee rounds (UI_MOCKUPS.md §7, DESIGN §10, WP24/25).

Drives the real `GameService`: each keypress issues one `CombatAction` command (one
combat round — the player's action plus the pack's volley) and recomposes from the
fresh `encounter_view`. The flee chance shown is the same `combat.flee_chance` number
the reducer rolls (the H4 view/reducer lockstep). The screen pops when the encounter
resolves (fled / victory / destroyed); movement stays blocked while it is live, so
there is no way to walk away from the modal without resolving it.
"""

from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Static

from edge.core.combat import CombatError
from edge.core.economy import EconomyError
from edge.core.engine_room import EngineRoomError
from edge.core.enums import Subsystem
from edge.core.events import CombatRound, EncounterEnded
from edge.core.movement import MovementError
from edge.core.rules import CombatAction
from edge.tui.chrome import notify_warning
from edge.tui import art_adapter
from edge.tui.widgets import bar
from edge.server.service import GameService


_OUTCOME_NOTES: "dict[str, tuple[str, Literal['information', 'warning', 'error']]]" = {
    "fled": ("Broke away — you escaped the engagement.", "warning"),
    "victory": ("Victory — the pack is destroyed.", "information"),
    "destroyed": ("Ship lost — the escape pod tumbles clear.", "error"),
}


class EncounterScreen(Screen[None]):
    BINDINGS = [
        Binding("f", "fight", "Fire"),
        Binding("m", "missile", "Missile"),
        Binding("r", "flee", "Flee"),
        Binding("k", "patch", "Field-patch"),
        # A live fight has no Esc (fight or flee) — but a *resolved* one must always be
        # exitable, so a stale screen can never strand the player.
        Binding("escape", "close_if_over", "Close", show=False),
    ]

    HELP_TITLE = "Encounter"
    HELP = """\
A live fight has no Esc — fight, missile, patch, or flee. Once it resolves,
[b]Esc[/] returns to the sector. Your escape chance never drops below the
configured floor; firing arcs decide who can answer."""

    CSS = """
    EncounterScreen #enc-title {
        dock: top; height: 1; background: $error; color: $background;
        text-style: bold; padding: 0 1;
    }
    EncounterScreen #enc-disp {
        height: 1; padding: 0 1; color: $text-muted; border-bottom: solid $error;
    }
    EncounterScreen #enc-body { height: 1fr; }
    EncounterScreen #enc-speech { height: auto; padding: 0 2; color: $warning; }
    EncounterScreen #enc-main { height: auto; padding: 1 2; }
    EncounterScreen #them {
        width: 1fr; height: auto; border: round $error; padding: 0 1;
    }
    EncounterScreen #you {
        width: 1fr; height: auto; border: round $primary; padding: 0 1; margin-left: 2;
    }
    EncounterScreen .arc { color: $text-muted; margin-top: 1; }
    EncounterScreen #enc-result {
        height: auto; min-height: 3; padding: 0 1; margin: 0 2;
        border: round $secondary;
    }
    EncounterScreen #enc-advice {
        height: auto; padding: 0 2; color: $text-muted;
    }
    EncounterScreen #enc-actions {
        height: auto; padding: 0 2 1 2; border-top: solid $error;
    }
    EncounterScreen #enc-actions Button { width: 1fr; margin-right: 1; }
    EncounterScreen.compact #enc-main { padding: 0; }
    EncounterScreen.compact #them, EncounterScreen.compact #you { padding: 0 1; margin: 0; }
    EncounterScreen.compact .foe-art { display: none; }
    EncounterScreen.compact #enc-result { margin: 0; min-height: 3; }
    EncounterScreen.compact #enc-advice { padding: 0; }
    EncounterScreen.compact #enc-actions { padding: 0; }
    EncounterScreen.compact #enc-actions Button { min-width: 12; height: 3; margin: 0; }
    EncounterScreen.wide #them { width: 3fr; }
    EncounterScreen.wide #you { width: 2fr; }
    """

    def __init__(self, service: GameService, player_id: int) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id
        self._last_round = "Opening engagement · choose a tactical action."

    def compose(self) -> ComposeResult:
        e = self._service.encounter_view(self._pid)
        if e is None:  # resolved between refreshes — nothing to show
            yield Static("The engagement is over.", id="enc-title")
            yield Static("\n[dim]Press Esc to return to your ship.[/]")
            yield Footer()
            return
        yield Static(f"ENCOUNTER · {e.title}        [b]they OPEN FIRE[/]", id="enc-title")
        yield Static(
            f"disposition [red]{bar(e.disposition_filled, 5)}[/] {e.band}        "
            f"detection: they spotted you",
            id="enc-disp",
        )
        with VerticalScroll(id="enc-body"):
            if e.speech:  # the pack's spoken combat beat (§6.7, WP31), in its own voice
                yield Static(f'[italic]“{e.speech}”[/]', id="enc-speech")
            with Horizontal(id="enc-main"):
                with Vertical(id="them") as them:
                    them.border_title = "ENEMY PACK"
                    if e.foes:
                        entity, sub = art_adapter.ship_entity(e.foes[0].name)
                        yield Static(art_adapter.sprite(
                            entity, sub, seed=len(e.foes), width=22, height=5, facing="left"),
                            classes="foe-art")
                    for s in e.foes:
                        mark = "[white]>[/]" if s.alive else "[dim]x[/]"
                        yield Static(
                            f"{mark} {s.name:<20} HULL [red]{bar(s.hull_filled)}[/] {s.hull_pct:>3}%\n"
                            f"  ARC {s.firing_arc.replace('_', ' ')}"
                        )
                with Vertical(id="you") as you:
                    you.border_title = "YOUR SHIP"
                    yield Static(f"◇ SHIELDS [cyan]{bar(e.shields_pct // 10)}[/] {e.shields_pct:>3}%")
                    yield Static(f"△ HULL    [green]{bar(e.hull_pct // 10)}[/] {e.hull_pct:>3}%")
                    yield Static(f"→ {e.combat_line}")
                    flag = "[red]\\[!][/]" if e.integrity_flag != "all nominal" else "[dim]\\[ ][/]"
                    yield Static(f"{flag} COMPONENTS  {e.integrity_flag}")
            result = Static(self._last_round, id="enc-result")
            result.border_title = "CURRENT ROUND RESULT"
            yield result
            yield Static(
                f"TACTICAL · Round {e.round_no} · Flee [b]{e.flee_chance}%[/] "
                f"(hard floor {e.flee_floor}%)\n"
                f"FIRING ARC · {e.arc_hint or 'no arc advantage known'} · "
                "Missiles ignore firing arcs.",
                id="enc-advice",
            )
            with Horizontal(id="enc-actions"):
                yield Button("▶ FIRE [F]", id="btn-fight", variant="error",
                             disabled=not e.gun_online)
                yield Button(f"◆ MISSILE [M] ×{e.missiles}", id="btn-missile",
                             disabled=e.missiles <= 0)
                yield Button("↱ FLEE [R]", id="btn-flee", variant="warning")
                yield Button(f"⚒ PATCH [K] ×{e.repair_kits}", id="btn-patch",
                             disabled=e.repair_kits <= 0 or self._first_knocked_out() is None)
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "btn-fight": self.action_fight,
            "btn-missile": self.action_missile,
            "btn-flee": self.action_flee,
            "btn-patch": self.action_patch,
        }
        handler = actions.get(event.button.id or "")
        if handler is not None:
            self.run_worker(handler())

    # --- actions: one CombatAction command per keypress -----------------------

    def action_close_if_over(self) -> None:
        """Esc leaves a *resolved* engagement; a live fight still has no way out."""
        if self._service.encounter_view(self._pid) is None:
            self.app.pop_screen()
        else:
            self.notify("No escape — fight or flee.", timeout=2)

    async def _act(self, action: CombatAction) -> None:
        if self._service.encounter_view(self._pid) is None:
            # A stale screen (the fight resolved elsewhere) heals itself instead of
            # stranding the player behind "no live encounter".
            self.app.pop_screen()
            return
        try:
            events = self._service.apply(self._pid, action)
        except (CombatError, EngineRoomError, MovementError, EconomyError) as exc:
            notify_warning(self, str(exc))
            return
        ended = next((e for e in events if isinstance(e, EncounterEnded)), None)
        if ended is not None:
            note, severity = _OUTCOME_NOTES.get(ended.outcome, (ended.outcome, "information"))
            self.notify(note, title="Encounter", severity=severity, timeout=4)
            self.app.pop_screen()
            return
        round_event = next((e for e in events if isinstance(e, CombatRound)), None)
        if round_event is not None:
            action_label = {
                "fight": "FIRE", "launch_missile": "MISSILE",
                "flee": "FLEE", "field_patch": "PATCH",
            }.get(round_event.action, round_event.action.upper())
            self._last_round = (
                f"Round {round_event.round} · {action_label} · "
                f"damage dealt {round_event.damage_dealt} · "
                f"damage taken {round_event.damage_taken} · "
                f"foes remaining {round_event.foes_left}"
            )
        await self.recompose()

    async def action_fight(self) -> None:
        await self._act(CombatAction(action="fight"))

    async def action_missile(self) -> None:
        await self._act(CombatAction(action="launch_missile"))

    async def action_flee(self) -> None:
        await self._act(CombatAction(action="flee"))

    async def action_patch(self) -> None:
        target = self._first_knocked_out()
        if target is None:
            self.notify("Nothing is knocked out.", timeout=2)
            return
        sub, idx = target
        await self._act(CombatAction(action="field_patch", subsystem=sub, slot_index=idx))

    def _first_knocked_out(self) -> tuple[Subsystem, int] | None:
        view = self._service.engine_room_view(self._pid)
        for panel in view.subsystems:
            for idx, slot in enumerate(panel.slots):
                if slot.state == "knocked":
                    return Subsystem(panel.name.lower().replace(" ", "_")), idx
        return None
