"""State container for the Toy Robot Environment.

Kept separate from the environment's *behavior* (toy_robot.py) so that the
data shape is easy to read, serialize (get_state) and reset independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RobotState:
    """The full mutable state of one toy-robot episode.

    Attributes:
        robot_location: Name of the location the robot currently occupies.
        held_object: Name of the object currently held by the robot, or None.
        object_locations: Mapping of object_name -> location_name.
        locations: The set of valid location names in this world.
        objects: The set of valid object names in this world.
        history: Ordered list of human-readable action descriptions.
        container_open: Mapping of container_name -> bool (open/closed).
        done: Whether the episode has been explicitly reset/terminated.
    """

    robot_location: str
    held_object: str | None = None
    object_locations: dict[str, str] = field(default_factory=dict)
    locations: set[str] = field(default_factory=set)
    objects: set[str] = field(default_factory=set)
    history: list[str] = field(default_factory=list)
    container_open: dict[str, bool] = field(default_factory=dict)
    done: bool = False

    def snapshot(self) -> dict:
        """Return a plain-dict snapshot suitable for logging/serialization."""

        return {
            "robot_location": self.robot_location,
            "held_object": self.held_object,
            "object_locations": dict(self.object_locations),
            "container_open": dict(self.container_open),
            "history_length": len(self.history),
            "done": self.done,
        }
