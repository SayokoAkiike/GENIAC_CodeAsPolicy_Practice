"""Tests for Evaluator: aggregate metrics and JSON/CSV persistence."""

from __future__ import annotations

import json

from geniac_cap.evaluation.evaluator import Evaluator
from geniac_cap.planners.feedback import FeedbackPlanner
from geniac_cap.planners.rule_based import RuleBasedPlanner
from geniac_cap.tasks.loader import load_tasks


def test_evaluator_computes_100_percent_success_rate_for_rule_based(tmp_path):
    tasks = load_tasks()
    evaluator = Evaluator(results_dir=tmp_path)
    summary = evaluator.evaluate(tasks, RuleBasedPlanner())
    assert summary.total_tasks == len(tasks)
    assert summary.success_rate == 1.0
    assert summary.failed_tasks == 0


def test_evaluator_saves_json_and_csv(tmp_path):
    tasks = load_tasks()[:2]
    evaluator = Evaluator(results_dir=tmp_path)
    summary = evaluator.evaluate(tasks, RuleBasedPlanner())
    json_path, csv_path = evaluator.save_results(summary)

    assert json_path.exists()
    assert csv_path.exists()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["total_tasks"] == 2

    csv_text = csv_path.read_text(encoding="utf-8")
    assert "task_id" in csv_text.splitlines()[0]


def test_feedback_vs_no_feedback_success_rate_comparison(tmp_path):
    tasks = load_tasks()
    evaluator = Evaluator(results_dir=tmp_path)

    with_feedback = evaluator.evaluate(tasks, FeedbackPlanner(), allow_feedback=True)
    without_feedback = evaluator.evaluate(tasks, FeedbackPlanner(), allow_feedback=False)

    assert with_feedback.success_rate > without_feedback.success_rate
