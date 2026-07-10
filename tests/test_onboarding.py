"""WP-UI11 — menu hierarchy, save metadata, and Captain's objectives.

Objectives progress is local presentation state only: it lives in the UI
settings JSON, never in universe state or the command log, so marking one must
not disturb replay determinism (the flow below plays on the live service and
only ever asserts UI-side effects).
"""

from __future__ import annotations

from textual.widgets import Button, Static

from edge.tui.app import EdgeApp
from edge.tui.onboarding import OBJECTIVE_IDS, ObjectivesStrip, all_done, next_hint
from edge.tui.saves import save_summary
from edge.tui.settings import load_settings


def test_objective_vocabulary_and_helpers() -> None:
    assert OBJECTIVE_IDS == ("dock", "trade", "inspect", "scan", "discover")
    assert not all_done(("dock",))
    assert all_done(OBJECTIVE_IDS)
    assert next_hint(()) .startswith("press P")
    assert next_hint(("dock",)) != next_hint(())
    assert next_hint(OBJECTIVE_IDS) == ""


def test_save_summary_absent_without_save() -> None:
    assert save_summary() is None


async def test_objectives_mark_dismiss_and_persist() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.press("n")  # new game (starts at the StarDock sector)
        await pilot.pause()
        assert app.screen.query(ObjectivesStrip), "fresh game shows the objectives strip"
        assert app.ui_settings.objectives_done == ()
        await pilot.press("p")  # dock
        await pilot.pause()
        assert "dock" in app.ui_settings.objectives_done
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("e")  # engine room
        await pilot.pause()
        assert "inspect" in app.ui_settings.objectives_done
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("z")  # scan teaches the key even with nothing in range
        await pilot.pause()
        assert "scan" in app.ui_settings.objectives_done
        # Progress persisted to the settings JSON (survives a fresh load).
        persisted, warning = load_settings()
        assert warning is None
        assert set(persisted.objectives_done) == {"dock", "inspect", "scan"}
        # O dismisses the strip and persists the preference.
        await pilot.press("o")
        await pilot.pause()
        assert not app.screen.query(ObjectivesStrip)
        assert app.ui_settings.show_onboarding is False
        assert load_settings()[0].show_onboarding is False


async def test_menu_with_save_leads_with_continue_and_metadata() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:  # create the save slot
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
    summary = save_summary()
    assert summary is not None
    assert summary.commands >= 0 and summary.day_number >= 1
    # The current day is creation day + logged dawns (meta.day_number is never
    # rewritten — regression: the menu used to show day 1 forever).
    from edge.store.repo import SqliteRepository
    from edge.tui.saves import default_save
    repo = SqliteRepository(default_save())
    repo.append_maintenance("daily_turn_reset", tick=24, after_command_seq=0)
    repo.append_maintenance("daily_turn_reset", tick=48, after_command_seq=0)
    repo.close()
    after_dawns = save_summary()
    assert after_dawns is not None
    assert after_dawns.day_number == summary.day_number + 2
    app2 = EdgeApp()
    async with app2.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        buttons = list(app2.screen.query(Button))
        assert buttons[0].id == "continue" and buttons[0].variant == "primary"
        assert buttons[1].id == "new" and buttons[1].variant == "default"
        assert app2.focused is buttons[0]
        card = app2.screen.query(".save-card")
        assert card and f"seed {summary.seed}" in str(card.first().render())
        # Arrow keys walk the buttons (visual reading order).
        await pilot.press("down")
        assert app2.focused is buttons[1]
        await pilot.press("up")
        assert app2.focused is buttons[0]
