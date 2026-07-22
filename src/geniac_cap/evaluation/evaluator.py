"""Runs a batch of tasks through a given Planner + SafeExecutor and reports metrics."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

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
from geniac_cap.planners.base import BasePlanner, PlanningContext
from geniac_cap.planners.feedback import FeedbackPlanner
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)


def _build_context(env: ToyRobotEnv) -> PlanningContext:
    return PlanningContext(
        objects=env.list_objects(),
        locations=env.list_locations(),
        object_locations=dict(env.state.object_locations),
        robot_location=env.state.robot_location,
    )


def run_single_task(
    task: TaskDefinition,
    planner: BasePlanner,
    executor: SafeExecutor,
    allow_feedback: bool = True,
) -> TaskOutcome:
    """Run one task through ``planner`` + ``executor`` and return its outcome.

    If ``planner`` is a FeedbackPlanner, execution fails, and ``allow_feedback``
    is True, the environment is reset and exactly one replanning attempt is
    made using the planner's ``replan`` method.
    """

    env = ToyRobotEnv.from_task_state(task.initial_state)
    context = _build_context(env)

    logger.info("Starting task %s: '%s'", task.task_id, task.instruction)

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

    if not result.success and allow_feedback and isinstance(planner, FeedbackPlanner):
        logger.info("Task %s failed; attempting one feedback-driven replan", task.task_id)
        env.reset()
        try:
            repaired_plan = planner.replan(task.instruction, context)
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
    ) -> EvaluationSummary:
        """Run every task in ``tasks`` and return an aggregated EvaluationSummary."""

        outcomes = [
            run_single_task(task, planner, self.executor, allow_feedback=allow_feedback)
            for task in tasks
        ]
        return compute_summary(planner.name, outcomes)

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
