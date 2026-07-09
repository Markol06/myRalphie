"""Scaffolding for Claude Code project-local Ralph instructions."""
from __future__ import annotations

from pathlib import Path


RALPH_CLAUDE_SECTION_START = "<!-- RALPH_CLAUDE_START -->"
RALPH_CLAUDE_SECTION_END = "<!-- RALPH_CLAUDE_END -->"


def ensure_claude_scaffold(project_root: Path) -> list[Path]:
    """Create the ralph-interview skill and inject CLAUDE.md guidance."""
    created: list[Path] = []

    _remove_legacy_command_files(project_root)
    _remove_legacy_prompt_files(project_root)

    ralph_dir = project_root / ".ralph"
    prompts_dir = ralph_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    bootstrap_prompt = prompts_dir / "bootstrap_message.txt"
    if not bootstrap_prompt.exists() or "prompts/interview.md" in bootstrap_prompt.read_text(encoding="utf-8"):
        bootstrap_prompt.write_text(_bootstrap_message_text(), encoding="utf-8")
        created.append(bootstrap_prompt)

    # The interview lives in a Claude Code skill: its body loads into context
    # only when invoked, and it's callable explicitly as /ralph-interview
    skill_file = project_root / ".claude" / "skills" / "ralph-interview" / "SKILL.md"
    if not skill_file.exists():
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(_interview_skill_text(), encoding="utf-8")
        created.append(skill_file)

    claude_md = project_root / "CLAUDE.md"
    if _upsert_claude_md(claude_md):
        created.append(claude_md)

    gitignore = project_root / ".gitignore"
    if _ensure_gitignore(gitignore):
        created.append(gitignore)

    return created


def _ensure_gitignore(path: Path) -> bool:
    """Keep Ralph local state (incl. .ralphrc with tokens) out of the repo."""
    entries = [".ralph/", ".ralphrc"]
    if path.exists():
        text = path.read_text(encoding="utf-8")
        present = {line.strip().rstrip("/") for line in text.splitlines()}
        missing = [e for e in entries if e.rstrip("/") not in present]
        if not missing:
            return False
        sep = "" if text.endswith("\n") or not text else "\n"
        path.write_text(
            text + sep + "\n# Ralph local state\n" + "\n".join(missing) + "\n",
            encoding="utf-8",
        )
        return True
    path.write_text("# Ralph local state\n" + "\n".join(entries) + "\n", encoding="utf-8")
    return True


def _remove_legacy_command_files(project_root: Path) -> None:
    commands_dir = project_root / ".claude" / "commands"
    for name in ("ralph-interview.md", "ralph-next-story.md"):
        path = commands_dir / name
        if path.exists():
            path.unlink()


def _remove_legacy_prompt_files(project_root: Path) -> None:
    prompts_dir = project_root / ".ralph" / "prompts"
    # interview.md moved into the ralph-interview skill
    for name in ("next_story.md", "interview.md"):
        path = prompts_dir / name
        if path.exists():
            path.unlink()


def _upsert_claude_md(path: Path) -> bool:
    section = _claude_md_section()
    if path.exists():
        text = path.read_text(encoding="utf-8")
        start = text.find(RALPH_CLAUDE_SECTION_START)
        end = text.find(RALPH_CLAUDE_SECTION_END)
        if start != -1 and end != -1 and end > start:
            new_text = text[:start] + section + text[end + len(RALPH_CLAUDE_SECTION_END):]
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                return True
            return False

        if section.strip() in text:
            return False

        sep = "\n\n" if text and not text.endswith("\n\n") else ""
        path.write_text(text + sep + section, encoding="utf-8")
        return True

    path.write_text("# Claude Code Project Instructions\n\n" + section, encoding="utf-8")
    return True


def _claude_md_section() -> str:
    return f"""{RALPH_CLAUDE_SECTION_START}
## Ralph

Ralph (autonomous coding loop) is set up in this repo. To plan a new feature, invoke the `/ralph-interview` skill — it interviews the user one question at a time and creates `.ralph/prd.json` plus the other Ralph files. After the interview, the user starts the loop from the shell with `ralph run`.
{RALPH_CLAUDE_SECTION_END}"""


def _bootstrap_message_text() -> str:
    return (
        "Start a Ralph requirements interview for this project: "
        "invoke the /ralph-interview skill."
    )


def _interview_skill_text() -> str:
    return f"""---
name: ralph-interview
description: Conduct a Ralph requirements interview — break a feature into small stories and create .ralph/prd.json, .ralph/progress.txt, .ralph/AGENT.md and .ralphrc for the autonomous loop. Use when the user wants to plan a feature for Ralph, asks for a Ralph interview, or describes work to prepare for `ralph run`.
---

{_interview_body_text()}"""


def _interview_body_text() -> str:
    return """# Ralph Interview Flow

You are conducting a Ralph requirements interview for this repository.

Goals:
- understand what needs to be built
- break the work into small implementation stories
- capture durable project conventions for future coding sessions

How to work:
1. Inspect the repository before asking questions.
2. Use AskUserQuestionTool.
3. Ask exactly one question at a time.
4. Prefer specific technical questions over broad ones.
5. Keep going until you have enough detail to write the Ralph files.

You must cover:
- project goal and user value
- stack, architecture, tests, lint/build commands
- scope boundaries and files that must not be touched
- external services, credentials, performance/security constraints
- definition of done
- a story breakdown small enough for one implementation session per story

Required outputs:

## .ralph/prd.json
```json
{
  "project_name": "project-name",
  "description": "Short summary of the requested work",
  "branch_name": "ralph/feature-name",
  "stories": [
    {
      "id": "S001",
      "title": "Short title",
      "description": "Concrete implementation scope",
      "acceptance_criteria": [
        "Tests pass",
        "Specific behavior works",
        "No regression in related behavior"
      ],
      "passes": false,
      "failed": false,
      "retries": 0,
      "branch": "",
      "commit": "",
      "notes": ""
    }
  ]
}
```

## .ralph/progress.txt
```text
# Ralph Progress Log

## [INTERVIEW] Project Context
- Goal: ...
- Stack: ...
- Test command: ...
- Lint command: ...
- Build command: ...
- Files to never touch: ...
- Key conventions: ...
- Important notes: ...
```

## .ralph/AGENT.md
```md
# Agent Instructions

## Build & Test Commands
- Test: `<test_command>` or `none`
- Lint: `<lint_command>` or `none`
- Build: `<build_command>` or `none`

## Project Conventions
- ...

## Files to Never Touch
- ...

## Key Architecture Notes
- ...
```

## .ralphrc
```json
{
  "test_command": "...",
  "lint_command": "...",
  "build_command": "...",
  "base_branch": "main"
}
```

When done:
- summarize the final plan briefly
- stop asking questions
- tell the user to start the autonomous loop from the shell with `ralph run`
"""
