"""WP9 — the always-present contact floor (§6.7).

A top-level branching node replaces the derived verb menu with authored player replies; the
floor keeps Ask about… / Farewell / Leave on offer there too, unless an authored reply already
covers them. `_contact_floor` is the server policy; `AlienContactScreen._menu_items` is the
unified render order (authored choices, then the uncovered floor).
"""

from __future__ import annotations

from edge.config import load_default_config
from edge.core import dto
from edge.server import session
from edge.tui.screens.contact import AlienContactScreen

_ROSTER = load_default_config().roster

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
    floor = session._contact_floor(_VERBS, [_choice(0, next_context="branch.shop")], "greeting", _ROSTER)
    assert [v.key for v in floor] == ["ask", "farewell"]


def test_floor_drops_what_the_grammar_already_covers() -> None:
    # A choice that asks about others covers Ask about…; one that says farewell covers the exit.
    ask_covered = session._contact_floor(_VERBS, [_choice(0, next_context="dossier_other")],
                                         "greeting", _ROSTER)
    assert [v.key for v in ask_covered] == ["farewell"]
    exit_covered = session._contact_floor(_VERBS, [_choice(0, action="farewell")], "greeting", _ROSTER)
    assert [v.key for v in exit_covered] == ["ask"]


def test_no_floor_on_deep_branch_or_plain_nodes() -> None:
    # Deeper branch.* nodes show exactly what the author wrote (top-level only).
    assert session._contact_floor(_VERBS, [_choice(0, action="farewell")], "branch.shop", _ROSTER) == []
    # A plain node has no authored choices, so the derived menu already carries the floor verbs.
    assert session._contact_floor(_VERBS, [], "greeting", _ROSTER) == []


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


def test_check_action_shows_a_verb_iff_it_is_enabled() -> None:
    # The shortcut tracks the verb's enablement, not whether it is a rendered row — so an offered
    # Trade shows even on a branching node whose visible rows are authored choices, while a
    # refused/empty one is hidden.
    verbs = [
        dto.ContactVerbDTO("trade", "Buy tech"),  # offered (enabled)
        dto.ContactVerbDTO("barter", "Barter", False, "they offer no barter"),  # disabled
        dto.ContactVerbDTO("farewell", "Farewell", kind="say", context="farewell"),
    ]
    plain = AlienContactScreen(_dto(choices=[], floor=[], verbs=verbs))
    assert plain.check_action("verb", ("trade",)) is True
    assert plain.check_action("verb", ("barter",)) is False
    branch = AlienContactScreen(_dto(
        choices=[_choice(0, next_context="branch.shop")], floor=[], verbs=verbs))
    assert branch.check_action("verb", ("trade",)) is True  # offered ⇒ shown even on a branch
    assert branch.check_action("verb", ("barter",)) is False


def test_check_action_shows_enabled_say_verbs_and_hides_disabled_ones() -> None:
    # Regreet / Ask / Farewell show on a branching node when enabled in the view's verbs.
    verbs = [
        dto.ContactVerbDTO("hail", "Regreet", kind="say", context="greeting"),
        dto.ContactVerbDTO("ask", "Ask about…", True, kind="say", context="dossier_other"),
        dto.ContactVerbDTO("farewell", "Farewell", kind="say", context="farewell"),
    ]
    branch = AlienContactScreen(_dto(
        choices=[_choice(0, next_context="branch.shop"), _choice(1, action="farewell")],
        floor=[], verbs=verbs))
    for key in ("hail", "ask", "farewell"):
        assert branch.check_action("verb", (key,)) is True
    # A disabled verb is hidden (e.g. Ask with nobody met yet).
    no_subjects = AlienContactScreen(_dto(choices=[], floor=[], verbs=[
        dto.ContactVerbDTO("ask", "Ask about…", False, "no other species met yet",
                           kind="say", context="dossier_other")]))
    assert no_subjects.check_action("verb", ("ask",)) is False


def test_check_action_hides_regreet_when_the_game_omits_it() -> None:
    # The game drops the Greet/Regreet verb, so its shortcut never shows there.
    game = AlienContactScreen(_dto(choices=[], floor=[], verbs=[
        dto.ContactVerbDTO("ask", "Ask about…", True, kind="say", context="dossier_other"),
        dto.ContactVerbDTO("farewell", "Farewell", kind="say", context="farewell")]))
    assert game.check_action("verb", ("hail",)) is False


def test_check_action_hides_back_without_history() -> None:
    no_history = AlienContactScreen(_dto(choices=[], floor=[]))
    assert no_history.check_action("back_one", ()) is False
    assert no_history.check_action("back", ()) is True  # Escape always breaks contact
    with_history = AlienContactScreen(_dto(choices=[], floor=[]),
                                      history=(("greeting", None),))
    assert with_history.check_action("back_one", ()) is True


def test_floor_context_and_keys_are_configurable() -> None:
    # Set a custom floor context and list of floor keys
    custom_roster = _ROSTER.model_copy(update={
        "floor_context": "offer_coordinates",
        "floor_keys": ["trade"]
    })
    # If the active context is "offer_coordinates", it should now return the configured floor verbs
    floor = session._contact_floor(_VERBS, [_choice(0, next_context="branch.shop")], "offer_coordinates", custom_roster)
    assert [v.key for v in floor] == ["trade"]
    # If the active context is "greeting", it should now return empty list (since it's not the configured context)
    assert session._contact_floor(_VERBS, [_choice(0, next_context="branch.shop")], "greeting", custom_roster) == []
