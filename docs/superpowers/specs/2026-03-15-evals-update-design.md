# Evals Update for Refactored Agent Tools

**Date:** 2026-03-15
**Status:** Approved

## Problem

The `evals/` folder is out of sync with the refactored `agents/` package:

1. `runner.py` manually imports 15 tool definitions, but the agents package now exports ~40
2. `tasks.json` references the old monolithic `agents.py` file (now `agents/` package)
3. `tasks.json` has stale file paths for test assets moved to `samples/`
4. No eval tasks exist for GitHub, travel, document, audio, directory navigation, or browser automation tools

## Scope

- Update `runner.py` to dynamically discover all tool definitions
- Fix stale references in existing `tasks.json` entries
- Add new eval tasks for all missing tool categories (dry-run style)
- Leave `metrics.py` unchanged (already handles dynamic categories)

## Design

### 1. `runner.py` — Dynamic Tool Discovery

Replace the manual import block (lines 36-54) and explicit tool list (lines 62-78) with dynamic discovery:

```python
import agents as agents_module

Agent = agents_module.Agent

# Dynamically collect all tool definitions
tools = [
    getattr(agents_module, name)
    for name in sorted(dir(agents_module))
    if name.endswith('_DEFINITION')
]
```

This ensures any future tool additions are automatically included in evals without modifying `runner.py`.

### 2. `tasks.json` — Fix Stale References

Update existing tasks that reference `agents.py`:

| Task | Current | Updated |
|------|---------|---------|
| task_011 | `agents.py` | `agents/` package |
| task_012 | `agents.py` | `agents/` package |
| task_019 | `agents.py` | `agents/` package |
| task_022 | `agents.py` | `agents/file_tools.py` |
| task_023 | `agents.py` | `agents/core.py` |
| task_024 | `agents.py` | `agents/file_tools.py` |

Update file paths for moved test assets:

| Task | Current | Updated |
|------|---------|---------|
| task_025 | `test_image.jpg` | `samples/test_image.jpg` |
| task_026 | `test_video.mp4` | `samples/test_video.mp4` |

### 3. `tasks.json` — New Eval Tasks

All new tasks are **dry-run style** — they ask the agent to explain how it would use tools rather than executing with real side effects.

| Task ID | Category | Description |
|---------|----------|-------------|
| task_028 | GitHub Tools | Explain creating a branch, committing, and opening a PR |
| task_029 | Travel Tools | Explain searching flights, booking, and retrieving details |
| task_030 | Document Creation | Explain creating a PDF report and Excel spreadsheet |
| task_031 | Document Read/Edit | Explain reading and editing a DOCX file |
| task_032 | Audio Recognition | Explain transcribing/analyzing an audio file |
| task_033 | Directory Navigation | Explain changing working directory and listing contents |
| task_034 | Browser Automation | Explain using Playwright MCP for web automation |

### 4. Files Not Changed

- `metrics.py` — already handles dynamic per-category breakdowns
- `baseline_results.json`, `results.json`, `full_results.json` — existing result snapshots, untouched

## Approach Rationale

**Dynamic discovery over explicit lists:** The root cause of the drift was a manually maintained import list. Dynamic discovery via `dir(agents_module)` filtering for `*_DEFINITION` names eliminates this class of problem. The trade-off (slightly less visibility into which tools are active) is acceptable because the agents package `__init__.py` is the authoritative list.

**Dry-run tasks for side-effect tools:** GitHub, travel, email, and browser tools have real external side effects. Dry-run tasks test the agent's understanding and tool selection without requiring test infrastructure or risking unintended actions.
