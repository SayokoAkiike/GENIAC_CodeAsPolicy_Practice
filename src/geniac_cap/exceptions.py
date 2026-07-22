"""Custom exceptions for geniac_cap.

Using specific exception types (instead of generic Exception) makes it
possible for the Executor to catch failures and translate them into a
structured FailureReason without ever swallowing unexpected errors silently.
"""

from __future__ import annotations


class GeniacCapError(Exception):
    """Base class for all geniac_cap errors."""


class ObjectNotFoundError(GeniacCapError):
    """Raised when an action references an object that does not exist."""


class LocationNotFoundError(GeniacCapError):
    """Raised when an action references a location that does not exist."""


class PreconditionFailedError(GeniacCapError):
    """Raised when an action's preconditions are not met (e.g. pick without being co-located)."""


class InvalidActionError(GeniacCapError):
    """Raised when an action name is not in the executor's whitelist."""


class InvalidArgumentError(GeniacCapError):
    """Raised when an action's arguments are missing or malformed."""


class MaxStepsExceededError(GeniacCapError):
    """Raised when a plan exceeds the maximum allowed number of execution steps."""


class TaskLoadError(GeniacCapError):
    """Raised when a task definition file cannot be parsed or is malformed."""


class PlanningError(GeniacCapError):
    """Raised when a Planner cannot produce a plan for a given instruction."""
