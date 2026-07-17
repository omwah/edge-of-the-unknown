"""The LLM pilot console's shared Start/Stop control and Ctrl-S toggle."""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

from textual.widgets import Button, Footer

from edge.bot.llm.brain import BotRecord, InstructionMode
from edge.bot.llm.tui import LLMBotApp


class _Brain:
    """Small blocking brain double so Textual can exercise the real worker toggle."""

    def __init__(self) -> None:
        self.llm = SimpleNamespace(model="test-model")
        self.emit: Any = lambda _record: None
        self._running = threading.Event()
        self._stop = threading.Event()
        self.instructions: list[tuple[InstructionMode, str]] = []

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

    def instruct(self, text: str, *, mode: InstructionMode = "objective") -> None:
        self.instructions.append((mode, text))

    def run_single(self) -> None:
        pass


def _toggle_description(app: LLMBotApp) -> str:
    return app.active_bindings["ctrl+s"].binding.description


def _footer_text(app: LLMBotApp) -> str:
    footer = app.query_one(Footer)
    return " ".join(str(widget.render()) for widget in footer.query("FooterKey"))


def _rendered(app: LLMBotApp, selector: str) -> str:
    return str(app.query_one(selector).render())


async def test_start_stop_share_one_button_and_ctrl_s_updates_footer() -> None:
    brain = _Brain()
    app = LLMBotApp(brain)  # type: ignore[arg-type]

    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.focused is app.query_one("#chat-input")
        assert len(app.query("#controls Button")) == 1
        button = app.query_one("#run-toggle", Button)
        assert button.id == "run-toggle"
        assert str(button.label) == "▶ Start"
        assert _toggle_description(app) == "Start"
        assert "Start" in _footer_text(app)
        assert app.active_bindings["ctrl+x"].binding.action == "cut"

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


async def test_ctrl_t_switches_query_mode_with_input_focused_and_submits_query() -> None:
    brain = _Brain()
    app = LLMBotApp(brain)  # type: ignore[arg-type]

    async with app.run_test() as pilot:
        await pilot.pause()
        assert "objective" in _rendered(app, "#instruction-mode")
        assert app.active_bindings["ctrl+t"].binding.description == "Query mode"

        chat_input = app.query_one("#chat-input")
        chat_input.focus()
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert "query" in _rendered(app, "#instruction-mode")
        assert app.active_bindings["ctrl+t"].binding.description == "Objective mode"
        assert "Objective mode" in _footer_text(app)

        await pilot.press(*"what is here?", "enter")
        await pilot.pause()
        assert brain.instructions == [("query", "what is here?")]


async def test_direct_pilot_response_uses_operator_channel_not_reasoning() -> None:
    brain = _Brain()
    app = LLMBotApp(brain)  # type: ignore[arg-type]

    async with app.run_test() as pilot:
        await pilot.pause()
        reasoning = app.query_one("#reasoning")
        chat = app.query_one("#chat")
        reasoning_lines = len(reasoning.lines)  # type: ignore[attr-defined]
        chat_lines = len(chat.lines)  # type: ignore[attr-defined]

        app._on_record(BotRecord("operator", "Objective accepted."))

        assert len(reasoning.lines) == reasoning_lines  # type: ignore[attr-defined]
        assert len(chat.lines) == chat_lines + 1  # type: ignore[attr-defined]
