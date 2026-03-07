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
