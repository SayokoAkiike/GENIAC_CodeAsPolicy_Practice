"""Tests for RuleBasedPlanner."""

from __future__ import annotations

import pytest

from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.exceptions import PlanningError
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.models import ActionName
from geniac_cap.planners.base import PlanningContext
from geniac_cap.planners.rule_based import RuleBasedPlanner
from geniac_cap.tasks.loader import load_tasks


def test_rule_based_planner_plans_basic_japanese_task():
    context = PlanningContext(
        objects=["red_block"],
        locations=["table", "blue_shelf"],
        object_locations={"red_block": "table"},
        robot_location="table",
    )
    plan = RuleBasedPlanner().plan("赤いブロックを青い棚に置いてください", context)
    actions = [step.action for step in plan.steps]
    assert actions == [ActionName.MOVE_TO, ActionName.PICK, ActionName.MOVE_TO, ActionName.PLACE]
    assert plan.steps[1].args["object_name"] == "red_block"
    assert plan.steps[-1].args["target_location"] == "blue_shelf"


def test_rule_based_planner_plans_basic_english_task():
    context = PlanningContext(
        objects=["red_block"],
        locations=["table", "blue_shelf"],
        object_locations={"red_block": "table"},
        robot_location="table",
    )
    plan = RuleBasedPlanner().plan("Move the red block to the blue shelf", context)
    assert plan.steps[1].args["object_name"] == "red_block"
    assert plan.steps[-1].args["target_location"] == "blue_shelf"


def test_rule_based_planner_raises_planning_error_for_unsupported_instruction():
    context = PlanningContext(objects=[], locations=[], object_locations={}, robot_location="table")
    with pytest.raises(PlanningError):
        RuleBasedPlanner().plan("空を飛んでください", context)


@pytest.mark.parametrize("task_index", range(12))
def test_rule_based_planner_executes_successfully_on_every_sample_task(task_index):
    tasks = load_tasks()
    task = tasks[task_index]
    env = ToyRobotEnv.from_task_state(task.initial_state)
    context = PlanningContext(
        objects=env.list_objects(),
        locations=env.list_locations(),
        object_locations=dict(env.state.object_locations),
        robot_location=env.state.robot_location,
    )
    plan = RuleBasedPlanner().plan(task.instruction, context)
    result = SafeExecutor().execute(env, plan, task.goal_state)
    assert result.success is True, f"Task {task.task_id} failed: {result.failure_reason}"
