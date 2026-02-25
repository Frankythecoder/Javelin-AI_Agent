# Model Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Route user requests to GPT-4.1 (heavy tasks) or GPT-4.1-mini (light tasks) via an LLM-based classifier node in LangGraph.

**Architecture:** A new `classify_task` node at the start of the LangGraph uses GPT-4.1-mini to classify each user message. The existing `call_model` node then selects the appropriate LLM based on the classification stored in `AgentState.task_class`. Both models get the full toolset.

**Tech Stack:** LangChain (ChatOpenAI), LangGraph (StateGraph), OpenAI GPT-4.1 / GPT-4.1-mini

**Design doc:** `docs/plans/2026-02-25-model-routing-design.md`

---

### Task 1: Add `task_class` to AgentState

**Files:**
- Modify: `agents.py:3719-3730` (AgentState TypedDict)

**Step 1: Add the new field**

In `agents.py`, add `task_class: str` to the `AgentState` TypedDict after the existing `execution_path` field:

```python
class AgentState(TypedDict):
    """State for the LangGraph agent execution graph."""
    messages: list
    use_pending: bool
    dry_run_plan: list
    pending_tools: list
    status: str
    response: str
    response_history: list
    stopped: bool
    tools_enabled: bool
    execution_path: list
    task_class: str
```

**Step 2: Verify no syntax errors**

Run: `python -c "import agents; print('OK')"`
Expected: `OK` (no import errors)

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: add task_class field to AgentState for model routing"
```

---

### Task 2: Add light model to Agent.__init__

**Files:**
- Modify: `agents.py:3733-3752` (Agent.__init__)

**Step 1: Update the constructor signature and create both LLMs**

Change `Agent.__init__` to accept a `light_model_name` parameter and create two LLM instances. The exact change is:

Replace the current `__init__` signature (line 3734):
```python
def __init__(self, client, model_name, get_user_message, tools: List[ToolDefinition], max_history: int = 15):
```

With:
```python
def __init__(self, client, model_name, get_user_message, tools: List[ToolDefinition], max_history: int = 15, light_model_name: str = "gpt-4.1-mini"):
```

Then after the existing `self.llm_with_tools` line (line 3752), add the mini model:
```python
        self.llm_with_tools = self.llm.bind_tools(self.langchain_tools)

        # Light model for simple tasks (email, templates, formatting)
        self.llm_mini = ChatOpenAI(
            model=light_model_name,
            api_key=client.api_key,
            request_timeout=30,
        )
        self.llm_mini_with_tools = self.llm_mini.bind_tools(self.langchain_tools)
```

**Step 2: Verify no syntax errors**

Run: `python -c "import agents; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add agents.py
git commit -m "feat: add light model (gpt-4.1-mini) to Agent constructor"
```

---

### Task 3: Add classify_task node and rewire graph

**Files:**
- Modify: `agents.py:3819-4011` (_build_graph method)

**Step 1: Add the classify_task node function**

Inside `_build_graph()`, add the `classify_task` function right after the `agent_self = self` line (line 3821) and before the existing `call_model` function:

```python
        def classify_task(state: AgentState) -> dict:
            """Classify the user's message as heavy or light using the mini model."""
            path = state.get("execution_path", []) + ["classify_task"]

            # If task_class is already set (re-entry after tool execution), skip
            if state.get("task_class"):
                return {"execution_path": path}

            # Extract the latest user message
            user_msg = ""
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_msg = msg.content
                    break

            # No user message (e.g. tool approval continuation) → default heavy
            if not user_msg:
                return {"task_class": "heavy", "execution_path": path}

            try:
                classification = agent_self.llm_mini.invoke([
                    SystemMessage(content=(
                        "Classify this user request into exactly one category. "
                        "Reply with ONLY the word \"heavy\" or \"light\".\n\n"
                        "heavy: multi-step tasks, code generation/editing, debugging, "
                        "file operations, vision/image analysis, tool-heavy workflows, "
                        "complex reasoning, planning, architecture decisions, GitHub "
                        "operations, browser automation, travel booking.\n\n"
                        "light: email/letter drafting, template filling, text formatting, "
                        "simple text generation, document content writing, presentation content."
                    )),
                    HumanMessage(content=user_msg)
                ])
                task_class = classification.content.strip().lower()
                if task_class not in ("heavy", "light"):
                    task_class = "heavy"
            except Exception:
                task_class = "heavy"

            return {"task_class": task_class, "execution_path": path}
```

**Step 2: Update call_model to select LLM based on task_class**

In the existing `call_model` function, replace the line (currently line 3834):
```python
                response = agent_self.llm_with_tools.invoke(state["messages"])
```

With:
```python
                llm = agent_self.llm_with_tools if state.get("task_class", "heavy") == "heavy" else agent_self.llm_mini_with_tools
                response = llm.invoke(state["messages"])
```

**Step 3: Rewire the graph assembly**

In the graph assembly section (starting at line 3991), make these changes:

Replace:
```python
        graph = StateGraph(AgentState)
        graph.add_node("call_model", call_model)
        graph.add_node("collect_dry_run", collect_dry_run)
        graph.add_node("execute_or_hold_tools", execute_or_hold_tools)
        graph.add_node("format_output", format_output)

        graph.set_entry_point("call_model")
        graph.add_conditional_edges("call_model", route_after_model, {
```

With:
```python
        graph = StateGraph(AgentState)
        graph.add_node("classify_task", classify_task)
        graph.add_node("call_model", call_model)
        graph.add_node("collect_dry_run", collect_dry_run)
        graph.add_node("execute_or_hold_tools", execute_or_hold_tools)
        graph.add_node("format_output", format_output)

        graph.set_entry_point("classify_task")
        graph.add_edge("classify_task", "call_model")
        graph.add_conditional_edges("call_model", route_after_model, {
```

Everything after this line stays identical — the conditional edges from `call_model` and `execute_or_hold_tools` are unchanged.

**Step 4: Verify no syntax errors**

Run: `python -c "import agents; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add agents.py
git commit -m "feat: add classify_task LangGraph node for model routing"
```

---

### Task 4: Add task_class to initial state in chat_once and execute_dry_run

**Files:**
- Modify: `agents.py:4066-4077` (chat_once initial_state)
- Modify: `agents.py:4135-4146` (execute_dry_run initial_state)

**Step 1: Update chat_once initial state**

In `chat_once()`, add `task_class` to the `initial_state` dict (after line 4076):

Replace:
```python
            initial_state: AgentState = {
                "messages": messages,
                "use_pending": use_pending,
                "dry_run_plan": [],
                "pending_tools": [],
                "status": "",
                "response": "",
                "response_history": [],
                "stopped": self.control.stopped,
                "tools_enabled": self.control.tools_enabled,
                "execution_path": ["__start__"],
            }
```

With:
```python
            initial_state: AgentState = {
                "messages": messages,
                "use_pending": use_pending,
                "dry_run_plan": [],
                "pending_tools": [],
                "status": "",
                "response": "",
                "response_history": [],
                "stopped": self.control.stopped,
                "tools_enabled": self.control.tools_enabled,
                "execution_path": ["__start__"],
                "task_class": "",
            }
```

**Step 2: Update execute_dry_run initial state**

In `execute_dry_run()`, add `task_class` to its `initial_state` dict similarly:

Replace:
```python
            initial_state: AgentState = {
                "messages": self._trim_messages(messages),
                "use_pending": True,
                "dry_run_plan": [],
                "pending_tools": [],
                "status": "",
                "response": "",
                "response_history": [],
                "stopped": self.control.stopped,
                "tools_enabled": self.control.tools_enabled,
                "execution_path": ["__start__"],
            }
```

With:
```python
            initial_state: AgentState = {
                "messages": self._trim_messages(messages),
                "use_pending": True,
                "dry_run_plan": [],
                "pending_tools": [],
                "status": "",
                "response": "",
                "response_history": [],
                "stopped": self.control.stopped,
                "tools_enabled": self.control.tools_enabled,
                "execution_path": ["__start__"],
                "task_class": "",
            }
```

**Step 3: Verify no syntax errors**

Run: `python -c "import agents; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add agents.py
git commit -m "feat: add task_class to initial state in chat_once and execute_dry_run"
```

---

### Task 5: Update model names in views.py, tui.py, and evals/runner.py

**Files:**
- Modify: `chat/views.py:109-110` (model_name and Agent instantiation)
- Modify: `tui.py:267` (Agent instantiation)
- Modify: `evals/runner.py:80-83` (model_name and Agent instantiation)

**Step 1: Update chat/views.py**

Replace line 109:
```python
model_name = 'gpt-4o'
agent = Agent(client, model_name, get_user_message=None, tools=tools)
```

With:
```python
model_name = 'gpt-4.1'
light_model_name = 'gpt-4.1-mini'
agent = Agent(client, model_name, get_user_message=None, tools=tools, light_model_name=light_model_name)
```

**Step 2: Update tui.py**

Replace line 267:
```python
        self.agent = Agent(client, "gpt-4o", get_user_message=None, tools=ALL_TOOLS)
```

With:
```python
        self.agent = Agent(client, "gpt-4.1", get_user_message=None, tools=ALL_TOOLS, light_model_name="gpt-4.1-mini")
```

**Step 3: Update evals/runner.py**

Replace line 80:
```python
    model_name = 'gpt-4o'
```

With:
```python
    model_name = 'gpt-4.1'
```

And update the Agent instantiation at line 83 to pass `light_model_name`:

Replace:
```python
    agent = Agent(client, model_name, lambda: ("", False), tools)
```

With:
```python
    agent = Agent(client, model_name, lambda: ("", False), tools, light_model_name='gpt-4.1-mini')
```

**Step 4: Verify no syntax errors**

Run: `python -c "import agents; print('OK')"`
Expected: `OK`

**Step 5: Commit**

```bash
git add chat/views.py tui.py evals/runner.py
git commit -m "feat: update model names from gpt-4o to gpt-4.1 with mini routing"
```

---

### Task 6: Manual smoke test

**Step 1: Start the Django server**

Run: `python manage.py runserver`

**Step 2: Test a heavy task**

Send a message like: "Read the file agents.py and tell me how many lines it has"
- Expected: classify_task routes to "heavy", call_model uses GPT-4.1, tools execute normally

**Step 3: Test a light task**

Send a message like: "Draft a professional email to John thanking him for the meeting"
- Expected: classify_task routes to "light", call_model uses GPT-4.1-mini, email text generated

**Step 4: Verify execution path includes classify_task**

Check the API response's `execution_path` field — it should start with `["__start__", "classify_task", "call_model", ...]`

**Step 5: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address smoke test issues in model routing"
```
