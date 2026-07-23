"""A Planner backed by the Google Gemini API (free tier friendly).

Mirrors AnthropicPlanner's design exactly: the model is asked to return a
JSON array of whitelisted actions, which is then validated against the same
`Action` model the executor already enforces. The Gemini response is
requested with `response_mime_type="application/json"`, so no markdown
fences should normally appear, but stripping is still applied defensively.

Design choices that keep the rest of the project working without this
planner:
  * The ``google.genai`` package is only imported inside ``_get_client()``,
    not at module import time.
  * No API key is read unless this planner is actually constructed and used.
  * A ``client`` can be injected in the constructor for testing without any
    real API calls or the package installed.
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

# "gemini-flash-latest" is Google's auto-updating alias for its current
# recommended free-tier Flash model (currently gemini-3.5-flash as of mid-
# 2026). Using the alias instead of a pinned version avoids breaking when
# Google retires a specific dated model, which happens periodically -- see
# docs/roadmap.md for a note on keeping this current.
DEFAULT_MODEL = "gemini-flash-latest"


class GeminiPlanner(BasePlanner):
    """Planner that delegates plan generation to a Gemini model."""

    name = "gemini"
    supports_feedback = True

    def __init__(
        self,
        model: str | None = None,
        client: object | None = None,
        api_key: str | None = None,
    ) -> None:
        """Create a GeminiPlanner.

        Args:
            model: Model name to use; defaults to DEFAULT_MODEL.
            client: Pre-built genai.Client (mainly for tests). If given, no
                API key or `google-genai` import is needed.
            api_key: Explicit API key, overriding the GEMINI_API_KEY
                environment variable. Pass an empty string to force "no key"
                regardless of the environment (used in tests).
        """

        self._model = model or DEFAULT_MODEL
        self._client = client
        self._api_key = api_key if api_key is not None else settings.gemini_api_key

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise PlanningError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env and set "
                "it, or export GEMINI_API_KEY, to use GeminiPlanner. Get a free "
                "key at https://aistudio.google.com/apikey"
            )
        try:
            from google import genai
        except ImportError as exc:
            raise PlanningError(
                "The 'google-genai' package is not installed. Install it with: "
                "pip install -e '.[llm]'"
            ) from exc
        self._client = genai.Client(api_key=self._api_key)
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

        logger.info("GeminiPlanner calling model '%s' for: '%s'", self._model, instruction)
        try:
            # The google-genai SDK accepts a plain dict wherever it accepts a
            # types.GenerateContentConfig, so we use a dict here to avoid an
            # extra import (and keep this call injectable in tests without
            # the package installed).
            response = client.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config={
                    "system_instruction": ACTION_PLAN_SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                },
            )
        except PlanningError:
            raise
        except Exception as exc:  # network/API errors of any kind
            raise PlanningError(f"Gemini API call failed: {exc}") from exc

        text = self._extract_text(response)
        plan = self._parse_plan(text)
        logger.info("GeminiPlanner produced %d step(s) for: '%s'", len(plan), instruction)
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
        text = getattr(response, "text", None)
        if not text:
            raise PlanningError("Gemini response contained no text content")
        return text

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            lines = lines[1:]
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
