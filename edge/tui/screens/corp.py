"""Corporations (DESIGN §4, WP66; completed WP76) — the Computer's **Corp** subview.

No longer a screen of its own. The corp is a *relationship*, like a contract, an alliance
or a dossier, so it lives with them under the Computer's Relations category rather than
behind a game-screen hotkey of its own (which the UI_MOCKUPS verb table had long flagged
as grandfathered, "rename when corp gets a hub" — this is that hub).

Two pieces, so the Computer can host it without inheriting a screen:

- `CorpPanels` — presentation. Three bordered panels (roster · treasury & holdings ·
  diplomacy) built on DataTables and Buttons, or the corpless empty state. Panel-first and
  mouse-first: every corp verb is a button acting on the highlighted row of its panel, and
  the keys are accelerators for those same buttons.
- `CorpActions` — the verbs, as a mixin. The host supplies `_service`, `_pid` and
  `_reopen_corp()`; nothing here touches a screen stack directly.

Chartering asks for a *name* only: the short uppercase tag is an internal identifier
derived from it (initials, uniquified on collision). War is declared and ended against the
corp selected in the diplomacy table — never by typing an index. Actions are the ordinary
corp commands issued through the service, so single-player it manages a corp of one and
the same panels serve multiplayer.
"""

from __future__ import annotations

from typing import Any

import re

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Static

from textual.css.query import NoMatches

from edge.core.economy import EconomyError
from edge.core.rules import (
    AcceptCorpInvite, CorpDeposit, CorpWithdraw, DeclareCorpWar, EndCorpWar,
    ExpelFromCorp, FormCorp, InviteToCorp, LeaveCorp, TransferPlanetFromCorp,
    TransferPlanetToCorp,
)
from edge.server.service import GameService
from edge.tui.chrome import EmptyState, TextPrompt, notify_warning


def _ceo_button(label: str, button_id: str, *, is_ceo: bool,
                variant: str = "default") -> Button:
    """A CEO-gated verb: members see it disabled with the reason (WP-UI19)."""
    button = Button(label, id=button_id, variant=variant, disabled=not is_ceo)  # type: ignore[arg-type]
    if not is_ceo:
        button.tooltip = "Only the CEO may do this."
    return button


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


class _FormCorpModal(TextPrompt):
    """Prompt a corporation *name* — the tag is derived, not typed (WP-UI07 shared form)."""

    def __init__(self) -> None:
        super().__init__("Charter a corporation", placeholder="Corporation name",
                         submit_label="Charter")


class CorpPanels(Vertical):
    """The corp's three panels — or the corpless empty state (presentation only).

    Rendered from a `CorpDTO`; it issues no commands. The host (the Computer's Corp
    subview) routes its button presses into `CorpActions` and rebuilds this on any change.
    """

    DEFAULT_CSS = """
    CorpPanels { height: auto; }
    CorpPanels #corp-title { height: 1; background: $accent; color: $background;
        text-style: bold; padding: 0 1; margin-bottom: 1; }
    CorpPanels #corp-panels { height: auto; }
    CorpPanels .corp-panel {
        width: 1fr; height: auto; border: round $primary;
        padding: 0 1; margin: 0 1 0 0;
    }
    CorpPanels .corp-panel DataTable { height: auto; max-height: 8; margin-bottom: 1; }
    CorpPanels .corp-panel Button { margin: 0 1 1 0; min-width: 14; }
    CorpPanels .corp-panel .buttons { height: auto; }
    CorpPanels .corp-panel Static.stat { margin-bottom: 1; }
    CorpPanels #corp-empty-box { padding: 0; height: auto; }
    CorpPanels #corp-empty-box Button { margin: 1 1 0 0; min-width: 18; }
    """

    def __init__(self, view: object, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._view = view

    # --- layout ----------------------------------------------------------------

    def compose(self) -> ComposeResult:
        view = self._view
        if view is None or not view.corp_id:  # type: ignore[attr-defined]
            yield Static("[b]CORPORATION[/]        [dim]you fly alone[/]", id="corp-title")
            with Vertical(id="corp-empty-box"):
                yield EmptyState(
                    "You fly alone — no charter, no shared treasury.",
                    "Charter a corporation to pool latinum, worlds, and bases "
                    "with other captains (a corp of one works too).")
                invites = view.invites if view is not None else []  # type: ignore[attr-defined]
                if invites:
                    table: DataTable[Any] = DataTable(id="corp-invites", cursor_type="row")
                    table.add_columns("Standing invites")
                    for cid, label in zip(view.invite_ids, invites):  # type: ignore[union-attr]
                        table.add_row(label, key=str(cid))
                    yield table
                with Horizontal(classes="buttons"):
                    yield Button("Charter a corporation…", id="btn-form", variant="primary")
                    if invites:
                        yield Button("Accept selected invite", id="btn-accept", variant="success")
            return
        role = "CEO" if view.is_ceo else "member"  # type: ignore[attr-defined]
        yield Static(f"⟨{view.tag}⟩ {view.name} — you are {role}",  # type: ignore[attr-defined]
                     id="corp-title")
        with Horizontal(id="corp-panels"):
            yield self._roster_panel(view)
            yield self._holdings_panel(view)
            yield self._diplomacy_panel(view)

    def _roster_panel(self, view: object) -> Vertical:
        is_ceo: bool = view.is_ceo  # type: ignore[attr-defined]
        table: DataTable[Any] = DataTable(id="corp-members", zebra_stripes=True, cursor_type="row")
        table.add_columns("Member", "Role")
        for m in view.members:  # type: ignore[attr-defined]
            table.add_row(m.name, "CEO" if m.is_ceo else "member", key=str(m.player_id))
        # WP-UI19: the CEO's primary verb is growing the roster; members see the
        # CEO-gated verbs disabled with the reason instead of a surprise rejection.
        panel = Vertical(
            table,
            Horizontal(
                _ceo_button("Invite…", "btn-invite", is_ceo=is_ceo,
                            variant="primary" if is_ceo else "default"),
                _ceo_button("Expel selected", "btn-expel", is_ceo=is_ceo,
                            variant="warning"),
                classes="buttons"),
            Horizontal(Button("Leave corp", id="btn-leave", variant="error"),
                       classes="buttons"),
            classes="corp-panel")
        panel.border_title = "Roster"
        return panel

    def _holdings_panel(self, view: object) -> Vertical:
        is_ceo: bool = view.is_ceo  # type: ignore[attr-defined]
        panel = Vertical(
            Static(f"Bank      [b yellow]{view.bank_balance:,}[/] slips", classes="stat"),  # type: ignore[attr-defined]
            Static(f"Worlds    [b]{view.planet_count}[/]", classes="stat"),  # type: ignore[attr-defined]
            Static(f"Bases     [b]{view.starbase_count}[/]", classes="stat"),  # type: ignore[attr-defined]
            Horizontal(
                Button("Deposit 1k", id="btn-deposit",
                       variant="default" if is_ceo else "primary"),
                _ceo_button("Withdraw 1k", "btn-withdraw", is_ceo=is_ceo),
                classes="buttons"),
            Horizontal(
                Button("World → corp", id="btn-world-to"),
                _ceo_button("World → CEO", "btn-world-from", is_ceo=is_ceo),
                classes="buttons"),
            Static("[dim]World transfers act on the planet in your current sector."
                   + ("" if is_ceo else " Withdrawals and world returns are CEO-only.")
                   + "[/]"),
            classes="corp-panel")
        panel.border_title = "Treasury & holdings"
        return panel

    def _diplomacy_panel(self, view: object) -> Vertical:
        is_ceo: bool = view.is_ceo  # type: ignore[attr-defined]
        table: DataTable[Any] = DataTable(id="corp-others", zebra_stripes=True, cursor_type="row")
        table.add_columns("Corporation", "Status")
        at_war = set(view.at_war_with)  # type: ignore[attr-defined]
        for cid, label in view.other_corps:  # type: ignore[attr-defined]
            tag = label.split(" — ", 1)[0]
            status = "[red]at war[/]" if tag in at_war else "[dim]—[/]"
            table.add_row(label, status, key=str(cid))
        children: list[object] = [table]
        has_rivals = bool(view.other_corps)  # type: ignore[attr-defined]
        if not has_rivals:
            children = [EmptyState("No other corporations charted.",
                                   "Rival corps appear here as they charter.")]
        war = _ceo_button("Declare war", "btn-war", is_ceo=is_ceo, variant="error")
        peace = _ceo_button("End war", "btn-peace", is_ceo=is_ceo, variant="success")
        if is_ceo and not has_rivals:
            for button in (war, peace):
                button.disabled = True
                button.tooltip = "No other corporation to act on."
        panel = Vertical(
            *children,  # type: ignore[arg-type]
            Horizontal(war, peace, classes="buttons"),
            Static("[dim]War acts on the selected row"
                   + ("." if is_ceo else " — declaring and ending it are CEO-only.")
                   + "[/]"),
            classes="corp-panel")
        panel.border_title = "Diplomacy"
        return panel


class CorpActions:
    """The corp verbs, as a mixin for the screen that hosts `CorpPanels` (the Computer).

    The host supplies `_service`, `_pid`, and `_reopen_corp()` (rebuild on the Corp
    subview). Keeping the verbs here — rather than on a screen — is what let the corp move
    under the Computer without either half knowing about the other's chrome.
    """

    _service: GameService
    _pid: int

    def _reopen_corp(self) -> None:
        raise NotImplementedError

    def _apply(self, command: object, ok: str | None = None) -> None:
        try:
            self._service.apply(self._pid, command)  # type: ignore[arg-type]
        except EconomyError as exc:
            self.app.bell()  # type: ignore[attr-defined]
            notify_warning(self, str(exc))
            return
        if ok:
            self.notify(ok, timeout=2)  # type: ignore[attr-defined]
        self._reopen_corp()

    def _selected_key(self, table_id: str) -> int | None:
        """The int key of the highlighted row in `table_id`, or None."""
        try:
            table = self.query_one(f"#{table_id}", DataTable)  # type: ignore[attr-defined]
        except NoMatches:
            return None
        if not table.row_count:
            return None
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return int(key.value) if key.value is not None else None

    # Button id -> action name. The host's `on_button_pressed` offers each press here
    # first; anything unclaimed stays the host's own.
    CORP_BUTTONS = {
        "btn-form": "form", "btn-accept": "accept_invite", "btn-invite": "invite",
        "btn-expel": "expel", "btn-leave": "leave", "btn-deposit": "deposit",
        "btn-withdraw": "withdraw", "btn-world-to": "planet_to_corp",
        "btn-world-from": "planet_from_corp", "btn-war": "declare_war",
        "btn-peace": "end_war",
    }

    def handle_corp_button(self, button_id: str) -> bool:
        """Run the corp verb this button names; True if it was one of ours."""
        action = self.CORP_BUTTONS.get(button_id)
        if action is None:
            return False
        getattr(self, f"action_{action}")()
        return True

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
                self.app.bell()  # type: ignore[attr-defined]
                notify_warning(self, str(exc))
                return
            self.notify(f"Chartered ⟨{tag}⟩ {name}.", timeout=2)  # type: ignore[attr-defined]
            self._reopen_corp()
            return
        notify_warning(self, "Couldn't derive a free tag — try a different name.")

    def action_form(self) -> None:
        view = self._service.corp_view(self._pid)
        if view is not None and view.corp_id:
            notify_warning(self, "You already belong to a corporation.")
            return

        def _done(name: str | None) -> None:
            if name:
                self._form(name)

        self.app.push_screen(_FormCorpModal(), _done)  # type: ignore[attr-defined]

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
        self.app.push_screen(_AmountInput("Invite which captain (player id)?"), _go)  # type: ignore[attr-defined]

    def action_accept_invite(self) -> None:
        """Accept the invite selected in the invites table (or the only one)."""
        view = self._service.corp_view(self._pid)
        if view is None or view.corp_id or not view.invite_ids:
            self.notify("No standing invite to accept.", timeout=2)  # type: ignore[attr-defined]
            return
        cid = self._selected_key("corp-invites") or view.invite_ids[0]
        label = dict(zip(view.invite_ids, view.invites)).get(cid, "the corporation")
        self._apply(AcceptCorpInvite(corp_id=cid), f"Joined {label}")

    def action_expel(self) -> None:
        """CEO expels the roster member selected in the roster table."""
        member = self._selected_key("corp-members")
        if member is None:
            self.notify("Select a roster member first.", timeout=2)  # type: ignore[attr-defined]
            return
        self._apply(ExpelFromCorp(member_player_id=member))

    def _war_target(self) -> int | None:
        """The corp selected in the diplomacy table — war is picked, never typed."""
        target = self._selected_key("corp-others")
        if target is None:
            self.notify("Select a corporation in the Diplomacy panel first.",  # type: ignore[attr-defined]
                        timeout=2)
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
            self.notify("No planet in this sector.", timeout=2)  # type: ignore[attr-defined]
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
