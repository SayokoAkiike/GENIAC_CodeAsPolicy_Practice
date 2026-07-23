"""The default, non-vision perception: read the environment state directly.

This is exactly what the Evaluator did before Phase 4 (see the old
``_build_context`` helper) -- it's now formalized as a ``BasePerception``
implementation so it can be swapped for ``VLMPerception`` behind the same
interface.
"""

from __future__ import annotations

from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.perception.base import BasePerception
from geniac_cap.planners.base import PlanningContext


class GroundTruthPerception(BasePerception):
    """Builds a PlanningContext directly from the environment's true state."""

    name = "ground-truth"

    def perceive(self, env: ToyRobotEnv) -> PlanningContext:
        return PlanningContext(
            objects=env.list_objects(),
            locations=env.list_locations(),
            object_locations=dict(env.state.object_locations),
            robot_location=env.state.robot_location,
        )
