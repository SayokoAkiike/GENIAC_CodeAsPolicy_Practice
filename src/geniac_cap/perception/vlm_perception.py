"""Perception backed by a real vision-language model (VLM).

Renders the environment as a PNG (see ``renderer.py``) and asks a
vision-capable model (Claude via the Anthropic API, or Gemini) to describe
the scene as structured JSON, which is then parsed into a ``PlanningContext``
-- the exact same shape ``GroundTruthPerception`` produces, so Planners
never need to know which perception source is in use.

Design choices mirroring the LLM planners (see planners/anthropic_planner.py
and planners/gemini_planner.py):
  * The ``anthropic`` / ``google-genai`` packages are only imported inside
    the provider-specific client getters, not at module import time.
  * No API key is read unless this class is actually constructed and used.
  * A ``client`` can be injected in the constructor, which is how the test
    suite exercises the JSON-parsing logic without making real API calls.
"""

from __future__ import annotations

import base64
import json

from geniac_cap.config import settings
from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.exceptions import PlanningError
from geniac_cap.perception.base import BasePerception
from geniac_cap.perception.renderer import render_scene
from geniac_cap.planners.base import PlanningContext
from geniac_cap.planners.llm_prompts import SCENE_PERCEPTION_SYSTEM_PROMPT
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"

_USER_PROMPT = "Describe this scene as the specified JSON object."


class VLMPerception(BasePerception):
    """Perceives the environment by rendering it and asking a VLM to read it."""

    name = "vlm"

    def __init__(
        self,
        provider: str = "anthropic",
        model: str | None = None,
        client: object | None = None,
        api_key: str | None = None,
    ) -> None:
        """Create a VLMPerception.

        Args:
            provider: "anthropic" or "gemini".
            model: Model name; defaults to a sensible per-provider default.
            client: Pre-built API client (mainly for tests). If given, no
                API key or SDK import is needed.
            api_key: Explicit API key, overriding the provider's environment
                variable. Pass an empty string to force "no key" regardless
                of the environment (used in tests).
        """

        if provider not in ("anthropic", "gemini"):
            raise PlanningError(
                f"Unknown vision provider: '{provider}' (expected anthropic/gemini)"
            )
        self._provider = provider
        self._model = model or (
            DEFAULT_ANTHROPIC_MODEL if provider == "anthropic" else DEFAULT_GEMINI_MODEL
        )
        self._client = client
        if api_key is not None:
            self._api_key = api_key
        elif provider == "anthropic":
            self._api_key = settings.anthropic_api_key
        else:
            self._api_key = settings.gemini_api_key

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            env_var = "ANTHROPIC_API_KEY" if self._provider == "anthropic" else "GEMINI_API_KEY"
            raise PlanningError(
                f"{env_var} is not set. Copy .env.example to .env and set it "
                f"to use VLMPerception(provider='{self._provider}')."
            )
        if self._provider == "anthropic":
            try:
                import anthropic
            except ImportError as exc:
                raise PlanningError(
                    "The 'anthropic' package is not installed. Install it with: "
                    "pip install -e '.[llm]'"
                ) from exc
            self._client = anthropic.Anthropic(api_key=self._api_key)
        else:
            try:
                from google import genai
            except ImportError as exc:
                raise PlanningError(
                    "The 'google-genai' package is not installed. Install it with: "
                    "pip install -e '.[llm]'"
                ) from exc
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def perceive(self, env: ToyRobotEnv) -> PlanningContext:
        client = self._get_client()

        try:
            png_bytes = render_scene(env)
        except PlanningError:
            raise
        except Exception as exc:  # e.g. RenderingError if Pillow isn't installed
            raise PlanningError(f"Scene rendering failed: {exc}") from exc

        logger.info("VLMPerception (%s/%s) reading rendered scene", self._provider, self._model)
        try:
            if self._provider == "anthropic":
                text = self._call_anthropic(client, png_bytes)
            else:
                text = self._call_gemini(client, png_bytes)
        except PlanningError:
            raise
        except Exception as exc:  # network/API errors of any kind
            raise PlanningError(f"VLM perception call failed: {exc}") from exc

        return self._parse_context(text)

    def _call_anthropic(self, client, png_bytes: bytes) -> str:
        b64 = base64.b64encode(png_bytes).decode("ascii")
        response = client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=SCENE_PERCEPTION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/png", "data": b64},
                        },
                        {"type": "text", "text": _USER_PROMPT},
                    ],
                }
            ],
        )
        parts = [
            block.text
            for block in getattr(response, "content", [])
            if getattr(block, "type", None) == "text"
        ]
        if not parts:
            raise PlanningError("Anthropic vision response contained no text content")
        return "".join(parts)

    def _call_gemini(self, client, png_bytes: bytes) -> str:
        b64 = base64.b64encode(png_bytes).decode("ascii")
        response = client.models.generate_content(
            model=self._model,
            contents=[
                {"text": SCENE_PERCEPTION_SYSTEM_PROMPT + "\n\n" + _USER_PROMPT},
                {"inline_data": {"mime_type": "image/png", "data": b64}},
            ],
            config={"response_mime_type": "application/json"},
        )
        text = getattr(response, "text", None)
        if not text:
            raise PlanningError("Gemini vision response contained no text content")
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
    def _parse_context(cls, text: str) -> PlanningContext:
        cleaned = cls._strip_code_fences(text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PlanningError(
                f"Could not parse JSON from VLM response: {exc}. Raw text: {text[:200]!r}"
            ) from exc

        if not isinstance(data, dict):
            raise PlanningError(
                f"Expected a JSON object describing the scene, got: {type(data).__name__}"
            )

        try:
            return PlanningContext(
                objects=list(data.get("objects", [])),
                locations=list(data.get("locations", [])),
                object_locations=dict(data.get("object_locations", {})),
                robot_location=str(data.get("robot_location", "")),
            )
        except Exception as exc:
            raise PlanningError(
                f"VLM scene description did not match the expected shape: {exc}"
            ) from exc
