"""Project config loader — reads .ralphrc from project root."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class RalphConfig:
    # Loop behaviour
    chunk_size: int = 5           # iterations per session
    max_retries: int = 3          # retries per failing story
    claude_timeout: int = 900     # seconds per claude instance (15 min)

    # Circuit breaker
    cb_no_progress_threshold: int = 3   # stop after N iters with no git change
    cb_same_error_threshold: int = 5    # stop after N iters with same error

    # Commands (auto-detected by interview, override here)
    test_command: str = ""
    lint_command: str = ""
    build_command: str = ""

    # Allowed claude tools
    allowed_tools: list[str] = field(default_factory=lambda: [
        "Write", "Read", "Edit", "MultiEdit",
        "Bash(git *)", "Bash(pytest *)", "Bash(python *)",
        "Bash(npm *)", "Bash(yarn *)", "Bash(pnpm *)",
        "Bash(make *)", "Bash(cargo *)",
    ])

    # Notifications
    discord_webhook: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""

    # Branch strategy — trunk-based: the whole run happens on prd.branch_name,
    # created from base_branch if it doesn't exist yet
    base_branch: str = "main"

    # Dry run
    dry_run: bool = False

    @classmethod
    def load(cls, project_root: Path) -> "RalphConfig":
        rc_file = project_root / ".ralphrc"
        if not rc_file.exists():
            return cls()
        with open(rc_file) as f:
            data = json.load(f)
        # merge: only known fields
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self, project_root: Path) -> None:
        rc_file = project_root / ".ralphrc"
        with open(rc_file, "w") as f:
            json.dump(asdict(self), f, indent=2)
        print(f"  Saved {rc_file}")
