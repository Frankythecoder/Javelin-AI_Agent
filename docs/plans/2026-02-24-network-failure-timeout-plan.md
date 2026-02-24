# Network Failure Timeout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make LLM calls fail with an error message and failure-point graph after 30 seconds when the network is down, instead of hanging forever.

**Architecture:** Add `request_timeout=30` to the `ChatOpenAI` constructor. The existing error handling in graph nodes already catches exceptions and returns error status with execution path. No other changes needed.

**Tech Stack:** LangChain (`langchain_openai.ChatOpenAI`), LangGraph, Django

---

### Task 1: Add request_timeout to ChatOpenAI

**Files:**
- Modify: `agents.py:3747-3750`

**Step 1: Add the timeout parameter**

In `agents.py`, find the `ChatOpenAI` constructor (line 3747) and add `request_timeout=30`:

```python
# Current code (line 3747-3750):
self.llm = ChatOpenAI(
    model=model_name,
    api_key=client.api_key,
)

# Change to:
self.llm = ChatOpenAI(
    model=model_name,
    api_key=client.api_key,
    request_timeout=30,
)
```

**Step 2: Verify the server starts without errors**

Run: `python manage.py check`
Expected: `System check identified no issues.`

**Step 3: Verify with /test-error command**

1. Start the dev server: `python manage.py runserver`
2. Open the chat UI in browser
3. Type `/test-error call_model` in the chat
4. Expected: Error message appears with `call_model ✗` in the execution path graph (red node). This confirms the existing error handling pipeline still works.

**Step 4: Manual WiFi test**

1. Send a message to the agent (e.g., "Hello")
2. While it says "Executing...", turn off WiFi
3. Expected: Within ~30 seconds, the UI shows a failure message like `LLM call failed at **call_model**: <timeout/connection error>` and the execution path shows `call_model ✗` with a red node
4. Turn WiFi back on

**Step 5: Commit**

```bash
git add agents.py
git commit -m "fix: add 30s request timeout to ChatOpenAI to prevent hanging on network loss"
```

---

### Verification Checklist

- [ ] Server starts without errors (`python manage.py check`)
- [ ] `/test-error call_model` still shows error with failure graph
- [ ] WiFi-off test: agent fails within ~30s with error message and failure-point graph
- [ ] WiFi-on test: normal operation unaffected (agent responds normally)
