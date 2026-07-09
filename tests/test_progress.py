"""Tests for progress.txt splitting and compaction."""
from pathlib import Path

from ralph import progress as prog


SAMPLE = """# Ralph Progress Log
# This file is read by every new Claude Code instance.

## [2026-07-01 10:00] Story S001: First
✅ DONE
Summary: did the first thing

## [2026-07-02 10:00] Story S002: Second
❌ FAILED attempt 1
Error: broke

## [2026-07-03 10:00] Story S002: Second
✅ DONE
Summary: fixed it

## [2026-07-04 10:00] Story S003: Third
✅ DONE
Summary: third thing
"""


def test_split_entries():
    header, entries = prog.split_entries(SAMPLE)
    assert header.startswith("# Ralph Progress Log")
    assert len(entries) == 4
    assert entries[0].startswith("## [2026-07-01")
    assert entries[-1].startswith("## [2026-07-04")


def test_split_entries_no_entries():
    header, entries = prog.split_entries("# Just a header\n")
    assert entries == []


def test_compact_keeps_recent_and_digests_old(tmp_path: Path):
    path = tmp_path / "progress.txt"
    path.write_text(SAMPLE, encoding="utf-8")

    changed, message = prog.compact(
        path, keep=2, summarize=lambda prompt: "- digest of old learnings",
        project_root=tmp_path,
    )
    assert changed
    text = path.read_text(encoding="utf-8")
    assert "COMPACTED digest of 2 earlier entries" in text
    assert "- digest of old learnings" in text
    assert "Story S003: Third" in text          # recent kept verbatim
    assert "Story S001: First" not in text      # old entry gone
    assert (tmp_path / "progress.txt.bak").exists()


def test_compact_noop_when_few_entries(tmp_path: Path):
    path = tmp_path / "progress.txt"
    path.write_text(SAMPLE, encoding="utf-8")
    changed, message = prog.compact(
        path, keep=10, summarize=lambda prompt: "unused", project_root=tmp_path,
    )
    assert not changed
    assert "nothing to compact" in message


def test_compact_aborts_when_summarize_fails(tmp_path: Path):
    path = tmp_path / "progress.txt"
    path.write_text(SAMPLE, encoding="utf-8")
    changed, message = prog.compact(
        path, keep=1, summarize=lambda prompt: None, project_root=tmp_path,
    )
    assert not changed
    assert path.read_text(encoding="utf-8") == SAMPLE  # untouched
