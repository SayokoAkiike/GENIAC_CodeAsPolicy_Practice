"""Regression test for the tracked hard benchmark (benchmarks/hard_benchmark_v1.yaml).

Guards against the benchmark or RuleBasedPlanner silently drifting apart
from the documented baseline in benchmarks/README.md /
docs/experiment-log.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from geniac_cap.evaluation.evaluator import Evaluator
from geniac_cap.planners.rule_based import RuleBasedPlanner
from geniac_cap.tasks.loader import load_tasks_from_file

BENCHMARK_PATH = Path(__file__).resolve().parent.parent / "benchmarks" / "hard_benchmark_v1.yaml"


def test_hard_benchmark_exists_and_has_60_tasks():
    tasks = load_tasks_from_file(BENCHMARK_PATH)
    assert len(tasks) == 60


def test_hard_benchmark_rule_based_baseline_is_stable(tmp_path):
    """RuleBasedPlanner should solve exactly the 20 single-object tasks and
    fail all 40 two-object/container tasks -- if this ever changes, either
    the benchmark file or RuleBasedPlanner's behavior has drifted and the
    documented baseline (benchmarks/README.md) needs updating.
    """

    tasks = load_tasks_from_file(BENCHMARK_PATH)
    evaluator = Evaluator(results_dir=tmp_path)
    summary = evaluator.evaluate(tasks, RuleBasedPlanner())

    assert summary.total_tasks == 60
    assert summary.successful_tasks == 20
    assert summary.success_rate == pytest.approx(20 / 60)
