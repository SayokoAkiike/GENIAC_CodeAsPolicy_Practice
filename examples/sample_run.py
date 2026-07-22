"""Example: use geniac_cap as a library instead of the CLI.

Run with:
    python examples/sample_run.py
"""

from __future__ import annotations

from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.evaluation.evaluator import Evaluator, run_single_task
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.planners.base import PlanningContext
from geniac_cap.planners.feedback import FeedbackPlanner
from geniac_cap.planners.rule_based import RuleBasedPlanner
from geniac_cap.tasks.loader import load_tasks


def run_one_task_manually() -> None:
    tasks = load_tasks()
    task = tasks[0]

    env = ToyRobotEnv.from_task_state(task.initial_state)
    context = PlanningContext(
        objects=env.list_objects(),
        locations=env.list_locations(),
        object_locations=dict(env.state.object_locations),
        robot_location=env.state.robot_location,
    )

    planner = RuleBasedPlanner()
    plan = planner.plan(task.instruction, context)
    print(f"Instruction: {task.instruction}")
    print("Plan:", [f"{s.action.value}({s.args})" for s in plan.steps])

    result = SafeExecutor().execute(env, plan, task.goal_state)
    print("Success:", result.success, "| Goal achieved:", result.goal_achieved)


def evaluate_two_planners() -> None:
    tasks = load_tasks()
    evaluator = Evaluator()

    rule_based_summary = evaluator.evaluate(tasks, RuleBasedPlanner())
    print(f"\nRuleBasedPlanner success rate: {rule_based_summary.success_rate:.0%}")

    feedback_summary = evaluator.evaluate(tasks, FeedbackPlanner(), allow_feedback=True)
    print(f"FeedbackPlanner (with feedback) success rate: {feedback_summary.success_rate:.0%}")

    no_feedback_summary = evaluator.evaluate(tasks, FeedbackPlanner(), allow_feedback=False)
    print(f"FeedbackPlanner (no feedback) success rate: {no_feedback_summary.success_rate:.0%}")


def run_single_task_directly() -> None:
    task = load_tasks()[2]
    outcome = run_single_task(task, RuleBasedPlanner(), SafeExecutor())
    print(f"\nTask {task.task_id}: success={outcome.success}, steps={outcome.steps}")


if __name__ == "__main__":
    run_one_task_manually()
    evaluate_two_planners()
    run_single_task_directly()
