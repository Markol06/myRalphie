"""Iteration logger — saves full Claude output per story to .ralph/logs/."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def _log_path(logs_dir: Path, story_id: str, chunk: int, iteration: int) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return logs_dir / f"{ts}_chunk{chunk}_iter{iteration}_{story_id}.log"


def save(
    logs_dir: Path,
    story_id: str,
    story_title: str,
    chunk: int,
    iteration: int,
    prompt: str,
    output: str,
    result: str,
    duration: float,
    cost_usd: float,
) -> Path:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = _log_path(logs_dir, story_id, chunk, iteration)

    meta = {
        "story_id": story_id,
        "story_title": story_title,
        "chunk": chunk,
        "iteration": iteration,
        "result": result,
        "duration_seconds": round(duration, 1),
        "cost_usd": cost_usd,
        "timestamp": datetime.now().isoformat(),
    }

    content = (
        f"{'='*72}\n"
        f"RALPH ITERATION LOG\n"
        f"{json.dumps(meta, indent=2)}\n"
        f"{'='*72}\n\n"
        f"── PROMPT ({'─'*60})\n\n"
        f"{prompt}\n\n"
        f"── OUTPUT ({'─'*60})\n\n"
        f"{output}\n"
    )
    path.write_text(content, encoding="utf-8")
    return path


def list_logs(logs_dir: Path) -> list[dict]:
    """Return log entries sorted newest-first."""
    if not logs_dir.exists():
        return []

    entries = []
    for f in sorted(logs_dir.glob("*.log"), reverse=True):
        # filename: 20260301_143022_chunk1_iter3_S001.log
        parts = f.stem.split("_")
        entries.append({
            "path": f,
            "filename": f.name,
            "story_id": parts[-1] if len(parts) >= 5 else "?",
            "chunk": parts[2].replace("chunk", "") if len(parts) >= 3 else "?",
            "iteration": parts[3].replace("iter", "") if len(parts) >= 4 else "?",
            "timestamp": f"{parts[0][:4]}-{parts[0][4:6]}-{parts[0][6:]} {parts[1][:2]}:{parts[1][2:4]}",
            "size_kb": round(f.stat().st_size / 1024, 1),
        })
    return entries


def find_latest(logs_dir: Path, story_id: str | None = None) -> Path | None:
    logs = list_logs(logs_dir)
    if story_id:
        logs = [l for l in logs if l["story_id"].upper() == story_id.upper()]
    return logs[0]["path"] if logs else None
