"""Ralph CLI — `ralph interview`, `ralph run`, `ralph status`, etc."""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .config import RalphConfig
from .prd import PRD
from .session import Session
from . import cost_tracker

console = Console()


def _resolve_project(project_arg: str | None) -> Path:
    """Returns absolute project root — either CWD or --project arg."""
    if project_arg:
        p = Path(project_arg).expanduser().resolve()
        if not p.exists():
            console.print(f"[red]Project path does not exist: {p}[/red]")
            sys.exit(1)
        return p
    return Path.cwd()


def _require_ralph_dir(project_root: Path) -> Path:
    ralph_dir = project_root / ".ralph"
    if not ralph_dir.exists():
        console.print(
            "[red]No .ralph/ directory found.[/red]\n"
            "Run [bold]ralph init[/bold] first."
        )
        sys.exit(1)
    return ralph_dir


# ──────────────────────────────────────────────────────────────────────────────
@click.group()
@click.version_option()
def main():
    """Ralph — autonomous Claude Code loop with chunk-based execution."""


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option("--project", "-p", default=None, help="Path to project root (default: cwd)")
@click.option("--dry-run", is_flag=True, help="Simulate without running claude")
def interview(project, dry_run):
    """Run the interview phase to generate prd.json from a conversation."""
    from .interview import run_interview

    project_root = _resolve_project(project)
    console.print(f"[dim]Project root: {project_root}[/dim]")

    success = run_interview(project_root, dry_run=dry_run)
    sys.exit(0 if success else 1)


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option("--project", "-p", default=None, help="Path to project root (default: cwd)")
@click.option("--resume", "-r", is_flag=True, help="Resume from last paused state")
@click.option("--chunk-size", default=None, type=int, help="Override chunk size (default from config)")
@click.option("--until-done", is_flag=True, help="Keep rolling into new chunks until all stories are done or a safeguard stops the run")
@click.option("--dry-run", is_flag=True, help="Simulate without running claude")
def run(project, resume, chunk_size, until_done, dry_run):
    """Run a chunk of autonomous coding iterations (default: 5)."""
    from .loop import run_loop

    project_root = _resolve_project(project)
    ralph_dir = _require_ralph_dir(project_root)

    prd_path = ralph_dir / "prd.json"
    if not prd_path.exists():
        console.print("[red]No .ralph/prd.json found. Run [bold]ralph interview[/bold] first.[/red]")
        sys.exit(1)

    config = RalphConfig.load(project_root)
    if chunk_size:
        config.chunk_size = chunk_size
    if dry_run:
        config.dry_run = True

    console.print(Panel(
        f"[bold]Starting Ralph Loop[/bold]\n\n"
        f"Project: [cyan]{project_root.name}[/cyan]\n"
        f"Chunk size: [cyan]{config.chunk_size}[/cyan] iterations"
        + (" · [cyan]until done[/cyan]" if until_done else "") + "\n"
        f"Mode: {'[yellow]DRY RUN[/yellow]' if dry_run else '[green]LIVE[/green]'}",
        border_style="blue",
    ))

    run_loop(project_root, config, resume=resume, until_done=until_done)


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option("--project", "-p", default=None)
def resume(project):
    """Resume from where the last chunk left off (shortcut for run --resume)."""
    from .loop import run_loop

    project_root = _resolve_project(project)
    _require_ralph_dir(project_root)
    config = RalphConfig.load(project_root)
    run_loop(project_root, config, resume=True)


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option("--project", "-p", default=None)
def status(project):
    """Show current project status."""
    project_root = _resolve_project(project)
    ralph_dir = _require_ralph_dir(project_root)

    prd_path = ralph_dir / "prd.json"
    session_path = ralph_dir / "session.json"
    cost_log_path = ralph_dir / "cost.log"

    if not prd_path.exists():
        console.print("[red]No prd.json found.[/red]")
        sys.exit(1)

    prd = PRD.load(prd_path)
    session = Session.load(session_path)
    total_cost = cost_tracker.total_cost(cost_log_path)
    total_in, total_out = cost_tracker.total_tokens(cost_log_path)
    stats = prd.stats()

    # Header
    console.print(Panel(
        f"[bold]{prd.project_name}[/bold]\n{prd.description}",
        border_style="blue",
    ))

    # Session info
    session_table = Table(show_header=False, box=None)
    session_table.add_row("Status", f"[bold]{session.status}[/bold]")
    if session.pause_reason:
        session_table.add_row("Paused reason", session.pause_reason)
    session_table.add_row("Chunk", str(session.chunk_number))
    session_table.add_row("Total iterations", str(session.total_iterations))
    session_table.add_row("Tokens", f"in {total_in} / out {total_out}")
    session_table.add_row("Total cost", f"${total_cost:.4f}")
    console.print(session_table)
    console.print()

    # Stories table
    story_table = Table(title="Stories", show_lines=True)
    story_table.add_column("ID", style="bold", width=8)
    story_table.add_column("Title")
    story_table.add_column("Status", width=10)
    story_table.add_column("Retries", width=8)
    story_table.add_column("Branch", style="dim")

    for story in prd.stories:
        if story.passes:
            status_str = "[green]✅ done[/green]"
        elif story.failed:
            status_str = "[red]❌ failed[/red]"
        else:
            status_str = "[yellow]⏳ pending[/yellow]"
        story_table.add_row(
            story.id, story.title, status_str,
            str(story.retries), story.branch or "-",
        )

    console.print(story_table)
    console.print(f"\n[dim]✅ {stats['done']}  ❌ {stats['failed']}  ⏳ {stats['pending']}  total: {stats['total']}[/dim]")


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.argument("story_id")
@click.option("--project", "-p", default=None)
def skip(story_id, project):
    """Mark a story as failed (skip it) so the loop moves on."""
    project_root = _resolve_project(project)
    ralph_dir = _require_ralph_dir(project_root)
    prd_path = ralph_dir / "prd.json"
    prd = PRD.load(prd_path)

    story = prd.get(story_id)
    if not story:
        console.print(f"[red]Story {story_id} not found.[/red]")
        sys.exit(1)

    prd.mark_failed(story_id, notes="Manually skipped")
    prd.save(prd_path)

    # Clear pause reason so run --resume works
    session = Session.load(ralph_dir / "session.json")
    session.status = "paused"
    session.pause_reason = ""
    session.save(ralph_dir / "session.json")

    console.print(f"[yellow]Story {story_id} marked as skipped.[/yellow]")
    console.print("Run [bold]ralph run --resume[/bold] to continue.")


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.argument("story_id")
@click.option("--project", "-p", default=None)
def retry(story_id, project):
    """Reset a failed story so Ralph tries it again."""
    project_root = _resolve_project(project)
    ralph_dir = _require_ralph_dir(project_root)
    prd_path = ralph_dir / "prd.json"
    prd = PRD.load(prd_path)

    story = prd.get(story_id)
    if not story:
        console.print(f"[red]Story {story_id} not found.[/red]")
        sys.exit(1)

    story.failed = False
    story.passes = False
    story.retries = 0
    story.notes = ""
    prd.save(prd_path)

    # Reset circuit breaker too
    from .circuit_breaker import CircuitState
    cb_path = ralph_dir / "circuit_state.json"
    state = CircuitState()
    import json
    cb_path.write_text(json.dumps(state.__dict__, indent=2))

    # Unblock session
    session = Session.load(ralph_dir / "session.json")
    session.status = "paused"
    session.pause_reason = ""
    session.save(ralph_dir / "session.json")

    console.print(f"[green]Story {story_id} reset for retry.[/green]")
    console.print("Run [bold]ralph run --resume[/bold] to continue.")


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option("--project", "-p", default=None)
def cost(project):
    """Show cost breakdown by iteration."""
    project_root = _resolve_project(project)
    ralph_dir = _require_ralph_dir(project_root)
    log_path = ralph_dir / "cost.log"

    if not log_path.exists():
        console.print("[dim]No cost data yet.[/dim]")
        return

    import csv
    rows = []
    with open(log_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    table = Table(title="Cost per Iteration")
    table.add_column("Time", style="dim")
    table.add_column("Chunk/Iter")
    table.add_column("Story")
    table.add_column("Result")
    table.add_column("Cost", justify="right")
    table.add_column("Tokens in", justify="right")
    table.add_column("Tokens out", justify="right")

    for r in rows:
        res = r.get("result", "")
        res_styled = f"[green]{res}[/green]" if res == "pass" else f"[red]{res}[/red]"
        table.add_row(
            r.get("timestamp", "")[:16],
            f"{r.get('chunk')}/{r.get('iteration')}",
            f"{r.get('story_id')} {r.get('story_title', '')[:25]}",
            res_styled,
            f"${float(r.get('cost_usd', 0)):.4f}",
            r.get("input_tokens", "0"),
            r.get("output_tokens", "0"),
        )

    console.print(table)
    total = cost_tracker.total_cost(log_path)
    console.print(f"\n[bold]Total: ${total:.4f}[/bold]")


# ──────────────────────────────────────────────────────────────────────────────
@main.command(name="log")
@click.argument("story_id", required=False, default=None)
@click.option("--project", "-p", default=None)
@click.option("--list", "list_all", is_flag=True, help="List all available logs")
@click.option("--output-only", is_flag=True, help="Show only Claude's output (skip prompt)")
def log_cmd(story_id, project, list_all, output_only):
    """Show full iteration log.

    \b
    ralph log           -- show last log
    ralph log S001      -- show last log for story S001
    ralph log --list    -- list all logs
    """
    from . import logger as iteration_logger

    project_root = _resolve_project(project)
    ralph_dir = _require_ralph_dir(project_root)
    logs_dir = ralph_dir / "logs"

    if list_all:
        entries = iteration_logger.list_logs(logs_dir)
        if not entries:
            console.print("[dim]No logs yet.[/dim]")
            return
        table = Table(title="Iteration Logs", show_lines=False)
        table.add_column("#", width=4, style="dim")
        table.add_column("Timestamp", width=17)
        table.add_column("Story", width=8)
        table.add_column("Chunk/Iter", width=10)
        table.add_column("Size", width=8, justify="right")
        table.add_column("File", style="dim")
        for i, e in enumerate(entries, 1):
            table.add_row(
                str(i), e["timestamp"], e["story_id"],
                f"{e['chunk']}/{e['iteration']}", f"{e['size_kb']} KB", e["filename"],
            )
        console.print(table)
        return

    log_path = iteration_logger.find_latest(logs_dir, story_id)
    if not log_path:
        msg = f"No logs found for story {story_id}." if story_id else "No logs found."
        console.print(f"[red]{msg}[/red]  Run [bold]ralph log --list[/bold] to see all logs.")
        return

    content = log_path.read_text(encoding="utf-8")

    if output_only:
        if "── OUTPUT " in content:
            content = "\n".join(content.split("── OUTPUT ")[1].splitlines()[1:]).strip()
        console.print(content)
        return

    console.print(Panel(f"[bold]{log_path.name}[/bold]", border_style="blue"))
    for line in content.splitlines():
        if line.startswith("── PROMPT"):
            console.print(f"\n[bold cyan]{line}[/bold cyan]")
        elif line.startswith("── OUTPUT"):
            console.print(f"\n[bold yellow]{line}[/bold yellow]")
        elif line.startswith("=" * 20):
            console.print(f"[dim]{line}[/dim]")
        elif "RALPH_STATUS" in line:
            console.print(f"[bold green]{line}[/bold green]")
        elif any(w in line for w in ("Error", "error", "FAIL", "failed")):
            console.print(f"[red]{line}[/red]")
        elif any(w in line for w in ("PASS", "✅", "passed")):
            console.print(f"[green]{line}[/green]")
        else:
            console.print(line)


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option("--project", "-p", default=None)
@click.option("--keep", default=10, show_default=True, help="Recent entries to keep verbatim")
@click.option("--model", default="claude-haiku-4-5-20251001", show_default=True,
              help="Model used for summarization")
def compact(project, keep, model):
    """Compress old progress.txt entries into a digest (memory management)."""
    from functools import partial
    from . import progress as prog
    from .executor import run_claude_text

    project_root = _resolve_project(project)
    ralph_dir = _require_ralph_dir(project_root)
    progress_path = ralph_dir / "progress.txt"
    if not progress_path.exists():
        console.print("[red]No progress.txt found.[/red]")
        sys.exit(1)

    console.print(f"[dim]Summarizing old entries with {model}...[/dim]")
    summarize = partial(run_claude_text, cwd=project_root, model=model)
    changed, message = prog.compact(progress_path, keep, summarize, project_root)
    style = "green" if changed else "yellow"
    console.print(f"[{style}]{message}[/{style}]")
    sys.exit(0 if changed or "nothing to compact" in message else 1)


# ──────────────────────────────────────────────────────────────────────────────
@main.command(name="pr")
@click.option("--project", "-p", default=None)
@click.option("--draft", is_flag=True, help="Create as draft PR")
def pr_cmd(project, draft):
    """Create a GitHub PR from the run branch (requires gh CLI)."""
    from .pr import create_pr

    project_root = _resolve_project(project)
    ralph_dir = _require_ralph_dir(project_root)
    if not (ralph_dir / "prd.json").exists():
        console.print("[red]No prd.json found.[/red]")
        sys.exit(1)

    sys.exit(0 if create_pr(project_root, draft=draft) else 1)


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option("--project", "-p", default=None)
def reset_circuit(project):
    """Reset the circuit breaker (clears no-progress / same-error counters)."""
    project_root = _resolve_project(project)
    ralph_dir = _require_ralph_dir(project_root)
    from .circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(ralph_dir / "circuit_state.json", project_root)
    cb.reset()
    console.print("[green]Circuit breaker reset.[/green]")


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option("--project", "-p", default=None)
@click.option("--force", is_flag=True, help="Archive even with pending stories")
def archive(project, force):
    """Move the finished run's state to .ralph/history/ for a fresh start."""
    from .archive import archive_run

    project_root = _resolve_project(project)
    _require_ralph_dir(project_root)

    archived, message = archive_run(project_root, force=force)
    style = "green" if archived else "yellow"
    console.print(f"[{style}]{message}[/{style}]")
    sys.exit(0 if archived else 1)


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option("--project", "-p", default=None)
@click.option("--run-tests", is_flag=True, help="Also execute test_command as part of the check")
def doctor(project, run_tests):
    """Validate the Ralph setup (claude binary, git, prd, config, notifications)."""
    from .doctor import run_doctor

    project_root = _resolve_project(project)
    sys.exit(0 if run_doctor(project_root, run_tests=run_tests) else 1)


# ──────────────────────────────────────────────────────────────────────────────
@main.command()
@click.option("--project", "-p", default=None)
def init(project):
    """Initialize a new Ralph project (creates .ralph/ directory and .ralphrc)."""
    from .scaffold import ensure_claude_scaffold
    from .detect import detect_commands

    project_root = _resolve_project(project)
    ralph_dir = project_root / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    (ralph_dir / "logs").mkdir(exist_ok=True)

    # Keep an existing .ralphrc; env secrets are not applied so they can't
    # leak into the saved file
    config = RalphConfig.load(project_root, apply_env=False)
    detected = detect_commands(project_root)
    detected_lines = []
    for field_name, command in detected.items():
        if not getattr(config, field_name):
            setattr(config, field_name, command)
            detected_lines.append(f"Detected {field_name}: [cyan]{command}[/cyan]")
    config.save(project_root)
    created = ensure_claude_scaffold(project_root)
    created_lines = "\n".join(
        f"Created: [cyan]{p.relative_to(project_root)}[/cyan]" for p in created
    )
    if not created_lines:
        created_lines = "Claude Code Ralph instructions already present."

    detected_block = ("\n".join(detected_lines) + "\n") if detected_lines else ""
    console.print(Panel(
        f"[bold green]Ralph initialized[/bold green]\n\n"
        f"Created: [cyan].ralph/[/cyan]\n"
        f"Created: [cyan].ralphrc[/cyan]\n"
        f"{created_lines}\n{detected_block}\n"
        "Next shell step: [bold]claude[/bold]\n"
        "Then tell Claude what you want to build in plain language.\n"
        "It will use the Ralph instructions from [cyan]CLAUDE.md[/cyan].\n"
        "Or from shell: [bold]ralph interview[/bold]",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
