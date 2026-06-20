"""AlienContactScreen — interactive alien dialogue + derived verb menu (UI_MOCKUPS.md §6).

Wired to `GameService.contact_view` (DESIGN §6, §6.7, WP9/WP17): the speech line is the
**active context's** persona-voiced line (the greeting by default; a *Say* verb sets
another); the verb menu is **derived** from species params and split into **Say**
(dialogue) and **Do** (mechanical) groups, each row clickable + key-bound. *Say* verbs
issue `Converse` (greeting / ask-about / farewell); *Do* verbs reach the existing buy /
barter reducers or break contact. A disabled verb shows *why* it is greyed. With no
service (screenshot harness) it renders a passed sample DTO.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Static

from edge.core import dto
from edge.core.rules import BarterArtifact, BuyAlienTech, Converse
from edge.server.service import GameService
from edge.tui.widgets import ClickableEntry, bar


class SubjectPickerScreen(ModalScreen[int | None]):
    """Pick a met species to ask a contact about (WP17); dismisses with its id or None."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    SubjectPickerScreen { align: center middle; }
    SubjectPickerScreen #subject-box {
        width: 44; height: auto; padding: 1 2; border: round $primary; background: $surface;
    }
    SubjectPickerScreen #subject-box Static.title { margin-bottom: 1; }
    """

    def __init__(self, subjects: list[tuple[int, str]]) -> None:
        super().__init__()
        self._subjects = subjects

    def compose(self) -> ComposeResult:
        with Vertical(id="subject-box"):
            yield Static("[b]Ask about which species?[/]  [dim](Esc to cancel)[/]", classes="title")
            for sid, name in self._subjects:
                yield ClickableEntry(f"  [b]{name}[/]", dest="subject", ref=sid)

    @on(ClickableEntry.Picked)
    def on_pick(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest == "subject":
            self.dismiss(int(msg.ref))  # type: ignore[arg-type]

    def action_cancel(self) -> None:
        self.dismiss(None)


class AlienContactScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Break contact"),
        Binding("6", "back", "Leave"),
        Binding("h", "verb('hail')", "Greet"),
        Binding("a", "verb('ask')", "Ask about…"),
        Binding("t", "verb('trade')", "Buy tech"),
        Binding("b", "verb('barter')", "Barter"),
        Binding("f", "verb('farewell')", "Farewell"),
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
    AlienContactScreen #left { width: 2fr; height: 1fr; }
    AlienContactScreen #verbs .heading { color: $secondary; text-style: bold; }
    AlienContactScreen #verbs .subhead { color: $text-muted; text-style: bold; margin-top: 1; }
    AlienContactScreen #offers { height: auto; border: round $primary; padding: 0 1; margin-top: 1; }
    AlienContactScreen #verbs .derived { color: $text-muted; margin-top: 1; }
    AlienContactScreen #dossier {
        width: 1fr; height: auto; border: round $primary; padding: 0 1; margin-left: 2;
    }
    """

    def __init__(self, contact: dto.ContactDTO, service: GameService | None = None,
                 pid: int = 1, species_id: int = 0, *,
                 active_context: str = "greeting", active_subject: int | None = None) -> None:
        super().__init__()
        self._contact = contact
        self._service = service
        self._pid = pid
        self._species_id = species_id
        self._active_context = active_context
        self._active_subject = active_subject

    def _view(self) -> dto.ContactDTO:
        if self._service is None:
            return self._contact
        return self._service.contact_view(self._pid, self._species_id,
                                          self._active_context, self._active_subject)

    def _reopen(self) -> None:
        """Re-fetch the view and rebuild (mirrors the engine-room screen)."""
        if self._service is None:
            return
        self.app.pop_screen()
        self.app.push_screen(AlienContactScreen(
            self._view(), self._service, self._pid, self._species_id,
            active_context=self._active_context, active_subject=self._active_subject))

    def compose(self) -> ComposeResult:
        c = self._view()
        yield Static(
            f"CONTACT · {c.species}        "
            f"[dim]disposition[/] [green]{bar(c.disposition_filled, 5)}[/] {c.band}",
            id="contact-title",
        )
        yield Static(
            f"standing: [green]{c.standing}[/]  "
            f"[dim](base {c.base_disposition:.2f} {c.attitude:+.2f} you = {c.effective:.2f})[/]"
            f"        alliance: [cyan]{c.alliance}[/]",
            id="contact-standing",
        )
        speech = Static(c.opener, id="speech")
        speech.border_title = "they speak"
        yield speech
        with Horizontal(id="contact-main"):
            with Vertical(id="left"):
                with Vertical(id="verbs"):
                    yield Static("Say / Do", classes="heading")
                    yield Static("Say", classes="subhead")
                    for v in c.verbs:
                        if v.kind == "say":
                            yield ClickableEntry(self._verb_line(v), dest="verb", ref=v.key)
                    yield Static("Do", classes="subhead")
                    for v in c.verbs:
                        if v.kind != "say":
                            yield ClickableEntry(self._verb_line(v), dest="verb", ref=v.key)
                    yield Static("[dim](menu derived from params)[/]", classes="derived")
                offers = Vertical(id="offers")
                offers.border_title = "Tech offers — click to buy / barter"
                with offers:
                    if not c.offers:
                        yield Static("[dim]nothing on offer[/]")
                    for o in c.offers:
                        yield ClickableEntry(self._offer_line(o), dest="offer", ref=o.index,
                                             classes="offer")
            dossier = Static("\n".join(c.dossier) or "[dim]nothing told to you yet[/]", id="dossier")
            dossier.border_title = "Dossier (told to you)"
            yield dossier
        yield Footer()

    @staticmethod
    def _verb_line(v: dto.ContactVerbDTO) -> str:
        # Literal brackets are escaped so Rich shows "[h]" rather than a markup tag.
        if v.enabled:
            return f"  [b]\\[{v.key}][/] {v.label}"
        return f"  [dim]\\[{v.key}] {v.label}  ({v.reason})[/]"

    @staticmethod
    def _offer_line(o: dto.TechOfferDTO) -> str:
        cost = f"{o.price} latinum" if o.mode == "latinum" else o.barter_cost
        if o.available:
            return f"  [b]{o.label}[/]  [green]{cost}[/]"
        return f"  [dim]{o.label}  {cost}  ({o.reason})[/]"

    # --- dispatch ------------------------------------------------------------

    @on(ClickableEntry.Picked)
    def on_picked(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest == "offer":
            self._buy_by_index(int(msg.ref))  # type: ignore[arg-type]
        elif msg.dest == "verb":
            self._dispatch(str(msg.ref))

    def action_verb(self, key: str) -> None:
        self._dispatch(key)

    def _dispatch(self, key: str) -> None:
        verb = next((v for v in self._view().verbs if v.key == key), None)
        if verb is None:
            return
        if not verb.enabled:
            self.notify(verb.reason or "unavailable here", timeout=2)
            return
        if verb.kind == "say":
            if verb.needs_subject:
                self._ask_about(verb.context)
            else:
                self._say(verb.context, None, close=(key == "farewell"))
        elif key == "leave":
            self.app.pop_screen()
        elif key in ("trade", "barter"):
            self._act_offer("latinum" if key == "trade" else "barter")
        else:
            self.notify(verb.reason or "not available", timeout=2)

    def _say(self, context: str, subject_id: int | None, *, close: bool) -> None:
        if self._service is None:
            return
        try:
            self._service.apply(self._pid, Converse(self._species_id, context, subject_id))
        except Exception as exc:  # core rejected it — surface and stay put
            self.notify(str(exc), timeout=2)
            return
        if close:
            self.app.pop_screen()  # Farewell breaks contact after the parting line
            return
        self._active_context, self._active_subject = context, subject_id
        self._reopen()

    def _ask_about(self, context: str) -> None:
        subjects = self._view().subjects
        if not subjects:
            self.notify("no other species met yet", timeout=2)
            return

        def picked(subject_id: int | None) -> None:
            if subject_id is not None:
                self._say(context, subject_id, close=False)

        self.app.push_screen(SubjectPickerScreen(subjects), picked)

    def _act_offer(self, mode: str) -> None:
        offers = [o for o in self._view().offers if o.mode == mode]
        available = [o for o in offers if o.available]
        if len(available) == 1:
            self._buy(available[0])  # act on the lone offer of that mode
        elif offers:
            self.notify("pick an offer in the Tech offers panel", timeout=2)
        else:
            self.notify(f"nothing on offer ({mode})", timeout=2)

    def _buy_by_index(self, index: int) -> None:
        offer = next((o for o in self._view().offers if o.index == index), None)
        if offer is not None:
            self._buy(offer)

    def _buy(self, offer: dto.TechOfferDTO) -> None:
        if self._service is None:
            return
        if not offer.available:
            self.notify(offer.reason or "that offer is unavailable", timeout=2)
            return
        command = (BuyAlienTech(self._species_id, offer.index) if offer.mode == "latinum"
                   else BarterArtifact(self._species_id, offer.index))
        try:
            self._service.apply(self._pid, command)
        except Exception as exc:  # core rejected it — surface the reason, stay put
            self.notify(str(exc), timeout=2)
            return
        self._reopen()

    def action_back(self) -> None:
        self.app.pop_screen()
