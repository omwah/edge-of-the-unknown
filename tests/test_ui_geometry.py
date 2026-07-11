"""WP-UI22 geometry guards for compact player-facing screens."""

from __future__ import annotations

from textual.widget import Widget

from edge.tui.app import EdgeApp
from edge.tui.screens.computer import ComputerScreen
from edge.tui.screens.game import GameScreen
from edge.tui.screens.lobby import LobbyScreen


def _has_scrollable_ancestor(widget: Widget) -> bool:
    parent = widget.parent
    while isinstance(parent, Widget):
        if parent.is_scrollable:
            return True
        parent = parent.parent
    return False


def _assert_controls_reachable(app: EdgeApp) -> None:
    screen_region = app.screen.region
    for widget in app.screen.query("*"):
        if not widget.can_focus or not widget.display or widget.disabled:
            continue
        visible = widget.region.intersection(screen_region)
        assert visible or _has_scrollable_ancestor(widget), (
            f"{type(app.screen).__name__} control {widget.id or type(widget).__name__} "
            "is outside the viewport and has no keyboard-scrollable ancestor"
        )


async def test_compact_live_screen_controls_are_visible_or_scrollable() -> None:
    app = EdgeApp(plain=True)
    async with app.run_test(size=(80, 24)) as pilot:
        service = app.start_new_game(seed=1986)
        for screen in (
            GameScreen(service, app.player_id),
            ComputerScreen(service, app.player_id, initial_tab="ports"),
            LobbyScreen("ws://host.example:8765"),
        ):
            app.push_screen(screen)
            await pilot.pause()
            await pilot.pause()
            _assert_controls_reachable(app)
            app.pop_screen()
            await pilot.pause()
