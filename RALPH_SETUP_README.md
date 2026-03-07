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

```bash
# 1. Create your project folder
mkdir my-new-project
cd my-new-project
git init

# 2. Copy full Ralph codebase from this repo into the project root
# (README.md, pyproject.toml, ralph/ package, etc.)
git clone https://github.com/Markol06/myRalphie.git _ralph_tmp
Copy-Item -Path .\_ralph_tmp\pyproject.toml -Destination . -Force
Copy-Item -Path .\_ralph_tmp\ralph -Destination . -Recurse -Force
Copy-Item -Path .\_ralph_tmp\RALPH_SETUP_README.md -Destination . -Force
Remove-Item -Path .\_ralph_tmp -Recurse -Force

# 3. Install Ralph from the copied local code
pip install -e .

# 4. Initialize Ralph in this project
ralph init

# 5. Start interview
claude
```

Inside Claude Code, describe your feature in plain language. After interview files are created, run:

```bash
ralph run
```

## Setup in an Existing Project (copy full Ralph codebase)

Use this when your project is already in development and has no Ralph setup yet.

```bash
# 1. Open existing project repo
cd my-existing-project

# 2. Copy full Ralph codebase from https://github.com/Markol06/myRalphie
# into this repository (README.md, pyproject.toml, ralph/ package, etc.)
git clone https://github.com/Markol06/myRalphie.git _ralph_tmp
Copy-Item -Path .\_ralph_tmp\pyproject.toml -Destination . -Force
Copy-Item -Path .\_ralph_tmp\ralph -Destination . -Recurse -Force
Copy-Item -Path .\_ralph_tmp\RALPH_SETUP_README.md -Destination . -Force
Remove-Item -Path .\_ralph_tmp -Recurse -Force

# 3. Install Ralph from local project root
pip install -e .

# 4. Initialize Ralph files in this repo
ralph init

# 5. Start interview
claude
```

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

Set in `.ralphrc`:
- `telegram_token`
- `telegram_chat_id`

Ralph sends notifications for important autonomous loop events (fail-stop, circuit-breaker, completion).
