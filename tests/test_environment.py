"""Tests for the Toy Robot Environment."""

from __future__ import annotations

import pytest

from geniac_cap.environment.toy_robot import ToyRobotEnv
from geniac_cap.exceptions import (
    LocationNotFoundError,
    ObjectNotFoundError,
    PreconditionFailedError,
)


def make_env() -> ToyRobotEnv:
    return ToyRobotEnv(
        locations={"table", "shelf"},
        objects={"cup"},
        object_locations={"cup": "table"},
        robot_location="table",
    )


def test_move_to_valid_location_updates_robot_location():
    env = make_env()
    env.move_to("shelf")
    assert env.state.robot_location == "shelf"


def test_move_to_unknown_location_raises():
    env = make_env()
    with pytest.raises(LocationNotFoundError):
        env.move_to("nowhere")


def test_pick_when_colocated_succeeds():
    env = make_env()
    env.pick("cup")
    assert env.state.held_object == "cup"


def test_pick_when_not_colocated_fails():
    env = make_env()
    env.move_to("shelf")
    with pytest.raises(PreconditionFailedError):
        env.pick("cup")


def test_pick_unknown_object_raises():
    env = make_env()
    with pytest.raises(ObjectNotFoundError):
        env.pick("ghost")


def test_pick_while_already_holding_fails():
    env = ToyRobotEnv(
        locations={"table"},
        objects={"cup", "plate"},
        object_locations={"cup": "table", "plate": "table"},
        robot_location="table",
    )
    env.pick("cup")
    with pytest.raises(PreconditionFailedError):
        env.pick("plate")


def test_place_without_holding_anything_fails():
    env = make_env()
    with pytest.raises(PreconditionFailedError):
        env.place("shelf")


def test_place_moves_object_to_target_location():
    env = make_env()
    env.pick("cup")
    env.move_to("shelf")
    env.place("shelf")
    assert env.state.object_locations["cup"] == "shelf"
    assert env.state.held_object is None


def test_reset_restores_initial_state():
    env = make_env()
    env.pick("cup")
    env.move_to("shelf")
    env.place("shelf")
    env.reset()
    assert env.state.robot_location == "table"
    assert env.state.object_locations["cup"] == "table"
    assert env.state.held_object is None


def test_check_goal_true_when_object_location_matches():
    env = make_env()
    env.pick("cup")
    env.move_to("shelf")
    env.place("shelf")
    assert env.check_goal({"object_locations": {"cup": "shelf"}}) is True


def test_check_goal_false_when_object_location_does_not_match():
    env = make_env()
    assert env.check_goal({"object_locations": {"cup": "shelf"}}) is False


def test_list_objects_and_locations():
    env = make_env()
    assert env.list_objects() == ["cup"]
    assert env.list_locations() == ["shelf", "table"]


def make_env_with_container() -> ToyRobotEnv:
    return ToyRobotEnv(
        locations={"office", "supply_box"},
        objects={"documents"},
        object_locations={"documents": "office"},
        robot_location="office",
        containers={"supply_box"},
    )


def test_place_into_closed_container_fails():
    env = make_env_with_container()
    env.pick("documents")
    env.move_to("supply_box")
    with pytest.raises(PreconditionFailedError):
        env.place("supply_box")


def test_place_into_open_container_succeeds():
    env = make_env_with_container()
    env.pick("documents")
    env.move_to("supply_box")
    env.open_container("supply_box")
    env.place("supply_box")
    assert env.state.object_locations["documents"] == "supply_box"


def test_pick_from_closed_container_fails():
    env = ToyRobotEnv(
        locations={"supply_box"},
        objects={"documents"},
        object_locations={"documents": "supply_box"},
        robot_location="supply_box",
        containers={"supply_box"},
    )
    with pytest.raises(PreconditionFailedError):
        env.pick("documents")
