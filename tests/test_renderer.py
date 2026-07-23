"""Tests for the scene renderer (Phase 4: VLM perception)."""

from __future__ import annotations

import pytest

from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.perception.renderer import render_scene
from geniac_cap.tasks.loader import get_task_by_id, load_tasks

pytest.importorskip("PIL", reason="Pillow (the 'vision' extra) is required for these tests")


def test_render_scene_returns_valid_png_bytes():
    env = ToyRobotEnv(
        locations={"table", "shelf"},
        objects={"cup"},
        object_locations={"cup": "table"},
        robot_location="table",
    )
    png_bytes = render_scene(env)
    assert isinstance(png_bytes, bytes)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")  # PNG magic number


def test_render_scene_works_for_every_sample_task():
    for task in load_tasks():
        env = ToyRobotEnv.from_task_state(task.initial_state)
        png_bytes = render_scene(env)
        assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n"), f"Task {task.task_id} failed to render"


def test_render_scene_reflects_container_state():
    task = get_task_by_id("task_013")
    env = ToyRobotEnv.from_task_state(task.initial_state)

    from io import BytesIO

    from PIL import Image

    closed_bytes = render_scene(env)
    env.pick("documents")
    env.move_to("supply_box")
    env.open_container("supply_box")
    open_bytes = render_scene(env)

    # Rendering the same environment in a different state should produce a
    # different image (not asserting on pixel content, just that state changes
    # actually affect the render).
    assert closed_bytes != open_bytes
    for data in (closed_bytes, open_bytes):
        img = Image.open(BytesIO(data))
        assert img.size[0] > 0 and img.size[1] > 0
