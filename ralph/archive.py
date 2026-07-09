"""`ralph archive` — move a finished run's state into .ralph/history/."""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from .prd import PRD

# Run state that belongs to one feature run. Durable files (AGENT.md,
# prompts/) stay in place for the next run.
RUN_STATE_FILES = [
    "prd.json",
    "progress.txt",
    "cost.log",
    "session.json",
    "circuit_state.json",
]
RUN_STATE_DIRS = ["logs"]


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "run"


def archive_run(project_root: Path, force: bool = False) -> tuple[bool, str]:
    """Move the current run state to .ralph/history/<date>-<name>/.

    Refuses when stories are still pending unless force is set.
    Returns (archived, message).
    """
    ralph_dir = project_root / ".ralph"
    prd_path = ralph_dir / "prd.json"
    if not prd_path.exists():
        return False, "no prd.json — nothing to archive"

    prd = PRD.load(prd_path)
    if not prd.all_done() and not force:
        stats = prd.stats()
        return False, (
            f"{stats['pending']} stories still pending — finish the run or "
            "use --force to archive anyway"
        )

    name = f"{datetime.now().strftime('%Y-%m-%d')}-{_slug(prd.project_name)}"
    dest = ralph_dir / "history" / name
    counter = 2
    while dest.exists():
        dest = ralph_dir / "history" / f"{name}-{counter}"
        counter += 1
    dest.mkdir(parents=True)

    moved = []
    for filename in RUN_STATE_FILES:
        src = ralph_dir / filename
        if src.exists():
            shutil.move(str(src), str(dest / filename))
            moved.append(filename)
    for dirname in RUN_STATE_DIRS:
        src = ralph_dir / dirname
        if src.exists() and any(src.iterdir()):
            shutil.move(str(src), str(dest / dirname))
            moved.append(f"{dirname}/")
        (ralph_dir / dirname).mkdir(exist_ok=True)

    return True, (
        f"archived {', '.join(moved)} to {dest.relative_to(project_root)} — "
        "start the next interview with `claude`"
    )
