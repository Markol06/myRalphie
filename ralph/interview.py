"""Interview phase helpers for the Claude-native Ralph workflow."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .scaffold import ensure_claude_scaffold

console = Console()


def ensure_ralph_dir(project_root: Path) -> Path:
    ralph_dir = project_root / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    return ralph_dir


def run_interview(project_root: Path, dry_run: bool = False) -> bool:
    """
    Prepare the Claude-native interview flow.

    Returns True if setup completed successfully.
    """
    ensure_ralph_dir(project_root)
    ensure_claude_scaffold(project_root)

    if dry_run:
        console.print("[yellow][DRY RUN] Claude-native interview scaffold prepared.[/yellow]")
        return True

    console.print(Panel(
        "[bold cyan]Interview flow prepared[/bold cyan]\n\n"
        "1. Start Claude Code in this project: [bold]claude[/bold]\n"
        "2. Describe your feature in plain language\n"
        "3. Claude will use AskUserQuestionTool and create:\n"
        "   [cyan].ralph/prd.json[/cyan], [cyan].ralph/progress.txt[/cyan], "
        "[cyan].ralph/AGENT.md[/cyan], [cyan].ralphrc[/cyan]\n"
        "4. After interview is done, run [bold]ralph run[/bold]",
        title="Interview Ready",
        border_style="cyan",
    ))
    return True
