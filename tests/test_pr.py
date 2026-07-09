"""Tests for PR body generation."""
from pathlib import Path

from ralph.pr import build_pr_body, _story_summaries
from ralph.prd import PRD, Story


PROGRESS = """# Ralph Progress Log

## [2026-07-09 10:00] Story S001: Login endpoint
✅ DONE
Summary: Added POST /login with JWT
Learnings: none

## [2026-07-09 11:00] Story S002: Logout endpoint
❌ FAILED attempt 1
Error: tests failing

## [2026-07-09 12:00] Story S002: Logout endpoint
✅ DONE
Summary: Added POST /logout, fixed token revocation
Learnings: none
"""


def test_story_summaries_takes_latest_done():
    summaries = _story_summaries(PROGRESS)
    assert summaries["S001"] == "Added POST /login with JWT"
    assert summaries["S002"] == "Added POST /logout, fixed token revocation"


def test_build_pr_body(tmp_path: Path):
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    (ralph_dir / "progress.txt").write_text(PROGRESS, encoding="utf-8")

    prd = PRD(
        project_name="auth-feature",
        description="Add auth endpoints",
        branch_name="ralph/auth",
        stories=[
            Story(id="S001", title="Login endpoint", description="", acceptance_criteria=[], passes=True),
            Story(id="S002", title="Logout endpoint", description="", acceptance_criteria=[], passes=True),
            Story(id="S003", title="Refresh tokens", description="", acceptance_criteria=[], failed=True),
            Story(id="S004", title="Rate limiting", description="", acceptance_criteria=[]),
        ],
    )

    body = build_pr_body(prd, ralph_dir)
    assert "Add auth endpoints" in body
    assert "✅ `S001` Login endpoint — Added POST /login with JWT" in body
    assert "❌ `S003` Refresh tokens (failed/skipped)" in body
    assert "⏳ `S004` Rate limiting (pending)" in body
    assert "2/4 stories completed" in body
