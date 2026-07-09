"""Project config loader — reads .ralphrc from project root."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

# Secrets are preferably taken from the environment, not .ralphrc
_ENV_OVERRIDES = {
    "telegram_token": "RALPH_TELEGRAM_TOKEN",
    "telegram_chat_id": "RALPH_TELEGRAM_CHAT_ID",
    "discord_webhook": "RALPH_DISCORD_WEBHOOK",
}


@dataclass
class RalphConfig:
    # Loop behaviour
    chunk_size: int = 5           # iterations per session
    max_retries: int = 3          # retries per failing story
    claude_timeout: int = 900     # seconds per claude instance (15 min)

    # Claude instance
    model: str = ""               # e.g. "claude-sonnet-5"; empty = account default
    retry_model: str = ""         # stronger model for retries (e.g. "claude-opus-4-8"); empty = same as model
    max_turns: int = 0            # cap agent turns per iteration; 0 = unlimited
    use_goal: bool = True         # drive each iteration with /goal (independent per-turn evaluator)

    # Budget — total cost.log spend at which the run pauses; 0 = unlimited
    max_cost_usd: float = 0.0

    # Circuit breaker
    cb_no_progress_threshold: int = 3   # stop after N iters with no git change
    cb_same_error_threshold: int = 5    # stop after N iters with same error

    # Commands (auto-detected by interview, override here)
    test_command: str = ""
    lint_command: str = ""
    build_command: str = ""

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
    def load(cls, project_root: Path, apply_env: bool = True) -> "RalphConfig":
        """Load .ralphrc; set apply_env=False when the result will be saved
        back, so env-provided secrets never get written to the file."""
        rc_file = project_root / ".ralphrc"
        if rc_file.exists():
            with open(rc_file) as f:
                data = json.load(f)
            # merge: only known fields
            known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            config = cls(**known)
        else:
            config = cls()

        if apply_env:
            # env vars win over .ralphrc for secrets
            for attr, env_name in _ENV_OVERRIDES.items():
                value = os.environ.get(env_name)
                if value:
                    setattr(config, attr, value)
        return config

    def save(self, project_root: Path) -> None:
        rc_file = project_root / ".ralphrc"
        with open(rc_file, "w") as f:
            json.dump(asdict(self), f, indent=2)
        print(f"  Saved {rc_file}")
