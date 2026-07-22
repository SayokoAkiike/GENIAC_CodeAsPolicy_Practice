"""A Planner backed by the Anthropic API.

This is the first real external-LLM planner (Phase 2 of docs/roadmap.md).
It asks the model to return a JSON array of whitelisted actions, then
validates that JSON against the same `Action` model the executor already
enforces -- the model can never bypass the whitelist, it can only produce
data that either validates or gets rejected as a PlanningError.

Design choices that keep the rest of the project working without this
planner:
  * The ``anthropic`` package is only imported inside ``_get_client()``,
    not at module import time, so importing this module (and the rest of
    geniac_cap) never requires the package to be installed.
  * No API key is read unless this planner is actually constructed and
    used. Every other command/test in the project works with zero keys.
  * A ``client`` can be injected in the constructor, which is how the test
    suite exercises the JSON-parsing logic without making real API calls.
"""

from __future__ import annotations

import json

from geniac_cap.config import settings
from geniac_cap.exceptions import PlanningError
from geniac_cap.models import Action, ActionPlan
from geniac_cap.planners.base import BasePlanner, PlanningContext
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-5"

_SYSTEM_PROMPT = """You control a simple robot in a toy environment. Given an \
instruction and the current world state, respond with ONLY a JSON array of \
actions (no prose, no markdown fences) that will accomplish the instruction.

Each action must be an object with exactly these keys:
  "action": one of "move_to", "pick", "place", "inspect", "wait", "reset", \
"open_container", "close_container"
  "args": an object with the arguments that action needs:
    - move_to: {"location": "<a known location>"}
    - pick: {"object_name": "<a known object>"}
    - place: {"target_location": "<a known location>"}
    - inspect: {"object_name": "<a known object>"}
    - open_container / close_container: {"object_name": "<a known container>"}
    - wait / reset: {}

Rules:
  - Only use object and location names from the provided "known_objects" and \
"known_locations" lists.
  - The robot must move_to an object's location before picking it, and must \
move_to a destination before placing an object there.
  - Output nothing but the JSON array itself.

Example output:
[
  {"action": "move_to", "args": {"location": "table"}},
  {"action": "pick", "args": {"object_name": "cup"}},
  {"action": "move_to", "args": {"location": "tray"}},
  {"action": "place", "args": {"target_location": "tray"}}
]
"""


class AnthropicPlanner(BasePlanner):
    """Planner that delegates plan generation to a Claude model."""

    name = "anthropic"

    def __init__(
        self,
        model: str | None = None,
        client: object | None = None,
        api_key: str | None = None,
    ) -> None:
        """Create an AnthropicPlanner.

        Args:
            model: Model name to use; defaults to MODEL_NAME env var, then
                DEFAULT_MODEL.
            client: Pre-built Anthropic client (mainly for tests). If given,
                no API key or `anthropic` import is needed.
            api_key: Explicit API key, overriding the ANTHROPIC_API_KEY
                environment variable. Pass an empty string to force "no key"
                regardless of the environment (used in tests).
        """

        self._model = model or settings.model_name or DEFAULT_MODEL
        self._client = client
        self._api_key = api_key if api_key is not None else settings.anthropic_api_key

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise PlanningError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and set "
                "it, or export ANTHROPIC_API_KEY, to use AnthropicPlanner."
            )
        try:
            import anthropic
        except ImportError as exc:
            raise PlanningError(
                "The 'anthropic' package is not installed. Install it with: "
                "pip install -e '.[llm]'"
            ) from exc
        self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def plan(self, instruction: str, context: PlanningContext) -> ActionPlan:
        client = self._get_client()
        user_prompt = self._build_user_prompt(instruction, context)

        logger.info("AnthropicPlanner calling model '%s' for: '%s'", self._model, instruction)
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except PlanningError:
            raise
        except Exception as exc:  # network/API errors of any kind
            raise PlanningError(f"Anthropic API call failed: {exc}") from exc

        text = self._extract_text(response)
        plan = self._parse_plan(text)
        logger.info("AnthropicPlanner produced %d step(s) for: '%s'", len(plan), instruction)
        return plan

    @staticmethod
    def _build_user_prompt(instruction: str, context: PlanningContext) -> str:
        payload = {
            "instruction": instruction,
            "known_objects": context.objects,
            "known_locations": context.locations,
            "object_locations": context.object_locations,
            "robot_location": context.robot_location,
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _extract_text(response) -> str:
        parts = [
            block.text
            for block in getattr(response, "content", [])
            if getattr(block, "type", None) == "text"
        ]
        if not parts:
            raise PlanningError("Anthropic response contained no text content")
        return "".join(parts)

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = lines[1:]  # drop opening fence (with optional language tag)
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines)
        return cleaned.strip()

    @classmethod
    def _parse_plan(cls, text: str) -> ActionPlan:
        cleaned = cls._strip_code_fences(text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PlanningError(
                f"Could not parse JSON from model response: {exc}. Raw text: {text[:200]!r}"
            ) from exc

        if not isinstance(data, list):
            raise PlanningError(f"Expected a JSON array of actions, got: {type(data).__name__}")

        try:
            steps = [Action.model_validate(item) for item in data]
        except Exception as exc:
            raise PlanningError(f"Model response did not match the Action schema: {exc}") from exc

        return ActionPlan(steps=steps)
