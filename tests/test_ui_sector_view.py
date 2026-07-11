"""WP-UI12 — responsive sector view.

Compact replaces the art scene with a location header + focusable object list
and drops the sidebar (the `I` status drawer stands in); standard keeps the
grouped sidebar; wide adds the objectives checklist. Every scene click hotspot
has a keyboard/list equivalent: object rows post the identical
`ClickableEntry.Picked` routing, exercised end-to-end below by docking at the
StarDock from the drawer with Enter alone.
"""

from __future__ import annotations

from edge.tui.app import EdgeApp
from edge.tui.screens.game import GameScreen
from edge.tui.screens.stardock import StarDockScreen
from edge.tui.screens.status_drawer import StatusDrawerScreen
from edge.tui.widgets import ObjectRow, SectorObjectList, SectorScene, StatusSidebar


async def test_compact_tier_lists_objects_instead_of_art() -> None:
    app = EdgeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press("n")  # new game — starts at the StarDock sector
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        # Art and sidebar give way to gameplay information (plan contract).
        assert not app.screen.query(SectorScene)
        assert not app.screen.query(StatusSidebar)
        rows = list(app.screen.query(ObjectRow))
        assert rows, "the object list carries the sector's interactables"
        # Location is retained in the compact header.
        header = str(app.screen.query_one("#compact-header").render())
        assert header.startswith("[") and "(Hub)" in header  # "[id] Region (Band)"
        # Enter on the dock row is the hotspot's keyboard equivalent.
        port_row = next(r for r in rows if "Dock" in str(r.render()))
        port_row.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, StarDockScreen)


async def test_status_drawer_opens_and_routes_a_pick() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        # Standard tier keeps art + sidebar.
        assert app.screen.query(SectorScene)
        assert app.screen.query(StatusSidebar)
        await pilot.press("i")
        await pilot.pause()
        assert isinstance(app.screen, StatusDrawerScreen)
        # Drawer carries the sidebar readout and the focusable object list; focus
        # lands on the first object row so Enter works immediately.
        assert app.screen.query(StatusSidebar)
        assert app.screen.query(SectorObjectList)
        assert isinstance(app.focused, ObjectRow)
        # Esc (or I again) closes without acting.
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, GameScreen)
        # Reopen, pick the dock row with Enter: the drawer dismisses and the
        # GameScreen routes it through its one shared Picked handler.
        await pilot.press("i")
        await pilot.pause()
        row = next(r for r in app.screen.query(ObjectRow) if "Dock" in str(r.render()))
        row.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, StarDockScreen)


async def test_status_drawer_up_down_walks_object_rows() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        await pilot.press("i")
        await pilot.pause()
        rows = list(app.screen.query(ObjectRow))
        assert len(rows) >= 2
        assert app.focused is rows[0]
        await pilot.press("down")
        assert app.focused is rows[1]
        await pilot.press("up")
        assert app.focused is rows[0]


async def test_resize_across_breakpoint_recomposes() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert app.screen.query(SectorScene)
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        await pilot.pause()
        assert not app.screen.query(SectorScene)
        assert app.screen.query(SectorObjectList)
        await pilot.resize_terminal(100, 34)
        await pilot.pause()
        await pilot.pause()
        assert app.screen.query(SectorScene)
        assert app.screen.query(StatusSidebar)


async def test_wide_sidebar_adds_objectives_checklist() -> None:
    app = EdgeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        texts = [str(s.render()) for s in app.screen.query("#sidebar Static")]
        assert any("Objectives" in t for t in texts)
        assert any("Dock" in t for t in texts)  # the checklist's first open item


async def test_objective_visibility_is_one_setting_for_strip_and_sidebar() -> None:
    app = EdgeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert app.screen.query("#objectives")
        assert any("Objectives" in str(s.render())
                   for s in app.screen.query("#sidebar Static"))

        app.update_ui_settings(show_onboarding=False)
        await app.screen.recompose()
        await pilot.pause()
        assert not app.screen.query("#objectives")
        assert not any("Objectives" in str(s.render())
                       for s in app.screen.query("#sidebar Static"))

        done = app.ui_settings.objectives_done
        app.update_ui_settings(show_onboarding=True)
        await app.screen.recompose()
        await pilot.pause()
        assert app.ui_settings.objectives_done == done
        assert app.screen.query("#objectives")
        assert any("Objectives" in str(s.render())
                   for s in app.screen.query("#sidebar Static"))
