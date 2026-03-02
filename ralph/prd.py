"""PRD task management — prd.json is the source of truth for task state."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Story:
    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    passes: bool = False
    failed: bool = False
    retries: int = 0
    branch: str = ""
    commit: str = ""
    notes: str = ""                   # learnings written after each attempt

    @classmethod
    def from_dict(cls, d: dict) -> "Story":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PRD:
    project_name: str
    description: str
    branch_name: str
    stories: list[Story] = field(default_factory=list)

    # ──────────────────────────────────────────────
    # persistence
    # ──────────────────────────────────────────────
    @classmethod
    def load(cls, path: Path) -> "PRD":
        with open(path) as f:
            d = json.load(f)
        stories = [Story.from_dict(s) for s in d.pop("stories", [])]
        return cls(**d, stories=stories)

    def save(self, path: Path) -> None:
        d = asdict(self)
        with open(path, "w") as f:
            json.dump(d, f, indent=2)

    # ──────────────────────────────────────────────
    # queries
    # ──────────────────────────────────────────────
    def next_story(self) -> Optional[Story]:
        """First story that is not done and not permanently failed."""
        for s in self.stories:
            if not s.passes and not s.failed:
                return s
        return None

    def all_done(self) -> bool:
        return all(s.passes or s.failed for s in self.stories)

    def stats(self) -> dict:
        total = len(self.stories)
        done = sum(1 for s in self.stories if s.passes)
        failed = sum(1 for s in self.stories if s.failed)
        pending = total - done - failed
        return {"total": total, "done": done, "failed": failed, "pending": pending}

    # ──────────────────────────────────────────────
    # mutations
    # ──────────────────────────────────────────────
    def mark_done(self, story_id: str, commit: str, branch: str) -> None:
        for s in self.stories:
            if s.id == story_id:
                s.passes = True
                s.commit = commit
                s.branch = branch
                return

    def mark_failed(self, story_id: str, notes: str = "") -> None:
        for s in self.stories:
            if s.id == story_id:
                s.failed = True
                s.notes = notes
                return

    def increment_retry(self, story_id: str) -> int:
        for s in self.stories:
            if s.id == story_id:
                s.retries += 1
                return s.retries
        return 0

    def get(self, story_id: str) -> Optional[Story]:
        for s in self.stories:
            if s.id == story_id:
                return s
        return None
