"""Tests for prompt hill-climbing (Step 4 of docs/model-improvement-roadmap.md).

The core loop is decoupled from planners/tasks/API calls (it only needs a
str -> EvaluationSummary function), so these tests use a fake evaluate_fn
instead of any real or fake LLM client.
"""

from __future__ import annotations

import pytest

from geniac_cap.evaluation.metrics import compute_summary
from geniac_cap.models import FailureReason, TaskOutcome
from geniac_cap.planners.prompt_hillclimb import PromptMutation, hill_climb


def _summary(success_rate: float):
    """Build a minimal EvaluationSummary with the given success rate (out of 10 tasks)."""

    n_success = round(success_rate * 10)
    outcomes = [
        TaskOutcome(
            task_id=f"t{i}",
            instruction="x",
            planner_name="fake",
            success=(i < n_success),
            steps=1,
            execution_time_seconds=0.0,
            failure_reason=None if i < n_success else FailureReason.GOAL_NOT_ACHIEVED,
        )
        for i in range(10)
    ]
    return compute_summary("fake", outcomes)


def test_hill_climb_accepts_a_mutation_that_improves_success_rate():
    # base prompt -> 50%, one mutation -> 80%
    scores = {"base": 0.5, "base\n\nMUTATED": 0.8}

    def evaluate_fn(prompt: str):
        return _summary(scores[prompt])

    mutation = PromptMutation("boost", "improves things", apply=lambda p: p + "\n\nMUTATED")
    result = hill_climb("base", evaluate_fn, mutations=[mutation])

    assert result.baseline_success_rate == 0.5
    assert result.final_success_rate == 0.8
    assert result.final_prompt == "base\n\nMUTATED"
    assert result.improvement == pytest.approx(0.3)


def test_hill_climb_rejects_a_mutation_that_hurts_success_rate():
    scores = {"base": 0.8, "base\n\nMUTATED": 0.5}

    def evaluate_fn(prompt: str):
        return _summary(scores[prompt])

    mutation = PromptMutation("bad", "hurts things", apply=lambda p: p + "\n\nMUTATED")
    result = hill_climb("base", evaluate_fn, mutations=[mutation])

    assert result.final_success_rate == 0.8
    assert result.final_prompt == "base"  # rejected mutation not kept
    assert result.improvement == 0.0
    assert result.steps[-1].accepted is False


def test_hill_climb_accepted_mutations_compound():
    # Each mutation should build on the *current best*, not the original base.
    calls = []

    def evaluate_fn(prompt: str):
        calls.append(prompt)
        # Reward more accumulated mutations with a higher score.
        return _summary(0.5 + 0.1 * prompt.count("STEP"))

    mutation_a = PromptMutation("a", "a", apply=lambda p: p + " STEP_A")
    mutation_b = PromptMutation("b", "b", apply=lambda p: p + " STEP_B")

    result = hill_climb("base", evaluate_fn, mutations=[mutation_a, mutation_b])

    assert "STEP_A" in result.final_prompt
    assert "STEP_B" in result.final_prompt
    # mutation_b was applied on top of the already-accepted mutation_a.
    assert calls[-1] == "base STEP_A STEP_B"


def test_hill_climb_ties_are_accepted():
    # A mutation that doesn't help but doesn't hurt either should still be
    # accepted (>=), matching the "keep if not worse" policy.
    scores = {"base": 0.6, "base\n\nMUTATED": 0.6}

    def evaluate_fn(prompt: str):
        return _summary(scores[prompt])

    mutation = PromptMutation("neutral", "no effect", apply=lambda p: p + "\n\nMUTATED")
    result = hill_climb("base", evaluate_fn, mutations=[mutation])

    assert result.steps[-1].accepted is True
    assert result.final_prompt == "base\n\nMUTATED"


def test_hill_climb_records_a_baseline_step_first():
    def evaluate_fn(prompt: str):
        return _summary(0.5)

    result = hill_climb("base", evaluate_fn, mutations=[])
    assert len(result.steps) == 1
    assert result.steps[0].mutation_name == "baseline"
    assert result.steps[0].accepted is True
