# Ralph

Ralph is an autonomous Claude Code loop with a Claude-native interview phase.

Target workflow:
1. Interview in Claude Code using `AskUserQuestionTool`
2. Execute stories via autonomous `ralph run`
3. Track tokens/cost and get Telegram notifications

## Install

```bash
git clone https://github.com/Markol06/myRalphie.git
cd myRalphie
pip install -e .
```

## Setup in a New Project (copy full Ralph codebase)

Use this when you start a new project and want Ralph scripts inside the same repo.

```powershell
# 1. Create your project folder
mkdir my-new-project
cd my-new-project
git init

# 2. Copy full Ralph codebase from this repo into the project root
git clone https://github.com/Markol06/myRalphie.git _ralph_tmp
Copy-Item -Path .\_ralph_tmp\pyproject.toml -Destination . -Force
Copy-Item -Path .\_ralph_tmp\ralph -Destination . -Recurse -Force
Copy-Item -Path .\_ralph_tmp\README.md -Destination .\RALPH_SETUP_README.md -Force
Remove-Item -Path .\_ralph_tmp -Recurse -Force

# 3. Install Ralph from the copied local code
pip install -e .

# 4. Initialize Ralph in this project
ralph init

# 5. Start interview
claude
```

On macOS/Linux replace the `Copy-Item`/`Remove-Item` lines with `cp`/`rm -rf`.

Inside Claude Code, describe your feature in plain language. After interview files are created, run:

```bash
ralph run
```

## Setup in an Existing Project

Same as above, starting from step 2, inside your existing repo.

Then continue with:

```bash
ralph run
ralph run --resume
```

## End-to-End Flow

```bash
# In your project
ralph init
claude
```

Inside Claude Code, describe your feature in plain language. Claude should run the interview and create:
- `.ralph/prd.json`
- `.ralph/progress.txt`
- `.ralph/AGENT.md`
- `.ralphrc`

Then run the autonomous loop:

```bash
ralph run
ralph run --resume
```

## How a Run Works

- The run starts only on a clean working tree, so your local edits never get
  mixed into the agent's commits.
- The whole run happens on a single branch — `branch_name` from `prd.json`,
  created from `base_branch` if it doesn't exist yet (trunk-based, so every
  story builds on the previous ones).
- Each iteration spawns a fresh non-interactive Claude Code instance with
  **full tool access** (`bypassPermissions`). Run Ralph only in repos where
  you accept that.
- A story is marked done only after Ralph independently verifies the claim:
  a new commit must exist and the configured `test_command`, `lint_command`
  and `build_command` must pass when Ralph runs them itself.
- Cost and token usage come from Claude Code's structured `stream-json`
  output and are logged per iteration to `.ralph/cost.log`.
- Safeguards that pause the run: circuit breaker (no git progress / same
  failure repeating), per-story retry limit, per-iteration timeout, and the
  `max_cost_usd` budget limit.
- By default the run pauses for review after each chunk (`chunk_size`
  iterations); `ralph run --until-done` rolls through chunks automatically
  until the stories are done or a safeguard stops it.
- Retries can escalate to a stronger model via `retry_model` — cheap first
  attempt, bigger model when a story resists.

## Commands

| Command | Description |
|---------|-------------|
| `ralph init` | Initialize `.ralph/`, `.ralphrc` (with auto-detected commands), `.gitignore` entries and `CLAUDE.md` instructions |
| `ralph doctor` | Validate the setup: claude binary, git, prd, config, notifications (`--run-tests` also runs tests) |
| `ralph interview` | Prepare the Claude-native interview flow and show next steps |
| `ralph run` | Run autonomous chunk loop |
| `ralph run --resume` | Resume loop |
| `ralph run --until-done` | Keep rolling through chunks until done or a safeguard stops the run |
| `ralph resume` | Alias for `run --resume` |
| `ralph status` | Show progress and totals |
| `ralph cost` | Show per-iteration cost/tokens |
| `ralph log` | Show full iteration logs |
| `ralph skip S001` | Mark story failed and move on |
| `ralph retry S001` | Reset failed story |
| `ralph reset-circuit` | Reset circuit breaker |
| `ralph compact` | Compress old `progress.txt` entries into a digest (memory management) |
| `ralph pr` | Push the run branch and open a GitHub PR via `gh` (`--draft` supported) |
| `ralph archive` | Move the finished run's state to `.ralph/history/` for a fresh start |

## Configuration (`.ralphrc`)

```json
{
  "chunk_size": 5,
  "max_retries": 3,
  "claude_timeout": 900,
  "model": "",
  "retry_model": "",
  "max_turns": 0,
  "max_cost_usd": 0,
  "test_command": "pytest -q",
  "lint_command": "ruff check .",
  "build_command": "",
  "base_branch": "main"
}
```

- `model` — model for autonomous iterations (e.g. `claude-sonnet-5`); empty
  uses your account default.
- `retry_model` — stronger model for retries (e.g. `claude-opus-4-8`); empty
  keeps using `model`.
- `max_turns` — cap on agent turns per iteration; `0` means unlimited.
- `max_cost_usd` — pause the run when total spend in `cost.log` reaches this
  amount; `0` means unlimited. Recommended for `--until-done` runs.
- `test_command` / `lint_command` / `build_command` are auto-detected by
  `ralph init` where possible and all run during PASS verification.
- `ralph init` also adds `.ralph/` and `.ralphrc` to the target project's
  `.gitignore` so local state and tokens never get committed.

## Files Created by `ralph init`

```text
.ralph/
  prompts/
    interview.md
    bootstrap_message.txt
  logs/
.ralphrc
CLAUDE.md
```

## Telegram Integration

Preferred: set environment variables (they override `.ralphrc`):

- `RALPH_TELEGRAM_TOKEN`
- `RALPH_TELEGRAM_CHAT_ID`
- `RALPH_DISCORD_WEBHOOK` (optional, Discord)

Ralph sends notifications for important autonomous loop events (fail-stop, circuit-breaker, completion).

## Development

```bash
pip install -e .[dev]
pytest
```
