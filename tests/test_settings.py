"""WP-UI04 — local presentation settings recovery and startup safety."""

from __future__ import annotations

from edge.tui.app import EdgeApp
from edge.tui.screens.main_menu import MainMenuScreen
from edge.tui.settings import UISettings, load_settings, settings_path


async def test_corrupt_preferences_reset_once_without_blocking_startup(monkeypatch) -> None:
    """Garbage JSON yields defaults + one warning, and the first screen still mounts."""
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ definitely not valid JSON", encoding="utf-8")

    settings, warning = load_settings()
    assert settings == UISettings()
    assert warning is not None and warning.startswith("UI settings were reset:")

    warnings: list[str] = []
    monkeypatch.setattr("edge.tui.app.notify_warning", lambda _host, message: warnings.append(message))
    app = EdgeApp()
    assert app.ui_settings == UISettings()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        await pilot.pause()  # allow the call-after-refresh warning to run
        assert isinstance(app.screen, MainMenuScreen)
        assert warnings == [app._settings_warning]
