"""WP9 — the always-present contact floor (§6.7).

A top-level branching node replaces the derived verb menu with authored player replies; the
floor keeps Ask about… / Farewell / Leave on offer there too, unless an authored reply already
covers them. `_contact_floor` is the server policy; `AlienContactScreen._menu_items` is the
unified render order (authored choices, then the uncovered floor).
"""

from __future__ import annotations

from edge.core import dto
from edge.server import session
from edge.tui.screens.contact import AlienContactScreen

_VERBS = [
    dto.ContactVerbDTO("hail", "Greet", kind="say", context="greeting"),
    dto.ContactVerbDTO("ask", "Ask about…", True, kind="say", context="dossier_other",
                       needs_subject=True),
    dto.ContactVerbDTO("trade", "Buy tech"),
    dto.ContactVerbDTO("farewell", "Farewell", kind="say", context="farewell"),
    dto.ContactVerbDTO("leave", "Leave"),
]


def _choice(index: int, *, action: str = "", next_context: str = "") -> dto.ContactChoiceDTO:
    return dto.ContactChoiceDTO(index=index, text="reply", action=action,
                                next_context=next_context)


def test_floor_fills_gaps_on_a_branching_top_node() -> None:
    # An authored greeting that only opens a branch leaves every floor verb uncovered.
    floor = session._contact_floor(_VERBS, [_choice(0, next_context="branch.shop")], "greeting")
    assert [v.key for v in floor] == ["ask", "farewell", "leave"]


def test_floor_drops_what_the_grammar_already_covers() -> None:
    # A choice that asks about others covers Ask about…; one that says farewell covers the exit.
    ask_covered = session._contact_floor(_VERBS, [_choice(0, next_context="dossier_other")],
                                         "greeting")
    assert [v.key for v in ask_covered] == ["farewell", "leave"]
    exit_covered = session._contact_floor(_VERBS, [_choice(0, action="farewell")], "greeting")
    assert [v.key for v in exit_covered] == ["ask"]


def test_no_floor_on_deep_branch_or_plain_nodes() -> None:
    # Deeper branch.* nodes show exactly what the author wrote (top-level only).
    assert session._contact_floor(_VERBS, [_choice(0, action="farewell")], "branch.shop") == []
    # A plain node has no authored choices, so the derived menu already carries the floor verbs.
    assert session._contact_floor(_VERBS, [], "greeting") == []


def _dto(*, choices: list[dto.ContactChoiceDTO], floor: list[dto.ContactVerbDTO],
         verbs: list[dto.ContactVerbDTO] | None = None) -> dto.ContactDTO:
    return dto.ContactDTO(
        species="Vesk", persona="serial_formal", alliance="unaligned", standing="friendly",
        band="friendly", disposition_filled=4, base_disposition=0.8, attitude=0.0,
        effective=0.8, opener="…", verbs=_VERBS if verbs is None else verbs, offers=[],
        dossier=[], choices=choices, floor_verbs=floor)


def _ids(items: list[tuple[str, object]]) -> list[tuple[str, object]]:
    return [(kind, getattr(o, "index", getattr(o, "key", None))) for kind, o in items]


def test_menu_items_renders_choices_then_floor() -> None:
    screen = AlienContactScreen(_dto(
        choices=[_choice(0, next_context="branch.shop"), _choice(1, next_context="branch.lab")],
        floor=[_VERBS[1]]))  # ask
    assert _ids(screen._menu_items(screen._view())) == [
        ("choice", 0), ("choice", 1), ("verb", "ask")]


def test_farewell_always_sorts_last() -> None:
    # Derived menu: the farewell verb drops below Leave (everything else keeps its order).
    plain = AlienContactScreen(_dto(choices=[], floor=[]))
    assert [o.key for _, o in plain._menu_items(plain._view())] == [
        "hail", "ask", "trade", "leave", "farewell"]
    # Branching node: a farewell *choice* sorts behind the later floor verbs too.
    branch = AlienContactScreen(_dto(
        choices=[_choice(0, next_context="branch.shop"), _choice(1, action="farewell")],
        floor=[_VERBS[1], _VERBS[4]]))  # ask, leave
    assert _ids(branch._menu_items(branch._view())) == [
        ("choice", 0), ("verb", "ask"), ("verb", "leave"), ("choice", 1)]


def test_on_exit_hook_replaces_the_default_pop() -> None:
    calls: list[str] = []
    screen = AlienContactScreen(_dto(choices=[], floor=[]), on_exit=lambda: calls.append("exit"))
    screen._break_contact()  # no app needed: the hook runs instead of app.pop_screen()
    assert calls == ["exit"]


def test_check_action_hides_verbs_absent_from_the_menu() -> None:
    # Derived menu: an enabled verb's shortcut shows; a disabled one is hidden.
    verbs = [
        dto.ContactVerbDTO("hail", "Greet", kind="say", context="greeting"),
        dto.ContactVerbDTO("trade", "Trade", False, "they refuse to trade"),
        dto.ContactVerbDTO("farewell", "Farewell", kind="say", context="farewell"),
    ]
    screen = AlienContactScreen(_dto(choices=[], floor=[], verbs=verbs))
    assert screen.check_action("verb", ("hail",)) is True
    assert screen.check_action("verb", ("trade",)) is None  # disabled ⇒ hidden
    # Branching node: only floor verbs are in the menu, so Greet/Trade vanish, Ask stays.
    branch = AlienContactScreen(_dto(
        choices=[_choice(0, next_context="branch.shop")], floor=[_VERBS[1]]))  # ask
    assert branch.check_action("verb", ("ask",)) is True
    assert branch.check_action("verb", ("hail",)) is None
    assert branch.check_action("verb", ("trade",)) is None


def test_check_action_hides_back_without_history() -> None:
    no_history = AlienContactScreen(_dto(choices=[], floor=[]))
    assert no_history.check_action("back_one", ()) is None
    assert no_history.check_action("back", ()) is True  # Escape always breaks contact
    with_history = AlienContactScreen(_dto(choices=[], floor=[]),
                                      history=(("greeting", None),))
    assert with_history.check_action("back_one", ()) is True
