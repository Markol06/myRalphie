"""Circuit breaker — prevents burning limits on stuck loops."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, asdict


@dataclass
class CircuitState:
    no_progress_count: int = 0
    last_error: str = ""
    same_error_count: int = 0
    last_commit: str = ""

    @classmethod
    def load(cls, path: Path) -> "CircuitState":
        if not path.exists():
            return cls()
        with open(path) as f:
            d = json.load(f)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def save(self, path: Path) -> None:
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)


class CircuitBreaker:
    def __init__(
        self,
        state_path: Path,
        project_root: Path,
        no_progress_threshold: int = 3,
        same_error_threshold: int = 5,
    ):
        self.state_path = state_path
        self.project_root = project_root
        self.no_progress_threshold = no_progress_threshold
        self.same_error_threshold = same_error_threshold
        self.state = CircuitState.load(state_path)

    def _current_commit(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.project_root,
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def record_success(self) -> None:
        self.state.no_progress_count = 0
        self.state.same_error_count = 0
        self.state.last_error = ""
        self.state.last_commit = self._current_commit()
        self.state.save(self.state_path)

    def record_failure(self, error: str) -> None:
        current = self._current_commit()

        # No progress = no new commit
        if current == self.state.last_commit:
            self.state.no_progress_count += 1
        else:
            self.state.no_progress_count = 0
            self.state.last_commit = current

        # Same error repeated
        if error and error == self.state.last_error:
            self.state.same_error_count += 1
        else:
            self.state.same_error_count = 1
            self.state.last_error = error

        self.state.save(self.state_path)

    def should_open(self) -> tuple[bool, str]:
        """Returns (should_stop, reason)."""
        if self.state.no_progress_count >= self.no_progress_threshold:
            return True, (
                f"No git progress for {self.state.no_progress_count} iterations. "
                f"Possible infinite loop."
            )
        if self.state.same_error_count >= self.same_error_threshold:
            return True, (
                f"Same error repeated {self.state.same_error_count} times: "
                f"{self.state.last_error[:120]}"
            )
        return False, ""

    def reset(self) -> None:
        self.state = CircuitState()
        self.state.save(self.state_path)
