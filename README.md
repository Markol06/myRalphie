# Ralph

Ralph is a lightweight wrapper around a Ralph Wiggum style workflow for Claude Code.

The intended setup is Claude-native:
- `ralph init` prepares `.ralph/` files and injects Ralph workflow guidance into `CLAUDE.md`
- you start `claude` in your project
- you describe what you want to build in plain language
- Claude uses `AskUserQuestionTool` to interview you and writes Ralph state files

The autonomous external loop is still available through the `ralph` CLI.

## Install

```bash
pip install -e /path/to/this/ralph/
```

## Recommended Flow

```bash
# 1. Go to your project
cd my-project

# 2. Initialize Ralph
ralph init

# 3. Start Claude Code
claude
```

Inside Claude Code, say something like:

```text
I want to build a Telegram bot that summarizes AI news daily.
```

Claude should inspect the repository, use `AskUserQuestionTool`, ask one question at a time, and then create:
- `.ralph/prd.json`
- `.ralph/progress.txt`
- `.ralph/AGENT.md`
- `.ralphrc`

When the PRD already exists, you can continue naturally inside Claude Code:

```text
Please continue Ralph and implement the next pending story.
```

## External Loop

If you want the existing fresh-process loop, install Claude Code CLI and use:

```bash
ralph run
ralph run --resume
```

If you explicitly want the old interview mode that spawns an external Claude process:

```bash
ralph interview --spawn-claude
```

## Commands

| Command | Description |
|---------|-------------|
| `ralph init` | Initialize `.ralph/`, prompt files, and Ralph instructions in `CLAUDE.md` |
| `ralph interview` | Prepare the Claude-native interview flow and show the next steps |
| `ralph interview --spawn-claude` | Run the legacy external Claude interview |
| `ralph run` | Run the autonomous chunk loop |
| `ralph run --resume` | Resume the autonomous loop |
| `ralph resume` | Alias for `run --resume` |
| `ralph status` | Show current project status |
| `ralph cost` | Show cost breakdown |
| `ralph log` | Show iteration logs |
| `ralph skip S001` | Mark a story as failed and move on |
| `ralph retry S001` | Reset a failed story |
| `ralph reset-circuit` | Reset the circuit breaker |

## What `ralph init` Creates

```text
.ralph/
  prompts/
    interview.md
    next_story.md
    bootstrap_message.txt
  logs/
.ralphrc
CLAUDE.md   # updated or created with Ralph workflow instructions
```

## Claude-native Behavior

After `ralph init`, the project `CLAUDE.md` tells Claude Code to:
- start a Ralph interview when the user describes a new feature and `.ralph/prd.json` does not exist
- read `.ralph/prompts/interview.md`
- use `AskUserQuestionTool`
- ask one question at a time
- write the Ralph state files

If `.ralph/prd.json` already exists and the user asks to continue Ralph, Claude should:
- read `.ralph/prompts/next_story.md`
- pick the first pending story
- implement it
- run checks
- update Ralph state files

## Notes

- `/ralph-interview` is not part of the intended flow anymore.
- You should talk to Claude normally after launching `claude`.
- The current autonomous loop still uses the external `claude` executable for `ralph run`.
