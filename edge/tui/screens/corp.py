"""CorpScreen — the `T` screen: corporations (DESIGN §4, WP66; completed WP76).

Panel-first, mouse-first: three bordered panels (roster · treasury & holdings ·
diplomacy) built on DataTables and Buttons, so every corp verb is a click on a
button acting on the highlighted table row — the hotkeys remain as accelerators
only. Chartering asks for a *name* only: the short uppercase tag is an internal
identifier, derived from the name (initials, uniquified on collision). War is
declared and ended against the corp selected in the diplomacy table — never by
typing an index. Actions are the ordinary corp commands issued through the
service, so single-player it manages a corp of one and the same screen serves
multiplayer.
"""

from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Input, Static

from edge.core.economy import EconomyError
from edge.core.rules import (
    AcceptCorpInvite, CorpDeposit, CorpWithdraw, DeclareCorpWar, EndCorpWar,
    ExpelFromCorp, FormCorp, InviteToCorp, LeaveCorp, TransferPlanetFromCorp,
    TransferPlanetToCorp,
)
from edge.server.service import GameService


def _derive_tag(name: str, max_len: int) -> str:
    """A short uppercase tag from the corp name — internal id, never typed (WP80+).

    Multi-word names take their initials; a single word takes its first letters.
    Alphanumeric only, capped to the config length; `_form` uniquifies on collision.
    """
    words = [w for w in re.split(r"[^0-9A-Za-z]+", name) if w]
    if not words:
        return "CORP"[: max(1, max_len)]
    if len(words) == 1:
        tag = words[0][: max(1, min(3, max_len))]
    else:
        tag = "".join(w[0] for w in words)[: max(1, max_len)]
    return tag.upper()


class _FormCorpModal(ModalScreen[str | None]):
    """Prompt a corporation *name* — the tag is derived, not typed."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    _FormCorpModal { align: center middle; background: $background 60%; }
    _FormCorpModal #corp-form-box {
        width: 50; height: auto; padding: 1 2; border: round $primary; background: $surface;
    }
    _FormCorpModal Input { margin-top: 1; }
    _FormCorpModal Button { margin-top: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="corp-form-box"):
            yield Static("[b]Charter a corporation[/]  [dim](Esc to cancel)[/]")
            yield Input(placeholder="Corporation name", id="corp-name")
            yield Button("Charter", id="corp-ok", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#corp-name", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._submit()

    def _submit(self) -> None:
        name = self.query_one("#corp-name", Input).value.strip()
        self.dismiss(name or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class CorpScreen(Screen):
    # Hotkeys are accelerators only — every verb is also a Button on its panel.
    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("f", "form", "Form corp"),
        Binding("d", "deposit", "Deposit 1k"),
        Binding("w", "withdraw", "Withdraw 1k"),
        Binding("l", "leave", "Leave corp"),
        Binding("i", "invite", "Invite"),
        Binding("a", "accept_invite", "Accept invite"),
        Binding("x", "expel", "Expel selected"),
        Binding("g", "declare_war", "Declare war"),
        Binding("e", "end_war", "End war"),
        Binding("p", "planet_to_corp", "World → corp"),
        Binding("o", "planet_from_corp", "World → CEO"),
    ]

    HELP_TITLE = "Corporation"
    HELP = """\
Everything is clickable: buttons act on the [b]highlighted table row[/] of their
panel (expel a roster member, declare/end war on a diplomacy row). Chartering
asks only for a name — the ⟨TAG⟩ is derived internally. The keys listed above
are accelerators for the same buttons."""

    CSS = """
    CorpScreen #corp-title {
        dock: top; height: 1; background: $accent; color: $background;
        text-style: bold; padding: 0 1;
    }
    CorpScreen #corp-panels { height: 1fr; padding: 1 1 0 1; }
    CorpScreen .corp-panel {
        width: 1fr; height: auto; max-height: 100%; border: round $primary;
        padding: 0 1; margin: 0 1 0 0;
    }
    CorpScreen .corp-panel DataTable { height: auto; max-height: 12; margin-bottom: 1; }
    CorpScreen .corp-panel Button { margin: 0 1 1 0; min-width: 14; }
    CorpScreen .corp-panel .buttons { height: auto; }
    CorpScreen .corp-panel Static.stat { margin-bottom: 1; }
    CorpScreen .note { padding: 0 2; }
    CorpScreen #corp-empty-box { padding: 1 2; height: auto; }
    CorpScreen #corp-empty-box Button { margin: 1 1 0 0; min-width: 18; }
    """

    def __init__(self, service: GameService, player_id: int) -> None:
        super().__init__()
        self._service = service
        self._pid = player_id

    # --- layout ----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        view = self._service.corp_view(self._pid)
        if view is None or not view.corp_id:
            yield Static("You have no corporation.", id="corp-title")
            with Vertical(id="corp-empty-box"):
                invites = view.invites if view is not None else []
                if invites:
                    table: DataTable = DataTable(id="corp-invites", cursor_type="row")
                    table.add_columns("Standing invites")
                    for cid, label in zip(view.invite_ids, invites):  # type: ignore[union-attr]
                        table.add_row(label, key=str(cid))
                    yield table
                with Horizontal(classes="buttons"):
                    yield Button("Charter a corporation…", id="btn-form", variant="primary")
                    if invites:
                        yield Button("Accept selected invite", id="btn-accept", variant="success")
            yield Footer()
            return
        role = "CEO" if view.is_ceo else "member"
        yield Static(f"⟨{view.tag}⟩ {view.name} — you are {role}", id="corp-title")
        with Horizontal(id="corp-panels"):
            yield self._roster_panel(view)
            yield self._holdings_panel(view)
            yield self._diplomacy_panel(view)
        yield Footer()

    def _roster_panel(self, view: object) -> Vertical:
        table: DataTable = DataTable(id="corp-members", zebra_stripes=True, cursor_type="row")
        table.add_columns("Member", "Role")
        for m in view.members:  # type: ignore[attr-defined]
            table.add_row(m.name, "CEO" if m.is_ceo else "member", key=str(m.player_id))
        panel = Vertical(
            table,
            Horizontal(
                Button("Invite…", id="btn-invite"),
                Button("Expel selected", id="btn-expel", variant="warning"),
                classes="buttons"),
            Horizontal(Button("Leave corp", id="btn-leave", variant="error"),
                       classes="buttons"),
            classes="corp-panel")
        panel.border_title = "Roster"
        return panel

    def _holdings_panel(self, view: object) -> Vertical:
        panel = Vertical(
            Static(f"Bank      [b yellow]{view.bank_balance:,}[/] slips", classes="stat"),  # type: ignore[attr-defined]
            Static(f"Worlds    [b]{view.planet_count}[/]", classes="stat"),  # type: ignore[attr-defined]
            Static(f"Bases     [b]{view.starbase_count}[/]", classes="stat"),  # type: ignore[attr-defined]
            Horizontal(
                Button("Deposit 1k", id="btn-deposit"),
                Button("Withdraw 1k", id="btn-withdraw"),
                classes="buttons"),
            Horizontal(
                Button("World → corp", id="btn-world-to"),
                Button("World → CEO", id="btn-world-from"),
                classes="buttons"),
            Static("[dim]World transfers act on the planet in your current sector.[/]"),
            classes="corp-panel")
        panel.border_title = "Treasury & holdings"
        return panel

    def _diplomacy_panel(self, view: object) -> Vertical:
        table: DataTable = DataTable(id="corp-others", zebra_stripes=True, cursor_type="row")
        table.add_columns("Corporation", "Status")
        at_war = set(view.at_war_with)  # type: ignore[attr-defined]
        for cid, label in view.other_corps:  # type: ignore[attr-defined]
            tag = label.split(" — ", 1)[0]
            status = "[red]at war[/]" if tag in at_war else "[dim]—[/]"
            table.add_row(label, status, key=str(cid))
        children: list[object] = [table]
        if not view.other_corps:  # type: ignore[attr-defined]
            children = [Static("[dim]No other corporations charted.[/]", classes="stat")]
        panel = Vertical(
            *children,  # type: ignore[arg-type]
            Horizontal(
                Button("Declare war", id="btn-war", variant="error"),
                Button("End war", id="btn-peace", variant="success"),
                classes="buttons"),
            Static("[dim]War acts on the selected row.[/]"),
            classes="corp-panel")
        panel.border_title = "Diplomacy"
        return panel

    # --- helpers ---------------------------------------------------------------

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

    def _selected_key(self, table_id: str) -> int | None:
        """The int key of the highlighted row in `table_id`, or None."""
        try:
            table = self.query_one(f"#{table_id}", DataTable)
        except Exception:
            return None
        if not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return int(key.value) if key.value is not None else None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "btn-form": self.action_form, "btn-accept": self.action_accept_invite,
            "btn-invite": self.action_invite, "btn-expel": self.action_expel,
            "btn-leave": self.action_leave, "btn-deposit": self.action_deposit,
            "btn-withdraw": self.action_withdraw, "btn-world-to": self.action_planet_to_corp,
            "btn-world-from": self.action_planet_from_corp, "btn-war": self.action_declare_war,
            "btn-peace": self.action_end_war,
        }
        handler = actions.get(event.button.id or "")
        if handler is not None:
            handler()

    def action_back(self) -> None:
        self.app.pop_screen()

    # --- charter / membership ----------------------------------------------------

    def _form(self, name: str) -> None:
        """Charter with a derived tag, uniquifying on a tag collision (never typed)."""
        max_len = self._service.config.corp.tag_max_len
        base = _derive_tag(name, max_len)
        candidates = [base] + [
            (base[: max_len - 1] if len(base) >= max_len else base) + str(n) for n in range(2, 10)
        ]
        for tag in candidates:
            try:
                self._service.apply(self._pid, FormCorp(name=name, tag=tag))
            except EconomyError as exc:
                if "already taken" in str(exc):
                    continue  # collision — try the next derived tag
                self.app.bell()
                self.notify(str(exc), severity="warning")
                return
            self.notify(f"Chartered ⟨{tag}⟩ {name}.", timeout=2)
            self._refresh()
            return
        self.notify("Couldn't derive a free tag — try a different name.", severity="warning")

    def action_form(self) -> None:
        view = self._service.corp_view(self._pid)
        if view is not None and view.corp_id:
            self.notify("You already belong to a corporation.", severity="warning")
            return

        def _done(name: str | None) -> None:
            if name:
                self._form(name)

        self.app.push_screen(_FormCorpModal(), _done)

    def action_deposit(self) -> None:
        self._apply(CorpDeposit(amount=1_000))

    def action_withdraw(self) -> None:
        self._apply(CorpWithdraw(amount=1_000))

    def action_leave(self) -> None:
        self._apply(LeaveCorp())

    # --- WP76: invite / accept / expel / war / asset transfer -----------------

    def action_invite(self) -> None:
        """CEO invites a captain by player id (the two-step consent join, WP66/WP76)."""
        from edge.tui.screens.stardock import _AmountInput

        def _go(pid: int | None) -> None:
            if pid:
                self._apply(InviteToCorp(invitee_player_id=pid), f"Invited captain #{pid}")
        self.app.push_screen(_AmountInput("Invite which captain (player id)?"), _go)

    def action_accept_invite(self) -> None:
        """Accept the invite selected in the invites table (or the only one)."""
        view = self._service.corp_view(self._pid)
        if view is None or view.corp_id or not view.invite_ids:
            self.notify("No standing invite to accept.", timeout=2)
            return
        cid = self._selected_key("corp-invites") or view.invite_ids[0]
        label = dict(zip(view.invite_ids, view.invites)).get(cid, "the corporation")
        self._apply(AcceptCorpInvite(corp_id=cid), f"Joined {label}")

    def action_expel(self) -> None:
        """CEO expels the roster member selected in the roster table."""
        member = self._selected_key("corp-members")
        if member is None:
            self.notify("Select a roster member first.", timeout=2)
            return
        self._apply(ExpelFromCorp(member_player_id=member))

    def _war_target(self) -> int | None:
        """The corp selected in the diplomacy table — war is picked, never typed."""
        target = self._selected_key("corp-others")
        if target is None:
            self.notify("Select a corporation in the Diplomacy panel first.", timeout=2)
        return target

    def action_declare_war(self) -> None:
        target = self._war_target()
        if target is not None:
            self._apply(DeclareCorpWar(target_corp_id=target), "War declared")

    def action_end_war(self) -> None:
        target = self._war_target()
        if target is not None:
            self._apply(EndCorpWar(target_corp_id=target), "War ended")

    def _sector_planet_id(self) -> int | None:
        planet = self._service.current_planet_view(self._pid)
        if planet is None:
            self.notify("No planet in this sector.", timeout=2)
            return None
        return planet.planet_id

    def action_planet_to_corp(self) -> None:
        """Hand this sector's world (yours) to the corp as a shared holding (WP76)."""
        pid = self._sector_planet_id()
        if pid is not None:
            self._apply(TransferPlanetToCorp(planet_id=pid), "World transferred to the corp.")

    def action_planet_from_corp(self) -> None:
        """Return this sector's corp-owned world to the CEO (CEO-gated, WP76)."""
        pid = self._sector_planet_id()
        if pid is not None:
            self._apply(TransferPlanetFromCorp(planet_id=pid), "World returned to the CEO.")
