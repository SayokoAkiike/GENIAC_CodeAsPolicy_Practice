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

### Step 0 — Evaluation tracking (foundation)
Before changing anything, add a lightweight mechanism to record each
change's measured effect (success rate, average steps) against a
before/after baseline. Without this, "improvement" claims for every
technique below are unverifiable. This is also the mechanism behind the
compact log at the bottom of `README.md`.
- **Cost:** none
- **Complexity:** low

### Step 1 — Planner cascade (cost-aware routing)
Try `RuleBasedPlanner` first (free, instant, deterministic); only call a
paid/quota-limited LLM planner when it fails. This is the client-side
analog of "inference-efficiency tricks" — it can't make the model faster,
but it can avoid calling it unnecessarily.
- **Cost:** none
- **Complexity:** low
- **Direct benefit:** reduces exposure to free-tier daily quotas (e.g. the
  Gemini `GenerateRequestsPerDayPerProjectPerModel-FreeTier` limit hit
  during Phase 4 testing)

### Step 2 — Synthetic task augmentation
Programmatically generate additional task variations (new object/location
name combinations, paraphrase templates) instead of hand-authoring every
task. Operationalizes "data diversity matters most" at zero API cost,
though it's honest to note this is structural variation, not genuinely
novel data — see the caveat below.
- **Cost:** none (pure Python, no API calls to generate tasks)
- **Complexity:** low
- **Caveat:** increases the *evaluation set's* statistical weight, but
  doesn't teach any planner something new; RuleBasedPlanner's structural
  limits (single-object, no containers) are unaffected

### Step 3 — Distillation into RuleBasedPlanner's rule tables
Use a modest number of LLM calls to harvest correct plans for phrasing
variations RuleBasedPlanner doesn't yet recognize, then fold the new
vocabulary into `OBJECT_SYNONYMS` / `LOCATION_SYNONYMS`. This is symbolic
distillation (LLM output → static rules), not neural distillation.
- **Cost:** a handful of API calls (one-time harvesting run)
- **Complexity:** low
- **Limit:** only fixes vocabulary gaps, not RuleBasedPlanner's structural
  limits (multi-object tasks, containers)

### Step 4 — Prompt hill-climbing (post-training analog)
Treat the system prompt (and few-shot examples) as the only "trainable"
artifact. Evaluate a baseline, propose a mutation (add a few-shot example,
add a self-check instruction, reword a rule), re-evaluate, keep the change
only if success rate improves. This reuses the Step 0 tracking loop as its
reward signal — it's the closest zero-cost analog to "learn from failure
data" available here.
- **Cost:** API calls proportional to (mutations tried) × (tasks) × (eval
  runs); pace with `--delay-seconds` on free tiers
- **Complexity:** medium

### Step 5 — Bandit-based strategy selection
A multi-armed bandit (e.g. epsilon-greedy or UCB) that learns, from
`ToyRobotEnv`'s free, deterministic reward signal, which planner or repair
strategy to try first for a given task shape. This is genuine
reinforcement learning, just applied to a small decision (which strategy,
not model weights) instead of token-level policy weights.
- **Cost:** none (learns from local simulation results, not API calls)
- **Complexity:** medium-high
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
