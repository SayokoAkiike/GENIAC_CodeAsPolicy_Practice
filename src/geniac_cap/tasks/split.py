"""Stratified train/validation/test splitting for task sets (see
docs/rigorous-verification-plan.md).

Exists so that tuning-based techniques (vocabulary distillation, prompt
hill-climbing) can be developed against a "train" split and validated
against a held-out "test" split they never see during development --
standard ML methodology, applied to prompts/rules instead of weights.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from geniac_cap.models import TaskDefinition


def _default_stratify_key(task: TaskDefinition) -> str:
    """Group by task_id with any trailing "_<digits>" stripped (so e.g.
    "synth_single_007" and "synth_single_012" land in the same group), or by
    difficulty if the task_id has no numeric suffix.
    """

    match = re.match(r"^(.*)_\d+$", task.task_id)
    return match.group(1) if match else task.difficulty.value


@dataclass
class TaskSplit:
    train: list[TaskDefinition]
    validation: list[TaskDefinition]
    test: list[TaskDefinition]


def split_tasks(
    tasks: list[TaskDefinition],
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2,
    seed: int = 0,
    stratify_key=None,
) -> TaskSplit:
    """Split ``tasks`` into disjoint train/validation/test sets.

    Splitting is stratified (by default, by task pattern -- see
    ``_default_stratify_key``) so each split has a proportional mix of
    task types, rather than e.g. all the container tasks accidentally
    landing in test only.

    Args:
        train_ratio, val_ratio, test_ratio: Must sum to ~1.0 (validated).
        seed: Random seed; the same seed always produces the same split.
        stratify_key: Optional ``TaskDefinition -> str`` grouping function.
            Defaults to ``_default_stratify_key``.

    Raises:
        ValueError: if the ratios don't sum to ~1.0, or ``tasks`` is empty.
    """

    if not tasks:
        raise ValueError("split_tasks requires at least one task")
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 1e-6:
        raise ValueError(f"train/val/test ratios must sum to 1.0, got {total_ratio}")

    key_fn = stratify_key or _default_stratify_key
    rng = random.Random(seed)

    groups: dict[str, list[TaskDefinition]] = {}
    for task in tasks:
        groups.setdefault(key_fn(task), []).append(task)

    train: list[TaskDefinition] = []
    validation: list[TaskDefinition] = []
    test: list[TaskDefinition] = []

    for _key, group in sorted(groups.items()):
        shuffled = list(group)
        rng.shuffle(shuffled)
        n = len(shuffled)
        n_train = round(n * train_ratio)
        n_val = round(n * val_ratio)
        # Whatever's left (due to rounding) goes to test.
        n_test = max(0, n - n_train - n_val)
        n_train = n - n_val - n_test  # keep counts consistent if rounding overshot
        train.extend(shuffled[:n_train])
        validation.extend(shuffled[n_train : n_train + n_val])
        test.extend(shuffled[n_train + n_val : n_train + n_val + n_test])

    return TaskSplit(train=train, validation=validation, test=test)
