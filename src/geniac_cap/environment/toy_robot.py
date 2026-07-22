"""A lightweight, pure-Python "Toy Robot Environment".

This intentionally avoids any physics simulator (no MuJoCo / Isaac Sim / ROS).
It models a robot that can move between named locations, pick up one object
at a time, place it, inspect objects, and open/close simple containers.

Extension point: later phases can replace this module with a wrapper around
a real simulator while keeping the same public method signatures, so
Planners and the Executor do not need to change.
"""

from __future__ import annotations

from typing import Any

from geniac_cap.environment.state import RobotState
from geniac_cap.exceptions import (
    LocationNotFoundError,
    ObjectNotFoundError,
    PreconditionFailedError,
)
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)


class ToyRobotEnv:
    """A minimal environment with locations, objects, and a single robot."""

    def __init__(
        self,
        locations: set[str],
        objects: set[str],
        object_locations: dict[str, str],
        robot_location: str,
        containers: set[str] | None = None,
    ) -> None:
        if robot_location not in locations:
            raise LocationNotFoundError(
                f"robot_location '{robot_location}' is not a known location"
            )
        for obj, loc in object_locations.items():
            if loc not in locations:
                raise LocationNotFoundError(f"Object '{obj}' placed at unknown location '{loc}'")

        self._initial_locations = set(locations)
        self._initial_objects = set(objects)
        self._initial_object_locations = dict(object_locations)
        self._initial_robot_location = robot_location
        self._containers = set(containers or set())

        self.state = RobotState(
            robot_location=robot_location,
            object_locations=dict(object_locations),
            locations=set(locations),
            objects=set(objects),
            container_open={c: False for c in self._containers},
        )

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_task_state(cls, initial_state: dict[str, Any]) -> ToyRobotEnv:
        """Build an environment from a TaskDefinition.initial_state dict.

        Expected keys: robot_location, object_locations, locations (optional),
        objects (optional), containers (optional).
        """

        object_locations: dict[str, str] = dict(initial_state.get("object_locations", {}))
        locations = set(initial_state.get("locations", set(object_locations.values())))
        locations.add(initial_state["robot_location"])
        objects = set(initial_state.get("objects", set(object_locations.keys())))
        containers = set(initial_state.get("containers", []))
        return cls(
            locations=locations,
            objects=objects,
            object_locations=object_locations,
            robot_location=initial_state["robot_location"],
            containers=containers,
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def list_objects(self) -> list[str]:
        """Return all known object names."""

        return sorted(self.state.objects)

    def list_locations(self) -> list[str]:
        """Return all known location names."""

        return sorted(self.state.locations)

    def get_state(self) -> dict[str, Any]:
        """Return a serializable snapshot of the current state."""

        return self.state.snapshot()

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def _require_location(self, location: str) -> None:
        if location not in self.state.locations:
            raise LocationNotFoundError(f"Unknown location: '{location}'")

    def _require_object(self, object_name: str) -> None:
        if object_name not in self.state.objects:
            raise ObjectNotFoundError(f"Unknown object: '{object_name}'")

    # ------------------------------------------------------------------
    # Core actions
    # ------------------------------------------------------------------
    def move_to(self, location: str) -> str:
        """Move the robot to ``location``. Fails if location is unknown."""

        self._require_location(location)
        self.state.robot_location = location
        msg = f"Robot moved to '{location}'"
        self.state.history.append(msg)
        logger.debug(msg)
        return msg

    def pick(self, object_name: str) -> str:
        """Pick up ``object_name``.

        Preconditions:
          * The object must exist.
          * The robot must not already be holding something.
          * The robot must be at the same location as the object.
        """

        self._require_object(object_name)
        if self.state.held_object is not None:
            raise PreconditionFailedError(
                f"Cannot pick '{object_name}': robot already holds '{self.state.held_object}'"
            )
        object_loc = self.state.object_locations.get(object_name)
        if object_loc != self.state.robot_location:
            raise PreconditionFailedError(
                f"Cannot pick '{object_name}': robot is at '{self.state.robot_location}' "
                f"but object is at '{object_loc}'"
            )
        self.state.held_object = object_name
        msg = f"Robot picked up '{object_name}'"
        self.state.history.append(msg)
        logger.debug(msg)
        return msg

    def place(self, target_location: str) -> str:
        """Place the currently held object at ``target_location``.

        Preconditions:
          * The robot must currently hold an object.
          * The target location must exist.
          * The robot must be at target_location (moved there first).
        """

        self._require_location(target_location)
        if self.state.held_object is None:
            raise PreconditionFailedError("Cannot place: robot is not holding any object")
        if self.state.robot_location != target_location:
            raise PreconditionFailedError(
                f"Cannot place at '{target_location}': robot is at '{self.state.robot_location}'"
            )
        obj = self.state.held_object
        self.state.object_locations[obj] = target_location
        self.state.held_object = None
        msg = f"Robot placed '{obj}' at '{target_location}'"
        self.state.history.append(msg)
        logger.debug(msg)
        return msg

    def inspect(self, object_name: str) -> str:
        """Return a description of where an object currently is."""

        self._require_object(object_name)
        loc = self.state.object_locations.get(object_name, "unknown")
        msg = f"'{object_name}' is at '{loc}'"
        self.state.history.append(f"Inspected '{object_name}': {msg}")
        logger.debug(msg)
        return msg

    def wait(self) -> str:
        """No-op action, useful as a placeholder / synchronization point."""

        msg = "Robot waited"
        self.state.history.append(msg)
        logger.debug(msg)
        return msg

    def open_container(self, object_name: str) -> str:
        """Open a container-type object (e.g. a drawer or box)."""

        if object_name not in self._containers:
            raise ObjectNotFoundError(f"'{object_name}' is not a known container")
        self.state.container_open[object_name] = True
        msg = f"Opened container '{object_name}'"
        self.state.history.append(msg)
        return msg

    def close_container(self, object_name: str) -> str:
        """Close a container-type object."""

        if object_name not in self._containers:
            raise ObjectNotFoundError(f"'{object_name}' is not a known container")
        self.state.container_open[object_name] = False
        msg = f"Closed container '{object_name}'"
        self.state.history.append(msg)
        return msg

    def reset(self) -> str:
        """Reset the environment back to its initial configuration."""

        self.state = RobotState(
            robot_location=self._initial_robot_location,
            object_locations=dict(self._initial_object_locations),
            locations=set(self._initial_locations),
            objects=set(self._initial_objects),
            container_open={c: False for c in self._containers},
        )
        msg = "Environment reset to initial state"
        logger.debug(msg)
        return msg

    # ------------------------------------------------------------------
    # Goal checking
    # ------------------------------------------------------------------
    def check_goal(self, goal_state: dict[str, Any]) -> bool:
        """Check whether the current state satisfies ``goal_state``.

        ``goal_state`` may contain:
          * "object_locations": dict[str, str] of required object -> location
          * "held_object": expected held object (or None)
          * "robot_location": expected robot location
        Only keys present in goal_state are checked.
        """

        if "object_locations" in goal_state:
            for obj, expected_loc in goal_state["object_locations"].items():
                if self.state.object_locations.get(obj) != expected_loc:
                    return False
        if "held_object" in goal_state:
            if self.state.held_object != goal_state["held_object"]:
                return False
        if "robot_location" in goal_state:
            if self.state.robot_location != goal_state["robot_location"]:
                return False
        return True
