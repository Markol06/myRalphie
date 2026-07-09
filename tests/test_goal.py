"""Tests for the /goal condition builder."""
from ralph.config import RalphConfig
from ralph.loop import _build_goal_condition, _GOAL_MAX_CHARS
from ralph.prd import Story


def _story(**kwargs) -> Story:
    defaults = dict(
        id="S001", title="Login endpoint", description="d",
        acceptance_criteria=["POST /login returns a JWT", "invalid creds return 401"],
    )
    defaults.update(kwargs)
    return Story(**defaults)


def test_condition_includes_criteria_tests_and_commit():
    config = RalphConfig(test_command="pytest -q")
    condition = _build_goal_condition(_story(), config)
    assert 'Story S001 "Login endpoint"' in condition
    assert "POST /login returns a JWT" in condition
    assert "`pytest -q` was run and exited 0" in condition
    assert "git status" in condition
    assert "stop after 30 turns" in condition


def test_condition_without_test_command():
    condition = _build_goal_condition(_story(), RalphConfig())
    assert "exited 0" not in condition
    assert "git status" in condition


def test_condition_capped_at_goal_limit():
    story = _story(acceptance_criteria=[f"criterion {i} " + "x" * 200 for i in range(40)])
    condition = _build_goal_condition(story, RalphConfig())
    assert len(condition) <= _GOAL_MAX_CHARS


def test_condition_with_empty_criteria():
    condition = _build_goal_condition(_story(acceptance_criteria=[]), RalphConfig())
    assert "story description is implemented" in condition
