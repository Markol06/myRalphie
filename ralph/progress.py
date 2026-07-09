"""Append-only progress.txt — the memory between Claude instances."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


HEADER = """# Ralph Progress Log
# This file is read by every new Claude Code instance.
# Each entry is a learning from a previous iteration.
# DO NOT DELETE — this is the memory of the loop.
"""


def init(path: Path) -> None:
    if not path.exists():
        path.write_text(HEADER, encoding="utf-8")


def append(path: Path, story_id: str, story_title: str, content: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## [{ts}] Story {story_id}: {story_title}\n{content.strip()}\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


def read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def split_entries(text: str) -> tuple[str, list[str]]:
    """Split progress.txt into (header, list of '## ' entries)."""
    lines = text.splitlines()
    header_lines: list[str] = []
    body_start = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            body_start = i
            break
        header_lines.append(line)
    if body_start is None:
        return text, []

    entries: list[str] = []
    current: list[str] = []
    for line in lines[body_start:]:
        if line.startswith("## ") and current:
            entries.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        entries.append("\n".join(current).strip())
    return "\n".join(header_lines).strip(), entries


COMPACT_PROMPT = """Compress the following Ralph progress log entries into a concise digest.

Rules:
- Keep every durable learning, convention, gotcha and architectural note.
- Drop per-story ceremony (timestamps, test output dumps, repeated boilerplate).
- Group related learnings together.
- Output plain markdown bullet points only, no preamble and no code fences.

Entries to compress:

{entries}
"""


def compact(
    path: Path, keep: int, summarize, project_root: Path
) -> tuple[bool, str]:
    """Compress all but the last `keep` entries into a digest.

    `summarize` is a callable(prompt) -> str | None (kept injectable for tests).
    Returns (changed, message). Writes a .bak backup before rewriting.
    """
    text = read(path)
    header, entries = split_entries(text)
    if len(entries) <= keep:
        return False, f"only {len(entries)} entries — nothing to compact (keep={keep})"

    old_entries, recent = entries[:-keep], entries[-keep:]
    digest = summarize(COMPACT_PROMPT.format(entries="\n\n".join(old_entries)))
    if not digest:
        return False, "claude summarization call failed — progress.txt left untouched"

    path.with_suffix(".txt.bak").write_text(text, encoding="utf-8")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_text = (
        f"{header}\n"
        f"\n## [{ts}] COMPACTED digest of {len(old_entries)} earlier entries\n"
        f"{digest.strip()}\n\n"
        + "\n\n".join(recent) + "\n"
    )
    path.write_text(new_text, encoding="utf-8")
    return True, (
        f"compacted {len(old_entries)} entries into a digest, "
        f"kept {len(recent)} recent entries (backup: {path.name}.bak)"
    )


def read_recent(path: Path, max_chars: int = 6000) -> str:
    """Return the last max_chars of progress.txt to keep context small."""
    text = read(path)
    if len(text) <= max_chars:
        return text
    # always include the header + last N chars
    lines = text.splitlines()
    header_lines = []
    for line in lines:
        if line.startswith("## "):
            break
        header_lines.append(line)
    header = "\n".join(header_lines)
    tail = text[-max_chars:]
    return f"{header}\n\n[... truncated, showing last entries ...]\n{tail}"
