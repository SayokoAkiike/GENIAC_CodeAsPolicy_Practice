"""Tests for loading task definitions from YAML."""

from __future__ import annotations

import pytest

from geniac_cap.exceptions import TaskLoadError
from geniac_cap.tasks.loader import get_task_by_id, load_tasks, load_tasks_from_file


def test_load_tasks_returns_at_least_ten_tasks():
    tasks = load_tasks()
    assert len(tasks) >= 10


def test_load_tasks_from_missing_file_raises():
    with pytest.raises(TaskLoadError):
        load_tasks_from_file("does_not_exist.yaml")


def test_get_task_by_id_returns_matching_task():
    task = get_task_by_id("task_001")
    assert task.task_id == "task_001"
    assert task.expected_objects == ["red_block"]


def test_get_task_by_id_raises_for_unknown_id():
    with pytest.raises(TaskLoadError):
        get_task_by_id("does_not_exist")


def test_all_sample_tasks_have_required_fields():
    tasks = load_tasks()
    for task in tasks:
        assert task.task_id
        assert task.instruction
        assert task.initial_state
        assert task.goal_state
        assert task.expected_objects
        assert task.expected_locations
