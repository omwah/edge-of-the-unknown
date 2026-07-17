"""Objective and answer-only query behavior in the LLM pilot brain."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from edge.bot.llm import brain as brain_module
from edge.bot.llm.actions import DECISION_SCHEMA
from edge.bot.llm.brain import BotRecord, Brain, QUERY_SCHEMA


class _Service:
    def encounter_view(self, _player_id: int) -> None:
        return None


class _Bot:
    def __init__(self) -> None:
        self.service = _Service()
        self.player_id = 1
        self.game_reads = 0

    def game(self) -> Any:
        self.game_reads += 1
        return SimpleNamespace(turns=100)

    def current_starbase(self) -> None:
        return None


class _LLM:
    model = "test-model"
    host = "test-host"

    def __init__(self, *responses: dict[str, Any]) -> None:
        self.responses = list(responses)
        self.schemas: list[dict[str, Any]] = []

    def chat(self, _messages: list[dict[str, str]], *, schema: dict[str, Any]) -> dict[str, Any]:
        self.schemas.append(schema)
        return self.responses.pop(0)


def _decision(*, action: str, operator_response: str) -> dict[str, Any]:
    return {
        "reasoning": "Holding course.",
        "operator_response": operator_response,
        "action": action,
        "sector": 0,
        "commodity": "",
        "units": 0,
        "planet_id": 0,
        "species_id": 0,
        "discovery_id": 0,
        "starbase_id": 0,
        "offer_index": -1,
        "subsystem": "",
        "slot_index": -1,
        "count": 0,
    }


@pytest.fixture(autouse=True)
def _simple_observation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(brain_module, "observe", lambda _bot, **_kwargs: "OBSERVATION")
    monkeypatch.setattr(brain_module, "sidebar", lambda _bot: "SIDEBAR")


def test_query_answers_without_action_or_turn_budget() -> None:
    bot = _Bot()
    llm = _LLM({"response": "There is a port in this sector."})
    records: list[BotRecord] = []
    brain = Brain(bot, llm, emit=records.append)  # type: ignore[arg-type]

    brain.instruct("What is here?", mode="query")
    assert brain._cycle() is False

    assert llm.schemas == [QUERY_SCHEMA]
    assert brain.actions_taken == 0
    assert bot.game_reads == 0
    assert [(record.kind, record.text) for record in records] == [
        ("operator", "There is a port in this sector."),
    ]


def test_objective_prompt_requires_computer_coordinate_check() -> None:
    brain = Brain(_Bot(), _LLM(), emit=lambda _record: None)  # type: ignore[arg-type]
    brain._objective = "Return to Stardock."

    messages = brain._messages("== SHIP'S COMPUTER ==\nStardock location: sector 3")

    assert "Before plotting movement for an objective" in messages[0]["content"]
    assert "exact displayed sector with `travel_to`" in messages[0]["content"]
    assert "Check SHIP'S COMPUTER for this objective's sector" in messages[-1]["content"]


def test_live_pace_adjustment_clamps_at_zero() -> None:
    brain = Brain(_Bot(), _LLM(), pace=0.5, emit=lambda _record: None)  # type: ignore[arg-type]

    assert brain.adjust_pace(-1.0) == 0.0
    assert brain.adjust_pace(1.0) == 1.0


def test_query_does_not_replace_or_suppress_a_queued_objective() -> None:
    llm = _LLM(
        {"response": "The neighboring sector remains uncharted."},
        _decision(action="wait", operator_response="Objective accepted."),
    )
    records: list[BotRecord] = []
    brain = Brain(_Bot(), llm, emit=records.append)  # type: ignore[arg-type]
    brain.instruct("Chart the neighboring sector.", mode="objective")
    brain.instruct("Is it already charted?", mode="query")

    assert brain._cycle() is False  # answer-only query cycle
    assert brain.actions_taken == 0
    assert brain._objective == "Chart the neighboring sector."
    assert brain._cycle() is False  # objective acknowledgment + first action

    assert [record.text for record in records if record.kind == "operator"] == [
        "The neighboring sector remains uncharted.",
        "Objective accepted.",
    ]


def test_objective_acknowledgment_and_completion_are_direct_operator_messages() -> None:
    llm = _LLM(
        _decision(action="wait", operator_response="Objective accepted. Plotting a course."),
        _decision(action="objective_done", operator_response="Objective complete. Sector charted."),
    )
    records: list[BotRecord] = []
    brain = Brain(_Bot(), llm, emit=records.append)  # type: ignore[arg-type]

    brain.instruct("Chart the neighboring sector.", mode="objective")
    assert brain._cycle() is False
    assert brain._objective == "Chart the neighboring sector."
    assert brain._cycle() is False
    assert brain._objective is None

    operator_messages = [record.text for record in records if record.kind == "operator"]
    assert operator_messages == [
        "Objective accepted. Plotting a course.",
        "Objective complete. Sector charted.",
    ]
    assert llm.schemas == [DECISION_SCHEMA, DECISION_SCHEMA]


def test_objective_completion_has_a_fallback_operator_message() -> None:
    llm = _LLM(_decision(action="objective_done", operator_response=""))
    records: list[BotRecord] = []
    brain = Brain(_Bot(), llm, emit=records.append)  # type: ignore[arg-type]
    brain._objective = "Hold position."

    assert brain._cycle() is False

    assert any(record.kind == "operator" and record.text == "Objective complete: Hold position."
               for record in records)
