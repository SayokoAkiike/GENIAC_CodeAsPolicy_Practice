"""Tests for RuleBasedPlanner."""

from __future__ import annotations

import pytest

from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.exceptions import PlanningError
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.models import ActionName, FailureReason
from geniac_cap.planners.base import PlanningContext
from geniac_cap.planners.rule_based import RuleBasedPlanner
from geniac_cap.tasks.loader import get_task_by_id, load_tasks

# task_013 (container) and task_014 (two objects) are intentionally beyond
# RuleBasedPlanner's single-object, no-container pattern -- see the tests
# below and docs/experiment-log.md for why they're useful as a comparison
# point against LLM-backed planners.
SINGLE_OBJECT_TASK_IDS = [f"task_{i:03d}" for i in range(1, 13)]


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


def test_rule_based_planner_recognizes_vocabulary_harvested_via_groq():
    """Regression test for the 7 synonyms harvested for real via
    `harvest-vocabulary --provider groq` and merged into rule_based.py on
    2026-07-24 -- see docs/experiment-log.md.
    """

    context = PlanningContext(
        objects=["red_block", "cup", "water_bottle", "medicine_box", "notebook", "documents"],
        locations=["table", "blue_shelf", "kitchen"],
        object_locations={
            "red_block": "table",
            "cup": "table",
            "water_bottle": "table",
            "medicine_box": "table",
            "notebook": "table",
            "documents": "table",
        },
        robot_location="table",
    )
    cases = [
        ("Move the crimson block to the blue shelf", "red_block", "blue_shelf"),
        ("Move the mug to the blue shelf", "cup", "blue_shelf"),
        ("Move the flask to the blue shelf", "water_bottle", "blue_shelf"),
        ("Move the pill box to the blue shelf", "medicine_box", "blue_shelf"),
        ("Move the notepad to the blue shelf", "notebook", "blue_shelf"),
        ("Move the paperwork to the blue shelf", "documents", "blue_shelf"),
        ("Move the red block to the kitchenette", "red_block", "kitchen"),
    ]
    for instruction, expected_object, expected_location in cases:
        plan = RuleBasedPlanner().plan(instruction, context)
        assert plan.steps[1].args["object_name"] == expected_object, instruction
        assert plan.steps[-1].args["target_location"] == expected_location, instruction


def test_rule_based_planner_raises_planning_error_for_unsupported_instruction():
    context = PlanningContext(objects=[], locations=[], object_locations={}, robot_location="table")
    with pytest.raises(PlanningError):
        RuleBasedPlanner().plan("空を飛んでください", context)


@pytest.mark.parametrize("task_id", SINGLE_OBJECT_TASK_IDS)
def test_rule_based_planner_executes_successfully_on_every_single_object_task(task_id):
    task = get_task_by_id(task_id)
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


def test_all_sample_tasks_are_covered_by_the_id_lists():
    """Guards against silently forgetting to classify a newly added task."""

    all_ids = {task.task_id for task in load_tasks()}
    assert all_ids == set(SINGLE_OBJECT_TASK_IDS) | {"task_013", "task_014"}


def test_rule_based_planner_cannot_solve_the_container_task():
    """Documents a known limitation: RuleBasedPlanner never emits open_container,
    so a task that requires opening a container before placing something inside
    it fails on a precondition. This is exactly the kind of task an LLM-backed
    planner (AnthropicPlanner / GeminiPlanner) can be compared against.
    """

    task = get_task_by_id("task_013")
    env = ToyRobotEnv.from_task_state(task.initial_state)
    context = PlanningContext(
        objects=env.list_objects(),
        locations=env.list_locations(),
        object_locations=dict(env.state.object_locations),
        robot_location=env.state.robot_location,
    )
    plan = RuleBasedPlanner().plan(task.instruction, context)
    result = SafeExecutor().execute(env, plan, task.goal_state)
    assert result.success is False
    assert result.failure_reason == FailureReason.PRECONDITION_FAILED


def test_rule_based_planner_cannot_solve_the_two_object_task():
    """Documents a known limitation: RuleBasedPlanner only extracts and moves
    a single object per instruction, so a task requiring two objects to reach
    their goal locations only ever moves one of them.
    """

    task = get_task_by_id("task_014")
    env = ToyRobotEnv.from_task_state(task.initial_state)
    context = PlanningContext(
        objects=env.list_objects(),
        locations=env.list_locations(),
        object_locations=dict(env.state.object_locations),
        robot_location=env.state.robot_location,
    )
    plan = RuleBasedPlanner().plan(task.instruction, context)
    result = SafeExecutor().execute(env, plan, task.goal_state)
    assert result.success is False
    assert result.failure_reason == FailureReason.GOAL_NOT_ACHIEVED
