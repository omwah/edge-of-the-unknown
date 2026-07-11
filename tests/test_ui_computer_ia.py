"""WP-UI20 — the Computer's five-category information architecture.

Every legacy tab maps to exactly one category subview; direct hotkeys and
links open the correct subview; each category remembers its last subview
(app-level, so [C] reopens where the player left off); and at 80×24 the
category tab bar yields to a popup selector with no clipped labels.
"""

from __future__ import annotations

from textual.widgets import Button, Tab, TabbedContent

from edge.tui.app import EdgeApp
from edge.tui.screens.computer import CATEGORIES, SUBVIEW_LABELS, ComputerScreen

_LEGACY_TABS = {"map", "ports", "planets", "trade", "market", "log", "route",
                "codex", "leads", "contracts", "alliances", "dossier", "notes"}


def test_every_old_tab_maps_to_exactly_one_subview() -> None:
    placed = [sub for subs in CATEGORIES.values() for sub in subs]
    assert sorted(placed) == sorted(_LEGACY_TABS)  # all present, none twice
    assert set(SUBVIEW_LABELS) == _LEGACY_TABS


async def _open_computer(app: EdgeApp, pilot: object, key: str = "c") -> ComputerScreen:
    await pilot.press("n")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.press(key)  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    screen = app.screen
    assert isinstance(screen, ComputerScreen)
    return screen


async def test_direct_hotkeys_open_the_expected_subview() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot, key="m")  # galactic map
        assert screen._active_subview() == "map"
        assert screen._active_category() == "navigation"
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("g")  # event log
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ComputerScreen)
        assert screen._active_subview() == "log"
        assert screen._active_category() == "records"


async def test_each_category_remembers_its_last_subview() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        # Visit non-default subviews in two categories.
        screen.show_subview("market")
        await pilot.pause()
        screen.show_subview("codex")
        await pilot.pause()
        # Returning to Commerce lands on Market, not the category's first subview.
        screen.query_one("#cats", TabbedContent).active = "cat-commerce"
        await pilot.pause()
        assert screen._active_subview() == "market"
        # The memory is app-level: reopening the Computer restores it too.
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("c")  # reopens on the last subview (market)
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, ComputerScreen)
        assert screen._active_subview() == "market"
        screen.query_one("#cats", TabbedContent).active = "cat-exploration"
        await pilot.pause()
        assert screen._active_subview() == "codex"  # remembered across screens


async def test_plotting_a_route_opens_navigation_route() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        await pilot.press("r")  # Route to… prompt
        await pilot.pause()
        from textual.widgets import Input
        svc = app.service
        assert svc is not None
        here = svc.game_view(1).sector.sector_id
        dest = next(iter(svc.state.sectors[here].warps_out))
        app.screen.query_one("#field-input", Input).value = str(svc.state.spatial_ids[dest])
        await pilot.press("enter")
        await pilot.pause()
        assert screen._active_subview() == "route"
        assert screen._active_category() == "navigation"


async def test_compact_uses_popup_selector_and_no_clipped_labels() -> None:
    app = EdgeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        assert screen.has_class("compact")
        # The category tab bar yields to the popup selector button…
        button = screen.query_one("#cat-button", Button)
        assert button.display and button.region.width > 0
        cats_tabs = screen.query_one("#cats > ContentTabs")
        assert not cats_tabs.display
        # …and the visible subview tabs all fit inside the 80-column screen.
        active_sub = screen.query_one(f"#sub-{screen._active_category()}", TabbedContent)
        for tab in active_sub.query(Tab):
            assert tab.region.right <= 80
        # The popup drives category switching (mouse path).
        await pilot.click("#cat-button")
        await pilot.pause()
        from edge.tui.screens.picker import ListPicker
        assert isinstance(app.screen, ListPicker)
        await pilot.press("down", "down", "enter")  # → third category (exploration)
        await pilot.pause()
        assert screen._active_category() == "exploration"
        assert "Exploration" in str(screen.query_one("#cat-button", Button).label)


async def test_standard_shows_category_tabs_with_subview_row() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        screen = await _open_computer(app, pilot)
        assert not screen.query_one("#cat-strip").display  # popup is compact-only
        cats_tabs = screen.query_one("#cats > ContentTabs")
        assert cats_tabs.display
        for tab in cats_tabs.query(Tab):  # five category labels, none clipped
            assert tab.region.right <= 100
