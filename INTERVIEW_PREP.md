# AI Agent Project — Interview & Study Guide

A complete study/interview preparation document covering the crucial concepts, likely interview questions, model answers, potential modification asks, and a concept-by-concept study checklist for this project.

---

## Table of Contents

1. [Part 1 — Crucial Concepts Behind This Project](#part-1--crucial-concepts-behind-this-project)
2. [Part 2 — Interview Questions & Model Answers](#part-2--interview-questions--model-answers)
3. [Part 3 — Modifications an Interviewer Might Ask You to Make](#part-3--modifications-an-interviewer-might-ask-you-to-make)
4. [Two Meta-Points That Impress Interviewers](#two-meta-points-that-impress-interviewers)
5. [Concept-by-Concept Study Checklist](#concept-by-concept-study-checklist)
6. [Recommended Study Order](#recommended-study-order)

---

# Part 1 — Crucial Concepts Behind This Project

## 1. Agent Architecture (The Core Loop)

**Concept: Tool-using ReAct-style LLM agent.**
The agent is not just an LLM — it's an LLM wrapped in a **plan-act-observe loop** where the model can emit `tool_calls` (structured JSON), the framework executes them, and the observations are fed back as `ToolMessage`s. The loop continues until the model produces a final text response with no tool calls.

**Where it lives:** `agents/core.py` → `Agent` class, driven by a LangGraph `StateGraph`.

## 2. LangGraph State Machine

The project explicitly moved off a "vibe-coded" while-loop into a **compiled, explicit state graph** with these nodes:

- `classify_task` → routes to a "heavy" (`gpt-6-sol`) or "light" (`gpt-5.6-terra`) LLM to save cost
- `call_model` → invokes the LLM with bound tools
- `collect_dry_run` → gathers proposed tool calls into a plan for user approval (safety)
- `execute_or_hold_tools` → auto-runs low-risk tools, holds high-risk for per-tool approval
- `format_output` → normalizes the final response

**Why it matters:** deterministic control-flow, testable nodes, explicit approval boundaries. This is the **research contribution around safety** — most agent frameworks (AutoGPT-style) let LLMs autonomously execute, this one enforces a human-in-the-loop checkpoint via a graph node.

## 3. EATP — Experience-Augmented Tool Planning (The Novel Contribution)

This is what makes the project **publishable**. It's essentially **RAG applied to the agent's own past executions**, not to external documents.

**Pipeline:**
1. Every completed task produces an `ExperienceRecord` (task description, plan, tools used, outcome, user corrections, denials).
2. Records are embedded with `text-embedding-3-small` and stored in **ChromaDB** (persistent HNSW index, cosine similarity).
3. On a new user message, the store retrieves the top-K similar past experiences (`SIMILARITY_THRESHOLD = 0.75`).
4. Retrieved records are **re-ranked** so that corrections > failures > successes (the agent learns most from mistakes).
5. A **recency decay factor** (1.0 for < 30 days, linear decay to 0.5 at 180 days, boosted by `confirmation_count`) prevents stale lessons from dominating.
6. Near-duplicates (`similarity > 0.95`) are consolidated instead of stored (`confirmation_count++`), controlling store growth.
7. The formatted "Lessons from Past Experience" block is injected into the system prompt within an **800-token budget** (`~4 chars/token`).

**Why it matters:** the agent gets **better with use without fine-tuning**. This is the pitch: RAG-over-episodic-memory as an alternative to expensive model retraining.

## 4. Dual-Mode Human-in-the-Loop Safety

- **Dry-run mode:** for a new user message, ALL planned tools are collected into a plan, LLM-summarized in plain English, and shown to the user before any execution.
- **Per-tool approval:** after approval, follow-up tool calls trigger only for `requires_approval=True` tools (delete, run_code, GitHub ops, browser).
- **Kill switch:** `AgentControlState` with `stop` and `disable_tools` flags, protected by a `threading.Lock` (real thread safety, not just cosmetic).

## 5. Model Context Protocol (MCP)

GitHub and Playwright integrations don't call APIs directly — they spawn **MCP servers** as subprocesses (`stdio_client`) and communicate via the MCP JSON-RPC protocol. This is Anthropic's emerging standard for tool interoperability. It means the GitHub tools could theoretically be re-used by Claude Desktop or any MCP-compatible host.

## 6. Tool Definition Abstraction

Every capability is a `ToolDefinition(name, description, parameters, function, requires_approval)`. At init, these are converted to LangChain `StructuredTool`s using dynamic Pydantic model generation (`create_model`). This gives you:

- One source of truth per tool
- Auto-generated JSON schemas for the LLM
- Type validation from Pydantic
- A `requires_approval` flag that survives the conversion (`ApprovalAwareTool` subclass)

## 7. Prompt Injection Defense

`is_prompt_injection()` uses **regex heuristics** to catch known patterns ("ignore previous instructions", "act as root", "sudo", etc.). It's a lightweight first line of defense before the message reaches the LLM. Not ML-based (yet) but explicit and auditable.

## 8. Evaluation Framework (Proving It Works)

`evals/runner.py` supports **5 experimental conditions** — this is the paper's methodology:

- `off` — no EATP (baseline)
- `cold` — EATP starts empty (measures learning from scratch)
- `warm` — EATP pre-populated with training experiences
- `warm-successes` — ablation, keeps successes but strips corrections
- `static-fewshot` — control condition using fixed few-shot examples

Plus: **task workspaces are isolated per-task in tempdirs**, results are **validated by task-specific validators**, and there's a **correction policy** system that scripts user denials to test EATP's ability to learn from feedback. This is publication-grade methodology.

## 9. Other Notable Concepts

- **Django** as the web/API layer with SQLite for `ToolLog` (audit) and `ChatSession` (memory).
- **Conversation trimming** (`_trim_messages`) + summary preservation to stay under context limits.
- **Orphaned tool-call cleanup** (`_strip_orphaned_tool_calls`) — critical for correctness when a user aborts approval mid-plan (otherwise the message history is malformed and the API rejects it).
- **Interrupted-task detection** (`_detect_interrupted_task`) — resumes work if user says "continue".
- **Broad file search** — recursive fuzzy search across Desktop/Documents/Downloads/OneDrive with 4-level depth cap. Makes the agent feel human.

---

# Part 2 — Interview Questions & Model Answers

## Category A: Architecture & Design

### Q1: Walk me through what happens when a user types "read my notes.txt file and summarize it".

> The message enters `chat_api` in Django, which calls `Agent.chat_once()`. Inside, the system prompt is augmented with any relevant past experiences retrieved from ChromaDB (EATP). A prompt-injection heuristic check runs. Then a LangGraph `StateGraph` is invoked starting from `classify_task`, which uses the light model to label it "heavy" (file ops). `call_model` invokes gpt-6-sol with the tools bound; the LLM emits a tool call for `read_file`. Since this is a fresh user message with `use_pending=False`, we route to `collect_dry_run` which packages the plan, LLM-summarizes it in plain English, and returns `status="dry_run"` to the frontend. When the user approves, `execute_dry_run()` runs each tool, logs it to SQLite, appends the results as `ToolMessage`s, and re-invokes the graph in `use_pending=True` mode so any follow-up calls go through per-tool approval. Finally the model produces a text summary, and the full run is logged as an `ExperienceRecord`.

### Q2: Why LangGraph instead of a simple while-loop?

> Three reasons. First, **explicit control flow** — safety checkpoints like the dry-run gate are first-class nodes, not `if` statements buried in a loop. Second, **testability** — each node is a pure function of state that I can unit-test in isolation, plus I have a `_test_fail_node` hook that simulates node-level failures. Third, **future extensibility** — adding retry branches, parallel tool execution, or richer routing is a matter of adding nodes and edges, not surgery on a monolithic loop. LangGraph also enforces a recursion limit (I set 25) which prevents runaway agents.

### Q3: What's the difference between dry-run and per-tool approval, and why have both?

> Dry-run is **plan-level**: the user sees the entire proposed sequence before anything executes. It answers "am I OK with this whole workflow?" — good for high-stakes new tasks. Per-tool approval is **action-level**: only high-risk tools (`delete_file`, `run_code`, GitHub writes) prompt individually. It answers "am I OK with this specific action?" — good for follow-up steps where the workflow is already understood. Having both is a UX trade-off: dry-run stops surprises, per-tool avoids approval fatigue for read-only follow-ups.

## Category B: EATP (The Research Contribution)

### Q4: Explain EATP and how it's different from RAG.

> EATP retrieves from the agent's own past executions, not external documents. Each completed task becomes an `ExperienceRecord` containing the task description, tool sequence, outcome, and any user corrections. On a new task, semantically similar past records are retrieved from ChromaDB, re-ranked (**corrections > failures > successes**), decayed by recency, and injected into the system prompt. It's episodic memory as retrieval — the agent learns from experience without any weight updates.

### Q5: Why re-rank corrections first? Why not just use similarity?

> Because the most information-dense past experiences are the ones where the user pushed back. If EATP only surfaced high-similarity successes, the agent would keep repeating whatever it already does — no learning. Ranking corrections first means the retrieved context is dominated by "here's what to avoid," which has been shown in in-context learning literature to be more corrective than positive examples. My `warm-successes` ablation isolates exactly this: it strips corrections and only keeps successful examples, letting me measure the delta.

### Q6: What's your dedup strategy and why does it matter?

> Any new record with cosine similarity > 0.95 to an existing one triggers a **consolidation** instead of an insert: I increment `confirmation_count`, refresh `last_validated`, and merge new corrections. Without this, popular tasks like "read a file" would flood the store and dominate retrieval. Consolidation also feeds back into the ranking: high-confirmation records resist recency decay, so genuinely-repeated lessons stay influential.

### Q7: How do you prevent stale experience records from hurting the agent?

> Two mechanisms. **Recency decay** — records older than 30 days start losing weight linearly, hitting a floor of 0.5 at 180 days. **Confirmation boost** — each consolidation adds up to 0.3 back to the recency factor, so lessons the user keeps validating stay relevant. Records below `SIMILARITY_THRESHOLD = 0.75` after decay are filtered out entirely.

### Q8: What are the failure modes of EATP?

> Three main ones. **Semantic drift** — tasks that use similar language but need different approaches could pull the wrong lesson (I mitigate by filtering below 0.75). **Poisoning** — a bad correction gets stored and biases future runs (mitigated by user rating via `RATE_EXPERIENCE_DEFINITION`, currently disabled but built). **Prompt bloat** — retrieved sections eat context budget (mitigated with an 800-token cap). A subtler failure is **overfitting to the corpus** — if the store gets biased toward one type of task, novel tasks might get irrelevant retrievals.

## Category C: Safety & Security

### Q9: How do you defend against prompt injection?

> Layered defenses. First, a **regex-based screener** in `is_prompt_injection()` catches known patterns before the message reaches the LLM. Second, the **dry-run mode** means even if an injection succeeds and gets the model to plan malicious actions, the user sees the plan first. Third, **tool approval tiers** — even in per-tool mode, destructive tools require explicit approval. Fourth, **audit logging** — every tool call is persisted so you can post-hoc detect exploitation. I'll be honest: regex heuristics are weak against sophisticated injections, and the roadmap has ML-based detection as v1.2.

### Q10: What happens if `run_code` gets called with `rm -rf /`?

> `run_code` is in the `requires_approval=True` tier, so the user sees the plan before execution. Assuming they approve, the command runs with a 30-second timeout under whatever OS-level user permissions the Django process has. That's the current state — and it's a real limitation I document in the README. Production-grade would be an **allowlist** of commands (in the enterprise policy YAML I sketched), plus a **Docker sandbox** (I have a `Dockerfile.sandbox` skeleton). This is honestly one of the things I'd tighten first before any real deployment.

### Q11: Your `AgentControlState` uses a `threading.Lock`. When can two threads actually race here?

> Django's dev server is threaded — a user can hit the `/api/agent-control/` endpoint (setting `stopped=True`) from one HTTP request while another thread is inside the agent loop checking `self.control.stopped` and dispatching the next tool. Without the lock, a stop signal could be lost between the read and the next tool dispatch, or two calls to `disable_tools()` could race. The lock isn't for correctness of a single boolean assignment (Python is fine with those under the GIL) but for **composite reads-then-writes** and future-proofing when the flags become dicts.

## Category D: Engineering & Evaluation

### Q12: How did you evaluate whether EATP actually helps?

> I built a benchmark of 24+ tasks across categories (debugging, refactoring, multi-step reasoning) in `evals/tasks.json`, with per-task ground-truth validators in `evals/validators.py`. External APIs are mocked (`evals/mocks.py`) for determinism. The runner supports 5 modes: `off` (baseline), `cold` (EATP starting empty), `warm` (EATP pre-populated), `static-fewshot` (control), and `warm-successes` (ablation with corrections stripped). I measure **validated success rate, tool efficiency (tool calls per success), and per-category breakdown**. The methodology follows the "two-phase" protocol: Phase B populates the store using a scripted correction policy, Phase C evaluates on held-out tasks.

### Q13: Why light + heavy models?

> Cost. Roughly 60-70% of the tasks I see are "light" — email drafting, formatting, template filling — where `gpt-5.6-terra` is indistinguishable in quality from `gpt-6-sol` and roughly 5-10x cheaper. `classify_task` uses the light model itself to route, so the classification is almost free. Heavy multi-step reasoning, code generation, and vision go to the full model. It's a poor-man's mixture-of-experts routing.

### Q14: How do you handle tool errors and retries?

> Two layers. **Node-level:** each LangGraph node has a try/except that returns `status="error"` with the failure location, so I never crash the whole graph. **LLM-level:** system instruction rule 20 tells the model to auto-recover — install missing packages via `run_code`, fix syntax errors it wrote, try alternative approaches — before ever reporting failure to the user. It has to make **3 genuine attempts with different approaches** before escalating. This is a form of **self-correction agent loop** without needing a separate reflector agent.

## Category E: Data & Persistence

### Q15: You have SQLite for logs and ChromaDB for experiences. Why two stores?

> They serve different purposes. **SQLite (`ToolLog`, `ChatSession`)** is for structured, queryable audit and session data — I want to `WHERE tool_name='delete_file'` for security reviews. **ChromaDB** is for semantic retrieval — I need vector similarity, HNSW indexing, and persistent embeddings, which SQLite can't do natively. In production I'd move sessions to Postgres and keep the same split.

### Q16: How is context managed when a conversation gets long?

> `_trim_messages` drops middle messages while preserving the system prompt and the most recent N (default 15). Before dropping, `_conversation_summary` captures a rolling summary so context isn't lost entirely. I also `_strip_orphaned_tool_calls` — if the user denies approval mid-plan, the AI message still has `tool_calls` referring to executions that never happened, which OpenAI rejects on the next turn. Stripping those keeps the message history valid.

---

# Part 3 — Modifications an Interviewer Might Ask You to Make

An interviewer will test whether you actually understand the code by asking you to change it live. Here are the most likely asks, ordered from easy → hard, and how to approach each.

## Easy (tests you can navigate the codebase)

### 1. "Add a new tool that reads the contents of a URL."
Create `agents/web_tools.py`, define a `WEB_FETCH_DEFINITION` with `ToolDefinition(name, description, parameters, function, requires_approval=False)`, register in `agents/core.py`'s `main()` and `agents/__init__.py` so `evals/runner.py`'s dynamic discovery picks it up. Discuss whether URL fetching should require approval (arguments for: SSRF risk; against: read-only).

### 2. "Add a new prompt injection pattern to block."
Add regex to `injection_patterns` in `agents/helpers.py`. Show you know to add a test in `tests/`.

### 3. "Change the recency decay from 30/180 days to 7/90 days and explain why."
Modify `_recency_factor` in `experience_store.py`. Discuss: tighter decay reacts faster to a changing codebase but risks losing valid long-term lessons.

## Medium (tests architectural understanding)

### 4. "Make the EATP retrieval configurable per task category — e.g., always retrieve 10 for `code` tasks, 2 for `email` tasks."
Modify `ExperienceStore.retrieve(query, n_results)` to accept a category, or make `n_results` a dict in the caller (`core.py` → `chat_once`). The design conversation matters more than the code.

### 5. "Add a new graph node that runs after `call_model` and checks if the response contains any secrets before returning."
Add `secret_scanner` node, insert into the graph between `call_model` and `format_output`, wire the conditional routing. This tests whether you understand LangGraph's `add_node`/`add_edge`/`add_conditional_edges`.

### 6. "Right now `execute_or_hold_tools` executes tools sequentially. Make read-only tools run in parallel."
Introduces `asyncio.gather` or a `ThreadPoolExecutor`, careful about ordering the `ToolMessage`s back so `tool_call_id`s align. Discuss why write tools shouldn't parallelize.

### 7. "Add a scheduled job that garbage-collects experiences with `confirmation_count == 0` and older than 90 days."
Add a Django management command or Celery task. Discuss whether it should also check for a low user rating.

## Hard (tests deeper systems thinking)

### 8. "Replace ChromaDB with pgvector so it uses the same Postgres as sessions."
Rewrite `ExperienceStore` against `psycopg2` + `pgvector`, keep the same `add/retrieve/format_for_prompt` API so nothing above changes. Discuss: cost of maintaining two DB drivers vs. operational simplicity of one.

### 9. "Add streaming: the frontend should see the LLM tokens as they arrive."
LangChain's `astream` on the LLM, WebSocket in Django Channels, buffer at the tool-call boundary because you can't stream a partial JSON tool call. Discuss the trickiness of streaming when the model might emit either text or a tool call and you don't know until it commits.

### 10. "Make the agent work with Claude, not just OpenAI."
Wrap `ChatOpenAI` behind a factory. Discuss that LangChain already abstracts this, but tool schemas differ (OpenAI's `function` calling vs. Anthropic's `tool_use` blocks) — LangChain handles it. Also discuss why I don't just do this today: current cost is fine and single-provider means simpler failure modes.

### 11. "How would you evaluate whether EATP actually reduces hallucinations, not just improves task success?"
Introduce a separate metric: **groundedness score** using an LLM-as-judge on tool arguments (does the model invent file paths that don't exist? Does it fabricate flight prices?). Add to `evals/metrics.py`. This is a **research question** — expect follow-ups on how you'd validate the judge itself.

### 12. "There's a race condition in `AgentControlState`. Find it and fix it."
This is a gotcha. The `stopped`/`tools_enabled` reads outside the lock in the graph nodes are a form of double-checked pattern; under CPython's GIL they're safe, but on a hypothetical free-threaded Python or if these become non-atomic types (dicts), they'd race. The real fix is `with self.control.lock: stopped = self.control.stopped` at read sites. Bonus: discuss that stopping is inherently racy — you can't cancel a tool that's already executing.

### 13. "Show me how you'd write a paper's ablation table from your eval framework."
Run `runner.py --eatp-mode off/cold/warm/warm-successes/static-fewshot`, produce `results_*.json`, then a script that reads all five and emits a LaTeX table with success rate, tool efficiency, per-category breakdown, and 95% CIs (bootstrap over tasks). Discuss statistical significance — with 24 tasks, differences under ~10% may not be significant, motivating a bigger benchmark for the paper.

---

# Two Meta-Points That Impress Interviewers

1. **Know your project's limits and say them out loud.** "Regex-based prompt injection is weak. `run_code` has no sandbox. My benchmark is 24 tasks which is too small for tight CIs." Volunteering these before being asked signals research maturity.

2. **Have one number ready for every claim.** "EATP improved validated success rate from X% to Y% on cold-start, Z% on warm-start." Even ballpark numbers matter — if you don't have them yet, run the evals *before* the interview.

Given the target is a CS/AI conference, EATP is the headline. Practice the 60-second pitch:

> **"Agentic LLMs typically don't learn between sessions without fine-tuning. EATP treats past executions as a retrievable episodic memory, re-ranked to prioritize user corrections. On a 24-task benchmark, it improves validated task completion by X% over a strong tool-use baseline, without any model weight changes."**

That's your abstract.

---

# Concept-by-Concept Study Checklist

For each concept: **what it is**, **where it lives in your project**, and **the exact sentence to say in an interview**.

## 1. LLM & Agent Foundations

### Large Language Model (LLM) / Chat Completion
- **What:** A model that takes a sequence of messages (system/user/assistant) and returns the next message.
- **In your project:** gpt-6-sol (heavy) and gpt-5.6-terra (light) via OpenAI's chat completion API.
- **Say:** "The LLM is the reasoning engine — the framework around it is just plumbing that gives it tools, memory, and safety gates."

### Tool Calling / Function Calling
- **What:** A structured output mode where the LLM emits JSON matching a declared schema, instead of prose. The framework then executes that "function" and feeds the result back.
- **In your project:** Each `ToolDefinition` has a JSON Schema in `parameters`; the LLM returns `tool_calls` with matching arguments; you dispatch them in `_execute_tool_by_name`.
- **Say:** "The LLM never actually runs code — it decides what to run. My framework enforces the boundary."

### ReAct Loop (Reasoning + Acting)
- **What:** The pattern of `LLM thinks → calls a tool → observes the result → thinks again → …` until the model produces a final answer.
- **In your project:** Implemented inside the `call_model` → `execute_or_hold_tools` → `call_model` cycle in the LangGraph.
- **Say:** "It's a ReAct-style loop, but with explicit approval nodes between reason and act."

### System Prompt / System Instruction
- **What:** The high-priority message that sets the agent's role, rules, and constraints for the whole conversation.
- **In your project:** The 20-rule `self.system_instruction` in `core.py` — includes task classification, self-recovery protocol, document rules, etc.
- **Say:** "The system prompt is my agent's constitution — task classification, HITL rules, and recovery behavior all live there."

### Context Window / Token Budget
- **What:** LLMs have a hard limit on how many tokens they can process; you must trim aggressively.
- **In your project:** `_trim_messages` (last 15 messages), `_conversation_summary` for rolling summary, EATP's 800-token cap.
- **Say:** "I budget context explicitly — 15 messages of history plus 800 tokens for retrieved experiences."

## 2. LangChain

### What LangChain Is
- **What:** A Python framework that abstracts LLM providers, tool schemas, message formats, and prompt templates behind a common API. Think of it as an ORM for LLMs.
- **In your project:** `ChatOpenAI` wraps the OpenAI client so you could swap to Claude/Gemini by changing one line; `bind_tools` attaches your tools to the model.

### Key LangChain Objects You Use

| Object | Purpose in your code |
|---|---|
| `ChatOpenAI` | LLM client, provider-agnostic wrapper |
| `SystemMessage` / `HumanMessage` / `AIMessage` / `ToolMessage` | Typed messages instead of raw dicts — safer, self-documenting |
| `StructuredTool` | LangChain's tool object built from a Pydantic schema |
| `bind_tools(tools)` | Attaches tools to the LLM so it emits proper `tool_calls` |
| `create_model` (Pydantic) | You generate Pydantic argument schemas dynamically from your JSON-Schema `ToolDefinition`s |

- **Say:** "LangChain gives me typed messages and a provider-agnostic LLM interface. I don't use its agent classes — my agent is custom on LangGraph."

### ApprovalAwareTool (Your Extension)
- **What:** You subclassed `StructuredTool` to carry a `requires_approval` boolean, because base LangChain has no such concept.
- **Say:** "I extended `StructuredTool` because LangChain doesn't model approval tiers natively — this is a first-class safety concept in my agent."

## 3. LangGraph

### What LangGraph Is
- **What:** A LangChain sub-library for building agents as **stateful graphs**: nodes are functions that transform state, edges route between them, and it compiles down to a runnable state machine.
- **In your project:** The whole agent loop in `_build_graph()` — five nodes, conditional routing, explicit start/end.

### Key LangGraph Concepts

| Concept | Meaning | In your code |
|---|---|---|
| `StateGraph(AgentState)` | Graph parameterized by a typed state schema | `AgentState` TypedDict with `messages`, `use_pending`, `dry_run_plan`, etc. |
| **Node** | A function `(state) → partial_state_update` | `classify_task`, `call_model`, `collect_dry_run`, `execute_or_hold_tools`, `format_output` |
| **Edge** | Unconditional next step | `classify_task → call_model` |
| **Conditional edge** | Routing function decides the next node from state | `route_after_model`, `route_after_tools` |
| `END` | Sentinel meaning "return the final state" | Used after `format_output` and after pending approvals |
| **Recursion limit** | Max node executions to prevent infinite loops | You set `25` |
| **State merging** | Return value is merged into the running state | Every node returns a partial dict |

- **Say:** "LangGraph gives me a compiled state machine where approval and safety are graph nodes, not `if` statements. Each node is testable in isolation."

### Why LangGraph over a plain while-loop
Three points to memorize:

1. **Explicit control flow** — safety gates are first-class nodes.
2. **Testability** — every node is a pure function of state, plus your `_test_fail_node` hook simulates node failures.
3. **Extensibility** — new features (retry branches, parallel execution) are edges, not surgery.

## 4. Retrieval, Embeddings, and Vector Databases (for EATP)

### Embedding
- **What:** A fixed-length vector (1536 floats for `text-embedding-3-small`) that represents the *meaning* of text. Similar meanings → similar vectors.
- **In your project:** Every experience's `task_description` is embedded; every incoming user message is embedded for retrieval.
- **Say:** "Embeddings turn language into geometry — similarity in vector space equals similarity in meaning."

### Cosine Similarity
- **What:** The cosine of the angle between two vectors, ∈ [-1, 1]. 1 means identical direction, 0 means unrelated.
- **In your project:** ChromaDB stores cosine *distance* (`1 - similarity`); you convert with `similarity = 1 - distance`. Thresholds: `0.75` to retrieve, `0.95` to dedup.
- **Say:** "I use cosine similarity because it's magnitude-invariant — long and short task descriptions get compared fairly."

### Vector Database
- **What:** A database indexed for fast nearest-neighbor search over embeddings, typically with HNSW or IVF-PQ under the hood.
- **In your project:** **ChromaDB** with HNSW cosine index, persisted to disk at `~/.ai_agent/experiences`.
- **Say:** "ChromaDB uses HNSW — approximate nearest neighbor with logarithmic query time — so retrieval stays fast even as the store grows."

### HNSW (Hierarchical Navigable Small World)
- **What:** The graph-based ANN algorithm ChromaDB uses. You don't implement it, but you should know the name.
- **Say:** "HNSW gives me sub-linear search over thousands of vectors."

### RAG (Retrieval-Augmented Generation)
- **What:** Retrieve relevant context, stuff it into the prompt, generate. Standard pattern for grounding LLMs.
- **In your project:** EATP is RAG — but over the agent's own past executions, not external docs. This is your differentiator.
- **Say:** "EATP is RAG applied to episodic memory instead of a document corpus."

### Re-ranking
- **What:** After vector retrieval, apply a secondary sort using signals the embedding didn't capture.
- **In your project:** Sort key `(has_corrections, is_failure, similarity × recency_factor)` — prioritizes lessons over confirmations.
- **Say:** "Vector similarity gets me candidates, re-ranking picks the pedagogically useful ones."

### Deduplication / Consolidation
- **What:** Prevent near-duplicates from flooding the store by merging them.
- **In your project:** Similarity > 0.95 → increment `confirmation_count`, refresh `last_validated`, merge corrections.
- **Say:** "Dedup keeps the store diverse — popular tasks don't drown out rare, valuable ones."

### Recency Decay
- **What:** Weight recent observations more than old ones.
- **In your project:** 1.0 for < 30 days, linear to 0.5 by 180 days; `confirmation_count` × 0.05 (capped at 0.3) boosts back.
- **Say:** "Older lessons decay unless the user keeps validating them."

### Episodic Memory (concept from cognitive science)
- **What:** Memory of specific events (vs. semantic memory of facts). Framing EATP this way sounds sophisticated.
- **Say:** "EATP gives the agent episodic memory — it remembers *when it did* something and *what happened*, not just *what to do*."

## 5. Protocol / Integration Layer

### MCP (Model Context Protocol)
- **What:** Anthropic's open standard for connecting LLM hosts to tool servers over JSON-RPC (usually over stdio or HTTP).
- **In your project:** `mcp_servers/github_server.py` and `mcp_servers/playwright_server.py` are FastMCP servers; your agent spawns them via `stdio_client` and calls them with `session.call_tool`.
- **Say:** "MCP means my GitHub and Playwright tools are interoperable — any MCP-compatible host, like Claude Desktop, could reuse them."

### JSON Schema
- **What:** The standard for describing JSON shapes — properties, types, required fields.
- **In your project:** Every `ToolDefinition.parameters` is a JSON Schema; the LLM uses it to construct valid `tool_calls`.

### stdio Transport
- **What:** Parent-child process communication via stdin/stdout, used by MCP.
- **In your project:** Your agent runs the MCP servers as subprocesses and exchanges JSON-RPC over their pipes.

## 6. Backend & Web Layer

### Django (MVT framework)
- **What:** Python web framework with a built-in ORM, admin, migrations, and URL router.
- **In your project:** `config/` is the Django project, `chat/` is the app with models (`ToolLog`, `ChatSession`), views (`chat_api`, `agent_control_api`), and URLs.
- **Say:** "Django gives me the API layer, ORM for audit logs, and session persistence for free."

### Django ORM & Migrations
- **What:** Model classes → SQL tables; `makemigrations` / `migrate` handles schema evolution.
- **In your project:** `chat/migrations/` shows the schema history — including the booking-model replacement (migration 0004).

### SQLite
- **What:** Serverless file-based SQL database. Great for dev, limited for production concurrency.
- **In your project:** `db.sqlite3` holds tool logs and chat sessions. You'd swap to Postgres in production.

### HTTP JSON API
- **What:** REST-ish endpoints that take/return JSON.
- **In your project:** `/api/chat/`, `/api/agent-control/`, `/api/chat-sessions/`. Understand the request/response shapes (especially the `status: dry_run | pending | success | error` envelope).

## 7. Concurrency & Systems

### Threading & GIL
- **What:** Python's Global Interpreter Lock makes single-instruction reads/writes atomic but composite operations still need locks.
- **In your project:** Django's dev server is multi-threaded; a stop request can arrive from one thread while the agent loop runs in another. `AgentControlState` uses `threading.Lock` to protect state.
- **Say:** "The lock isn't paranoia — Django is threaded, and I need composite operations on the control state to be atomic."

### Timeouts
- **What:** Bound external calls so a hung process doesn't hang the whole agent.
- **In your project:** LLM calls have `request_timeout=30`; `run_code` has a 30s timeout.

## 8. Human-in-the-Loop (HITL) & Safety

### Dry-Run Mode
- **What:** Preview all actions before executing any.
- **In your project:** `collect_dry_run` node bundles all `tool_calls` into a plan and returns `status=dry_run`; the frontend shows it, user approves.

### Per-Tool Approval
- **What:** After the plan runs, any *follow-up* tool with `requires_approval=True` triggers a `status=pending` return so the user gates it individually.
- **In your project:** `execute_or_hold_tools` node splits low-risk tools (auto-run) from high-risk (hold as `pending_tools`).

### Kill Switch
- **What:** A global flag that halts execution or disables all tools.
- **In your project:** `AgentControlState.stop()` and `disable_tools()`; checked before every tool dispatch and at the top of each node.

### Prompt Injection
- **What:** An attack where user input tries to override system instructions ("ignore previous instructions and...").
- **In your project:** `is_prompt_injection()` in `helpers.py` — regex heuristics on ~13 patterns. Weak but explicit; you cite the roadmap to ML-based detection.

### Audit Logging
- **What:** Persistent record of every action for post-hoc review.
- **In your project:** `ToolLog.objects.create(...)` on every tool call.

## 9. Evaluation Methodology (For The Paper)

### Benchmark Suite
- **What:** A fixed set of tasks with known correct outcomes.
- **In your project:** `evals/tasks.json` — 24+ tasks in categories (debugging, refactoring, multi-step).

### Ground-Truth Validators
- **What:** Per-task Python functions that check whether the agent actually produced the expected outcome (file exists, code runs, response mentions key term).
- **In your project:** `evals/validators.py` with `VALIDATORS` dict, `default_validator` fallback.

### Ablation Study
- **What:** Turn off individual components to isolate their contribution.
- **In your project:** `--eatp-mode off / cold / warm / warm-successes / static-fewshot` — this is the ablation matrix.

### Baseline / Control Condition
- **What:** A comparison against something simpler to prove your fancy thing is worth it.
- **In your project:** `off` is the baseline (no EATP); `static-fewshot` is a control (fixed examples vs. retrieved ones).

### Mocking
- **What:** Replace external APIs with deterministic fakes so runs are reproducible.
- **In your project:** `evals/mocks.py` with `MOCK_REGISTRY`.

### Metrics You Report
- Validated success rate (%)
- Overall completion rate (%)
- Tool efficiency (calls per successful task)
- Per-category breakdown
- Average duration
- **Say:** "I don't just measure success — I measure efficiency, because an agent that succeeds in 20 tool calls is worse than one that succeeds in 5."

## 10. Design Patterns You Should Name

| Pattern | Where |
|---|---|
| **Strategy** | Task classification picks between heavy/light LLM strategies |
| **State machine** | LangGraph — nodes are states, edges are transitions |
| **Decorator/wrapper** | `ApprovalAwareTool` wraps `StructuredTool` |
| **Adapter** | `tool_definition_to_langchain` adapts your `ToolDefinition` to LangChain's format |
| **Repository** | `ExperienceStore` abstracts ChromaDB behind `add / retrieve / format_for_prompt` |
| **Mixin** | `AgentMessagesMixin` extends `Agent` with message-conversion utilities |
| **Factory** | Dynamic Pydantic model creation via `create_model` |

---

# Recommended Study Order

If you have limited time, learn in this order — earlier concepts unlock the later ones:

1. **LLMs + tool calling** — the foundation (1 hour)
2. **LangChain messages + `ChatOpenAI` + `bind_tools`** — how you talk to the model (1 hour)
3. **LangGraph nodes, edges, state, conditional routing** — your control flow (2 hours)
4. **Embeddings + cosine similarity + vector DBs + HNSW + RAG** — EATP's foundation (2 hours)
5. **Your EATP additions: re-ranking, dedup, recency decay** — your novel contribution (1 hour)
6. **MCP + JSON Schema** — external integrations (1 hour)
7. **Django models/views + threading + SQLite** — the boring-but-necessary layer (1 hour)
8. **HITL patterns + prompt injection** — safety story (30 min)
9. **Evaluation methodology + ablation studies** — how you defend the paper (1 hour)

**Total: ~10 hours to master enough to explain any part fluently.**

The single most important concept to over-prepare is **LangGraph** — it's the least-familiar to most interviewers, so if you can explain it clearly, you sound like the expert in the room. The single most important concept for your **paper** is **RAG-over-episodic-memory with correction-weighted re-ranking** — that's your abstract in one phrase.
