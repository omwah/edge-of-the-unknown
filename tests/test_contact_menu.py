"""The unified alien-contact reply menu (§6.7): per-reply gating + TUI render order.

The whole contact menu is authored `choices` now (no code-derived verb menu).
`session._gate_choice` is the server-side availability policy that greys a reply with a reason;
`AlienContactScreen._menu_items` is the render order (choices, with the farewell reply last) and
`check_action` controls the `b` (Back) / `f` (Farewell) / `f5` (Refresh, play-test-only) shortcuts.
"""

from __future__ import annotations

from edge.core import dto
from edge.core.config import DialogueChoice
from edge.server import session
from edge.tui.screens.contact import AlienContactScreen


# --- server gating (session._gate_choice) ----------------------------------------

def _gate(choice: DialogueChoice, *, posture: str = "open", treaty_mode: str = "open",
          attack_block: str | None = None, has_barter: bool = True, has_intel: bool = True,
          subjects_available: bool = True) -> tuple[bool, str]:
    return session._gate_choice(
        choice, posture=posture, treaty_mode=treaty_mode, attack_block=attack_block,
        has_barter=has_barter, has_intel=has_intel, subjects_available=subjects_available)


def test_gate_trade_follows_posture() -> None:
    trade = DialogueChoice(text="Trade", action="trade")
    assert _gate(trade) == (True, "")
    assert _gate(trade, posture="alliance_gated")[0] is False
    assert _gate(trade, posture="circuit_gated")[0] is False
    # A `refuses` posture keeps Trade live — an empty shelf routes to a spoken trade_refuse beat.
    assert _gate(trade, posture="refuses") == (True, "")


def test_gate_barter_and_accept_lead_track_availability() -> None:
    barter = DialogueChoice(text="Barter", action="barter")
    assert _gate(barter, has_barter=True) == (True, "")
    assert _gate(barter, has_barter=False)[0] is False
    log = DialogueChoice(text="Log", action="accept_lead")
    assert _gate(log, has_intel=True) == (True, "")
    assert _gate(log, has_intel=False)[0] is False


def test_gate_attack_follows_the_first_strike_block() -> None:
    """FIGHT is live (WP70): offered when nothing blocks it, greyed with the shared reason."""
    attack = DialogueChoice(text="Attack", action="attack")
    assert _gate(attack) == (True, "")
    blocked = _gate(attack, attack_block="the Core is a sanctuary — no attacks here")
    assert blocked == (False, "the Core is a sanctuary — no attacks here")


def test_gate_treaty_stays_disabled_with_a_reason() -> None:
    treaty = DialogueChoice(text="Treaty", next_context="treaty_offer")
    enabled, reason = _gate(treaty, treaty_mode="none")
    assert enabled is False and reason


def test_gate_ask_about_needs_met_others() -> None:
    ask = DialogueChoice(text="Ask", next_context="dossier_other")
    assert _gate(ask, subjects_available=True) == (True, "")
    assert _gate(ask, subjects_available=False)[0] is False


def test_gate_plain_transition_is_always_offered() -> None:
    coords = DialogueChoice(text="Coords", next_context="offer_coordinates")
    assert _gate(coords) == (True, "")
    back = DialogueChoice(text="Maybe later", next_context="back")
    assert _gate(back) == (True, "")


# --- TUI render order + shortcuts (AlienContactScreen) ----------------------------

def _choice(index: int, *, action: str = "", next_context: str = "",
            enabled: bool = True) -> dto.ContactChoiceDTO:
    return dto.ContactChoiceDTO(index=index, text="reply", action=action,
                                next_context=next_context, enabled=enabled)


def _dto(choices: list[dto.ContactChoiceDTO]) -> dto.ContactDTO:
    return dto.ContactDTO(
        species="Vesk", roster_id="vesk", persona="serial_formal", alliance="unaligned",
        standing="friendly", band="friendly", disposition_filled=4, base_disposition=0.8,
        attitude=0.0, effective=0.8, opener="…", offers=[], dossier=[], choices=choices)


def test_menu_items_renders_choices_with_farewell_last() -> None:
    screen = AlienContactScreen(_dto([
        _choice(0, action="trade"),
        _choice(1, action="leave"),              # the farewell reply sorts last
        _choice(2, next_context="dossier_other"),
    ]))
    items = screen._menu_items(screen._view())
    assert [o.index for _, o in items] == [0, 2, 1]


def test_menu_items_hides_disabled_unless_show_disabled() -> None:
    screen = AlienContactScreen(_dto([
        _choice(0, action="trade", enabled=True),
        _choice(1, next_context="treaty_offer", enabled=False),  # Phase-3 greyed
    ]))
    # No service ⇒ show_disabled defaults False, so the disabled reply is hidden.
    assert [o.index for _, o in screen._menu_items(screen._view())] == [0]


def test_check_action_gates_back_and_refresh() -> None:
    plain = AlienContactScreen(_dto([_choice(0, action="trade")]))
    assert plain.check_action("back_one", ()) is False   # no breadcrumb
    assert plain.check_action("refresh", ()) is False     # not the play-test harness
    assert plain.check_action("farewell", ()) is True
    with_history = AlienContactScreen(_dto([_choice(0, action="trade")]),
                                      history=(("greeting", None),))
    assert with_history.check_action("back_one", ()) is True
    playtest = AlienContactScreen(_dto([_choice(0, action="trade")]), playtest_mode=True)
    assert playtest.check_action("refresh", ()) is True


def test_on_exit_hook_replaces_the_default_pop() -> None:
    calls: list[str] = []
    screen = AlienContactScreen(_dto([_choice(0, action="leave")]),
                                on_exit=lambda: calls.append("exit"))
    screen._break_contact()  # no app needed: the hook runs instead of app.pop_screen()
    assert calls == ["exit"]
