"""Whitelist-based validation for actions before they are ever executed.

This is the core safety mechanism requested by the project: the Executor
never ``exec()``s arbitrary code. It only calls a fixed set of environment
methods, and only after checking the action name and its arguments here.
"""

from __future__ import annotations

from geniac_cap.exceptions import InvalidActionError, InvalidArgumentError
from geniac_cap.models import Action, ActionName

# Required argument names per action. Every argument listed here must be
# present (any extra/unknown args are ignored, not rejected, to stay lenient
# with planners that might add optional metadata later).
REQUIRED_ARGS: dict[ActionName, tuple[str, ...]] = {
    ActionName.MOVE_TO: ("location",),
    ActionName.PICK: ("object_name",),
    ActionName.PLACE: ("target_location",),
    ActionName.INSPECT: ("object_name",),
    ActionName.WAIT: (),
    ActionName.RESET: (),
    ActionName.OPEN_CONTAINER: ("object_name",),
    ActionName.CLOSE_CONTAINER: ("object_name",),
}


def validate_action(action: Action) -> None:
    """Validate that ``action`` is whitelisted and has the required arguments.

    Raises:
        InvalidActionError: if the action name is not whitelisted.
        InvalidArgumentError: if a required argument is missing or not a string.
    """

    if action.action not in REQUIRED_ARGS:
        raise InvalidActionError(f"Action '{action.action}' is not in the execution whitelist")

    required = REQUIRED_ARGS[action.action]
    for arg_name in required:
        if arg_name not in action.args:
            raise InvalidArgumentError(
                f"Action '{action.action.value}' is missing required argument '{arg_name}'"
            )
        value = action.args[arg_name]
        if not isinstance(value, str) or not value.strip():
            raise InvalidArgumentError(
                f"Action '{action.action.value}' argument '{arg_name}' must be a non-empty string"
            )
