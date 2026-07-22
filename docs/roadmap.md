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
- [ ] Implement `OpenAIPlanner` / `LocalModelPlanner` the same way
- [ ] Compare LLM planner vs. `RuleBasedPlanner` success rate on the same
  tasks and log it in `docs/experiment-log.md`
- [ ] Consider whether `AnthropicPlanner` also needs its own
  execution-feedback repair path (today only `FeedbackPlanner` supports the
  single-retry loop)

## Phase 3 — Execution feedback and self-correction

- Extend the current single-retry `FeedbackPlanner` into a multi-turn loop
  with a configurable retry budget
- Track *why* retries succeed or fail, not just whether they did

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
