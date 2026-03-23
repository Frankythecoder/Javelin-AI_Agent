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
User Request → retrieve_experiences → augment_prompt → classify_task → call_model → dry-run plan → approval → execute → log_experience
```

Two new nodes are added to the existing LangGraph:

1. **`retrieve_experiences`** (before planning) — Embeds the user's request, queries a vector store for similar past tasks, and injects the top matches into the system prompt as "lessons learned."
2. **`log_experience`** (after execution) — Captures the full execution record: what was asked, what was planned, what tools ran, what succeeded/failed, and any user corrections.

### New Components
- `agents/experience_store.py` — Vector store wrapper (ChromaDB)
- `agents/experience_logger.py` — Captures and structures execution records
- Enhancement to `agents/core.py` — Two new LangGraph nodes + prompt augmentation logic

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
```

### Key Design Decision
The `user_corrections` field is the most valuable part. When a user denies a tool call and the agent recovers with a different approach, that correction gets captured as a lesson. Next time a similar task comes up, the agent already knows the preferred approach.

### Storage
ChromaDB (local, file-based, no server needed). Each record is embedded by its `task_description` and stored with all other fields as metadata. The existing `ToolLog` Django model stays as-is — EATP is a parallel system, not a replacement.

---

## 4. Experience Retrieval & Prompt Augmentation

### Retrieval Step

When a new user request comes in:
1. Embed the request using OpenAI's `text-embedding-3-small` ($0.02 per 1M tokens)
2. Query ChromaDB for the 3-5 most similar past experiences (cosine similarity, threshold > 0.75)
3. Filter: only retrieve experiences with `outcome != "success"` OR those that have `user_corrections` — the agent learns more from mistakes and corrections than from things that went fine

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
One new tool:

```
rate_experience:
    description: "Rate how well the agent handled the last task"
    parameters:
        rating: int (1-5)
        feedback: str (optional, what could be improved)
```

The agent asks for this at the end of complex tasks but does not nag. When provided, it gets attached to the experience record and heavily weighted during retrieval (an experience rated 1/5 with feedback is the most valuable lesson in the store).

### 5.4 Deduplication
If the agent encounters the same correction multiple times, it consolidates rather than storing duplicates. A similarity check: if a new experience is >0.95 cosine similarity to an existing one with the same lesson, update the existing record's confidence score instead of creating a new one.

---

## 6. Evaluation Design

### Experiment 1: Learning Curve (primary claim)

Run the eval task suite in three phases:
- **Phase A — Cold start:** Run all tasks with an empty experience store. Record success rate, tool efficiency, cost per task. This is the baseline.
- **Phase B — Seeded failures:** Run the same tasks again, injecting corrections during Phase A runs (deny certain tools, redirect approaches). The experience store accumulates lessons.
- **Phase C — Warm start:** Run the exact same tasks with the populated experience store. Measure the same metrics.

The difference between Phase A and Phase C is the primary result.

### Experiment 2: Cross-task Transfer

Test whether lessons from one task improve different but related tasks:
- Correct the agent on "delete old log files" (teach it to list before deleting)
- Then ask it to "clean up temp files from the build directory" (never seen before)
- Measure whether the learned lesson transfers

### Experiment 3: Comparison with Baselines

Run the same task suite on three configurations:
- **Baseline A:** Agent without EATP (current system)
- **Baseline B:** Agent with static few-shot examples hardcoded in the prompt (no retrieval, manually written)
- **EATP:** Agent with the full experience system

This isolates whether dynamic retrieval matters, or if static examples would suffice.

### Metrics

| Metric | What it measures |
|--------|-----------------|
| Task success rate (%) | Does it complete correctly? |
| Tool efficiency ratio | Tools used / minimum tools needed |
| Plan revision rate (%) | How often the user corrects the plan |
| Cost per task ($) | API token spending |
| Correction carryover rate (%) | If corrected on task X, does it avoid the same mistake on similar task Y? |

### Scale
Expand the eval suite from 35 to ~100 tasks (add variations of existing categories). 100 tasks across 3 conditions = 300 runs.

### Optional: User Study
If feasible, recruit 10-15 classmates to use both the baseline and EATP versions for a set of tasks. Measure task completion time, correction frequency, and subjective satisfaction (Likert scale survey). This would strengthen the paper significantly but is not required.

---

## 7. Paper Structure

**Title:** *"Experience-Augmented Tool Planning: Self-Improving LLM Agents Through Execution History Retrieval"*

### Sections

1. **Introduction** — The problem: agents repeat mistakes across sessions. Motivating example.
2. **Related Work** — ReAct agents, AutoGPT, LangChain, Voyager (skill library), Reflexion (self-reflection without persistent memory), MemGPT (memory management, not tool-planning focused). EATP fills the gap.
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

### Files to Modify
- `agents/core.py` — Add two LangGraph nodes, augment system prompt
- `agents/control.py` — Add `rate_experience` tool definition
- `evals/runner.py` — Support EATP-aware evaluation (cold/warm modes)
- `evals/tasks.json` — Expand from 35 to ~100 tasks

### Estimated Timeline
- Weeks 1-2: Experience store + logger
- Weeks 3-4: LangGraph integration + prompt augmentation
- Weeks 5-6: Feedback loop (denial, correction, explicit)
- Weeks 7-8: Expand eval suite to 100 tasks
- Weeks 9-11: Run experiments 1-3, collect results
- Weeks 12-14: Write paper draft
- Weeks 15-16: Revisions and submission
- Remaining months: User study (optional), conference revisions
