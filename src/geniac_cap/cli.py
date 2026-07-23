"""Command-line interface for geniac_cap.

Run ``python -m geniac_cap.cli --help`` to see all commands, or install the
package and run ``geniac-cap --help``.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from geniac_cap.config import settings
from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.evaluation.cascade import run_single_task_cascade
from geniac_cap.evaluation.evaluator import Evaluator, run_single_task
from geniac_cap.evaluation.metrics import SummaryLoadError, compare_summaries, load_summary
from geniac_cap.exceptions import GeniacCapError
from geniac_cap.execution.executor import SafeExecutor
from geniac_cap.perception.base import BasePerception
from geniac_cap.perception.ground_truth import GroundTruthPerception
from geniac_cap.perception.renderer import render_scene
from geniac_cap.perception.vlm_perception import VLMPerception
from geniac_cap.planners.anthropic_planner import AnthropicPlanner
from geniac_cap.planners.base import BasePlanner, PlanningContext
from geniac_cap.planners.feedback import FeedbackPlanner
from geniac_cap.planners.gemini_planner import GeminiPlanner
from geniac_cap.planners.mock_llm import MockLLMPlanner
from geniac_cap.planners.rule_based import LOCATION_SYNONYMS, OBJECT_SYNONYMS, RuleBasedPlanner
from geniac_cap.planners.vocabulary_distiller import (
    VocabularyDistiller,
    default_probe_instructions,
    filter_probes_needing_harvest,
)
from geniac_cap.tasks.generator import generate_tasks
from geniac_cap.tasks.loader import get_task_by_id, load_tasks, save_tasks_to_yaml
from geniac_cap.utils.logging import configure_logging, get_logger

app = typer.Typer(add_completion=False, help="GENIAC Code-as-Policy practice CLI")
console = Console()
logger = get_logger(__name__)

_PLANNERS: dict[str, type[BasePlanner] | None] = {
    "rule-based": RuleBasedPlanner,
    "feedback": FeedbackPlanner,
    "mock-llm": MockLLMPlanner,
    "anthropic": AnthropicPlanner,
    "gemini": GeminiPlanner,
}


def _make_planner(name: str) -> BasePlanner:
    if name not in _PLANNERS:
        raise typer.BadParameter(f"Unknown planner '{name}'. Choose from: {list(_PLANNERS)}")
    return _PLANNERS[name]()  # type: ignore[misc]


def _make_perception(name: str, vision_provider: str) -> BasePerception:
    if name == "ground-truth":
        return GroundTruthPerception()
    if name == "vlm":
        return VLMPerception(provider=vision_provider)
    raise typer.BadParameter(f"Unknown perception '{name}'. Choose from: ground-truth, vlm")


def _make_cascade(spec: str) -> list[BasePlanner]:
    """Parse a comma-separated '--cascade' spec like 'rule-based,gemini' into
    planner instances, in the given fallback order (see Step 1 of
    docs/model-improvement-roadmap.md).
    """

    names = [name.strip() for name in spec.split(",") if name.strip()]
    if not names:
        raise typer.BadParameter("--cascade must list at least one planner name")
    return [_make_planner(name) for name in names]


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


@app.command("harvest-vocabulary")
def harvest_vocabulary(
    provider: str = typer.Option(
        "anthropic", "--provider", help="Vision/LLM provider to ask: anthropic or gemini"
    ),
    output: str = typer.Option(
        "results/vocabulary_proposal.json", "--output", help="Where to save the proposal JSON"
    ),
) -> None:
    """Harvest new RuleBasedPlanner vocabulary via an LLM (Step 3:
    docs/model-improvement-roadmap.md).

    Runs a small built-in set of paraphrases through RuleBasedPlanner,
    skips the ones it already handles, and asks an LLM to identify which
    known object/location the rest refer to. Prints a human-reviewable
    proposal for OBJECT_SYNONYMS / LOCATION_SYNONYMS -- nothing is applied
    to source code automatically.
    """

    known_objects = sorted(OBJECT_SYNONYMS.keys())
    known_locations = sorted(LOCATION_SYNONYMS.keys())
    probes = default_probe_instructions()
    needs_harvest = filter_probes_needing_harvest(probes, known_objects, known_locations)

    console.print(
        f"{len(needs_harvest)}/{len(probes)} probe instruction(s) need harvesting "
        f"(the rest RuleBasedPlanner already handles)."
    )
    if not needs_harvest:
        console.print("Nothing to harvest.")
        return

    try:
        distiller = VocabularyDistiller(provider=provider)
        proposal = distiller.harvest(
            needs_harvest,
            known_objects,
            known_locations,
            existing_object_synonyms=OBJECT_SYNONYMS,
            existing_location_synonyms=LOCATION_SYNONYMS,
        )
    except GeniacCapError as exc:
        console.print(f"[red]Error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=1) from exc

    if proposal.is_empty():
        if proposal.unresolved_instructions:
            console.print("No new vocabulary proposed (all probes were unresolved -- see below).")
        else:
            console.print("No new vocabulary proposed (LLM found nothing new).")
    else:
        console.print(escape(proposal.as_python_snippet()))

    if proposal.unresolved_instructions:
        console.print(f"\n{len(proposal.unresolved_instructions)} instruction(s) unresolved.")

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "object_synonyms": proposal.object_synonyms,
                "location_synonyms": proposal.location_synonyms,
                "unresolved_instructions": proposal.unresolved_instructions,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    console.print(f"\nSaved proposal to: {output_path}")


@app.command("generate-tasks")
def generate_tasks_cmd(
    single: int = typer.Option(
        10, "--single", help="Number of single-object 'move X to Y' tasks"
    ),
    two_object: int = typer.Option(
        5,
        "--two-object",
        help="Number of two-object tasks (documented to be hard for RuleBasedPlanner)",
    ),
    container: int = typer.Option(
        5,
        "--container",
        help="Number of container tasks (documented to be hard for RuleBasedPlanner)",
    ),
    seed: int = typer.Option(0, "--seed", help="Random seed, for reproducible generation"),
    output: str = typer.Option(
        "results/synthetic_tasks.yaml", "--output", help="Output YAML path"
    ),
) -> None:
    """Generate synthetic tasks (Step 2: docs/model-improvement-roadmap.md).

    Generates single-object, two-object, and container task variations from
    templates and saves them in the same YAML schema as sample_tasks.yaml,
    so they can be loaded with --tasks-file on evaluate/run-task.
    """

    tasks = generate_tasks(
        n_single=single, n_two_object=two_object, n_container=container, seed=seed
    )
    output_path = save_tasks_to_yaml(tasks, output)
    console.print(
        f"Generated {len(tasks)} task(s) "
        f"({single} single-object, {two_object} two-object, {container} container) "
        f"-> {output_path}"
    )


@app.command("show-task")
def show_task(task_id: str = typer.Option(..., "--task-id")) -> None:
    """Show full details of a single task."""

    try:
        task = get_task_by_id(task_id)
    except GeniacCapError as exc:
        console.print(f"[red]Error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=1) from exc
    console.print_json(data=task.model_dump(mode="json"))


@app.command("render-scene")
def render_scene_cmd(
    task_id: str = typer.Option(..., "--task-id"),
    output: str = typer.Option(
        None, "--output", help="Output PNG path (default: results/<task_id>_scene.png)"
    ),
) -> None:
    """Render a task's initial state as a PNG (Phase 4: VLM perception).

    Requires the 'vision' extra: pip install -e ".[vision]"
    """

    try:
        task = get_task_by_id(task_id)
    except GeniacCapError as exc:
        console.print(f"[red]Error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=1) from exc

    env = ToyRobotEnv.from_task_state(task.initial_state)
    try:
        png_bytes = render_scene(env)
    except GeniacCapError as exc:
        console.print(f"[red]Error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=1) from exc

    output_path = Path(output) if output else Path("results") / f"{task.task_id}_scene.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(png_bytes)
    console.print(f"Saved scene render to: {output_path}")


@app.command("run-task")
def run_task(
    task_id: str = typer.Option(..., "--task-id"),
    planner: str = typer.Option("rule-based", "--planner", help=f"One of: {list(_PLANNERS)}"),
    cascade: str = typer.Option(
        None,
        "--cascade",
        help=(
            "Comma-separated planner names tried in order, stopping at the "
            "first success, e.g. 'rule-based,gemini'. Overrides --planner."
        ),
    ),
    perception: str = typer.Option(
        "ground-truth", "--perception", help="One of: ground-truth, vlm"
    ),
    vision_provider: str = typer.Option(
        "anthropic", "--vision-provider", help="Used when --perception vlm: anthropic or gemini"
    ),
) -> None:
    """Run a single task with the chosen planner and print the outcome."""

    try:
        task = get_task_by_id(task_id)
    except GeniacCapError as exc:
        console.print(f"[red]Error:[/red] {escape(str(exc))}")
        raise typer.Exit(code=1) from exc

    perception_obj = _make_perception(perception, vision_provider)
    executor = SafeExecutor()

    if cascade:
        planners = _make_cascade(cascade)
        outcome = run_single_task_cascade(task, planners, executor, perception=perception_obj)
        planner_label = "cascade(" + "->".join(p.name for p in planners) + ")"
    else:
        planner_obj = _make_planner(planner)
        outcome = run_single_task(task, planner_obj, executor, perception=perception_obj)
        planner_label = outcome.planner_name

    status = "[green]SUCCESS[/green]" if outcome.success else "[red]FAILED[/red]"
    console.print(f"Task [bold]{task.task_id}[/bold]: {status}")
    console.print(f"  instruction: {task.instruction}")
    console.print(f"  planner: {planner_label} (solved by: {outcome.planner_name})")
    console.print(f"  perception: {perception_obj.name}")
    console.print(f"  steps: {outcome.steps}")
    console.print(f"  replanned: {outcome.replanned}")
    if outcome.failure_reason:
        console.print(f"  failure_reason: {outcome.failure_reason.value}")


@app.command("demo")
def demo() -> None:
    """Run a short end-to-end demo: one task, rule-based planner, printed trace."""

    task = get_task_by_id("task_006")  # "Move the red block to the blue shelf"
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
    cascade: str = typer.Option(
        None,
        "--cascade",
        help=(
            "Comma-separated planner names tried in order per task, stopping "
            "at the first success, e.g. 'rule-based,gemini'. Overrides --planner."
        ),
    ),
    tasks_file: str = typer.Option(
        None, "--tasks-file", help="Optional path to a custom tasks YAML"
    ),
    no_feedback: bool = typer.Option(
        False,
        "--no-feedback",
        help="Disable the single-retry feedback loop even for the feedback planner",
    ),
    delay_seconds: float = typer.Option(
        0.0,
        "--delay-seconds",
        help=(
            "Pause between tasks in seconds. Useful for rate-limited free-tier "
            "LLM APIs, e.g. '--delay-seconds 13' keeps Gemini's free tier "
            "(5 requests/minute) from hitting 429s across all 12 tasks."
        ),
    ),
    perception: str = typer.Option(
        "ground-truth", "--perception", help="One of: ground-truth, vlm"
    ),
    vision_provider: str = typer.Option(
        "anthropic", "--vision-provider", help="Used when --perception vlm: anthropic or gemini"
    ),
    compare_to: str = typer.Option(
        None,
        "--compare-to",
        help=(
            "Path to a previous evaluation JSON (see 'Saved:' output) to diff "
            "this run against. Prints a delta and a README-log-ready row "
            "(see docs/model-improvement-roadmap.md)."
        ),
    ),
    label: str = typer.Option(
        "", "--label", help="Short description of the change, used in the README-ready row"
    ),
) -> None:
    """Evaluate a planner across all sample tasks and save JSON/CSV results."""

    tasks = load_tasks(tasks_file)
    perception_obj = _make_perception(perception, vision_provider)
    evaluator = Evaluator()

    baseline_summary = None
    if compare_to:
        try:
            baseline_summary = load_summary(compare_to)
        except SummaryLoadError as exc:
            console.print(f"[red]Error:[/red] {escape(str(exc))}")
            raise typer.Exit(code=1) from exc

    if cascade:
        planners = _make_cascade(cascade)
        summary = evaluator.evaluate_cascade(
            tasks,
            planners,
            allow_feedback=not no_feedback,
            delay_seconds=delay_seconds,
            perception=perception_obj,
        )
    else:
        planner_obj = _make_planner(planner)
        summary = evaluator.evaluate(
            tasks,
            planner_obj,
            allow_feedback=not no_feedback,
            delay_seconds=delay_seconds,
            perception=perception_obj,
        )
    json_path, csv_path = evaluator.save_results(summary)

    table = Table(
        title=f"Evaluation summary — planner: {summary.planner_name} "
        f"(perception: {perception_obj.name})"
    )
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

    if baseline_summary is not None:
        comparison = compare_summaries(baseline_summary, summary)
        delta_sign = "+" if comparison.success_rate_delta >= 0 else ""
        console.print("\n[bold]Comparison vs. baseline:[/bold]")
        console.print(
            f"  success_rate: {baseline_summary.success_rate:.2%} -> "
            f"{summary.success_rate:.2%} ({delta_sign}{comparison.success_rate_delta:.2%})"
        )
        console.print(
            f"  average_steps: {baseline_summary.average_steps:.2f} -> "
            f"{summary.average_steps:.2f} ({comparison.average_steps_delta:+.2f})"
        )
        console.print("\n[bold]README log row (paste into the Model improvement log table):[/bold]")
        console.print(escape(comparison.as_readme_row(label or "(describe the change)")))


if __name__ == "__main__":
    app()
