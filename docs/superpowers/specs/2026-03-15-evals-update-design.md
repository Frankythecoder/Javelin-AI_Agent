# Evals Update for Refactored Agent Tools

**Date:** 2026-03-15
**Status:** Approved

## Problem

The `evals/` folder is out of sync with the refactored `agents/` package:

1. `runner.py` manually imports 15 tool definitions, but the agents package now exports 40
2. `tasks.json` references the old monolithic `agents.py` file (now `agents/` package)
3. `tasks.json` has stale file paths for test assets moved to `samples/`
4. No eval tasks exist for GitHub, travel, email, document, audio, directory navigation, or browser automation tools

## Scope

- Update `runner.py` to dynamically discover all tool definitions
- Fix stale references in existing `tasks.json` entries
- Add new eval tasks for all missing tool categories (dry-run style)
- Leave `metrics.py` unchanged (already handles dynamic categories)

## Design

### 1. `runner.py` — Dynamic Tool Discovery

Replace the manual import block (lines 36-53) and explicit tool list (lines 62-77) with dynamic discovery:

```python
import agents as agents_module

Agent = agents_module.Agent

# Dynamically collect all tool definitions (with type guard)
tools = [
    getattr(agents_module, name)
    for name in sorted(dir(agents_module))
    if name.endswith('_DEFINITION')
    and isinstance(getattr(agents_module, name), agents_module.ToolDefinition)
]

print(f"Discovered {len(tools)} tool definitions")
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

Fix task_022 expected_output: current text says "Enhanced error handling in agents.py" but the prompt says "do not edit the file." Update expected_output to "Agent identifies potential error handling improvements without editing the file."

Update file paths for moved test assets:

| Task | Current | Updated |
|------|---------|---------|
| task_025 | `test_image.jpg` | `samples/test_image.jpg` |
| task_026 | `test_video.mp4` | `samples/test_video.mp4` |

### 3. `tasks.json` — New Eval Tasks

All new tasks are **dry-run style** — they ask the agent to explain how it would use tools rather than executing with real side effects.

| Task ID | Category | Description |
|---------|----------|-------------|
| task_028 | GitHub Tools | Explain creating a branch, committing, opening a PR, and creating an issue |
| task_029 | Travel Tools | Explain searching flights, booking, retrieving details, listing bookings, and cancelling |
| task_030 | Document Creation | Explain creating a PDF report, Excel spreadsheet, DOCX document, and PPTX presentation |
| task_031 | Document Read/Edit | Explain reading and editing each document type (PDF, DOCX, Excel, PPTX) |
| task_032 | Audio Recognition | Explain transcribing/analyzing an audio file |
| task_033 | Directory Navigation | Explain changing working directory and listing contents |
| task_034 | Browser Automation | Explain using the Playwright MCP tool to automate web interaction (note: this tool is defined in `agents/email_tools.py` alongside the Gmail tool) |
| task_035 | Email Composition | Explain how to compose and send an email using the Gmail tool, describing the tool call and parameters |

### 4. Files Not Changed

- `metrics.py` — already handles dynamic per-category breakdowns
- `baseline_results.json`, `results.json`, `full_results.json` — existing result snapshots, untouched. Note: these baselines were generated with 27 tasks and will not be directly comparable to new runs with 35 tasks. Future runs will establish new baselines.

### 5. Known Agent Package Issues

The dynamic discovery approach will include all `*_DEFINITION` exports from `agents/__init__.py`. Two observations about the current exports:

- `GITHUB_MCP_DEFINITION` is exported but has no corresponding `github_mcp_tool` function import. It likely serves as the definition for `github_create_pr_tool` under a different naming convention.
- `github_create_pr_tool` is imported but no `GITHUB_CREATE_PR_DEFINITION` is exported — the `GITHUB_MCP_DEFINITION` likely fills this role.

These are pre-existing naming inconsistencies in the agents package and are out of scope for this change. The dynamic discovery will include `GITHUB_MCP_DEFINITION` as-is.

## Approach Rationale

**Dynamic discovery over explicit lists:** The root cause of the drift was a manually maintained import list. Dynamic discovery via `dir(agents_module)` filtering for `*_DEFINITION` names eliminates this class of problem. The trade-off (slightly less visibility into which tools are active) is acceptable because the agents package `__init__.py` is the authoritative list.

**Dry-run tasks for side-effect tools:** GitHub, travel, email, and browser tools have real external side effects. Dry-run tasks test the agent's understanding and tool selection without requiring test infrastructure or risking unintended actions.
