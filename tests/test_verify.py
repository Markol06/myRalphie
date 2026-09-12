"""Tests for the independent PASS verification (deterministic checks + LLM verifier)."""
from pathlib import Path

from ralph import loop
from ralph.config import RalphConfig
from ralph.executor import ExecutionResult
from ralph.prd import Story


def _story() -> Story:
    return Story(
        id="S002", title="Rate limiter", description="Limit login attempts",
        acceptance_criteria=["5 attempts per minute", "429 after the limit"],
    )


def _ok_command(*_args, **_kwargs) -> ExecutionResult:
    return ExecutionResult(returncode=0, stdout="ok", stderr="", duration_seconds=0.1)


def _patch_deterministic(monkeypatch, commit_after: str = "def456") -> None:
    monkeypatch.setattr(loop, "git_current_commit", lambda _root: commit_after)
    monkeypatch.setattr(loop, "run_command", _ok_command)
    monkeypatch.setattr(loop, "git_diff_since", lambda _root, _base: "+ limiter code")


def test_parse_verdict_reads_pass_fail_and_garbage():
    assert loop._parse_verdict("VERDICT: PASS\nREASON: all criteria implemented") == (
        True, "all criteria implemented",
    )
    passed, reason = loop._parse_verdict("verdict: fail\nREASON: no 429 response")
    assert passed is False and reason == "no 429 response"
    assert loop._parse_verdict("I think it is fine")[0] is None
    assert loop._parse_verdict(None)[0] is None


def test_verify_prompt_carries_story_and_diff():
    prompt = loop._verify_prompt(_story(), "+ limiter code")
    assert 'Story S002: Rate limiter' in prompt
    assert "- 5 attempts per minute" in prompt and "- 429 after the limit" in prompt
    assert "+ limiter code" in prompt and "VERDICT: PASS or FAIL" in prompt


def test_verifier_veto_turns_pass_into_unverified(monkeypatch, tmp_path: Path):
    _patch_deterministic(monkeypatch)
    calls: dict = {}

    def fake_claude_text(prompt, cwd, model="", timeout=0):
        calls.update(model=model, timeout=timeout, prompt=prompt)
        return "VERDICT: FAIL\nREASON: 429 path is missing"

    monkeypatch.setattr(loop, "run_claude_text", fake_claude_text)
    config = RalphConfig(test_command="pytest -q", verify_model="claude-haiku-4-5", verify_timeout=42)

    ok, reason = loop._verify_pass(tmp_path, config, "abc123", _story())

    assert ok is False
    assert "claude-haiku-4-5" in reason and "429 path is missing" in reason
    assert calls["model"] == "claude-haiku-4-5" and calls["timeout"] == 42
    assert "429 after the limit" in calls["prompt"]


def test_verifier_pass_keeps_the_story_done(monkeypatch, tmp_path: Path):
    _patch_deterministic(monkeypatch)
    monkeypatch.setattr(
        loop, "run_claude_text", lambda *a, **k: "VERDICT: PASS\nREASON: all criteria implemented"
    )
    assert loop._verify_pass(tmp_path, RalphConfig(), "abc123", _story()) == (True, "")


def test_unreadable_verifier_answer_does_not_block(monkeypatch, tmp_path: Path):
    _patch_deterministic(monkeypatch)
    monkeypatch.setattr(loop, "run_claude_text", lambda *a, **k: None)
    assert loop._verify_pass(tmp_path, RalphConfig(), "abc123", _story()) == (True, "")


def test_empty_verify_model_skips_the_llm(monkeypatch, tmp_path: Path):
    _patch_deterministic(monkeypatch)

    def boom(*_a, **_k):
        raise AssertionError("verifier must not be called")

    monkeypatch.setattr(loop, "run_claude_text", boom)
    config = RalphConfig(verify_model="")
    assert loop._verify_pass(tmp_path, config, "abc123", _story()) == (True, "")


def test_deterministic_failure_short_circuits_before_the_llm(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(loop, "git_current_commit", lambda _root: "abc123")

    def boom(*_a, **_k):
        raise AssertionError("verifier must not be called")

    monkeypatch.setattr(loop, "run_claude_text", boom)
    ok, reason = loop._verify_pass(tmp_path, RalphConfig(), "abc123", _story())
    assert ok is False and "no new commit" in reason
