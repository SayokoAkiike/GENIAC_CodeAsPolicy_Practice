"""Planner abstraction.

Every planner (rule-based today; OpenAI/Anthropic/local-model planners in the
future) implements the same ``BasePlanner`` interface, so the rest of the
pipeline (Executor, Evaluator, CLI) never needs to know which kind of planner
produced a given ActionPlan.

Future extension points (not implemented yet, intentionally):
  * OpenAIPlanner(BasePlanner)   -- would call the OpenAI API
  * AnthropicPlanner(BasePlanner) -- would call the Anthropic API
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

    @abstractmethod
    def plan(self, instruction: str, context: PlanningContext) -> ActionPlan:
        """Turn a natural-language instruction into an ActionPlan.

        Implementations should raise ``geniac_cap.exceptions.PlanningError``
        (not a generic Exception) when they cannot produce a plan.
        """

        raise NotImplementedError
