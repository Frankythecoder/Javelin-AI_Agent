# AI Agent — System Architecture

A part-by-part explanation of the entire project: every layer, workflow, tool, data structure, external integration, and control-flow decision. This is the document to hand to a new contributor (or an interviewer) that leaves nothing important out.

---

## Table of Contents

1. [Executive Overview](#1-executive-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Repository Layout](#3-repository-layout)
4. [Layer 1 — Presentation (Frontends)](#4-layer-1--presentation-frontends)
5. [Layer 2 — Django Web / API Layer](#5-layer-2--django-web--api-layer)
6. [Layer 3 — Agent Core (`agents/core.py`)](#6-layer-3--agent-core-agentscorepy)
7. [Layer 4 — LangGraph State Machine](#7-layer-4--langgraph-state-machine)
8. [Layer 5 — Control & Safety Subsystem](#8-layer-5--control--safety-subsystem)
9. [Layer 6 — Tool System](#9-layer-6--tool-system)
10. [Layer 7 — MCP Integration](#10-layer-7--mcp-integration)
11. [Layer 8 — EATP: Experience-Augmented Tool Planning](#11-layer-8--eatp-experience-augmented-tool-planning)
12. [Layer 9 — Persistence](#12-layer-9--persistence)
13. [Layer 10 — Evaluation Framework](#13-layer-10--evaluation-framework)
14. [Layer 11 — Testing](#14-layer-11--testing)
15. [End-to-End Workflows](#15-end-to-end-workflows)
16. [Message Lifecycle & Format Conversions](#16-message-lifecycle--format-conversions)
17. [Context Management](#17-context-management)
18. [Capabilities Matrix](#18-capabilities-matrix)
19. [External Dependencies & Configuration](#19-external-dependencies--configuration)
20. [Concurrency Model](#20-concurrency-model)
21. [Extension Points](#21-extension-points)

---

## 1. Executive Overview

**What it is:** A local-first, tool-using AI agent that combines an OpenAI-powered LLM (gpt-6-sol heavy + gpt-5.6-terra light) with a LangGraph-orchestrated state machine, 40+ specialized tools, human-in-the-loop safety gates, and a novel **Experience-Augmented Tool Planning (EATP)** memory system that lets the agent learn from past executions without fine-tuning.

**Three faces:**
- **Web UI** (Django + vanilla JS) at `http://localhost:8000/`
- **TUI** (Textual) via `python tui.py`
- **CLI** (interactive) via `python -m agents.core`

**Three research narratives it supports:**
1. **Safety** — Dry-run + per-tool approval + kill switch + prompt-injection defense as a first-class agent architecture.
2. **Memory** — EATP as RAG over the agent's own episodic memory, re-ranked to prioritize user corrections.
3. **Cost-aware routing** — Heavy/light model classification cuts LLM costs on trivial tasks.

---

## 2. High-Level Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION LAYER                            │
│    Web UI (chat/index.html)   │   TUI (tui.py)   │   CLI (core.main)  │
└─────────────────┬─────────────────────┬──────────────────┬───────────┘
                  │                     │                  │
                  ▼                     ▼                  ▼
┌───────────────────────────────────────────────────────────────────────┐
│                      DJANGO WEB / API LAYER                            │
│   chat/views.py  → /api/chat, /api/agent/control, /api/chats, /api/graph│
│   chat/models.py → ToolLog, ChatSession, Booking (SQLite)              │
└───────────────────────────────┬───────────────────────────────────────┘
                                │ Agent.chat_once() / .execute_dry_run()
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                          AGENT CORE                                    │
│  agents/core.py  ── Agent class ── LangGraph StateGraph                │
│                                                                        │
│  [classify_task]→[call_model]→[collect_dry_run | execute_or_hold_tools]│
│                                          │                             │
│                                          └────►[format_output]         │
└──┬─────────────────┬──────────────────┬─────────────────┬────────────┘
   │                 │                  │                 │
   ▼                 ▼                  ▼                 ▼
┌────────┐   ┌────────────────┐  ┌───────────────┐  ┌─────────────────┐
│ CONTROL│   │ TOOL SYSTEM    │  │ MCP SERVERS   │  │ EATP MEMORY     │
│ stop/  │   │ 40+ tools with │  │ GitHub server │  │ ChromaDB store  │
│ kill/  │   │ ToolDefinition │  │ Playwright    │  │ Experience log  │
│ inject │   │ → LangChain    │  │ (stdio/JSON-  │  │ Feedback tool   │
│ check  │   │  StructuredTool│  │  RPC subproc) │  │ Retrieval + RR  │
└────────┘   └────────────────┘  └───────────────┘  └────────┬────────┘
                                                              │
                                                              ▼
                                                     ┌─────────────────┐
                                                     │  ChromaDB       │
                                                     │  (HNSW index)   │
                                                     │  ~/.ai_agent/   │
                                                     └─────────────────┘

┌───────────────────────────────────────────────────────────────────────┐
│                     EVALUATION FRAMEWORK (offline)                     │
│  evals/runner.py, tasks.json, validators.py, mocks.py,                 │
│  metrics.py, compare_phases.py, generate_figures.py                    │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 3. Repository Layout

```
ai_agent/
├── manage.py                          # Django management entrypoint
├── db.sqlite3                          # SQLite: ToolLog, ChatSession, Booking
├── Dockerfile.sandbox                  # (planned) sandbox for run_code
├── requirements.txt
├── pyproject.toml
├── tui.py                              # Textual TUI (35 KB)
├── README.md
│
├── config/                             # Django project
│   ├── settings.py                     # env-var driven config
│   ├── urls.py                         # root URL routing
│   ├── asgi.py / wsgi.py               # deployment entrypoints
│
├── chat/                               # Django app
│   ├── models.py                       # ToolLog, ChatSession, Booking
│   ├── views.py                        # HTTP JSON API
│   ├── urls.py                         # /api/... routes
│   ├── templates/chat/index.html       # Web UI
│   ├── migrations/                     # DB schema history
│   └── management/commands/
│       ├── showlogs.py                 # dump ToolLog rows
│       └── export_logs_csv.py          # CSV export
│
├── agents/                             # Agent package (was one 2400-line file)
│   ├── __init__.py                     # re-exports every public name
│   ├── core.py                         # Agent class, LangGraph, AgentState
│   ├── agent_messages.py               # AgentMessagesMixin: msg conversion, trim, summarize
│   ├── control.py                      # AgentControlState, ToolDefinition, ApprovalAwareTool
│   ├── helpers.py                      # find_file_broadly, prompt-injection regex
│   │
│   ├── file_tools.py                   # 9 tools
│   ├── code_tools.py                   # 4 tools
│   ├── github_tools.py                 # 5 tools (via MCP + REST)
│   ├── email_tools.py                  # Gmail draft + Playwright MCP
│   ├── multimedia_tools.py             # 3 tools (image, video, audio)
│   ├── travel_tools.py                 # 5 tools (Duffel API)
│   ├── document_tools.py               # 4 create tools (PDF/DOCX/XLSX/PPTX)
│   ├── document_rw_tools.py            # 8 read/edit tools
│   ├── feedback_tools.py               # rate_experience (EATP hook)
│   │
│   ├── experience_store.py             # EATP: ChromaDB wrapper + ExperienceRecord
│   ├── experience_logger.py            # EATP: builds records from execution context
│   └── migrate_experiences.py          # EATP: re-embed on model change
│
├── mcp_servers/                        # MCP tool servers (stdio subprocesses)
│   ├── github_server.py                # FastMCP: create_branch/pr/commit
│   └── playwright_server.py            # FastMCP: navigate + screenshot
│
├── evals/                              # Evaluation framework
│   ├── tasks.json                      # 24+ benchmark tasks
│   ├── runner.py                       # 5-mode eval driver
│   ├── validators.py                   # per-task ground-truth checkers
│   ├── mocks.py                        # deterministic API stubs
│   ├── static_fewshot.py               # control condition: fixed examples
│   ├── correction_policy.json          # scripted user denials for Phase B
│   ├── transfer_map.json               # cross-domain transfer test config
│   ├── metrics.py                      # success rate + category breakdown
│   ├── compare_phases.py               # A/B analysis across eval runs
│   ├── generate_figures.py             # matplotlib chart generation
│   ├── seeds/                          # buggy / legacy code inputs
│   └── figures/                        # generated plots
│
├── tests/                              # pytest suite
│   ├── test_experience_store.py
│   ├── test_experience_logger.py
│   ├── test_feedback_tools.py
│   ├── test_eatp_integration.py
│   ├── test_eatp_manual.py
│   ├── test_mcp_navigate.py
│   ├── test_mocks.py
│   ├── test_normalize_url.py
│   ├── test_static_fewshot.py
│   └── test_validators.py
│
├── samples/                            # test media (image, video, java, py)
├── assets/                             # UI assets (logo)
└── .env                                # secrets (git-ignored)
```

---

## 4. Layer 1 — Presentation (Frontends)

Three frontends, one shared `Agent` core.

### 4.1 Web UI (`chat/templates/chat/index.html`)
- Vanilla JavaScript + Bootstrap.
- Posts JSON to `/api/chat/` with fields: `message`, `history`, `status`, `pending_tools`, `dry_run_plan`.
- Renders four response `status` types: `dry_run`, `pending`, `success`, `error`.
- Includes a **Stop** button and **Disable Tools** toggle wired to `/api/agent/control/`.
- Session save/load via `/api/chats/` and `/api/chats/<id>/`.
- Optional **LangGraph visualizer** via `/api/graph/` (renders the Mermaid diagram of the state machine).

### 4.2 TUI (`tui.py`)
- Built with the **Textual** framework — real terminal UI with widgets, input, chat log.
- Bootstraps Django (`django.setup()`) so it can share the same models/settings.
- Uses the same `Agent` class with the same tool list as the Web UI.

### 4.3 CLI (`agents/core.main`)
- Simple `input()` REPL: `python -m agents.core`.
- No approval UI — uses `Agent.run()` which auto-executes tools via `_process_response_simple`.
- Intended for developer scripting.

---

## 5. Layer 2 — Django Web / API Layer

### 5.1 Django Project Layout
- **Project:** `config/` (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`).
- **App:** `chat/` — the only Django app.
- **Settings** (`config/settings.py`): reads all secrets from `.env` via `python-dotenv` + `python-decouple`. SQLite in dev; S3 static storage in prod.
- **URL routing** (`config/urls.py` → `chat/urls.py`).

### 5.2 API Endpoints (`chat/views.py`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Serve `chat/index.html` |
| `/api/chat/` | POST | Main chat endpoint. Dispatches on `status` |
| `/api/agent/control/` | POST | `stop`, `disable_tools`, `enable_tools` |
| `/api/chats/` | GET / POST | List sessions / save session |
| `/api/chats/<id>/` | GET / DELETE | Load / delete session |
| `/api/files/` | GET | Enumerate files in cwd (for UI file browser) |
| `/api/graph/` | GET | Return Mermaid diagram of the LangGraph |
| `/api/test-error/` | POST | Set `_test_fail_node` to simulate node failure |
| `/api/shutdown/` | POST | Kill the dev server (dev-only) |
| `/logo.png` | GET | Serve the Javelin logo |

### 5.3 `chat_api` Dispatch Logic

The main endpoint switches on the `status` field:

```
No status              →  Agent.chat_once(history, message)             # fresh turn
status = "dry_run_approved" →  Agent.execute_dry_run(plan, history)     # plan approved
status = "dry_run_denied"   →  chat_once with denial injected           # replan
status = "approved"    →  execute pending tools then chat_once(use_pending=True)
status = "denied"      →  inject denial then chat_once(use_pending=True)
```

The Agent is instantiated **once at module import** (`agent = Agent(...)`) — meaning the process holds a single stateful agent (including its ExperienceStore and control flags) shared across all HTTP requests. This is why threading and locks matter.

### 5.4 Data Models (`chat/models.py`)

| Model | Fields | Purpose |
|---|---|---|
| **ToolLog** | `tool_name`, `input_args`, `output_result`, `created_at` | Audit trail; one row per tool execution |
| **ChatSession** | `title`, `history` (JSON text), `created_at`, `updated_at` | Persistent conversation storage |
| **Booking** | `booking_ref`, `booking_type`, `duffel_order_id`, `passenger_name`, `total_price`, `status`, `details` (JSON) | Travel booking records |

---

## 6. Layer 3 — Agent Core (`agents/core.py`)

### 6.1 The `AgentState` TypedDict

The state that flows through every LangGraph node:

```python
class AgentState(TypedDict):
    messages: list             # LangChain messages (System/Human/AI/Tool)
    use_pending: bool          # True = per-tool approval mode, False = dry-run mode
    dry_run_plan: list         # collected tool calls awaiting approval
    pending_tools: list        # high-risk tools held for per-tool approval
    status: str                # "" | "success" | "dry_run" | "pending" | "stopped" | "error"
    response: str              # final text for the user
    response_history: list     # frontend-format history (dicts)
    stopped: bool              # snapshot of control.stopped
    tools_enabled: bool        # snapshot of control.tools_enabled
    execution_path: list       # trace of nodes visited (for observability)
    task_class: str            # "heavy" | "light" — routes to gpt-6-sol or gpt-5.6-terra
```

Every node returns a **partial** dict; LangGraph merges it into the running state.

### 6.2 The `Agent` Class

Constructed once in `chat/views.py`:

```python
Agent(
    client,             # OpenAI client (used for API key mostly)
    model_name,         # "gpt-6-sol"        (heavy)
    get_user_message,   # CLI callback, None in web mode
    tools,              # list[ToolDefinition]
    max_history=15,     # conversation trim window
    light_model_name,   # "gpt-5.6-terra"   (light)
)
```

**What `__init__` builds:**

1. `AgentControlState()` — stop/disable flags + `threading.Lock`.
2. Converts each `ToolDefinition` → `ApprovalAwareTool` via `tool_definition_to_langchain`.
3. Two `ChatOpenAI` clients (heavy + light), each with tools bound via `bind_tools`.
4. Backward-compat OpenAI-format tool list (`_convert_tools_to_openai_format`).
5. The compiled LangGraph (`self._graph = self._build_graph()`).
6. `_test_fail_node` hook for failure-injection tests.
7. `_conversation_summary` for rolling context summarization.
8. `ExperienceStore` and `ExperienceLogger` (EATP).
9. Wires the feedback tool to the store via `set_experience_store`.
10. Session-level feedback tracking (`_session_corrections`, `_session_approval_actions`).
11. The 20-rule `system_instruction` — task classification, self-recovery, document rules, GitHub workflow, etc.

### 6.3 The System Instruction (20 Rules)

Notable rules encoded in the system prompt:

- **Rule 3** — always use `check_syntax`, `run_tests`, `lint_code` to catch errors.
- **Rule 10** — simple tasks (< 3 tool calls) execute without asking.
- **Rule 11** — never use the words "Error"/"Exception" in successful summaries (they trigger the eval failure detector).
- **Rule 14** — GitHub operations MUST use MCP tools, never `run_code` + git.
- **Rule 15** — document page count is exact: N pages = N-1 `<!-- PAGE_BREAK -->` markers.
- **Rule 17-18** — task classification (SIMPLE vs COMPLEX) → EXPLORE→CLARIFY→PLAN→EXECUTE phases.
- **Rule 20** — self-recovery protocol: install missing deps, fix errors, try alternatives, escalate only after 3 different approaches.

### 6.4 Public API of `Agent`

| Method | Purpose |
|---|---|
| `chat_once(history, message, use_pending=False)` | Handle one HTTP turn. EATP-augmented, prompt-injection-checked, returns `{status, response, history, ...}` |
| `execute_dry_run(dry_run_plan, history)` | Execute a user-approved plan, log to EATP, re-invoke graph in per-tool mode for follow-ups |
| `run()` | CLI-mode interactive loop |
| `_execute_tool_by_name(name, args)` | Dispatch a tool, check stop/disable flags, log to `ToolLog`, return string |
| `record_correction(text)`, `record_denial(tool, action)` | Feed session-level EATP feedback |
| `clear_session_feedback()` | Reset before a new task (called by eval runner) |
| `generate_code(desc, language, stepwise)` | Standalone code generation with prompt injection guard (defined in mixin) |

### 6.5 `AgentMessagesMixin` (`agents/agent_messages.py`)

The messaging Swiss army knife the Agent inherits from:

| Method | Purpose |
|---|---|
| `_dicts_to_messages(history)` | Frontend dict → LangChain messages |
| `_messages_to_dicts(messages)` | LangChain messages → frontend dicts |
| `_strip_orphaned_tool_calls(msgs)` | Remove `AIMessage.tool_calls` with no matching `ToolMessage` (happens when approval is aborted). OpenAI rejects such histories, so this is essential correctness |
| `_summarize_tool_call(name, args)` | One-line human summary for the dry-run card (40+ tool-specific formatters) |
| `_generate_plan_summary(plan, request)` | LLM-generated 2-4 sentence plain-English plan summary |
| `_trim_messages(msgs)` | Keep last `max_history` messages, preserve system prompt, don't split tool-call/response pairs, generate rolling summary |
| `_summarize_messages(msgs)` | LLM-summarize dropped messages into 3-5 bullets |
| `_detect_interrupted_task(msgs, user_msg)` | Detect "continue"-intent + prior interruption; inject resume context |
| `_convert_tools_to_openai_format()` | Backward-compat |
| `generate_code(desc, lang, stepwise)` | Standalone code generation (with injection guard) |

---

## 7. Layer 4 — LangGraph State Machine

The LangGraph replaces what would otherwise be a `while` loop. Every node is a pure function `(state) → partial_state`.

### 7.1 Nodes

| Node | What it does |
|---|---|
| **`classify_task`** | Uses `llm_mini` to label the message `"heavy"` or `"light"`. Skipped if `task_class` is already set (re-entry after tool execution) |
| **`call_model`** | Invokes the heavy or light LLM (with tools bound) on the current message list. Appends the response to state |
| **`collect_dry_run`** | Builds a `dry_run_plan` from the last AI message's `tool_calls`. Generates a plan summary. Returns `status="dry_run"` and ends |
| **`execute_or_hold_tools`** | Iterates the last AI's `tool_calls`. High-risk tools go to `pending_tools` (returns `status="pending"`); low-risk tools execute immediately via `_execute_tool_by_name` and their results are appended as `ToolMessage`s |
| **`format_output`** | Final normalization. If no status set yet, extracts the last AI message content as `response` with `status="success"` |

### 7.2 Edges

```
START ─► classify_task ─► call_model
                              │
                              ▼ (conditional: route_after_model)
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   format_output       collect_dry_run       execute_or_hold_tools
        │                     │                     │
        │                     ▼                     ▼ (conditional: route_after_tools)
        │                    END              ┌─────┼─────┐
        ▼                                     │     │     │
       END                                    ▼     ▼     ▼
                                        format_out call_model END(pending)
```

**Routing logic:**

`route_after_model` inspects `state.status` and the last message:
- If `status ∈ {stopped, error}` → `format_output`
- If last message is not an `AIMessage` with `tool_calls` → `format_output`
- If `use_pending=True` → `execute_or_hold_tools` (per-tool approval mode)
- Else → `collect_dry_run` (dry-run mode)

`route_after_tools` after `execute_or_hold_tools`:
- If `status ∈ {stopped, error}` → `format_output`
- If any `pending_tools` were collected → `END` (return to user for approval)
- Else all tools ran → `call_model` (continue the ReAct loop)

**Recursion limit:** compiled with `{"recursion_limit": 25}` — hard cap on node executions per invocation.

### 7.3 Failure Injection Hook

`self._test_fail_node = "call_model"` (settable via `/api/test-error/`) makes the next execution of that node raise a synthetic exception. Every node has a try/except that catches this and returns `status="error"` with a labeled `execution_path` so failures are debuggable at node granularity.

---

## 8. Layer 5 — Control & Safety Subsystem

### 8.1 `AgentControlState` (`agents/control.py`)

```python
class AgentControlState:
    stopped: bool = False
    tools_enabled: bool = True
    lock: threading.Lock

    stop()          # with lock: stopped = True
    disable_tools() # with lock: tools_enabled = False
    enable_tools()  # with lock: tools_enabled = True
```

Checked at:
- Top of every LangGraph node (early exit if stopped).
- Beginning of `_execute_tool_by_name` (stop or disable → returns a message, does NOT call the tool).
- Beginning of `chat_once` and `execute_dry_run`.

The lock protects **composite reads-then-writes**; single boolean assignments are atomic under CPython's GIL, but the lock future-proofs the control state for when fields become dicts.

### 8.2 Dry-Run Mode (Default for Fresh Messages)

`chat_once(..., use_pending=False)` → `call_model` proposes tool calls → `collect_dry_run` bundles them → response is:

```json
{
  "status": "dry_run",
  "dry_run_plan": [
    {"id": "call_1", "name": "read_file", "arguments": {...}, "summary": "Read file: notes.txt"}
  ],
  "response": "I will read your notes.txt and summarize its contents.",
  "history": [...]
}
```

Frontend shows a card, user clicks Approve → posts `status="dry_run_approved"` → `execute_dry_run` runs the whole plan.

### 8.3 Per-Tool Approval (Post-Approval Follow-Ups)

After `execute_dry_run`, the graph re-enters with `use_pending=True`. Now `execute_or_hold_tools` splits by `requires_approval`:

- **Low-risk** (read_file, list_files, search_file, recognize_*, most read tools) → execute immediately.
- **High-risk** (delete_file, run_code, rename_file, GitHub writes, playwright_navigate) → return `status="pending"` with `pending_tools=[…]`, user must approve individually.

### 8.4 Kill Switch

- **Stop** — sets `stopped=True`, checked before every tool dispatch. Existing tools don't cancel mid-execution (Python can't safely kill blocking subprocess/network calls), but the next scheduled action won't run.
- **Disable Tools** — tool dispatch returns "🔒 Tool execution disabled" without invoking the tool.

### 8.5 Prompt-Injection Defense (`agents/helpers.py`)

`is_prompt_injection(text)` runs regex over ~13 patterns:

- Instruction overrides: `ignore\s+(all\s+)?previous\s+instructions`, `disregard\s+earlier\s+commands`, `stop\s+being\s+an\s+assistant`, `you\s+must\s+now`
- Privilege escalation: `you\s+are\s+now\s+admin`, `act\s+as\s+root`, `bypass\s+restrictions`, `enable\s+developer\s+mode`, `sudo\s+`

Called at the top of `chat_once` and inside `generate_code`. Match → returns `{"status": "error", "message": "Security Warning..."}` and never invokes the LLM.

**Layered defenses recap:**
1. Regex screener (input filter).
2. Dry-run gate (user sees plan first even if injection succeeds).
3. Tool approval tiers (destructive tools always ask).
4. `ToolLog` audit trail.
5. Output truncation limits (10K chars for stdout/stderr, 10K for file reads, 6K for browser text).

---

## 9. Layer 6 — Tool System

### 9.1 The Tool Contract

Every tool is a `ToolDefinition`:

```python
ToolDefinition(
    name: str,                    # snake_case identifier
    description: str,             # what the LLM sees to decide when to use it
    parameters: dict,             # JSON Schema (properties, required)
    function: Callable[[dict], str], # the actual implementation
    requires_approval: bool,      # gates it into per-tool approval tier
)
```

### 9.2 The Conversion Pipeline

`tool_definition_to_langchain(td)` (in `agents/control.py`):

1. Reads the JSON Schema `properties` and `required` fields.
2. Dynamically builds a Pydantic model (`ArgsModel = create_model(...)`).
3. Wraps the function to strip `None` values so optional args behave correctly.
4. Returns an `ApprovalAwareTool` (a `StructuredTool` subclass that preserves `requires_approval`).

**Why the subclass:** LangChain's `StructuredTool` has no concept of approval. Rather than storing it in a sidecar dict (fragile), it lives on the tool object itself.

### 9.3 Tool Catalog

Total: **40+ tools** across 9 categories.

#### File & System Operations (9) — `agents/file_tools.py`
| Tool | Approval | Notes |
|---|---|---|
| `search_file` | No | Fuzzy filename search across ~/Desktop, Documents, Downloads, Pictures, Videos, OneDrive, projects, repos, work — 4 levels deep |
| `read_file` | No | Auto-detects binary (recommends `recognize_image` for images), 10K char limit with offset support |
| `list_files` | No | Directory listing with file/folder differentiation |
| `create_and_edit_file` | Yes | Create new or edit via `old_str → new_str` replacement |
| `delete_file` | Yes | File or directory (recursive) |
| `rename_file` | Yes | Also handles moves |
| `find_file_broadly` | No | Explicit broad-search version of `search_file` |
| `find_directory_broadly` | No | Directory equivalent |
| `change_working_directory` | Yes | Changes process cwd |

#### Code Execution & Validation (4) — `agents/code_tools.py`
| Tool | Approval | Notes |
|---|---|---|
| `run_code` | Yes | Arbitrary shell command; `capture_output=True`, 10K stdout/stderr truncation |
| `check_syntax` | No | Auto-picks compiler by extension (py, java, c, cpp, rs, js, ts, go, sql) |
| `run_tests` | No | Auto-detects pytest / cargo test / npm test / go test / etc. |
| `lint_code` | No | pylint / eslint / cppcheck / clippy / go vet |

#### Multimedia Recognition (3) — `agents/multimedia_tools.py`
| Tool | Approval | Notes |
|---|---|---|
| `recognize_image` | No | Base64-encodes image, sends to `gpt-4o` vision, 500-token cap |
| `recognize_video` | No | `cv2.VideoCapture` → sample ≤10 frames evenly → send frames to gpt-4o |
| `recognize_audio` | No | `gpt-4o-audio-preview`; auto-converts unsupported formats via pydub |

#### Document Creation (4) — `agents/document_tools.py`
| Tool | Approval | Backend |
|---|---|---|
| `create_pdf` | No | ReportLab (`SimpleDocTemplate`, `Paragraph`, `Table`) |
| `create_docx` | No | `python-docx` |
| `create_excel` | No | `openpyxl` |
| `create_pptx` | No | `python-pptx` |

All parse markdown into structured blocks (`_parse_markdown_blocks`), honor `<!-- PAGE_BREAK -->` markers, and enforce the requested page/slide count.

#### Document Read/Edit (8) — `agents/document_rw_tools.py`
| Tool | Approval | Backend |
|---|---|---|
| `read_pdf` / `edit_pdf` | No/Yes | PyMuPDF (falls back to pdfplumber) |
| `read_docx` / `edit_docx` | No/Yes | python-docx |
| `read_excel` / `edit_excel` | No/Yes | openpyxl |
| `read_pptx` / `edit_pptx` | No/Yes | python-pptx |

#### Email (1) — `agents/email_tools.py`
| Tool | Approval | Notes |
|---|---|---|
| `open_gmail_and_compose` | No | Creates draft via IMAP (`imaplib`) with attachments, opens Gmail in the Chrome profile matching `GMAIL_SENDER_ADDRESS`; falls back to `mailto:` if IMAP fails |

#### GitHub (5) — `agents/github_tools.py`
| Tool | Approval | Backend |
|---|---|---|
| `github_create_branch` | Yes | MCP → `github_server.py` |
| `github_commit_file` | Yes | MCP |
| `github_commit_local_file` | Yes | MCP |
| `github_create_pr` | Yes | MCP |
| `create_github_issue` | Yes | Direct REST API call |

Enforces workflow: **branch → commit → PR**. System instruction rule 14 forbids using `run_code` for git.

#### Browser Automation (1) — `agents/email_tools.py`
| Tool | Approval | Backend |
|---|---|---|
| `playwright_navigate` | Yes | Directly uses Playwright async; also has an MCP variant via `playwright_server.py`. Retries with/without `www.` prefix. Screenshots + first 6K chars of body text |

#### Travel Booking (5) — `agents/travel_tools.py`
| Tool | Approval | Notes |
|---|---|---|
| `search_flights` | No | Duffel REST API, results cached with offer expiry tracking |
| `book_travel` | Yes | Books cached offer with passenger details, persists to `Booking` model |
| `get_booking` | No | Lookup by `booking_ref` |
| `list_bookings` | No | List all rows in `Booking` |
| `cancel_booking` | Yes | Cancels via Duffel + updates DB status |

#### Feedback (1) — `agents/feedback_tools.py`
| Tool | Approval | Notes |
|---|---|---|
| `rate_experience` | No | User rates last task 1-5 + feedback; writes back into the ExperienceStore via `update_rating` |

### 9.4 Tool Execution Contract

Every call to `_execute_tool_by_name` in `agents/core.py`:

1. Checks `control.stopped` → returns "⛔ stopped".
2. Checks `control.tools_enabled` → returns "🔒 disabled".
3. Prints a colored tool-call trace to stdout.
4. Finds the `ToolDefinition` by name and invokes `function(args)`.
5. **Always logs** to `ToolLog` (SQLite), success or failure.
6. Returns the string result (or an "Error executing tool: …" string on exception).

---

## 10. Layer 7 — MCP Integration

### 10.1 What MCP Is

**Model Context Protocol** — Anthropic's open standard for connecting LLM hosts to tool servers over JSON-RPC. Transports: stdio (child process) or HTTP.

### 10.2 GitHub MCP Server (`mcp_servers/github_server.py`)

Built with `FastMCP`. Exposes:
- `create_pull_request(title, head, base, body)` — validates head branch exists and differs from base before POST-ing to `/pulls`.
- `create_branch(name, source)` — resolves source SHA, then POST `/git/refs`.
- `commit_file(path, content, branch, message)` — base64-encode, PUT `/contents/{path}`.
- `commit_local_file(local_path, ...)` — reads local file, delegates to `commit_file`.

### 10.3 Playwright MCP Server (`mcp_servers/playwright_server.py`)

Exposes:
- `navigate(url, screenshot)` — headless Chromium, retries with `_toggle_www` (adds/removes `www.` prefix), waits for `networkidle` (15s cap), takes screenshot, returns first 6K chars of body text.

### 10.4 Client Invocation Pattern

In `agents/github_tools.py::_github_mcp_call`:

```python
server_params = StdioServerParameters(
    command=sys.executable,
    args=["-B", ".../mcp_servers/github_server.py"],
)
async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(tool_name, args)
        return result.content[0].text
```

**Why this matters architecturally:** the GitHub and Playwright tools are **not tightly coupled** to this project. Any MCP-compatible host (Claude Desktop, other MCP clients) can spawn these servers and use the same tools.

---

## 11. Layer 8 — EATP: Experience-Augmented Tool Planning

The novel research contribution. RAG over the agent's own past executions instead of external documents.

### 11.1 `ExperienceRecord` — the Data Structure

Dataclass in `agents/experience_store.py`:

```python
@dataclass
class ExperienceRecord:
    task_description: str          # the user's original message
    task_category: str             # file_ops, code, document, travel, github, ...
    task_complexity: str           # heavy | light
    outcome: str                   # success | partial | failure

    id: str                        # uuid4
    created_at: datetime

    plan_summary: str              # what the agent planned
    tools_planned: List[str]

    tools_executed: List[str]      # what actually ran
    tool_results: List[Dict]       # per-tool: name, args summary, success, error

    user_corrections: List[str]    # verbal corrections from the user
    approval_actions: List[Dict]   # denials/approvals per tool

    last_validated: datetime
    confirmation_count: int        # increments on dedup consolidation

    schema_version: int = 1
    embedding_model: str = "text-embedding-3-small"
```

### 11.2 `ExperienceStore` — the ChromaDB Wrapper

Persisted at `~/.ai_agent/experiences` (or `~/.ai_agent/experiences_eval` for eval). Uses `chromadb.PersistentClient` with **HNSW cosine index**.

**Public API:**
| Method | Purpose |
|---|---|
| `add(record, skip_dedup=False)` | Embed, check for near-duplicate (similarity > 0.95), consolidate or insert |
| `retrieve(query, n_results=5)` | Embed query, top-K search, filter below 0.75 similarity, re-rank |
| `format_for_prompt(records)` | Render as "Lessons from Past Experience" section within 800-token budget |
| `update_rating(id, rating, feedback)` | Attach a user rating to a record |
| `get_all()` | Retrieve every record (used by migration script) |

**Constants:**
- `EMBEDDING_MODEL = "text-embedding-3-small"` — 1536 dim
- `SIMILARITY_THRESHOLD = 0.75` — retrieval cutoff
- `DEDUP_THRESHOLD = 0.95` — consolidation cutoff
- `TOKEN_BUDGET = 800` — prompt-injection budget for retrieved lessons

**Thread safety:** `_lock = threading.Lock()` protects `add` and `update_rating` (composite read-modify-write against ChromaDB).

### 11.3 Retrieval Pipeline

1. **Embed** query with `text-embedding-3-small`.
2. **Query** ChromaDB for top-K nearest neighbors by cosine distance.
3. **Filter** records with `similarity < 0.75`.
4. **Re-rank** by tuple key `(has_corrections, is_failure, similarity × recency_factor)` — corrections first, then failures, then similarity-weighted successes.
5. **Recency decay:**
   - `age < 30 days`: factor = 1.0
   - `30 ≤ age ≤ 180`: linear decay to 0.5
   - `age > 180`: factor = 0.5
   - `confirmation_count` × 0.05 boost (capped at +0.3)
6. **Format** as a header + per-record `TASK / OUTCOME / LESSON / PREFERRED APPROACH` blocks, greedily packing until 800 tokens.

### 11.4 Deduplication Pipeline

New record → embed → query top-1 → if `similarity > 0.95`:
- Load existing record's metadata.
- `confirmation_count += 1`.
- `last_validated = now`.
- Merge `user_corrections` (unique union).
- `collection.update` → return without inserting.

### 11.5 `ExperienceLogger` — the Record Builder

`agents/experience_logger.py`:

- `infer_category(tool_names)` — maps tool names to categories via `CATEGORY_MAP` (file_ops, code, document, travel, github, multimedia, email, browser).
- `summarize_tool_args(tool_name, args)` — replaces large content fields (`new_str`, `old_str`, `content`, `body`) with `content_length` metadata, truncates strings > 200 chars. Prevents log bloat.
- `build_record(...)` — assembles the `ExperienceRecord` from task metadata + tool executions.

### 11.6 Integration Points

**In `chat_once`:**
1. Before LLM call: `experience_store.retrieve(message)` → `format_for_prompt` → appended to system prompt.
2. After execution (on `status="success"`): infer category, build record, `store.add(...)`, wire `feedback_tools.set_last_experience_id(record.id)`.

**In `execute_dry_run`:**
Same post-execution logging, using the approved plan and actual tool results. Outcome derived from per-tool success:
- All success → `success`
- Some success → `partial`
- None success → `failure`

### 11.7 Feedback Loop (`agents/feedback_tools.py`)

Module-level state:
- `_last_experience_id` — set by the logger after each store.add.
- `_experience_store` — set by `Agent.__init__` via `set_experience_store`.

The `rate_experience` tool:
- Validates rating ∈ [1, 5].
- Calls `_experience_store.update_rating(_last_experience_id, rating, feedback)`.
- Returns thank-you message.

Ratings are stored as metadata on the record but not currently used in the ranking function — the wiring is there for future use.

### 11.8 Migration Script (`agents/migrate_experiences.py`)

When you change embedding models (e.g., upgrade from `text-embedding-3-small` to `text-embedding-3-large`), old vectors are incompatible. The migration script:

1. Loads every record via `store.get_all()`.
2. For each record with a mismatched `embedding_model`: delete from collection, re-add with `skip_dedup=True`, updating the embedding.

Prevents silent similarity errors caused by mixing embedding spaces.

---

## 12. Layer 9 — Persistence

### 12.1 SQLite (`db.sqlite3`)

Three Django-managed tables:

- **ToolLog** — one row per tool execution: `tool_name`, `input_args` (JSON), `output_result`, `created_at`. Used for audit trail. `python manage.py showlogs` prints them; `export_logs_csv` dumps to CSV.
- **ChatSession** — persistent conversations: `title`, `history` (JSON text), `created_at`, `updated_at`.
- **Booking** — travel bookings: `booking_ref`, `booking_type`, `duffel_order_id`, `passenger_name`, `passenger_email`, `total_price`, `currency`, `status`, `details` (JSON).

Migration history: 4 migrations, with `0004_replace_booking_models.py` swapping out an earlier booking schema.

### 12.2 ChromaDB (`~/.ai_agent/experiences/`)

- Persistent HNSW cosine index.
- One collection named `experiences`.
- Vectors: 1536-dim (text-embedding-3-small).
- Metadata: all `ExperienceRecord` fields JSON-serialized where necessary (ChromaDB only accepts str/int/float/bool, so lists/dicts are JSON-encoded strings).
- Eval mode uses a separate directory (`~/.ai_agent/experiences_eval/`) to keep production and experimental stores isolated.

---

## 13. Layer 10 — Evaluation Framework

Complete offline evaluation harness for reproducible research.

### 13.1 Task Suite (`evals/tasks.json`)

24+ tasks with schema:
```json
{
  "id": "task_001",
  "category": "debugging" | "refactoring" | "multi_step" | ...,
  "prompt": "Fix the off-by-one error in buggy.py",
  "seed_files": [{"source": "buggy.py", "name": "buggy.py"}]
}
```

Seed files live in `evals/seeds/` (`buggy.py`, `legacy_code.py`) and are copied into an **isolated per-task tempdir** so tests don't interfere.

### 13.2 The Runner (`evals/runner.py`)

Command line:
```bash
python evals/runner.py --output results.json --eatp-mode cold --correction-policy correction_policy.json
```

**Modes** (`--eatp-mode`):
| Mode | Purpose |
|---|---|
| `off` | Baseline — EATP disabled entirely |
| `cold` | EATP starts empty — measures cold-start learning |
| `warm` | Pre-populated store — measures warm-start improvement |
| `warm-successes` | Ablation — strips corrections, keeps only successes |
| `static-fewshot` | Control — injects `STATIC_EXAMPLES` from `static_fewshot.py` into system prompt |

**Per-task flow:**
1. `clear_session_feedback()` — reset per-task state.
2. `mkdtemp` an isolated workspace, copy seed files.
3. `change_working_directory` to that workspace.
4. `chat_once(task["prompt"])` → possibly `execute_dry_run` in loop until terminal status (max 15 turns).
5. Apply **correction policy** if configured: match a task's `deny` tool, remove it from the plan, inject a correction message via `record_denial` + `record_correction`.
6. Validate result with `VALIDATORS.get(task_id, default_validator)`.
7. Record: `id, category, prompt, response, status, duration_seconds, tool_calls, validated`.
8. Cleanup workspace, 2s sleep to avoid rate limits.

### 13.3 Mocks (`evals/mocks.py`)

`MOCK_REGISTRY` intercepts external API tools before real network calls:
- `search_flights` / `book_travel` / `get_booking` / `cancel_booking` / `list_bookings` — deterministic Duffel responses.
- `open_gmail_and_compose` — mock success.
- GitHub tools — mock branch/commit/PR responses.
- `playwright_navigate` — mock screenshot + body.

Applied by monkey-patching `agent._execute_tool_by_name` in the runner.

### 13.4 Validators (`evals/validators.py`)

Combinator library:
- `file_exists(path)`, `file_contains(path, substr)`, `response_mentions(kw)`, `tool_was_called(name)`, `script_runs(path)`, and composites.
- `VALIDATORS` dict maps `task_id → validator`.
- `default_validator` = "task did not error out."

### 13.5 Metrics (`evals/metrics.py`)

Reads `results.json`, computes:
- Overall success rate.
- Category breakdown.
- Average tool efficiency (calls per successful task).
- Average duration.

### 13.6 Cross-Phase Analysis

- `compare_phases.py` — A/B comparison across multiple result files (e.g., cold vs warm vs off).
- `correction_policy.json` — scripted user denials for Phase B of the two-phase methodology.
- `transfer_map.json` — cross-domain transfer test configuration.
- `generate_figures.py` — matplotlib chart generation for the paper (bars, learning curves).
- `figures/` — output plots.

### 13.7 Two-Phase Methodology

The research protocol supported by this framework:

1. **Phase A (baseline):** `--eatp-mode off`. Measure ceiling of the agent without memory.
2. **Phase B (populate):** `--eatp-mode cold --correction-policy correction_policy.json`. Feed a training set of tasks with scripted user denials to teach the agent lessons.
3. **Phase C (evaluate):** `--eatp-mode warm` on a held-out test set. Measure the improvement over Phase A on tasks the agent has never seen but can retrieve lessons for.

Ablations (`warm-successes`, `static-fewshot`) isolate individual contributions.

---

## 14. Layer 11 — Testing

Pytest suite in `tests/`:

| Test | Coverage |
|---|---|
| `test_experience_store.py` | ChromaDB add/retrieve/dedup/decay/format |
| `test_experience_logger.py` | Record building, category inference, arg summarization |
| `test_feedback_tools.py` | Rating tool wiring |
| `test_eatp_integration.py` | End-to-end EATP: log → retrieve → prompt injection |
| `test_eatp_manual.py` | Manual regression scenarios |
| `test_mcp_navigate.py` | Playwright MCP navigation |
| `test_mocks.py` | Mock registry sanity |
| `test_normalize_url.py` | `_normalize_url` (schemes, quotes, whitespace) |
| `test_static_fewshot.py` | Fixed few-shot content validation |
| `test_validators.py` | Validator combinators |

---

## 15. End-to-End Workflows

### 15.1 Workflow: "Read notes.txt and summarize" (Fresh Task)

```
1. USER  →  POST /api/chat/  {"message": "read my notes.txt and summarize"}
2. Django views.chat_api → Agent.chat_once(history=[], message=...)
3. EATP: store.retrieve("read my notes...") → format_for_prompt → append to system prompt
4. is_prompt_injection → false
5. HumanMessage appended → _trim_messages → LangGraph invoke
6. classify_task → LLM_mini → "heavy" (file ops)
7. call_model → gpt-6-sol with tools bound → AIMessage(tool_calls=[read_file])
8. route_after_model → use_pending=False → collect_dry_run
9. dry_run_plan = [{name: read_file, args: {path: notes.txt}, summary: "Read file: notes.txt"}]
10. _generate_plan_summary → LLM writes "I will read your notes.txt..."
11. Return {status: "dry_run", dry_run_plan, response, history}

12. USER approves → POST {"status": "dry_run_approved", "dry_run_plan": [...], "history": [...]}
13. Agent.execute_dry_run(plan, history)
14. For each tool: _execute_tool_by_name("read_file", args) → returns file content
15. ToolMessage appended to messages, ToolLog row inserted
16. EATP: build_record + store.add (outcome derived from tool success)
17. Re-invoke graph with use_pending=True, task_class="heavy"
18. classify_task skipped (task_class preset)
19. call_model → LLM sees tool results, produces summary AIMessage(no tool_calls)
20. route_after_model → not an AIMessage w/ tool_calls → format_output
21. Return {status: "success", response: "Your notes contain...", history}
```

### 15.2 Workflow: Multi-Step Coding Task with Correction

```
1. USER: "Create a Python script that sorts numbers"
2. Fresh chat_once → dry-run: [create_and_edit_file: sort.py]
3. USER denies dry-run → chat_once with denial in history
4. Agent replans: [create_and_edit_file: sort.py with different content]
5. USER: "Use quicksort not bubble sort" (correction via chat)
6. Session-level: record_correction("Use quicksort, not bubble sort")
7. New dry-run with quicksort
8. USER approves → execute_dry_run
9. Follow-up: LLM wants to run_tests → route through per-tool approval (pending)
10. USER approves run_tests → executes, LLM sees green tests
11. Final AIMessage: "Created sort.py with quicksort, tests pass"
12. EATP: record stored with user_corrections=["Use quicksort, not bubble sort"], outcome=success
```

Next time a similar task appears, retrieval will surface this record, ranked highly because it has `user_corrections`.

### 15.3 Workflow: GitHub PR (Enforced 3-Step)

```
1. USER: "Push fix.py to a new branch and open a PR"
2. Agent plans: [github_create_branch, github_commit_local_file, github_create_pr]
3. Each is requires_approval=True → dry-run shown, user approves whole plan
4. execute_dry_run:
   - github_create_branch → MCP subprocess → GitHub REST API
   - github_commit_local_file → reads fix.py, base64, PUT /contents
   - github_create_pr → validates branch exists, POSTs /pulls
5. Final response: "PR #42 created: https://..."
```

**Rule 14** in system instruction prevents the LLM from using `run_code` with `git` — must use MCP tools.

### 15.4 Workflow: Interrupted Task Resume

```
1. USER: "Refactor the auth module"
2. Agent proposes 5-tool plan, user approves
3. Mid-execution, USER hits Stop → control.stopped=True
4. Next tool dispatch returns "⛔ stopped"
5. Later, USER: "continue"
6. _detect_interrupted_task scans last 5 messages, finds tool_calls without responses
7. Injects context: "[System note: The previous task was interrupted. Context: The agent was about to execute tools [X, Y] but execution was interrupted...]"
8. Prepends this before the user message
9. Agent resumes from where it left off
```

### 15.5 Workflow: EATP Retrieval Loop

```
1. USER: "Delete all .log files in this directory"
2. store.retrieve("delete all .log files") queries embeddings
3. Top-K hits (similarity > 0.75), re-ranked → top record has:
     - user_corrections=["Always confirm before mass deletion — user reported wrong dir last time"]
4. format_for_prompt renders as "Lessons from Past Experience"
5. Injected into system prompt for THIS turn only
6. LLM sees the lesson, structures its plan to explicitly confirm the directory
```

---

## 16. Message Lifecycle & Format Conversions

Messages exist in **three formats**; the mixin translates between them:

| Format | Where | Example |
|---|---|---|
| **Frontend dict** | Wire format, `chat/index.html` ↔ Django | `{"role": "assistant", "content": "...", "tool_calls": [{"id":..., "type":"function", "function":{"name":..., "arguments":"{...}"}}]}` |
| **LangChain message object** | Inside the graph | `AIMessage(content=..., tool_calls=[{"id":..., "name":..., "args":{...}}])` |
| **OpenAI native** | Kept for backward compat | Same as frontend dict roughly |

**Key translation subtleties:**
- Frontend uses `tool_calls[*].function.arguments` as a **JSON string**; LangChain uses `tool_calls[*].args` as a **dict**.
- `ToolMessage.tool_call_id` must match the corresponding `AIMessage.tool_calls[*].id` — mismatches cause OpenAI 400s.
- `_strip_orphaned_tool_calls` prevents these mismatches when approval is aborted mid-plan.

---

## 17. Context Management

### 17.1 The Trim Algorithm (`_trim_messages`)

1. If `len(messages) ≤ max_history + 1`, return unchanged.
2. Preserve the first message (system prompt).
3. Compute `start_index = len(messages) - max_history`.
4. If `messages[start_index]` is a `ToolMessage`, walk backward until we find a non-tool message — never split a `AIMessage(tool_calls)` from its `ToolMessage` responses (this would violate OpenAI's contract).
5. Collect dropped messages (excluding system).
6. If any are LangChain messages, generate a rolling summary via `_summarize_messages`.
7. Reassemble: `[system_prompt, summary_as_SystemMessage, ...recent_messages]`.

### 17.2 The Summarization

`_summarize_messages` builds a plain-text transcript (user, assistant with tool call names, tool results — each truncated to 500 chars), then asks the heavy LLM for a "3-5 bullet points" summary. If there's an existing summary, the prompt tells the LLM to **extend** it, not restart — so context accumulates over long conversations.

### 17.3 Interruption Detection (`_detect_interrupted_task`)

Runs on every new user message. If the user's message matches a "continue"-intent phrase (`continue`, `go on`, `resume`, `retry`, `keep going`, ...), it scans the last 5 messages for:

1. **Pattern 1:** `AIMessage` with `tool_calls` that lack matching `ToolMessage` responses → "was about to execute X but interrupted"
2. **Pattern 2:** Last `ToolMessage` says "denied" → "user denied X"
3. **Pattern 3:** Last `AIMessage` mentions "error/failed/could not" → last content excerpt

If any pattern matches, prepends a `[System note: ...]` context block before the user's message.

---

## 18. Capabilities Matrix

| Capability | Tools/Layer | Notes |
|---|---|---|
| **Read local files** | `read_file`, `list_files`, `search_file`, `find_file_broadly`, `find_directory_broadly` | Absolute or relative; broad search across common dirs |
| **Modify local files** | `create_and_edit_file`, `rename_file`, `delete_file`, `change_working_directory` | All require approval |
| **Execute shell / code** | `run_code` | 10K stdout/stderr cap, approval required |
| **Validate code** | `check_syntax`, `run_tests`, `lint_code` | 8+ languages |
| **Analyze images** | `recognize_image` | GPT-4o vision |
| **Analyze video** | `recognize_video` | OpenCV frame extraction + GPT-4o |
| **Analyze audio** | `recognize_audio` | GPT-4o audio; pydub format conversion |
| **Create documents** | `create_pdf/docx/excel/pptx` | Markdown → structured document |
| **Read/edit documents** | 8 read/edit tools | PyMuPDF, python-docx, openpyxl, python-pptx |
| **Send email drafts** | `open_gmail_and_compose` | IMAP draft + Chrome profile detection |
| **GitHub workflow** | `github_create_branch/commit/pr`, `create_github_issue` | Enforced 3-step; via MCP |
| **Web browsing** | `playwright_navigate` | Headless Chromium, screenshots + text extraction |
| **Book flights** | `search_flights`, `book_travel`, `get/list/cancel_booking` | Duffel API |
| **Give feedback to agent** | `rate_experience` | Writes to EATP store |
| **Persistent conversations** | `ChatSession` model | Save/load/delete |
| **Audit tool executions** | `ToolLog` model | Every call, forever |
| **Learn from past runs** | EATP subsystem | Retrieval-augmented, correction-weighted |
| **Human-in-the-loop safety** | Dry-run + per-tool approval | Two-tier |
| **Emergency stop** | `AgentControlState.stop()` | Thread-safe |
| **Kill switch** | `AgentControlState.disable_tools()` | Global |
| **Prompt-injection defense** | `is_prompt_injection` regex | ~13 patterns |
| **Cost-aware routing** | `classify_task` | Heavy (gpt-6-sol) vs Light (gpt-5.6-terra) |
| **Task classification** | System instruction rules 17-18 | SIMPLE vs COMPLEX phases |
| **Self-recovery** | System instruction rule 20 | Install deps, fix errors, 3-attempt escalation |
| **Interrupted-task resume** | `_detect_interrupted_task` | Auto-injects context on "continue" |
| **Reproducible evaluation** | `evals/runner.py` | 5-mode ablation matrix |

---

## 19. External Dependencies & Configuration

### 19.1 Runtime Dependencies (Selected)

| Package | Purpose |
|---|---|
| `django` | Web framework, ORM, migrations |
| `openai` | gpt-6-sol, gpt-5.6-terra, embeddings, audio |
| `langchain-openai` | ChatOpenAI wrapper |
| `langchain-core` | Message types, tools |
| `langgraph` | StateGraph, compiled state machines |
| `chromadb` | Vector DB for EATP |
| `mcp>=1.2.0` | Model Context Protocol client/server |
| `playwright` | Browser automation |
| `pydantic` | Dynamic tool argument schemas |
| `opencv-python` | Video frame extraction |
| `pydub` | Audio format conversion |
| `reportlab` | PDF generation |
| `python-docx` | Word documents |
| `openpyxl` | Excel |
| `python-pptx` | PowerPoint |
| `PyMuPDF` (fitz) | PDF reading |
| `imaplib` (stdlib) | Gmail draft creation |
| `requests` | REST API calls |
| `boto3` + `django-storages` | S3 static file storage (prod) |
| `python-dotenv`, `python-decouple` | .env loading |
| `textual` | TUI |

### 19.2 Environment Variables (`.env`)

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Required — LLM, embeddings, vision, audio |
| `GMAIL_ADDRESS` / `GMAIL_PASSWORD` | Gmail draft creation via IMAP (16-char app password) |
| `CHROME_PROFILE_DIRECTORY` | Manual override for profile auto-detection |
| `GITHUB_TOKEN` / `GITHUB_REPO` | GitHub MCP + REST tools |
| `DUFFEL_API_TOKEN` | Flight booking |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_STORAGE_BUCKET_NAME` / `AWS_S3_REGION_NAME` | S3 static storage (prod) |

### 19.3 External Services

| Service | Used by |
|---|---|
| OpenAI Chat Completions API | `call_model`, `_generate_plan_summary`, `_summarize_messages`, `generate_code`, image/video/audio recognition |
| OpenAI Embeddings API | `ExperienceStore._embed_texts` |
| GitHub REST API | `github_server.py`, `create_github_issue_tool` |
| Duffel REST API | `travel_tools.py` |
| Gmail IMAP | `email_tools.create_gmail_draft` |
| Chrome (via Playwright) | `playwright_navigate` |
| Chrome (system) | Gmail compose window open |

---

## 20. Concurrency Model

### 20.1 Where Concurrency Happens

- **Django dev server** is multi-threaded (WSGI). Every HTTP request runs on a separate thread.
- The **single global `agent` object** in `chat/views.py` is shared across those threads.
- Async is used inside `playwright_mcp_tool` and `_github_mcp_call` (`asyncio.run` per invocation), but these blocks are synchronous from the agent's perspective.

### 20.2 What's Protected

| Shared State | Protected By |
|---|---|
| `AgentControlState.stopped` / `.tools_enabled` | `threading.Lock` for writes |
| `ExperienceStore.add` / `.update_rating` | `threading.Lock` (ChromaDB doesn't guarantee cross-thread safety for consolidation) |
| `ToolLog.objects.create` | Django ORM handles connection-per-thread |
| `chat/views.py`'s Agent instance | Not protected — but individual `chat_once` calls create fresh graph state and message lists |

### 20.3 Known Race Windows

- A stop-request during an in-flight LLM API call cannot preempt the call; only the next scheduled tool dispatch checks the flag.
- Reads of `control.stopped` at the top of graph nodes are outside the lock; safe under GIL for a bool, but future-proof by wrapping in `with lock:` if types change.

---

## 21. Extension Points

Where to plug things in without breaking the architecture:

| Adding... | Where |
|---|---|
| **A new tool** | Create a new module in `agents/`, define a `ToolDefinition`, register in `agents/__init__.py` (for eval auto-discovery), `chat/views.py::tools`, `tui.py::ALL_TOOLS`, and `agents/core.py::main` |
| **A new safety check** | Add a graph node (e.g. between `call_model` and `format_output`), wire the conditional edge |
| **A new LLM provider** | Wrap `ChatOpenAI` behind a factory in `Agent.__init__`; LangChain has adapters for Anthropic, Google, etc. |
| **A new MCP server** | Drop a `FastMCP` file in `mcp_servers/`, add a client wrapper in the corresponding `*_tools.py` |
| **A new experience-ranking signal** | Extend `rank_key` in `ExperienceStore.retrieve` |
| **A new prompt-injection pattern** | Add regex to `agents/helpers.py::injection_patterns` + test in `tests/` |
| **A new benchmark task** | Add to `evals/tasks.json`, seed files to `evals/seeds/`, validator to `evals/validators.py::VALIDATORS` |
| **A new eval mode** | Add branch in `evals/runner.py::run_evals` + new option in argparse choices |
| **A new API endpoint** | Add view function in `chat/views.py`, URL in `chat/urls.py` |
| **A new DB model** | Add to `chat/models.py`, `makemigrations` + `migrate` |
| **A new frontend** | Use the same `Agent` class + tool list; mimic the `status`-based dispatch pattern from `chat/views.py::chat_api` |

---

## Appendix — Key Files Cheat Sheet

| File | Purpose |
|---|---|
| `agents/core.py` | Agent class + LangGraph + system instruction |
| `agents/control.py` | AgentControlState, ToolDefinition, ApprovalAwareTool |
| `agents/agent_messages.py` | Message format conversion mixin |
| `agents/helpers.py` | File search + prompt injection regex |
| `agents/experience_store.py` | EATP ChromaDB store |
| `agents/experience_logger.py` | EATP record builder |
| `agents/feedback_tools.py` | rate_experience tool |
| `agents/*_tools.py` | Tool implementations by category |
| `mcp_servers/*.py` | MCP tool servers |
| `chat/views.py` | HTTP API |
| `chat/models.py` | DB schema |
| `chat/urls.py` | URL routing |
| `chat/templates/chat/index.html` | Web UI |
| `config/settings.py` | Django settings, env vars |
| `tui.py` | Terminal UI |
| `evals/runner.py` | Eval driver |
| `evals/tasks.json` | Benchmark |
| `evals/validators.py` | Ground-truth checkers |
| `evals/mocks.py` | Deterministic external API stubs |
| `tests/` | pytest suite |
