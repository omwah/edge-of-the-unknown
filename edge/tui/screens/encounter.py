"""EncounterScreen — hostile greeting-or-fight/flee (UI_MOCKUPS.md §7).

Phase-3 screen, stubbed here so engaging a hostile-band ship has somewhere to go.
A hostile opener (the species' disposition rolled to violence, DESIGN §10) shows
the enemy group per `pack_behavior`/`escort` with per-ship hull and a firing-arc
hint, the player's shields/hull/combat-speed and any knocked-out component, and
round controls whose flee chance is **clamped to the config escape-chance floor**.
A peaceful opener would reuse the §6 contact panel instead of these controls.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.tui import art_adapter
from edge.tui.dummy import EncounterDTO
from edge.tui.widgets import bar

_PLAYER_SHIP = "S.S. Wayfarer"  # the skeleton's single ship (matches the sidebar)


class EncounterScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Disengage"),
        Binding("f", "noop", "Fire"),
        Binding("m", "noop", "Missile"),
        Binding("e", "noop", "Evade"),
        Binding("r", "back", "Flee"),
        Binding("k", "noop", "Field-patch"),
    ]

    CSS = """
    EncounterScreen #enc-title {
        dock: top; height: 1; background: $error; color: $background;
        text-style: bold; padding: 0 1;
    }
    EncounterScreen #enc-disp {
        height: 1; padding: 0 1; color: $text-muted; border-bottom: solid $error;
    }
    EncounterScreen #taunt {
        height: auto; padding: 1 2 0 2; color: $warning; text-style: italic;
    }
    EncounterScreen #enc-main { height: 1fr; padding: 1 2; }
    EncounterScreen #them {
        width: 1fr; height: auto; border: round $error; padding: 0 1;
    }
    EncounterScreen #you {
        width: 1fr; height: auto; border: round $primary; padding: 0 1; margin-left: 2;
    }
    EncounterScreen .arc { color: $text-muted; margin-top: 1; }
    EncounterScreen #enc-round {
        height: 1; padding: 0 2; color: $secondary; text-style: bold;
    }
    EncounterScreen #enc-controls {
        height: auto; padding: 0 2 1 2; border-top: solid $error;
    }
    """

    def __init__(self, encounter: EncounterDTO) -> None:
        super().__init__()
        self._enc = encounter

    def compose(self) -> ComposeResult:
        e = self._enc
        yield Static(
            f"ENCOUNTER · {e.title}        [b]{e.opener}[/]", id="enc-title"
        )
        yield Static(
            f"disposition [red]{bar(e.disposition_filled, 5)}[/] {e.band}        "
            f"detection: {e.detection}",
            id="enc-disp",
        )
        yield Static(e.taunt, id="taunt")
        with Horizontal(id="enc-main"):
            with Vertical(id="them") as them:
                them.border_title = "THEM"
                if e.enemies:
                    # Art faces left -- the enemy group bears down on the player's ship.
                    entity, sub = art_adapter.ship_entity(e.enemies[0].name)
                    yield Static(art_adapter.sprite(
                        entity, sub, seed=len(e.enemies), width=22, height=6, facing="left"))
                for s in e.enemies:
                    yield Static(
                        f"[white]>[/] {s.name:<7} hull [red]{bar(s.hull_filled)}[/] "
                        f"{s.hull_pct:>2}%"
                    )
                yield Static(e.arc_hint, classes="arc")
            with Vertical(id="you") as you:
                you.border_title = f"YOU · {_PLAYER_SHIP}"
                yield Static(f"Shields  [cyan]{bar(e.shields_filled)}[/] {e.shields_pct:>2}%")
                yield Static(f"Hull     [green]{bar(e.hull_filled)}[/] {e.hull_pct:>2}%")
                yield Static(e.combat_line)
                yield Static(f"[red]\\[!][/] {e.integrity_flag}")
        yield Static(
            f"Round {e.round_no}      flee chance  [b]{e.flee_chance}%[/]  "
            f"[dim](floor {e.flee_floor}%)[/]",
            id="enc-round",
        )
        yield Static(
            "[b]F[/] Fire Main Gun [green][+][/]    [b]M[/] Missile x3 [dim](ignores arc)[/]\n"
            "[b]E[/] Evade / strafe       [b]R[/] Flee     [b]K[/] Field-patch kit x2",
            id="enc-controls",
        )
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
