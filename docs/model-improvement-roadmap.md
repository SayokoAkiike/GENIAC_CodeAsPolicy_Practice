# Model Improvement Roadmap (zero-budget, no local GPU)

This document evaluates techniques for improving Code-as-Policy planner
performance under two hard constraints: **no paid API usage** (free tiers
only) and **no local GPU** (no gradient-based training). It exists because
most standard "how to improve model performance" advice (bigger models,
fine-tuning, RL post-training) assumes you control the model weights or can
pay for compute — neither is true for a project that only *consumes* hosted
LLM APIs.

## Why most standard techniques don't apply here

| Technique | Why it's out of scope |
|---|---|
| Inference-efficiency tricks (quantization, distillation, speculative decoding) | These are done by whoever *hosts* the model; an API consumer has no access to the serving stack |
| LoRA / PEFT fine-tuning | Requires a GPU and gradient computation |
| RL / DPO post-training | Same as above, plus needs a reward model and rollout infrastructure |
| Scaling model size | Not controllable from the client side — the closest analog is "pick a bigger model from the API," which is either paid (Anthropic) or not meaningfully bigger within the free tier (Gemini) |

## Adopted techniques, in implementation order

### Step 0 — Evaluation tracking (foundation) ✅ implemented

Before changing anything, add a lightweight mechanism to record each
change's measured effect (success rate, average steps) against a
before/after baseline. Without this, "improvement" claims for every
technique below are unverifiable. This is also the mechanism behind the
compact log at the bottom of `README.md`.
- **Cost:** none
- **Complexity:** low
- **Implementation:** `evaluate --compare-to <previous-results.json> --label
  "..."` loads a previously saved evaluation JSON, diffs it against the
  current run, and prints a row ready to paste into the README log table.
  See `geniac_cap.evaluation.metrics.compare_summaries` /
  `SummaryComparison.as_readme_row`.

### Step 1 — Planner cascade (cost-aware routing) ✅ implemented

Try `RuleBasedPlanner` first (free, instant, deterministic); only call a
paid/quota-limited LLM planner when it fails. This is the client-side
analog of "inference-efficiency tricks" — it can't make the model faster,
but it can avoid calling it unnecessarily.
- **Cost:** none
- **Complexity:** low
- **Direct benefit:** reduces exposure to free-tier daily quotas (e.g. the
  Gemini `GenerateRequestsPerDayPerProjectPerModel-FreeTier` limit hit
  during Phase 4 testing)
- **Implementation:** `geniac_cap.evaluation.cascade.run_single_task_cascade`
  and `Evaluator.evaluate_cascade` try a list of planners per task, in
  order, stopping at the first that actually achieves the goal (not just
  the first that runs without error — see the design note below). Exposed
  via `--cascade "rule-based,gemini"` on `run-task` / `evaluate`.
- **Design note:** this lives in the Evaluator layer, not as a
  `BasePlanner` subclass, because only the Evaluator knows the task's
  `goal_state` at the point a cascade decision needs to be made —
  `BasePlanner.plan()` doesn't receive it. A planner-level cascade would
  only be able to check "did this raise an exception," missing failures
  like `goal_not_achieved` (e.g. task_014's two-object case).

### Step 2 — Synthetic task augmentation ✅ implemented

Programmatically generate additional task variations (new object/location
name combinations, paraphrase templates) instead of hand-authoring every
task. Operationalizes "data diversity matters most" at zero API cost,
though it's honest to note this is structural variation, not genuinely
novel data — see the caveat below.
- **Cost:** none (pure Python, no API calls to generate tasks)
- **Complexity:** low
- **Implementation:** `geniac_cap.tasks.generator` generates all three
  patterns already present in `sample_tasks.yaml` (single-object,
  two-object, container), from combinatorial pools of colors/shapes/
  locations/containers. `geniac_cap.tasks.loader.save_tasks_to_yaml` saves
  them in the same schema, loadable via `--tasks-file`. CLI:
  `generate-tasks --single N --two-object N --container N --seed S
  --output path.yaml`. Verified: 16 generated tasks (8/4/4 split) evaluated
  against `RuleBasedPlanner` gave exactly the expected 50% success rate —
  100% on single-object, 0% (goal_not_achieved) on two-object, 0%
  (precondition_failed) on container — matching the hand-authored
  task_001-014 characterization exactly.
- **Caveat:** increases the *evaluation set's* statistical weight, but
  doesn't teach any planner something new; RuleBasedPlanner's structural
  limits (single-object, no containers) are unaffected

### Step 3 — Distillation into RuleBasedPlanner's rule tables ✅ implemented

Use a modest number of LLM calls to harvest correct plans for phrasing
variations RuleBasedPlanner doesn't yet recognize, then fold the new
vocabulary into `OBJECT_SYNONYMS` / `LOCATION_SYNONYMS`. This is symbolic
distillation (LLM output → static rules), not neural distillation.
- **Cost:** a handful of API calls (one-time harvesting run)
- **Complexity:** low
- **Implementation:** `geniac_cap.planners.vocabulary_distiller` filters a
  built-in probe list down to instructions RuleBasedPlanner currently fails
  on (`filter_probes_needing_harvest`, so no API calls are wasted on
  phrasing it already handles), asks an LLM which known object/location
  each refers to, and outputs a human-reviewable proposal (JSON + a
  ready-to-paste snippet) -- nothing is auto-applied to source. CLI:
  `harvest-vocabulary --provider anthropic|gemini`.
- **Limit:** only fixes vocabulary gaps, not RuleBasedPlanner's structural
  limits (multi-object tasks, containers)

### Step 4 — Prompt hill-climbing (post-training analog) ✅ implemented

Treat the system prompt (and few-shot examples) as the only "trainable"
artifact. Evaluate a baseline, propose a mutation (add a few-shot example,
add a self-check instruction, reword a rule), re-evaluate, keep the change
only if success rate improves. This reuses the Step 0 tracking loop as its
reward signal — it's the closest zero-cost analog to "learn from failure
data" available here.
- **Cost:** API calls proportional to (mutations tried) × (tasks) × (eval
  runs); pace with `--delay-seconds` on free tiers
- **Complexity:** medium
- **Implementation:** `AnthropicPlanner`/`GeminiPlanner` now accept a
  `system_prompt` override (for evaluating mutated prompts without
  touching the shared default). `geniac_cap.planners.prompt_hillclimb`
  implements the greedy accept-if-not-worse loop as a pure function of
  `str -> EvaluationSummary`, decoupled from any specific planner/task set.
  CLI: `hill-climb-prompt --planner anthropic|gemini`.
- **Verified (fake client, see docs/experiment-log.md):** simulating an
  LLM that forgets to call `open_container` unless reminded, the loop
  correctly found and kept the `container_reminder` mutation, improving
  task_013 from 0% to 100% success.

### Step 5 — Bandit-based strategy selection ✅ implemented

A multi-armed bandit (e.g. epsilon-greedy or UCB) that learns, from
`ToyRobotEnv`'s free, deterministic reward signal, which planner or repair
strategy to try first for a given task shape. This is genuine
reinforcement learning, just applied to a small decision (which strategy,
not model weights) instead of token-level policy weights.
- **Cost:** none (learns from local simulation results, not API calls)
- **Complexity:** medium-high
- **Implementation:** `geniac_cap.evaluation.bandit.EpsilonGreedyBandit` is
  a contextual (per-task-difficulty) epsilon-greedy bandit over a set of
  cascade orders ("arms"); reward is 1.0 on success (with a small per-tier
  penalty so cheaper cascades win ties), 0.0 on failure.
  `Evaluator.evaluate_bandit` + `bandit-cascade --arms
  "rule-based;rule-based,gemini" --epsilon --seed` wire it into the normal
  evaluation pipeline, reusing `run_single_task_cascade` under the hood.
- **Verified (fake "smart-llm" tier, see docs/experiment-log.md):** across
  3 episodes of all 14 tasks, the bandit correctly learned to prefer
  `rule-based` alone for easy/medium tasks (0 wasted LLM calls) and
  `rule-based->smart-llm` for hard tasks (0.964 vs 0.5 average reward) --
  discovering, purely from reward signal, exactly which task difficulty
  needs the expensive tier.
- **Honest caveat:** the decision space here is small (a handful of
  planners/strategies), so this is a modest, illustrative RL loop, not a
  demonstration of RL at any meaningful scale

## What this roadmap deliberately does not claim

- None of the above are equivalent to gradient-based fine-tuning or RL
  post-training on model weights. Steps 3-5 borrow the *spirit* of those
  techniques (learn from data / failure / reward) while operating entirely
  on prompts, rules, or small decision policies.
- Step 2's "data diversity" is structural augmentation of a tiny toy
  domain, not a substitute for genuinely diverse real-world data.
- Results at this scale (14-and-growing tasks) are illustrative, not
  statistically rigorous — treat success-rate deltas as directional, not
  as fully independent evidence.

See the log at the bottom of `README.md` for which of these have actually
been implemented, when, and what effect was measured.
