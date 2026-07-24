"""Tests for train/validation/test splitting (see
docs/rigorous-verification-plan.md).
"""

from __future__ import annotations

import pytest

from geniac_cap.tasks.generator import generate_tasks
from geniac_cap.tasks.split import split_tasks


def _tasks():
    return generate_tasks(n_single=10, n_two_object=10, n_container=10, seed=1)  # 30 tasks


def test_split_produces_expected_sizes():
    result = split_tasks(_tasks(), train_ratio=0.6, val_ratio=0.2, test_ratio=0.2, seed=0)
    assert len(result.train) == 18
    assert len(result.validation) == 6
    assert len(result.test) == 6


def test_split_is_stratified_by_task_pattern():
    result = split_tasks(_tasks(), train_ratio=0.6, val_ratio=0.2, test_ratio=0.2, seed=0)

    def pattern_counts(tasks):
        counts = {}
        for t in tasks:
            key = t.task_id.rsplit("_", 1)[0]
            counts[key] = counts.get(key, 0) + 1
        return counts

    # 10 of each pattern -> 6/2/2 split for each, in every subset.
    assert pattern_counts(result.train) == {
        "synth_single": 6,
        "synth_two_object": 6,
        "synth_container": 6,
    }
    assert pattern_counts(result.validation) == {
        "synth_single": 2,
        "synth_two_object": 2,
        "synth_container": 2,
    }
    assert pattern_counts(result.test) == {
        "synth_single": 2,
        "synth_two_object": 2,
        "synth_container": 2,
    }


def test_split_partitions_are_disjoint_and_complete():
    tasks = _tasks()
    result = split_tasks(tasks, seed=0)
    all_ids = {t.task_id for t in tasks}
    train_ids = {t.task_id for t in result.train}
    val_ids = {t.task_id for t in result.validation}
    test_ids = {t.task_id for t in result.test}

    assert train_ids | val_ids | test_ids == all_ids
    assert train_ids & val_ids == set()
    assert train_ids & test_ids == set()
    assert val_ids & test_ids == set()


def test_split_is_deterministic_given_the_same_seed():
    tasks = _tasks()
    first = split_tasks(tasks, seed=42)
    second = split_tasks(tasks, seed=42)
    assert [t.task_id for t in first.train] == [t.task_id for t in second.train]
    assert [t.task_id for t in first.test] == [t.task_id for t in second.test]


def test_split_rejects_ratios_that_dont_sum_to_one():
    with pytest.raises(ValueError):
        split_tasks(_tasks(), train_ratio=0.5, val_ratio=0.3, test_ratio=0.3)


def test_split_rejects_empty_task_list():
    with pytest.raises(ValueError):
        split_tasks([])
