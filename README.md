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

- The whole run happens on a single branch — `branch_name` from `prd.json`,
  created from `base_branch` if it doesn't exist yet (trunk-based, so every
  story builds on the previous ones).
- Each iteration spawns a fresh non-interactive Claude Code instance with
  **full tool access** (`bypassPermissions`). Run Ralph only in repos where
  you accept that.
- A story is marked done only after Ralph independently verifies the claim:
  a new commit must exist and `test_command` (if configured) must pass when
  Ralph runs it itself.
- Cost and token usage come from Claude Code's structured `stream-json`
  output and are logged per iteration to `.ralph/cost.log`.
- A circuit breaker pauses the run after repeated no-progress iterations or
  the same failure summary repeating.

## Commands

| Command | Description |
|---------|-------------|
| `ralph init` | Initialize `.ralph/`, prompt files, and Ralph instructions in `CLAUDE.md` |
| `ralph interview` | Prepare the Claude-native interview flow and show next steps |
| `ralph run` | Run autonomous chunk loop |
| `ralph run --resume` | Resume loop |
| `ralph resume` | Alias for `run --resume` |
| `ralph status` | Show progress and totals |
| `ralph cost` | Show per-iteration cost/tokens |
| `ralph log` | Show full iteration logs |
| `ralph skip S001` | Mark story failed and move on |
| `ralph retry S001` | Reset failed story |
| `ralph reset-circuit` | Reset circuit breaker |

## Configuration (`.ralphrc`)

```json
{
  "chunk_size": 5,
  "max_retries": 3,
  "claude_timeout": 900,
  "model": "",
  "max_turns": 0,
  "test_command": "pytest -q",
  "lint_command": "ruff check .",
  "build_command": "",
  "base_branch": "main"
}
```

- `model` — model for autonomous iterations (e.g. `claude-sonnet-5`); empty
  uses your account default.
- `max_turns` — cap on agent turns per iteration; `0` means unlimited.
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
