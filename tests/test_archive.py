"""Tests for run archiving."""
import json
from pathlib import Path

from ralph.archive import archive_run


def _make_run(tmp_path: Path, all_done: bool = True) -> Path:
    # exist_ok: archive_run recreates logs/, and repeated calls reuse the tree
    ralph_dir = tmp_path / ".ralph"
    (ralph_dir / "logs").mkdir(parents=True, exist_ok=True)
    (ralph_dir / "prompts").mkdir(exist_ok=True)
    (ralph_dir / "prompts" / "interview.md").write_text("keep me")
    (ralph_dir / "AGENT.md").write_text("conventions")
    (ralph_dir / "progress.txt").write_text("# log")
    (ralph_dir / "cost.log").write_text("timestamp,cost_usd\n")
    (ralph_dir / "logs" / "iter1.log").write_text("output")
    (ralph_dir / "prd.json").write_text(json.dumps({
        "project_name": "My Feature!",
        "description": "d",
        "branch_name": "ralph/x",
        "stories": [{
            "id": "S001", "title": "t", "description": "d",
            "acceptance_criteria": [], "passes": all_done, "failed": False,
        }],
    }))
    return ralph_dir


def test_archive_moves_run_state(tmp_path: Path):
    ralph_dir = _make_run(tmp_path)
    archived, message = archive_run(tmp_path)
    assert archived

    history = list((ralph_dir / "history").iterdir())
    assert len(history) == 1
    dest = history[0]
    assert dest.name.endswith("-my-feature")
    assert (dest / "prd.json").exists()
    assert (dest / "progress.txt").exists()
    assert (dest / "logs" / "iter1.log").exists()

    # run state gone, durable files stay, logs dir recreated empty
    assert not (ralph_dir / "prd.json").exists()
    assert (ralph_dir / "AGENT.md").exists()
    assert (ralph_dir / "prompts" / "interview.md").exists()
    assert (ralph_dir / "logs").exists()


def test_archive_refuses_pending_without_force(tmp_path: Path):
    _make_run(tmp_path, all_done=False)
    archived, message = archive_run(tmp_path)
    assert not archived
    assert "pending" in message


def test_archive_force_with_pending(tmp_path: Path):
    _make_run(tmp_path, all_done=False)
    archived, _ = archive_run(tmp_path, force=True)
    assert archived


def test_archive_nothing_to_archive(tmp_path: Path):
    (tmp_path / ".ralph").mkdir()
    archived, message = archive_run(tmp_path)
    assert not archived
    assert "no prd.json" in message


def test_archive_unique_destination(tmp_path: Path):
    _make_run(tmp_path)
    assert archive_run(tmp_path)[0]
    _make_run(tmp_path)  # same project name again, same day
    assert archive_run(tmp_path)[0]
    history = sorted(p.name for p in (tmp_path / ".ralph" / "history").iterdir())
    assert len(history) == 2
    assert history[1].endswith("-2")
