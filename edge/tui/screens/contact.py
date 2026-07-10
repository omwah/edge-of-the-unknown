"""AlienContactScreen — interactive alien dialogue + authored reply menu (UI_MOCKUPS.md §6).

Wired to `GameService.contact_view` (DESIGN §6, §6.7, WP9/WP17): the speech line is the
**active context's** persona-voiced line (the greeting by default; a reply may set another).
The reply menu is the node's **authored `choices`**, resolved via the species → persona →
generic fallback chain (the `generic` persona's `start_context` choices are the baseline), each
row clickable and numbered (1–9). A reply may speak (`Converse`), reach the buy / barter
reducers, log a coordinate tip, or break contact; a disabled reply shows *why* it is greyed.
Only `b` (Back) and `f` (Farewell) are letter shortcuts; the play-test harness adds `f5`
(Refresh) to re-roll the current line. With no service (screenshot harness) it renders a
passed sample DTO.
"""

from __future__ import annotations

from collections.abc import Callable

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core import dto
from edge.core.rules import BarterArtifact, BuyAlienTech, Converse
from edge.server.service import GameService
from edge.art import portrait as art_portrait
from edge.tui.portrait import SpeciesPortrait
from edge.tui.screens.picker import ListPicker
from edge.tui.widgets import ClickableEntry, bar


class SubjectPickerScreen(ListPicker):
    """Pick a met species to ask a contact about (WP17); dismisses with its id or None."""

    def __init__(self, subjects: list[tuple[int, str]]) -> None:
        super().__init__("Ask about which species?",
                         [(f"[b]{name}[/]", sid) for sid, name in subjects], width=44)


class OfferPickerScreen(ListPicker):
    """Pick a tech offer to buy or barter; dismisses with its index or None."""

    def __init__(self, offers: list[dto.TechOfferDTO], mode: str) -> None:
        title = "Buy which tech?" if mode == "latinum" else "Barter which item?"
        options: list[tuple[str, int | str]] = []
        for offer in offers:
            cost = f"{offer.price} latinum" if mode == "latinum" else offer.barter_cost
            options.append((f"[b]{offer.label}[/]  {cost}", offer.index))
        super().__init__(title, options)


class AlienContactScreen(Screen):
    BINDINGS = [
        Binding("b", "back_one", "Back"),       # step back to the previous node (no-op at the opener)
        Binding("f", "farewell", "Farewell"),   # speak a parting line, then break contact
        # Esc backs out of any screen (the WP73 convention): here it IS a farewell — the
        # parting line speaks and the contact session closes properly, never a raw pop.
        Binding("escape", "farewell", "Farewell", show=False),
        Binding("j", "alliance", "Join/Resign bloc"),  # derived §6.3 verb (WP72)
        # Play-test only: re-roll the current context's line in place. `check_action` hides it
        # (and disables it) outside the dialogue play-test harness.
        Binding("f5", "refresh", "Refresh"),
        # Numbered player replies (§6.7) — the whole reply menu is authored choices.
        *[Binding(str(n), f"choice({n})", show=False) for n in range(1, 10)],
    ]
    # WP-UI06: resigning a bloc resets standings — the resign branch confirms.
    ACTION_DANGER = {"alliance": "caution"}

    HELP_TITLE = "Contact"
    HELP = """\
[b]1–9[/] speak the numbered replies. [b]Esc[/]/[b]F[/] is a farewell — the parting
line speaks and the visit closes properly. Verbs are derived from the species:
trade posture, treaty, bloc membership, and mood all move what's on offer."""

    CSS = """
    AlienContactScreen #contact-title {
        dock: top; height: 1; background: $primary; color: $background;
        text-style: bold; padding: 0 1;
    }
    AlienContactScreen #contact-standing {
        height: 1; padding: 0 1; color: $text-muted; border-bottom: solid $primary;
    }
    AlienContactScreen #contact-main { height: 1fr; padding: 0 1; }
    AlienContactScreen #portrait-box {
        width: 1fr; height: 1fr; border: round $secondary; margin: 1 1; padding: 0;
    }
    AlienContactScreen #portrait-box SpeciesPortrait {
        width: 1fr; height: 1fr; content-align: center middle;
    }
    AlienContactScreen #right { width: 1fr; height: 1fr; }
    AlienContactScreen #speech {
        height: 1fr; border: round $secondary; padding: 0 1; margin: 1 1;
    }
    AlienContactScreen #verbs { height: 2fr; margin: 0 1; }
    AlienContactScreen #verbs .heading { color: $secondary; text-style: bold; }
    AlienContactScreen #verbs .subhead { color: $text-muted; text-style: bold; margin-top: 1; }
    AlienContactScreen #verbs .derived { color: $text-muted; margin-top: 1; }
    """

    def __init__(self, contact: dto.ContactDTO, service: GameService | None = None,
                 pid: int = 1, species_id: int = 0, *,
                 active_context: str = "greeting", active_subject: int | None = None,
                 pinned_speech: str | None = None,
                 history: tuple[tuple[str, int | None], ...] = (),
                 on_exit: Callable[[], None] | None = None,
                 playtest_mode: bool = False) -> None:
        super().__init__()
        self._contact = contact
        self._service = service
        self._pid = pid
        self._species_id = species_id
        self._active_context = active_context
        self._active_subject = active_subject
        # A one-shot frozen speech line (e.g. after logging a tip), overriding the recomputed
        # opener for this rebuild only; any later reply reopens without it.
        self._pinned_speech = pinned_speech
        # What "break contact" does (farewell / leave / Escape). Default pops back to the game;
        # a host can override it — the dialogue play-test harness routes it to its controls modal
        # so a farewell lands somewhere useful instead of a blank screen.
        self._on_exit = on_exit
        # The (context, subject) nodes walked to reach here, oldest first — the breadcrumb for
        # Back (b) backtracking out of a dead-end branch node (§6.7). View-only: stepping back
        # re-renders an earlier node without issuing any command (the Converse already fired).
        self._history = history
        self.playtest_mode = playtest_mode

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
            pinned_speech=pinned_speech, history=self._history, on_exit=self._on_exit,
            playtest_mode=self.playtest_mode))

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
        with Horizontal(id="contact-main"):
            with Vertical(id="portrait-box"):
                symbols, font_ratio, images_dir = self._portrait_opts()
                # variant keyed deterministically (seeded from the game seed + species
                # instance id in contact_view) so a given alien keeps one face across
                # screen rebuilds, while different individuals of the same species get
                # different portraits.
                yield SpeciesPortrait(c.roster_id, c.species, symbols, font_ratio,
                                      images_dir, c.portrait_variant, bloom=c.singular_entity)
            with Vertical(id="right"):
                speech = Static(self._pinned_speech or c.opener, id="speech")
                speech.border_title = "they speak"
                yield speech
                with Vertical(id="verbs"):
                    yield Static("Your reply", classes="heading")
                    for n, (_kind, item) in enumerate(self._menu_items(c), start=1):
                        yield ClickableEntry(self._choice_line(n, item, self.playtest_mode),
                                             dest="choice", ref=item.index)
                    if self._history:
                        yield ClickableEntry("  [dim]← Back (b)[/]", dest="back",
                                             classes="derived")
                    if c.alliance_id is not None:
                        verb = "Resign from" if c.alliance_member else "Join"
                        yield Static(f"  [dim][b]J[/] {verb} the {c.alliance} (§6.3)[/]",
                                     classes="derived")
                    if self.playtest_mode:
                        yield Static(f"\n  [dim]context = {c.debug_context} | when = {c.debug_when}[/]", classes="derived")
        yield Footer()

    def _portrait_opts(self) -> tuple[str, float, str | None]:
        """The chafa symbol selector, cell font-ratio, and image dir from config.

        Falls back to the art-module defaults (and the default image dir) for the
        screenshot harness, which has no service/config.
        """
        if self._service is not None:
            ui = self._service.config.ui
            return ui.portrait_symbols, ui.portrait_font_ratio, ui.portrait_dir
        return art_portrait.DEFAULT_SYMBOLS, art_portrait.DEFAULT_FONT_RATIO, None

    def _show_disabled(self) -> bool:
        # Prefer the app-held UI config (synced from game config at start; the WP73
        # Options screen toggles it live) over the frozen service config. An unmounted
        # screen (unit tests drive _menu_items directly) has no app — fall through.
        try:
            settings = getattr(self.app, "ui_settings", None)
            ui = getattr(self.app, "ui_config", None)
        except Exception:
            settings = None
            ui = None
        if settings is not None:
            return bool(settings.show_disabled_options)
        if ui is not None:
            return bool(ui.show_disabled_options)
        return self._service.config.ui.show_disabled_options if self._service else False

    def _menu_items(self, c: dto.ContactDTO) -> list[tuple[str, object]]:
        """The ordered reply menu — the node's authored `choices` (§6.7).

        Disabled replies are hidden unless `ui.show_disabled_options`. The farewell reply always
        sorts last (stable, so everything else keeps its order); dispatch is by canonical index,
        so reordering is safe. Returning one ordered list keeps click dispatch (by ref) and
        number-key dispatch (by position) in lockstep.
        """
        show_disabled = self._show_disabled()
        chs = c.choices if show_disabled else [ch for ch in c.choices if ch.enabled]
        items: list[tuple[str, object]] = [("choice", ch) for ch in chs]
        items.sort(key=lambda it: 1 if self._is_farewell(it) else 0)
        return items

    @staticmethod
    def _is_farewell(item: tuple[str, object]) -> bool:
        _, obj = item
        return obj.action == "leave"  # type: ignore[attr-defined]

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Show a footer shortcut only when its key would actually do something here (§11).

        Back shows only when there is somewhere to step back to; Refresh is a play-test-only
        affordance, so it shows (and dispatches) only in `playtest_mode` — on the runtime screen
        the only letter shortcuts are Back and Farewell.

        Textual's `active_bindings` drops a binding whose `check_action` is **False** but keeps a
        **None** one greyed, so we return plain bools to make an invalid shortcut vanish entirely.
        Farewell and the number-key replies stay live.
        """
        if action == "back_one":
            return bool(self._history)
        if action == "refresh":
            return self.playtest_mode
        return True

    @staticmethod
    def _choice_line(n: int, ch: dto.ContactChoiceDTO, playtest_mode: bool = False) -> str:
        # Literal brackets escaped so Rich shows "[1]" rather than a markup tag.
        text = ch.text
        if playtest_mode:
            details = []
            if ch.next_context:
                details.append(f"next={ch.next_context}")
            if ch.action:
                details.append(f"action={ch.action}")
            if details:
                text = f"{text} [dim]({', '.join(details)})[/]"
        if ch.enabled:
            return f"  [b]\\[{n}][/] {text}"
        return f"  [dim]\\[{n}] {text}  ({ch.reason})[/]"

    # --- dispatch ------------------------------------------------------------

    @on(ClickableEntry.Picked)
    def on_picked(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest == "choice":
            self._choose(int(msg.ref))  # type: ignore[arg-type]
        elif msg.dest == "back":
            self.action_back_one()

    def action_choice(self, n: int) -> None:
        """Select the n-th shown reply (key 1–9), in render order."""
        items = self._menu_items(self._view())
        if not 1 <= n <= len(items):
            return
        _kind, item = items[n - 1]
        self._choose(item.index)  # type: ignore[attr-defined]

    def _choose(self, index: int, *, confirmed: bool = False) -> None:
        """Apply a player reply, then navigate per its action/transition (§6.7)."""
        pre = self._view()
        choice = next((ch for ch in pre.choices if ch.index == index), None)
        if choice is None:
            return
        if not choice.enabled:
            self.notify(choice.reason or "unavailable here", timeout=2)
            return
        if self._service is None:
            return
        if choice.action == "attack" and not confirmed:
            # D7 (WP73): a first strike from a conversation is confirmed before it fires —
            # betrayal consequences (WP27/WP70) are not for a slipped keypress.
            from edge.tui.screens.confirm import ConfirmScreen
            self.app.push_screen(
                ConfirmScreen(f"Open fire on the {pre.species}?\n"
                              "A first strike is a betrayal they will remember."),
                lambda ok: self._choose(index, confirmed=True) if ok else None)
            return
        # Capture the intel feedback *before* the reducer consumes the tip (an accept_lead reply
        # logs the lead inside Converse, then the next view no longer offers it).
        summary, pinned = pre.intel_summary, pre.opener
        try:
            self._service.apply(self._pid, Converse(self._species_id, self._active_context,
                                                    subject_id=self._active_subject,
                                                    choice_index=index))
        except Exception as exc:  # core rejected it — surface and stay put
            self.notify(str(exc), timeout=2)
            return
        if choice.action == "leave":
            self._break_contact()  # the parting line was spoken; break contact
            return
        if choice.action == "attack":
            # The first strike opened combat (WP70): contact is over, the encounter is
            # live — popping back lets the game screen's resume hook raise the fight.
            self.notify("You open fire — betrayal remembered.", severity="warning", timeout=3)
            self._break_contact()
            return
        if choice.action == "trade":
            self._trade_or_refuse()
            return
        if choice.action == "barter":
            self._pick_offer("barter")
            return
        if choice.action == "accept_lead":  # the Converse above already logged the tip
            self.notify(f"Logged: {summary}" if summary else "Coordinates logged.", timeout=3)
            self._reopen(pinned_speech=pinned)
            return
        if choice.next_context:
            if choice.next_context == "back":
                if self._history:
                    *rest, prev = self._history
                    self._history = tuple(rest)
                    self._active_context, self._active_subject = prev
                else:
                    self._active_context, self._active_subject = "greeting", None
                self._reopen()
            elif choice.next_context == "dossier_other":
                self._ask_about("dossier_other")
            else:
                self._history = (*self._history, (self._active_context, self._active_subject))
                self._active_context, self._active_subject = choice.next_context, None
                self._reopen()

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

    def _trade_or_refuse(self) -> None:
        """Open the buy menu if there's stock, else speak the persona's `trade_refuse` beat (§6.7).

        Keeps Trade a live, voiced action even when the shelf is empty (or the species refuses):
        no offers ⇒ navigate to the `trade_refuse` context so the alien says so, rather than a
        terse toast or a dead button.
        """
        if any(o.mode == "latinum" and o.available for o in self._view().offers):
            self._pick_offer("latinum")
        else:
            self._say("trade_refuse", None, close=False)

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

    def action_alliance(self) -> None:
        """Join the speaker's bloc — or resign it (§6.3, WP38 — the derived WP72 verb).

        Joining is gated reducer-side (admission price, fee, exclusivity) and its rival
        fallout can flip the Core hostile; resigning is the amends path.
        """
        if self._service is None:
            return
        c = self._view()
        if c.alliance_id is None:
            self.notify("They answer to no bloc.", timeout=2)
            return
        from edge.core.rules import JoinAlliance, ResignAlliance
        command = ResignAlliance() if c.alliance_member else JoinAlliance(c.alliance_id)

        def _go(ok: bool | None = True) -> None:
            if not ok:
                return
            try:
                self._service.apply(self._pid, command)
            except Exception as exc:  # core rejected it — surface the reason, stay put
                self.notify(str(exc), timeout=3)
                return
            done = ("You stand apart again." if c.alliance_member
                    else f"Sworn to the {c.alliance}.")
            self.notify(done, timeout=3)
            self._reopen()

        if c.alliance_member:  # D7 (WP73): resigning resets standings — confirm it
            from edge.tui.screens.confirm import ConfirmScreen
            self.app.push_screen(ConfirmScreen(
                f"Resign from the {c.alliance}?\nYour standing with them resets."), _go)
        else:
            _go()

    def action_farewell(self) -> None:
        """Farewell (f / Esc): speak a parting line, then break contact — the single exit."""
        if self._service is None:  # screenshot harness — no session to close, just leave
            self._break_contact()
            return
        self._say("farewell", None, close=True)

    def action_refresh(self) -> None:
        """Play-test only: re-roll the current context's line in place (advance its recency ring).

        Re-speaks the active context via `Converse` (no choice), which advances the
        `(species, context)` recency ring so the next render picks a different variant. Gated to
        `playtest_mode` by `check_action`; branch nodes (not directly sayable) simply no-op.
        """
        if not self.playtest_mode or self._service is None:
            return
        try:
            self._service.apply(self._pid, Converse(self._species_id, self._active_context,
                                                    subject_id=self._active_subject))
        except Exception:  # a non-sayable node (e.g. a branch.*) — nothing to re-roll
            return
        self._reopen()

    def action_back_one(self) -> None:
        """Step back to the previous conversation node (b), out of a dead end (§6.7).

        View-only: it re-renders an earlier `(context, subject)` from the breadcrumb without
        issuing a command — the navigating `Converse` already fired. With no breadcrumb (at the
        opener) it does nothing; use Farewell (f) to break contact.
        """
        if not self._history:
            return
        *rest, prev = self._history
        self._history = tuple(rest)
        self._active_context, self._active_subject = prev
        self._reopen()
