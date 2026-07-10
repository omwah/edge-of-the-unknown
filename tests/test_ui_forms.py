"""WP-UI07 — standardized feedback, focus, and forms.

The shared `FieldPrompt` family must validate inline (no silent dismiss-on-bad-
input, typed values preserved), be completable with the keyboard alone, return
focus to the invoking widget when it closes, and fit inside an 80×24 terminal.
"""

from __future__ import annotations

from textual.widgets import Input, Static

from edge.tui.app import EdgeApp
from edge.tui.chrome import AmountPrompt, FieldPrompt, TextPrompt


def _error_text(app: EdgeApp) -> str:
    return str(app.screen.query_one("#field-error", Static).render())


async def test_amount_prompt_holds_open_on_invalid_and_keeps_value() -> None:
    app = EdgeApp()
    results: list[object] = []
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        app.push_screen(AmountPrompt("Deposit how many slips?"), results.append)
        await pilot.pause()
        assert isinstance(app.screen, AmountPrompt)
        field = app.screen.query_one("#field-input", Input)
        field.value = "0"  # integer-typed input: zero is typeable but invalid
        await pilot.press("enter")
        await pilot.pause()
        # Recoverable error: same screen, value intact, reason shown inline.
        assert isinstance(app.screen, AmountPrompt)
        assert field.value == "0"
        assert "positive" in _error_text(app)
        assert results == []
        field.value = "500"
        await pilot.press("enter")
        await pilot.pause()
        assert results == [500]
        assert not isinstance(app.screen, AmountPrompt)


async def test_text_prompt_requires_a_message_keyboard_only() -> None:
    app = EdgeApp()
    results: list[object] = []
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        app.push_screen(TextPrompt("Beacon text"), results.append)
        await pilot.pause()
        await pilot.press("enter")  # empty submit
        await pilot.pause()
        assert isinstance(app.screen, TextPrompt)
        assert _error_text(app)
        # The whole form is completable from the keyboard (input starts focused).
        await pilot.press("h", "i", "enter")
        await pilot.pause()
        assert results == ["hi"]


async def test_travel_prompt_rejects_non_numbers_inline() -> None:
    from edge.tui.screens.travel import TravelPromptScreen

    app = EdgeApp()
    results: list[object] = []
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        app.push_screen(TravelPromptScreen(), results.append)
        await pilot.pause()
        await pilot.press("enter")  # nothing typed — old code silently cancelled
        await pilot.pause()
        assert isinstance(app.screen, TravelPromptScreen)
        assert "sector number" in _error_text(app)
        await pilot.press("4", "2", "enter")
        await pilot.pause()
        assert results == [42]


async def test_corp_charter_submits_via_button_and_validates() -> None:
    from edge.tui.screens.corp import _FormCorpModal

    app = EdgeApp()
    results: list[object] = []
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        app.push_screen(_FormCorpModal(), results.append)
        await pilot.pause()
        await pilot.click("#field-submit")  # empty — must not dismiss
        await pilot.pause()
        assert isinstance(app.screen, _FormCorpModal)
        assert _error_text(app)
        app.screen.query_one("#field-input", Input).value = "Void Runners"
        await pilot.click("#field-submit")
        await pilot.pause()
        assert results == ["Void Runners"]


async def test_modal_close_returns_focus_to_invoker() -> None:
    app = EdgeApp()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        invoker = app.focused  # a main-menu button
        assert invoker is not None
        app.push_screen(FieldPrompt("Test prompt"))
        await pilot.pause()
        assert isinstance(app.focused, Input)  # the prompt grabbed focus
        await pilot.press("escape")
        await pilot.pause()
        assert app.focused is invoker


async def test_prompt_fits_and_gets_tier_class_at_80x24() -> None:
    app = EdgeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.push_screen(TextPrompt("Post a notice"))
        await pilot.pause()
        await pilot.pause()
        screen = app.screen
        assert screen.has_class("compact")  # pushed screens get the tier class
        box = screen.query_one(".modal-box")
        region = box.region
        assert region.right <= 80 and region.bottom <= 24
