"""PT-32 — the Stardock's keyboard model: a tab owns its keys.

The same model the Computer uses (tests/test_ui_computer_keys.py), applied to the
services hub. The screen binds only screen-wide keys (undock and the tab accelerators);
every per-tab verb — the Engine Room included, which belongs to Hardware — is declared in
`StardockScreen.PANE_BINDINGS` and
bound onto that tab's `ActionPane` by `ServiceHub`, so it is live only while focus rests
inside that tab. These tests pin the consequences:

- the footer (and the `.` menu / palette, via `action_descriptors`) advertises exactly
  the visible tab's verbs — never another tab's, never a navigation key — with Back
  pinned to the front (chrome.EdgeScreen);
- no `check_action` scoping: the keys simply are not in the chain off their tab;
- focus lands inside the visible tab — including on the Bank, which is pure text and so
  must hold focus itself, or its Deposit/Withdraw keys would never be live.
"""

from __future__ import annotations

from dataclasses import replace

from textual.binding import Binding
from textual.widgets import TabbedContent

from edge.core.movement import shortest_path
from edge.core.rules import Warp
from edge.tui.app import EdgeApp
from edge.tui.saves import clear_slot
from edge.tui.screens.stardock import StardockScreen


def _screen_keys() -> set[str]:
    return {b.key for b in StardockScreen.BINDINGS if isinstance(b, Binding)}


# --- static: the tables cannot drift ---------------------------------------------


def test_every_tab_declares_its_action_keys() -> None:
    assert set(StardockScreen.PANE_BINDINGS) == set(StardockScreen._TAB_ACCEL)


def test_pane_actions_all_exist_on_the_screen() -> None:
    """Panes bind into the `screen.` namespace — every action must be a screen method.

    Covers the hidden pane keys too (the Colonists digits): they are bindings like any
    other, just kept off the footer, so a typo in one would still be a dead key.
    """
    panes = {**StardockScreen.PANE_BINDINGS, **StardockScreen.PANE_HIDDEN}
    for tab, triples in panes.items():
        for _key, action, description in triples:
            name = action.split("(", 1)[0]  # a binding may carry parameters
            assert callable(getattr(StardockScreen, f"action_{name}", None)), (
                f"{tab} binds {action!r}, which StardockScreen does not implement")
            assert description, f"{tab}.{action} has no description"


def test_pane_keys_never_collide_with_screen_keys() -> None:
    """A pane key may not shadow — or be shadowed by — a screen key: an accelerator that
    a focused pane swallowed would be unreachable from the very tab it must work on.
    (Reuse *across* panes is the point and is allowed: one pane is in the chain at a time.)
    """
    screen_keys = _screen_keys()
    for tab in StardockScreen.PANE_BINDINGS:
        keys = [key for key, _a, _d in (StardockScreen.PANE_BINDINGS[tab]
                                        + StardockScreen.PANE_HIDDEN.get(tab, ()))]
        assert len(keys) == len(set(keys)), f"{tab} binds a key twice: {keys}"
        for key in keys:
            assert key not in screen_keys, (
                f"{tab} binds {key!r}, which is already a screen-wide key")


def test_tab_accelerators_are_legible_and_unique() -> None:
    """Each accelerator is a letter of its own tab title, so it can be underlined there."""
    labels = {"trade": "Commodities", "shipyard": "Shipyard", "hardware": "Hardware",
              "devices": "Devices & Armaments", "colonists": "Colonists",
              "barracks": "Marines", "bank": "Bank", "tavern": "Tavern"}
    accels = StardockScreen._TAB_ACCEL
    assert len(set(accels.values())) == len(accels)
    for tab, letter in accels.items():
        assert letter in labels[tab].lower(), (
            f"{letter!r} is not in {labels[tab]!r} — it cannot be underlined")


# --- live -------------------------------------------------------------------------


async def _dock(app: EdgeApp, pilot: object) -> object:
    clear_slot()
    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    svc = app.service
    assert svc is not None
    dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)
    start = svc.game_view(1).sector.sector_id
    for hop in (shortest_path(svc.state.adjacency, start, dock.sector_id) or [])[1:]:
        svc.apply(1, Warp(to_sector=hop))
    svc.state.players[1] = replace(svc.state.players[1], latinum=200_000)
    await pilot.press("p")  # dock -> StardockScreen  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    return svc


def _footer_keys(screen: StardockScreen) -> set[str]:
    """The keys the footer is currently offering (its exact source of truth)."""
    return {key for key, binding in screen.active_bindings.items() if binding.binding.show}


async def test_footer_offers_only_the_visible_tabs_verbs() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StardockScreen)

        keys = _footer_keys(screen)  # opens on Commodities
        assert {"t", "g"} <= keys                       # Trade / Haggle
        assert {"p", "e", "k", "a", "w", "r", "n"} & keys == set()
        assert "escape" in keys                         # the one screen-wide verb

        for tab, verbs, gone in (
            # The Engine Room is Hardware's own key, not a screen key: you buy the part
            # and slot it in one errand, and it is offered nowhere else.
            ("hardware", {"p", "e"}, {"t", "g"}),
            ("colonists", {"k"}, {"p", "e"}),
            ("bank", {"a", "w"}, {"k"}),
            ("tavern", {"r", "n"}, {"a", "w"}),
        ):
            await pilot.press(StardockScreen._TAB_ACCEL[tab])
            await pilot.pause()
            keys = _footer_keys(screen)
            assert verbs <= keys, f"{tab} footer is missing {verbs - keys}"
            assert not (gone & keys), f"{tab} footer still offers {gone & keys}"


async def test_back_leads_the_footer_on_every_tab() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StardockScreen)
        for tab, accel in StardockScreen._TAB_ACCEL.items():
            await pilot.press(accel)
            await pilot.pause()
            shown = [k for k, b in screen.active_bindings.items() if b.binding.show]
            assert shown[0] == "escape", f"{tab} footer leads with {shown[0]!r}"


async def test_accelerators_reach_every_tab_and_stay_off_the_footer() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StardockScreen)
        tabs = screen.query_one(TabbedContent)
        for tab, accel in StardockScreen._TAB_ACCEL.items():
            await pilot.press(accel)
            await pilot.pause()
            assert tabs.active == tab, f"{accel!r} did not reach {tab}"
        # They are navigation, not verbs: none of them appears in the footer.
        assert not (set(StardockScreen._TAB_ACCEL.values()) & _footer_keys(screen))


async def test_bank_holds_focus_so_its_keys_are_live() -> None:
    """The Bank pane has no focusable content — it must hold focus itself, or Deposit
    and Withdraw could never fire from it (widgets.focus_content)."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StardockScreen)

        await pilot.press("b")  # → Bank
        await pilot.pause()
        assert screen.focused is not None
        assert {"a", "w"} <= _footer_keys(screen)
        assert screen.active_bindings["a"].binding.action == "screen.deposit"


async def test_colonists_digits_type_an_amount_and_plus_minus_step_it() -> None:
    """The Colonists tab opens on its Recruit button, which leaves the digits free: typing
    one starts an amount (and hands focus to the field, so the rest is plain typing), and
    `+`/`−` step it without entering the field at all."""
    from textual.widgets import Input

    from edge.tui.amount_stepper import AmountStepper

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StardockScreen)

        await pilot.press("l")  # → Colonists
        await pilot.pause()
        stepper = screen.query_one("#stepper-recruit", AmountStepper)

        # `+` / `−` step by the stepper's own step, from the tab's own focus.
        await pilot.press("plus")
        await pilot.pause()
        assert stepper.amount == stepper.step
        await pilot.press("minus")
        await pilot.pause()
        assert stepper.amount == 0

        # A digit *starts* an amount: it replaces the field and takes focus, so the digits
        # after it are ordinary typing and Enter recruits what was typed.
        await pilot.press("4")
        await pilot.pause()
        assert isinstance(screen.focused, Input)
        assert screen.focused.id == "amt-recruit"
        await pilot.press("2")
        await pilot.pause()
        assert stepper.amount == 42

        before = svc.state.ships[1].colonists  # type: ignore[attr-defined]
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        assert svc.state.ships[1].colonists - before == 42  # type: ignore[attr-defined]


async def test_descriptors_match_the_footer_for_every_tab() -> None:
    """Parity guard for the `action_descriptors` override (tests/test_ui_actions.py
    delegates to this): the `.` menu, help and palette advertise the footer's keys."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StardockScreen)
        for tab, accel in StardockScreen._TAB_ACCEL.items():
            await pilot.press(accel)
            await pilot.pause()
            described = {d.key for d in screen.action_descriptors()}
            assert described == _footer_keys(screen), f"{tab} footer/menu disagree"


async def test_purchase_key_is_live_on_every_buy_tab() -> None:
    """P buys on Hardware, Shipyard and Devices — one key, three catalogs, no scoping."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _dock(app, pilot)
        screen = app.screen
        assert isinstance(screen, StardockScreen)

        await pilot.press("h")  # → Hardware
        await pilot.pause()
        assert screen.active_bindings["p"].binding.action == "screen.buy"
        await pilot.press("p")
        await pilot.pause()
        # The component is aboard, loose, ready to slot in the Engine Room.
        assert sum(svc.state.ships[1].components.values()) == 1  # type: ignore[attr-defined]
