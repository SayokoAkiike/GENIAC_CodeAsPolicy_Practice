# Contributing

This is a small personal/portfolio practice project, but contributions,
issues, and suggestions are welcome.

## Setup

```bash
git clone https://github.com/USERNAME/geniac-cap-practice.git
cd geniac-cap-practice
pip install -e ".[dev]"
```

## Before opening a PR

Please make sure the following all pass locally:

```bash
ruff check .
python -m pytest
```

## Adding a new task

Tasks live in `src/geniac_cap/tasks/sample_tasks.yaml`. Add a new list item
with `task_id`, `instruction`, `initial_state`, `goal_state`, `difficulty`,
`category`, `expected_objects`, and `expected_locations`. No Python code
changes are required to add a task.

## Adding a new Planner

Implement `geniac_cap.planners.base.BasePlanner` (a single `plan()` method)
and register it in `_PLANNERS` in `src/geniac_cap/cli.py` if you want it
available from the CLI.

## Code style

- Python 3.11, type hints where practical.
- Keep modules small and single-purpose; avoid very large files.
- Never add code paths that `exec()`/`eval()` untrusted or model-generated
  text — see `docs/architecture.md` for why.
- Prefer clear names over clever ones; this project is also a learning
  reference.

## Reporting issues

Please open a GitHub issue with steps to reproduce, the command you ran, and
the full error output.
