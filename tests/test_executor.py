"""Tests for SafeExecutor: whitelist enforcement and plan execution."""

from __future__ import annotations

from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.models import Action, ActionName, ActionPlan, FailureReason


def make_env() -> ToyRobotEnv:
    return ToyRobotEnv(
        locations={"table", "shelf"},
        objects={"cup"},
        object_locations={"cup": "table"},
        robot_location="table",
    )


def test_executor_runs_a_valid_plan_successfully():
    env = make_env()
    plan = ActionPlan(
        steps=[
            Action(action=ActionName.MOVE_TO, args={"location": "table"}),
            Action(action=ActionName.PICK, args={"object_name": "cup"}),
            Action(action=ActionName.MOVE_TO, args={"location": "shelf"}),
            Action(action=ActionName.PLACE, args={"target_location": "shelf"}),
        ]
    )
    result = SafeExecutor().execute(env, plan, goal_state={"object_locations": {"cup": "shelf"}})
    assert result.success is True
    assert result.goal_achieved is True
    assert result.steps_executed == 4


def test_executor_stops_on_precondition_failure():
    env = make_env()
    plan = ActionPlan(
        steps=[
            Action(action=ActionName.PICK, args={"object_name": "cup"}),
            Action(action=ActionName.PLACE, args={"target_location": "shelf"}),
        ]
    )
    env.move_to("shelf")
    result = SafeExecutor().execute(env, plan)
    assert result.success is False
    assert result.failure_reason == FailureReason.PRECONDITION_FAILED


def test_executor_rejects_action_not_in_whitelist_via_model_validation():
    # ActionName is an Enum, so constructing an Action with a bad name fails
    # at the pydantic validation layer -- this proves the whitelist can't be bypassed.
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Action(action="delete_universe", args={})  # type: ignore[arg-type]


def test_executor_reports_max_steps_exceeded():
    env = make_env()
    plan = ActionPlan(steps=[Action(action=ActionName.WAIT, args={}) for _ in range(5)])
    result = SafeExecutor(max_steps=3).execute(env, plan)
    assert result.success is False
    assert result.failure_reason == FailureReason.MAX_STEPS_EXCEEDED


def test_executor_goal_not_achieved_reported_when_goal_state_unmet():
    env = make_env()
    plan = ActionPlan(steps=[Action(action=ActionName.WAIT, args={})])
    result = SafeExecutor().execute(env, plan, goal_state={"object_locations": {"cup": "shelf"}})
    assert result.success is False
    assert result.failure_reason == FailureReason.GOAL_NOT_ACHIEVED
