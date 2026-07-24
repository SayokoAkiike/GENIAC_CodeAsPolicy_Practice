# geniac-cap-practice

## Overview

This is an independent practice project exploring Code-as-Policy style
tasks: turning natural-language instructions into robot behavior.

It turns a natural-language instruction (English or Japanese) into a
structured, whitelisted sequence of robot actions, executes that sequence
against a small in-memory "Toy Robot Environment," checks whether the goal
was reached, and reports success/failure metrics across a batch of tasks.

No physical robot or simulator (MuJoCo, Isaac Sim, ROS) is used in this
version — the environment is pure Python. No external LLM API is required
to run anything in this repository today.

## What is "Code-as-Policy" here?

Code-as-Policy (CaP) refers to using a language model to translate a
natural-language instruction into executable robot behavior — either
generated code or a structured action plan — instead of hand-writing a
control policy for every possible instruction. This project implements the
"structured action plan" side of that idea: a `Planner` turns text into a
list of whitelisted `Action` objects, and a `SafeExecutor` runs them. Direct
code generation/execution is left as a documented future extension point
(see `docs/architecture.md`), not something this version does.

## Current features

- **Toy Robot Environment**: locations, objects, held-object state,
  container open/close, action history, precondition checks
  (`move_to`, `pick`, `place`, `inspect`, `wait`, `reset`,
  `open_container`, `close_container`)
- **14 sample tasks** in YAML, including household, kitchen, office, and
  healthcare-adjacent tasks (object transport / tidying only — no
  medication or clinical actions). Twelve are solvable by
  `RuleBasedPlanner`; two (`task_013`, a container task, and `task_014`, a
  two-object task) are intentionally beyond it, as a comparison point
  against LLM-backed planners — see `docs/experiment-log.md`. `generate-tasks`
  can programmatically generate more of all three patterns (single-object,
  two-object, container) for larger-scale evaluation — see
  `docs/model-improvement-roadmap.md`. `benchmarks/hard_benchmark_v1.yaml`
  is a tracked, larger (60-task) version of this used specifically to give
  real headroom for measuring model-improvement techniques, since the
  original 14 turned out to be solvable almost entirely by a real Gemini
  run — see `benchmarks/README.md`
- **RuleBasedPlanner**: works without any API key; handles English and
  Japanese phrasing variation for move/carry/place-style verbs.
  `harvest-vocabulary` can use an LLM to propose new
  `OBJECT_SYNONYMS`/`LOCATION_SYNONYMS` entries for phrasing it doesn't yet
  recognize (human-reviewed, never auto-applied — see
  `docs/model-improvement-roadmap.md`)
- **BasePlanner interface** so `OpenAIPlanner` / `LocalModelPlanner` can be
  added later without touching the executor or evaluator
- **AnthropicPlanner**: calls the Anthropic API to generate a plan as a
  whitelisted, `Action`-validated JSON array; requires `pip install -e
  ".[llm]"` and `ANTHROPIC_API_KEY` — every other command still works with
  neither installed nor set
- **GeminiPlanner**: same approach against the Google Gemini API (a genuinely
  free tier is available, no credit card required); requires `pip install -e
  ".[llm]"` and `GEMINI_API_KEY`. Both LLM planners accept a `system_prompt`
  override, used by `hill-climb-prompt` (see below) to evaluate mutated
  prompts without touching the shared default
- **GroqPlanner**: same approach against the Groq API (OpenAI-compatible;
  free tier is very generous — no credit card, ~14,400 requests/day as of
  mid-2026); requires `pip install -e ".[llm]"` and `GROQ_API_KEY`. Exists
  specifically as a cascade fallback tier: `--cascade
  "rule-based,gemini,groq"` automatically moves on to Groq once Gemini's
  much smaller daily quota (~20/day) is exhausted — a 429 there is just
  another planning failure to the existing cascade logic, no special
  quota-handling code needed
- **MockLLMPlanner**: canned-response planner as an LLM-planner stand-in
- **SafeExecutor**: whitelist-only execution, argument validation, max-step
  limit, structured failure reasons, per-step logging
- **FeedbackPlanner**: a single-retry execution-feedback loop, with a
  `NaivePlanner` used to demonstrate the difference between "with feedback"
  and "without feedback" success rates. `AnthropicPlanner` and
  `GeminiPlanner` support the same feedback loop (`supports_feedback`), so
  a failed plan is retried once with the failure reason included in the
  follow-up prompt
- **Evaluator**: aggregate metrics saved to both JSON and CSV under
  `results/`; `--cascade "rule-based,gemini"` tries planners in order per
  task, stopping at the first success, so paid/quota-limited planners are
  only called when a cheaper one fails; `bandit-cascade` goes further and
  *learns*, per task-difficulty context, which cascade order tends to
  work best, via a contextual epsilon-greedy bandit
  (`geniac_cap.evaluation.bandit`); `--compare-to <prev.json> --label
  "..."` diffs a run against a saved baseline and prints a row ready to
  paste into the improvement log at the bottom of this README (see
  `docs/model-improvement-roadmap.md`)
- **Perception (Phase 4)**: `GroundTruthPerception` (default, reads
  environment state directly) and `VLMPerception` (renders the scene as a
  PNG and asks Claude's or Gemini's vision capability to describe it,
  producing the same `PlanningContext` shape); `render-scene` CLI command
  to save a task's rendered scene, `--perception vlm --vision-provider
  anthropic|gemini` on `run-task` / `evaluate`. Requires `pip install -e
  ".[vision]"` for the renderer (Pillow) plus `.[llm]` for the vision API
  call — every other command works without either installed
- **CLI** (Typer): `demo`, `run-task`, `evaluate`, `list-tasks`, `show-task`
- **134 pytest tests**, all passing; ruff-clean; GitHub Actions CI
- **Codespaces-ready** via `.devcontainer/devcontainer.json`

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full diagram.
Short version:

```
Instruction → Planner → ActionPlan → SafeExecutor → ToyRobotEnv
            → Goal Evaluation → (success) → done
                              → (failure) → Feedback → Replanning (max 1 retry)
```

## Directory structure

```text
geniac-cap-practice/
├── .devcontainer/devcontainer.json
├── .github/workflows/ci.yml
├── docs/                     # architecture, roadmap, experiment log, notes
├── examples/sample_run.py    # library-usage example (no CLI)
├── results/                  # evaluate output (JSON/CSV), gitignored
├── src/geniac_cap/
│   ├── cli.py
│   ├── config.py / models.py / exceptions.py
│   ├── environment/          # ToyRobotEnv, RobotState
│   ├── perception/            # BasePerception, GroundTruthPerception, VLMPerception, renderer.py
│   ├── planners/             # BasePlanner, RuleBasedPlanner, MockLLMPlanner, FeedbackPlanner, AnthropicPlanner, GeminiPlanner
│   ├── execution/             # SafeExecutor, validation, future CodeParser/SafeCodeExecutor stubs
│   ├── evaluation/           # Evaluator, metrics
│   ├── tasks/                 # loader.py, sample_tasks.yaml
│   └── utils/logging.py
├── tests/                     # 134 pytest tests
├── pyproject.toml
└── README.md
```

## Setup

Requires Python 3.11+.

```bash
git clone https://github.com/USERNAME/geniac-cap-practice.git
cd geniac-cap-practice
pip install -e ".[dev]"
```

To also use `AnthropicPlanner`, `GeminiPlanner`, or `GroqPlanner`, install
the optional `llm` extra and set an API key:

```bash
pip install -e ".[llm]"
cp .env.example .env   # then edit .env and set ANTHROPIC_API_KEY=... / GEMINI_API_KEY=... / GROQ_API_KEY=...
```

Gemini has a free tier with no credit card required — get a key at
https://aistudio.google.com/apikey. Note the free tier is rate-limited (a
handful of requests per minute, and only ~20 requests/day for the current
default model) so running `evaluate` across many tasks back-to-back may
hit a `429`; that's an API quota, not a bug — those tasks are recorded as
`planning_error` and the rest still complete. Use `--delay-seconds` (e.g.
`--delay-seconds 13`) to pace requests and avoid the per-minute limit.

Groq also has a free tier with no credit card required — get a key at
https://console.groq.com — with a much larger daily quota (~14,400
requests/day as of mid-2026), so it works well as a cascade fallback once
Gemini's smaller quota runs out: `--cascade "rule-based,gemini,groq"`.

These planners are only needed for `--planner anthropic` /
`--planner gemini` / `--planner groq`; every other command works with
neither the extra installed nor a key set.

To also render scenes and use `VLMPerception` (Phase 4), install the
optional `vision` extra (adds Pillow):

```bash
pip install -e ".[vision]"
```

`VLMPerception` additionally needs the `llm` extra and an API key (same
ones as the LLM planners above) since it calls Claude's or Gemini's vision
capability — `--perception vlm` is only needed for that; every other
command works with neither installed.

## Getting started in GitHub Codespaces

1. Open the repository on GitHub and click **Code → Codespaces → Create
   codespace on main**.
2. The devcontainer runs `pip install -e ".[dev]"` automatically
   (`postCreateCommand`). If it doesn't finish for any reason, just run it
   yourself in the terminal.
3. Then run any of the commands below.

## CLI usage

```bash
python -m geniac_cap.cli list-tasks
python -m geniac_cap.cli show-task --task-id task_001
python -m geniac_cap.cli demo
python -m geniac_cap.cli run-task --task-id task_001
python -m geniac_cap.cli run-task --task-id task_001 --planner feedback
python -m geniac_cap.cli evaluate
python -m geniac_cap.cli evaluate --planner rule-based
python -m geniac_cap.cli evaluate --planner feedback
python -m geniac_cap.cli evaluate --planner feedback --no-feedback
python -m geniac_cap.cli evaluate --planner anthropic
python -m geniac_cap.cli evaluate --planner gemini
python -m geniac_cap.cli evaluate --planner gemini --delay-seconds 13
python -m geniac_cap.cli render-scene --task-id task_013
python -m geniac_cap.cli run-task --task-id task_013 --planner gemini --perception vlm --vision-provider gemini
python -m geniac_cap.cli evaluate --planner rule-based --compare-to results/evaluation_20260101_120000.json --label "describe the change"
python -m geniac_cap.cli evaluate --cascade "rule-based,gemini" --delay-seconds 13
python -m geniac_cap.cli generate-tasks --single 10 --two-object 5 --container 5
python -m geniac_cap.cli evaluate --planner rule-based --tasks-file results/synthetic_tasks.yaml
python -m geniac_cap.cli harvest-vocabulary --provider gemini
python -m geniac_cap.cli hill-climb-prompt --planner gemini --delay-seconds 13
python -m geniac_cap.cli bandit-cascade --arms "rule-based;rule-based,gemini" --epsilon 0.2
python -m geniac_cap.cli evaluate --cascade "rule-based,gemini,groq" --delay-seconds 13
```

(If you installed with `pip install -e .`, `geniac-cap ...` also works as a
shorter alias for `python -m geniac_cap.cli ...`.)

## Sample run

```bash
$ python -m geniac_cap.cli demo
Instruction: Move the red block to the blue shelf

Generated plan:
  0. move_to({'location': 'table'})
  1. pick({'object_name': 'red_block'})
  2. move_to({'location': 'blue_shelf'})
  3. place({'target_location': 'blue_shelf'})

Execution log:
  step 0 OK: Robot moved to 'table'
  step 1 OK: Robot picked up 'red_block'
  step 2 OK: Robot moved to 'blue_shelf'
  step 3 OK: Robot placed 'red_block' at 'blue_shelf'

Goal achieved: yes
```

Also see [`examples/sample_run.py`](examples/sample_run.py) for a
library-style (non-CLI) usage example.

## Evaluation metrics

`evaluate` computes, per planner, over all tasks in
`src/geniac_cap/tasks/sample_tasks.yaml`:

- `total_tasks`, `successful_tasks`, `failed_tasks`, `success_rate`
- `planning_error_count`, `execution_error_count`, `invalid_action_count`
- `average_steps`, `average_execution_time`
- a failure-reason breakdown (`planning_error`, `invalid_action`,
  `invalid_argument`, `object_not_found`, `location_not_found`,
  `precondition_failed`, `goal_not_achieved`, `max_steps_exceeded`,
  `unexpected_error`)
- per-task results

Results are printed to the terminal **and** saved as
`results/evaluation_YYYYMMDD_HHMMSS.json` and `.csv`.

## Testing

```bash
python -m pytest
# or
pytest
```

77 tests cover the environment (including container open/close
preconditions), executor whitelist/validation, planner behavior (all 12
single-object sample tasks, plus dedicated tests documenting why
RuleBasedPlanner can't solve the 2 harder ones), the feedback/replanning
loop (shared by RuleBasedPlanner-based `FeedbackPlanner` and the LLM
planners), perception (`GroundTruthPerception`, `VLMPerception`, the scene
renderer), the evaluator's metrics and JSON/CSV output, the CLI, and the
task loader.

## Current constraints

- No physical robot or physics simulator is used; the environment is a
  simplified in-memory Python model.
- No external LLM/VLM API is called by default; `MockLLMPlanner` and the
  `BasePlanner` interface exist to make adding one later straightforward.
- `RuleBasedPlanner` only handles the single "move one object from its
  current location to a mentioned destination" pattern; it does not (yet)
  handle multi-object tasks, containers-as-goals, or free-form dialogue.
- The feedback loop performs at most one retry and repairs plans using
  rule-based logic, not a learned model.

## Roadmap

See [`docs/roadmap.md`](docs/roadmap.md) for the full phase-by-phase plan
(external LLM planners → execution feedback improvements → vision/VLM →
simulator integration → model comparison/fine-tuning → healthcare tasks).

## Disclaimer

This is an independent, personal practice project, not a production
system. Healthcare-adjacent sample tasks are limited to object transport /
environment tidying and never model medication administration or other
clinical actions.

## License

[MIT](LICENSE)

---

<details>
<summary>Model improvement log</summary>

Tracks changes made under <a href="docs/model-improvement-roadmap.md">the zero-budget/no-GPU model improvement roadmap</a>, in adoption order.

**Columns:** *Success rate* = performance on the full 14 sample tasks (the one number comparable across every row — `RuleBasedPlanner` alone has stayed flat at **12/14 (85.71%)** throughout; none of these steps change what it can solve, only how the LLM tier is reached/used). *Efficiency* = change in how many (costly/quota-limited) LLM calls are needed for the same outcome. *Learning/Adaptation* = evidence the mechanism itself improves or adapts (as opposed to just running a fixed pipeline). *Verified* = 🧪 fake/mock client (sandbox logic check only) vs ✅ real API call.

| # | Change | PR/Branch | Date | Success rate (14-task) | Efficiency | Learning/Adaptation | Verified |
|---|---|---|---|---|---|---|---|
| — | Baseline: RuleBasedPlanner alone | `1c77297` | 2026-07-23 | 12/14 (85.71%) | — (0 LLM calls) | — | ✅ |
| 0 | Evaluation tracking (`--compare-to`/`--label`) | `d8f0794` | 2026-07-23 | 12/14 (unchanged) | — | — (infra, not a planner change) | ✅ |
| 1 | Planner cascade (`--cascade`) | `772882b` | 2026-07-23 | 12/14 (unchanged) | ~86% fewer LLM calls (only 2/14 tasks reach tier 2) | — | 🧪 |
| 2 | Synthetic task augmentation (`generate-tasks`) | `d0b522a` | 2026-07-23 | N/A — separate 16-task set: 8/16 (50%) | — | — (dataset tool, not a planner) | ✅ |
| 3 | Vocabulary distillation (`harvest-vocabulary`) | `e6b1aea` | 2026-07-23 | 12/14 (unchanged; proposal not yet merged) | — | 9/11 probes correctly identified as needing new vocabulary | 🧪 |
| 4 | Prompt hill-climbing (`hill-climb-prompt`) | `968bd30` | 2026-07-23 | N/A — single-task demo only | — | task_013 success 0%→100% after 1 accepted mutation (of 3 tried) | 🧪 |
| 5 | Contextual bandit (`bandit-cascade`) | `2ba18da` | 2026-07-23 | 12/14 (unchanged) | matches cascade (tier 2 only reached when needed) | learned reward 0.964 (hard tasks, LLM tier) vs 0.5 (hard tasks, rule-based only), per-context | 🧪 |
| — | **Best real-API result so far** | — | 2026-07-23 | 14/14 (100%) *projected, not yet run as one pass* | not yet measured together | — | ✅ (two separate real runs combined) |
| — | **Created `benchmarks/hard_benchmark_v1.yaml`** (60 tasks) to fix the "too easy" problem above | — | 2026-07-23 | RuleBasedPlanner: 20/60 (33.33%) | — | — (new measurement ground, not a technique) | ✅ |
| 1+ | **Added `GroqPlanner`** as a 3rd cascade tier; **first real, verified improvement**: `--cascade "rule-based,gemini,groq"` on `train_mini.yaml` (18 tasks) | `1cbbdc0` | 2026-07-24 | ✅ **33.33% → 100.00% (+66.67%)** | Groq rescued 9/18 tasks after Gemini's daily quota (429) ran out mid-run — without it, this run would have stopped at 50% | feedback/replan loop caught a real GroqPlanner mistake (misidentified a container as an object) and self-corrected | ✅ real API, not simulated |
| 3 | Vocabulary distillation (real, via `harvest-vocabulary --provider groq`), reviewed and merged into `rule_based.py` | (fill in) | 2026-07-24 | 12/14 on `sample_tasks.yaml` (unchanged — vocab doesn't touch structural limits) | — | 7/9 unresolved probes correctly resolved into real, reviewed synonyms (crimson block→red_block, mug→cup, flask→water_bottle, pill box→medicine_box, notepad→notebook, paperwork→documents, kitchenette→kitchen); all now pass a regression test | ✅ real API, human-reviewed before merge |
| 5 | Contextual bandit (real): `bandit-cascade --arms "rule-based;rule-based,groq"` on `train_mini.yaml` | (fill in) | 2026-07-24 | ✅ 16/18 (88.89%) | learned `hard`→cascade, `easy`→rule-based alone (no wasted calls) | correctly learned the context-dependent split with a real 2nd tier; one real failure (`synth_container_004`) where Groq repeated the same mistake even after 1 replan — logged as evidence a single retry isn't always enough | ✅ real API, not simulated |

**Status:** Steps 1, 3, and 5 now have real, verified results (all on 2026-07-24, using Groq once Gemini's daily quota ran out — see the rows above). Step 3's harvested vocabulary was human-reviewed before merging, per `docs/rigorous-verification-plan.md`'s discipline for tuning-based techniques. Step 4 (prompt hill-climbing) is still only validated with a fake client (🧪 row above); its real number should come from `benchmarks/hard_benchmark_v1_test.yaml` (held out, touched once), not an ad-hoc run.

</details>
