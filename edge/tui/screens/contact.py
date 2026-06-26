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

from collections.abc import Callable

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Static

from edge.core import dto
from edge.core.rules import AcceptLead, BarterArtifact, BuyAlienTech, Converse
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


class OfferPickerScreen(ModalScreen[int | None]):
    """Pick a tech offer to buy or barter; dismisses with its index or None."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    OfferPickerScreen { align: center middle; }
    OfferPickerScreen #offer-box {
        width: 50; height: auto; padding: 1 2; border: round $primary; background: $surface;
    }
    OfferPickerScreen #offer-box Static.title { margin-bottom: 1; }
    """

    def __init__(self, offers: list[dto.TechOfferDTO], mode: str) -> None:
        super().__init__()
        self._offers = offers
        self._mode = mode  # "latinum" or "barter"

    def compose(self) -> ComposeResult:
        title = "Buy which tech?" if self._mode == "latinum" else "Barter which item?"
        with Vertical(id="offer-box"):
            yield Static(f"[b]{title}[/]  [dim](Esc to cancel)[/]", classes="title")
            for offer in self._offers:
                cost = f"{offer.price} latinum" if self._mode == "latinum" else offer.barter_cost
                line = f"  [b]{offer.label}[/]  {cost}"
                yield ClickableEntry(line, dest="offer", ref=offer.index)

    @on(ClickableEntry.Picked)
    def on_pick(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest == "offer":
            self.dismiss(int(msg.ref))  # type: ignore[arg-type]

    def action_cancel(self) -> None:
        self.dismiss(None)


class AlienContactScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Break contact"),
        Binding("backspace", "back_one", "Back"),
        Binding("h", "verb('hail')", "Greet"),
        Binding("a", "verb('ask')", "Ask about…"),
        Binding("t", "verb('trade')", "Buy tech"),
        Binding("b", "verb('barter')", "Barter"),
        Binding("f", "verb('farewell')", "Farewell"),
        # Numbered player replies on an authored branching node (§6.7); inert on a plain node.
        *[Binding(str(n), f"choice({n})", show=False) for n in range(1, 10)],
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
    AlienContactScreen #left { width: 1fr; height: 1fr; }
    AlienContactScreen #verbs .heading { color: $secondary; text-style: bold; }
    AlienContactScreen #verbs .subhead { color: $text-muted; text-style: bold; margin-top: 1; }
    AlienContactScreen #verbs .derived { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, contact: dto.ContactDTO, service: GameService | None = None,
                 pid: int = 1, species_id: int = 0, *,
                 active_context: str = "greeting", active_subject: int | None = None,
                 pinned_speech: str | None = None,
                 history: tuple[tuple[str, int | None], ...] = (),
                 on_exit: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._contact = contact
        self._service = service
        self._pid = pid
        self._species_id = species_id
        self._active_context = active_context
        self._active_subject = active_subject
        # A one-shot frozen speech line (e.g. after logging a tip), overriding the recomputed
        # opener for this rebuild only; any later verb click reopens without it.
        self._pinned_speech = pinned_speech
        # What "break contact" does (farewell / leave / Escape). Default pops back to the game;
        # a host can override it — the dialogue play-test harness routes it to its controls modal
        # so a farewell lands somewhere useful instead of a blank screen.
        self._on_exit = on_exit
        # The (context, subject) nodes walked to reach here, oldest first — the breadcrumb for
        # Backspace backtracking out of a dead-end branch node (§6.7). View-only: stepping back
        # re-renders an earlier node without issuing any command (the Converse already fired).
        self._history = history

    def _view(self) -> dto.ContactDTO:
        if self._service is None:
            return self._contact
        return self._service.contact_view(self._pid, self._species_id,
                                          self._active_context, self._active_subject)

    def _reopen(self, pinned_speech: str | None = None) -> None:
        """Re-fetch the view and rebuild (mirrors the engine-room screen).

        `pinned_speech` freezes the speech panel to a given line for the rebuilt screen;
        callers that omit it clear any pin, so the recomputed opener shows as usual.
        """
        if self._service is None:
            return
        self.app.pop_screen()
        self.app.push_screen(AlienContactScreen(
            self._view(), self._service, self._pid, self._species_id,
            active_context=self._active_context, active_subject=self._active_subject,
            pinned_speech=pinned_speech, history=self._history, on_exit=self._on_exit))

    def _break_contact(self) -> None:
        """End the conversation: run the host's exit hook, or pop back to the game by default."""
        if self._on_exit is not None:
            self._on_exit()
        else:
            self.app.pop_screen()

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
        speech = Static(self._pinned_speech or c.opener, id="speech")
        speech.border_title = "they speak"
        yield speech
        with Horizontal(id="contact-main"):
            with Vertical(id="left"):
                with Vertical(id="verbs"):
                    heading = "Your reply" if c.choices else "Options"
                    yield Static(heading, classes="heading")
                    for n, (kind, item) in enumerate(self._menu_items(c), start=1):
                        if kind == "choice":
                            yield ClickableEntry(self._choice_line(n, item), dest="choice",
                                                 ref=item.index)
                        else:
                            yield ClickableEntry(self._numbered_verb_line(n, item), dest="verb",
                                                 ref=item.key)
                    if self._history:
                        yield ClickableEntry("  [dim]← Back (Backspace)[/]", dest="back",
                                             classes="derived")
        yield Footer()

    def _show_disabled(self) -> bool:
        return self._service.config.ui.show_disabled_options if self._service else False

    def _menu_items(self, c: dto.ContactDTO) -> list[tuple[str, object]]:
        """The unified, ordered reply menu: authored choices then the always-present floor.

        On a plain node this is the derived Say/Do verb menu; on a branching top node it is the
        authored player replies followed by the floor verbs (Ask about… / Farewell / Leave) the
        author didn't already cover (`ContactDTO.floor_verbs`, §6.7). Returning one ordered list
        keeps click dispatch (by dest/ref) and number-key dispatch (by position) in lockstep.
        """
        show_disabled = self._show_disabled()
        items: list[tuple[str, object]] = []
        if c.choices:
            chs = c.choices if show_disabled else [ch for ch in c.choices if ch.enabled]
            items += [("choice", ch) for ch in chs]
            floor = c.floor_verbs if show_disabled else [v for v in c.floor_verbs if v.enabled]
            items += [("verb", v) for v in floor]
        else:
            verbs = c.verbs if show_disabled else [v for v in c.verbs if v.enabled]
            items += [("verb", v) for v in verbs]
        # The farewell — an authored reply or the derived/floor verb — always sorts last (stable,
        # so everything else keeps its order). Dispatch is by item id, so reordering is safe.
        items.sort(key=lambda it: 1 if self._is_farewell(it) else 0)
        return items

    @staticmethod
    def _is_farewell(item: tuple[str, object]) -> bool:
        kind, obj = item
        return obj.action == "farewell" if kind == "choice" else obj.key == "farewell"  # type: ignore[attr-defined]

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Show a footer shortcut only when it is a valid option in the current menu (§11).

        Textual hides a binding whose `check_action` returns None. The lettered verb shortcuts
        (Greet / Ask / Buy tech / Barter / Farewell) appear only when that verb is actually a
        rendered, enabled row — so they vanish on a branching node that doesn't offer them — and
        Back appears only when there is somewhere to step back to. Escape and the number-key
        replies stay live.
        """
        if action == "back_one":
            return True if self._history else None
        if action == "verb":
            key = parameters[0] if parameters else None
            keys = {o.key for kind, o in self._menu_items(self._view())  # type: ignore[attr-defined]
                    if kind == "verb" and o.enabled}  # type: ignore[attr-defined]
            return True if key in keys else None
        return True

    @staticmethod
    def _verb_line(v: dto.ContactVerbDTO) -> str:
        # Literal brackets are escaped so Rich shows "[h]" rather than a markup tag.
        if v.enabled:
            return f"  [b]\\[{v.key}][/] {v.label}"
        return f"  [dim]\\[{v.key}] {v.label}  ({v.reason})[/]"

    @staticmethod
    def _choice_line(n: int, ch: dto.ContactChoiceDTO) -> str:
        # Literal brackets escaped so Rich shows "[1]" rather than a markup tag.
        if ch.enabled:
            return f"  [b]\\[{n}][/] {ch.text}"
        return f"  [dim]\\[{n}] {ch.text}  ({ch.reason})[/]"

    @staticmethod
    def _numbered_verb_line(n: int, v: dto.ContactVerbDTO) -> str:
        # Numbered verbs (unified Say + Do menu).
        if v.enabled:
            return f"  [b]\\[{n}][/] {v.label}"
        return f"  [dim]\\[{n}] {v.label}  ({v.reason})[/]"

    # --- dispatch ------------------------------------------------------------

    @on(ClickableEntry.Picked)
    def on_picked(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest == "choice":
            self._choose(int(msg.ref))  # type: ignore[arg-type]
        elif msg.dest == "verb":
            self._dispatch(str(msg.ref))
        elif msg.dest == "back":
            self.action_back_one()

    def action_verb(self, key: str) -> None:
        self._dispatch(key)

    def action_choice(self, n: int) -> None:
        """Select the n-th shown reply (key 1–9): an authored choice or a verb, in render order."""
        items = self._menu_items(self._view())
        if not 1 <= n <= len(items):
            return
        kind, item = items[n - 1]
        if kind == "choice":
            self._choose(item.index)  # type: ignore[attr-defined]
        else:
            self._dispatch(item.key)  # type: ignore[attr-defined]

    def _choose(self, index: int) -> None:
        """Apply a player reply on a branching node, then navigate per its action/transition."""
        choice = next((ch for ch in self._view().choices if ch.index == index), None)
        if choice is None:
            return
        if not choice.enabled:
            self.notify(choice.reason or "unavailable here", timeout=2)
            return
        if self._service is None:
            return
        try:
            self._service.apply(self._pid, Converse(self._species_id, self._active_context,
                                                    choice_index=index))
        except Exception as exc:  # core rejected it — surface and stay put
            self.notify(str(exc), timeout=2)
            return
        if choice.action == "farewell":
            self._break_contact()  # the parting line was spoken; break contact
            return
        if choice.action in ("trade", "barter"):
            self._pick_offer("latinum" if choice.action == "trade" else "barter")
            return
        if choice.action == "accept_lead":
            self.notify("Coordinates logged.", timeout=3)
            self._reopen()
            return
        if choice.next_context:
            self._history = (*self._history, (self._active_context, self._active_subject))
            self._active_context, self._active_subject = choice.next_context, None
        self._reopen()

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
            self._break_contact()
        elif key in ("trade", "barter"):
            self._pick_offer("latinum" if key == "trade" else "barter")
        elif key == "accept_lead":
            self._accept_lead()
        else:
            self.notify(verb.reason or "not available", timeout=2)

    def _accept_lead(self) -> None:
        """Log the coordinate tip the alien is offering (§6.7); confirm with its summary."""
        if self._service is None:
            return
        view = self._view()
        summary = view.intel_summary
        pinned = view.opener  # freeze the line the player just acted on (don't reveal the next tip)
        try:
            self._service.apply(self._pid, AcceptLead(self._species_id))
        except Exception as exc:  # core rejected it — surface the reason, stay put
            self.notify(str(exc), timeout=2)
            return
        self.notify(f"Logged: {summary}" if summary else "Coordinates logged.", timeout=3)
        self._reopen(pinned_speech=pinned)

    def _say(self, context: str, subject_id: int | None, *, close: bool) -> None:
        if self._service is None:
            return
        try:
            self._service.apply(self._pid, Converse(self._species_id, context, subject_id))
        except Exception as exc:  # core rejected it — surface and stay put
            self.notify(str(exc), timeout=2)
            return
        if close:
            self._break_contact()  # Farewell breaks contact after the parting line
            return
        self._history = (*self._history, (self._active_context, self._active_subject))
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

    def _pick_offer(self, mode: str) -> None:
        """Open a menu to pick a tech offer to buy or barter."""
        offers = [o for o in self._view().offers if o.mode == mode and o.available]
        if not offers:
            self.notify(f"nothing on offer ({mode})", timeout=2)
            return

        def picked(index: int | None) -> None:
            if index is not None:
                offer = next((o for o in self._view().offers if o.index == index), None)
                if offer is not None:
                    self._buy(offer)

        self.app.push_screen(OfferPickerScreen(offers, mode), picked)

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
        self._break_contact()

    def action_back_one(self) -> None:
        """Step back to the previous conversation node (Backspace), out of a dead end (§6.7).

        View-only: it re-renders an earlier `(context, subject)` from the breadcrumb without
        issuing a command — the navigating `Converse` already fired. With no breadcrumb (at the
        opener) it does nothing; use Escape to break contact.
        """
        if not self._history:
            return
        *rest, prev = self._history
        self._history = tuple(rest)
        self._active_context, self._active_subject = prev
        self._reopen()
