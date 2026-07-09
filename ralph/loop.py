"""Main Ralph loop — runs chunk_size iterations of the autonomous coding loop."""
from __future__ import annotations

import json
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
    git_current_branch, git_create_branch, git_checkout, git_dirty_files,
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
_STATUS_MARKER_RE = re.compile(r"RALPH_STATUS", re.IGNORECASE)

# Passed to claude via --json-schema: the CLI validates the final structured
# output against this, so the status arrives as data instead of parsed text
STATUS_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "story_id": {"type": "string"},
        "result": {"type": "string", "enum": ["PASS", "FAIL"]},
        "exit_signal": {"type": "boolean"},
        "summary": {"type": "string"},
        "learnings": {"type": "string"},
        "test_output": {"type": "string"},
    },
    "required": ["story_id", "result", "exit_signal", "summary"],
})


def _status_from_structured(data: dict | None) -> dict | None:
    """Normalize --json-schema structured output into the status dict."""
    if not isinstance(data, dict):
        return None
    result = str(data.get("result", "")).upper()
    if result not in ("PASS", "FAIL"):
        return None
    return {
        "story_id": str(data.get("story_id", "")),
        "result": result,
        "exit_signal": bool(data.get("exit_signal", False)),
        "summary": str(data.get("summary", "")),
        "learnings": str(data.get("learnings", "")),
        "test_output": str(data.get("test_output", "")),
    }


def _parse_ralph_status(output: str) -> dict | None:
    # Anchor to the LAST "RALPH_STATUS" marker: Claude may quote the status
    # format earlier in the output, but the real block is emitted at the end.
    # (A single greedy search would swallow both blocks as one match.)
    markers = list(_STATUS_MARKER_RE.finditer(output))
    for marker in reversed(markers):
        tail = output[marker.start():]
        m = _STATUS_RE.search(tail)
        if not m:
            continue  # partial/quoted mention without fields — try earlier one
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
    return None


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


VERIFY_COMMAND_TIMEOUT = 600  # seconds per verification command after a claimed PASS
GOAL_STOP_TURNS = 30          # bound inside the /goal condition; /goal conditions max out at 4000 chars
_GOAL_MAX_CHARS = 3800


def _build_goal_condition(story, config: RalphConfig) -> str:
    """Completion condition for /goal — checked by an independent evaluator
    after every turn, so it must be demonstrable from the transcript."""
    criteria = "; ".join(story.acceptance_criteria) or "the story description is implemented"
    parts = [
        f'Story {story.id} "{story.title}" is fully implemented. '
        f"All acceptance criteria demonstrably hold: {criteria}."
    ]
    if config.test_command:
        parts.append(f"`{config.test_command}` was run and exited 0 (show the output).")
    parts.append("All changes are committed (`git status` shows a clean tree).")
    parts.append("The final status has been reported.")
    parts.append(
        f"If the story cannot be completed, stop after {GOAL_STOP_TURNS} turns "
        "and report result FAIL with the blocker."
    )
    condition = " ".join(parts)
    return condition[:_GOAL_MAX_CHARS]


def _ensure_run_branch(project_root: Path, branch: str, base: str) -> tuple[bool, str]:
    """Trunk-based run: one branch (prd.branch_name) for the whole run.

    Checks out the branch if it exists, otherwise creates it from base.
    """
    if not branch:
        return True, ""
    if git_current_branch(project_root) == branch:
        return True, ""
    if git_checkout(project_root, branch):
        return True, ""
    if git_create_branch(project_root, branch, base):
        return True, ""
    return False, f"could not checkout or create branch '{branch}' from '{base}'"


def _verify_pass(
    project_root: Path, config: RalphConfig, commit_before: str
) -> tuple[bool, str]:
    """Independently verify a claimed PASS: new commit exists, tests/lint/build pass."""
    commit_after = git_current_commit(project_root)
    if commit_after == commit_before:
        return False, "claimed PASS but produced no new commit"

    checks = [
        ("tests", config.test_command),
        ("lint", config.lint_command),
        ("build", config.build_command),
    ]
    for label, command in checks:
        if not command:
            continue
        console.print(f"  [dim]Verifying {label}: {command}[/dim]")
        r = run_command(command, project_root, timeout=VERIFY_COMMAND_TIMEOUT)
        if r.timed_out:
            return False, f"verification {label} run timed out after {VERIFY_COMMAND_TIMEOUT}s"
        if r.returncode != 0:
            tail = (r.stdout + "\n" + r.stderr).strip()[-500:]
            return False, f"claimed PASS but verification {label} failed:\n{tail}"

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
    until_done: bool = False,
) -> None:
    ralph_dir = project_root / ".ralph"
    prd_path = ralph_dir / "prd.json"
    session_path = ralph_dir / "session.json"
    cost_log_path = ralph_dir / "cost.log"
    cb_state_path = ralph_dir / "circuit_state.json"

    # Load state
    prd = PRD.load(prd_path)
    session = Session.load(session_path)
    prog.init(ralph_dir / "progress.txt")
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
    elif session.is_chunk_done(config.chunk_size):
        # Resuming after chunk_done: the finished chunk would make the loop a
        # no-op, so roll into the next chunk
        session.start_new_chunk()

    # Refuse to start on a dirty tree — the agent commits with `git add -A`,
    # so any local edits would get mixed into its commits
    if not config.dry_run:
        dirty = git_dirty_files(project_root)
        if dirty:
            shown = "\n".join(dirty[:10])
            more = f"\n... and {len(dirty) - 10} more" if len(dirty) > 10 else ""
            console.print(Panel(
                f"[bold red]Working tree is not clean[/bold red]\n\n{shown}{more}\n\n"
                "Commit or stash your changes first, then run [bold]ralph run[/bold] again.",
                border_style="red",
            ))
            return

    # Trunk-based branching: the whole run lives on prd.branch_name
    if not config.dry_run:
        ok, branch_err = _ensure_run_branch(project_root, prd.branch_name, config.base_branch)
        if not ok:
            console.print(Panel(
                f"[bold red]Git branch setup failed[/bold red]\n\n{branch_err}\n\n"
                "Fix the working tree (uncommitted changes?) and run "
                "[bold]ralph run --resume[/bold]",
                border_style="red",
            ))
            session.status = "paused"
            session.pause_reason = f"branch_setup: {branch_err}"
            session.save(session_path)
            return

    session.status = "running"
    session.save(session_path)

    _print_stats(prd, session, config, project_root)

    # ──────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────
    while not session.is_chunk_done(config.chunk_size):
        story = prd.next_story()
        if story is None:
            # No pending stories left — the completion block below handles
            # status and the single completion notification
            console.print("[bold green]✅ No more pending stories![/bold green]")
            break

        # Budget check — the only safeguard that protects the wallet directly
        if config.max_cost_usd > 0:
            spent = cost_tracker.total_cost(cost_log_path)
            if spent >= config.max_cost_usd:
                console.print(Panel(
                    f"[bold red]💸 Budget limit reached[/bold red]\n\n"
                    f"Spent ${spent:.2f} of max ${config.max_cost_usd:.2f}\n\n"
                    "Raise max_cost_usd in .ralphrc (or archive cost.log) and run "
                    "[bold]ralph run --resume[/bold]",
                    border_style="red",
                ))
                session.status = "paused"
                session.pause_reason = f"budget_limit: ${spent:.2f} >= ${config.max_cost_usd:.2f}"
                session.save(session_path)
                notify(
                    config,
                    f"💸 *{prd.project_name}* — budget limit reached: "
                    f"${spent:.2f} of ${config.max_cost_usd:.2f}. Run paused.",
                )
                return

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

        # Build prompt
        prompt = _build_iteration_prompt(story, config, project_root)

        # Execute — escalate to retry_model after a failed first attempt
        model = config.model
        if story.retries > 0 and config.retry_model:
            model = config.retry_model
            console.print(f"  [dim]Retry {story.retries} — escalating to {model}[/dim]")

        commit_before = git_current_commit(project_root)
        console.print("  [dim]Spawning fresh Claude Code instance...[/dim]")

        if config.use_goal:
            # /goal mode: the iteration context rides in the system prompt and
            # the user message is the goal condition — an independent evaluator
            # (small fast model) re-checks it after every turn and keeps the
            # agent working until it holds
            context_file = ralph_dir / "iteration_context.md"
            context_file.write_text(prompt, encoding="utf-8")
            goal_message = f"/goal {_build_goal_condition(story, config)}"
            result = run_claude(
                prompt=goal_message,
                project_root=project_root,
                timeout_seconds=config.claude_timeout,
                dry_run=config.dry_run,
                model=model,
                max_turns=config.max_turns,
                json_schema=STATUS_SCHEMA,
                append_system_prompt_file=context_file,
            )
            prompt = f"{goal_message}\n\n── SYSTEM CONTEXT ──\n\n{prompt}"  # for the log
        else:
            result = run_claude(
                prompt=prompt,
                project_root=project_root,
                timeout_seconds=config.claude_timeout,
                dry_run=config.dry_run,
                model=model,
                max_turns=config.max_turns,
                json_schema=STATUS_SCHEMA,
            )

        output = result.combined_output()

        # Status: validated structured output first, text parsing as fallback
        # (older CLI versions without --json-schema support)
        status = (
            _status_from_structured(result.structured_output)
            or _parse_ralph_status(result.result_text)
            or _parse_ralph_status(output)
        )

        # Cost tracking — structured data from the stream-json result event
        cost_data = {
            "cost_usd": result.cost_usd,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
        console.print(
            "  [dim]Usage: "
            f"in {cost_data['input_tokens']} · "
            f"out {cost_data['output_tokens']} · "
            f"cost ${cost_data['cost_usd']:.4f} · "
            f"turns {result.num_turns}[/dim]"
        )

        if result.timed_out:
            # A timeout usually means the story is too large for one session —
            # record that explicitly so the retry (and the human) know
            console.print(f"[yellow]⚠️  Claude timed out after {config.claude_timeout}s[/yellow]")
            result_str = "timeout"
            is_pass = False
            status = None
        elif status is None:
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
            prd.mark_done(story.id, current_commit, prd.branch_name)
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
            if result.timed_out:
                failure_summary = (
                    f"timed out after {config.claude_timeout}s — "
                    "story may be too large for one session, consider splitting it"
                )
            elif verify_reason:
                failure_summary = verify_reason
            elif status:
                failure_summary = status["summary"]
            else:
                failure_summary = "No RALPH_STATUS"

            retry_count = prd.increment_retry(story.id)
            # Persist the reason so the next iteration sees it as retry_notes
            story.notes = f"attempt {retry_count}: {failure_summary}"[:500]
            # Use the summary for same-error detection: raw output tails are
            # full of timestamps/paths and never compare equal
            cb.record_failure(failure_summary)
            prd.save(prd_path)
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
                    f"Test output:\n{(status.get('test_output', '') if status else output[-500:])[:500]}",
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
        total_cost = cost_tracker.total_cost(cost_log_path)
        next_step = (
            "Continuing automatically ([bold]--until-done[/bold])"
            if until_done
            else "Continue with: [bold]ralph run --resume[/bold]"
        )
        console.print(Panel(
            f"[bold yellow]⏸  Chunk {session.chunk_number} done[/bold yellow]\n\n"
            f"Progress: {stats['done']}/{stats['total']} stories complete\n"
            f"Remaining: {stats['pending']} stories, {stats['failed']} failed\n\n"
            f"{next_step}",
            border_style="yellow",
        ))
        notify(
            config,
            f"⏸ *{prd.project_name}* — chunk {session.chunk_number} done: "
            f"{stats['done']}/{stats['total']} stories, ${total_cost:.2f} spent. "
            + ("Continuing automatically." if until_done
               else "Continue with `ralph run --resume`."),
        )
        if until_done:
            # Roll straight into the next chunk; the resume path starts it.
            # Budget limit and circuit breaker remain the stop conditions.
            session.save(session_path)
            return run_loop(project_root, config, resume=True, until_done=True)
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
