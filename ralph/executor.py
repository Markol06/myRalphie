"""Executor — spawns a fresh claude process for each iteration."""
from __future__ import annotations

import json
import subprocess
import threading
import time
import sys
import shutil
from pathlib import Path
from dataclasses import dataclass

from rich.console import Console

console = Console()


@dataclass
class ExecutionResult:
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    result_text: str = ""          # final assistant message from the result event
    cost_usd: float = 0.0
    input_tokens: int = 0          # includes cache creation/read tokens
    output_tokens: int = 0
    num_turns: int = 0

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


def find_claude() -> str:
    if sys.platform.startswith("win"):
        return shutil.which("claude.cmd") or shutil.which("claude") or "claude.cmd"
    return shutil.which("claude") or "claude"


def run_claude_text(
    prompt: str, cwd: Path, model: str = "", timeout: int = 300
) -> str | None:
    """One-shot `claude -p` text call for prompts that need no tools.

    Returns the output text, or None on failure/timeout.
    """
    cmd = [find_claude(), "-p", "--output-format", "text"]
    if model:
        cmd.extend(["--model", model])
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _handle_stream_line(line: str, transcript: list[str], final: dict) -> None:
    """Parse one stream-json line: echo progress, collect the result event."""
    line = line.strip()
    if not line:
        return
    try:
        evt = json.loads(line)
    except json.JSONDecodeError:
        transcript.append(line)
        return

    etype = evt.get("type")
    if etype == "assistant":
        for block in evt.get("message", {}).get("content", []):
            if block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    transcript.append(text)
                    console.print(text, style="dim", markup=False, highlight=False)
            elif block.get("type") == "tool_use":
                name = block.get("name", "?")
                transcript.append(f"[tool_use] {name}")
                console.print(f"  ⚙ {name}", style="dim cyan", markup=False)
    elif etype == "result":
        final.update(evt)


def run_claude(
    prompt: str,
    project_root: Path,
    timeout_seconds: int = 900,
    dry_run: bool = False,
    model: str = "",
    max_turns: int = 0,
) -> ExecutionResult:
    """Spawn a fresh non-interactive Claude Code instance (stream-json output).

    Runs with full tool access (bypassPermissions) — an allowlist would be
    ignored in this mode anyway, so we don't pretend to have one.
    """

    if dry_run:
        print(f"\n  [DRY RUN] Would run claude with prompt:\n{prompt[:300]}...\n")
        return ExecutionResult(returncode=0, stdout="[dry-run]", stderr="", duration_seconds=0)

    claude_bin = find_claude()

    cmd = [
        claude_bin,
        "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", "bypassPermissions",
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        "--add-dir", str(project_root),
    ]
    if model:
        cmd.extend(["--model", model])
    if max_turns > 0:
        cmd.extend(["--max-turns", str(max_turns)])

    start = time.time()
    transcript: list[str] = []
    final: dict = {}
    stderr_chunks: list[str] = []

    proc = subprocess.Popen(
        cmd,
        cwd=project_root,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    def _consume_stdout() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            _handle_stream_line(line, transcript, final)

    def _consume_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            stderr_chunks.append(line)

    out_thread = threading.Thread(target=_consume_stdout, daemon=True)
    err_thread = threading.Thread(target=_consume_stderr, daemon=True)
    out_thread.start()
    err_thread.start()

    try:
        assert proc.stdin is not None
        proc.stdin.write(prompt)
        proc.stdin.close()
    except OSError:
        pass  # process died before reading the prompt; returncode will tell

    timed_out = False
    try:
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()

    out_thread.join(timeout=10)
    err_thread.join(timeout=10)
    duration = time.time() - start

    usage = final.get("usage") or {}
    total_input = (
        int(usage.get("input_tokens") or 0)
        + int(usage.get("cache_creation_input_tokens") or 0)
        + int(usage.get("cache_read_input_tokens") or 0)
    )

    return ExecutionResult(
        returncode=-1 if timed_out else proc.returncode,
        stdout="\n".join(transcript),
        stderr="".join(stderr_chunks),
        duration_seconds=duration,
        timed_out=timed_out,
        result_text=str(final.get("result") or ""),
        cost_usd=float(final.get("total_cost_usd") or 0.0),
        input_tokens=total_input,
        output_tokens=int(usage.get("output_tokens") or 0),
        num_turns=int(final.get("num_turns") or 0),
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


def git_dirty_files(project_root: Path) -> list[str]:
    """Uncommitted changes (staged, unstaged and untracked), porcelain lines."""
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root, capture_output=True, text=True, timeout=10,
    )
    return [line for line in r.stdout.splitlines() if line.strip()]


def git_current_branch(project_root: Path) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=project_root, capture_output=True, text=True, timeout=10,
    )
    return r.stdout.strip()


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
