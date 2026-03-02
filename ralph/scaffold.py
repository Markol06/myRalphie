"""Scaffolding for Claude Code project-local Ralph instructions."""
from __future__ import annotations

from pathlib import Path


RALPH_CLAUDE_SECTION_START = "<!-- RALPH_CLAUDE_START -->"
RALPH_CLAUDE_SECTION_END = "<!-- RALPH_CLAUDE_END -->"


def ensure_claude_scaffold(project_root: Path) -> list[Path]:
    """Create project-local Ralph prompt files and inject CLAUDE.md guidance."""
    created: list[Path] = []

    _remove_legacy_command_files(project_root)

    ralph_dir = project_root / ".ralph"
    prompts_dir = ralph_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    interview_prompt = prompts_dir / "interview.md"
    if not interview_prompt.exists():
        interview_prompt.write_text(_interview_prompt_text(), encoding="utf-8")
        created.append(interview_prompt)

    next_story_prompt = prompts_dir / "next_story.md"
    if not next_story_prompt.exists():
        next_story_prompt.write_text(_next_story_prompt_text(), encoding="utf-8")
        created.append(next_story_prompt)

    bootstrap_prompt = prompts_dir / "bootstrap_message.txt"
    if not bootstrap_prompt.exists():
        bootstrap_prompt.write_text(_bootstrap_message_text(), encoding="utf-8")
        created.append(bootstrap_prompt)

    claude_md = project_root / "CLAUDE.md"
    if _upsert_claude_md(claude_md):
        created.append(claude_md)

    return created


def _remove_legacy_command_files(project_root: Path) -> None:
    commands_dir = project_root / ".claude" / "commands"
    for name in ("ralph-interview.md", "ralph-next-story.md"):
        path = commands_dir / name
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
## Ralph Workflow

When the user describes a new feature, project, refactor, or automation idea and `.ralph/prd.json` does not exist yet, switch into a Ralph requirements interview:

- Read `.ralph/prompts/interview.md` before asking questions.
- Use `AskUserQuestionTool`.
- Ask exactly one question at a time.
- After you have enough detail, write:
  - `.ralph/prd.json`
  - `.ralph/progress.txt`
  - `.ralph/AGENT.md`
  - `.ralphrc`
- Keep stories small enough to complete in one implementation session per story.

When `.ralph/prd.json` already exists and the user asks you to continue Ralph or implement the next story:

- Read `.ralph/prompts/next_story.md`.
- Read `.ralph/prd.json`, `.ralph/progress.txt`, and `.ralph/AGENT.md`.
- Implement only the first story where `passes` is `false` and `failed` is `false`.

If the user explicitly asks for the autonomous external Ralph loop, the shell commands are still available via the installed `ralph` CLI.
{RALPH_CLAUDE_SECTION_END}"""


def _bootstrap_message_text() -> str:
    return (
        "I want to start a Ralph-style requirements interview for this project. "
        "Please read .ralph/prompts/interview.md, inspect the repository, then use "
        "AskUserQuestionTool to ask me one question at a time. After the interview, "
        "write .ralph/prd.json, .ralph/progress.txt, .ralph/AGENT.md, and .ralphrc."
    )


def _interview_prompt_text() -> str:
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
  "branch_per_task": true,
  "base_branch": "main"
}
```

When done:
- summarize the final plan briefly
- stop asking questions
"""


def _next_story_prompt_text() -> str:
    return """# Ralph Next Story Flow

Continue Ralph manually inside the current Claude Code session.

Workflow:
1. Read `.ralph/prd.json`, `.ralph/progress.txt`, and `.ralph/AGENT.md`.
2. Pick the first story where `passes` is false and `failed` is false.
3. Implement only that story.
4. Run the commands from `.ralph/AGENT.md` or `.ralphrc`:
   - test
   - lint, if configured
   - build, if configured and relevant
5. If checks pass:
   - commit with `git commit -m "ralph: <story_id> - <story_title>"`
   - update `.ralph/prd.json`:
     - `passes: true`
     - `commit`: current commit hash
     - `branch`: current branch name
   - append a short learning entry to `.ralph/progress.txt`
   - update `.ralph/AGENT.md` if you discovered durable conventions
6. If checks fail:
   - do not mark the story as passed
   - increment retries in `.ralph/prd.json`
   - append a failure note to `.ralph/progress.txt`
   - explain the blocker clearly

Rules:
- keep diffs small
- do not modify unrelated stories
- do not skip checks unless the repository truly has no runnable checks and that is already documented
- if the next story is too large, stop and say it should be split first
"""
