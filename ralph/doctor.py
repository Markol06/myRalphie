"""`ralph doctor` — validate the setup before burning tokens mid-run."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .config import RalphConfig
from .prd import PRD
from .executor import find_claude, run_command

console = Console()

OK = "ok"
WARN = "warn"
FAIL = "fail"

_ICONS = {OK: "✅", WARN: "⚠️", FAIL: "❌"}


def _check_claude() -> tuple[str, str]:
    claude_bin = find_claude()
    if not shutil.which(claude_bin) and not Path(claude_bin).exists():
        return FAIL, "claude binary not found in PATH — install Claude Code"
    try:
        r = subprocess.run(
            [claude_bin, "--version"],
            capture_output=True, text=True, timeout=30,
        )
        version = r.stdout.strip() or r.stderr.strip()
        return OK, f"{claude_bin} ({version})"
    except Exception as e:
        return FAIL, f"claude --version failed: {e}"


def _check_git(project_root: Path) -> tuple[str, str]:
    r = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_root, capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        return FAIL, "not a git repository — run git init"
    return OK, "git repository detected"


def _check_prd(ralph_dir: Path) -> tuple[str, str]:
    prd_path = ralph_dir / "prd.json"
    if not prd_path.exists():
        return WARN, "no prd.json yet — run the interview first (claude)"
    try:
        prd = PRD.load(prd_path)
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        return FAIL, f"prd.json is invalid: {e}"
    if not prd.stories:
        return FAIL, "prd.json has no stories"
    if not prd.branch_name:
        return WARN, "prd.json has no branch_name — the run will stay on the current branch"
    stats = prd.stats()
    return OK, f"{stats['total']} stories ({stats['done']} done, {stats['pending']} pending)"


def _check_config(project_root: Path) -> tuple[str, str, RalphConfig | None]:
    try:
        config = RalphConfig.load(project_root)
    except json.JSONDecodeError as e:
        return FAIL, f".ralphrc is not valid JSON: {e}", None
    return OK, ".ralphrc loaded", config


def _check_commands(config: RalphConfig) -> tuple[str, str]:
    if not config.test_command:
        return WARN, "no test_command — PASS verification will only check for a new commit"
    configured = [
        label for label, cmd in
        (("test", config.test_command), ("lint", config.lint_command), ("build", config.build_command))
        if cmd
    ]
    return OK, f"configured: {', '.join(configured)}"


def _check_notifications(config: RalphConfig) -> tuple[str, str]:
    if config.telegram_token and config.telegram_chat_id:
        return OK, "telegram configured"
    if config.discord_webhook:
        return OK, "discord configured"
    return WARN, "no notifications — set RALPH_TELEGRAM_TOKEN / RALPH_TELEGRAM_CHAT_ID"


def _check_gh() -> tuple[str, str]:
    if shutil.which("gh"):
        return OK, "gh CLI available (ralph pr will work)"
    return WARN, "gh CLI not found — ralph pr won't work"


def run_doctor(project_root: Path, run_tests: bool = False) -> bool:
    """Run all checks. Returns True when there are no FAIL results."""
    ralph_dir = project_root / ".ralph"
    results: list[tuple[str, str, str]] = []

    results.append(("claude", *_check_claude()))
    results.append(("git", *_check_git(project_root)))

    if ralph_dir.exists():
        results.append((".ralph", OK, "initialized"))
        results.append(("prd.json", *_check_prd(ralph_dir)))
    else:
        results.append((".ralph", FAIL, "not initialized — run ralph init"))

    status, message, config = _check_config(project_root)
    results.append((".ralphrc", status, message))
    if config:
        results.append(("commands", *_check_commands(config)))
        results.append(("notifications", *_check_notifications(config)))
        if run_tests and config.test_command:
            r = run_command(config.test_command, project_root, timeout=600)
            if r.timed_out:
                results.append(("test run", FAIL, "test_command timed out"))
            elif r.returncode != 0:
                tail = (r.stdout + r.stderr).strip()[-200:]
                results.append(("test run", FAIL, f"test_command failed: {tail}"))
            else:
                results.append(("test run", OK, "test_command passes"))

    results.append(("gh", *_check_gh()))

    table = Table(title="🩺 Ralph Doctor", show_header=False, padding=(0, 1))
    for name, status, message in results:
        table.add_row(_ICONS[status], f"[bold]{name}[/bold]", message)
    console.print(table)

    failed = [r for r in results if r[1] == FAIL]
    if failed:
        console.print(f"\n[red]{len(failed)} check(s) failed.[/red]")
        return False
    console.print("\n[green]Setup looks good.[/green]")
    return True
