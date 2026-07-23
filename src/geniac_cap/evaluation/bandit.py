"""Contextual multi-armed bandit for planner-cascade selection (Step 5 of
the zero-budget model-improvement roadmap; see
docs/model-improvement-roadmap.md).

This is genuine reinforcement learning -- an epsilon-greedy bandit learns,
from ToyRobotEnv's free, deterministic reward signal, which planner
*cascade order* (see evaluation/cascade.py) tends to work best for a given
task's difficulty label. It's a small, illustrative decision space (a
handful of cascade orderings), not a demonstration of RL at scale, but it
costs nothing to run since rewards come from local simulation, not API
calls -- only the actually-selected cascade tier makes API calls, exactly
as in a plain cascade.

Honest note: the "context" here is just task.difficulty (easy/medium/hard),
a coarse signal already present in the task metadata. A richer contextual
bandit could use more features (category, object/location counts), but
this keeps the mechanism easy to inspect and test.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass

from geniac_cap.evaluation.evaluator import run_single_task
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.models import TaskDefinition, TaskOutcome
from geniac_cap.perception.base import BasePerception
from geniac_cap.planners.base import BasePlanner
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)

# Small per-tier penalty so that, among equally-successful arms, cheaper
# (shorter / cheaper-first) cascades are preferred -- success still always
# dominates (0.05 * tier_index can never flip a success below a failure's 0.0
# for any realistic arm length).
_TIER_PENALTY = 0.05


@dataclass
class BanditStats:
    """Running statistics for one (context, arm) pair."""

    pulls: int = 0
    total_reward: float = 0.0

    @property
    def average_reward(self) -> float:
        return self.total_reward / self.pulls if self.pulls else 0.0


class EpsilonGreedyBandit:
    """Epsilon-greedy contextual bandit over a fixed set of arms.

    An "arm" is a tuple of planner names (a cascade order, e.g.
    ``("rule-based", "gemini")``); "context" is any hashable key describing
    the task (this project uses ``task.difficulty.value``).
    """

    def __init__(
        self, arms: list[tuple[str, ...]], epsilon: float = 0.2, seed: int | None = None
    ) -> None:
        if not arms:
            raise ValueError("EpsilonGreedyBandit requires at least one arm")
        self.arms = list(arms)
        self.epsilon = epsilon
        self._rng = random.Random(seed)
        self._stats: dict[str, dict[tuple[str, ...], BanditStats]] = {}

    def _stats_for(self, context: str) -> dict[tuple[str, ...], BanditStats]:
        return self._stats.setdefault(context, {arm: BanditStats() for arm in self.arms})

    def select_arm(self, context: str) -> tuple[str, ...]:
        """Choose an arm for ``context``: try every arm once, then
        epsilon-greedy (explore with probability ``epsilon``, else exploit
        the best-known arm for this context).
        """

        stats = self._stats_for(context)
        untried = [arm for arm, s in stats.items() if s.pulls == 0]
        if untried:
            return self._rng.choice(untried)
        if self._rng.random() < self.epsilon:
            return self._rng.choice(self.arms)
        return max(stats.items(), key=lambda kv: kv[1].average_reward)[0]

    def update(self, context: str, arm: tuple[str, ...], reward: float) -> None:
        stats = self._stats_for(context)
        s = stats[arm]
        s.pulls += 1
        s.total_reward += reward

    def best_arm(self, context: str) -> tuple[str, ...] | None:
        """The arm with the highest average reward so far for ``context``,
        or None if nothing has been tried for it yet.
        """

        stats = self._stats.get(context)
        if not stats:
            return None
        tried = {arm: s for arm, s in stats.items() if s.pulls > 0}
        if not tried:
            return None
        return max(tried.items(), key=lambda kv: kv[1].average_reward)[0]

    def summary(self) -> dict[str, dict[str, dict]]:
        """A plain-dict snapshot of all contexts/arms/stats, for reporting."""

        return {
            context: {
                "->".join(arm): {"pulls": s.pulls, "average_reward": s.average_reward}
                for arm, s in arm_stats.items()
            }
            for context, arm_stats in self._stats.items()
        }


def run_bandit_episode(
    task: TaskDefinition,
    bandit: EpsilonGreedyBandit,
    planner_factories: dict[str, Callable[[], BasePlanner]],
    executor: SafeExecutor,
    allow_feedback: bool = True,
    perception: BasePerception | None = None,
) -> TaskOutcome:
    """Run one task: bandit selects a cascade arm, the arm runs as a normal
    planner cascade, and the bandit is updated with the observed reward.
    """

    from geniac_cap.evaluation.cascade import run_single_task_cascade

    context = task.difficulty.value
    arm = bandit.select_arm(context)
    planners = [planner_factories[name]() for name in arm]

    if len(planners) == 1:
        outcome = run_single_task(
            task, planners[0], executor, allow_feedback=allow_feedback, perception=perception
        )
    else:
        outcome = run_single_task_cascade(
            task, planners, executor, allow_feedback=allow_feedback, perception=perception
        )

    tier_index = arm.index(outcome.planner_name) if outcome.planner_name in arm else len(arm) - 1
    reward = (1.0 - _TIER_PENALTY * tier_index) if outcome.success else 0.0
    bandit.update(context, arm, reward)

    logger.info(
        "Task %s (context=%s): bandit chose arm %s, reward=%.2f",
        task.task_id,
        context,
        "->".join(arm),
        reward,
    )
    return outcome
