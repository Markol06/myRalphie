"""Session state — tracks chunk progress so you can pause and resume."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime


@dataclass
class Session:
    chunk_number: int = 1             # which 5-iteration block we're on
    iteration_in_chunk: int = 0       # 0-4 within current chunk
    total_iterations: int = 0         # across all chunks
    last_story_id: str = ""
    started_at: str = ""
    last_updated: str = ""
    status: str = "idle"              # idle | running | paused | complete | failed
    pause_reason: str = ""            # why we paused (test_failure, chunk_done, etc.)
    total_cost_usd: float = 0.0

    @classmethod
    def load(cls, path: Path) -> "Session":
        if not path.exists():
            s = cls()
            s.started_at = datetime.now().isoformat()
            return s
        with open(path) as f:
            d = json.load(f)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def save(self, path: Path) -> None:
        self.last_updated = datetime.now().isoformat()
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)

    def next_iteration(self) -> None:
        self.iteration_in_chunk += 1
        self.total_iterations += 1

    def is_chunk_done(self, chunk_size: int) -> bool:
        return self.iteration_in_chunk >= chunk_size

    def start_new_chunk(self) -> None:
        self.chunk_number += 1
        self.iteration_in_chunk = 0
