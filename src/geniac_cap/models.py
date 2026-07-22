"""Shared data models used across the environment, planners, executor and evaluator.

Keeping these in one place makes it easy to see the "shape" of data flowing
through the whole pipeline: Instruction -> Action(s) -> ExecutionResult -> ...
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ActionName(str, Enum):
    """Whitelisted action names. The Executor refuses anything not listed here."""

    MOVE_TO = "move_to"
    PICK = "pick"
    PLACE = "place"
    INSPECT = "inspect"
    WAIT = "wait"
    RESET = "reset"
    OPEN_CONTAINER = "open_container"
    CLOSE_CONTAINER = "close_container"


class Action(BaseModel):
    """A single structured robot action.

    Example:
        Action(action=ActionName.MOVE_TO, args={"location": "table"})
    """

    action: ActionName
    args: dict[str, Any] = Field(default_factory=dict)

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"{self.action.value}({self.args})"


class ActionPlan(BaseModel):
    """An ordered list of actions produced by a Planner."""

    steps: list[Action] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.steps)

    def __iter__(self):  # type: ignore[override]
        return iter(self.steps)


class FailureReason(str, Enum):
    """Structured failure categories used by the Executor / Evaluator."""

    PLANNING_ERROR = "planning_error"
    INVALID_ACTION = "invalid_action"
    INVALID_ARGUMENT = "invalid_argument"
    OBJECT_NOT_FOUND = "object_not_found"
    LOCATION_NOT_FOUND = "location_not_found"
    PRECONDITION_FAILED = "precondition_failed"
    GOAL_NOT_ACHIEVED = "goal_not_achieved"
    MAX_STEPS_EXCEEDED = "max_steps_exceeded"
    UNEXPECTED_ERROR = "unexpected_error"


class StepLog(BaseModel):
    """Log entry for a single executed (or rejected) action."""

    step_index: int
    action: str
    args: dict[str, Any] = Field(default_factory=dict)
    success: bool
    message: str = ""
    failure_reason: FailureReason | None = None


class ExecutionResult(BaseModel):
    """Result of executing an ActionPlan against the environment."""

    success: bool
    goal_achieved: bool
    steps_executed: int
    logs: list[StepLog] = Field(default_factory=list)
    failure_reason: FailureReason | None = None
    final_state: dict[str, Any] = Field(default_factory=dict)
    execution_time_seconds: float = 0.0
    replanned: bool = False


class TaskDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TaskCategory(str, Enum):
    HOUSEHOLD = "household"
    HEALTHCARE = "healthcare"
    OFFICE = "office"
    KITCHEN = "kitchen"


class TaskDefinition(BaseModel):
    """A single benchmark task, loadable from YAML."""

    task_id: str
    instruction: str
    initial_state: dict[str, Any]
    goal_state: dict[str, Any]
    difficulty: TaskDifficulty
    category: TaskCategory
    expected_objects: list[str] = Field(default_factory=list)
    expected_locations: list[str] = Field(default_factory=list)


class TaskOutcome(BaseModel):
    """Outcome of running one task through Planner + Executor."""

    task_id: str
    instruction: str
    planner_name: str
    success: bool
    steps: int
    execution_time_seconds: float
    failure_reason: FailureReason | None = None
    replanned: bool = False


class EvaluationSummary(BaseModel):
    """Aggregate metrics over a batch of TaskOutcome results."""

    planner_name: str
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    success_rate: float
    planning_error_count: int
    execution_error_count: int
    invalid_action_count: int
    average_steps: float
    average_execution_time: float
    failure_breakdown: dict[str, int] = Field(default_factory=dict)
    task_results: list[TaskOutcome] = Field(default_factory=list)
