"""Planner cascade (Step 1 of the zero-budget model improvement roadmap;
see docs/model-improvement-roadmap.md).

Tries a list of planners in order for a task, stopping at the first one
that actually succeeds (goal achieved), so expensive/quota-limited LLM
planners are only called when a cheaper one (e.g. RuleBasedPlanner) can't
solve the task. This is the client-side analog of "inference-efficiency
tricks" for a project that only consumes hosted APIs rather than hosting
models itself.

Deliberately reuses ``run_single_task`` unchanged for each individual
attempt (including its own feedback/replan handling), rather than adding a
"cascade-aware" mode to ``BasePlanner`` -- ``plan()`` doesn't have access to
the task's goal_state, so only the Evaluator layer (which does) can
correctly decide whether an attempt actually succeeded.
"""

from __future__ import annotations

from geniac_cap.evaluation.evaluator import run_single_task
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.models import TaskDefinition, TaskOutcome
from geniac_cap.perception.base import BasePerception
from geniac_cap.planners.base import BasePlanner
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)


def run_single_task_cascade(
    task: TaskDefinition,
    planners: list[BasePlanner],
    executor: SafeExecutor,
    allow_feedback: bool = True,
    perception: BasePerception | None = None,
) -> TaskOutcome:
    """Try ``planners`` in order, returning the first successful outcome.

    If every planner fails, returns the outcome from the *last* (typically
    most capable/expensive) planner tried, so the reported failure reason
    reflects the strongest attempt rather than the cheapest one.

    Raises:
        ValueError: if ``planners`` is empty.
    """

    if not planners:
        raise ValueError("run_single_task_cascade requires at least one planner")

    outcome: TaskOutcome | None = None
    for i, planner in enumerate(planners):
        outcome = run_single_task(
            task, planner, executor, allow_feedback=allow_feedback, perception=perception
        )
        if outcome.success:
            if i > 0:
                logger.info(
                    "Task %s: cascade succeeded with planner '%s' (tier %d/%d), "
                    "skipping %d more expensive planner(s)",
                    task.task_id,
                    planner.name,
                    i + 1,
                    len(planners),
                    len(planners) - i - 1,
                )
            return outcome
        logger.info(
            "Task %s: cascade tier %d/%d ('%s') failed (%s), trying next planner",
            task.task_id,
            i + 1,
            len(planners),
            planner.name,
            outcome.failure_reason.value if outcome.failure_reason else "unknown",
        )

    assert outcome is not None  # loop ran at least once since planners is non-empty
    return outcome
