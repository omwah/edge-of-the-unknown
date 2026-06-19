"""AlienContactScreen — peaceful alien dialogue + derived verb menu (UI_MOCKUPS.md §6).

Wired to `GameService.contact_view` (DESIGN §6, §6.7, WP9): the opener line comes from
the species' persona-voiced `dialogue_pack` keyed to standing; the verb menu is
**derived** from species params, so a disabled verb shows *why* it is greyed; the
tech-offer list shows latinum vs barter side by side, gated by effective disposition;
the dossier panel narrates what this contact has told the player about others. Clicking
an available offer buys it (latinum) or barters an artifact for it; `H` re-greets. With
no service (screenshot harness) it renders a passed sample DTO.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Static

from edge.core import dto
from edge.core.rules import BarterArtifact, BuyAlienTech, Hail
from edge.server.service import GameService
from edge.tui.widgets import ClickableEntry, bar


class AlienContactScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Break contact"),
        Binding("6", "back", "Leave"),
        Binding("h", "rehail", "Hail again"),
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
    AlienContactScreen #offers { height: auto; border: round $primary; padding: 0 1; margin-top: 1; }
    AlienContactScreen #verbs .derived { color: $text-muted; margin-top: 1; }
    AlienContactScreen #dossier {
        width: 1fr; height: auto; border: round $primary; padding: 0 1; margin-left: 2;
    }
    """

    def __init__(self, contact: dto.ContactDTO, service: GameService | None = None,
                 pid: int = 1, species_id: int = 0) -> None:
        super().__init__()
        self._contact = contact
        self._service = service
        self._pid = pid
        self._species_id = species_id

    def _view(self) -> dto.ContactDTO:
        if self._service is None:
            return self._contact
        return self._service.contact_view(self._pid, self._species_id)

    def _reopen(self) -> None:
        """Re-fetch the view and rebuild after a trade (mirrors the engine-room screen)."""
        if self._service is None:
            return
        self.app.pop_screen()
        self.app.push_screen(AlienContactScreen(
            self._service.contact_view(self._pid, self._species_id),
            self._service, self._pid, self._species_id))

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
                    for v in c.verbs:
                        yield Static(self._verb_line(v))
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

    @on(ClickableEntry.Picked)
    def on_offer_picked(self, msg: ClickableEntry.Picked) -> None:
        if msg.dest != "offer" or self._service is None:
            return
        offer = next((o for o in self._view().offers if o.index == int(msg.ref)), None)
        if offer is None:
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

    def action_rehail(self) -> None:
        if self._service is None:
            return
        self._service.apply(self._pid, Hail(self._species_id))
        self._reopen()

    def action_back(self) -> None:
        self.app.pop_screen()
