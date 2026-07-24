# Benchmarks

Tracked (non-gitignored) benchmark task sets and baseline results, used to
measure whether the zero-budget model-improvement roadmap
(`docs/model-improvement-roadmap.md`) actually moves the needle -- as
opposed to `sample_tasks.yaml`'s 14 hand-authored tasks, which turned out
to be too easy for this purpose (a real Gemini run already solves all of
them; see `docs/experiment-log.md`).

## `hard_benchmark_v1.yaml`

60 synthetically generated tasks (20 single-object, 20 two-object, 20
container), generated with:

```bash
python -m geniac_cap.cli generate-tasks --single 20 --two-object 20 --container 20 --seed 100 --output benchmarks/hard_benchmark_v1.yaml
```

**RuleBasedPlanner baseline** (see `baseline_rule_based_v1.json`):

```
total_tasks: 60, successful_tasks: 20, success_rate: 33.33%
  single-object: 20/20 (100%)
  two-object:    0/20  (0%, goal_not_achieved)
  container:     0/20  (0%, precondition_failed)
```

This gives 40 tasks (66.7%) that RuleBasedPlanner cannot solve at all --
real headroom for the roadmap's LLM-backed techniques (cascade,
vocabulary distillation, prompt hill-climbing, bandit selection) to
demonstrate an actual improvement, unlike the original 14-task set where
only 2 tasks were out of reach.

## Train / validation / test splits

Generated with (seed fixed for reproducibility):

```bash
python -m geniac_cap.cli split-benchmark --input benchmarks/hard_benchmark_v1.yaml --seed 0 --output-dir benchmarks
```

Stratified so each split has the same proportion of each task pattern
(single-object/two-object/container):

| Split | Tasks | RuleBasedPlanner baseline | Baseline file |
|---|---|---|---|
| `hard_benchmark_v1_train.yaml` | 36 (12/12/12) | 12/36 (33.33%) | `baseline_rule_based_train.json` |
| `hard_benchmark_v1_validation.yaml` | 12 (4/4/4) | 4/12 (33.33%) | `baseline_rule_based_validation.json` |
| `hard_benchmark_v1_test.yaml` | 12 (4/4/4) | 4/12 (33.33%) | `baseline_rule_based_test.json` |

**Usage discipline (see `docs/rigorous-verification-plan.md`):** develop
and iterate (vocabulary distillation, prompt hill-climbing) against
`train` and `validation` only. Touch `test` exactly once, at the end, for
the number that actually goes into the README's Model improvement log —
otherwise a reported "improvement" may just mean the technique overfit to
these specific 60 tasks.

## How to use this for future roadmap verification

Re-run any planner/technique against this fixed benchmark and diff against
the baseline:

```bash
python -m geniac_cap.cli evaluate --planner rule-based --tasks-file benchmarks/hard_benchmark_v1.yaml --compare-to benchmarks/baseline_rule_based_v1.json --label "..."
python -m geniac_cap.cli evaluate --cascade "rule-based,gemini" --tasks-file benchmarks/hard_benchmark_v1.yaml --delay-seconds 13 --compare-to benchmarks/baseline_rule_based_v1.json --label "..."
```

This is the file to use once real API quota is available to genuinely
re-verify Steps 1/3/4/5 of the roadmap (see the "Honest gap" note in
`docs/experiment-log.md` and the README's Model improvement log) --
today's fake-client demos showed the *mechanisms* work, not that they
improve results on a task set with real headroom.
