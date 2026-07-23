"""Tests for synthetic task generation (Step 2 of
docs/model-improvement-roadmap.md).
"""

from __future__ import annotations

from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.models import FailureReason
from geniac_cap.planners.base import PlanningContext
from geniac_cap.planners.rule_based import RuleBasedPlanner
from geniac_cap.tasks.generator import (
    generate_container_tasks,
    generate_single_object_tasks,
    generate_tasks,
    generate_two_object_tasks,
)
from geniac_cap.tasks.loader import load_tasks_from_file, save_tasks_to_yaml


def _run_with_rule_based(task):
    env = ToyRobotEnv.from_task_state(task.initial_state)
    context = PlanningContext(
        objects=env.list_objects(),
        locations=env.list_locations(),
        object_locations=dict(env.state.object_locations),
        robot_location=env.state.robot_location,
    )
    plan = RuleBasedPlanner().plan(task.instruction, context)
    return SafeExecutor().execute(env, plan, task.goal_state)


def test_generate_single_object_tasks_are_solvable_by_rule_based_planner():
    tasks = generate_single_object_tasks(count=6, seed=1)
    assert len(tasks) == 6
    for task in tasks:
        result = _run_with_rule_based(task)
        assert result.success is True, f"{task.task_id} failed: {result.failure_reason}"


def test_generate_two_object_tasks_fail_rule_based_planner_as_documented():
    tasks = generate_two_object_tasks(count=4, seed=1)
    assert len(tasks) == 4
    for task in tasks:
        result = _run_with_rule_based(task)
        assert result.success is False
        assert result.failure_reason == FailureReason.GOAL_NOT_ACHIEVED


def test_generate_container_tasks_fail_rule_based_planner_as_documented():
    tasks = generate_container_tasks(count=4, seed=1)
    assert len(tasks) == 4
    for task in tasks:
        result = _run_with_rule_based(task)
        assert result.success is False
        assert result.failure_reason == FailureReason.PRECONDITION_FAILED


def test_generate_tasks_produces_unique_task_ids():
    tasks = generate_tasks(n_single=5, n_two_object=3, n_container=3, seed=7)
    assert len(tasks) == 11
    task_ids = [t.task_id for t in tasks]
    assert len(task_ids) == len(set(task_ids))


def test_generation_is_deterministic_given_the_same_seed():
    first = generate_tasks(n_single=4, n_two_object=2, n_container=2, seed=99)
    second = generate_tasks(n_single=4, n_two_object=2, n_container=2, seed=99)
    assert [t.model_dump() for t in first] == [t.model_dump() for t in second]


def test_different_seeds_produce_different_tasks():
    first = generate_single_object_tasks(count=5, seed=1)
    second = generate_single_object_tasks(count=5, seed=2)
    assert [t.instruction for t in first] != [t.instruction for t in second]


def test_save_and_reload_round_trip(tmp_path):
    tasks = generate_tasks(n_single=3, n_two_object=2, n_container=2, seed=5)
    output_path = save_tasks_to_yaml(tasks, tmp_path / "synthetic.yaml")

    reloaded = load_tasks_from_file(output_path)
    assert len(reloaded) == len(tasks)
    assert [t.task_id for t in reloaded] == [t.task_id for t in tasks]
    assert [t.instruction for t in reloaded] == [t.instruction for t in tasks]
