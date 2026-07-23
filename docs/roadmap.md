# Roadmap

This project is deliberately built in small phases so that each phase adds
one capability on top of a working, tested foundation.

## Phase 1 — Rule-based planner and toy environment (this version)

- Pure-Python Toy Robot Environment (no simulator)
- `RuleBasedPlanner` (Japanese + simple English)
- `SafeExecutor` with a whitelist of actions
- `Evaluator` with JSON/CSV output
- Single-retry execution feedback loop (`FeedbackPlanner`)
- CLI, tests, CI, Codespaces support

## Phase 2 — External LLM planner

- [x] `AnthropicPlanner` implemented against the existing `BasePlanner`
  interface (`--planner anthropic`), gated behind the optional `llm` extra
  and `ANTHROPIC_API_KEY` so the project still runs with zero API keys
- [x] `GeminiPlanner` implemented the same way (`--planner gemini`), using
  Google's free tier (`GEMINI_API_KEY`, no credit card required); both LLM
  planners share one prompt (`planners/llm_prompts.py`) for a fair comparison
- [ ] Implement `OpenAIPlanner` / `LocalModelPlanner` the same way
- [x] Compared GeminiPlanner vs. RuleBasedPlanner on the 12 single-object
  tasks (both 100%, Gemini used fewer average steps by skipping redundant
  moves) — logged in `docs/experiment-log.md`. Two additional "hard" tasks
  (`task_013`, `task_014`) were added specifically to give LLM planners
  room to show an edge RuleBasedPlanner structurally cannot reach; not yet
  run against a real LLM planner.
- [x] `AnthropicPlanner` and `GeminiPlanner` now support the same
  single-retry execution-feedback loop as `FeedbackPlanner`, via the
  generic `BasePlanner.supports_feedback` / `replan()` interface (see
  Phase 3)

## Phase 3 — Execution feedback and self-correction

- [x] Generalized the single-retry feedback loop: `BasePlanner` exposes
  `supports_feedback` and an optional `replan(instruction, context,
  feedback)` method; the Evaluator calls it for *any* planner that opts in
  (not just `FeedbackPlanner`), passing a structured description of why the
  first attempt failed (`evaluation.evaluator._build_failure_feedback`)
- [ ] Extend beyond a single retry into a multi-turn loop with a
  configurable retry budget
- [ ] Track *why* retries succeed or fail, not just whether they did

## Phase 4 — Vision or scene representation

- Add a VLM-based perception interface that produces the same
  `PlanningContext` shape the planners already consume, so planners do not
  need to change
- Explore a simple synthetic "scene description" before wiring in a real VLM

## Phase 5 — CaP-X or robotics simulator integration

- Replace or wrap `ToyRobotEnv` with a MuJoCo- or Isaac-Sim-backed
  environment behind the same public method names
- Investigate CaP-Bench-style evaluation protocols

## Phase 6 — Model comparison and fine-tuning

- Run the same task set across multiple planners/models and report
  comparative metrics
- Explore fine-tuning a planner on collected (instruction, successful plan)
  pairs

## Phase 7 — Healthcare and assistive robotics tasks

- Expand the healthcare-adjacent task set (still limited to object
  transport / environment tidying, never medication administration or
  clinical actions)
- Consider safety-specific evaluation criteria for this task category
