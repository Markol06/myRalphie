"""Executor — spawns a fresh claude process for each iteration."""
from __future__ import annotations

import subprocess
import time
import sys
import shutil
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def combined_output(self) -> str:
        return self.stdout + "\n" + self.stderr


def _to_text(value: str | bytes | None) -> str:
    """TimeoutExpired carries str in text mode, bytes otherwise."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_claude(
    prompt: str,
    project_root: Path,
    allowed_tools: list[str],
    timeout_seconds: int = 900,
    dry_run: bool = False,
) -> ExecutionResult:
    """Spawn a fresh non-interactive Claude Code instance."""

    if dry_run:
        print(f"\n  [DRY RUN] Would run claude with prompt:\n{prompt[:300]}...\n")
        return ExecutionResult(returncode=0, stdout="[dry-run]", stderr="", duration_seconds=0)

    tools_str = ",".join(allowed_tools)

    if sys.platform.startswith("win"):
        claude_bin = shutil.which("claude.cmd") or shutil.which("claude") or "claude.cmd"
    else:
        claude_bin = shutil.which("claude") or "claude"

    cmd = [
        claude_bin,
        "-p",
        "--output-format", "text",
        "--permission-mode", "bypassPermissions",
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        "--add-dir", str(project_root),
    ]
    if tools_str:
        cmd.extend(["--allowed-tools", tools_str])

    start = time.time()
    timed_out = False

    try:
        proc = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            input=prompt,
            timeout=timeout_seconds,
        )
        duration = time.time() - start
        return ExecutionResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired as e:
        timed_out = True
        duration = time.time() - start
        return ExecutionResult(
            returncode=-1,
            stdout=_to_text(e.stdout),
            stderr=_to_text(e.stderr),
            duration_seconds=duration,
            timed_out=True,
        )


def run_command(cmd: str, project_root: Path, timeout: int = 120) -> ExecutionResult:
    """Run a shell command (tests, lint, etc.) in the project root."""
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return ExecutionResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_seconds=time.time() - start,
        )
    except subprocess.TimeoutExpired as e:
        return ExecutionResult(
            returncode=-1,
            stdout=_to_text(e.stdout),
            stderr=_to_text(e.stderr),
            duration_seconds=time.time() - start,
            timed_out=True,
        )


def git_current_commit(project_root: Path) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_root, capture_output=True, text=True, timeout=10,
    )
    return r.stdout.strip()


def git_commit_message(project_root: Path, message: str) -> bool:
    subprocess.run(["git", "add", "-A"], cwd=project_root, timeout=30)
    r = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=project_root, capture_output=True, text=True, timeout=30,
    )
    return r.returncode == 0


def git_create_branch(project_root: Path, branch_name: str, base: str = "main") -> bool:
    r = subprocess.run(
        ["git", "checkout", "-b", branch_name, base],
        cwd=project_root, capture_output=True, text=True, timeout=30,
    )
    return r.returncode == 0


def git_checkout(project_root: Path, branch: str) -> bool:
    r = subprocess.run(
        ["git", "checkout", branch],
        cwd=project_root, capture_output=True, text=True, timeout=30,
    )
    return r.returncode == 0
