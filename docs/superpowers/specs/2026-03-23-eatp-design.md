# Experience-Augmented Tool Planning (EATP): Design Specification

**Date:** 2026-03-23
**Status:** Approved
**Author:** Frank
**Target:** CS/AI or Software Engineering conference paper (final year project)

---

## 1. Problem Statement

LLM-based tool-using agents start from scratch every session. If a user corrects the agent's approach (e.g., "don't delete that file, rename it instead"), the agent has no mechanism to carry that lesson forward. The same mistake recurs in every new conversation.

This project already has a capable agent with 40+ tools, dry-run planning, dual-model routing, and human-in-the-loop approval. EATP adds a persistent learning layer on top: the agent retrieves relevant past experiences — especially user corrections — before planning new tasks, and improves over time without fine-tuning.

---

## 2. Architecture Overview

### Current Flow
```
User Request → classify_task → call_model (with tools) → dry-run plan → approval → execute
```

### New Flow with EATP
```
User Request → [retrieve_experiences + augment_prompt] → classify_task → call_model → dry-run plan → approval → execute → [log_experience]
```

### Integration Point (in `chat_once()`)

Experience retrieval and prompt augmentation happen inside `chat_once()` (around line 479 of `core.py`), **before** constructing `initial_state` and invoking the graph. This avoids restructuring the LangGraph itself:

1. **Before graph invocation:** Call `experience_store.retrieve(user_message)` to get relevant past experiences. Format them into a "Lessons from Past Experience" section. Append this section to the system message that `chat_once()` already constructs.
2. **After graph completes:** Call `experience_logger.log(...)` with the full execution context (plan, tools used, outcomes, user corrections). This runs after the graph returns, not as a graph node.

The `log_experience` step is a post-execution call in `chat_once()`, not a LangGraph node, since it needs the full execution trace which is only available after the graph finishes.

### New Components
- `agents/experience_store.py` — ChromaDB wrapper: store, retrieve, deduplicate
- `agents/experience_logger.py` — Captures and structures experience records
- Enhancement to `agents/core.py` — Retrieval + augmentation in `chat_once()` before graph invocation, logging after graph completion

### What Stays Unchanged
- All existing tools and their implementations
- The dry-run planning mechanism
- The approval routing system (requires_approval flag)
- The dual-model task classification
- The conversation memory / message trimming system
- Django models, views, TUI

---

## 3. Experience Record Schema

Every completed task gets stored as an experience record:

```
ExperienceRecord:
    # Identity
    id: str (uuid)
    created_at: datetime

    # What was asked
    task_description: str          # Original user message
    task_category: str             # "file_ops", "code", "travel", "document", etc.
    task_complexity: str           # "heavy" or "light" (from existing classifier)

    # What was planned
    plan_summary: str              # The dry-run plan text
    tools_planned: list[str]       # ["read_file", "create_and_edit_file", ...]

    # What actually happened
    tools_executed: list[str]      # Tools that actually ran
    tool_results: list[dict]       # {tool_name, args_summary, success: bool, error: str|null}
    outcome: str                   # "success", "partial", "failure"

    # What the human corrected
    user_corrections: list[str]    # e.g., ["User denied delete_file, used rename_file instead"]
    approval_actions: list[dict]   # {tool_name, action: "approved"|"denied"|"modified"}

    # For retrieval
    embedding: list[float]         # Vector embedding of task_description

    # Learning metadata
    last_validated: datetime       # Updated when the same lesson is confirmed again
    confirmation_count: int        # How many times this lesson has been re-confirmed (resists decay)

    # Versioning
    schema_version: int            # Current version: 1. Increment on breaking changes.
    embedding_model: str           # e.g., "text-embedding-3-small". Used to detect incompatible embeddings.
```

### `args_summary` Format

Tool arguments can contain large content blobs (e.g., an entire file for `create_and_edit_file`). Raw arguments must not be stored directly. `args_summary` is a structured summary:
- For file tools: `{path: "foo.py", content_length: 1500}` (path + content size, not content itself)
- For code tools: `{command: "python test.py"}` (command string, truncated to 200 chars)
- For travel tools: `{origin: "LAX", destination: "JFK", date: "2026-05-15"}`
- General rule: include identifying parameters (paths, names, codes), replace large content with length/type metadata, truncate any field at 200 characters

### Key Design Decision
The `user_corrections` field is the most valuable part. When a user denies a tool call and the agent recovers with a different approach, that correction gets captured as a lesson. Next time a similar task comes up, the agent already knows the preferred approach.

### Storage
ChromaDB (local, file-based, no server needed). Each record is embedded by its `task_description` and stored with all other fields as metadata. The existing `ToolLog` Django model stays as-is — EATP is a parallel system, not a replacement.

### Concurrency
The experience store operates in single-writer mode. ChromaDB's local persistence is not designed for concurrent writers. Since the Django app supports multiple `ChatSession` objects, the ChromaDB client is instantiated once at module level with a file lock to prevent concurrent writes. For this research prototype, this is acceptable — concurrent sessions will queue writes sequentially.

### Embedding Migration
If the embedding model changes (e.g., from `text-embedding-3-small` to a newer version), old embeddings become incompatible. The `schema_version` and `embedding_model` fields on each record enable detection. A migration script (`agents/migrate_experiences.py`) will re-embed all records using the new model when needed.

### Data Privacy
Experience records contain user messages and tool argument summaries, which may include file paths or code references. All data is stored locally (ChromaDB's persistent directory, default `~/.ai_agent/experiences/`). For the user study, participant data will be anonymized (task descriptions stripped of PII) before inclusion in any published results.

---

## 4. Experience Retrieval & Prompt Augmentation

### Retrieval Step

When a new user request comes in:
1. Embed the request using OpenAI's `text-embedding-3-small` ($0.02 per 1M tokens)
2. Query ChromaDB for the 3-5 most similar past experiences (cosine similarity, threshold > 0.75)
3. Retrieve top-5 results. Re-rank so experiences with `user_corrections` appear first (highest priority), followed by failures, then successes. Successful experiences without corrections are included but weighted lower — positive patterns are still useful for reinforcing good behavior

### Prompt Augmentation

Retrieved experiences get injected into the system prompt as a new section:

```
## Lessons from Past Experience

TASK: "Delete the old log files from the project directory"
OUTCOME: partial failure
LESSON: User denied delete_file for .log files in project root.
User corrected: "Use list_files first to show me which files before deleting."
PREFERRED APPROACH: Always list files before destructive operations. Ask for confirmation with specific file list.

TASK: "Create a PDF report from the meeting notes"
OUTCOME: success
LESSON: User had a .docx file, not plain text. Used read_docx first to extract content, then create_pdf.
PREFERRED APPROACH: When user mentions "notes" or "document", check for existing files before assuming raw text input.
```

### Token Budget

The existing system prompt is ~2000 tokens. Injected experience context is capped at **800 tokens**. If retrieved experiences exceed this budget, they are ranked by relevance score and the lowest-ranked experiences are dropped until the budget is met. Each experience entry is ~100-150 tokens, so the typical injection is 3-5 experiences.

This keeps the total system prompt under 3000 tokens, leaving ample room for tool definitions and conversation history within the context window.

### Properties
- Cost: one embedding call (~$0.0001) + one ChromaDB query (~5ms). Negligible.
- Cold start: when there are no past experiences, the agent behaves exactly as it does today. EATP is purely additive.
- No extra LLM calls beyond what already exist — experiences go into the existing system prompt.

---

## 5. Feedback Loop

Three types of feedback, captured with minimal friction:

### 5.1 Denial Feedback (automatic)
When a user denies a tool in the approval step, the system logs:
- Which tool was denied
- What arguments it had
- What the agent did instead (if it recovered)

Already captured by `execute_or_hold_tools`. The new code listens for denial events and writes them to the experience record.

### 5.2 Correction Feedback (automatic)
When the agent's dry-run plan gets rejected and the user provides a corrective instruction (e.g., "no, don't delete it, just rename it"), the system detects the gap between the original plan and the revised execution. This gets stored as a `user_correction`.

Leverages the same pattern-matching approach used by `_detect_interrupted_task()` in `agent_messages.py`.

### 5.3 Explicit Feedback (new tool, optional)
One new tool, defined in a new file `agents/feedback_tools.py` (consistent with the project's pattern of one tool file per domain):

```
rate_experience:
    description: "Rate how well the agent handled the last task"
    parameters:
        rating: int (1-5)
        feedback: str (optional, what could be improved)
```

The agent asks for this at the end of complex tasks but does not nag. When provided, it gets attached to the experience record and heavily weighted during retrieval (an experience rated 1/5 with feedback is the most valuable lesson in the store).

### 5.4 Confidence Decay
Experiences from early sessions may reflect inconsistent user behavior or evolving preferences. To address this:
- Each experience has a `last_validated` timestamp, updated when the same lesson is confirmed again (i.e., a similar correction is made)
- During retrieval, results are weighted by recency: `weight = relevance_score * recency_factor`, where `recency_factor = 1.0` for experiences < 30 days old, decaying linearly to `0.5` for experiences > 180 days old
- Experiences that are repeatedly validated (high confirmation count) resist decay

### 5.5 Deduplication
If the agent encounters the same correction multiple times, it consolidates rather than storing duplicates. A similarity check: if a new experience is >0.95 cosine similarity to an existing one with the same lesson, update the existing record's confidence score instead of creating a new one.

---

## 6. Evaluation Design

### Experiment 1: Learning Curve (primary claim)

Run the eval task suite in three phases:
- **Phase A — Cold start:** Run all tasks with an empty experience store. Record success rate, tool efficiency, cost per task. This is the baseline.
- **Phase B — Seeded failures:** Run the same tasks again, injecting corrections via a **correction script** — a JSON file (`evals/correction_policy.json`) that maps task IDs to specific denial/correction actions (e.g., `{"task_12": {"deny": "delete_file", "correction": "Use list_files first, then ask for confirmation"}}`). The eval runner is extended to apply these policies automatically instead of auto-approving, ensuring reproducibility. The experience store accumulates lessons.
- **Phase C — Warm start:** Run the exact same tasks with the populated experience store. Measure the same metrics.

The difference between Phase A and Phase C is the primary result.

### Experiment 2: Cross-task Transfer

Test whether lessons from one task improve different but related tasks:
- Correct the agent on "delete old log files" (teach it to list before deleting)
- Then ask it to "clean up temp files from the build directory" (never seen before)
- Measure whether the learned lesson transfers

### Experiment 3: Comparison with Baselines

Run the same task suite on four configurations:
- **Baseline A:** Agent without EATP (current system)
- **Baseline B:** Agent with static few-shot examples hardcoded in the prompt (no retrieval, manually written)
- **Baseline C:** Agent with EATP retrieval but using only successful experiences (no correction data) — isolates the contribution of correction-based learning specifically
- **EATP (full):** Agent with the full experience system including corrections

This isolates: (1) whether any examples help vs. none (A vs B), (2) whether dynamic retrieval beats static examples (B vs EATP), and (3) whether corrections specifically matter (C vs EATP).

### Metrics

| Metric | What it measures |
|--------|-----------------|
| Task success rate (%) | Does it complete correctly? |
| Tool efficiency ratio | Tools used / minimum tools needed |
| Plan revision rate (%) | How often the user corrects the plan |
| Cost per task ($) | API token spending |
| Correction carryover rate (%) | If corrected on task X, does it avoid the same mistake on similar task Y? |

### Scale
Expand the eval suite from 35 to ~100 tasks. Target distribution by category:
- 15 file operations (search, read, create, edit, delete, rename)
- 15 code tasks (execution, syntax check, testing, linting, debugging)
- 15 document creation/editing (PDF, DOCX, XLSX, PPTX)
- 10 travel/booking (search, book, retrieve, cancel)
- 10 GitHub operations (branch, commit, PR, issue)
- 10 multimedia (image, video, audio recognition)
- 10 multi-tool orchestration (tasks requiring 3+ tools in sequence)
- 15 cross-category tasks (e.g., "read this PDF and email a summary")

100 tasks across 4 conditions = 400 runs.

### Optional: User Study
If feasible, recruit 10-15 classmates to use both the baseline and EATP versions for a set of tasks. Measure task completion time, correction frequency, and subjective satisfaction (Likert scale survey). This would strengthen the paper significantly but is not required.

---

## 7. Paper Structure

**Title:** *"Experience-Augmented Tool Planning: Self-Improving LLM Agents Through Execution History Retrieval"*

### Sections

1. **Introduction** — The problem: agents repeat mistakes across sessions. Motivating example.
2. **Related Work** — ReAct agents, AutoGPT, LangChain, Voyager (skill library), Reflexion (self-reflection without persistent memory), MemGPT (memory management, not tool-planning focused), ToolBench/ToolLLM (tool-using benchmarks and tool selection). EATP fills the gap between memory systems and tool-planning frameworks.
3. **System Architecture** — Existing agent (LangGraph, dual-model, dry-run, approval routing) + the EATP layer.
4. **Experience-Augmented Tool Planning** — Core contribution: record schema, retrieval, prompt augmentation, feedback loop, deduplication.
5. **Evaluation** — Experiments 1-3 with tables and learning curve graphs.
6. **Discussion** — Limitations (API-dependent, no fine-tuning, cold start), threats to validity, future work.
7. **Conclusion**

### Target Venues
- AAAI / IJCAI workshop on LLM agents
- ASE / ICSE NIER track (new ideas, short paper)
- AAMAS (agent self-improvement angle)
- arXiv preprint for immediate priority

---

## 8. Implementation Notes

### Dependencies to Add
- `chromadb` — local vector store
- `openai` embeddings (already have openai dependency)

### Files to Create
- `agents/experience_store.py` — ChromaDB wrapper: store, retrieve, deduplicate
- `agents/experience_logger.py` — Build ExperienceRecord from execution context

### Files to Create (additional)
- `agents/feedback_tools.py` — `rate_experience` tool definition (follows project convention of one tool file per domain)
- `agents/migrate_experiences.py` — Re-embedding migration script for model version changes
- `evals/correction_policy.json` — Maps task IDs to denial/correction actions for reproducible Phase B experiments

### Files to Modify
- `agents/core.py` — Add retrieval + augmentation in `chat_once()` before graph invocation, logging after graph completion
- `agents/__init__.py` — Export new tool definitions
- `evals/runner.py` — Support EATP-aware evaluation (cold/warm modes, correction policy application)
- `evals/tasks.json` — Expand from 35 to ~100 tasks with balanced category distribution

### Estimated Timeline
- Weeks 1-2: Experience store + logger
- Weeks 3-4: LangGraph integration + prompt augmentation
- Weeks 5-6: Feedback loop (denial, correction, explicit)
- Weeks 7-8: Expand eval suite to 100 tasks
- Weeks 9-11: Run experiments 1-3, collect results
- Weeks 12-14: Write paper draft
- Weeks 15-16: Revisions and submission
- Remaining months: User study (optional), conference revisions
