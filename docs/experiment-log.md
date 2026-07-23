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
- **Commit:** (fill in after pushing)
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
- **Commit:** (fill in after pushing)
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
- **Commit:** (fill in after pushing)
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
- **Commit:** (fill in after pushing)
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
- **Commit:** (fill in after pushing)
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
- **Commit:** (fill in after pushing)
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
