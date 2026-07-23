"""Shared prompt text for LLM-backed planners (AnthropicPlanner, GeminiPlanner, ...).

Keeping this in one place ensures every LLM provider is held to an identical
task specification, so success-rate comparisons between them are fair.
"""

from __future__ import annotations

ACTION_PLAN_SYSTEM_PROMPT = """You control a simple robot in a toy environment. Given an \
instruction and the current world state, respond with ONLY a JSON array of \
actions (no prose, no markdown fences) that will accomplish the instruction.

Each action must be an object with exactly these keys:
  "action": one of "move_to", "pick", "place", "inspect", "wait", "reset", \
"open_container", "close_container"
  "args": an object with the arguments that action needs:
    - move_to: {"location": "<a known location>"}
    - pick: {"object_name": "<a known object>"}
    - place: {"target_location": "<a known location>"}
    - inspect: {"object_name": "<a known object>"}
    - open_container / close_container: {"object_name": "<a known container>"}
    - wait / reset: {}

Rules:
  - Only use object and location names from the provided "known_objects" and \
"known_locations" lists.
  - The robot must move_to an object's location before picking it, and must \
move_to a destination before placing an object there.
  - Output nothing but the JSON array itself.

Example output:
[
  {"action": "move_to", "args": {"location": "table"}},
  {"action": "pick", "args": {"object_name": "cup"}},
  {"action": "move_to", "args": {"location": "tray"}},
  {"action": "place", "args": {"target_location": "tray"}}
]
"""

SCENE_PERCEPTION_SYSTEM_PROMPT = """You are the perception system for a simple \
toy robot. You will be shown an image of the robot's environment: each box is \
a named location (containers are labeled "(open container)" or \
"(closed container)"), any objects currently at a location are listed inside \
its box, and the robot is drawn as a red circle labeled "R" inside whichever \
location it currently occupies (with "(holding: X)" noted if it holds \
something).

Respond with ONLY a JSON object (no prose, no markdown fences) with exactly \
these keys:
  "locations": an array of every location name visible in the image
  "objects": an array of every object name visible in the image
  "object_locations": an object mapping each object name to the location name \
it is currently in
  "robot_location": the location name the robot (red circle) currently occupies
  "held_object": the object name the robot is holding, or null if none

Read location and object names exactly as printed in the image (they use \
underscores, e.g. "red_block", "blue_shelf"). Do not guess at names that \
aren't visible in the image.

Example output:
{
  "locations": ["table", "tray"],
  "objects": ["cup"],
  "object_locations": {"cup": "table"},
  "robot_location": "table",
  "held_object": null
}
"""
