"""Synthetic task generation (Step 2 of the zero-budget model-improvement
roadmap; see docs/model-improvement-roadmap.md).

Programmatically generates additional TaskDefinitions from templates,
instead of hand-authoring every one. Three patterns are generated,
mirroring the hand-authored tasks in sample_tasks.yaml:

  - single-object "move X to Y" tasks (RuleBasedPlanner should solve these)
  - two-object "move both X and Y to Z" tasks (RuleBasedPlanner is
    documented to fail these -- see tests/test_planner.py)
  - container "open C and put X inside" tasks (RuleBasedPlanner is
    documented to fail these too)

Generated instructions are English, built directly from the object/
location names (with underscores turned into spaces). RuleBasedPlanner's
object/location matching already falls back to a literal
``name.replace("_", " ")`` check (see planners/rule_based.py), so generated
tasks work without adding entries to OBJECT_SYNONYMS / LOCATION_SYNONYMS.

Honest caveat (see docs/model-improvement-roadmap.md): this increases the
*evaluation set's* size and structural variety, but it's combinatorial
variation of a small toy domain, not genuinely novel data.
"""

from __future__ import annotations

import random

from geniac_cap.models import TaskCategory, TaskDefinition, TaskDifficulty

_COLORS = ["red", "green", "blue", "yellow", "purple", "orange", "white", "black"]
_SHAPES = ["block", "ball", "cube", "cone", "cylinder", "disc", "prism", "ring"]
_LOCATIONS = [
    "table",
    "shelf",
    "desk",
    "cabinet",
    "counter",
    "cart",
    "bin",
    "rack",
    "bench",
    "tray",
]
_CONTAINERS = ["storage_box", "supply_crate", "toolbox", "drawer", "locker", "chest"]


def _object_pool(rng: random.Random, count: int) -> list[str]:
    combos = [f"{color}_{shape}" for color in _COLORS for shape in _SHAPES]
    rng.shuffle(combos)
    return combos[:count]


def _location_pool(rng: random.Random, count: int) -> list[str]:
    locs = list(_LOCATIONS)
    rng.shuffle(locs)
    return locs[:count]


def _container_pool(rng: random.Random, count: int) -> list[str]:
    containers = list(_CONTAINERS)
    rng.shuffle(containers)
    return containers[:count]


def generate_single_object_tasks(
    count: int, seed: int = 0, id_prefix: str = "synth_single"
) -> list[TaskDefinition]:
    """Generate 'move X to Y' tasks -- the pattern RuleBasedPlanner solves."""

    rng = random.Random(seed)
    objects = _object_pool(rng, max(count, 4))
    locations = _location_pool(rng, max(4, min(len(_LOCATIONS), count + 2)))

    tasks = []
    for i in range(count):
        obj = objects[i % len(objects)]
        src, dst = rng.sample(locations, 2)
        readable_obj = obj.replace("_", " ")
        readable_dst = dst.replace("_", " ")
        task = TaskDefinition(
            task_id=f"{id_prefix}_{i + 1:03d}",
            instruction=f"Move the {readable_obj} to the {readable_dst}",
            initial_state={
                "robot_location": src,
                "object_locations": {obj: src},
                "locations": [src, dst],
                "objects": [obj],
            },
            goal_state={"object_locations": {obj: dst}},
            difficulty=TaskDifficulty.EASY,
            category=TaskCategory.HOUSEHOLD,
            expected_objects=[obj],
            expected_locations=[src, dst],
        )
        tasks.append(task)
    return tasks


def generate_two_object_tasks(
    count: int, seed: int = 0, id_prefix: str = "synth_two_object"
) -> list[TaskDefinition]:
    """Generate 'move both X and Y to Z' tasks -- documented to be beyond
    RuleBasedPlanner's single-object extraction (see tests/test_planner.py).
    """

    rng = random.Random(seed + 1)  # different stream than single-object
    objects = _object_pool(rng, max(count * 2, 8))
    locations = _location_pool(rng, max(3, min(len(_LOCATIONS), count + 2)))

    tasks = []
    for i in range(count):
        obj1, obj2 = objects[2 * i], objects[2 * i + 1]
        src, dst = rng.sample(locations, 2)
        readable1, readable2 = obj1.replace("_", " "), obj2.replace("_", " ")
        readable_dst = dst.replace("_", " ")
        task = TaskDefinition(
            task_id=f"{id_prefix}_{i + 1:03d}",
            instruction=f"Move both the {readable1} and the {readable2} to the {readable_dst}",
            initial_state={
                "robot_location": src,
                "object_locations": {obj1: src, obj2: src},
                "locations": [src, dst],
                "objects": [obj1, obj2],
            },
            goal_state={"object_locations": {obj1: dst, obj2: dst}},
            difficulty=TaskDifficulty.HARD,
            category=TaskCategory.HOUSEHOLD,
            expected_objects=[obj1, obj2],
            expected_locations=[src, dst],
        )
        tasks.append(task)
    return tasks


def generate_container_tasks(
    count: int, seed: int = 0, id_prefix: str = "synth_container"
) -> list[TaskDefinition]:
    """Generate 'open C and put X inside' tasks -- documented to be beyond
    RuleBasedPlanner, which never emits open_container (see
    tests/test_planner.py).
    """

    rng = random.Random(seed + 2)  # different stream than the other generators
    objects = _object_pool(rng, max(count, 4))
    containers = _container_pool(rng, max(count, 2))
    source_locations = _location_pool(rng, max(2, min(len(_LOCATIONS), count + 1)))

    tasks = []
    for i in range(count):
        obj = objects[i % len(objects)]
        container = containers[i % len(containers)]
        src = source_locations[i % len(source_locations)]
        readable_obj = obj.replace("_", " ")
        readable_container = container.replace("_", " ")
        task = TaskDefinition(
            task_id=f"{id_prefix}_{i + 1:03d}",
            instruction=f"Open the {readable_container} and put the {readable_obj} inside",
            initial_state={
                "robot_location": src,
                "object_locations": {obj: src},
                "locations": [src, container],
                "objects": [obj],
                "containers": [container],
            },
            goal_state={"object_locations": {obj: container}},
            difficulty=TaskDifficulty.HARD,
            category=TaskCategory.OFFICE,
            expected_objects=[obj],
            expected_locations=[src, container],
        )
        tasks.append(task)
    return tasks


def generate_tasks(
    n_single: int = 10,
    n_two_object: int = 5,
    n_container: int = 5,
    seed: int = 0,
) -> list[TaskDefinition]:
    """Generate a mixed batch of synthetic tasks across all three patterns."""

    return [
        *generate_single_object_tasks(n_single, seed=seed),
        *generate_two_object_tasks(n_two_object, seed=seed),
        *generate_container_tasks(n_container, seed=seed),
    ]
