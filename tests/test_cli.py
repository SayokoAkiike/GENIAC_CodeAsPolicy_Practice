"""Smoke tests for the CLI, including a regression test for Rich markup
mangling error messages that contain square brackets (e.g. "pip install
-e '.[vision]'" was previously silently truncated to "pip install -e '.'").
"""

from __future__ import annotations

from typer.testing import CliRunner

from geniac_cap.cli import app

runner = CliRunner()


def test_list_tasks_runs_without_error():
    result = runner.invoke(app, ["list-tasks"])
    assert result.exit_code == 0
    assert "task_001" in result.stdout


def test_show_task_unknown_id_reports_error_cleanly():
    result = runner.invoke(app, ["show-task", "--task-id", "does_not_exist"])
    assert result.exit_code != 0
    assert "Error" in result.stdout


def test_error_messages_with_brackets_are_not_mangled_by_rich_markup(monkeypatch):
    """Regression test: rich.console.Console.print() treats "[text]" as markup
    unless escaped, which previously ate "[vision]" out of error messages.
    """

    from geniac_cap import cli as cli_module
    from geniac_cap.exceptions import GeniacCapError

    def _boom(task_id):
        raise GeniacCapError("Install it with: pip install -e '.[vision]'")

    monkeypatch.setattr(cli_module, "get_task_by_id", _boom)

    result = runner.invoke(app, ["show-task", "--task-id", "task_001"])
    assert "[vision]" in result.stdout
