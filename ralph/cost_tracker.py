"""Cost tracker — logs structured cost data per iteration (CSV)."""
from __future__ import annotations

import csv
from pathlib import Path
from datetime import datetime


def log(
    log_path: Path,
    chunk: int,
    iteration: int,
    story_id: str,
    story_title: str,
    result: str,
    cost_data: dict,
) -> None:
    is_new = not log_path.exists()
    with open(log_path, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp", "chunk", "iteration", "story_id", "story_title",
                "result", "cost_usd", "input_tokens", "output_tokens",
            ],
        )
        if is_new:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().isoformat(),
            "chunk": chunk,
            "iteration": iteration,
            "story_id": story_id,
            "story_title": story_title,
            "result": result,
            **cost_data,
        })


def total_cost(log_path: Path) -> float:
    if not log_path.exists():
        return 0.0
    total = 0.0
    with open(log_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                total += float(row.get("cost_usd", 0))
            except ValueError:
                pass
    return total


def total_tokens(log_path: Path) -> tuple[int, int]:
    if not log_path.exists():
        return 0, 0
    total_in = 0
    total_out = 0
    with open(log_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                total_in += int(row.get("input_tokens", 0) or 0)
            except ValueError:
                pass
            try:
                total_out += int(row.get("output_tokens", 0) or 0)
            except ValueError:
                pass
    return total_in, total_out
