"""CorpScreen — the `T` screen: corporations (DESIGN §4, WP66).

A read-first roster of the player's corporation: members (CEO marked), the shared bank,
holdings, and active corp wars. Actions are the ordinary corp commands (form / deposit /
withdraw / leave) issued through the service, so single-player it manages a corp of one and the
same screen serves multiplayer. Deliberately light — the interesting rules live in the reducers.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Input, Static

from edge.core.economy import EconomyError
from edge.core.rules import CorpDeposit, CorpWithdraw, FormCorp, LeaveCorp
from edge.server.service import GameService


class _FormCorpModal(ModalScreen[tuple[str, str] | None]):
    """Prompt a name + tag to charter a corporation."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

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
        Binding("y", "withdraw", "Withdraw 1k"),
        Binding("l", "leave", "Leave corp"),
    ]

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
        table: DataTable = DataTable(zebra_stripes=True)
        table.add_columns("Player", "Role")
        for m in view.members:
            table.add_row(m.name, "CEO" if m.is_ceo else "member")
        yield table
        yield Footer()

    # --- actions -------------------------------------------------------------

    def _refresh(self) -> None:
        self.app.pop_screen()
        self.app.push_screen(CorpScreen(self._service, self._pid))

    def _apply(self, command: object) -> None:
        try:
            self._service.apply(self._pid, command)  # type: ignore[arg-type]
        except EconomyError as exc:
            self.app.bell()
            self.notify(str(exc), severity="warning")
            return
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
