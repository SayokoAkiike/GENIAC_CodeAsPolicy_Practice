# Experiment Log

Use one entry per experiment run. Copy the template below and fill it in
after running `python -m geniac_cap.cli evaluate --planner <name>`.

---

## Template

- **Date:**
- **Commit:**
- **Planner:** (rule-based / feedback / mock-llm)
- **Dataset:** `src/geniac_cap/tasks/sample_tasks.yaml` (or custom file)
- **Number of tasks:**
- **Success rate:**
- **Average steps:**
- **Errors:** (failure_reason breakdown from the evaluate output)
- **Changes:** (what changed since the previous entry, if anything)
- **Interpretation:**
- **Next action:**

---

## Example (baseline, rule-based planner)

- **Date:** 2026-07-23
- **Commit:** `<fill in after first commit>`
- **Planner:** rule-based
- **Dataset:** `sample_tasks.yaml` (12 tasks)
- **Number of tasks:** 12
- **Success rate:** 100%
- **Average steps:** 4.0
- **Errors:** none
- **Changes:** initial version
- **Interpretation:** RuleBasedPlanner always inserts the correct
  `move_to` steps before `pick`/`place`, so it solves every current sample
  task (all are single-object transport tasks).
- **Next action:** add harder tasks (multiple objects, containers) that the
  current rule-based planner cannot solve, to create headroom for future
  planners to show improvement.

## Example (feedback loop comparison)

- **Date:** 2026-07-23
- **Commit:** `<fill in after first commit>`
- **Planner:** feedback (NaivePlanner + 1-retry repair) vs. no-feedback
- **Dataset:** `sample_tasks.yaml` (12 tasks)
- **Number of tasks:** 12
- **Success rate:** with feedback 100%, without feedback 0%
- **Average steps:** with feedback 4.0 (after 1 replan), without feedback 1.0
- **Errors:** without feedback: `precondition_failed` on every task (missing
  `move_to` before pick/place)
- **Changes:** n/a (first comparison run)
- **Interpretation:** the single-retry feedback loop fully recovers from the
  intentionally naive initial plan on this task set, demonstrating that
  execution feedback has clear value even with a simple rule-based repair.
- **Next action:** measure whether a single retry is still sufficient once
  harder, multi-step tasks are added.

## Generalized feedback loop + harder tasks (task_013, task_014)

- **Date:** 2026-07-23
- **Commit:** `3277f14`
- **Planner:** rule-based, feedback (both now run against 14 tasks)
- **Dataset:** sample_tasks.yaml (14 tasks: 12 single-object + 2 hard)
- **Number of tasks:** 14
- **Success rate:** rule-based 85.71% (12/14), feedback 85.71% (12/14)
- **Average steps:** rule-based 3.93
- **Errors:** task_013 -> precondition_failed (RuleBasedPlanner never emits
  open_container, so placing into the closed supply_box fails); task_014 ->
  goal_not_achieved (RuleBasedPlanner only moves one of the two mentioned
  objects, so the two-object goal is never fully satisfied)
- **Changes:** added container open/closed preconditions to ToyRobotEnv
  (pick/place now check container_open); added task_013 (container) and
  task_014 (two objects) to sample_tasks.yaml as intentionally
  RuleBasedPlanner-unsolvable tasks; generalized the feedback/replan
  interface so AnthropicPlanner and GeminiPlanner can use it too
- **Interpretation:** these two new tasks isolate exactly the two
  structural limitations RuleBasedPlanner was already documented to have
  (single-object extraction, no container awareness) rather than just
  restating the same "move one object" pattern with different words. They
  give LLM-backed planners a genuine chance to show an advantage instead of
  just matching RuleBasedPlanner's steps.
- **Next action:** run task_013/task_014 against AnthropicPlanner and
  GeminiPlanner (with `--delay-seconds` for Gemini's free tier) and record
  whether they succeed where RuleBasedPlanner cannot, and whether the
  generalized feedback loop helps them recover from a first failed attempt.

## GeminiPlanner vs RuleBasedPlanner on the hard tasks (task_013, task_014)

- **Date:** 2026-07-23
- **Commit:** `3277f14`
- **Planner:** gemini (gemini-flash-latest) vs rule-based
- **Dataset:** sample_tasks.yaml, task_013 and task_014 only
- **Number of tasks:** 2
- **Success rate:** gemini 100% (2/2), rule-based 0% (0/2)
- **Average steps:** gemini task_013=4, task_014=7 (single attempt, no replan needed)
- **Errors:** none for gemini; rule-based fails both as documented in
  tests/test_planner.py (precondition_failed / goal_not_achieved)
- **Changes:** none (evaluation run only)
- **Interpretation:** this is the first concrete evidence that GeminiPlanner
  solves tasks RuleBasedPlanner structurally cannot: it correctly inserted
  open_container before placing into the closed supply_box, and correctly
  planned two full pick-and-place cycles for the two-object task, without
  needing a replan. This validates task_013/task_014 as a meaningful
  comparison point, not just a restated "move one object" task.
- **Next action:** run task_013/task_014 against AnthropicPlanner once
  credits are available, for a 3-way comparison; consider adding more
  multi-object / multi-container tasks to see where GeminiPlanner's
  planning starts to break down.

## Template: GroundTruthPerception vs. VLMPerception (Phase 4)

- **Date:**
- **Commit:**
- **Planner:**
- **Perception:** ground-truth vs vlm (vision-provider: anthropic/gemini)
- **Dataset:**
- **Number of tasks:**
- **Success rate:** ground-truth ___%, vlm ___%
- **Average steps:**
- **Errors:** (note any perception_error-style failures, i.e. the VLM
  misread the scene -- e.g. missed an object, mislabeled a location, or
  read the robot's position wrong)
- **Changes:**
- **Interpretation:**
- **Next action:**

## Phase 4 implementation notes (bug found and fixed during development)

- **Date:** 2026-07-23
- **Commit:** `7e98d38`
- **Change:** Added `geniac_cap.perception` (`GroundTruthPerception`,
  `VLMPerception`, `renderer.py`), wired into the Evaluator/CLI via
  `--perception` / `--vision-provider`, plus a `render-scene` CLI command.
- **Bug found:** CLI error messages containing square brackets (e.g. "pip
  install -e '.[vision]'") were being silently mangled by Rich's markup
  parser, which treats `[text]` as a style tag. `[vision]` was disappearing
  from the printed message entirely.
- **Fix:** escape dynamic exception text with `rich.markup.escape()` before
  interpolating it into `console.print()` calls; added a regression test
  (`tests/test_cli.py::test_error_messages_with_brackets_are_not_mangled_by_rich_markup`).
- **Interpretation:** this is a good example of why error-path testing
  matters even for "just a CLI" — the bug only shows up when an error
  message happens to contain characters meaningful to the display library,
  which is easy to miss when testing the happy path.

## VLMPerception first real test (Gemini)

- **Date:** 2026-07-23
- **Commit:** `713626e`
- **Planner:** gemini, **Perception:** vlm (vision-provider: gemini)
- **Dataset:** task_001 (single task)
- **Result:** VLMPerception succeeded (200 OK) -- the scene render was
  correctly read by gemini-flash-latest. The subsequent GeminiPlanner call
  hit a 429 due to the free tier's *daily* quota
  (GenerateRequestsPerDayPerProjectPerModel-FreeTier, limit 20/day), not
  the per-minute limit `--delay-seconds` addresses.
- **Interpretation:** Phase 4's core mechanism (render scene -> VLM reads
  it -> PlanningContext) is validated end-to-end against a real API. The
  planner-side failure is purely a quota exhaustion artifact from a full
  day of testing, not a code issue.
- **Next action:** re-run `run-task --perception vlm` and a full
  `evaluate --perception vlm` comparison once the daily quota resets (or
  with a fresh API key/project), and log ground-truth vs. vlm success
  rates using the template above.

## Step 0 of the model-improvement roadmap: evaluation tracking

- **Date:** 2026-07-23
- **Commit:** `d8f0794`
- **Change:** Added `evaluate --compare-to <path.json> --label "..."`,
  backed by `geniac_cap.evaluation.metrics.load_summary` /
  `compare_summaries` / `SummaryComparison.as_readme_row`. Loads a
  previously saved evaluation JSON, diffs success rate and average steps
  against the current run, and prints a row ready to paste into README's
  "Model improvement log" table.
- **Interpretation:** this is purely infrastructure (no planner/prompt
  change), so no success-rate delta is expected. Verified with a
  same-vs-same rule-based run: 85.71% -> 85.71% (+0.00%), confirming the
  diff logic reports zero change correctly.
- **Next action:** use this for every subsequent step
  (1-5) in docs/model-improvement-roadmap.md, pasting the printed row into
  README after each change.

## Step 1 of the model-improvement roadmap: planner cascade

- **Date:** 2026-07-23
- **Commit:** `772882b`
- **Change:** Added `geniac_cap.evaluation.cascade.run_single_task_cascade`
  and `Evaluator.evaluate_cascade`, exposed via `--cascade
  "rule-based,gemini"` on `run-task` / `evaluate`. Tries planners in order
  per task, stopping at the first that actually achieves the goal.
- **Dataset:** all 14 sample tasks, cascade `rule-based -> mock-llm` (a
  free stand-in for `gemini`/`anthropic` used here since no real API key is
  available in this environment; the routing logic is identical regardless
  of which planner is in the second tier)
- **Result:** 12/14 tasks (85.7%) were solved by tier 1 (RuleBasedPlanner)
  alone -- tier 2 was invoked for only 2/14 tasks (task_013, task_014, the
  two tasks documented as beyond RuleBasedPlanner's structural
  limitations). Overall success rate: 85.71% (identical to running
  RuleBasedPlanner alone, since mock-llm's fallback logic also delegates to
  RuleBasedPlanner for unrecognized instructions in this sandbox -- the
  same *routing* would apply with a genuinely more capable tier-2 planner).
- **Interpretation:** with a real LLM as tier 2 (e.g. Gemini), this
  cascade would cut LLM API calls by ~85.7% compared to running the LLM
  planner on all 14 tasks, while only needing the LLM for the tasks that
  actually require it. Directly mitigates the free-tier daily quota
  exhaustion hit during Phase 4 testing.
- **Next action:** re-run `--cascade "rule-based,gemini"` once daily quota
  allows, to confirm tier 2 (real Gemini) actually solves task_013/014 when
  reached (already independently confirmed in the Phase 4 log above), and
  record the real API-call count saved.

## Step 2 of the model-improvement roadmap: synthetic task augmentation

- **Date:** 2026-07-23
- **Commit:** `d0b522a`
- **Change:** Added `geniac_cap.tasks.generator` (single-object, two-object,
  container templates over combinatorial color/shape/location/container
  pools) and `save_tasks_to_yaml`, exposed via `generate-tasks --single N
  --two-object N --container N --seed S --output path.yaml`.
- **Dataset:** 16 generated tasks (8 single-object, 4 two-object, 4
  container), seed 42, evaluated with RuleBasedPlanner
- **Result:** success_rate 50.00% (8/16) -- exactly the single-object tasks
  succeeded (100%), two-object tasks failed with `goal_not_achieved`
  (100%), container tasks failed with `precondition_failed` (100%).
- **Interpretation:** the generated tasks reproduce the exact same
  structural failure pattern as the hand-authored task_013/task_014, at
  arbitrary scale and zero API cost. This validates the generator's
  templates are faithful to the real structural limitations, not just
  superficially similar tasks.
- **Next action:** use `generate-tasks` with a larger `--two-object` /
  `--container` count as a bigger benchmark for Step 4 (prompt
  hill-climbing) and future LLM-vs-RuleBasedPlanner comparisons, so results
  aren't based on just 2 hand-authored examples.

## Step 3 of the model-improvement roadmap: vocabulary distillation

- **Date:** 2026-07-23
- **Commit:** `e6b1aea` (inferred from the Step 4 push range shown below; no
  explicit `git push` output was pasted back for this step specifically)
- **Change:** Added `geniac_cap.planners.vocabulary_distiller`
  (`VocabularyDistiller`, `filter_probes_needing_harvest`,
  `default_probe_instructions`) and `harvest-vocabulary --provider
  anthropic|gemini`. Filters a built-in probe list to instructions
  RuleBasedPlanner can't parse, asks an LLM which known object/location
  each refers to, and prints/saves a human-reviewable proposal for
  OBJECT_SYNONYMS/LOCATION_SYNONYMS. Nothing is auto-applied to source.
- **Dataset:** 11 built-in probe instructions against sample_tasks.yaml's
  vocabulary
- **Result (filtering logic only, no real API key available in this
  environment):** 9/11 probes correctly identified as needing harvest (2
  were already resolvable, incidentally, via substring quirks in the
  existing matcher -- e.g. "bookshelf" contains the literal substring
  "book"). Verified end-to-end with a fake client that harvest() correctly
  proposes new synonym entries and skips ones already known.
- **Interpretation:** the filtering step means this only ever spends API
  calls on genuine gaps, keeping cost proportional to what's actually
  missing rather than the full probe list.
- **Next action:** run `harvest-vocabulary` with a real API key, review the
  proposed snippet, and manually merge accepted entries into
  `planners/rule_based.py`'s OBJECT_SYNONYMS/LOCATION_SYNONYMS; then
  re-run the 9 probe instructions through RuleBasedPlanner to confirm they
  now succeed.

## Step 4 of the model-improvement roadmap: prompt hill-climbing

- **Date:** 2026-07-23
- **Commit:** `968bd30`
- **Change:** Added `AnthropicPlanner`/`GeminiPlanner` `system_prompt`
  override, `geniac_cap.planners.prompt_hillclimb` (`hill_climb`,
  `PromptMutation`, `DEFAULT_MUTATIONS`), and `hill-climb-prompt --planner
  anthropic|gemini`. Greedily accepts prompt mutations that don't decrease
  success rate, reusing Step 0's EvaluationSummary as the reward signal.
- **Dataset:** task_013 (the container task) only, with a fake Gemini
  client simulating an LLM that only remembers to call open_container
  when the prompt explicitly reminds it to (a realistic failure mode: the
  model otherwise correctly identifies the object/destination but omits
  the container step)
- **Result:** baseline 0% -> after `container_reminder` mutation: 100%
  (+100%). The `self_check_names` mutation (tried first) had no effect and
  was still accepted (ties count as "not worse"); `multi_object_reminder`
  had no effect on this single-task, container-only run.
- **Interpretation:** this demonstrates the full mechanism working
  end-to-end: a specific, plausible LLM failure mode (forgetting a
  required action) is fixed by a targeted prompt addition, and the
  hill-climbing loop correctly identifies and keeps only the mutation that
  helped, using nothing but the existing Evaluator as ground truth.
- **Next action:** run `hill-climb-prompt --planner gemini` for real
  against the full 14-task set (or generated tasks from Step 2) once a key
  is available; if `container_reminder` and/or `multi_object_reminder`
  are accepted, review the final prompt and consider merging it into
  `planners/llm_prompts.py`'s `ACTION_PLAN_SYSTEM_PROMPT` default.

## Step 5 of the model-improvement roadmap: contextual bandit for cascade selection

- **Date:** 2026-07-23
- **Commit:** `2ba18da`
- **Change:** Added `geniac_cap.evaluation.bandit`
  (`EpsilonGreedyBandit`, `run_bandit_episode`), `Evaluator.evaluate_bandit`,
  and `bandit-cascade --arms "rule-based;rule-based,gemini" --epsilon
  --seed`. Learns, per task-difficulty context (easy/medium/hard), which
  cascade order tends to succeed most efficiently.
- **Dataset:** all 14 sample tasks, 3 episodes (42 task-runs total), arms
  `("rule-based",)` vs `("rule-based","smart-llm")`, where `smart-llm` is a
  fake planner (no real API) that can actually solve the container
  (task_013) and two-object (task_014) tasks -- simulating a genuinely
  more capable LLM tier, to demonstrate the bandit learning a real
  capability gap rather than a coincidence.
- **Result:** learned best arm per context:
  - `easy`: `("rule-based",)` -- average reward 1.0 for both arms (ties),
    correctly settling on the cheaper option
  - `medium`: `("rule-based",)` -- same as above
  - `hard`: `("rule-based","smart-llm")` -- average reward 0.964 vs 0.5 for
    rule-based alone (task_012 is labeled "hard" but rule-based solves it;
    task_013/014 need the second tier)
- **Interpretation:** the bandit correctly discovered, purely from
  ToyRobotEnv's free reward signal, that the LLM tier is only worth its
  cost for "hard"-labeled tasks -- without being told this in advance. This
  validates the context-dependent design (vs. a single global "which
  planner is best" answer) actually captures something a flat cascade
  order can't: a fixed `rule-based->gemini` cascade already gets this for
  free by construction, but the bandit's value is in *automatically
  discovering* which contexts need which strategy, which matters more once
  more arms/strategies are added.
- **Next action:** re-run with real `gemini`/`anthropic` as the second
  tier once quota allows; consider adding a third arm (e.g.
  `anthropic`-only) to see whether the bandit correctly avoids it if it's
  costlier/less reliable than the cascade.

## Created a genuinely hard benchmark (benchmarks/hard_benchmark_v1.yaml)

- **Date:** 2026-07-23
- **Commit:** (fill in after pushing)
- **Change:** Realized the original 14-task `sample_tasks.yaml` cannot
  distinguish "the mechanism works" from "the mechanism actually helped,"
  because a real Gemini run already solves all 14 tasks -- there was no
  headroom left. Generated `benchmarks/hard_benchmark_v1.yaml` (60 tasks:
  20 single-object, 20 two-object, 20 container; `generate-tasks --single
  20 --two-object 20 --container 20 --seed 100`) and saved it, plus a
  RuleBasedPlanner baseline result, as tracked (non-gitignored) files
  under `benchmarks/` specifically so future roadmap verification has a
  fixed, reusable, genuinely-hard reference point.
- **Result:** RuleBasedPlanner baseline on the new benchmark: 20/60
  (33.33%) -- exactly the 20 single-object tasks succeed, all 20
  two-object tasks fail (`goal_not_achieved`), all 20 container tasks fail
  (`precondition_failed`). 40/60 tasks (66.7%) are out of reach for
  RuleBasedPlanner, versus only 2/14 (14.3%) on the original sample set.
- **Interpretation:** this is the honest fix for a gap identified while
  reviewing today's "Model improvement log": most of Steps 1/3/4/5 were
  only validated with fake/mock clients using contrived failure modes
  (e.g. Step 4's `container_reminder` fix was demonstrated against a
  simulated bug that has never actually been observed in a real Gemini
  run). A genuinely hard, larger benchmark is a precondition for any
  future claim that these techniques measurably improve results, not just
  that their internal logic is correct.
- **Next action:** once quota allows, run RuleBasedPlanner, the planner
  cascade, and (after harvest-vocabulary proposals are reviewed and
  merged) RuleBasedPlanner again against `benchmarks/hard_benchmark_v1.yaml`
  with real Anthropic/Gemini calls, using `--compare-to
  benchmarks/baseline_rule_based_v1.json` each time to get real,
  comparable deltas for the README's Model improvement log.

## Added GroqPlanner as a multi-provider cascade fallback

- **Date:** 2026-07-24
- **Commit:** (fill in after pushing)
- **Change:** Added `GroqPlanner` (`src/geniac_cap/planners/groq_planner.py`),
  mirroring AnthropicPlanner/GeminiPlanner's design (lazy import, injectable
  client, `system_prompt` override, `supports_feedback`). Groq's API is
  OpenAI-compatible; its `response_format={"type":"json_object"}` requires
  a top-level JSON *object*, so a Groq-specific instruction asks the model
  to wrap the action array as `{"actions": [...]}` (parsing accepts both
  the wrapped and bare-array shape). Registered as `--planner groq`,
  usable in `--cascade`/`bandit-cascade`/`hill-climb-prompt`.
- **Motivation:** Gemini's free tier is limited to ~20 requests/day for
  the current default model, which was already hit once during Phase 4
  testing. Groq's free tier is much larger (~14,400 requests/day, no
  credit card), so `--cascade "rule-based,gemini,groq"` gives automatic,
  zero-extra-code fallback once Gemini's quota is exhausted -- a 429 from
  Gemini is just another planning failure to the existing cascade logic in
  evaluation/cascade.py.
- **Verified:** fake-client tests confirm JSON parsing (both bare-array
  and `{"actions": [...]}`-wrapped responses), markdown-fence stripping,
  the feedback/replan loop, and custom `system_prompt` injection. A real
  3-tier CLI dry run (`run-task --cascade "rule-based,gemini,groq"`, no
  keys set) confirmed the cascade correctly tries all three tiers in order
  and reports the last one's failure reason -- no crashes.
- **Next action:** get a real Groq API key (free, https://console.groq.com)
  and re-run the Step 1/5 real-API verification plan
  (docs/rigorous-verification-plan.md) using `--cascade
  "rule-based,gemini,groq"` on `benchmarks/train_mini.yaml`, so Gemini's
  daily quota no longer blocks a full day's iteration.

## First real 3-tier cascade verification (rule-based -> gemini -> groq) on train_mini

- **Date:** 2026-07-24
- **Commit:** (fill in after pushing)
- **Command:** `evaluate --cascade "rule-based,gemini,groq" --tasks-file benchmarks/train_mini.yaml --delay-seconds 13 --compare-to benchmarks/baseline_rule_based_train_mini.json`
- **Dataset:** `benchmarks/train_mini.yaml` (18 tasks: 6 single-object, 6
  two-object, 6 container) -- the "genuinely hard" benchmark created
  specifically because the original 14-task sample set had no headroom
- **Result:** success_rate **33.33% -> 100.00% (+66.67%)**, average steps
  3.67 -> 5.83. Full real breakdown by tier:
  - tier 1 (rule-based): 6/18 (all single-object, as designed)
  - tier 2 (gemini): 3/18 (2 two-object, 1 container) -- succeeded before
    hitting the day's already-partially-used quota
  - tier 3 (groq): 9/18 -- caught every task where Gemini returned `429`
    (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, limit 20/day)
- **This is real, not simulated (✅):** no fake/mock client was used. This
  is the first entry in the log that is a genuine, verified improvement on
  a benchmark designed to have real headroom -- not a mechanism check
  against a contrived failure mode.
- **Direct validation of today's Groq addition:** without the groq tier,
  this run would have stopped at rule-based(6) + gemini(3) = **9/18
  (50%)**, since Gemini's daily quota was already exhausted partway
  through testing today and there would have been no third tier to catch
  the rest. Groq specifically rescued 9/9 remaining tasks. This is a
  concrete, not hypothetical, demonstration of why the cascade fallback
  chain matters.
- **Bonus finding -- the feedback loop caught a real mistake:** on
  `synth_container_006`, GroqPlanner's first attempt incorrectly referenced
  the container name ("toolbox") as if it were a pickable object, failing
  with `object_not_found`. The existing feedback/replan mechanism (Step 4
  infrastructure, `supports_feedback=True`) triggered automatically, and
  GroqPlanner's second attempt succeeded. This is the first real (not
  simulated) evidence that the feedback loop recovers from an actual model
  mistake, not just a contrived one.
- **Caveat (per docs/rigorous-verification-plan.md):** this used
  `train_mini`, not the held-out `test` split -- but that's fine here
  because the cascade is a fixed procedure, not something tuned against
  these specific results (unlike Steps 3/4/5, which should still reserve
  `test` for their final numbers).
- **Next action:** run the same command against the full `train` split
  (36 tasks) and eventually the held-out `test` split, to confirm this
  holds at larger scale; re-run Steps 3 (vocabulary distillation with a
  real key) and 5 (bandit) for real now that a working 3-tier fallback
  exists to avoid being blocked by Gemini's quota mid-run.
