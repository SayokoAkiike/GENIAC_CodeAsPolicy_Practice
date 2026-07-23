"""Tests for GeminiPlanner.

These tests never call the real Gemini API: a fake client is injected via
the constructor, so the tests exercise only the prompt-building and
JSON-parsing/validation logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from geniac_cap.evaluation.evaluator import run_single_task
from geniac_cap.exceptions import PlanningError
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.planners.base import PlanningContext
from geniac_cap.planners.gemini_planner import GeminiPlanner
from geniac_cap.tasks.loader import get_task_by_id


@dataclass
class _FakeResponse:
    text: str


class _FakeModels:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.last_call_kwargs: dict | None = None

    def generate_content(self, **kwargs):
        self.last_call_kwargs = kwargs
        return _FakeResponse(text=self._response_text)


class _FakeClient:
    def __init__(self, response_text: str) -> None:
        self.models = _FakeModels(response_text)


class _SequentialFakeModels:
    """Returns a different canned response on each successive call."""

    def __init__(self, response_texts: list[str]) -> None:
        self._responses = list(response_texts)
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        text = self._responses[min(len(self.calls) - 1, len(self._responses) - 1)]
        return _FakeResponse(text=text)


class _SequentialFakeClient:
    def __init__(self, response_texts: list[str]) -> None:
        self.models = _SequentialFakeModels(response_texts)


def _context() -> PlanningContext:
    return PlanningContext(
        objects=["cup"],
        locations=["table", "tray"],
        object_locations={"cup": "table"},
        robot_location="table",
    )


def test_gemini_planner_raises_without_api_key_or_client():
    planner = GeminiPlanner(api_key="")  # force "no key" regardless of environment
    with pytest.raises(PlanningError):
        planner.plan("Move the cup to the tray", _context())


def test_gemini_planner_parses_valid_json_response():
    plan_json = json.dumps(
        [
            {"action": "move_to", "args": {"location": "table"}},
            {"action": "pick", "args": {"object_name": "cup"}},
            {"action": "move_to", "args": {"location": "tray"}},
            {"action": "place", "args": {"target_location": "tray"}},
        ]
    )
    planner = GeminiPlanner(client=_FakeClient(plan_json))
    plan = planner.plan("Move the cup to the tray", _context())

    assert len(plan) == 4
    assert plan.steps[1].args["object_name"] == "cup"
    assert plan.steps[-1].args["target_location"] == "tray"


def test_gemini_planner_strips_markdown_code_fences():
    plan_json = json.dumps([{"action": "wait", "args": {}}])
    fenced = f"```json\n{plan_json}\n```"
    planner = GeminiPlanner(client=_FakeClient(fenced))
    plan = planner.plan("wait please", _context())
    assert len(plan) == 1
    assert plan.steps[0].action.value == "wait"


def test_gemini_planner_raises_on_invalid_json():
    planner = GeminiPlanner(client=_FakeClient("this is not json"))
    with pytest.raises(PlanningError):
        planner.plan("Move the cup to the tray", _context())


def test_gemini_planner_raises_on_schema_mismatch():
    bad_json = json.dumps([{"action": "fly_away", "args": {}}])
    planner = GeminiPlanner(client=_FakeClient(bad_json))
    with pytest.raises(PlanningError):
        planner.plan("Move the cup to the tray", _context())


def test_gemini_planner_works_end_to_end_via_run_single_task():
    plan_json = json.dumps(
        [
            {"action": "move_to", "args": {"location": "table"}},
            {"action": "pick", "args": {"object_name": "red_block"}},
            {"action": "move_to", "args": {"location": "blue_shelf"}},
            {"action": "place", "args": {"target_location": "blue_shelf"}},
        ]
    )
    task = get_task_by_id("task_001")
    planner = GeminiPlanner(client=_FakeClient(plan_json))
    outcome = run_single_task(task, planner, SafeExecutor(), allow_feedback=False)
    assert outcome.success is True
    assert outcome.planner_name == "gemini"


def test_gemini_planner_supports_feedback_and_replans_on_failure():
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
    planner = GeminiPlanner(client=_SequentialFakeClient([broken_plan, fixed_plan]))

    assert planner.supports_feedback is True

    outcome = run_single_task(task, planner, SafeExecutor(), allow_feedback=True)

    assert outcome.success is True
    assert outcome.replanned is True
    assert len(planner._client.models.calls) == 2
    second_call_prompt = planner._client.models.calls[1]["contents"]
    assert "previous_attempt_failed_because" in second_call_prompt
