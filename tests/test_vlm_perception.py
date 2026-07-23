"""Tests for VLMPerception and GroundTruthPerception.

These never call a real vision API: a fake client is injected via the
constructor, so the tests exercise only the prompt-building and
JSON-parsing/validation logic (the same pattern used for AnthropicPlanner
and GeminiPlanner).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.exceptions import PlanningError
from geniac_cap.perception.ground_truth import GroundTruthPerception
from geniac_cap.perception.vlm_perception import VLMPerception


def _env() -> ToyRobotEnv:
    return ToyRobotEnv(
        locations={"table", "tray"},
        objects={"cup"},
        object_locations={"cup": "table"},
        robot_location="table",
    )


def test_ground_truth_perception_reads_env_state_directly():
    env = _env()
    context = GroundTruthPerception().perceive(env)
    assert context.robot_location == "table"
    assert context.object_locations == {"cup": "table"}
    assert set(context.objects) == {"cup"}
    assert set(context.locations) == {"table", "tray"}


# --- Anthropic-style fake client -------------------------------------------------


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeAnthropicResponse:
    content: list[_FakeTextBlock] = field(default_factory=list)


class _FakeAnthropicMessages:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.last_call_kwargs: dict | None = None

    def create(self, **kwargs):
        self.last_call_kwargs = kwargs
        return _FakeAnthropicResponse(content=[_FakeTextBlock(text=self._response_text)])


class _FakeAnthropicClient:
    def __init__(self, response_text: str) -> None:
        self.messages = _FakeAnthropicMessages(response_text)


# --- Gemini-style fake client -----------------------------------------------------


@dataclass
class _FakeGeminiResponse:
    text: str


class _FakeGeminiModels:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.last_call_kwargs: dict | None = None

    def generate_content(self, **kwargs):
        self.last_call_kwargs = kwargs
        return _FakeGeminiResponse(text=self._response_text)


class _FakeGeminiClient:
    def __init__(self, response_text: str) -> None:
        self.models = _FakeGeminiModels(response_text)


_VALID_SCENE_JSON = json.dumps(
    {
        "locations": ["table", "tray"],
        "objects": ["cup"],
        "object_locations": {"cup": "table"},
        "robot_location": "table",
        "held_object": None,
    }
)


def test_vlm_perception_raises_without_api_key_or_client():
    perception = VLMPerception(provider="anthropic", api_key="")
    with pytest.raises(PlanningError):
        perception.perceive(_env())


def test_vlm_perception_parses_valid_anthropic_response():
    perception = VLMPerception(provider="anthropic", client=_FakeAnthropicClient(_VALID_SCENE_JSON))
    context = perception.perceive(_env())
    assert context.robot_location == "table"
    assert context.object_locations == {"cup": "table"}
    assert set(context.objects) == {"cup"}
    assert set(context.locations) == {"table", "tray"}


def test_vlm_perception_parses_valid_gemini_response():
    perception = VLMPerception(provider="gemini", client=_FakeGeminiClient(_VALID_SCENE_JSON))
    context = perception.perceive(_env())
    assert context.robot_location == "table"
    assert context.object_locations == {"cup": "table"}


def test_vlm_perception_strips_markdown_code_fences():
    fenced = f"```json\n{_VALID_SCENE_JSON}\n```"
    perception = VLMPerception(provider="anthropic", client=_FakeAnthropicClient(fenced))
    context = perception.perceive(_env())
    assert context.robot_location == "table"


def test_vlm_perception_raises_on_invalid_json():
    perception = VLMPerception(provider="anthropic", client=_FakeAnthropicClient("not json"))
    with pytest.raises(PlanningError):
        perception.perceive(_env())


def test_vlm_perception_rejects_unknown_provider():
    with pytest.raises(PlanningError):
        VLMPerception(provider="openai")
