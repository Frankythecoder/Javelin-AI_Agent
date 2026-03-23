# EATP Evaluation Expansion & Ablation Baselines — Design Spec

**Date:** 2026-03-23
**Status:** Approved
**Depends on:** `2026-03-23-eatp-design.md` (core EATP system)

---

## 1. Problem Statement

The current eval suite has 35 tasks with a shallow success metric (string error checking) that yields 100% pass rate across all phases. This makes it impossible to demonstrate EATP improvement. Additionally, the experiment lacks ablation baselines — reviewers cannot isolate what makes EATP work without comparing against static few-shot prompting and retrieval-without-corrections.

This spec covers:
1. Expanding the eval suite to 100 tasks with ground-truth validation
2. Adding mock infrastructure for external API tools
3. Adding two ablation baselines (static few-shot, successes-only)
4. Generating paper-quality figures from experiment results
5. Isolating task workspaces to prevent cross-contamination

---

## 2. Task Distribution

### 2.1 Overview

100 tasks total, three classes:
- **20 Correctable tasks** — the agent's naive approach has a common pitfall. Phase B correction policy denies the wrong tool and teaches the right approach.
- **20 Transfer tasks** — similar to correctable tasks but never seen during Phase B. Tests whether lessons generalize to unseen-but-related tasks.
- **60 Standard tasks** — mix of easy/medium difficulty for baseline coverage.

### 2.2 Category Distribution

| Category | Correctable | Transfer | Standard | Total | ID Range |
|----------|------------|----------|----------|-------|----------|
| File Operations | 4 | 4 | 7 | 15 | task_001 – task_015 |
| Code Tasks | 4 | 4 | 7 | 15 | task_016 – task_030 |
| Document Creation/Editing | 3 | 3 | 9 | 15 | task_031 – task_045 |
| Travel/Booking | 2 | 2 | 6 | 10 | task_046 – task_055 |
| GitHub Operations | 2 | 2 | 6 | 10 | task_056 – task_065 |
| Multimedia | 2 | 2 | 6 | 10 | task_066 – task_075 |
| Multi-tool Orchestration | 2 | 2 | 6 | 10 | task_076 – task_085 |
| Cross-category | 1 | 1 | 13 | 15 | task_086 – task_100 |
| **Total** | **20** | **20** | **60** | **100** | |

### 2.3 Task Schema

Each task in `tasks.json`:

```json
{
    "id": "task_016",
    "category": "Code Tasks",
    "task_class": "correctable",
    "lesson_id": "L2",
    "prompt": "Edit config.yaml to add a new database host entry under the 'databases' section.",
    "expected_output": "config.yaml contains the new database host entry without losing existing content.",
    "seed_files": [{"name": "config.yaml", "source": "seeds/config.yaml"}]
}
```

Fields:
- `task_class`: `"correctable"`, `"transfer"`, or `"standard"`
- `lesson_id`: which lesson this task teaches or tests (null for standard tasks)
- `seed_files`: optional list of files to pre-populate in the task workspace
- All other fields same as current schema

### 2.4 Replacement of Explain-only Tasks

The 8 explain-only tasks (old task_028–task_035) are removed entirely. Those categories (travel, GitHub, email, browser) are now covered by mock-backed execution tasks.

---

## 3. Correction Lessons

### 3.1 Ten Reusable Lessons

Each lesson is taught by 2 correctable tasks and tested by 2 transfer tasks.

| ID | Lesson | Denied Tool | Correction Text |
|----|--------|-------------|-----------------|
| L1 | List before destructive ops | `delete_file` / `rename_file` | "Use list_files first to show affected files before modifying." |
| L2 | Read before editing | `create_and_edit_file` | "Use read_file first to understand current contents. Never edit blind." |
| L3 | Syntax check before running | `run_code` | "Use check_syntax to catch errors before executing." |
| L4 | Verify dependencies first | `run_code` | "Check if required packages are installed before running scripts." |
| L5 | Inspect data before processing | `run_code` / `create_and_edit_file` | "Read source data to verify structure before writing processing code." |
| L6 | Confirm before bulk operations | `delete_file` | "List all affected items and show count before bulk actions." |
| L7 | Read docs before creating | `create_pdf` / `create_docx` | "Read any existing document or template first before creating new." |
| L8 | Verify results before committing | `book_travel` / `github_create_pr` | "Review search/list results before committing to an action." |
| L9 | Check file format before converting | `run_code` | "Read file header to verify format before running conversion." |
| L10 | Validate output after creation | `create_and_edit_file` | "After creating a file, use read_file to verify it contains what you intended." |

### 3.2 Transfer Map

`evals/transfer_map.json` links transfer tasks to the correctable tasks that teach the relevant lesson:

```json
{
    "task_005": {"lesson_id": "L1", "source_tasks": ["task_001", "task_002"]},
    "task_006": {"lesson_id": "L1", "source_tasks": ["task_001", "task_002"]},
    "task_020": {"lesson_id": "L2", "source_tasks": ["task_016", "task_017"]}
}
```

The comparison script uses this to measure per-lesson carryover rate on both correctable and transfer tasks separately.

### 3.3 Correction Policy

`evals/correction_policy.json` contains entries for all 20 correctable tasks (keyed by task ID), using the lesson's denied tool and correction text. Same schema as current:

```json
{
    "task_001": {
        "deny": "delete_file",
        "correction": "Use list_files first to show affected files before modifying."
    }
}
```

---

## 4. Mock System for External APIs

### 4.1 Purpose

Travel, GitHub, Gmail, and Playwright tools require real API access. Mocks provide deterministic responses so eval results are reproducible without external dependencies.

### 4.2 File: `evals/mocks.py`

A `MOCK_REGISTRY` dict mapping tool names to lambda functions that accept the tool's `args` dict and return a realistic response string.

**Mocked tools (12):**
- Travel: `search_flights`, `book_travel`, `get_booking`, `cancel_booking`, `list_bookings`
- GitHub: `github_create_branch`, `github_commit_file`, `github_commit_local_file`, `github_create_pr`, `create_github_issue`
- Email: `open_gmail_and_compose`
- Browser: `playwright_navigate`

**Properties:**
- Responses are realistic enough for the LLM to reason about (include IDs, status fields, data)
- Deterministic — same input produces same output across runs
- Lambdas reference tool arguments where relevant (e.g., branch name, recipient email)

### 4.3 Runner Integration

The runner wraps the agent's tool execution. Before calling the real `_execute_tool_by_name`, it checks `MOCK_REGISTRY`:

```python
from evals.mocks import MOCK_REGISTRY

original_execute = agent._execute_tool_by_name

def mock_aware_execute(name, args):
    if name in MOCK_REGISTRY:
        return MOCK_REGISTRY[name](args)
    return original_execute(name, args)

agent._execute_tool_by_name = mock_aware_execute
```

This is applied once after agent creation, before the task loop begins. Local tools (file ops, code execution, documents, multimedia) are NOT mocked — they run for real.

---

## 5. Validation System

### 5.1 Two-tier Design

**Tier 1 — Lightweight validators (60 standard tasks):**
Single-condition checks: file exists, file contains string, response mentions keyword, tool was called.

**Tier 2 — Full validators (20 correctable + 20 transfer tasks):**
Composite checks that verify the agent followed the correct approach: tool ordering, specific tool called before another, file contents + correct process.

### 5.2 File: `evals/validators.py`

**Primitive validators (return a callable):**

| Validator | Signature | What it checks |
|-----------|-----------|---------------|
| `file_exists(path)` | `(result, workdir) -> bool` | File was created at path |
| `file_contains(path, substring)` | `(result, workdir) -> bool` | File exists and contains substring |
| `response_mentions(keyword)` | `(result, workdir) -> bool` | Agent response contains keyword |
| `tool_was_called(tool_name)` | `(result, workdir) -> bool` | Tool appears in execution history |
| `script_runs(path)` | `(result, workdir) -> bool` | Python script executes with return code 0 |
| `tool_called_before(before, after)` | `(result, workdir) -> bool` | `before` tool appears earlier in history than `after` |
| `correct_tool_order(*tools)` | `(result, workdir) -> bool` | Tools appear in specified order (not necessarily adjacent) |
| `composite(*validators)` | `(result, workdir) -> bool` | All inner validators pass |

**Validator registry:**

```python
VALIDATORS = {
    "task_001": composite(
        tool_called_before("list_files", "delete_file"),
        response_mentions("deleted"),
    ),
    "task_016": composite(
        file_exists("config.yaml"),
        tool_called_before("read_file", "create_and_edit_file"),
    ),
    "task_042": file_exists("report.pdf"),
    # ... one entry per task
}
```

**Default validator** (for tasks without an explicit entry): checks `tool_was_called` for at least one tool and response does not start with "Error".

### 5.3 Runner Integration

After each task completes:

```python
validator = VALIDATORS.get(task['id'], default_validator)
validated = validator(response_data, task_workdir)
result["validated"] = validated
```

The comparison script (`compare_phases.py`) is updated to use the `validated` field as the primary success metric instead of the old string-matching `status` field. The old `status` field is kept for backwards compatibility.

---

## 6. Runner Modes

### 6.1 Five Configurations

| Mode | CLI Flag | Experience Store | Retrieval | Corrections in Prompt | Static Examples |
|------|----------|-----------------|-----------|----------------------|-----------------|
| Off | `--eatp-mode off` | None | No | No | No |
| Cold | `--eatp-mode cold` | Fresh empty | Yes (returns nothing) | Yes (if any) | No |
| Static Few-shot | `--eatp-mode static-fewshot` | None | No | No | Yes (hardcoded) |
| Warm Successes-only | `--eatp-mode warm-successes` | Phase B populated | Yes | **Stripped** | No |
| Warm (full EATP) | `--eatp-mode warm` | Phase B populated | Yes | Yes | No |

### 6.2 File: `evals/static_fewshot.py`

Contains a `STATIC_EXAMPLES` string constant with 10 manually written guidelines — one per lesson from Section 3.1. These are the same lessons EATP would learn dynamically, presented as static text. This is the fairest comparison: same knowledge, different delivery mechanism.

### 6.3 Runner Changes

```python
# New mode: static-fewshot
if eatp_mode == 'static-fewshot':
    agent.experience_store = None
    from evals.static_fewshot import STATIC_EXAMPLES
    agent.system_instruction += "\n\n" + STATIC_EXAMPLES

# New mode: warm-successes
elif eatp_mode == 'warm-successes':
    agent.experience_store = ExperienceStore(persist_dir=experience_dir)
    original_format = agent.experience_store.format_for_prompt
    def format_without_corrections(records):
        for r in records:
            r.user_corrections = []
        return original_format(records)
    agent.experience_store.format_for_prompt = format_without_corrections
```

### 6.4 Experiment Protocol

Run in this order:

```bash
# 1. Baseline: No EATP
python evals/runner.py --eatp-mode off --output results_off.json

# 2. Static few-shot
python evals/runner.py --eatp-mode static-fewshot --output results_static_fewshot.json

# 3. Phase A: Cold start (empty store, EATP active but no experiences)
python evals/runner.py --eatp-mode cold --output results_phase_a.json

# 4. Phase B: Seeded corrections (populates experience store)
python evals/runner.py --eatp-mode cold --correction-policy correction_policy.json --output results_phase_b.json

# 5. Warm successes-only (retrieval but corrections stripped)
python evals/runner.py --eatp-mode warm-successes --output results_warm_successes.json

# 6. Phase C: Full EATP warm start
python evals/runner.py --eatp-mode warm --output results_phase_c.json
```

100 tasks x 6 configs = 600 runs. At ~15 seconds per task with rate limiting, expect ~2.5 hours total.

---

## 7. Working Directory Isolation

### 7.1 Problem

The current runner reuses the same working directory for all tasks. File-creating tasks contaminate subsequent tasks.

### 7.2 Design

Each task gets a fresh temporary directory:

1. Before each task: create `tempfile.mkdtemp(prefix=f"eatp_eval_{task_id}_")`
2. Copy seed files (if specified in `task.seed_files`) from `evals/seeds/` to the temp dir
3. Set the agent's working directory to the temp dir
4. Run the task
5. Run the validator against the temp dir
6. Cleanup the temp dir

### 7.3 Seed Files

`evals/seeds/` directory contains small template files needed by specific tasks:
- `config.yaml` — sample config for edit tasks
- `data.csv` — sample CSV for data processing tasks
- `buggy.py` — sample file with intentional error for debugging tasks
- `template.docx` — sample document for document editing tasks
- etc.

Tasks that don't need pre-existing files have an empty `seed_files` list and start with an empty workspace.

---

## 8. Figure Generation

### 8.1 File: `evals/generate_figures.py`

Reads all 6 result files and produces 4 matplotlib charts.

### 8.2 Figures

**Figure 1 — Success Rate Bar Chart:**
Grouped bars for the 5 configs (off, static-fewshot, cold, warm-successes, warm). Uses `validated` field. Error bars from per-category variance. This is the paper's headline result.

**Figure 2 — Tool Efficiency Bar Chart:**
Average tool calls per validated task for each config. Lower is better.

**Figure 3 — Category Heatmap:**
Success rate per category per config. Green color gradient. 8 rows (categories) x 5 columns (configs). Shows which categories benefit most from EATP.

**Figure 4 — Correction Carryover Chart:**
Horizontal bar chart with one bar per lesson (L1–L10). Each bar shows two segments: carryover rate on correctable tasks (expected high) and carryover rate on transfer tasks (the paper's strongest evidence). Overall rate displayed.

### 8.3 Output

- Individual PNGs: `evals/figures/fig1_success_rate.png`, etc.
- Combined 2x2 grid: `evals/figures/fig_all.png`
- Consistent styling: 10pt font, colorblind-safe palette, 3.5" width (single-column conference format)

### 8.4 Input

```python
RESULT_FILES = {
    "Off": "results_off.json",
    "Static Few-shot": "results_static_fewshot.json",
    "Cold (Phase A)": "results_phase_a.json",
    "Warm (succ. only)": "results_warm_successes.json",
    "Warm (full EATP)": "results_phase_c.json",
}
```

Phase B results are not plotted (they are the training phase, not a config comparison).

---

## 9. File Structure

```
evals/
  tasks.json                  # 100 tasks (expanded from 35)
  correction_policy.json      # 20 correctable task entries
  transfer_map.json           # 20 transfer task -> source mapping
  validators.py               # Lightweight + full validators
  mocks.py                    # Mock responses for external API tools
  static_fewshot.py           # Hardcoded examples for Baseline B
  runner.py                   # Modified: 5 modes, validators, mocks, workspace isolation
  compare_phases.py           # Updated: uses validated field, supports 5 configs
  generate_figures.py         # Matplotlib figure generation
  seeds/                      # Template files for tasks that need pre-existing files
    config.yaml
    data.csv
    buggy.py
    ...
  figures/                    # Generated charts (gitignored)
    fig1_success_rate.png
    fig2_tool_efficiency.png
    fig3_category_heatmap.png
    fig4_correction_carryover.png
    fig_all.png
```

---

## 10. Changes to Existing Files

### 10.1 `evals/runner.py`

- Add `static-fewshot` and `warm-successes` to `--eatp-mode` choices
- Add mock interception after agent creation
- Add workspace isolation (tempdir per task)
- Add validator call after each task, store `validated` field in results
- Import from `mocks.py`, `validators.py`, `static_fewshot.py`

### 10.2 `evals/compare_phases.py`

- Support 5+ configs (not just 3 phases)
- Use `validated` field as primary success metric
- Load `transfer_map.json` for per-lesson carryover analysis on transfer tasks specifically

### 10.3 No changes to core EATP files

`agents/core.py`, `agents/experience_store.py`, `agents/experience_logger.py`, `agents/feedback_tools.py` — no modifications needed. The eval expansion is entirely within `evals/`.

---

## 11. What This Spec Does NOT Cover

- Writing the actual 100 task prompts (deferred to implementation plan)
- Writing the actual seed files (deferred to implementation plan)
- Writing the paper itself
- User study design
- The actual experiment results
