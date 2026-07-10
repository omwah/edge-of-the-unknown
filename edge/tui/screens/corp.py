"""CorpScreen — the `T` screen: corporations (DESIGN §4, WP66; completed WP76).

The corp roster (CEO marked), the shared bank, holdings, and active corp wars, with the
full command set surfaced: form / deposit / withdraw / leave (WP66) plus invite, accept,
expel-highlighted, declare/end war, and planet transfer to/from the corp (WP76). Actions
are the ordinary corp commands issued through the service, so single-player it manages a
corp of one and the same screen serves multiplayer.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Input, Static

from edge.core.economy import EconomyError
from edge.core.rules import (
    AcceptCorpInvite, CorpDeposit, CorpWithdraw, DeclareCorpWar, EndCorpWar,
    ExpelFromCorp, FormCorp, InviteToCorp, LeaveCorp, TransferPlanetFromCorp,
    TransferPlanetToCorp,
)
from edge.server.service import GameService


class _FormCorpModal(ModalScreen[tuple[str, str] | None]):
    """Prompt a name + tag to charter a corporation."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    _FormCorpModal { align: center middle; background: $background 60%; }
    _FormCorpModal Input, _FormCorpModal Button { width: 40; }
    """

    def compose(self) -> ComposeResult:
        yield Static("Charter a corporation", id="corp-modal-title")
        yield Input(placeholder="Name", id="corp-name")
        yield Input(placeholder="TAG", id="corp-tag")
        yield Button("Charter", id="corp-ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        name = self.query_one("#corp-name", Input).value.strip()
        tag = self.query_one("#corp-tag", Input).value.strip()
        self.dismiss((name, tag) if name and tag else None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class CorpScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("f", "form", "Form corp"),
        Binding("d", "deposit", "Deposit 1k"),
        Binding("w", "withdraw", "Withdraw 1k"),
        Binding("l", "leave", "Leave corp"),
        Binding("i", "invite", "Invite"),
        Binding("a", "accept_invite", "Accept invite"),
        Binding("x", "expel", "Expel highlighted"),
        Binding("g", "declare_war", "Declare war"),
        Binding("e", "end_war", "End war"),
        Binding("p", "planet_to_corp", "World → corp"),
        Binding("o", "planet_from_corp", "World → CEO"),
    ]

    HELP_TITLE = "Corporation"

    CSS = """
    CorpScreen #corp-title {
        dock: top; height: 1; background: $accent; color: $background;
        text-style: bold; padding: 0 1;
    }
    CorpScreen DataTable { height: auto; max-height: 14; margin: 1 2; }
    CorpScreen Static.note { padding: 0 2; }
    """

    def __init__(self, service: GameService, player_id: int) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id

    def compose(self) -> ComposeResult:
        view = self._service.corp_view(self._pid)
        if view is None or not view.corp_id:
            yield Static("You have no corporation.", id="corp-title")
            invites = view.invites if view is not None else []
            if invites:
                yield Static("Standing invites: " + ", ".join(invites), classes="note")
                yield Static("[dim][b]A[/] accepts the first standing invite.[/]", classes="note")
            yield Static("[f] to charter one.", classes="note")
            yield Footer()
            return
        role = "CEO" if view.is_ceo else "member"
        yield Static(f"⟨{view.tag}⟩ {view.name} — you are {role}", id="corp-title")
        yield Static(
            f"Bank {view.bank_balance:,} slips · {view.planet_count} worlds · "
            f"{view.starbase_count} bases"
            + (f" · at war with {', '.join(view.at_war_with)}" if view.at_war_with else ""),
            classes="note")
        table: DataTable = DataTable(id="corp-members", zebra_stripes=True, cursor_type="row")
        table.add_columns("Player", "Role")
        for m in view.members:
            table.add_row(m.name, "CEO" if m.is_ceo else "member", key=str(m.player_id))
        yield table
        if view.other_corps:
            others = "   ".join(f"#{cid} {label}" for cid, label in view.other_corps)
            yield Static(f"Other corporations: {others}", classes="note")
        yield Static(
            "[dim][b]I[/] invite a captain (by id)   [b]X[/] expel highlighted   "
            "[b]G[/]/[b]E[/] declare/end war (by corp #)   "
            "[b]P[/]/[b]O[/] give/take this sector's world[/]",
            classes="note")
        yield Footer()

    # --- actions -------------------------------------------------------------

    def _refresh(self) -> None:
        self.app.pop_screen()
        self.app.push_screen(CorpScreen(self._service, self._pid))

    def _apply(self, command: object, ok: str | None = None) -> None:
        try:
            self._service.apply(self._pid, command)  # type: ignore[arg-type]
        except EconomyError as exc:
            self.app.bell()
            self.notify(str(exc), severity="warning")
            return
        if ok:
            self.notify(ok, timeout=2)
        self._refresh()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_form(self) -> None:
        view = self._service.corp_view(self._pid)
        if view is not None and view.corp_id:
            self.notify("You already belong to a corporation.", severity="warning")
            return

        def _done(result: tuple[str, str] | None) -> None:
            if result is not None:
                self._apply(FormCorp(name=result[0], tag=result[1]))

        self.app.push_screen(_FormCorpModal(), _done)

    def action_deposit(self) -> None:
        self._apply(CorpDeposit(amount=1_000))

    def action_withdraw(self) -> None:
        self._apply(CorpWithdraw(amount=1_000))

    def action_leave(self) -> None:
        self._apply(LeaveCorp())

    # --- WP76: invite / accept / expel / war / asset transfer -----------------

    def _prompt_number(self, prompt: str, then: object) -> None:
        from edge.tui.screens.stardock import _AmountInput
        self.app.push_screen(_AmountInput(prompt), then)  # type: ignore[arg-type]

    def action_invite(self) -> None:
        """CEO invites a captain by player id (the two-step consent join, WP66/WP76)."""
        def _go(pid: int | None) -> None:
            if pid:
                self._apply(InviteToCorp(invitee_player_id=pid), f"Invited captain #{pid}")
        self._prompt_number("Invite which captain (player id)?", _go)

    def action_accept_invite(self) -> None:
        """Accept the first standing invite (corpless only)."""
        view = self._service.corp_view(self._pid)
        if view is None or view.corp_id or not view.invite_ids:
            self.notify("No standing invite to accept.", timeout=2)
            return
        self._apply(AcceptCorpInvite(corp_id=view.invite_ids[0]),
                    f"Joined {view.invites[0]}")

    def action_expel(self) -> None:
        """CEO expels the highlighted member."""
        tables = list(self.query(DataTable))
        if not tables or not tables[0].row_count:
            return
        table = tables[0]
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        if key.value is None:
            return
        member_id = int(key.value)
        if member_id == self._pid:
            self.notify("You cannot expel yourself — leave (or dissolve) instead.", timeout=3)
            return
        self._apply(ExpelFromCorp(member_player_id=member_id), f"Expelled captain #{member_id}")

    def action_declare_war(self) -> None:
        """CEO declares war on a rival corp by its # (mutual by declaration, WP66)."""
        def _go(cid: int | None) -> None:
            if cid:
                self._apply(DeclareCorpWar(target_corp_id=cid), "War declared.")
        self._prompt_number("Declare war on which corp (#)?", _go)

    def action_end_war(self) -> None:
        """CEO withdraws from a war by corp # (re-declaration cooldown applies)."""
        def _go(cid: int | None) -> None:
            if cid:
                self._apply(EndCorpWar(target_corp_id=cid), "War ended.")
        self._prompt_number("End the war with which corp (#)?", _go)

    def _sector_planet_id(self) -> int | None:
        planet = self._service.current_planet_view(self._pid)
        if planet is None:
            self.notify("No planet in this sector.", timeout=2)
            return None
        return planet.planet_id

    def action_planet_to_corp(self) -> None:
        """Hand this sector's world (yours) to the corp as a shared holding."""
        pid = self._sector_planet_id()
        if pid is not None:
            self._apply(TransferPlanetToCorp(planet_id=pid), "World transferred to the corp.")

    def action_planet_from_corp(self) -> None:
        """Return this sector's corp-owned world to the CEO (CEO-gated)."""
        pid = self._sector_planet_id()
        if pid is not None:
            self._apply(TransferPlanetFromCorp(planet_id=pid), "World returned to the CEO.")
