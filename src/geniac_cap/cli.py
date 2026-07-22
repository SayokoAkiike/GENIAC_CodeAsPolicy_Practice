"""Command-line interface for geniac_cap.

Run ``python -m geniac_cap.cli --help`` to see all commands, or install the
package and run ``geniac-cap --help``.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from geniac_cap.config import settings
from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.evaluation.evaluator import Evaluator, run_single_task
from geniac_cap.exceptions import GeniacCapError
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.planners.base import BasePlanner, PlanningContext
from geniac_cap.planners.feedback import FeedbackPlanner
from geniac_cap.planners.mock_llm import MockLLMPlanner
from geniac_cap.planners.rule_based import RuleBasedPlanner
from geniac_cap.tasks.loader import get_task_by_id, load_tasks
from geniac_cap.utils.logging import configure_logging, get_logger

app = typer.Typer(add_completion=False, help="GENIAC Code-as-Policy practice CLI")
console = Console()
logger = get_logger(__name__)

_PLANNERS: dict[str, type[BasePlanner] | None] = {
    "rule-based": RuleBasedPlanner,
    "feedback": FeedbackPlanner,
    "mock-llm": MockLLMPlanner,
}


def _make_planner(name: str) -> BasePlanner:
    if name not in _PLANNERS:
        raise typer.BadParameter(f"Unknown planner '{name}'. Choose from: {list(_PLANNERS)}")
    return _PLANNERS[name]()  # type: ignore[misc]


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable DEBUG logging"),
) -> None:
    """GENIAC-PRIZE Theme 2 Code-as-Policy practice project."""

    configure_logging("DEBUG" if verbose else settings.log_level)


@app.command("list-tasks")
def list_tasks() -> None:
    """List all sample tasks with id, category, difficulty and instruction."""

    tasks = load_tasks()
    table = Table(title="Sample Tasks")
    table.add_column("task_id")
    table.add_column("category")
    table.add_column("difficulty")
    table.add_column("instruction")
    for task in tasks:
        table.add_row(task.task_id, task.category.value, task.difficulty.value, task.instruction)
    console.print(table)


@app.command("show-task")
def show_task(task_id: str = typer.Option(..., "--task-id")) -> None:
    """Show full details of a single task."""

    try:
        task = get_task_by_id(task_id)
    except GeniacCapError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    console.print_json(data=task.model_dump(mode="json"))


@app.command("run-task")
def run_task(
    task_id: str = typer.Option(..., "--task-id"),
    planner: str = typer.Option("rule-based", "--planner", help=f"One of: {list(_PLANNERS)}"),
) -> None:
    """Run a single task with the chosen planner and print the outcome."""

    try:
        task = get_task_by_id(task_id)
    except GeniacCapError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    planner_obj = _make_planner(planner)
    executor = SafeExecutor()
    outcome = run_single_task(task, planner_obj, executor)

    status = "[green]SUCCESS[/green]" if outcome.success else "[red]FAILED[/red]"
    console.print(f"Task [bold]{task.task_id}[/bold]: {status}")
    console.print(f"  instruction: {task.instruction}")
    console.print(f"  planner: {outcome.planner_name}")
    console.print(f"  steps: {outcome.steps}")
    console.print(f"  replanned: {outcome.replanned}")
    if outcome.failure_reason:
        console.print(f"  failure_reason: {outcome.failure_reason.value}")


@app.command("demo")
def demo() -> None:
    """Run a short end-to-end demo: one task, rule-based planner, printed trace."""

    tasks = load_tasks()
    task = tasks[0]
    console.rule("[bold]Code-as-Policy Demo[/bold]")
    console.print(f"Instruction: [italic]{task.instruction}[/italic]")

    env = ToyRobotEnv.from_task_state(task.initial_state)
    context = PlanningContext(
        objects=env.list_objects(),
        locations=env.list_locations(),
        object_locations=dict(env.state.object_locations),
        robot_location=env.state.robot_location,
    )
    planner = RuleBasedPlanner()
    plan = planner.plan(task.instruction, context)

    console.print("\n[bold]Generated plan:[/bold]")
    for i, action in enumerate(plan.steps):
        console.print(f"  {i}. {action.action.value}({action.args})")

    executor = SafeExecutor()
    result = executor.execute(env, plan, task.goal_state)

    console.print("\n[bold]Execution log:[/bold]")
    for log in result.logs:
        mark = "[green]OK[/green]" if log.success else "[red]FAIL[/red]"
        console.print(f"  step {log.step_index} {mark}: {log.message}")

    console.print(
        f"\nGoal achieved: {'[green]yes[/green]' if result.goal_achieved else '[red]no[/red]'}"
    )


@app.command("evaluate")
def evaluate(
    planner: str = typer.Option("rule-based", "--planner", help=f"One of: {list(_PLANNERS)}"),
    tasks_file: str = typer.Option(
        None, "--tasks-file", help="Optional path to a custom tasks YAML"
    ),
    no_feedback: bool = typer.Option(
        False,
        "--no-feedback",
        help="Disable the single-retry feedback loop even for the feedback planner",
    ),
) -> None:
    """Evaluate a planner across all sample tasks and save JSON/CSV results."""

    tasks = load_tasks(tasks_file)
    planner_obj = _make_planner(planner)
    evaluator = Evaluator()

    summary = evaluator.evaluate(tasks, planner_obj, allow_feedback=not no_feedback)
    json_path, csv_path = evaluator.save_results(summary)

    table = Table(title=f"Evaluation summary — planner: {summary.planner_name}")
    table.add_column("metric")
    table.add_column("value")
    table.add_row("total_tasks", str(summary.total_tasks))
    table.add_row("successful_tasks", str(summary.successful_tasks))
    table.add_row("failed_tasks", str(summary.failed_tasks))
    table.add_row("success_rate", f"{summary.success_rate:.2%}")
    table.add_row("planning_error_count", str(summary.planning_error_count))
    table.add_row("execution_error_count", str(summary.execution_error_count))
    table.add_row("invalid_action_count", str(summary.invalid_action_count))
    table.add_row("average_steps", f"{summary.average_steps:.2f}")
    table.add_row("average_execution_time", f"{summary.average_execution_time:.4f}s")
    console.print(table)

    if summary.failure_breakdown:
        console.print(f"Failure breakdown: {summary.failure_breakdown}")

    console.print(f"\nSaved: {json_path}")
    console.print(f"Saved: {csv_path}")


if __name__ == "__main__":
    app()
