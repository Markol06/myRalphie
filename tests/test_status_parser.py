"""Tests for RALPH_STATUS parsing in ralph.loop."""
from ralph.loop import _parse_ralph_status


SAMPLE_PASS = """
Implemented the feature and ran tests.

RALPH_STATUS:
  story_id: S001
  result: PASS
  exit_signal: true
  summary: "Added user login endpoint"
  learnings: "FastAPI TestClient needs the app fixture"
  test_output: "5 passed in 1.2s"
"""

SAMPLE_FAIL = """
RALPH_STATUS:
  story_id: S002
  result: FAIL
  exit_signal: false
  summary: "Tests failing on validation"
"""


def test_parse_pass():
    status = _parse_ralph_status(SAMPLE_PASS)
    assert status is not None
    assert status["story_id"] == "S001"
    assert status["result"] == "PASS"
    assert status["exit_signal"] is True
    assert "login endpoint" in status["summary"]
    assert "TestClient" in status["learnings"]
    assert "5 passed" in status["test_output"]


def test_parse_fail_without_optional_fields():
    status = _parse_ralph_status(SAMPLE_FAIL)
    assert status is not None
    assert status["result"] == "FAIL"
    assert status["exit_signal"] is False
    assert status["learnings"] == ""
    assert status["test_output"] == ""


def test_no_status_returns_none():
    assert _parse_ralph_status("I did some work but forgot the status.") is None
    assert _parse_ralph_status("") is None


def test_takes_last_status_block():
    quoted_then_real = (
        "I will end with a block like this:\n"
        "RALPH_STATUS:\n"
        "  story_id: EXAMPLE\n"
        "  result: PASS\n"
        "  exit_signal: true\n"
        "  summary: just an example\n"
        "\n...actual work happens...\n"
        + SAMPLE_FAIL
    )
    status = _parse_ralph_status(quoted_then_real)
    assert status is not None
    assert status["story_id"] == "S002"
    assert status["result"] == "FAIL"


def test_case_insensitive_result():
    text = SAMPLE_PASS.replace("result: PASS", "result: pass")
    status = _parse_ralph_status(text)
    assert status is not None
    assert status["result"] == "PASS"
