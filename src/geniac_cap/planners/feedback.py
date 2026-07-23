"""Execution feedback / single-retry replanning.

To make the value of feedback visible, this module also defines
``NaivePlanner``: a deliberately incomplete planner that picks and places an
object *without* first moving the robot to the right locations. Executing a
NaivePlanner plan directly typically fails on a precondition
(PreconditionFailedError -> FailureReason.PRECONDITION_FAILED).

``FeedbackPlanner`` wraps NaivePlanner. When the orchestrator (see
``evaluation/evaluator.py``) detects a failed execution, it asks
``FeedbackPlanner.replan(...)`` for a corrected plan built from the failure
feedback text, and retries exactly once. This is intentionally simple
(rule-based repair, not a real multi-turn agent) but the same interface can
later be swapped for an LLM-driven replanner.
"""

from __future__ import annotations

from geniac_cap.models import Action, ActionName, ActionPlan
from geniac_cap.planners.base import BasePlanner, PlanningContext
from geniac_cap.planners.rule_based import RuleBasedPlanner, _find_destination, _find_object
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)


class NaivePlanner(BasePlanner):
    """A deliberately incomplete planner used to demonstrate feedback repair.

    It identifies the object and destination correctly (reusing the same
    extraction helpers as RuleBasedPlanner) but skips the move_to steps,
    which will normally cause pick/place preconditions to fail.
    """

    name = "naive"

    def plan(self, instruction: str, context: PlanningContext) -> ActionPlan:
        object_name = _find_object(instruction, context)
        source_location = context.object_locations.get(object_name, "")
        destination = _find_destination(instruction, context, source_location)
        steps = [
            Action(action=ActionName.PICK, args={"object_name": object_name}),
            Action(action=ActionName.PLACE, args={"target_location": destination}),
        ]
        return ActionPlan(steps=steps)


def build_feedback_text(object_name: str, robot_location: str, object_location: str) -> str:
    """Build a short, structured feedback string describing why execution failed.

    Mirrors the style requested in the spec, e.g.:
    "Object red_block is at table. Robot is at kitchen."
    """

    return f"Object {object_name} is at {object_location}. Robot is at {robot_location}."


class FeedbackPlanner(BasePlanner):
    """Planner that starts naive and repairs its own plan once, given feedback.

    ``plan()`` alone returns the naive (likely-to-fail) plan, matching the
    BasePlanner interface. The Evaluator calls ``replan()`` after a failed
    execution to get the corrected, full plan.
    """

    name = "feedback"
    supports_feedback = True

    def __init__(self) -> None:
        self._naive = NaivePlanner()
        self._corrective = RuleBasedPlanner()

    def plan(self, instruction: str, context: PlanningContext) -> ActionPlan:
        return self._naive.plan(instruction, context)

    def replan(self, instruction: str, context: PlanningContext, feedback: str) -> ActionPlan:
        """Return a corrected plan that inserts the missing move_to steps.

        Reuses RuleBasedPlanner, which already knows how to build a full
        move -> pick -> move -> place sequence from the same context. The
        ``feedback`` text isn't needed here (the fix is derivable directly
        from ``context``) but is accepted for interface consistency with
        other planners (e.g. AnthropicPlanner, GeminiPlanner) that do use it.
        """

        logger.info(
            "FeedbackPlanner repairing plan for: '%s' (feedback: %s)", instruction, feedback
        )
        return self._corrective.plan(instruction, context)
