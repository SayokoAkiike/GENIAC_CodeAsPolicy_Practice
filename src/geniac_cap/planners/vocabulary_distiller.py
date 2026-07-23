"""Symbolic distillation: harvest new RuleBasedPlanner vocabulary from an LLM
(Step 3 of the zero-budget model improvement roadmap; see
docs/model-improvement-roadmap.md).

This is NOT neural distillation -- no model weights change. It asks an LLM
to identify which known object/location a paraphrase refers to, for
instructions RuleBasedPlanner currently can't parse, and proposes additions
to OBJECT_SYNONYMS / LOCATION_SYNONYMS in planners/rule_based.py. Proposals
are printed/saved for human review, never auto-applied to source code.

Design mirrors AnthropicPlanner / GeminiPlanner (see planners/
anthropic_planner.py, planners/gemini_planner.py): the anthropic /
google-genai packages are only imported inside the client getters, no API
key is read unless this class is used, and a client can be injected for
testing without real API calls.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from geniac_cap.config import settings
from geniac_cap.exceptions import PlanningError
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
DEFAULT_GEMINI_MODEL = "gemini-flash-latest"

_IDENTIFY_SYSTEM_PROMPT = """You help maintain a robot instruction parser's \
vocabulary. Given an instruction and lists of known object/location names, \
identify which known object_name and/or location_name (if any) the \
instruction refers to, and the exact phrase used for each.

Respond with ONLY a JSON object (no prose, no markdown fences) with exactly \
these keys:
  "object_name": one of the known_objects this instruction refers to, or null
  "object_phrase": the exact phrase in the instruction referring to that \
object, or null
  "location_name": one of the known_locations this instruction refers to \
(as its destination/target), or null
  "location_phrase": the exact phrase in the instruction referring to that \
location, or null

Only use names from the provided lists. If the instruction doesn't clearly \
refer to a known object or location, use null for that pair.

Example: known_objects=["red_block"], known_locations=["blue_shelf"], \
instruction="Move the crimson cube to the sky-blue shelf" ->
{"object_name": "red_block", "object_phrase": "crimson cube", \
"location_name": "blue_shelf", "location_phrase": "sky-blue shelf"}
"""


@dataclass
class VocabularyProposal:
    """Proposed additions to OBJECT_SYNONYMS / LOCATION_SYNONYMS, plus any
    probe instructions the LLM couldn't resolve.
    """

    object_synonyms: dict[str, list[str]] = field(default_factory=dict)
    location_synonyms: dict[str, list[str]] = field(default_factory=dict)
    unresolved_instructions: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.object_synonyms and not self.location_synonyms

    def as_python_snippet(self) -> str:
        """Format as a diff-like snippet ready for human review before
        merging into planners/rule_based.py's OBJECT_SYNONYMS / LOCATION_SYNONYMS.
        """

        lines = ["# Proposed additions -- review before merging into rule_based.py"]
        if self.object_synonyms:
            lines.append("# OBJECT_SYNONYMS:")
            for name, phrases in self.object_synonyms.items():
                lines.append(f'#   "{name}": add {phrases!r}')
        if self.location_synonyms:
            lines.append("# LOCATION_SYNONYMS:")
            for name, phrases in self.location_synonyms.items():
                lines.append(f'#   "{name}": add {phrases!r}')
        if self.unresolved_instructions:
            lines.append(
                f"# {len(self.unresolved_instructions)} instruction(s) could not be resolved"
            )
        return "\n".join(lines)


class VocabularyDistiller:
    """Uses an LLM to identify known object/location names in paraphrases
    RuleBasedPlanner doesn't recognize, proposing new synonym entries.
    """

    name = "vocabulary-distiller"

    def __init__(
        self,
        provider: str = "anthropic",
        model: str | None = None,
        client: object | None = None,
        api_key: str | None = None,
    ) -> None:
        if provider not in ("anthropic", "gemini"):
            raise PlanningError(
                f"Unknown provider: '{provider}' (expected anthropic/gemini)"
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
                f"to use VocabularyDistiller(provider='{self._provider}')."
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

    def identify(
        self, instruction: str, known_objects: list[str], known_locations: list[str]
    ) -> dict:
        """Ask the LLM which known object/location ``instruction`` refers to."""

        client = self._get_client()
        prompt = json.dumps(
            {
                "instruction": instruction,
                "known_objects": known_objects,
                "known_locations": known_locations,
            },
            ensure_ascii=False,
        )

        try:
            if self._provider == "anthropic":
                text = self._call_anthropic(client, prompt)
            else:
                text = self._call_gemini(client, prompt)
        except PlanningError:
            raise
        except Exception as exc:  # network/API errors of any kind
            raise PlanningError(f"Vocabulary identification call failed: {exc}") from exc

        return self._parse(text)

    def _call_anthropic(self, client, prompt: str) -> str:
        response = client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_IDENTIFY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [
            block.text
            for block in getattr(response, "content", [])
            if getattr(block, "type", None) == "text"
        ]
        if not parts:
            raise PlanningError("Anthropic response contained no text content")
        return "".join(parts)

    def _call_gemini(self, client, prompt: str) -> str:
        response = client.models.generate_content(
            model=self._model,
            contents=prompt,
            config={
                "system_instruction": _IDENTIFY_SYSTEM_PROMPT,
                "response_mime_type": "application/json",
            },
        )
        text = getattr(response, "text", None)
        if not text:
            raise PlanningError("Gemini response contained no text content")
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
    def _parse(cls, text: str) -> dict:
        cleaned = cls._strip_code_fences(text)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise PlanningError(
                f"Could not parse JSON from response: {exc}. Raw text: {text[:200]!r}"
            ) from exc
        if not isinstance(data, dict):
            raise PlanningError(f"Expected a JSON object, got: {type(data).__name__}")
        return data

    def harvest(
        self,
        probe_instructions: list[str],
        known_objects: list[str],
        known_locations: list[str],
        existing_object_synonyms: dict[str, list[str]] | None = None,
        existing_location_synonyms: dict[str, list[str]] | None = None,
    ) -> VocabularyProposal:
        """Run ``identify`` over every probe instruction and build a proposal
        of new synonym entries not already covered by the existing dicts.
        """

        existing_object_synonyms = existing_object_synonyms or {}
        existing_location_synonyms = existing_location_synonyms or {}
        proposal = VocabularyProposal()

        for instruction in probe_instructions:
            try:
                result = self.identify(instruction, known_objects, known_locations)
            except PlanningError as exc:
                logger.warning("Could not resolve probe instruction '%s': %s", instruction, exc)
                proposal.unresolved_instructions.append(instruction)
                continue

            obj_name = result.get("object_name")
            obj_phrase = result.get("object_phrase")
            if obj_name in known_objects and obj_phrase:
                known = [s.lower() for s in existing_object_synonyms.get(obj_name, [])]
                known.append(obj_name.replace("_", " ").lower())
                if obj_phrase.lower() not in known:
                    bucket = proposal.object_synonyms.setdefault(obj_name, [])
                    if obj_phrase not in bucket:
                        bucket.append(obj_phrase)

            loc_name = result.get("location_name")
            loc_phrase = result.get("location_phrase")
            if loc_name in known_locations and loc_phrase:
                known = [s.lower() for s in existing_location_synonyms.get(loc_name, [])]
                known.append(loc_name.replace("_", " ").lower())
                if loc_phrase.lower() not in known:
                    bucket = proposal.location_synonyms.setdefault(loc_name, [])
                    if loc_phrase not in bucket:
                        bucket.append(loc_phrase)

        return proposal


def filter_probes_needing_harvest(
    probe_instructions: list[str], known_objects: list[str], known_locations: list[str]
) -> list[str]:
    """Return only the probes RuleBasedPlanner currently fails to parse.

    Skips probes it already handles, so ``harvest()`` only spends API calls
    on genuine vocabulary gaps.
    """

    from geniac_cap.exceptions import PlanningError as _PlanningError
    from geniac_cap.planners.base import PlanningContext
    from geniac_cap.planners.rule_based import RuleBasedPlanner

    # A dummy context is enough here: we only care whether object/location
    # *matching* succeeds, not whether execution would (there's no real
    # environment for a bare vocabulary probe).
    dummy_location = known_locations[0] if known_locations else "somewhere"
    context = PlanningContext(
        objects=known_objects,
        locations=known_locations,
        object_locations=dict.fromkeys(known_objects, dummy_location),
        robot_location=dummy_location,
    )

    planner = RuleBasedPlanner()
    needs_harvest = []
    for instruction in probe_instructions:
        try:
            planner.plan(instruction, context)
        except _PlanningError:
            needs_harvest.append(instruction)
    return needs_harvest


def default_probe_instructions() -> list[str]:
    """A small built-in set of paraphrases for sample_tasks.yaml's
    vocabulary that RuleBasedPlanner's current synonyms don't cover --
    used as the default input to ``harvest()`` / the ``harvest-vocabulary``
    CLI command.
    """

    return [
        "Move the crimson block to the blue shelf",
        "Put the mug on the tray",
        "Carry the flask to the patient room",
        "Place the hand towel by the bedside",
        "Bring the pill box to the nurse station",
        "Move the novel to the bookshelf",
        "Put the dish on the table",
        "Carry the notepad to the table",
        "Move the paperwork into the supply box",
        "Take the item to the kitchenette",
        "Bring it to the ward",
    ]
