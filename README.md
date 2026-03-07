# Ralph

Ralph is an autonomous Claude Code loop with a Claude-native interview phase.

Target workflow:
1. Interview in Claude Code using `AskUserQuestionTool`
2. Execute stories via autonomous `ralph run`
3. Track tokens/cost and get Telegram notifications

## Install

```bash
pip install -e /path/to/this/ralph/
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
