"""Safe, whitelist-based execution of ActionPlans against a ToyRobotEnv.

Design principle (see project README / architecture.md): this executor
NEVER calls ``exec()`` or ``eval()`` on arbitrary text. It only ever invokes
one of a small, fixed set of environment methods, after validating the
action name and arguments in ``validation.py``.
"""

from __future__ import annotations

import time
from typing import Any

from geniac_cap.config import MAX_EXECUTION_STEPS
from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.exceptions import (
    GeniacCapError,
    InvalidActionError,
    InvalidArgumentError,
    LocationNotFoundError,
    ObjectNotFoundError,
    PreconditionFailedError,
)
from geniac_cap.execution.validation import validate_action
from geniac_cap.models import (
    ActionName,
    ActionPlan,
    ExecutionResult,
    FailureReason,
    StepLog,
)
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)

_ERROR_TO_REASON: dict[type[Exception], FailureReason] = {
    ObjectNotFoundError: FailureReason.OBJECT_NOT_FOUND,
    LocationNotFoundError: FailureReason.LOCATION_NOT_FOUND,
    PreconditionFailedError: FailureReason.PRECONDITION_FAILED,
    InvalidActionError: FailureReason.INVALID_ACTION,
    InvalidArgumentError: FailureReason.INVALID_ARGUMENT,
}

# Maps whitelisted action names to the ToyRobotEnv method that implements them
# and the keyword-argument name(s) each method expects.
_ACTION_DISPATCH: dict[ActionName, str] = {
    ActionName.MOVE_TO: "move_to",
    ActionName.PICK: "pick",
    ActionName.PLACE: "place",
    ActionName.INSPECT: "inspect",
    ActionName.WAIT: "wait",
    ActionName.RESET: "reset",
    ActionName.OPEN_CONTAINER: "open_container",
    ActionName.CLOSE_CONTAINER: "close_container",
}


class SafeExecutor:
    """Executes a validated ActionPlan step-by-step against a ToyRobotEnv."""

    def __init__(self, max_steps: int = MAX_EXECUTION_STEPS) -> None:
        self.max_steps = max_steps

    def execute(
        self,
        env: ToyRobotEnv,
        plan: ActionPlan,
        goal_state: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Run ``plan`` against ``env`` and return a structured ExecutionResult."""

        start = time.perf_counter()
        logs: list[StepLog] = []
        failure_reason: FailureReason | None = None
        success = True

        if len(plan) > self.max_steps:
            elapsed = time.perf_counter() - start
            logger.error("Plan has %d steps, exceeding max_steps=%d", len(plan), self.max_steps)
            return ExecutionResult(
                success=False,
                goal_achieved=False,
                steps_executed=0,
                logs=[],
                failure_reason=FailureReason.MAX_STEPS_EXCEEDED,
                final_state=env.get_state(),
                execution_time_seconds=elapsed,
            )

        steps_executed = 0
        for i, action in enumerate(plan.steps):
            try:
                validate_action(action)
                method_name = _ACTION_DISPATCH[action.action]
                method = getattr(env, method_name)
                message = method(**action.args)
                logs.append(
                    StepLog(step_index=i, action=action.action.value, args=action.args,
                             success=True, message=str(message))
                )
                steps_executed += 1
                logger.debug("Step %d OK: %s", i, action)
            except GeniacCapError as exc:
                reason = _ERROR_TO_REASON.get(type(exc), FailureReason.UNEXPECTED_ERROR)
                logs.append(
                    StepLog(
                        step_index=i,
                        action=action.action.value,
                        args=action.args,
                        success=False,
                        message=str(exc),
                        failure_reason=reason,
                    )
                )
                logger.warning("Step %d FAILED (%s): %s", i, reason.value, exc)
                success = False
                failure_reason = reason
                break
            except Exception as exc:  # pragma: no cover - safety net, not swallowed silently
                logs.append(
                    StepLog(
                        step_index=i,
                        action=action.action.value,
                        args=action.args,
                        success=False,
                        message=f"Unexpected error: {exc}",
                        failure_reason=FailureReason.UNEXPECTED_ERROR,
                    )
                )
                logger.exception("Step %d raised an unexpected error", i)
                success = False
                failure_reason = FailureReason.UNEXPECTED_ERROR
                break

        goal_achieved = False
        if success and goal_state is not None:
            goal_achieved = env.check_goal(goal_state)
            if not goal_achieved:
                success = False
                failure_reason = FailureReason.GOAL_NOT_ACHIEVED
                logger.warning("Plan executed but goal_state was not achieved")

        elapsed = time.perf_counter() - start
        return ExecutionResult(
            success=success,
            goal_achieved=goal_achieved,
            steps_executed=steps_executed,
            logs=logs,
            failure_reason=failure_reason,
            final_state=env.get_state(),
            execution_time_seconds=elapsed,
        )


# ---------------------------------------------------------------------------
# Future extension points (Phase 5+ in docs/roadmap.md): these are placeholder
# interfaces only. They are NOT wired into the CLI/Evaluator today, and no
# code path in this project calls exec()/eval() on model-generated text.
# ---------------------------------------------------------------------------


class CodeParser:  # pragma: no cover - interface stub for future use
    """Future extension point: parse LLM-generated Python "policy code" into
    a validated ActionPlan (or reject it), without ever executing it directly.
    """

    def parse(self, source_code: str) -> ActionPlan:
        raise NotImplementedError(
            "CodeParser is a placeholder for a future phase; only structured "
            "ActionPlans are supported today."
        )


class SafeCodeExecutor:  # pragma: no cover - interface stub for future use
    """Future extension point: execute a restricted subset of generated code
    in a sandboxed way (e.g. AST allow-listing) and translate the result into
    an ExecutionResult. Not implemented in this initial version.
    """

    def run(self, source_code: str, env: ToyRobotEnv) -> ExecutionResult:
        raise NotImplementedError(
            "SafeCodeExecutor is a placeholder for a future phase; use "
            "SafeExecutor.execute() with a structured ActionPlan instead."
        )
