"""Tests for the contextual bandit (Step 5 of docs/model-improvement-roadmap.md)."""

from __future__ import annotations

import pytest

from geniac_cap.evaluation.bandit import EpsilonGreedyBandit, run_bandit_episode
from geniac_cap.evaluation.evaluator import Evaluator
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.models import Action, ActionName, ActionPlan
from geniac_cap.planners.base import BasePlanner, PlanningContext
from geniac_cap.tasks.loader import get_task_by_id


class _SpyPlanner(BasePlanner):
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
    return [
        Action(action=ActionName.PICK, args={"object_name": "red_block"}),
        Action(action=ActionName.PLACE, args={"target_location": "blue_shelf"}),
    ]


def test_bandit_requires_at_least_one_arm():
    with pytest.raises(ValueError):
        EpsilonGreedyBandit(arms=[])


def test_bandit_tries_every_arm_at_least_once_before_exploiting():
    bandit = EpsilonGreedyBandit(arms=[("a",), ("b",), ("c",)], epsilon=0.0, seed=0)
    seen = set()
    for _ in range(3):
        arm = bandit.select_arm("easy")
        seen.add(arm)
        bandit.update("easy", arm, reward=0.5)
    assert seen == {("a",), ("b",), ("c",)}


def test_bandit_exploits_the_best_arm_when_epsilon_is_zero():
    bandit = EpsilonGreedyBandit(arms=[("a",), ("b",)], epsilon=0.0, seed=0)
    # Force both arms to be tried once.
    bandit.update("easy", ("a",), reward=0.2)
    bandit.update("easy", ("b",), reward=0.9)
    # With epsilon=0, selection should now always exploit the best arm.
    for _ in range(5):
        assert bandit.select_arm("easy") == ("b",)


def test_bandit_contexts_are_independent():
    bandit = EpsilonGreedyBandit(arms=[("a",), ("b",)], epsilon=0.0, seed=0)
    bandit.update("easy", ("a",), reward=1.0)
    bandit.update("easy", ("b",), reward=0.0)
    bandit.update("hard", ("a",), reward=0.0)
    bandit.update("hard", ("b",), reward=1.0)
    assert bandit.best_arm("easy") == ("a",)
    assert bandit.best_arm("hard") == ("b",)


def test_bandit_best_arm_is_none_before_any_updates():
    bandit = EpsilonGreedyBandit(arms=[("a",)], epsilon=0.0, seed=0)
    assert bandit.best_arm("easy") is None


def test_run_bandit_episode_prefers_cheaper_tier_on_success():
    tier1 = _SpyPlanner("tier1", _correct_plan_for_task_001())
    tier2 = _SpyPlanner("tier2", _correct_plan_for_task_001())
    task = get_task_by_id("task_001")

    bandit = EpsilonGreedyBandit(arms=[("tier1",), ("tier1", "tier2")], epsilon=0.0, seed=0)
    factories = {"tier1": lambda: tier1, "tier2": lambda: tier2}

    # Run enough episodes to get past the "try every arm once" phase and
    # into exploitation.
    for _ in range(2):
        run_bandit_episode(task, bandit, factories, SafeExecutor())

    best = bandit.best_arm(task.difficulty.value)
    assert best == ("tier1",)  # cheaper arm: same success, no wasted tier-2 call


def test_run_bandit_episode_updates_reward_zero_on_failure():
    tier1 = _SpyPlanner("tier1", _broken_plan())
    task = get_task_by_id("task_001")

    bandit = EpsilonGreedyBandit(arms=[("tier1",)], epsilon=0.0, seed=0)
    factories = {"tier1": lambda: tier1}

    run_bandit_episode(task, bandit, factories, SafeExecutor(), allow_feedback=False)

    stats = bandit._stats[task.difficulty.value][("tier1",)]
    assert stats.pulls == 1
    assert stats.average_reward == 0.0


def test_evaluator_evaluate_bandit_runs_all_tasks(tmp_path):
    task = get_task_by_id("task_001")
    tier1 = _SpyPlanner("tier1", _correct_plan_for_task_001())
    bandit = EpsilonGreedyBandit(arms=[("tier1",)], epsilon=0.0, seed=0)
    factories = {"tier1": lambda: tier1}

    evaluator = Evaluator(results_dir=tmp_path)
    summary = evaluator.evaluate_bandit([task, task], bandit, factories)

    assert summary.total_tasks == 2
    assert summary.planner_name == "bandit-cascade"
