# Ctrl+C Cancellation Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix Ctrl+C so it immediately stops agent execution during plan approval and prevents corrupted message history on resume.

**Architecture:** Two-layer fix: (1) immediate client-side cleanup in TUI and web UI when stop is triggered during approval, (2) server-side safety net in `chat_once` that strips orphaned `AIMessage` entries with unresponded `tool_calls` before calling the LLM.

**Tech Stack:** Python (LangChain messages), Textual TUI framework, Django + vanilla JS web UI.

---

### Task 1: Add `_strip_orphaned_tool_calls` safety net to `agents.py`

**Files:**
- Modify: `agents.py:4043-4050` (insert call in `chat_once`)
- Modify: `agents.py` (add new method near `_dicts_to_messages` around line 4310)

**Step 1: Write the `_strip_orphaned_tool_calls` method**

Add this method to the `Agent` class, right after `_dicts_to_messages` (after line 4310):

```python
def _strip_orphaned_tool_calls(self, messages: List[BaseMessage]) -> List[BaseMessage]:
    """Remove trailing AIMessage with tool_calls that have no matching ToolMessages.

    This happens when execution is stopped during plan approval — the
    AIMessage with tool_calls is saved to history but no ToolMessages
    were ever appended.  OpenAI rejects such sequences, so we strip
    them before the next LLM call.
    """
    if not messages:
        return messages

    # Walk backwards to find the last AIMessage with tool_calls
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if isinstance(msg, AIMessage) and msg.tool_calls:
            # Check if ALL tool_calls have matching ToolMessages after this index
            tool_call_ids = {tc["id"] for tc in msg.tool_calls}
            responded_ids = {
                m.tool_call_id for m in messages[i + 1:]
                if isinstance(m, ToolMessage)
            }
            if not tool_call_ids.issubset(responded_ids):
                # Orphaned — remove this AIMessage
                return messages[:i] + messages[i + 1:]
            # Found a complete AIMessage with tool_calls — history is valid
            break
        # Stop searching at first non-tool, non-AI message going backwards
        if not isinstance(msg, ToolMessage):
            break

    return messages
```

**Step 2: Call `_strip_orphaned_tool_calls` in `chat_once`**

In `chat_once` (line 4043-4050), insert the call right after the history-to-messages conversion loop and before `_detect_interrupted_task`. Change this section:

```python
            # Build LangChain message list
            messages = [SystemMessage(content=self.system_instruction)]
            if conversation_history:
                for lc_msg in self._dicts_to_messages(conversation_history):
                    if isinstance(lc_msg, SystemMessage):
                        continue
                    messages.append(lc_msg)

            # Detect interrupted task and inject context if user wants to continue
```

To:

```python
            # Build LangChain message list
            messages = [SystemMessage(content=self.system_instruction)]
            if conversation_history:
                for lc_msg in self._dicts_to_messages(conversation_history):
                    if isinstance(lc_msg, SystemMessage):
                        continue
                    messages.append(lc_msg)

            # Strip orphaned tool_calls left by interrupted plan approval
            messages = self._strip_orphaned_tool_calls(messages)

            # Detect interrupted task and inject context if user wants to continue
```

**Step 3: Verify manually**

Run: `python -c "from agents import Agent; print('Import OK')"`
Expected: `Import OK` (no syntax errors)

**Step 4: Commit**

```bash
git add agents.py
git commit -m "fix: add safety net to strip orphaned tool_calls from history in chat_once"
```

---

### Task 2: Extend TUI `action_stop_agent` to dismiss approval and clean history

**Files:**
- Modify: `tui.py:687-692` (extend `action_stop_agent`)
- Modify: `tui.py` (add `_clean_history_after_stop` helper)

**Step 1: Add `_clean_history_after_stop` helper**

Add this method to the `AgentChat` class, right after `action_stop_agent` (after line 692):

```python
def _clean_history_after_stop(self):
    """Remove the trailing assistant message with orphaned tool_calls.

    When stop is triggered during plan/tool approval, the conversation
    history contains an AIMessage with tool_calls but no matching tool
    responses.  Strip it so the next chat_once call has valid history.
    """
    if not self.conversation_history:
        return
    # Walk backwards — find the last assistant message with tool_calls
    for i in range(len(self.conversation_history) - 1, -1, -1):
        msg = self.conversation_history[i]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            # Check for matching tool responses after this index
            tool_call_ids = {tc["id"] for tc in msg["tool_calls"]}
            responded_ids = {
                m["tool_call_id"] for m in self.conversation_history[i + 1:]
                if m.get("role") == "tool"
            }
            if not tool_call_ids.issubset(responded_ids):
                self.conversation_history = self.conversation_history[:i] + self.conversation_history[i + 1:]
                return
            break
        if msg.get("role") != "tool":
            break
```

**Step 2: Extend `action_stop_agent`**

Replace the existing `action_stop_agent` (lines 687-692):

```python
    def action_stop_agent(self):
        if self.agent:
            self.agent.control.stop()
        log = self.query_one("#chat-log", RichLog)
        log.write("[bold red]Agent execution stopped.[/]")
        self._update_header("Stopped")
```

With:

```python
    def action_stop_agent(self):
        if self.agent:
            self.agent.control.stop()

        # Dismiss any pending approval and clean orphaned history
        if self._awaiting_approval:
            self._awaiting_approval = False
            self._approval_type = None
            self._pending_plan = []
            self._pending_tools = []
            self._pending_history = []
            self._clean_history_after_stop()

        log = self.query_one("#chat-log", RichLog)
        log.write("[bold red]Agent execution stopped.[/]")
        self._update_header("Stopped")
```

**Step 3: Verify manually**

Run: `python -c "from tui import AgentChat; print('Import OK')"`
Expected: `Import OK` (no syntax errors)

**Step 4: Commit**

```bash
git add tui.py
git commit -m "fix: TUI stop immediately dismisses plan approval and cleans history"
```

---

### Task 3: Extend web UI stop to dismiss approval and clean history

**Files:**
- Modify: `chat/templates/chat/index.html` (extend `controlAgent` function, add two new JS functions)

**Step 1: Add `cleanHistoryAfterStop` JS function**

Add this function right after the existing `controlAgent` function (after line 1122):

```javascript
function cleanHistoryAfterStop() {
    // Walk backwards — find the last assistant message with orphaned tool_calls
    for (let i = conversationHistory.length - 1; i >= 0; i--) {
        const msg = conversationHistory[i];
        if (msg.role === 'assistant' && msg.tool_calls && msg.tool_calls.length > 0) {
            // Check for matching tool responses after this index
            const toolCallIds = new Set(msg.tool_calls.map(tc => tc.id));
            const respondedIds = new Set();
            for (let j = i + 1; j < conversationHistory.length; j++) {
                if (conversationHistory[j].role === 'tool') {
                    respondedIds.add(conversationHistory[j].tool_call_id);
                }
            }
            const allResponded = [...toolCallIds].every(id => respondedIds.has(id));
            if (!allResponded) {
                conversationHistory.splice(i, 1);
                return;
            }
            break;
        }
        if (msg.role !== 'tool') {
            break;
        }
    }
}
```

**Step 2: Add `dismissPendingApprovals` JS function**

Add this function right after `cleanHistoryAfterStop`:

```javascript
function dismissPendingApprovals() {
    // Remove all plan approval and tool approval button groups from the DOM
    document.querySelectorAll('.btn-approve, .btn-deny').forEach(btn => {
        const card = btn.closest('.tool-card');
        if (card) {
            card.innerHTML = '<div style="text-align:center;color:var(--text-muted);font-size:0.8rem;padding:0.5rem;">Stopped by user.</div>';
        }
    });
}
```

**Step 3: Extend `controlAgent` to call these on stop**

Replace the existing `controlAgent` function (lines 1106-1122):

```javascript
async function controlAgent(action) {
    try {
        const res = await fetch('/api/agent/control/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });

        const data = await res.json();
        if (data.message) {
            appendMessage('agent', data.message);
        }
    } catch (err) {
        appendMessage('agent', '⚠️ Failed to control agent.');
        console.error(err);
    }
}
```

With:

```javascript
async function controlAgent(action) {
    try {
        const res = await fetch('/api/agent/control/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });

        const data = await res.json();
        if (data.message) {
            appendMessage('agent', data.message);
        }

        if (action === 'stop') {
            dismissPendingApprovals();
            cleanHistoryAfterStop();
        }
    } catch (err) {
        appendMessage('agent', '⚠️ Failed to control agent.');
        console.error(err);
    }
}
```

**Step 4: Verify manually**

Open the web UI in a browser, open DevTools console, confirm no JS errors on page load.

**Step 5: Commit**

```bash
git add chat/templates/chat/index.html
git commit -m "fix: web UI stop dismisses plan approval and cleans conversation history"
```

---

### Task 4: End-to-end manual verification

**Step 1: TUI test**

1. Start the TUI: `python tui.py`
2. Send a message that triggers a plan (e.g., "Create a new file called test.txt with hello world")
3. When the plan preview appears, press Ctrl+C
4. Verify: "Agent execution stopped." appears immediately, plan approval prompt is dismissed
5. Type "continue" or any new message
6. Verify: No error 400, agent responds normally

**Step 2: Web UI test**

1. Start the Django server: `python manage.py runserver`
2. Open browser to `http://localhost:8000/`
3. Send a message that triggers a plan
4. When the plan preview appears, click Stop
5. Verify: Plan approval buttons are replaced with "Stopped by user.", stop message appears
6. Type a new message
7. Verify: No error 400, agent responds normally

**Step 3: Regression test — normal approval flow**

1. Send a message that triggers a plan
2. Approve the plan with 'y' (TUI) or click Approve (web UI)
3. Verify: Plan executes normally, no breakage

**Step 4: Commit all changes together (if not already committed per-task)**

```bash
git add agents.py tui.py chat/templates/chat/index.html
git commit -m "fix: ctrl+c immediately stops agent and prevents corrupted history on resume"
```
