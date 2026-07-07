"""Main Ralph loop — runs chunk_size iterations of the autonomous coding loop."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import RalphConfig
from .prd import PRD
from .session import Session
from .circuit_breaker import CircuitBreaker
from . import progress as prog
from . import cost_tracker
from .executor import (
    run_claude, run_command, git_current_commit,
    git_create_branch, git_checkout,
)
from .notifier import notify
from . import logger as iteration_logger

console = Console()

_STATUS_RE = re.compile(
    r"RALPH_STATUS:.*?story_id:\s*(\S+).*?result:\s*(PASS|FAIL).*?"
    r"exit_signal:\s*(true|false).*?summary:\s*(.+?)(?=learnings:|test_output:|$)",
    re.DOTALL | re.IGNORECASE,
)
_LEARNINGS_RE = re.compile(r"learnings:\s*(.+?)(?=test_output:|$)", re.DOTALL | re.IGNORECASE)
_TEST_OUTPUT_RE = re.compile(r"test_output:\s*(.+?)$", re.DOTALL | re.IGNORECASE)


def _parse_ralph_status(output: str) -> dict | None:
    # Take the LAST match: Claude may quote the status format earlier in the
    # output, but the real block is emitted at the end.
    matches = list(_STATUS_RE.finditer(output))
    if not matches:
        return None
    m = matches[-1]
    tail = output[m.start():]
    learnings_m = _LEARNINGS_RE.search(tail)
    test_m = _TEST_OUTPUT_RE.search(tail)
    return {
        "story_id": m.group(1).strip(),
        "result": m.group(2).strip().upper(),
        "exit_signal": m.group(3).strip().lower() == "true",
        "summary": m.group(4).strip(),
        "learnings": learnings_m.group(1).strip() if learnings_m else "",
        "test_output": test_m.group(1).strip() if test_m else "",
    }


def _build_iteration_prompt(
    story, config: RalphConfig, project_root: Path
) -> str:
    templates_dir = Path(__file__).parent / "templates"
    template = (templates_dir / "iteration_prompt.md").read_text()

    # Recent git log
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-15"],
            cwd=project_root, capture_output=True, text=True, timeout=10,
        )
        git_log = result.stdout.strip() or "(no commits yet)"
    except Exception:
        git_log = "(could not read git log)"

    criteria_text = "\n".join(f"- {c}" for c in story.acceptance_criteria)

    prompt = template.format(
        story_id=story.id,
        story_title=story.title,
        story_description=story.description,
        acceptance_criteria=criteria_text,
        retries=story.retries,
        retry_notes=story.notes or "none",
        git_log=git_log,
        test_command=config.test_command or "# no test command configured",
        lint_command=config.lint_command or "# no lint command configured",
    )

    # Prepend recent progress (last 6000 chars)
    progress_text = prog.read_recent(project_root / ".ralph" / "progress.txt")
    agent_md_path = project_root / ".ralph" / "AGENT.md"
    agent_text = agent_md_path.read_text() if agent_md_path.exists() else ""

    return (
        f"## Recent Progress Log\n```\n{progress_text}\n```\n\n"
        f"## AGENT.md\n{agent_text}\n\n"
        f"---\n\n{prompt}"
    )


VERIFY_TEST_TIMEOUT = 600  # seconds for the independent test run after a claimed PASS


def _verify_pass(
    project_root: Path, config: RalphConfig, commit_before: str
) -> tuple[bool, str]:
    """Independently verify a claimed PASS: new commit exists, tests pass."""
    commit_after = git_current_commit(project_root)
    if commit_after == commit_before:
        return False, "claimed PASS but produced no new commit"

    if config.test_command:
        console.print(f"  [dim]Verifying: {config.test_command}[/dim]")
        r = run_command(config.test_command, project_root, timeout=VERIFY_TEST_TIMEOUT)
        if r.timed_out:
            return False, f"verification test run timed out after {VERIFY_TEST_TIMEOUT}s"
        if r.returncode != 0:
            tail = (r.stdout + "\n" + r.stderr).strip()[-500:]
            return False, f"claimed PASS but verification tests failed:\n{tail}"

    return True, ""


def _print_stats(prd: PRD, session: Session, config: RalphConfig, project_root: Path) -> None:
    stats = prd.stats()
    cost_log_path = project_root / ".ralph" / "cost.log"
    total_cost = cost_tracker.total_cost(cost_log_path)
    total_in, total_out = cost_tracker.total_tokens(cost_log_path)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("Chunk", f"{session.chunk_number}")
    table.add_row("Iteration in chunk", f"{session.iteration_in_chunk}/{config.chunk_size}")
    table.add_row("Total iterations", f"{session.total_iterations}")
    table.add_row("Stories", f"✅ {stats['done']}  ❌ {stats['failed']}  ⏳ {stats['pending']}  / {stats['total']}")
    table.add_row("Tokens", f"in {total_in} · out {total_out}")
    table.add_row("Total cost", f"${total_cost:.4f}")

    console.print(Panel(table, title="📊 Ralph Status", border_style="blue"))


def run_loop(
    project_root: Path,
    config: RalphConfig,
    resume: bool = False,
) -> None:
    ralph_dir = project_root / ".ralph"
    prd_path = ralph_dir / "prd.json"
    session_path = ralph_dir / "session.json"
    cost_log_path = ralph_dir / "cost.log"
    cb_state_path = ralph_dir / "circuit_state.json"

    # Load state
    prd = PRD.load(prd_path)
    session = Session.load(session_path)
    cb = CircuitBreaker(
        cb_state_path, project_root,
        no_progress_threshold=config.cb_no_progress_threshold,
        same_error_threshold=config.cb_same_error_threshold,
    )

    if prd.all_done():
        console.print(Panel(
            "[bold green]🎉 All stories complete! Project done.[/bold green]",
            border_style="green",
        ))
        notify(config, f"✅ *{prd.project_name}* — all stories complete!")
        return

    # Reset chunk counter if resuming a new chunk
    if not resume:
        session.iteration_in_chunk = 0
        if session.total_iterations > 0:
            session.start_new_chunk()

    session.status = "running"
    session.save(session_path)

    _print_stats(prd, session, config, project_root)

    # ──────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────
    while not session.is_chunk_done(config.chunk_size):
        story = prd.next_story()
        if story is None:
            console.print("[bold green]✅ No more pending stories![/bold green]")
            session.status = "complete"
            session.save(session_path)
            notify(config, f"✅ *{prd.project_name}* — all stories complete!")
            break

        # Circuit breaker check
        should_stop, reason = cb.should_open()
        if should_stop:
            console.print(Panel(
                f"[bold red]🔌 Circuit breaker opened[/bold red]\n\n{reason}\n\n"
                "Fix the issue then run [bold]ralph run --resume[/bold]",
                border_style="red",
            ))
            session.status = "paused"
            session.pause_reason = f"circuit_breaker: {reason}"
            session.save(session_path)
            notify(config, f"⚠️ *{prd.project_name}* — circuit breaker: {reason[:100]}")
            return

        iter_num = session.iteration_in_chunk + 1
        console.rule(
            f"[bold]Chunk {session.chunk_number} · Iteration {iter_num}/{config.chunk_size} "
            f"· Story {story.id}: {story.title}[/bold]"
        )

        # Branch per task
        if config.branch_per_task and not story.branch:
            branch_name = f"ralph/{story.id.lower()}-{story.title.lower().replace(' ', '-')[:30]}"
            branch_name = re.sub(r"[^a-z0-9\-/]", "", branch_name)
            story.branch = branch_name
            prd.save(prd_path)

            if not config.dry_run:
                git_create_branch(project_root, branch_name, config.base_branch)

        elif config.branch_per_task and story.branch:
            if not config.dry_run:
                git_checkout(project_root, story.branch)

        # Build prompt
        prompt = _build_iteration_prompt(story, config, project_root)

        # Execute
        commit_before = git_current_commit(project_root)
        console.print(f"  [dim]Spawning fresh Claude Code instance...[/dim]")
        result = run_claude(
            prompt=prompt,
            project_root=project_root,
            allowed_tools=config.allowed_tools,
            timeout_seconds=config.claude_timeout,
            dry_run=config.dry_run,
        )

        output = result.combined_output()

        # Parse RALPH_STATUS — prefer the final message, fall back to full transcript
        status = _parse_ralph_status(result.result_text) or _parse_ralph_status(output)

        # Cost tracking — structured data from the stream-json result event
        cost_data = {
            "cost_usd": result.cost_usd,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
        session.total_cost_usd += cost_data["cost_usd"]
        console.print(
            "  [dim]Usage: "
            f"in {cost_data['input_tokens']} · "
            f"out {cost_data['output_tokens']} · "
            f"cost ${cost_data['cost_usd']:.4f} · "
            f"turns {result.num_turns}[/dim]"
        )

        if status is None:
            # Claude didn't output RALPH_STATUS — treat as failure
            console.print("[yellow]⚠️  No RALPH_STATUS found in output[/yellow]")
            result_str = "no_status"
            is_pass = False
        else:
            is_pass = status["result"] == "PASS" and status["exit_signal"]
            result_str = "pass" if is_pass else "fail"

        # Don't trust the self-reported PASS — verify commit + tests independently
        verify_reason = ""
        if is_pass and not config.dry_run:
            verified, verify_reason = _verify_pass(project_root, config, commit_before)
            if not verified:
                console.print(f"  [yellow]⚠️  PASS not verified: {verify_reason}[/yellow]")
                is_pass = False
                result_str = "unverified"

        # Save full iteration log (prompt + raw output + result)
        iteration_logger.save(
            logs_dir=ralph_dir / "logs",
            story_id=story.id,
            story_title=story.title,
            chunk=session.chunk_number,
            iteration=session.total_iterations + 1,
            prompt=prompt,
            output=output,
            result=result_str,
            duration=result.duration_seconds,
            cost_usd=cost_data["cost_usd"],
        )

        cost_tracker.log(
            cost_log_path,
            chunk=session.chunk_number,
            iteration=session.total_iterations + 1,
            story_id=story.id,
            story_title=story.title,
            result=result_str,
            cost_data=cost_data,
        )

        if is_pass:
            # ── SUCCESS ──
            current_commit = git_current_commit(project_root)
            prd.mark_done(story.id, current_commit, story.branch)
            prd.save(prd_path)
            cb.record_success()

            if status:
                prog.append(
                    project_root / ".ralph" / "progress.txt",
                    story.id, story.title,
                    f"✅ DONE\nSummary: {status['summary']}\nLearnings: {status['learnings']}\n"
                    f"Test output:\n{status.get('test_output', '')[:500]}",
                )

            console.print(f"  [bold green]✅ Story {story.id} complete![/bold green]")
            if status:
                console.print(f"  [dim]{status['summary']}[/dim]")

        else:
            # ── FAILURE ──
            retry_count = prd.increment_retry(story.id)
            error_snippet = output[-500:] if output else ""
            cb.record_failure(error_snippet)
            prd.save(prd_path)

            if verify_reason:
                failure_summary = verify_reason
            elif status:
                failure_summary = status["summary"]
            else:
                failure_summary = "No RALPH_STATUS"
            console.print(f"  [red]❌ Story {story.id} failed (attempt {retry_count}/{config.max_retries})[/red]")
            console.print(f"  [dim]{failure_summary}[/dim]")

            if retry_count >= config.max_retries:
                # Stop and wait for human
                msg = (
                    f"Story [bold]{story.id}[/bold] failed after {retry_count} attempts.\n\n"
                    f"Last error: {failure_summary}\n\n"
                    "Options:\n"
                    "  1. Fix manually, then run [bold]ralph run --resume[/bold]\n"
                    f"  2. Skip this story: [bold]ralph skip {story.id}[/bold]\n"
                    f"  3. Retry from scratch: [bold]ralph retry {story.id}[/bold]"
                )
                console.print(Panel(msg, title="⏸  Waiting for you", border_style="yellow"))
                session.status = "paused"
                session.pause_reason = f"test_failure:{story.id}:{failure_summary[:100]}"
                session.save(session_path)
                notify(
                    config,
                    f"⚠️ *{prd.project_name}* — story `{story.id}` failed after "
                    f"{retry_count} attempts. Manual intervention needed."
                )
                return
            else:
                # retry next iteration — append failure note to progress
                prog.append(
                    project_root / ".ralph" / "progress.txt",
                    story.id, story.title,
                    f"❌ FAILED attempt {retry_count}\nError: {failure_summary}\n"
                    f"Test output:\n{(status.get('test_output', '') if status else error_snippet)[:500]}",
                )

        # Advance counters
        session.next_iteration()
        session.last_story_id = story.id
        session.save(session_path)

        _print_stats(prd, session, config, project_root)

    # ──────────────────────────────────────────────
    # CHUNK DONE
    # ──────────────────────────────────────────────
    if not prd.all_done():
        stats = prd.stats()
        console.print(Panel(
            f"[bold yellow]⏸  Chunk {session.chunk_number} done[/bold yellow]\n\n"
            f"Progress: {stats['done']}/{stats['total']} stories complete\n"
            f"Remaining: {stats['pending']} stories, {stats['failed']} failed\n\n"
            "Continue with: [bold]ralph run --resume[/bold]",
            border_style="yellow",
        ))
        session.status = "paused"
        session.pause_reason = "chunk_done"
    else:
        console.print(Panel(
            "[bold green]🎉 All done! Project complete.[/bold green]",
            border_style="green",
        ))
        session.status = "complete"
        notify(config, f"🎉 *{prd.project_name}* — project complete!")

    session.save(session_path)
