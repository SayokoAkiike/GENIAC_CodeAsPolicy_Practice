"""Planner abstraction.

Every planner (rule-based, Anthropic, Gemini today; OpenAI/local-model
planners in the future) implements the same ``BasePlanner`` interface, so
the rest of the pipeline (Executor, Evaluator, CLI) never needs to know
which kind of planner produced a given ActionPlan.

Future extension points (not implemented yet, intentionally):
  * OpenAIPlanner(BasePlanner)   -- would call the OpenAI API
  * LocalModelPlanner(BasePlanner) -- would call a locally hosted model
These can be added without changing PlanningContext, ActionPlan, or the
Executor, as long as they return a valid ActionPlan.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from geniac_cap.models import ActionPlan


@dataclass
class PlanningContext:
    """Everything a planner is allowed to know about the current world.

    This deliberately mirrors what a real robot's perception/state system
    would expose (known objects, known locations, current object positions),
    without giving the planner direct access to the environment object.
    """

    objects: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    object_locations: dict[str, str] = field(default_factory=dict)
    robot_location: str = ""


class BasePlanner(ABC):
    """Abstract base class that all planners must implement."""

    name: str = "base"

    #: Whether this planner supports single-retry feedback-driven replanning
    #: (see ``replan``). The Evaluator checks this attribute -- not the
    #: planner's concrete type -- so any planner can opt in.
    supports_feedback: bool = False

    @abstractmethod
    def plan(self, instruction: str, context: PlanningContext) -> ActionPlan:
        """Turn a natural-language instruction into an ActionPlan.

        Implementations should raise ``geniac_cap.exceptions.PlanningError``
        (not a generic Exception) when they cannot produce a plan.
        """

        raise NotImplementedError

    def replan(self, instruction: str, context: PlanningContext, feedback: str) -> ActionPlan:
        """Produce a corrected plan after a failed execution attempt.

        Only called by the Evaluator when ``supports_feedback`` is True and
        the first attempt failed. ``feedback`` is a short, structured
        description of why the previous plan failed (see
        ``evaluation.evaluator._build_failure_feedback``). The default
        implementation raises NotImplementedError; planners that opt in via
        ``supports_feedback = True`` must override this.
        """

        raise NotImplementedError(f"{type(self).__name__} does not implement replan()")
