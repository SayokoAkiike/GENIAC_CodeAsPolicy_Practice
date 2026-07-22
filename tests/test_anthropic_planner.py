"""Tests for AnthropicPlanner.

These tests never call the real Anthropic API: a fake client is injected via
the constructor, so the tests exercise only the prompt-building and
JSON-parsing/validation logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from geniac_cap.evaluation.evaluator import run_single_task
from geniac_cap.exceptions import PlanningError
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.planners.anthropic_planner import AnthropicPlanner
from geniac_cap.planners.base import PlanningContext
from geniac_cap.tasks.loader import get_task_by_id


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeResponse:
    content: list[_FakeTextBlock] = field(default_factory=list)


class _FakeMessages:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.last_call_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        return _FakeResponse(content=[_FakeTextBlock(text=self._response_text)])


class _FakeClient:
    def __init__(self, response_text: str) -> None:
        self.messages = _FakeMessages(response_text)


def _context() -> PlanningContext:
    return PlanningContext(
        objects=["cup"],
        locations=["table", "tray"],
        object_locations={"cup": "table"},
        robot_location="table",
    )


def test_anthropic_planner_raises_without_api_key_or_client():
    planner = AnthropicPlanner(api_key="")  # force "no key" regardless of environment
    with pytest.raises(PlanningError):
        planner.plan("Move the cup to the tray", _context())


def test_anthropic_planner_parses_valid_json_response():
    plan_json = json.dumps(
        [
            {"action": "move_to", "args": {"location": "table"}},
            {"action": "pick", "args": {"object_name": "cup"}},
            {"action": "move_to", "args": {"location": "tray"}},
            {"action": "place", "args": {"target_location": "tray"}},
        ]
    )
    planner = AnthropicPlanner(client=_FakeClient(plan_json))
    plan = planner.plan("Move the cup to the tray", _context())

    assert len(plan) == 4
    assert plan.steps[1].args["object_name"] == "cup"
    assert plan.steps[-1].args["target_location"] == "tray"


def test_anthropic_planner_strips_markdown_code_fences():
    plan_json = json.dumps([{"action": "wait", "args": {}}])
    fenced = f"```json\n{plan_json}\n```"
    planner = AnthropicPlanner(client=_FakeClient(fenced))
    plan = planner.plan("wait please", _context())
    assert len(plan) == 1
    assert plan.steps[0].action.value == "wait"


def test_anthropic_planner_raises_on_invalid_json():
    planner = AnthropicPlanner(client=_FakeClient("this is not json"))
    with pytest.raises(PlanningError):
        planner.plan("Move the cup to the tray", _context())


def test_anthropic_planner_raises_on_schema_mismatch():
    bad_json = json.dumps([{"action": "fly_away", "args": {}}])
    planner = AnthropicPlanner(client=_FakeClient(bad_json))
    with pytest.raises(PlanningError):
        planner.plan("Move the cup to the tray", _context())


def test_anthropic_planner_works_end_to_end_via_run_single_task():
    plan_json = json.dumps(
        [
            {"action": "move_to", "args": {"location": "table"}},
            {"action": "pick", "args": {"object_name": "red_block"}},
            {"action": "move_to", "args": {"location": "blue_shelf"}},
            {"action": "place", "args": {"target_location": "blue_shelf"}},
        ]
    )
    task = get_task_by_id("task_001")
    planner = AnthropicPlanner(client=_FakeClient(plan_json))
    outcome = run_single_task(task, planner, SafeExecutor(), allow_feedback=False)
    assert outcome.success is True
    assert outcome.planner_name == "anthropic"
