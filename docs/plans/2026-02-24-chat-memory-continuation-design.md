# Chat Memory & Continuation Design

**Date:** 2026-02-24
**Status:** Approved

## Problem

When loading a previous chat session with `javelin --load`, the agent has three gaps:

1. **History trimming loses context** — After 15+ messages, older messages are silently dropped. The LLM loses knowledge of earlier conversation.
2. **No continue detection** — If a task was interrupted (denied tools, errors, canceled execution), the agent doesn't recognize this and can't resume automatically.
3. **No conversation memory** — Trimmed messages are gone forever with no summary preserved.

## Approach: Hybrid

- **Rule-based continue detection** — Pattern-match the last messages for known interruption signals (fast, deterministic, no extra LLM call).
- **LLM-generated summaries** — When messages are trimmed, use the LLM to summarize dropped messages and insert the summary inline (smart, context-aware).

## Design

### 1. Conversation Summary (Memory)

Modify `_trim_messages()` in `agents.py`:

- When messages exceed `max_history` (15) and trimming is needed, collect the messages about to be dropped.
- Call the LLM with a summarization prompt: "Summarize this conversation so far in 3-5 bullet points, focusing on: what the user asked for, what was accomplished, what files/paths were involved, and any unfinished work."
- Insert the summary as a `SystemMessage` right after the system prompt, prefixed with `[Conversation context from earlier messages]`.
- Cache the summary in `self._conversation_summary` so repeated trims extend the existing summary rather than re-summarizing.
- Summary target: ~200 tokens (3-5 bullet points).
- Only triggers when messages are actually being trimmed.

### 2. Continue Detection

New method `_detect_interrupted_task(messages, user_message)` in `agents.py`:

Scan the last 5 messages in history for interruption patterns:

| Pattern | Signal |
|---------|--------|
| Assistant has `tool_calls` with no matching tool responses | Mid-execution interruption |
| Last tool message contains "denied" / "user has denied" | User denied an action |
| Last assistant message has error-like content | Task failed |
| History contains unapproved `dry_run_plan` | Dry-run abandoned |

If the user's message matches a continue intent ("continue", "go on", "resume", "keep going", "try again", "retry", or similar short phrases), inject a context message:

```
[System note: The previous task was interrupted. Context: {description}.
The user wants to continue. Resume the task from where it left off.]
```

Injected as a `HumanMessage` before the user's actual message. If the user sends a non-continue message, no injection — they're starting a new topic.

### 3. Integration

**Only `agents.py` is modified.** No changes to `tui.py`, `views.py`, models, or any other file.

Updated `chat_once()` flow:

```
chat_once(conversation_history, message, use_pending)
  1. Build messages: [SystemMessage] + convert history
  2. _detect_interrupted_task(messages, message) → inject context if needed
  3. Add user's HumanMessage
  4. _trim_messages() → summarize dropped messages, insert summary
  5. Invoke LangGraph (unchanged)
  6. Return result (unchanged)
```

**New instance variables:**
- `self._conversation_summary: str | None`

**New methods:**
- `_detect_interrupted_task(messages, user_message) -> str | None`
- `_summarize_messages(messages) -> str`

**Modified methods:**
- `_trim_messages()` — now calls `_summarize_messages()` when trimming

**Unchanged:**
- TUI load/save, web API, LangGraph graph, tool definitions, approval flow, session format, message conversion functions.
