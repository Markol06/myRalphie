"""Tests for the Claude scaffold (interview skill, CLAUDE.md, gitignore)."""
from pathlib import Path

from ralph.scaffold import (
    ensure_claude_scaffold,
    RALPH_CLAUDE_SECTION_START,
    RALPH_CLAUDE_SECTION_END,
)


def test_scaffold_creates_interview_skill(tmp_path: Path):
    ensure_claude_scaffold(tmp_path)

    skill = tmp_path / ".claude" / "skills" / "ralph-interview" / "SKILL.md"
    assert skill.exists()
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\nname: ralph-interview\n")
    assert "description:" in text
    assert "# Ralph Interview Flow" in text
    assert ".ralph/prd.json" in text


def test_scaffold_claude_md_is_short_pointer(tmp_path: Path):
    ensure_claude_scaffold(tmp_path)
    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "/ralph-interview" in text
    assert "ralph run" in text
    # the interview instructions themselves must NOT live in CLAUDE.md
    assert "AskUserQuestionTool" not in text


def test_scaffold_replaces_old_long_section(tmp_path: Path):
    old = (
        "# My project\n\nMy own instructions.\n\n"
        f"{RALPH_CLAUDE_SECTION_START}\n## Ralph Workflow\n"
        "old long interview instructions with AskUserQuestionTool\n"
        f"{RALPH_CLAUDE_SECTION_END}\n\nTrailing content.\n"
    )
    (tmp_path / "CLAUDE.md").write_text(old, encoding="utf-8")

    ensure_claude_scaffold(tmp_path)

    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "My own instructions." in text
    assert "Trailing content." in text
    assert "old long interview instructions" not in text
    assert "/ralph-interview" in text


def test_scaffold_removes_legacy_interview_prompt(tmp_path: Path):
    prompts = tmp_path / ".ralph" / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "interview.md").write_text("legacy", encoding="utf-8")
    (prompts / "bootstrap_message.txt").write_text(
        "read .ralph/prompts/interview.md and interview me", encoding="utf-8"
    )

    ensure_claude_scaffold(tmp_path)

    assert not (prompts / "interview.md").exists()
    bootstrap = (prompts / "bootstrap_message.txt").read_text(encoding="utf-8")
    assert "/ralph-interview" in bootstrap  # stale bootstrap rewritten


def test_scaffold_idempotent(tmp_path: Path):
    first = ensure_claude_scaffold(tmp_path)
    second = ensure_claude_scaffold(tmp_path)
    assert first
    assert second == []
