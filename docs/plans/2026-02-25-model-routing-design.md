# Model Routing Design: GPT-4.1 / GPT-4.1-mini Task Classification

**Date:** 2026-02-25
**Status:** Approved

## Goal

Route user requests to different OpenAI models based on task complexity:
- **GPT-4.1** for: orchestration, multi-step reasoning, code generation/editing, vision + tool integration
- **GPT-4.1-mini** (configurable, swappable to GPT-5-mini) for: email/text generation, template editing, formatting tasks

Both models retain full access to all 40+ tools. The routing is purely a cost/speed optimization.

## Approach: LLM-Based Classifier Node in LangGraph

A new `classify_task` node at the start of the LangGraph uses GPT-4.1-mini to classify each user message as `"heavy"` or `"light"`. The `call_model` node then invokes the appropriate LLM.

## Design

### 1. AgentState Change

New field:
```python
task_class: str  # "heavy" or "light"
```

### 2. Agent.__init__ Changes

- New optional parameter: `light_model_name` (default `"gpt-4.1-mini"`)
- Creates two LLM instances:
  - `self.llm` / `self.llm_with_tools` using primary model (GPT-4.1)
  - `self.llm_mini` / `self.llm_mini_with_tools` using light model
- Both LLMs get the same tool bindings

### 3. New classify_task Graph Node

- Extracts the latest user message from state
- Makes a single GPT-4.1-mini call with a classification prompt
- Returns `task_class: "heavy"` or `"light"`
- On error or ambiguity, defaults to `"heavy"`
- On re-entry (tool execution loop), no re-classification needed — task_class persists in state

### 4. call_model Changes

Reads `state["task_class"]` to select the LLM:
```python
llm = self.llm_with_tools if state.get("task_class", "heavy") == "heavy" else self.llm_mini_with_tools
```

### 5. Graph Topology

**Before:**
```
[call_model] -> route_after_model -> {format_output, collect_dry_run, execute_or_hold_tools}
```

**After:**
```
[classify_task] -> [call_model] -> route_after_model -> {format_output, collect_dry_run, execute_or_hold_tools}
```

- `classify_task` is the new entry point
- Unconditional edge from `classify_task` to `call_model`
- All other edges unchanged

### 6. Views & TUI Changes

- `chat/views.py`: model_name changes from `'gpt-4o'` to `'gpt-4.1'`, passes `light_model_name='gpt-4.1-mini'`
- `tui.py`: same model name changes

### 7. Error Handling

- If classifier LLM call fails, default to `task_class="heavy"` (never block the user)
- `_generate_plan_summary` stays on GPT-4.1 (plan summarization is heavy reasoning)

## Files Changed

1. `agents.py` — AgentState, Agent.__init__, _build_graph, call_model
2. `chat/views.py` — model_name, Agent instantiation
3. `tui.py` — model_name, Agent instantiation

## What Does NOT Change

- All 40+ tool definitions
- Approval system (dry-run + per-tool)
- Prompt injection detection
- Message trimming
- System instruction
- Django URL routing
- Frontend JavaScript
- Database models
