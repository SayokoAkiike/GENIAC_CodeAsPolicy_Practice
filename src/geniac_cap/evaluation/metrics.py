"""Pure functions that turn a list of TaskOutcome into an EvaluationSummary."""

from __future__ import annotations

from geniac_cap.models import EvaluationSummary, FailureReason, TaskOutcome


def compute_summary(planner_name: str, outcomes: list[TaskOutcome]) -> EvaluationSummary:
    """Aggregate a list of per-task outcomes into overall metrics."""

    total = len(outcomes)
    successful = sum(1 for o in outcomes if o.success)
    failed = total - successful

    planning_errors = sum(1 for o in outcomes if o.failure_reason == FailureReason.PLANNING_ERROR)
    invalid_action_errors = sum(
        1 for o in outcomes if o.failure_reason == FailureReason.INVALID_ACTION
    )
    execution_errors = sum(
        1
        for o in outcomes
        if o.failure_reason is not None
        and o.failure_reason not in (FailureReason.PLANNING_ERROR, FailureReason.INVALID_ACTION)
    )

    failure_breakdown: dict[str, int] = {}
    for o in outcomes:
        if o.failure_reason is not None:
            key = o.failure_reason.value
            failure_breakdown[key] = failure_breakdown.get(key, 0) + 1

    avg_steps = sum(o.steps for o in outcomes) / total if total else 0.0
    avg_time = sum(o.execution_time_seconds for o in outcomes) / total if total else 0.0

    return EvaluationSummary(
        planner_name=planner_name,
        total_tasks=total,
        successful_tasks=successful,
        failed_tasks=failed,
        success_rate=(successful / total) if total else 0.0,
        planning_error_count=planning_errors,
        execution_error_count=execution_errors,
        invalid_action_count=invalid_action_errors,
        average_steps=avg_steps,
        average_execution_time=avg_time,
        failure_breakdown=failure_breakdown,
        task_results=outcomes,
    )
