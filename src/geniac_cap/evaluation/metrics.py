"""Pure functions that turn a list of TaskOutcome into an EvaluationSummary,
plus helpers for comparing two summaries (Step 0 of the zero-budget model
improvement roadmap -- see docs/model-improvement-roadmap.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from geniac_cap.exceptions import GeniacCapError
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


class SummaryLoadError(GeniacCapError):
    """Raised when a saved evaluation summary JSON can't be loaded."""


def load_summary(path: Path | str) -> EvaluationSummary:
    """Load a previously saved evaluation JSON (see Evaluator.save_results)."""

    path = Path(path)
    if not path.exists():
        raise SummaryLoadError(f"Baseline results file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SummaryLoadError(f"Could not parse {path} as JSON: {exc}") from exc
    try:
        return EvaluationSummary.model_validate(data)
    except Exception as exc:
        raise SummaryLoadError(f"{path} does not look like an evaluation summary: {exc}") from exc


@dataclass
class SummaryComparison:
    """Delta between a baseline and a current EvaluationSummary."""

    baseline: EvaluationSummary
    current: EvaluationSummary

    @property
    def success_rate_delta(self) -> float:
        return self.current.success_rate - self.baseline.success_rate

    @property
    def average_steps_delta(self) -> float:
        return self.current.average_steps - self.baseline.average_steps

    def as_readme_row(self, change: str, pr_or_branch: str = "") -> str:
        """Format this comparison as a row ready to paste into README's
        "Model improvement log" table (see docs/model-improvement-roadmap.md).
        """

        sign = "+" if self.success_rate_delta >= 0 else ""
        result = (
            f"{self.baseline.planner_name}: "
            f"{self.baseline.success_rate:.0%}→{self.current.success_rate:.0%} "
            f"({sign}{self.success_rate_delta:.0%}), "
            f"avg steps {self.baseline.average_steps:.2f}→{self.current.average_steps:.2f}"
        )
        return f"| _ | {change} | {pr_or_branch} | {date.today().isoformat()} | {result} |"


def compare_summaries(baseline: EvaluationSummary, current: EvaluationSummary) -> SummaryComparison:
    """Compare two EvaluationSummary objects (typically same planner, before/after a change)."""

    return SummaryComparison(baseline=baseline, current=current)
