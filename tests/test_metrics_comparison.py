"""Tests for evaluation summary comparison (Step 0 of the model-improvement
roadmap: docs/model-improvement-roadmap.md).
"""

from __future__ import annotations

import json

import pytest

from geniac_cap.evaluation.evaluator import Evaluator
from geniac_cap.evaluation.metrics import (
    SummaryLoadError,
    compare_summaries,
    load_summary,
)
from geniac_cap.planners.rule_based import RuleBasedPlanner
from geniac_cap.tasks.loader import get_task_by_id

SINGLE_OBJECT_TASK_IDS = [f"task_{i:03d}" for i in range(1, 13)]


def _summary(tmp_path):
    tasks = [get_task_by_id(tid) for tid in SINGLE_OBJECT_TASK_IDS]
    return Evaluator(results_dir=tmp_path).evaluate(tasks, RuleBasedPlanner())


def test_load_summary_round_trips_through_save_results(tmp_path):
    evaluator = Evaluator(results_dir=tmp_path)
    summary = _summary(tmp_path)
    json_path, _ = evaluator.save_results(summary)

    loaded = load_summary(json_path)
    assert loaded.planner_name == summary.planner_name
    assert loaded.success_rate == summary.success_rate
    assert loaded.total_tasks == summary.total_tasks


def test_load_summary_raises_for_missing_file(tmp_path):
    with pytest.raises(SummaryLoadError):
        load_summary(tmp_path / "does_not_exist.json")


def test_load_summary_raises_for_malformed_json(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not valid json", encoding="utf-8")
    with pytest.raises(SummaryLoadError):
        load_summary(bad_file)


def test_load_summary_raises_for_wrong_shape_json(tmp_path):
    wrong_shape = tmp_path / "wrong.json"
    wrong_shape.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    with pytest.raises(SummaryLoadError):
        load_summary(wrong_shape)


def test_compare_summaries_computes_zero_delta_for_identical_runs(tmp_path):
    summary = _summary(tmp_path)
    comparison = compare_summaries(summary, summary)
    assert comparison.success_rate_delta == 0.0
    assert comparison.average_steps_delta == 0.0


def test_compare_summaries_detects_improvement(tmp_path):
    baseline = _summary(tmp_path)
    # Simulate an "improved" run by tweaking a copy's success rate directly.
    improved = baseline.model_copy(update={"success_rate": baseline.success_rate + 0.1})
    comparison = compare_summaries(baseline, improved)
    assert comparison.success_rate_delta == pytest.approx(0.1)


def test_as_readme_row_contains_change_label_and_planner_name(tmp_path):
    summary = _summary(tmp_path)
    comparison = compare_summaries(summary, summary)
    row = comparison.as_readme_row("test change", pr_or_branch="#99")
    assert "test change" in row
    assert "#99" in row
    assert summary.planner_name in row
    assert row.startswith("| _ |")
