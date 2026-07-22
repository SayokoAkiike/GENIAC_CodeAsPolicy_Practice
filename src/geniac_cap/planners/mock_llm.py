"""A mock "LLM" planner that does not call any external API.

This exists purely as an interface demonstration for what an
OpenAIPlanner / AnthropicPlanner / LocalModelPlanner would look like later:
same `plan()` signature, but backed by canned responses instead of a real
model call. It falls back to RuleBasedPlanner logic when no canned response
matches, so it can still be used in the demo/evaluate commands today.
"""

from __future__ import annotations

from geniac_cap.models import ActionPlan
from geniac_cap.planners.base import BasePlanner, PlanningContext
from geniac_cap.planners.rule_based import RuleBasedPlanner
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)


class MockLLMPlanner(BasePlanner):
    """Simulates an LLM-backed planner using a small lookup table.

    Args:
        canned_responses: Optional mapping of instruction -> ActionPlan to
            return verbatim, simulating pre-recorded model completions.
    """

    name = "mock-llm"

    def __init__(self, canned_responses: dict[str, ActionPlan] | None = None) -> None:
        self._canned_responses = canned_responses or {}
        # Reused so MockLLMPlanner still produces sensible plans for
        # instructions that are not in the canned-response table.
        self._fallback = RuleBasedPlanner()

    def plan(self, instruction: str, context: PlanningContext) -> ActionPlan:
        if instruction in self._canned_responses:
            logger.info("MockLLMPlanner returning canned response for: '%s'", instruction)
            return self._canned_responses[instruction]
        logger.info(
            "MockLLMPlanner has no canned response for '%s'; delegating to RuleBasedPlanner",
            instruction,
        )
        return self._fallback.plan(instruction, context)
