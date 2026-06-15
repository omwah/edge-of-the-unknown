"""AlienContactScreen — peaceful alien dialogue + derived verb menu (UI_MOCKUPS.md §6).

Phase-2 screen, stubbed here so hailing a friendly-band ship has somewhere to go.
The opener line comes from the species' `dialogue_pack` (persona-voiced, keyed to
standing/treaty/grudge); the verb menu is **derived** from species params (DESIGN
§6.1–6.7) rather than authored, so a disabled verb shows *why* it is greyed. The
dossier panel narrates what this contact has told the player about other species.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.tui.dummy import AlienContactDTO, ContactVerb
from edge.tui.widgets import bar


class AlienContactScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Break contact"),
        Binding("6", "back", "Leave"),
        Binding("1", "noop", "Tech"),
        Binding("2", "noop", "Barter"),
        Binding("3", "noop", "Region"),
        Binding("5", "noop", "Trade"),
    ]

    CSS = """
    AlienContactScreen #contact-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    AlienContactScreen #contact-standing {
        height: 1; padding: 0 1; color: $text-muted; border-bottom: solid $primary;
    }
    AlienContactScreen #speech {
        height: auto; border: round $secondary; padding: 0 1; margin: 1 2;
    }
    AlienContactScreen #contact-main { height: 1fr; padding: 0 2; }
    AlienContactScreen #verbs { width: 2fr; height: 1fr; }
    AlienContactScreen #verbs .heading { color: $secondary; text-style: bold; }
    AlienContactScreen #verbs .derived { color: $text-muted; margin-top: 1; }
    AlienContactScreen #dossier {
        width: 1fr; height: auto; border: round $primary; padding: 0 1; margin-left: 2;
    }
    AlienContactScreen #prompt { height: 1; padding: 0 2; color: $secondary; }
    """

    def __init__(self, contact: AlienContactDTO) -> None:
        super().__init__()
        self._contact = contact

    def compose(self) -> ComposeResult:
        c = self._contact
        disp = bar(c.disposition_filled, 5)
        yield Static(
            f"CONTACT · {c.species}        "
            f"[dim]disposition[/] [green]{disp}[/] {c.band}",
            id="contact-title",
        )
        yield Static(
            f"standing: [green]{c.standing}[/]        alliance: [cyan]{c.alliance}[/]",
            id="contact-standing",
        )
        speech = Static("\n".join(c.speech), id="speech")
        speech.border_title = "they speak"
        yield speech
        with Horizontal(id="contact-main"):
            with Vertical(id="verbs"):
                yield Static("Say / Do", classes="heading")
                for v in c.verbs:
                    yield Static(self._verb_line(v))
                yield Static("[dim](menu derived from params)[/]", classes="derived")
            dossier = Static("\n".join(c.dossier), id="dossier")
            dossier.border_title = "Dossier (told to you)"
            yield dossier
        yield Static("> _", id="prompt")
        yield Footer()

    @staticmethod
    def _verb_line(v: ContactVerb) -> str:
        # Literal brackets are escaped so Rich shows "[1]" rather than a tag.
        if v.enabled:
            return f"  [b]\\[{v.key}][/] {v.label}"
        return f"  [dim]\\[{v.key}] {v.label}  ({v.reason})[/]"

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_noop(self) -> None:
        self.notify("Not wired in the skeleton.", timeout=2)
