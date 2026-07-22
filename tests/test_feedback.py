"""Tests for NaivePlanner + FeedbackPlanner and the retry orchestration."""

from __future__ import annotations

from geniac_cap.evaluation.evaluator import run_single_task
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.planners.feedback import FeedbackPlanner, NaivePlanner
from geniac_cap.tasks.loader import get_task_by_id


def test_naive_planner_plan_omits_move_to_steps():
    from geniac_cap.planners.base import PlanningContext

    context = PlanningContext(
        objects=["cup"],
        locations=["table", "shelf"],
        object_locations={"cup": "table"},
        robot_location="table",
    )
    plan = NaivePlanner().plan("Move the cup to the shelf", context)
    names = {step.action.value for step in plan.steps}
    assert "move_to" not in names


def test_task_fails_without_feedback_when_using_naive_style_plan():
    task = get_task_by_id("task_003")
    outcome = run_single_task(task, FeedbackPlanner(), SafeExecutor(), allow_feedback=False)
    assert outcome.success is False


def test_task_succeeds_with_feedback_replanning():
    task = get_task_by_id("task_003")
    outcome = run_single_task(task, FeedbackPlanner(), SafeExecutor(), allow_feedback=True)
    assert outcome.success is True
    assert outcome.replanned is True
