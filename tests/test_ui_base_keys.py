"""PT-32 — the Starbase's keyboard model: a tab owns its keys.

The third and last screen on the model (after the Computer and the Stardock), and the one
that shows why the model is worth the trouble: the Base's tabs are **gated by standing**,
so a withheld tab now keeps *no* keys at all — the footer physically cannot offer a verb
the reducers would refuse, without a single `check_action`.

The screen binds only screen-wide keys (leave, and the tab accelerators); every verb is
declared in `BaseScreen.PANE_BINDINGS` and bound onto its tab's `ActionPane` by
`ServiceHub`, so it is live only while focus rests inside that tab.
"""

from __future__ import annotations

from dataclasses import replace

from textual.binding import Binding
from textual.widgets import Static, TabbedContent

from edge.tui.app import EdgeApp
from edge.tui.saves import clear_slot
from edge.tui.screens.base import BaseScreen

# The `trade` pane id is unchanged; only its label is Commodities now (matching the
# Stardock), so deep links and `initial_tab` keep addressing it by the same name.
_TAB_LABELS = {"station": "Station", "trade": "Commodities",
               "hardware": "Hardware", "bank": "Bank"}


def _screen_keys() -> set[str]:
    return {b.key for b in BaseScreen.BINDINGS if isinstance(b, Binding)}


# --- static: the tables cannot drift ---------------------------------------------


def test_every_tab_declares_its_action_keys() -> None:
    assert set(BaseScreen.PANE_BINDINGS) == set(BaseScreen._TAB_ACCEL) == set(_TAB_LABELS)


def test_pane_actions_all_exist_on_the_screen() -> None:
    """Panes bind into the `screen.` namespace — every action must be a screen method."""
    for tab, triples in BaseScreen.PANE_BINDINGS.items():
        for _key, action, description in triples:
            name = action.split("(", 1)[0]  # a binding may carry parameters
            assert callable(getattr(BaseScreen, f"action_{name}", None)), (
                f"{tab} binds {action!r}, which BaseScreen does not implement")
            assert description, f"{tab}.{action} has no footer description"


def test_pane_keys_never_collide_with_screen_keys() -> None:
    """A pane key may not shadow — or be shadowed by — a screen key, or the accelerator
    would be unreachable from the very tab it must work on. Reuse *across* panes is the
    point: `A` assaults on Station and deposits on Bank."""
    screen_keys = _screen_keys()
    for tab, triples in BaseScreen.PANE_BINDINGS.items():
        keys = [key for key, _a, _d in triples]
        assert len(keys) == len(set(keys)), f"{tab} binds a key twice: {keys}"
        for key in keys:
            assert key not in screen_keys, (
                f"{tab} binds {key!r}, which is already a screen-wide key")
    station = {a: k for k, a, _d in BaseScreen.PANE_BINDINGS["station"]}
    bank = {a: k for k, a, _d in BaseScreen.PANE_BINDINGS["bank"]}
    assert station["assault"] == bank["deposit"] == "a"  # the reuse, pinned


def test_tab_accelerators_are_legible_and_unique() -> None:
    accels = BaseScreen._TAB_ACCEL
    assert len(set(accels.values())) == len(accels)
    for tab, letter in accels.items():
        assert letter in _TAB_LABELS[tab].lower(), (
            f"{letter!r} is not in {_TAB_LABELS[tab]!r} — it cannot be underlined")


def test_keys_agree_with_the_other_service_screens() -> None:
    """A key means one thing across screens: the Base hosts the Stardock's TradePanel and
    sells the same components, so its trade/haggle/purchase keys must match."""
    from edge.tui.screens.stardock import StardockScreen

    base_trade = {k: a for k, a, _d in BaseScreen.PANE_BINDINGS["trade"]}
    dock_trade = {k: a for k, a, _d in StardockScreen.PANE_BINDINGS["trade"]}
    assert base_trade == dock_trade == {"t": "trade", "g": "haggle"}
    assert ("p", "buy") in {(k, a) for k, a, _d in BaseScreen.PANE_BINDINGS["hardware"]}
    assert BaseScreen._TAB_ACCEL["hardware"] == StardockScreen._TAB_ACCEL["hardware"] == "h"
    assert BaseScreen._TAB_ACCEL["bank"] == StardockScreen._TAB_ACCEL["bank"] == "b"


# --- live -------------------------------------------------------------------------


async def _at_base(app: EdgeApp, pilot: object) -> object:
    """Open the unified base view: teleport onto a base sector (no Warp — no encounters)."""
    clear_slot()
    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    svc = app.service
    assert svc is not None
    base = svc.state.starbases[min(svc.state.starbases)]
    ship = svc.state.ships[svc.state.players[1].ship_id]
    svc.state.ships[ship.id] = replace(ship, sector_id=base.sector_id)
    svc.state.players[1] = replace(svc.state.players[1], latinum=200_000)
    await pilot.press("p")  # board the base (one key for the orbit slot)  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    return svc


def _footer_keys(screen: BaseScreen) -> set[str]:
    return {key for key, binding in screen.active_bindings.items() if binding.binding.show}


async def test_footer_offers_only_the_visible_tabs_verbs() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _at_base(app, pilot)
        screen = app.screen
        assert isinstance(screen, BaseScreen)

        for tab, accel in BaseScreen._TAB_ACCEL.items():
            await pilot.press(accel)
            await pilot.pause()
            keys = _footer_keys(screen)
            assert "escape" in keys  # the one screen-wide verb, always
            # `_live_actions` is PANE_BINDINGS minus the verbs this base cannot honour.
            own = {key for key, _a, _d in screen._live_actions[tab]}
            others = {key for other, triples in BaseScreen.PANE_BINDINGS.items()
                      for key, _a, _d in triples if other != tab} - own
            assert not (others & keys), f"{tab} footer offers {others & keys} from other tabs"
            if screen._unavailable(tab):
                # The gate is the whole point: a withheld tab keeps none of its keys.
                assert not (own & keys), f"withheld {tab} still offers {own & keys}"
            else:
                assert own <= keys, f"{tab} footer is missing {own - keys}"


async def test_boarding_a_derelict_does_not_dock_or_crash() -> None:
    """Regression: `P` on a derelict base used to crash the TUI.

    A base *is* the port where it orbits, so `P` boards it and issues **no** `Dock`. The
    old path did dock, and `_market_port` rejects a dark market with an `EconomyError` that
    `_dock` never caught. Boarding also costs no turn — docking would have."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        clear_slot()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        base = next(b for b in svc.state.starbases.values()
                    if svc.starbase_view(1, b.id).standing == "derelict")
        ship = svc.state.ships[svc.state.players[1].ship_id]
        svc.state.ships[ship.id] = replace(ship, sector_id=base.sector_id)
        turns = svc.state.players[1].turns_remaining

        await pilot.press("p")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, BaseScreen)          # opened, did not crash
        assert svc.state.players[1].turns_remaining == turns  # boarding is not docking
        # Its market is dark, so Commodities withholds itself — and keeps none of its keys.
        assert screen._unavailable("trade")
        await pilot.press("c")
        await pilot.pause()
        assert not ({"t", "g"} & _footer_keys(screen))


async def test_a_base_you_hold_offers_neither_assault_nor_claim() -> None:
    """A verb the base cannot honour is not a key at all — the same rule that withholds a
    whole tab, applied per verb. You cannot assault or claim a base you already hold, so
    neither key reaches the footer (they used to sit there and answer with a notification).
    """
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        svc = await _at_base(app, pilot)
        screen = app.screen
        assert isinstance(screen, BaseScreen)

        view = screen._view()
        assert view.standing != "yours"
        # Hand the base to the player (state edit, not a Claim — the point here is the
        # *held* base's key map, not the claiming path), then reopen it.
        from edge.core.models import Ownership
        base = svc.state.starbases[view.starbase_id]  # type: ignore[attr-defined]
        svc.state.starbases[view.starbase_id] = replace(  # type: ignore[attr-defined]
            base, owner=Ownership(kind="player", ref=1))
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("p")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, BaseScreen)
        assert screen._view().standing == "yours"

        await pilot.press("s")  # → Station, where both verbs live
        await pilot.pause()
        keys = _footer_keys(screen)
        assert "a" not in keys, "a base you hold still offers Assault"
        assert "l" not in keys, "a base you hold still offers Claim"
        assert {d.key for d in screen.action_descriptors()} == keys  # menu agrees


async def test_station_is_never_withheld() -> None:
    """Station carries the Status panel, which every base owes you — a hostile base shows
    nothing else — so it is the one tab that can never be gated shut."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _at_base(app, pilot)
        screen = app.screen
        assert isinstance(screen, BaseScreen)
        assert not screen._unavailable("station")
        await pilot.press("s")
        await pilot.pause()
        panel = screen.query_one("#base-status-panel", Static)
        assert panel.border_title == "Status"
        assert "integrity" in str(panel.render())


async def test_a_withheld_tab_offers_no_verbs() -> None:
    """A fresh universe's base is not yours, so at least one service is gated shut — and
    that tab must advertise nothing (it used to inherit every screen binding)."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _at_base(app, pilot)
        screen = app.screen
        assert isinstance(screen, BaseScreen)
        withheld = [t for t in BaseScreen._TAB_ACCEL if screen._unavailable(t)]
        assert withheld, "expected a fresh base to gate at least one service shut"
        for tab in withheld:
            await pilot.press(BaseScreen._TAB_ACCEL[tab])
            await pilot.pause()
            assert _footer_keys(screen) == {"escape"}, f"{tab} is withheld but has verbs"
            assert {d.key for d in screen.action_descriptors()} == {"escape"}


async def test_back_leads_the_footer_on_every_tab() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _at_base(app, pilot)
        screen = app.screen
        assert isinstance(screen, BaseScreen)
        for tab, accel in BaseScreen._TAB_ACCEL.items():
            await pilot.press(accel)
            await pilot.pause()
            shown = [k for k, b in screen.active_bindings.items() if b.binding.show]
            assert shown[0] == "escape", f"{tab} footer leads with {shown[0]!r}"


async def test_accelerators_reach_every_tab_and_stay_off_the_footer() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _at_base(app, pilot)
        screen = app.screen
        assert isinstance(screen, BaseScreen)
        tabs = screen.query_one(TabbedContent)
        for tab, accel in BaseScreen._TAB_ACCEL.items():
            await pilot.press(accel)
            await pilot.pause()
            assert tabs.active == tab, f"{accel!r} did not reach {tab}"
        assert not (set(BaseScreen._TAB_ACCEL.values()) & _footer_keys(screen))


async def test_descriptors_match_the_footer_for_every_tab() -> None:
    """Parity guard for the `action_descriptors` override (tests/test_ui_actions.py
    delegates to this)."""
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _at_base(app, pilot)
        screen = app.screen
        assert isinstance(screen, BaseScreen)
        for tab, accel in BaseScreen._TAB_ACCEL.items():
            await pilot.press(accel)
            await pilot.pause()
            described = {d.key for d in screen.action_descriptors()}
            assert described == _footer_keys(screen), f"{tab} footer/menu disagree"
