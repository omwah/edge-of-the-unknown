"""PT-32 — the Computer's keyboard model: a tab owns its keys.

The screen binds only screen-wide keys (back, "route to…", the category accelerators).
Every per-tab verb is declared in `ComputerScreen.PANE_BINDINGS` and bound onto that
subview's `ActionPane`, so it is live only while focus rests inside that pane. These
tests pin the three consequences that matter:

- the footer (and the `.` menu / palette, via `action_descriptors`) advertises exactly
  the visible tab's verbs — never another tab's, and never a navigation key — with Back
  pinned to the front (chrome.EdgeScreen);
- a key may mean two things on two tabs ([Del] abandons a favor on Contracts, removes a
  note on Notes; a category's sub-tab numbers only address its own tabs) with no
  `check_action` scoping;
- focus lands on the tab's primary control (its table — *not* the filter box above it),
  which is what keeps the first two true.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.widgets import DataTable, Input, TabbedContent

from edge.core.rules import AddNote
from edge.tui.app import EdgeApp
from edge.tui.screens.computer import CATEGORY_LABELS, SUBVIEW_LABELS, ComputerScreen

# Keys a focused DetailTable owns (`/` filter, `O` cycle-sort). They sit *between* the
# focused table and the screen in the binding chain, so a pane or screen key that reused
# one would be unreachable from the very place it is meant to work — this is what sent
# the Logbook category's accelerator from `O` to `B`.
_TABLE_KEYS = {"o", "slash"}


def _screen_keys() -> set[str]:
    return {b.key for b in ComputerScreen.BINDINGS if isinstance(b, Binding)}


# --- static: the tables cannot drift ---------------------------------------------


def test_every_subview_declares_its_action_keys() -> None:
    assert set(ComputerScreen.PANE_BINDINGS) == set(SUBVIEW_LABELS)


def test_pane_actions_all_exist_on_the_screen() -> None:
    """Panes bind into the `screen.` namespace — every action must be a screen method."""
    for subview, triples in ComputerScreen.PANE_BINDINGS.items():
        for _key, action, description in triples:
            assert callable(getattr(ComputerScreen, f"action_{action}", None)), (
                f"{subview} binds {action!r}, which ComputerScreen does not implement")
            assert description, f"{subview}.{action} has no footer description"


def test_pane_keys_never_collide_with_screen_or_table_keys() -> None:
    """A pane key must win where it is bound, so it may not shadow — or be shadowed by —
    a screen binding or a DetailTable key. (Reuse *across* panes is the whole point and
    is allowed: only one pane is ever in the focus chain.)"""
    screen_keys = _screen_keys()
    for subview, triples in ComputerScreen.PANE_BINDINGS.items():
        keys = [key for key, _a, _d in triples]
        assert len(keys) == len(set(keys)), f"{subview} binds a key twice: {keys}"
        for key in keys:
            assert key not in screen_keys, (
                f"{subview} binds {key!r}, which is already a screen-wide key")
            assert key not in _TABLE_KEYS, (
                f"{subview} binds {key!r}, which its focused DetailTable consumes")


def test_category_accelerators_are_legible_and_unshadowed() -> None:
    """Each accelerator is a letter of its own tab title (so it can be underlined there),
    is unique, and is not swallowed by a focused table."""
    accels = ComputerScreen._CAT_ACCEL
    assert len(set(accels.values())) == len(accels)
    for category, letter in accels.items():
        assert letter in CATEGORY_LABELS[category].lower(), (
            f"{letter!r} is not in {CATEGORY_LABELS[category]!r} — it cannot be underlined")
        assert letter not in _TABLE_KEYS, (
            f"the {category} accelerator {letter!r} is consumed by a focused DetailTable")


# --- live: the footer follows the visible tab ------------------------------------


async def _open_computer(app: EdgeApp, pilot: object) -> ComputerScreen:
    await pilot.press("n")  # type: ignore[attr-defined]  (dismiss onboarding)
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.press("c")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    screen = app.screen
    assert isinstance(screen, ComputerScreen)
    return screen


def _footer_keys(screen: ComputerScreen) -> set[str]:
    """The keys the footer is currently offering (its exact source of truth)."""
    return {key for key, binding in screen.active_bindings.items() if binding.binding.show}


async def test_footer_offers_only_the_visible_tabs_verbs() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)  # opens on Trade

        keys = _footer_keys(screen)
        assert "p" in keys                      # Trade plots a route
        assert {"d", "delete", "j", "t", "s", "g", "v", "a", "w"} & keys == set()
        assert "escape" in keys                 # Back is the one screen-wide verb

        screen.show_subview("contracts")
        await pilot.pause()
        keys = _footer_keys(screen)
        assert {"d", "delete"} <= keys          # Deliver / Abandon appear…
        assert "p" not in keys                  # …and Trade's verb is gone

        screen.show_subview("notes")
        await pilot.pause()
        keys = _footer_keys(screen)
        assert {"a", "delete", "v"} <= keys
        assert "d" not in keys

        screen.show_subview("map")
        await pilot.pause()
        keys = _footer_keys(screen)
        assert {"g", "w"} <= keys               # Engage / Route to… (W, as on the sector view)


async def test_back_leads_the_footer_on_every_tab() -> None:
    """chrome.EdgeScreen pins Back first — it used to fall in behind whatever the
    focused widget owned (on Map it landed after Engage)."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        for subview in ("map", "trade", "contracts", "notes"):
            screen.show_subview(subview)
            await pilot.pause()
            shown = [k for k, b in screen.active_bindings.items() if b.binding.show]
            assert shown[0] == "escape", f"{subview} footer leads with {shown[0]!r}"


async def test_sub_tab_numbers_navigate_within_the_active_category() -> None:
    """Each category pane owns 1..N for its own sub-tabs — so `2` means a different tab
    in each category, and never reaches into another's."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)

        await pilot.press("n")  # → Navigation (Map · Route)
        await pilot.pause()
        await pilot.press("2")
        await pilot.pause()
        assert screen._active_subview() == "route"
        await pilot.press("1")
        await pilot.pause()
        assert screen._active_subview() == "map"

        await pilot.press("x")  # → eXploration (Planets · Codex · Leads)
        await pilot.pause()
        await pilot.press("3")
        await pilot.pause()
        assert screen._active_subview() == "leads"  # same key, this category's third tab

        # The numbers are navigation, not verbs: they stay out of the footer.
        assert not ({"1", "2", "3"} & _footer_keys(screen))


async def test_category_accelerators_reach_every_category() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        for key, category in (("n", "navigation"), ("c", "commerce"), ("x", "exploration"),
                              ("r", "relations"), ("b", "records")):
            await pilot.press(key)
            await pilot.pause()
            assert screen._active_category() == category, f"{key} did not reach {category}"


async def test_descriptors_match_the_footer_for_every_subview() -> None:
    """Parity guard for the `action_descriptors` override (tests/test_ui_actions.py
    delegates to this): the `.` menu, help and palette advertise the footer's keys."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        for subview in SUBVIEW_LABELS:
            screen.show_subview(subview)
            await pilot.pause()
            described = {d.key for d in screen.action_descriptors()}
            assert described == _footer_keys(screen), f"{subview} footer/menu disagree"


async def test_delete_means_two_things_on_two_tabs() -> None:
    """The payoff of pane-owned keys: one key, two verbs, no scoping maze."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")  # new game — the service exists from here
        await pilot.pause()
        service = app.service
        assert service is not None
        service.apply(1, AddNote(text="mind the black hole"))

        await pilot.press("c")  # open the Computer, which composes with the note in it
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ComputerScreen)
        screen.show_subview("notes")
        await pilot.pause()
        assert service.computer_view(1).notes == ["mind the black hole"]

        await pilot.press("delete")  # on Notes, Del strikes the highlighted note
        await pilot.pause()
        assert service.computer_view(1).notes == []

        # And on Contracts the same key is the abandon verb, not remove-note.
        screen = app.screen
        assert isinstance(screen, ComputerScreen)  # _reopen_tab rebuilt the screen
        screen.show_subview("contracts")
        await pilot.pause()
        assert screen.active_bindings["delete"].binding.action == "screen.abandon_contract"


async def test_accelerator_focuses_the_table_not_the_filter_box() -> None:
    """Enter-into-a-tab must land on the tab's primary control. DOM order would hand
    focus to the DetailTable's filter Input, which would eat the tab's action letters."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)

        await pilot.press("r")  # → Relations, focus its content
        await pilot.pause()
        assert screen._active_category() == "relations"
        focused = screen.focused
        assert isinstance(focused, DataTable), f"focus landed on {focused!r}"
        assert not isinstance(focused, Input)
        # …and the pane's verbs are therefore live.
        assert {"d", "delete"} <= _footer_keys(screen)


async def test_logbook_accelerator_survives_a_focused_table() -> None:
    """`B`, unlike the `O` it replaced, is not consumed by the focused DetailTable."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        assert isinstance(screen.focused, DataTable)  # a table has focus from the outset

        await pilot.press("b")
        await pilot.pause()
        assert screen._active_category() == "records"
        assert screen.query_one("#sub-records", TabbedContent).active in ("log", "notes")

        # And the converse: `O` still belongs to the focused table (it cycles that
        # table's sort), so it must not navigate anywhere.
        await pilot.press("o")
        await pilot.pause()
        assert screen._active_category() == "records"
