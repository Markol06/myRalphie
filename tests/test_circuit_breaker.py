"""Tests for the circuit breaker thresholds."""
from pathlib import Path

import pytest

from ralph.circuit_breaker import CircuitBreaker


@pytest.fixture
def cb(tmp_path: Path, monkeypatch) -> CircuitBreaker:
    breaker = CircuitBreaker(
        tmp_path / "circuit_state.json",
        tmp_path,
        no_progress_threshold=3,
        same_error_threshold=5,
    )
    monkeypatch.setattr(breaker, "_current_commit", lambda: "abc123")
    return breaker


def test_opens_after_no_progress(cb: CircuitBreaker):
    cb.state.last_commit = "abc123"  # same commit → no progress
    for _ in range(3):
        cb.record_failure("some error")
    should_stop, reason = cb.should_open()
    assert should_stop
    assert "No git progress" in reason


def test_opens_after_same_error(cb: CircuitBreaker, monkeypatch):
    # commits keep changing → no-progress counter stays quiet
    commits = iter(f"commit{i}" for i in range(10))
    monkeypatch.setattr(cb, "_current_commit", lambda: next(commits))
    for _ in range(5):
        cb.record_failure("ModuleNotFoundError: No module named 'foo'")
    should_stop, reason = cb.should_open()
    assert should_stop
    assert "Same error repeated" in reason


def test_same_error_is_whitespace_and_case_insensitive(cb: CircuitBreaker, monkeypatch):
    commits = iter(f"commit{i}" for i in range(10))
    monkeypatch.setattr(cb, "_current_commit", lambda: next(commits))
    cb.record_failure("Tests   Failing on VALIDATION")
    cb.record_failure("tests failing on validation")
    assert cb.state.same_error_count == 2


def test_success_resets_counters(cb: CircuitBreaker):
    cb.state.last_commit = "abc123"
    cb.record_failure("err")
    cb.record_failure("err")
    cb.record_success()
    should_stop, _ = cb.should_open()
    assert not should_stop
    assert cb.state.no_progress_count == 0
    assert cb.state.same_error_count == 0


def test_state_persists_across_instances(cb: CircuitBreaker, tmp_path: Path):
    cb.state.last_commit = "abc123"
    cb.record_failure("err")
    reloaded = CircuitBreaker(tmp_path / "circuit_state.json", tmp_path)
    assert reloaded.state.no_progress_count == 1
