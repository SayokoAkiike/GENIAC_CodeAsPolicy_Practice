"""Loads TaskDefinition objects from YAML files.

Tasks are kept out of source code so new tasks can be added without touching
any Python logic -- just append to sample_tasks.yaml or point at a new file.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from geniac_cap.config import DEFAULT_TASKS_FILE
from geniac_cap.exceptions import TaskLoadError
from geniac_cap.models import TaskDefinition
from geniac_cap.utils.logging import get_logger

logger = get_logger(__name__)


def load_tasks_from_file(path: Path | str) -> list[TaskDefinition]:
    """Load and validate a list of tasks from a YAML file.

    Raises:
        TaskLoadError: if the file is missing, malformed, or fails validation.
    """

    path = Path(path)
    if not path.exists():
        raise TaskLoadError(f"Task file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TaskLoadError(f"Failed to parse YAML in {path}: {exc}") from exc

    if not isinstance(raw, list):
        raise TaskLoadError(f"Expected a YAML list of tasks in {path}, got {type(raw)}")

    tasks: list[TaskDefinition] = []
    for i, item in enumerate(raw):
        try:
            tasks.append(TaskDefinition.model_validate(item))
        except ValidationError as exc:
            raise TaskLoadError(f"Task #{i} in {path} failed validation: {exc}") from exc

    logger.info("Loaded %d task(s) from %s", len(tasks), path)
    return tasks


def load_tasks(path: Path | str | None = None) -> list[TaskDefinition]:
    """Load tasks from ``path``, defaulting to the bundled sample task set."""

    return load_tasks_from_file(path or DEFAULT_TASKS_FILE)


def get_task_by_id(task_id: str, path: Path | str | None = None) -> TaskDefinition:
    """Convenience helper: load all tasks and return the one matching ``task_id``."""

    tasks = load_tasks(path)
    for task in tasks:
        if task.task_id == task_id:
            return task
    raise TaskLoadError(f"No task found with task_id='{task_id}'")


def save_tasks_to_yaml(tasks: list[TaskDefinition], path: Path | str) -> Path:
    """Save ``tasks`` to ``path`` in the same YAML schema as sample_tasks.yaml.

    The inverse of ``load_tasks_from_file``: a round trip through this
    function and back should reproduce equivalent TaskDefinition objects.
    Mainly used for synthetic task generation (see tasks/generator.py).
    """

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = [task.model_dump(mode="json") for task in tasks]
    path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    logger.info("Saved %d task(s) to %s", len(tasks), path)
    return path
