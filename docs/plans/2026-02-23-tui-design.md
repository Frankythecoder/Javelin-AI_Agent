# TUI Design: Interactive Terminal Interface for AI Agent

**Date:** 2026-02-23
**Status:** Approved

## Overview

A standalone Textual-based terminal interface that drives the existing Agent class directly, enabling independent TUI instances in separate terminal windows, each working in a different directory.

## Architecture

- **Approach:** Direct LangGraph integration (no HTTP, no Django server needed)
- **Entry point:** `tui.py` → installed as `agent` CLI command via `pyproject.toml`
- **Django bootstrap:** TUI calls `django.setup()` at startup for ToolLog ORM access
- **No existing files modified**

```
tui.py (Textual App)
  ├── Bootstraps Django settings
  ├── Creates Agent instance directly
  ├── Calls agent.chat_once() / execute_dry_run()
  └── Renders everything in terminal

agents.py (unchanged)
  ├── Agent class
  ├── chat_once() → returns status dict
  ├── execute_dry_run() → executes plan
  └── _execute_tool_by_name()
```

## TUI Layout

- **Header:** App name, current working directory, agent status (Ready/Thinking/Executing/Awaiting Approval)
- **Message area:** Scrollable history with Rich markdown rendering
- **Tool panels:** Collapsible sections showing tool name, arguments, output
- **Dry-run plan:** Numbered list with Approve/Deny (keyboard: y/n)
- **Pending tool approval:** Per-tool approve/deny for high-risk tools
- **Status bar:** Current working directory, session info
- **Input:** Persistent text input at bottom, supports /commands

## User Flow

1. User types message → `agent.chat_once(history, message)`
2. `status == "dry_run"` → Show plan, prompt y/n → `agent.execute_dry_run()` or deny
3. `status == "pending"` → Show per-tool approval → execute or deny each
4. `status == "success"` → Render markdown response
5. `status == "error"` → Show error in red panel
6. `status == "stopped"` → Show stop message

### Keyboard Shortcuts

- `y` / `n` — Approve/deny during prompts
- `Ctrl+C` — Stop agent execution
- `Ctrl+D` — Exit TUI
- `Escape` — Cancel current input

### Slash Commands

- `/help` — Show available commands
- `/save [title]` — Save current session
- `/load` — List and load saved session
- `/sessions` — List all saved sessions
- `/clear` — Clear conversation history
- `/cwd` — Show current working directory
- `/stop` — Stop agent execution
- `/tools` — Toggle tools enabled/disabled

## Session Management

**Storage:** `~/.ai_agent/sessions/` as JSON files.

**Format:**
```json
{
  "id": "2026-02-23_14-30-00",
  "title": "Create hello world",
  "created_at": "2026-02-23T14:30:00",
  "updated_at": "2026-02-23T14:35:22",
  "working_directory": "/path/to/project",
  "history": [...]
}
```

- Auto-save after every agent response
- Title auto-generated from first user message (~40 chars)
- History uses same dict format as `chat_once()` / `_dicts_to_messages()`

## CLI Entry Point

```bash
javelin                          # Launch in current directory
javelin --dir ~/projects/myapp   # Launch in specific directory
javelin --load                   # Launch and show session picker
```

**`pyproject.toml`:**
```toml
[project]
name = "ai-agent"
version = "0.1.0"
dependencies = ["textual>=0.50.0"]

[project.scripts]
agent = "tui:main"
```

## New Files

| File | Purpose |
|------|---------|
| `tui.py` | Textual app — all TUI logic |
| `pyproject.toml` | Package config with CLI entry point |

## New Dependencies

| Package | Purpose |
|---------|---------|
| `textual>=0.50.0` | TUI framework (includes Rich) |

## Existing Files Changed

None.
