"""WP-UI19 — territory, corporations, lobby, and minor-screen consistency.

Territory cards follow the layout tier (1/2/3 columns); the corp screen's
empty / member / CEO states expose clear primary actions and explain CEO-gated
verbs; the lobby carries persistent field labels, staged progress, inline
errors, and never loses typed values on a failed attempt; the shared ListPicker
rides the tier-scoped `.modal-box`; and empty tavern / market / contract /
diplomacy views use the shared `EmptyState`.
"""

from __future__ import annotations

from textual.widgets import Button, Input, Label, Static

from edge.tui.app import EdgeApp
from edge.tui.chrome import EmptyState


# --- Territory: responsive card grid ----------------------------------------

async def _open_territory(app: EdgeApp, pilot: object) -> None:
    from dataclasses import replace as _replace

    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    svc = app.service
    assert svc is not None
    ship = svc.state.ships[svc.state.players[1].ship_id]
    outside = next(s.id for s in svc.state.sectors.values() if not s.is_galactic_core)
    svc.state.ships[ship.id] = _replace(ship, sector_id=outside, fighters=40)
    await pilot.press("d")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


def _card_columns(app: EdgeApp) -> int:
    from edge.tui.screens.territory import _DeployCard

    cards = list(app.screen.query(_DeployCard))
    assert cards
    return len({c.region.x for c in cards})


async def test_territory_grid_is_one_column_compact() -> None:
    app = EdgeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await _open_territory(app, pilot)
        assert app.screen.has_class("compact")
        assert _card_columns(app) == 1


async def test_territory_grid_is_two_columns_standard() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await _open_territory(app, pilot)
        assert app.screen.has_class("standard")
        assert _card_columns(app) == 2


async def test_territory_grid_is_three_columns_wide() -> None:
    app = EdgeApp()
    async with app.run_test(size=(126, 44)) as pilot:
        await pilot.pause()
        await _open_territory(app, pilot)
        assert app.screen.has_class("wide")
        assert _card_columns(app) == 3


# --- Corporation states -------------------------------------------------------

async def test_corp_empty_state_offers_charter_as_primary() -> None:
    from edge.tui.screens.corp import CorpScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("t")  # corpless → the empty state
        await pilot.pause()
        assert isinstance(app.screen, CorpScreen)
        assert app.screen.query(EmptyState)  # what's missing and what fills it
        charter = app.screen.query_one("#btn-form", Button)
        assert charter.variant == "primary" and not charter.disabled


async def test_corp_ceo_state_enables_gated_verbs_with_invite_primary() -> None:
    from dataclasses import replace as _replace

    from edge.core.rules import FormCorp
    from edge.tui.screens.corp import CorpScreen

    app = EdgeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        svc.state.players[1] = _replace(svc.state.players[1], latinum=50_000)
        svc.apply(1, FormCorp(name="Void Runners", tag="VR"))
        await pilot.press("t")
        await pilot.pause()
        assert isinstance(app.screen, CorpScreen)
        invite = app.screen.query_one("#btn-invite", Button)
        assert invite.variant == "primary" and not invite.disabled
        for bid in ("btn-expel", "btn-withdraw", "btn-world-from"):
            assert not app.screen.query_one(f"#{bid}", Button).disabled
        # No rival corps chartered → war verbs are disabled with the reason.
        war = app.screen.query_one("#btn-war", Button)
        assert war.disabled and war.tooltip
        assert app.screen.query(EmptyState)  # empty diplomacy table


def test_corp_member_sees_ceo_verbs_disabled_with_reason() -> None:
    from edge.tui.screens.corp import _ceo_button

    locked = _ceo_button("Invite…", "btn-invite", is_ceo=False)
    assert locked.disabled
    assert "CEO" in str(locked.tooltip)
    open_verb = _ceo_button("Invite…", "btn-invite", is_ceo=True, variant="primary")
    assert not open_verb.disabled and open_verb.tooltip is None


# --- Lobby: labels, staged progress, inline errors, no data loss ---------------

async def test_lobby_validates_inline_and_keeps_typed_values() -> None:
    from edge.tui.screens.lobby import LobbyScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        app.push_screen(LobbyScreen("ws://example.invalid:1"))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, LobbyScreen)
        labels = " ".join(str(lab.render()) for lab in screen.query(Label))
        assert "Username" in labels and "Password" in labels and "Game" in labels
        await pilot.click("#login")  # nothing typed
        await pilot.pause()
        status = screen.query_one("#status", Static)
        assert "username required" in str(status.render())
        assert status.has_class("error")
        assert app.focused is screen.query_one("#user", Input)
        screen.query_one("#user", Input).value = "kirk"
        await pilot.click("#login")
        await pilot.pause()
        assert "password required" in str(status.render())
        assert screen.query_one("#user", Input).value == "kirk"  # value preserved


async def test_lobby_connection_failure_names_the_stage_and_preserves_form(
        monkeypatch: object) -> None:
    from edge.server.client import RemoteError
    from edge.tui.screens import lobby as lobby_mod
    from edge.tui.screens.lobby import LobbyScreen

    class _DeadBridge:
        def __init__(self, url: str) -> None:
            self.url = url

        def connect(self) -> None:
            raise RemoteError(-1, "connection refused")

        def close(self) -> None:  # the app tears the bridge down on unmount
            pass

    monkeypatch.setattr(lobby_mod, "RemoteBridge", _DeadBridge)  # type: ignore[attr-defined]
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        app.push_screen(LobbyScreen("ws://example.invalid:1"))
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, LobbyScreen)
        screen.query_one("#user", Input).value = "kirk"
        screen.query_one("#pass", Input).value = "hunter2"
        screen.query_one("#game", Input).value = "alpha"
        await pilot.click("#login")
        await pilot.pause()
        status = str(screen.query_one("#status", Static).render())
        assert "failed while connecting" in status and "connection refused" in status
        # Recoverable remote error: the form is intact and editable in place.
        assert screen.query_one("#user", Input).value == "kirk"
        assert screen.query_one("#pass", Input).value == "hunter2"
        for button in screen.query(Button):
            assert not button.disabled  # retry is live again


# --- Shared modal + empty states -----------------------------------------------

async def test_list_picker_uses_shared_modal_box_and_fits_80x24() -> None:
    from edge.tui.screens.picker import ListPicker

    app = EdgeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.push_screen(ListPicker("Pick one", [("Alpha", "a"), ("Beta", "b")]))
        await pilot.pause()
        await pilot.pause()
        box = app.screen.query_one("#picker-box")
        assert box.has_class("modal-box")
        region = box.region
        assert region.right <= 80 and region.bottom <= 24


async def test_computer_market_and_contracts_use_shared_empty_states() -> None:
    from edge.tui.screens.computer import ComputerScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        assert isinstance(app.screen, ComputerScreen)
        # A fresh game has no accepted favors: the table hides, the state explains.
        assert app.screen.query_one("#contracts").query(EmptyState)
        from textual.widgets import DataTable
        assert not app.screen.query_one("#contracts-table", DataTable).display
        market_pane = app.screen.query_one("#market")
        market_table = app.screen.query_one("#market-table", DataTable)
        assert market_table.display or market_pane.query(EmptyState)


async def test_tavern_empty_board_and_noticeboard_use_empty_states() -> None:
    from edge.core.movement import shortest_path
    from edge.core.rules import Warp
    from edge.tui.screens.stardock import StarDockScreen

    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        svc = app.service
        assert svc is not None
        dock = next(p for p in svc.state.ports.values() if p.klass.value == 9)
        start = svc.game_view(1).sector.sector_id
        path = shortest_path(svc.state.adjacency, start, dock.sector_id)
        assert path is not None
        for hop in path[1:]:
            svc.apply(1, Warp(to_sector=hop))
        await pilot.press("p")
        await pilot.pause()
        assert isinstance(app.screen, StarDockScreen)
        tav = svc.tavern_view(1)
        empties = list(app.screen.query(EmptyState))
        expected = (0 if tav.bounties else 1) + (0 if tav.notices else 1)
        assert len(empties) >= expected and expected >= 1  # fresh game: quiet board
