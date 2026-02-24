# Network Failure Timeout Design

**Date:** 2026-02-24
**Status:** Approved

## Problem

When WiFi/internet drops mid-task, `ChatOpenAI.invoke()` hangs indefinitely because no `request_timeout` is set. The existing error handling in `call_model` (agents.py:3835) correctly catches exceptions and returns an error status with a failure-marked execution path, but no exception is ever raised — the call just blocks forever.

## Solution

Add `request_timeout=30` to the `ChatOpenAI` constructor at agents.py:3747.

### Change

```python
# Before
self.llm = ChatOpenAI(
    model=model_name,
    api_key=client.api_key,
)

# After
self.llm = ChatOpenAI(
    model=model_name,
    api_key=client.api_key,
    request_timeout=30,
)
```

### Why This Works

1. `request_timeout=30` sets the underlying `httpx` HTTP timeout to 30 seconds.
2. When WiFi is off, after 30s, `httpx` raises a timeout/connection error.
3. The existing `except Exception` in `call_model` (line 3835) catches it.
4. It returns `status: "error"` with `"call_model X"` in the execution path.
5. The frontend's `handleResponse` displays the error with a warning icon and renders the execution path graph with red-highlighted failure nodes.

### What Does NOT Change

- No logic changes in any node, routing, or frontend.
- No new error types or error handling code.
- All 6 other `.invoke()` calls (lines 4193, 4227, 4392, 4536, 4675) also benefit since they use `self.llm` or `self.llm_with_tools` (bound from `self.llm`).

## Decisions

- **Timeout duration:** 30 seconds (fast enough to detect failure, patient enough to avoid false positives)
- **Retry:** None. If the network is down, retrying won't help.
- **Approach:** Built-in `request_timeout` parameter over custom threading wrappers or global graph timeouts.

## Scope

One parameter added to one line. No other changes.
