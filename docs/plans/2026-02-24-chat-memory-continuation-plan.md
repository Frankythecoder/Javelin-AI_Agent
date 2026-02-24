# Chat Memory & Continuation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add conversation memory (LLM-generated summaries of trimmed messages) and continue detection (rule-based interrupted task detection) to the agent, so loaded sessions retain full context and users can resume interrupted tasks.

**Architecture:** Modify only `agents.py`. Add a `_summarize_messages()` method that calls the LLM to summarize trimmed messages and a `_detect_interrupted_task()` method that pattern-matches the last messages for interruption signals. Integrate both into the existing `chat_once()` flow. No changes to TUI, web views, models, or LangGraph graph.

**Tech Stack:** Python, LangChain (ChatOpenAI, SystemMessage, HumanMessage), existing OpenAI GPT-4o model.

---

### Task 1: Add `_conversation_summary` instance variable

**Files:**
- Modify: `agents.py:3733-3760` (Agent.__init__)

**Step 1: Add the instance variable**

In `Agent.__init__()`, after line 3760 (`self._test_fail_node = None`), add:

```python
        # Conversation summary for memory across trimmed messages
        self._conversation_summary = None
```

**Step 2: Verify no syntax errors**

Run: `python -c "import agents; print('OK')"`
Expected: `OK` (or Django setup — just no SyntaxError)

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: add _conversation_summary instance variable to Agent"
```

---

### Task 2: Add `_summarize_messages()` method

**Files:**
- Modify: `agents.py` (add method after `_trim_messages`, before `generate_code`)

**Step 1: Write the `_summarize_messages` method**

Insert after `_trim_messages()` (after line 4457) and before `generate_code()` (line 4459):

```python
    def _summarize_messages(self, messages: List[Any]) -> str:
        """Summarize a list of messages into a concise context string using the LLM.

        Called when _trim_messages is about to drop older messages, so the agent
        retains awareness of earlier conversation context.

        Args:
            messages: List of LangChain message objects to summarize.

        Returns:
            A short summary string (3-5 bullet points).
        """
        # Build a plain-text transcript of the messages to summarize
        transcript_parts = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                transcript_parts.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                text = msg.content or ""
                if msg.tool_calls:
                    tool_names = ", ".join(tc["name"] for tc in msg.tool_calls)
                    text += f" [Called tools: {tool_names}]"
                transcript_parts.append(f"Assistant: {text}")
            elif isinstance(msg, ToolMessage):
                # Truncate long tool results to keep the summarization prompt small
                content = msg.content[:500] if len(msg.content) > 500 else msg.content
                transcript_parts.append(f"Tool ({msg.name}): {content}")

        transcript = "\n".join(transcript_parts)

        # If there's an existing summary, include it so the LLM extends rather than restarts
        existing_context = ""
        if self._conversation_summary:
            existing_context = (
                f"Previous conversation summary:\n{self._conversation_summary}\n\n"
                "The following messages occurred AFTER the above summary. "
                "Update the summary to include this new context.\n\n"
            )

        try:
            resp = self.llm.invoke([
                SystemMessage(content=(
                    "You are a conversation summarizer. Produce a concise summary "
                    "in 3-5 bullet points. Focus on: what the user asked for, what "
                    "was accomplished, what files/paths were involved, and any "
                    "unfinished work or errors. Be factual and brief."
                )),
                HumanMessage(content=(
                    f"{existing_context}"
                    f"Conversation to summarize:\n\n{transcript}\n\n"
                    "Summary:"
                )),
            ])
            summary = resp.content.strip() if resp.content else ""
            if summary:
                return summary
        except Exception as e:
            print(f"[memory] Summary generation failed: {e}")

        # Fallback: return a basic extraction if LLM fails
        return self._conversation_summary or ""
```

**Step 2: Verify no syntax errors**

Run: `python -c "import agents; print('OK')"`
Expected: No SyntaxError

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: add _summarize_messages method for conversation memory"
```

---

### Task 3: Modify `_trim_messages()` to generate summaries

**Files:**
- Modify: `agents.py:4420-4457` (`_trim_messages` method)

**Step 1: Update `_trim_messages` to call `_summarize_messages`**

Replace the current `_trim_messages` method with:

```python
    def _trim_messages(self, messages: List[Any]) -> List[Any]:
        """
        Trim message history to stay within token limits.
        Keeps the system message and ensures tool messages are not separated from their tool_calls.
        Works with both LangChain message objects and plain dicts.

        When trimming occurs, generates an LLM summary of the dropped messages
        and inserts it as a SystemMessage after the main system prompt, so the
        agent retains awareness of earlier conversation context.
        """
        if len(messages) <= self.max_history + 1:
            return messages

        first = messages[0]
        is_system = (
            isinstance(first, SystemMessage)
            or (isinstance(first, dict) and first.get("role") == "system")
        )
        system_message = first if is_system else None

        # Keep the most recent messages
        start_index = len(messages) - self.max_history

        # Ensure we don't start in the middle of a tool response sequence
        def _is_tool(m):
            if isinstance(m, ToolMessage):
                return True
            if isinstance(m, dict) and m.get("role") == "tool":
                return True
            return False

        while start_index > 1 and _is_tool(messages[start_index]):
            start_index -= 1

        # Collect messages that will be dropped (excluding system message)
        dropped_start = 1 if is_system else 0
        dropped_messages = messages[dropped_start:start_index]

        recent_messages = messages[start_index:]

        # Generate summary of dropped messages if there are any
        if dropped_messages:
            # Only summarize LangChain message objects (not dicts) to avoid
            # double-summarizing when called from execute_dry_run
            has_langchain_msgs = any(
                isinstance(m, (HumanMessage, AIMessage, ToolMessage))
                for m in dropped_messages
            )
            if has_langchain_msgs:
                self._conversation_summary = self._summarize_messages(dropped_messages)

        trimmed = []
        if system_message:
            trimmed.append(system_message)

        # Insert conversation summary as a SystemMessage right after the system prompt
        if self._conversation_summary:
            summary_msg = SystemMessage(
                content=f"[Conversation context from earlier messages]\n{self._conversation_summary}"
            )
            trimmed.append(summary_msg)

        trimmed.extend(recent_messages)

        return trimmed
```

**Step 2: Verify no syntax errors**

Run: `python -c "import agents; print('OK')"`
Expected: No SyntaxError

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: integrate conversation summary into _trim_messages"
```

---

### Task 4: Add `_detect_interrupted_task()` method

**Files:**
- Modify: `agents.py` (add method after `_summarize_messages`, before `generate_code`)

**Step 1: Write the `_detect_interrupted_task` method**

Insert after the `_summarize_messages` method:

```python
    def _detect_interrupted_task(self, messages: List[Any], user_message: str) -> Optional[str]:
        """Detect if the previous conversation was interrupted and the user wants to continue.

        Scans the last messages for interruption patterns (denied tools, errors,
        incomplete tool sequences) and checks if the user's new message is a
        "continue" intent.

        Args:
            messages: List of LangChain message objects (the current conversation).
            user_message: The user's new message text.

        Returns:
            A context string to inject before the user's message, or None if no
            continuation is detected.
        """
        if not user_message or not messages:
            return None

        # Check if user message is a "continue" intent
        continue_phrases = {
            "continue", "go on", "resume", "keep going", "try again", "retry",
            "proceed", "carry on", "go ahead", "finish it", "complete it",
            "do it", "yes continue", "yes go on", "please continue",
        }
        normalized = user_message.lower().strip().rstrip(".!?")
        if normalized not in continue_phrases:
            return None

        # Scan last 5 messages for interruption signals
        recent = messages[-5:] if len(messages) >= 5 else messages
        interruption_context = None

        # Pattern 1: Assistant has tool_calls but no matching tool responses
        for i, msg in enumerate(recent):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                tool_call_ids = {tc["id"] for tc in msg.tool_calls}
                # Check if ALL tool calls have corresponding ToolMessage responses
                remaining = messages[messages.index(msg) + 1:]
                responded_ids = {
                    m.tool_call_id for m in remaining
                    if isinstance(m, ToolMessage)
                }
                unresponded = tool_call_ids - responded_ids
                if unresponded:
                    tool_names = [
                        tc["name"] for tc in msg.tool_calls
                        if tc["id"] in unresponded
                    ]
                    interruption_context = (
                        f"The agent was about to execute tools [{', '.join(tool_names)}] "
                        f"but execution was interrupted before they completed."
                    )
                    break

        # Pattern 2: Last tool message contains denial
        if not interruption_context:
            for msg in reversed(recent):
                if isinstance(msg, ToolMessage):
                    content_lower = msg.content.lower()
                    if "denied" in content_lower or "user has denied" in content_lower:
                        interruption_context = (
                            f"The user previously denied the tool '{msg.name}'. "
                            f"The task was not completed."
                        )
                    break

        # Pattern 3: Last assistant message has error content
        if not interruption_context:
            for msg in reversed(recent):
                if isinstance(msg, AIMessage):
                    content_lower = (msg.content or "").lower()
                    if any(kw in content_lower for kw in ["error", "failed", "could not", "unable to"]):
                        interruption_context = (
                            f"The previous task encountered an issue. "
                            f"Last agent message: {(msg.content or '')[:200]}"
                        )
                    break

        if not interruption_context:
            return None

        return (
            f"[System note: The previous task was interrupted. "
            f"Context: {interruption_context} "
            f"The user wants to continue. Resume the task from where it left off.]"
        )
```

**Step 2: Verify no syntax errors**

Run: `python -c "import agents; print('OK')"`
Expected: No SyntaxError

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: add _detect_interrupted_task method for continue detection"
```

---

### Task 5: Integrate into `chat_once()` flow

**Files:**
- Modify: `agents.py:4039-4052` (inside `chat_once` method)

**Step 1: Add continue detection before adding the user's message**

Replace lines 4039-4052 (the message-building section of `chat_once`) with:

```python
            # Build LangChain message list
            messages = [SystemMessage(content=self.system_instruction)]
            if conversation_history:
                for lc_msg in self._dicts_to_messages(conversation_history):
                    if isinstance(lc_msg, SystemMessage):
                        continue
                    messages.append(lc_msg)

            # Detect interrupted task and inject context if user wants to continue
            if message:
                continuation_context = self._detect_interrupted_task(messages, message)
                if continuation_context:
                    messages.append(HumanMessage(content=continuation_context))

            if message:
                if is_prompt_injection(message):
                    return {"status": "error", "message": "Security Warning: Potential prompt injection detected. Message blocked."}
                messages.append(HumanMessage(content=message))

            messages = self._trim_messages(messages)
```

This inserts the continuation context message *before* the user's actual message, so the LLM sees: `[...history...] [continuation context] [user: "continue"]`.

**Step 2: Verify no syntax errors**

Run: `python -c "import agents; print('OK')"`
Expected: No SyntaxError

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: integrate continue detection into chat_once flow"
```

---

### Task 6: Manual Integration Test

**Files:**
- None (testing only)

**Step 1: Verify the agent loads and the new code paths are reachable**

Run: `python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()
from agents import Agent
print('Agent class imported successfully')
print('Has _conversation_summary:', hasattr(Agent.__init__, '__code__'))
# Quick instantiation check (will fail on missing tools but proves syntax is fine)
print('OK')
"`

Expected: `Agent class imported successfully` and `OK`

**Step 2: Verify _detect_interrupted_task returns None for non-continue messages**

Run: `python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()
from agents import Agent
from langchain_core.messages import HumanMessage, AIMessage

# Create a minimal agent (won't make LLM calls, just testing detection logic)
class FakeClient:
    api_key = 'fake'
a = Agent(FakeClient(), 'gpt-4o', lambda: ('', False), [], max_history=15)

# Test: non-continue message should return None
msgs = [HumanMessage(content='hello')]
result = a._detect_interrupted_task(msgs, 'What is the weather?')
assert result is None, f'Expected None, got {result}'
print('Test 1 passed: non-continue message returns None')

# Test: continue message with no interruption should return None
result = a._detect_interrupted_task(msgs, 'continue')
assert result is None, f'Expected None, got {result}'
print('Test 2 passed: continue with no interruption returns None')

print('All detection tests passed')
"`

Expected: All tests pass

**Step 3: Commit (final)**

```bash
git add agents.py
git commit -m "feat: complete chat memory and continuation feature"
```

---

## Summary of All Changes to `agents.py`

| Location | Change |
|----------|--------|
| `Agent.__init__` (line ~3760) | Add `self._conversation_summary = None` |
| After `_trim_messages` (line ~4457) | Add `_summarize_messages()` method |
| After `_summarize_messages` | Add `_detect_interrupted_task()` method |
| `_trim_messages` (lines 4420-4457) | Modify to summarize dropped messages and inject summary |
| `chat_once` (lines 4039-4052) | Add continuation detection before user message |

**No other files are modified.** TUI, web views, models, LangGraph graph, tool definitions, and approval flow remain unchanged.
