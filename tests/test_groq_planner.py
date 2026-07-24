"""Tests for GroqPlanner.

These never call a real Groq API: a fake client is injected via the
constructor, mirroring the pattern used for AnthropicPlanner/GeminiPlanner.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from geniac_cap.evaluation.evaluator import run_single_task
from geniac_cap.exceptions import PlanningError
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.planners.base import PlanningContext
from geniac_cap.planners.groq_planner import GroqPlanner
from geniac_cap.tasks.loader import get_task_by_id


@dataclass
class _FakeMessage:
    content: str


@dataclass
class _FakeChoice:
    message: _FakeMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice] = field(default_factory=list)


class _FakeCompletions:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.last_call_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        message = _FakeMessage(content=self._response_text)
        return _FakeResponse(choices=[_FakeChoice(message=message)])


class _FakeChat:
    def __init__(self, response_text: str) -> None:
        self.completions = _FakeCompletions(response_text)


class _FakeClient:
    def __init__(self, response_text: str) -> None:
        self.chat = _FakeChat(response_text)


class _SequentialCompletions:
    def __init__(self, response_texts: list[str]) -> None:
        self._responses = list(response_texts)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        text = self._responses[min(len(self.calls) - 1, len(self._responses) - 1)]
        return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content=text))])


class _SequentialFakeClient:
    def __init__(self, response_texts: list[str]) -> None:
        self.chat = type("Chat", (), {})()
        self.chat.completions = _SequentialCompletions(response_texts)


def _context() -> PlanningContext:
    return PlanningContext(
        objects=["cup"],
        locations=["table", "tray"],
        object_locations={"cup": "table"},
        robot_location="table",
    )


_VALID_PLAN_ARRAY = [
    {"action": "move_to", "args": {"location": "table"}},
    {"action": "pick", "args": {"object_name": "cup"}},
    {"action": "move_to", "args": {"location": "tray"}},
    {"action": "place", "args": {"target_location": "tray"}},
]


def test_groq_planner_raises_without_api_key_or_client():
    planner = GroqPlanner(api_key="")
    with pytest.raises(PlanningError):
        planner.plan("Move the cup to the tray", _context())


def test_groq_planner_parses_bare_array_response():
    plan_json = json.dumps(_VALID_PLAN_ARRAY)
    planner = GroqPlanner(client=_FakeClient(plan_json))
    plan = planner.plan("Move the cup to the tray", _context())
    assert len(plan) == 4
    assert plan.steps[1].args["object_name"] == "cup"


def test_groq_planner_parses_wrapped_actions_object():
    # Groq's response_format=json_object requires a top-level object; the
    # model may (correctly, per our prompt instruction) wrap the array.
    plan_json = json.dumps({"actions": _VALID_PLAN_ARRAY})
    planner = GroqPlanner(client=_FakeClient(plan_json))
    plan = planner.plan("Move the cup to the tray", _context())
    assert len(plan) == 4


def test_groq_planner_strips_markdown_code_fences():
    fenced = f"```json\n{json.dumps(_VALID_PLAN_ARRAY)}\n```"
    planner = GroqPlanner(client=_FakeClient(fenced))
    plan = planner.plan("Move the cup to the tray", _context())
    assert len(plan) == 4


def test_groq_planner_raises_on_invalid_json():
    planner = GroqPlanner(client=_FakeClient("not json"))
    with pytest.raises(PlanningError):
        planner.plan("Move the cup to the tray", _context())


def test_groq_planner_works_end_to_end_via_run_single_task():
    plan_json = json.dumps(
        [
            {"action": "move_to", "args": {"location": "table"}},
            {"action": "pick", "args": {"object_name": "red_block"}},
            {"action": "move_to", "args": {"location": "blue_shelf"}},
            {"action": "place", "args": {"target_location": "blue_shelf"}},
        ]
    )
    task = get_task_by_id("task_001")
    planner = GroqPlanner(client=_FakeClient(plan_json))
    outcome = run_single_task(task, planner, SafeExecutor(), allow_feedback=False)
    assert outcome.success is True
    assert outcome.planner_name == "groq"


def test_groq_planner_supports_feedback_and_replans_on_failure():
    broken_plan = json.dumps(
        [
            {"action": "pick", "args": {"object_name": "red_block"}},
            {"action": "place", "args": {"target_location": "blue_shelf"}},
        ]
    )
    fixed_plan = json.dumps(
        [
            {"action": "move_to", "args": {"location": "table"}},
            {"action": "pick", "args": {"object_name": "red_block"}},
            {"action": "move_to", "args": {"location": "blue_shelf"}},
            {"action": "place", "args": {"target_location": "blue_shelf"}},
        ]
    )
    task = get_task_by_id("task_001")
    planner = GroqPlanner(client=_SequentialFakeClient([broken_plan, fixed_plan]))

    assert planner.supports_feedback is True

    outcome = run_single_task(task, planner, SafeExecutor(), allow_feedback=True)

    assert outcome.success is True
    assert outcome.replanned is True
    assert len(planner._client.chat.completions.calls) == 2


def test_groq_planner_uses_custom_system_prompt_when_given():
    plan_json = json.dumps(_VALID_PLAN_ARRAY)
    fake_client = _FakeClient(plan_json)
    planner = GroqPlanner(client=fake_client, system_prompt="CUSTOM PROMPT")
    planner.plan("Move the cup to the tray", _context())
    sent_system = fake_client.chat.completions.last_call_kwargs["messages"][0]["content"]
    assert "CUSTOM PROMPT" in sent_system
