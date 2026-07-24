# Rigorous Verification Plan

This document exists because reviewing the "Model improvement log" honestly
surfaced a problem: most of Steps 1/3/4/5 in
`docs/model-improvement-roadmap.md` were only validated with fake/mock
clients, and the one real task set available (`sample_tasks.yaml`) turned
out to have no headroom left (a real Gemini run already solves all 14
tasks). `benchmarks/hard_benchmark_v1.yaml` fixes the "no headroom"
problem, but headroom alone isn't enough for a serious claim of
improvement. This plan addresses three further gaps: overfitting risk,
statistical rigor, and API budget planning.

## Gap 1: No train/validation/test split

Steps 3 (vocabulary distillation) and 4 (prompt hill-climbing) both *tune
against evaluation results*. If they're tuned and reported against the
same task set, an improvement could just mean "we found a prompt that
happens to work for these specific 60 tasks," not "we found a prompt that
generalizes."

**Fix:** split `hard_benchmark_v1.yaml` into three fixed, disjoint,
stratified subsets (same proportion of single-object/two-object/container
in each):

- **train** (~60%, 36 tasks): used for iterating during hill-climbing /
  distillation
- **validation** (~20%, 12 tasks): used to decide *when to stop* iterating
  (early-stopping signal), not for the headline number
- **test** (~20%, 12 tasks): touched *only* to report the final number for
  the improvement log. Never looked at during development.

This is the standard ML methodology, applied to prompts/rules instead of
weights. `tasks.split.split_tasks()` (to be added) implements this with a
fixed seed so the split itself is reproducible and auditable.

## Gap 2: No statistical rigor

A handful of percentage points on 12-60 tasks can easily be noise,
especially since LLM outputs aren't perfectly deterministic even at
temperature 0. Going forward:

- Report a **confidence interval** alongside every success rate (Wilson
  score interval is a reasonable choice for small-n binomial proportions),
  not just the raw percentage.
- Require a **minimum effect size** (e.g. the confidence intervals for
  baseline and candidate must not overlap, or the point estimate must
  differ by more than ~15 percentage points on a 12-36 task set) before
  writing "improved" in the log — otherwise report "no significant
  change."
- Where API budget allows, **re-run the same configuration twice** and
  report both, rather than treating a single run as ground truth.

## Gap 3: No API budget plan

Gemini's free tier allows roughly 20 requests/day for the current default
model (observed empirically — see `docs/experiment-log.md`). **A dry run
confirmed this matters concretely:** a single `--cascade "rule-based,X"`
pass over the full **train** split (36 tasks) needs the LLM tier for 24 of
them — that alone exceeds the daily quota by itself, before any other
activity that day. Two consequences:

1. `benchmarks/train_mini.yaml` (18 tasks: 6 single-object, 6 two-object,
   6 container; same 33.33% RuleBasedPlanner baseline as every other
   split) exists specifically for day-to-day iteration: only ~12 tasks
   need the LLM tier, comfortably inside one day's quota with room to
   spare for a second activity the same day.
2. The full 36-task **train** split should be reserved for periodic
   checkpoints (e.g. once every few days), not every iteration.

| Day | Activity | Est. LLM calls |
|---|---|---|
| 1 | Cascade baseline: `rule-based,gemini` on **train_mini** (18 tasks) | ~12 |
| 2 | `harvest-vocabulary` (real) on the probe list; review + merge accepted synonyms | ~10-15 |
| 3 | Re-run cascade on **train_mini** with updated vocabulary; compare | ~12 |
| 4 | `hill-climb-prompt` (real) on **train_mini**, 3 mutations = 4 evaluate passes | ~12 × 4 = 48, needs 3-4 days or a smaller task subset per pass |
| 5 | Full **train** (36 tasks) checkpoint run, once mutations/vocabulary are settled | ~24 |
| 6 | `bandit-cascade` (real), a handful of episodes over **train_mini** | multi-day, reuses train_mini-scale calls |
| 7 (final) | Single, one-time run of the winning configuration against the held-out **test** split (12 tasks, ~8 LLM calls) | ~8 |

This is a plan, not a strict schedule — the point is: iterate on
**train_mini**, checkpoint on the full **train** split periodically, and
spend the **test** split's small budget exactly once, at the end, for the
number that goes in the log.

## What "seriously improved" will mean going forward

A change only gets logged as an improvement in README's Model improvement
log if:

1. It was run against `benchmarks/hard_benchmark_v1.yaml` (or its
   train/val/test splits), not a fake client or a hand-picked single task.
2. The reported number is from the **test** split (or the full benchmark,
   for baseline/non-tuned comparisons like Step 1's cascade), not train.
3. The improvement exceeds the minimum effect size described above, or is
   explicitly reported as "not statistically distinguishable from
   baseline."
4. The row is marked ✅ (real API), not 🧪 (fake/mock).

Rows already in the log that don't meet this bar keep their existing 🧪
marking rather than being deleted — they still document that the
*mechanism* works, which remains useful, just distinct from a verified
improvement.
