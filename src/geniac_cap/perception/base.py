"""Perception abstraction (Phase 4: vision / scene representation).

Every Planner today receives a ``PlanningContext`` built directly from the
environment's internal state (ground truth: exact object/location names,
positions, etc). This module introduces a ``BasePerception`` interface that
produces the *same* ``PlanningContext`` shape, but can be backed by
something less direct -- most interestingly, a rendered image of the scene
interpreted by a real vision-language model (VLM).

This keeps Planners unchanged: whichever ``BasePerception`` implementation
is used, the planner still just receives a ``PlanningContext``. Only the
Evaluator/CLI need to choose which perception source to use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.planners.base import PlanningContext


class BasePerception(ABC):
    """Abstract base class for turning a ToyRobotEnv into a PlanningContext."""

    name: str = "base"

    @abstractmethod
    def perceive(self, env: ToyRobotEnv) -> PlanningContext:
        """Return a PlanningContext describing the current state of ``env``.

        Implementations should raise ``geniac_cap.exceptions.PlanningError``
        (not a generic Exception) if perception fails (e.g. a VLM call
        errors out or returns something unparseable).
        """

        raise NotImplementedError
