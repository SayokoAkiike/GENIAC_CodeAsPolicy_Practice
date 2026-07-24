"""A Planner backed by the Groq API (free tier friendly, OpenAI-compatible).

Mirrors AnthropicPlanner/GeminiPlanner's design exactly (see those modules
for more detail): lazy import of the ``groq`` package, no API key read
until this planner is actually used, an injectable client for tests, and
an overridable ``system_prompt`` for prompt hill-climbing (Step 4:
docs/model-improvement-roadmap.md).

Groq exists in this project specifically as a *fallback tier*: it has a
much larger free-tier daily quota than Gemini (thousands of
requests/day vs. Gemini's ~20/day for the current default model), so a
cascade like ``--cascade "rule-based,gemini,groq"`` automatically falls
through to Groq once Gemini's quota is exhausted (a 429 there is treated
like any other planning failure by the existing cascade logic in
evaluation/cascade.py -- no special "quota-aware" code needed).
"""

from __future__ import annotations

import json

from geniac_cap.config import settings
from geniac_cap.exceptions import PlanningError
from geniac_cap.models import Action, ActionPlan
from geniac_cap.planners.base import BasePlanner, PlanningContext
from geniac_cap.planners.llm_prompts import ACTION_PLAN_SYSTEM_PROMPT
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)

# llama-3.3-70b-versatile is a solid general-purpose free-tier default as of
# mid-2026; see docs/roadmap.md for a note on keeping this current.
DEFAULT_MODEL = "llama-3.3-70b-versatile"

# Groq's response_format={"type": "json_object"} requires the top-level
# response to be a JSON *object*, but the shared ACTION_PLAN_SYSTEM_PROMPT
# asks for a bare JSON array (which Anthropic/Gemini handle natively).
# This is appended on top of whatever system_prompt is in use (including
# hill-climbing mutations) rather than baked into the shared prompt, since
# it's a Groq-specific wire-format requirement, not part of the task spec.
_JSON_OBJECT_WRAPPER_INSTRUCTION = (
    "\n\nSince your response must be a JSON object (not a bare array), wrap "
    'the action array in an object with a single key "actions", e.g. '
    '{"actions": [...]}.'
)


class GroqPlanner(BasePlanner):
    """Planner that delegates plan generation to a Groq-hosted model."""

    name = "groq"
    supports_feedback = True

    def __init__(
        self,
        model: str | None = None,
        client: object | None = None,
        api_key: str | None = None,
        system_prompt: str | None = None,
    ) -> None:
        """Create a GroqPlanner.

        Args:
            model: Model name to use; defaults to DEFAULT_MODEL.
            client: Pre-built Groq client (mainly for tests). If given, no
                API key or `groq` import is needed.
            api_key: Explicit API key, overriding the GROQ_API_KEY
                environment variable. Pass an empty string to force "no key"
                regardless of the environment (used in tests).
            system_prompt: Override the default ACTION_PLAN_SYSTEM_PROMPT.
                Used by prompt hill-climbing (Step 4:
                docs/model-improvement-roadmap.md).
        """

        self._model = model or DEFAULT_MODEL
        self._client = client
        self._api_key = api_key if api_key is not None else settings.groq_api_key
        self._system_prompt = system_prompt or ACTION_PLAN_SYSTEM_PROMPT

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise PlanningError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and set it, "
                "or export GROQ_API_KEY, to use GroqPlanner. Get a free key "
                "(no credit card required) at https://console.groq.com"
            )
        try:
            from groq import Groq
        except ImportError as exc:
            raise PlanningError(
                "The 'groq' package is not installed. Install it with: "
                "pip install -e '.[llm]'"
            ) from exc
        self._client = Groq(api_key=self._api_key)
        return self._client

    def plan(self, instruction: str, context: PlanningContext) -> ActionPlan:
        return self._generate(instruction, context, feedback=None)

    def replan(self, instruction: str, context: PlanningContext, feedback: str) -> ActionPlan:
        """Ask the model for a corrected plan, given feedback on why the first one failed."""

        return self._generate(instruction, context, feedback=feedback)

    def _generate(
        self, instruction: str, context: PlanningContext, feedback: str | None
    ) -> ActionPlan:
        client = self._get_client()
        user_prompt = self._build_user_prompt(instruction, context, feedback)

        logger.info("GroqPlanner calling model '%s' for: '%s'", self._model, instruction)
        try:
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": self._system_prompt + _JSON_OBJECT_WRAPPER_INSTRUCTION,
                    },
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
        except PlanningError:
            raise
        except Exception as exc:  # network/API errors of any kind (incl. 429 quota)
            raise PlanningError(f"Groq API call failed: {exc}") from exc

        text = self._extract_text(response)
        plan = self._parse_plan(text)
        logger.info("GroqPlanner produced %d step(s) for: '%s'", len(plan), instruction)
        return plan

    @staticmethod
    def _build_user_prompt(
        instruction: str, context: PlanningContext, feedback: str | None = None
    ) -> str:
        payload = {
            "instruction": instruction,
            "known_objects": context.objects,
            "known_locations": context.locations,
            "object_locations": context.object_locations,
            "robot_location": context.robot_location,
        }
        if feedback:
            payload["previous_attempt_failed_because"] = feedback
            payload["note"] = "Produce a corrected plan that avoids this failure."
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _extract_text(response) -> str:
        try:
            text = response.choices[0].message.content
        except (AttributeError, IndexError) as exc:
            raise PlanningError(f"Unexpected Groq response shape: {exc}") from exc
        if not text:
            raise PlanningError("Groq response contained no text content")
        return text

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()[1:]
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

        # Groq's response_format=json_object requires a top-level JSON
        # *object*, not an array, unlike Anthropic/Gemini's raw array
        # response -- so the action list is expected under an "actions" key.
        if isinstance(data, dict) and "actions" in data:
            data = data["actions"]

        if not isinstance(data, list):
            raise PlanningError(f"Expected a JSON array of actions, got: {type(data).__name__}")

        try:
            steps = [Action.model_validate(item) for item in data]
        except Exception as exc:
            raise PlanningError(f"Model response did not match the Action schema: {exc}") from exc

        return ActionPlan(steps=steps)
