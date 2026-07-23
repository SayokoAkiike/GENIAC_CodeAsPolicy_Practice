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

## Gemini vs Rule-based comparison

- **Date:** 2026-07-23
- **Commit:** (この後pushするコミットハッシュ)
- **Planner:** gemini (gemini-flash-latest) vs rule-based
- **Dataset:** sample_tasks.yaml (12 tasks)
- **Number of tasks:** 12
- **Success rate:** gemini 100%, rule-based 100%
- **Average steps:** gemini 3.25, rule-based 4.0
- **Errors:** none (after adding --delay-seconds 13 to stay under Gemini's free-tier 5 req/min limit; without the delay, later tasks hit 429)
- **Changes:** added GeminiPlanner + --delay-seconds option
- **Interpretation:** Gemini matched RuleBasedPlanner's success rate but produced shorter plans by skipping redundant move_to steps when the robot was already co-located with the target object. Free-tier rate limits are the main practical constraint, not planning quality.
- **Next action:** try harder/multi-object tasks where RuleBasedPlanner would fail, to see if Gemini's more flexible planning gives it an actual edge (not just efficiency).

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
