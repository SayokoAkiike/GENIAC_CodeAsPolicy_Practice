# geniac-cap-practice

自然言語のロボット操作指示を構造化アクション列に変換し、軽量な仮想環境で実行・評価する、Code-as-Policy形式の練習用プロジェクトです。GENIAC-PRIZE テーマ2を想定した個人の学習プロジェクトであり、GENIACの公式実装・公式ベンチマークではありません。

---

## Overview

This is an independent practice project inspired by the Code-as-Policy
style tasks expected in GENIAC-PRIZE Theme 2. **It is not an official
GENIAC project or benchmark implementation.**

It turns a natural-language instruction (Japanese or simple English) into a
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
- **12 sample tasks** in YAML, including household, kitchen, office, and
  healthcare-adjacent tasks (object transport / tidying only — no
  medication or clinical actions)
- **RuleBasedPlanner**: works without any API key; handles Japanese and
  simple English phrasing variation ("運ぶ/置く/移動する/移す" /
  "move/carry/place/put")
- **BasePlanner interface** so `OpenAIPlanner` / `LocalModelPlanner` can be
  added later without touching the executor or evaluator
- **AnthropicPlanner**: calls the Anthropic API to generate a plan as a
  whitelisted, `Action`-validated JSON array; requires `pip install -e
  ".[llm]"` and `ANTHROPIC_API_KEY` — every other command still works with
  neither installed nor set
- **GeminiPlanner**: same approach against the Google Gemini API (a genuinely
  free tier is available, no credit card required); requires `pip install -e
  ".[llm]"` and `GEMINI_API_KEY`
- **MockLLMPlanner**: canned-response planner as an LLM-planner stand-in
- **SafeExecutor**: whitelist-only execution, argument validation, max-step
  limit, structured failure reasons, per-step logging
- **FeedbackPlanner**: a single-retry execution-feedback loop, with a
  `NaivePlanner` used to demonstrate the difference between "with feedback"
  and "without feedback" success rates
- **Evaluator**: aggregate metrics saved to both JSON and CSV under
  `results/`
- **CLI** (Typer): `demo`, `run-task`, `evaluate`, `list-tasks`, `show-task`
- **43 pytest tests**, all passing; ruff-clean; GitHub Actions CI
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
│   ├── planners/             # BasePlanner, RuleBasedPlanner, MockLLMPlanner, FeedbackPlanner
│   ├── execution/             # SafeExecutor, validation, future CodeParser/SafeCodeExecutor stubs
│   ├── evaluation/           # Evaluator, metrics
│   ├── tasks/                 # loader.py, sample_tasks.yaml
│   └── utils/logging.py
├── tests/                     # 43 pytest tests
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

To also use `AnthropicPlanner` or `GeminiPlanner`, install the optional `llm`
extra and set an API key:

```bash
pip install -e ".[llm]"
cp .env.example .env   # then edit .env and set ANTHROPIC_API_KEY=... and/or GEMINI_API_KEY=...
```

Gemini has a free tier with no credit card required — get a key at
https://aistudio.google.com/apikey. Note the free tier is rate-limited (a
handful of requests per minute depending on the model), so running
`evaluate` across all 12 tasks back-to-back may hit a `429` on a couple of
tasks; that's an API quota, not a bug — those tasks are recorded as
`planning_error` and the rest still complete. Use `--delay-seconds` (e.g.
`--delay-seconds 13` for Gemini's 5-requests-per-minute free tier) to pace
requests and avoid this. These planners are only needed for
`--planner anthropic` / `--planner gemini`; every other command works with
neither the extra installed nor a key set.

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
```

(If you installed with `pip install -e .`, `geniac-cap ...` also works as a
shorter alias for `python -m geniac_cap.cli ...`.)

## Sample run

```bash
$ python -m geniac_cap.cli demo
Instruction: 赤いブロックを青い棚に置いてください

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

43 tests cover the environment, executor whitelist/validation, planner
behavior (including all 12 sample tasks), the feedback/replanning loop, the
evaluator's metrics and JSON/CSV output, and the task loader.

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
(external LLM planner → execution feedback improvements → vision/VLM →
simulator integration → model comparison/fine-tuning → healthcare tasks).

## Disclaimer

This is an independent, personal practice project. It is not affiliated
with, endorsed by, or an official submission to GENIAC-PRIZE. Any notes
about the competition in `docs/competition-notes.md` are informal working
hypotheses, not authoritative competition information — please refer to
official GENIAC materials for anything time-sensitive or authoritative.
Healthcare-adjacent sample tasks are limited to object transport /
environment tidying and never model medication administration or other
clinical actions.

## License

[MIT](LICENSE)
