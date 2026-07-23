"""Tests for VocabularyDistiller (Step 3 of docs/model-improvement-roadmap.md).

These never call a real LLM API: a fake client is injected via the
constructor, mirroring the pattern used for AnthropicPlanner/GeminiPlanner.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from geniac_cap.exceptions import PlanningError
from geniac_cap.planners.vocabulary_distiller import (
    VocabularyDistiller,
    VocabularyProposal,
    default_probe_instructions,
    filter_probes_needing_harvest,
)


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeResponse:
    content: list[_FakeTextBlock] = field(default_factory=list)


class _FakeMessages:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = responses
        self.call_count = 0

    def create(self, **kwargs):
        response = self._responses[self.call_count % len(self._responses)]
        self.call_count += 1
        return _FakeResponse(content=[_FakeTextBlock(text=json.dumps(response))])


class _FakeClient:
    def __init__(self, responses: list[dict]) -> None:
        self.messages = _FakeMessages(responses)


def test_filter_probes_needing_harvest_skips_already_recognized_instructions():
    known_objects = ["red_block"]
    known_locations = ["blue_shelf"]
    probes = [
        "Move the red block to the blue shelf",  # RuleBasedPlanner already handles this
        "Move the crimson cube to the blue shelf",  # unrecognized vocabulary
    ]
    needing_harvest = filter_probes_needing_harvest(probes, known_objects, known_locations)
    assert needing_harvest == ["Move the crimson cube to the blue shelf"]


def test_default_probe_instructions_returns_a_nonempty_list():
    probes = default_probe_instructions()
    assert len(probes) > 5
    assert all(isinstance(p, str) for p in probes)


def test_vocabulary_distiller_raises_without_api_key_or_client():
    distiller = VocabularyDistiller(provider="anthropic", api_key="")
    with pytest.raises(PlanningError):
        distiller.identify("Move the crimson block to the shelf", ["red_block"], ["shelf"])


def test_vocabulary_distiller_rejects_unknown_provider():
    with pytest.raises(PlanningError):
        VocabularyDistiller(provider="openai")


def test_harvest_proposes_new_object_synonym():
    responses = [
        {
            "object_name": "red_block",
            "object_phrase": "crimson block",
            "location_name": "blue_shelf",
            "location_phrase": "blue shelf",
        }
    ]
    distiller = VocabularyDistiller(provider="anthropic", client=_FakeClient(responses))
    proposal = distiller.harvest(
        ["Move the crimson block to the blue shelf"],
        known_objects=["red_block"],
        known_locations=["blue_shelf"],
    )
    assert proposal.object_synonyms == {"red_block": ["crimson block"]}
    assert proposal.unresolved_instructions == []


def test_harvest_skips_phrases_already_in_existing_synonyms():
    responses = [
        {
            "object_name": "red_block",
            "object_phrase": "crimson block",
            "location_name": None,
            "location_phrase": None,
        }
    ]
    distiller = VocabularyDistiller(provider="anthropic", client=_FakeClient(responses))
    proposal = distiller.harvest(
        ["Move the crimson block somewhere"],
        known_objects=["red_block"],
        known_locations=[],
        existing_object_synonyms={"red_block": ["crimson block"]},  # already known
    )
    assert proposal.object_synonyms == {}


def test_harvest_records_unresolved_instructions_on_api_failure():
    distiller = VocabularyDistiller(provider="anthropic", api_key="")
    proposal = distiller.harvest(
        ["Move the mystery item somewhere"], known_objects=["red_block"], known_locations=[]
    )
    assert proposal.unresolved_instructions == ["Move the mystery item somewhere"]
    assert proposal.is_empty() is True


def test_proposal_as_python_snippet_contains_proposed_entries():
    proposal = VocabularyProposal(object_synonyms={"red_block": ["crimson block"]})
    snippet = proposal.as_python_snippet()
    assert "red_block" in snippet
    assert "crimson block" in snippet
