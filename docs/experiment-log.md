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
