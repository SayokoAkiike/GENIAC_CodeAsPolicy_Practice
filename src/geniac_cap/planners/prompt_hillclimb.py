"""Prompt hill-climbing (Step 4 of the zero-budget model-improvement
roadmap; see docs/model-improvement-roadmap.md).

Treats the system prompt as the only "trainable" artifact: evaluate a
baseline, propose a mutation, re-evaluate, keep the change only if it
measurably improves success rate. This is the closest zero-cost analog to
"learn from failure data" available without gradient-based training --
it reuses the same Evaluator/EvaluationSummary machinery as Step 0
(evaluation tracking) as its reward signal.

The core loop (``hill_climb``) is decoupled from planners/tasks/API calls:
it only needs a function ``str -> EvaluationSummary``. This keeps it
trivially testable with a fake evaluate_fn, and reusable regardless of
which planner or task set is being optimized.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from geniac_cap.models import EvaluationSummary


@dataclass
class PromptMutation:
    """A single candidate change to a system prompt."""

    name: str
    description: str
    apply: Callable[[str], str]


def _append_instruction(text: str) -> Callable[[str], str]:
    def _apply(prompt: str) -> str:
        return prompt.rstrip() + "\n\n" + text

    return _apply


DEFAULT_MUTATIONS: list[PromptMutation] = [
    PromptMutation(
        name="self_check_names",
        description="Add a self-check instruction to verify object/location names exist",
        apply=_append_instruction(
            "Before finalizing your answer, double check that every object_name and "
            "location value you used appears in known_objects or known_locations "
            "exactly as given."
        ),
    ),
    PromptMutation(
        name="container_reminder",
        description="Add an explicit reminder to open containers before placing into them",
        apply=_append_instruction(
            "If the destination is a container, you must open_container it before "
            "placing anything inside, and it's fine to close_container it afterward."
        ),
    ),
    PromptMutation(
        name="multi_object_reminder",
        description="Add an explicit reminder to handle every object mentioned",
        apply=_append_instruction(
            "If the instruction mentions more than one object, include a complete "
            "move_to/pick/move_to/place sequence for every one of them, not just the "
            "first."
        ),
    ),
]


@dataclass
class HillClimbStep:
    """Record of one mutation attempt."""

    mutation_name: str
    prompt: str
    success_rate: float
    accepted: bool


@dataclass
class HillClimbResult:
    baseline_success_rate: float
    final_success_rate: float
    final_prompt: str
    steps: list[HillClimbStep] = field(default_factory=list)

    @property
    def improvement(self) -> float:
        return self.final_success_rate - self.baseline_success_rate


def hill_climb(
    base_prompt: str,
    evaluate_fn: Callable[[str], EvaluationSummary],
    mutations: list[PromptMutation] | None = None,
) -> HillClimbResult:
    """Greedily accept mutations that don't decrease success rate.

    Args:
        base_prompt: The starting system prompt.
        evaluate_fn: Given a prompt, returns an EvaluationSummary for it
            (typically: build a planner with that system prompt, run
            Evaluator.evaluate against a task set).
        mutations: Candidate mutations to try, in order. Defaults to
            DEFAULT_MUTATIONS.

    Each mutation is applied on top of the *current best* prompt (not the
    original base_prompt), so accepted mutations compound.
    """

    mutations = mutations if mutations is not None else DEFAULT_MUTATIONS

    baseline_summary = evaluate_fn(base_prompt)
    current_prompt = base_prompt
    current_success_rate = baseline_summary.success_rate

    steps = [
        HillClimbStep(
            mutation_name="baseline",
            prompt=base_prompt,
            success_rate=current_success_rate,
            accepted=True,
        )
    ]

    for mutation in mutations:
        candidate_prompt = mutation.apply(current_prompt)
        candidate_summary = evaluate_fn(candidate_prompt)
        accepted = candidate_summary.success_rate >= current_success_rate
        steps.append(
            HillClimbStep(
                mutation_name=mutation.name,
                prompt=candidate_prompt,
                success_rate=candidate_summary.success_rate,
                accepted=accepted,
            )
        )
        if accepted:
            current_prompt = candidate_prompt
            current_success_rate = candidate_summary.success_rate

    return HillClimbResult(
        baseline_success_rate=baseline_summary.success_rate,
        final_success_rate=current_success_rate,
        final_prompt=current_prompt,
        steps=steps,
    )
