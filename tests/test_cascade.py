"""Tests for the planner cascade (Step 1 of docs/model-improvement-roadmap.md)."""

from __future__ import annotations

import pytest

from geniac_cap.evaluation.cascade import run_single_task_cascade
from geniac_cap.evaluation.evaluator import Evaluator
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.models import Action, ActionName, ActionPlan
from geniac_cap.planners.base import BasePlanner, PlanningContext
from geniac_cap.planners.rule_based import RuleBasedPlanner
from geniac_cap.tasks.loader import get_task_by_id


class _SpyPlanner(BasePlanner):
    """A planner that records whether plan() was ever called."""

    def __init__(self, name: str, steps: list[Action]) -> None:
        self.name = name
        self._steps = steps
        self.plan_call_count = 0

    def plan(self, instruction: str, context: PlanningContext) -> ActionPlan:
        self.plan_call_count += 1
        return ActionPlan(steps=self._steps)


def _correct_plan_for_task_001() -> list[Action]:
    return [
        Action(action=ActionName.MOVE_TO, args={"location": "table"}),
        Action(action=ActionName.PICK, args={"object_name": "red_block"}),
        Action(action=ActionName.MOVE_TO, args={"location": "blue_shelf"}),
        Action(action=ActionName.PLACE, args={"target_location": "blue_shelf"}),
    ]


def _broken_plan() -> list[Action]:
    # Missing move_to steps -> will fail on a precondition.
    return [
        Action(action=ActionName.PICK, args={"object_name": "red_block"}),
        Action(action=ActionName.PLACE, args={"target_location": "blue_shelf"}),
    ]


def test_cascade_does_not_call_later_planners_when_first_succeeds():
    tier1 = _SpyPlanner("tier1", _correct_plan_for_task_001())
    tier2 = _SpyPlanner("tier2", _correct_plan_for_task_001())
    task = get_task_by_id("task_001")

    outcome = run_single_task_cascade(task, [tier1, tier2], SafeExecutor())

    assert outcome.success is True
    assert outcome.planner_name == "tier1"
    assert tier1.plan_call_count == 1
    assert tier2.plan_call_count == 0  # never invoked


def test_cascade_falls_through_to_second_planner_on_failure():
    tier1 = _SpyPlanner("tier1", _broken_plan())
    tier2 = _SpyPlanner("tier2", _correct_plan_for_task_001())
    task = get_task_by_id("task_001")

    outcome = run_single_task_cascade(task, [tier1, tier2], SafeExecutor())

    assert outcome.success is True
    assert outcome.planner_name == "tier2"
    assert tier1.plan_call_count == 1
    assert tier2.plan_call_count == 1


def test_cascade_reports_last_planners_failure_when_all_fail():
    tier1 = _SpyPlanner("tier1", _broken_plan())
    tier2 = _SpyPlanner("tier2", _broken_plan())
    task = get_task_by_id("task_001")

    outcome = run_single_task_cascade(task, [tier1, tier2], SafeExecutor())

    assert outcome.success is False
    assert outcome.planner_name == "tier2"


def test_cascade_requires_at_least_one_planner():
    task = get_task_by_id("task_001")
    with pytest.raises(ValueError):
        run_single_task_cascade(task, [], SafeExecutor())


def test_evaluator_evaluate_cascade_labels_summary_with_the_chain(tmp_path):
    tier1 = _SpyPlanner("tier1", _correct_plan_for_task_001())
    tier2 = _SpyPlanner("tier2", _correct_plan_for_task_001())
    task = get_task_by_id("task_001")

    evaluator = Evaluator(results_dir=tmp_path)
    summary = evaluator.evaluate_cascade([task], [tier1, tier2])

    assert summary.planner_name == "cascade(tier1->tier2)"
    assert summary.success_rate == 1.0
    assert tier2.plan_call_count == 0


def test_cascade_with_real_rule_based_planner_solves_easy_tasks_alone():
    # Sanity check the real planner also participates correctly in a cascade.
    planner = RuleBasedPlanner()
    task = get_task_by_id("task_001")
    outcome = run_single_task_cascade(task, [planner], SafeExecutor())
    assert outcome.success is True
    assert outcome.planner_name == "rule-based"
