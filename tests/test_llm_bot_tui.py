"""The LLM pilot console's shared Start/Stop control and Ctrl-S toggle."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

from textual.widgets import Button, Footer

from edge.bot.llm.brain import BotRecord
from edge.bot.llm.tui import LLMBotApp


class _Brain:
    """Small blocking brain double so Textual can exercise the real worker toggle."""

    def __init__(self) -> None:
        self.llm = SimpleNamespace(model="test-model")
        self.emit: Any = lambda _record: None
        self._running = threading.Event()
        self._stop = threading.Event()

    @property
    def running(self) -> bool:
        return self._running.is_set()

    def run(self) -> None:
        self._stop.clear()
        self._running.set()
        self._stop.wait(timeout=2)
        self._running.clear()
        self.emit(BotRecord("status", "pilot stopped"))

    def request_stop(self) -> None:
        self._stop.set()

    def instruct(self, _text: str) -> None:
        pass

    def run_single(self) -> None:
        pass


def _toggle_description(app: LLMBotApp) -> str:
    return app.active_bindings["ctrl+s"].binding.description


def _footer_text(app: LLMBotApp) -> str:
    footer = app.query_one(Footer)
    return " ".join(str(widget.render()) for widget in footer.query("FooterKey"))


async def test_start_stop_share_one_button_and_ctrl_s_updates_footer() -> None:
    brain = _Brain()
    app = LLMBotApp(brain)  # type: ignore[arg-type]

    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.query("#controls Button")) == 1
        button = app.query_one("#run-toggle", Button)
        assert button.id == "run-toggle"
        assert str(button.label) == "▶ Start"
        assert _toggle_description(app) == "Start"
        assert "Start" in _footer_text(app)
        assert "ctrl+x" not in app.active_bindings

        await pilot.press("ctrl+s")
        await pilot.pause()
        assert brain.running
        assert str(app.query_one("#run-toggle", Button).label) == "■ Stop"
        assert _toggle_description(app) == "Stop"
        assert "Stop" in _footer_text(app)

        await pilot.press("ctrl+s")
        await pilot.pause()
        assert not brain.running
        assert str(app.query_one("#run-toggle", Button).label) == "▶ Start"
        assert _toggle_description(app) == "Start"
        assert "Start" in _footer_text(app)
