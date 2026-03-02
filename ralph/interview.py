"""Interview phase helpers for Claude-native and external Claude CLI modes."""
from __future__ import annotations

import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from .scaffold import ensure_claude_scaffold

console = Console()


def ensure_ralph_dir(project_root: Path) -> Path:
    ralph_dir = project_root / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    return ralph_dir


def run_interview(project_root: Path, dry_run: bool = False, spawn_claude: bool = False) -> bool:
    """
    Prepare or launch the Ralph interview flow.

    Default mode is Claude-native: scaffold project-local Ralph instructions and
    instruct the user to start Claude Code normally, then talk to it naturally.

    Optional legacy mode launches an external Claude Code CLI process that
    conducts the interview and writes Ralph state files.

    Returns True if interview completed successfully.
    """
    ralph_dir = ensure_ralph_dir(project_root)
    ensure_claude_scaffold(project_root)

    if not spawn_claude:
        console.print(Panel(
            "[bold cyan]Claude-native Ralph interview is ready[/bold cyan]\n\n"
            "First start Claude Code in this project:\n"
            "[bold]claude[/bold]\n\n"
            "Then describe what you want to build in plain language.\n"
            "Claude will read the project-local Ralph instructions from [cyan]CLAUDE.md[/cyan]\n"
            "and use [bold]AskUserQuestionTool[/bold] to run the interview.\n\n"
            "Suggested first message:\n"
            "[bold]I want to build a Telegram bot that summarizes AI news daily.[/bold]\n\n"
            "This flow writes:\n"
            "[cyan].ralph/prd.json[/cyan], [cyan].ralph/progress.txt[/cyan], "
            "[cyan].ralph/AGENT.md[/cyan], [cyan].ralphrc[/cyan]\n\n"
            "If you still want the old behavior that spawns the external Claude CLI, "
            "run [bold]ralph interview --spawn-claude[/bold].",
            title="Interview Ready",
            border_style="cyan",
        ))
        return True

    # Load interview prompt template
    templates_dir = Path(__file__).parent / "templates"
    prompt_template = (templates_dir / "interview_prompt.md").read_text()

    console.print(Panel(
        "[bold cyan]Ralph Interview Phase[/bold cyan]\n\n"
        "Claude Code will now conduct an interview to understand your project.\n"
        "Answer each question — Claude will ask follow-up questions.\n"
        "When done, it will generate [bold].ralph/prd.json[/bold] automatically.",
        title="🎤 Interview",
        border_style="cyan",
    ))

    if dry_run:
        console.print("[yellow][DRY RUN] Would launch claude with interview prompt[/yellow]")
        # Create minimal stub files for testing
        _create_stub_files(ralph_dir, project_root)
        return True

    cmd = [
        "claude",
        "--dangerously-skip-permissions",
        "--allowedTools", "Write,Read,Edit,Bash(git *),AskUserQuestionTool",
        # Interactive mode (no --print) so user can see the interview live
        prompt_template,
    ]

    console.print("[dim]Launching Claude Code...[/dim]\n")

    try:
        # Run interactively (no capture) so user sees the conversation
        proc = subprocess.run(cmd, cwd=project_root)
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] `claude` not found. Install Claude Code first:")
        console.print("  npm install -g @anthropic-ai/claude-code")
        return False
    except KeyboardInterrupt:
        console.print("\n[yellow]Interview interrupted.[/yellow]")
        return False

    # Check that prd.json was created
    prd_path = ralph_dir / "prd.json"
    if not prd_path.exists():
        console.print(
            "[bold red]Interview did not produce .ralph/prd.json[/bold red]\n"
            "Make sure Claude completed the interview and saved the files."
        )
        return False

    console.print(Panel(
        "[bold green]✅ Interview complete![/bold green]\n\n"
        f"Created: [cyan].ralph/prd.json[/cyan]\n"
        f"Created: [cyan].ralph/progress.txt[/cyan]\n"
        f"Created: [cyan].ralph/AGENT.md[/cyan]\n\n"
        "Now run: [bold]ralph run[/bold]",
        title="Interview Done",
        border_style="green",
    ))
    return True


def _create_stub_files(ralph_dir: Path, project_root: Path) -> None:
    """Create stub files for dry-run / testing."""
    import json

    prd = {
        "project_name": "dry-run-project",
        "description": "Dry run test project",
        "branch_name": "ralph/dry-run",
        "stories": [
            {
                "id": "S001",
                "title": "Stub story for dry run",
                "description": "This is a dry-run stub",
                "acceptance_criteria": ["Tests pass"],
                "passes": False,
                "failed": False,
                "retries": 0,
                "branch": "",
                "commit": "",
                "notes": "",
            }
        ],
    }
    (ralph_dir / "prd.json").write_text(json.dumps(prd, indent=2))
    (ralph_dir / "progress.txt").write_text("# Ralph Progress Log\n# Dry run\n")
    (ralph_dir / "AGENT.md").write_text(
        "# Agent Instructions\n\n## Build & Test Commands\n- Test: `echo 'no tests'`\n"
    )
    rc = {"test_command": "echo 'no tests'", "lint_command": "", "build_command": ""}
    (project_root / ".ralphrc").write_text(json.dumps(rc, indent=2))
