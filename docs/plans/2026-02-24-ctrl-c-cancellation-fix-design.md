# Ctrl+C Cancellation Fix Design

## Problem

Two bugs when user presses Ctrl+C (TUI) or clicks Stop (web UI) during agent execution:

1. **Stop not immediate during plan approval**: The stop flag is set but the plan approval prompt remains visible. The stop message only appears after the user interacts with the approval prompt.

2. **Corrupted message history**: After stopping, the conversation history contains an `AIMessage` with `tool_calls` but no corresponding `ToolMessage` responses. The next `chat_once` call fails with OpenAI error 400: "An assistant message with 'tool_calls' must be followed by tool messages responding to each 'tool_call_id'".

## Root Cause

- `collect_dry_run` in the LangGraph returns `status="dry_run"` with an `AIMessage` containing `tool_calls` saved in `response_history`.
- When Ctrl+C sets `control.stopped = True`, the graph has already returned. The plan approval UI is already visible.
- On the next `chat_once` call, `control.stopped` is reset to `False` (line 4035), but the history still has the orphaned `AIMessage` with `tool_calls`.
- OpenAI rejects this invalid message sequence.

## Approach: A + C Hybrid

### Part A — Immediate cleanup on stop

**TUI (`tui.py`)**: Extend `action_stop_agent()` to:
- Clear approval state (`_awaiting_approval`, `_approval_type`, `_pending_plan`, `_pending_tools`)
- Remove the trailing `AIMessage` with unresponded `tool_calls` from `conversation_history`

**Web UI (`chat/templates/chat/index.html`)**: Extend `controlAgent('stop')` to:
- Remove plan/tool approval buttons from the DOM
- Remove the trailing assistant message with unresponded `tool_calls` from `conversationHistory`

### Part C — Safety net in `chat_once`

**`agents.py`**: Add `_strip_orphaned_tool_calls()` method called in `chat_once()` after `_dicts_to_messages()` conversion, before graph invocation. Removes any trailing `AIMessage` with `tool_calls` that have no corresponding `ToolMessage` responses.

## Files Changed

| File | Change |
|------|--------|
| `agents.py` | Add `_strip_orphaned_tool_calls()`, call it in `chat_once()` |
| `tui.py` | Extend `action_stop_agent()`, add `_clean_history_after_stop()` |
| `chat/templates/chat/index.html` | Extend `controlAgent()`, add `dismissPendingApprovals()`, `cleanHistoryAfterStop()` |
