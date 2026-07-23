"""Runs a batch of tasks through a given Planner + SafeExecutor and reports metrics."""

from __future__ import annotations

import csv
import json
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from geniac_cap.config import RESULTS_DIR
from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.evaluation.metrics import compute_summary
from geniac_cap.exceptions import PlanningError
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.models import (
    EvaluationSummary,
    ExecutionResult,
    FailureReason,
    TaskDefinition,
    TaskOutcome,
)
from geniac_cap.perception.base import BasePerception
from geniac_cap.perception.ground_truth import GroundTruthPerception
from geniac_cap.planners.base import BasePlanner
from geniac_cap.utils.logging import get_logger

if TYPE_CHECKING:
    from geniac_cap.evaluation.bandit import EpsilonGreedyBandit

logger = get_logger(__name__)

_DEFAULT_PERCEPTION = GroundTruthPerception()


def _build_failure_feedback(result: ExecutionResult) -> str:
    """Build a short, structured description of why a plan's execution failed.

    Used as the ``feedback`` argument to ``BasePlanner.replan()``. Generic
    across planner types: describes the failing step (if any) and the
    resulting environment state, in the same spirit as the worked example in
    the project spec ("Object red_block is at table. Robot is at kitchen.").
    """

    failed_step = next((log for log in result.logs if not log.success), None)
    parts = []
    if failed_step is not None:
        parts.append(
            f"Step '{failed_step.action}' with args {failed_step.args} failed: "
            f"{failed_step.message}"
        )
    elif result.failure_reason is not None:
        parts.append(f"Plan failed: {result.failure_reason.value}")
    state = result.final_state
    if state:
        parts.append(
            f"Current state: robot_location={state.get('robot_location')}, "
            f"held_object={state.get('held_object')}, "
            f"object_locations={state.get('object_locations')}"
        )
    return " ".join(parts) if parts else "Execution failed for an unknown reason."


def run_single_task(
    task: TaskDefinition,
    planner: BasePlanner,
    executor: SafeExecutor,
    allow_feedback: bool = True,
    perception: BasePerception | None = None,
) -> TaskOutcome:
    """Run one task through ``planner`` + ``executor`` and return its outcome.

    If ``planner.supports_feedback`` is True, execution fails, and
    ``allow_feedback`` is True, the environment is reset and exactly one
    replanning attempt is made using the planner's ``replan`` method.

    Args:
        perception: How to build the PlanningContext from the environment.
            Defaults to ``GroundTruthPerception`` (reads state directly).
            Pass a ``VLMPerception`` to have a vision model read a rendered
            image of the scene instead (see docs/roadmap.md, Phase 4).
    """

    perception = perception or _DEFAULT_PERCEPTION
    env = ToyRobotEnv.from_task_state(task.initial_state)

    logger.info("Starting task %s: '%s'", task.task_id, task.instruction)

    try:
        context = perception.perceive(env)
    except PlanningError as exc:
        logger.warning("Perception failed for task %s: %s", task.task_id, exc)
        return TaskOutcome(
            task_id=task.task_id,
            instruction=task.instruction,
            planner_name=planner.name,
            success=False,
            steps=0,
            execution_time_seconds=0.0,
            failure_reason=FailureReason.PLANNING_ERROR,
            replanned=False,
        )

    try:
        plan = planner.plan(task.instruction, context)
    except PlanningError as exc:
        logger.warning("Planning failed for task %s: %s", task.task_id, exc)
        return TaskOutcome(
            task_id=task.task_id,
            instruction=task.instruction,
            planner_name=planner.name,
            success=False,
            steps=0,
            execution_time_seconds=0.0,
            failure_reason=FailureReason.PLANNING_ERROR,
            replanned=False,
        )

    result: ExecutionResult = executor.execute(env, plan, task.goal_state)

    if not result.success and allow_feedback and getattr(planner, "supports_feedback", False):
        logger.info("Task %s failed; attempting one feedback-driven replan", task.task_id)
        env.reset()
        feedback_text = _build_failure_feedback(result)
        try:
            repaired_plan = planner.replan(task.instruction, context, feedback_text)
            result = executor.execute(env, repaired_plan, task.goal_state)
            result.replanned = True
        except PlanningError as exc:
            logger.warning("Replanning failed for task %s: %s", task.task_id, exc)

    logger.info(
        "Task %s finished: success=%s steps=%d reason=%s",
        task.task_id,
        result.success,
        result.steps_executed,
        result.failure_reason.value if result.failure_reason else "none",
    )

    return TaskOutcome(
        task_id=task.task_id,
        instruction=task.instruction,
        planner_name=planner.name,
        success=result.success,
        steps=result.steps_executed,
        execution_time_seconds=result.execution_time_seconds,
        failure_reason=result.failure_reason,
        replanned=result.replanned,
    )


class Evaluator:
    """Evaluates a Planner across many tasks and persists the results."""

    def __init__(
        self, executor: SafeExecutor | None = None, results_dir: Path | None = None
    ) -> None:
        self.executor = executor or SafeExecutor()
        self.results_dir = results_dir or RESULTS_DIR

    def evaluate(
        self,
        tasks: list[TaskDefinition],
        planner: BasePlanner,
        allow_feedback: bool = True,
        delay_seconds: float = 0.0,
        perception: BasePerception | None = None,
    ) -> EvaluationSummary:
        """Run every task in ``tasks`` and return an aggregated EvaluationSummary.

        Args:
            delay_seconds: Optional pause between tasks. Useful for
                rate-limited free-tier LLM APIs (e.g. Gemini's free tier
                allows only a few requests per minute) so a full run doesn't
                immediately trigger 429 errors on later tasks.
            perception: How to build each task's PlanningContext. Defaults
                to ``GroundTruthPerception``; pass a ``VLMPerception`` to
                have a vision model read a rendered image of the scene
                instead (see docs/roadmap.md, Phase 4).
        """

        outcomes = []
        for i, task in enumerate(tasks):
            if i > 0 and delay_seconds > 0:
                time.sleep(delay_seconds)
            outcomes.append(
                run_single_task(
                    task,
                    planner,
                    self.executor,
                    allow_feedback=allow_feedback,
                    perception=perception,
                )
            )
        return compute_summary(planner.name, outcomes)

    def evaluate_cascade(
        self,
        tasks: list[TaskDefinition],
        planners: list[BasePlanner],
        allow_feedback: bool = True,
        delay_seconds: float = 0.0,
        perception: BasePerception | None = None,
    ) -> EvaluationSummary:
        """Run every task through a planner cascade (Step 1 of
        docs/model-improvement-roadmap.md): tries ``planners`` in order per
        task, stopping at the first one that succeeds, so expensive/quota-
        limited planners are only invoked when a cheaper one fails.

        The returned summary's ``planner_name`` is a label describing the
        whole cascade (e.g. "cascade(rule-based->gemini)"), since each task
        may have been solved by a different tier.
        """

        # Local import to avoid a circular import (cascade.py imports
        # run_single_task from this module).
        from geniac_cap.evaluation.cascade import run_single_task_cascade

        cascade_label = "cascade(" + "->".join(p.name for p in planners) + ")"
        outcomes = []
        for i, task in enumerate(tasks):
            if i > 0 and delay_seconds > 0:
                time.sleep(delay_seconds)
            outcomes.append(
                run_single_task_cascade(
                    task,
                    planners,
                    self.executor,
                    allow_feedback=allow_feedback,
                    perception=perception,
                )
            )
        return compute_summary(cascade_label, outcomes)

    def evaluate_bandit(
        self,
        tasks: list[TaskDefinition],
        bandit: EpsilonGreedyBandit,
        planner_factories: dict[str, Callable[[], BasePlanner]],
        allow_feedback: bool = True,
        delay_seconds: float = 0.0,
        perception: BasePerception | None = None,
    ) -> EvaluationSummary:
        """Run every task through a bandit-selected planner cascade (Step 5
        of docs/model-improvement-roadmap.md): for each task, ``bandit``
        picks a cascade order based on the task's difficulty, the cascade
        runs as usual, and the bandit is updated with the observed reward.

        Args:
            bandit: An ``EpsilonGreedyBandit`` (see evaluation/bandit.py).
            planner_factories: Maps planner name -> a zero-arg callable that
                builds a fresh planner instance (fresh instances avoid
                cross-task state leaking between cascade attempts).
        """

        # Local import to avoid a circular import (bandit.py imports
        # run_single_task from this module).
        from geniac_cap.evaluation.bandit import run_bandit_episode

        outcomes = []
        for i, task in enumerate(tasks):
            if i > 0 and delay_seconds > 0:
                time.sleep(delay_seconds)
            outcomes.append(
                run_bandit_episode(
                    task,
                    bandit,
                    planner_factories,
                    self.executor,
                    allow_feedback=allow_feedback,
                    perception=perception,
                )
            )
        return compute_summary("bandit-cascade", outcomes)

    def save_results(self, summary: EvaluationSummary) -> tuple[Path, Path]:
        """Save ``summary`` as both JSON and CSV, timestamped, under results_dir.

        Returns:
            (json_path, csv_path)
        """

        self.results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = self.results_dir / f"evaluation_{timestamp}.json"
        csv_path = self.results_dir / f"evaluation_{timestamp}.csv"

        json_path.write_text(
            json.dumps(summary.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["task_id", "instruction", "planner_name", "success", "steps",
                 "execution_time_seconds", "failure_reason", "replanned"]
            )
            for outcome in summary.task_results:
                writer.writerow(
                    [
                        outcome.task_id,
                        outcome.instruction,
                        outcome.planner_name,
                        outcome.success,
                        outcome.steps,
                        f"{outcome.execution_time_seconds:.6f}",
                        outcome.failure_reason.value if outcome.failure_reason else "",
                        outcome.replanned,
                    ]
                )

        logger.info("Saved evaluation results to %s and %s", json_path, csv_path)
        return json_path, csv_path
