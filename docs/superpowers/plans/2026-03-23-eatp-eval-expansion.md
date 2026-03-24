# EATP Eval Expansion & Ablation Baselines — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the eval suite from 35 to 100 tasks with ground-truth validation, add ablation baselines (static few-shot, successes-only), mock external APIs, isolate task workspaces, and generate paper-quality figures.

**Architecture:** Modular files under `evals/` — each concern (mocks, validators, static examples, figures) is a separate module imported by the runner. The runner gains 2 new modes (`static-fewshot`, `warm-successes`), workspace isolation via temp dirs, and post-task validation. No changes to core EATP files.

**Tech Stack:** Python 3.11, pytest, matplotlib, ChromaDB (existing), OpenAI API (existing)

**Spec:** `docs/superpowers/specs/2026-03-23-eatp-eval-expansion-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `evals/mocks.py` | Create | Mock registry for 12 external API tools |
| `evals/validators.py` | Create | 8 validator primitives + registry (100 entries) |
| `evals/static_fewshot.py` | Create | 10 hardcoded guidelines for Baseline B |
| `evals/seeds/` | Create dir | Template files needed by specific tasks |
| `evals/tasks.json` | Rewrite | 100 tasks (replacing 35) |
| `evals/correction_policy.json` | Rewrite | 20 correctable task entries |
| `evals/transfer_map.json` | Create | 20 transfer task → source lesson mapping |
| `evals/runner.py` | Modify | 2 new modes, mocks, workspace isolation, validators |
| `evals/compare_phases.py` | Modify | 5+ config support, validated field, transfer analysis |
| `evals/generate_figures.py` | Create | 4 matplotlib charts for the paper |

## Dependency Graph

```
Task 1 (mocks) ──────────────────────┐
Task 2 (validators framework) ───────┤
Task 3 (static fewshot) ─────────────┤
Task 4 (seed files) ─────────────────┤──→ Task 8 (runner mods) ──→ Task 10 (compare_phases) ──→ Task 11 (figures) ──→ Task 12 (verify)
Task 5 (tasks.json 100 tasks) ───────┤
Task 6 (correction policy + map) ────┤
Task 7 (validator registry) ─────────┘
```

Tasks 1-7 are independent of each other. Task 8 depends on all of 1-7. Tasks 9-11 are sequential.

---

### Task 1: Mock System for External APIs

**Files:**
- Create: `evals/mocks.py`
- Test: `tests/test_mocks.py`

- [ ] **Step 1: Write the test file**

```python
# tests/test_mocks.py
import json
import pytest
from evals.mocks import MOCK_REGISTRY


class TestMockRegistry:
    def test_all_external_tools_mocked(self):
        expected = {
            "search_flights", "book_travel", "get_booking",
            "cancel_booking", "list_bookings",
            "github_create_branch", "github_commit_file",
            "github_commit_local_file", "github_create_pr",
            "create_github_issue",
            "open_gmail_and_compose", "playwright_navigate",
        }
        assert set(MOCK_REGISTRY.keys()) == expected

    def test_search_flights_returns_valid_json(self):
        result = MOCK_REGISTRY["search_flights"]({"origin": "JFK", "destination": "LHR"})
        data = json.loads(result)
        assert "offers" in data
        assert len(data["offers"]) >= 1

    def test_book_travel_returns_confirmation(self):
        result = MOCK_REGISTRY["book_travel"]({"offer_id": "off_123"})
        data = json.loads(result)
        assert data["status"] == "confirmed"

    def test_github_create_branch_uses_args(self):
        result = MOCK_REGISTRY["github_create_branch"]({"branch_name": "feat/test"})
        data = json.loads(result)
        assert data["branch"] == "feat/test"

    def test_playwright_returns_page_content(self):
        result = MOCK_REGISTRY["playwright_navigate"]({"url": "https://example.com"})
        data = json.loads(result)
        assert "text_content" in data

    def test_mock_responses_are_strings(self):
        for name, mock_fn in MOCK_REGISTRY.items():
            result = mock_fn({})
            assert isinstance(result, str), f"{name} mock did not return a string"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mocks.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evals.mocks'`

- [ ] **Step 3: Implement mocks.py**

```python
# evals/mocks.py
"""Mock responses for external API tools used during evaluation.

These provide deterministic, realistic responses so eval runs don't
require real API access for travel, GitHub, email, and browser tools.
"""
import json


def _search_flights(args):
    origin = args.get("origin", "JFK")
    destination = args.get("destination", "LHR")
    return json.dumps({
        "offers": [
            {"id": "off_mock_001", "airline": "BA", "price": "$450",
             "departure": "10:30", "arrival": "18:45", "stops": 0,
             "origin": origin, "destination": destination},
            {"id": "off_mock_002", "airline": "AA", "price": "$520",
             "departure": "14:00", "arrival": "22:15", "stops": 1,
             "origin": origin, "destination": destination},
        ]
    })


def _book_travel(args):
    offer_id = args.get("offer_id", "off_mock_001")
    return json.dumps({
        "booking_ref": "MOCK-BK-001",
        "offer_id": offer_id,
        "status": "confirmed",
        "passenger": "Test User",
        "total_price": "$450",
    })


def _get_booking(args):
    ref = args.get("booking_reference", "MOCK-BK-001")
    return json.dumps({
        "booking_ref": ref,
        "status": "confirmed",
        "route": "JFK → LHR",
        "passenger": "Test User",
        "departure": "2026-06-15T10:30:00",
    })


def _cancel_booking(args):
    ref = args.get("booking_reference", "MOCK-BK-001")
    return json.dumps({
        "booking_ref": ref,
        "status": "cancelled",
        "refund_amount": "$450",
    })


def _list_bookings(args):
    return json.dumps({
        "bookings": [
            {"ref": "MOCK-BK-001", "route": "JFK → LHR",
             "status": "confirmed", "date": "2026-06-15"},
        ]
    })


def _github_create_branch(args):
    branch = args.get("branch_name", "test-branch")
    return json.dumps({
        "branch": branch,
        "status": "created",
        "base": "main",
    })


def _github_commit_file(args):
    path = args.get("file_path", "file.txt")
    return json.dumps({
        "commit_sha": "abc123mock",
        "status": "committed",
        "file": path,
    })


def _github_commit_local_file(args):
    path = args.get("file_path", "file.txt")
    return json.dumps({
        "commit_sha": "def456mock",
        "status": "committed",
        "file": path,
    })


def _github_create_pr(args):
    title = args.get("title", "Mock PR")
    return json.dumps({
        "pr_number": 42,
        "title": title,
        "url": "https://github.com/mock/repo/pull/42",
        "status": "open",
    })


def _create_github_issue(args):
    title = args.get("title", "Mock Issue")
    return json.dumps({
        "issue_number": 7,
        "title": title,
        "url": "https://github.com/mock/repo/issues/7",
        "status": "open",
    })


def _open_gmail_and_compose(args):
    to = args.get("to", "test@example.com")
    subject = args.get("subject", "")
    return json.dumps({
        "status": "draft_created",
        "to": to,
        "subject": subject,
    })


def _playwright_navigate(args):
    url = args.get("url", "https://example.com")
    return json.dumps({
        "status": "page_loaded",
        "url": url,
        "title": "Mock Page — " + url.split("//")[-1].split("/")[0],
        "text_content": "This is mock page content for testing purposes. "
                        "The page contains sample text that the agent can analyze.",
    })


MOCK_REGISTRY = {
    "search_flights": _search_flights,
    "book_travel": _book_travel,
    "get_booking": _get_booking,
    "cancel_booking": _cancel_booking,
    "list_bookings": _list_bookings,
    "github_create_branch": _github_create_branch,
    "github_commit_file": _github_commit_file,
    "github_commit_local_file": _github_commit_local_file,
    "github_create_pr": _github_create_pr,
    "create_github_issue": _create_github_issue,
    "open_gmail_and_compose": _open_gmail_and_compose,
    "playwright_navigate": _playwright_navigate,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_mocks.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add evals/mocks.py tests/test_mocks.py
git commit -m "feat(eval): add mock registry for 12 external API tools"
```

---

### Task 2: Validator Framework

**Files:**
- Create: `evals/validators.py`
- Test: `tests/test_validators.py`

- [ ] **Step 1: Write the test file**

```python
# tests/test_validators.py
import os
import pytest
from evals.validators import (
    file_exists, file_contains, response_mentions, tool_was_called,
    script_runs, tool_called_before, correct_tool_order, composite,
    default_validator,
)


@pytest.fixture
def workdir(tmp_path):
    """Create a temp workdir with some test files."""
    (tmp_path / "hello.py").write_text("print('hello')\n")
    (tmp_path / "data.csv").write_text("name,age\nAlice,30\n")
    return str(tmp_path)


def _make_result(tool_history=None, response="Task completed."):
    """Helper to build a result dict with tool history."""
    history = []
    for name in (tool_history or []):
        history.append({"role": "tool", "name": name, "content": "ok"})
    return {"response": response, "history": history}


class TestFileExists:
    def test_existing_file(self, workdir):
        assert file_exists("hello.py")(_make_result(), workdir) is True

    def test_missing_file(self, workdir):
        assert file_exists("nope.txt")(_make_result(), workdir) is False


class TestFileContains:
    def test_substring_found(self, workdir):
        assert file_contains("data.csv", "Alice")(_make_result(), workdir) is True

    def test_substring_missing(self, workdir):
        assert file_contains("data.csv", "Bob")(_make_result(), workdir) is False

    def test_file_missing(self, workdir):
        assert file_contains("nope.txt", "x")(_make_result(), workdir) is False


class TestResponseMentions:
    def test_keyword_found(self):
        assert response_mentions("completed")(_make_result(response="Task completed."), "") is True

    def test_keyword_case_insensitive(self):
        assert response_mentions("COMPLETED")(_make_result(response="Task completed."), "") is True

    def test_keyword_missing(self):
        assert response_mentions("failed")(_make_result(response="Task completed."), "") is False


class TestToolWasCalled:
    def test_tool_present(self):
        assert tool_was_called("read_file")(_make_result(["read_file", "run_code"]), "") is True

    def test_tool_absent(self):
        assert tool_was_called("delete_file")(_make_result(["read_file"]), "") is False


class TestToolCalledBefore:
    def test_correct_order(self):
        result = _make_result(["list_files", "delete_file"])
        assert tool_called_before("list_files", "delete_file")(result, "") is True

    def test_wrong_order(self):
        result = _make_result(["delete_file", "list_files"])
        assert tool_called_before("list_files", "delete_file")(result, "") is False

    def test_missing_tool(self):
        result = _make_result(["list_files"])
        assert tool_called_before("list_files", "delete_file")(result, "") is False


class TestCorrectToolOrder:
    def test_tools_in_order(self):
        result = _make_result(["list_files", "read_file", "create_and_edit_file"])
        assert correct_tool_order("list_files", "create_and_edit_file")(result, "") is True

    def test_tools_out_of_order(self):
        result = _make_result(["create_and_edit_file", "list_files"])
        assert correct_tool_order("list_files", "create_and_edit_file")(result, "") is False


class TestScriptRuns:
    def test_valid_script(self, workdir):
        assert script_runs("hello.py")(_make_result(), workdir) is True

    def test_missing_script(self, workdir):
        assert script_runs("nope.py")(_make_result(), workdir) is False


class TestComposite:
    def test_all_pass(self):
        v = composite(response_mentions("done"), tool_was_called("read_file"))
        result = _make_result(["read_file"], "done")
        assert v(result, "") is True

    def test_one_fails(self):
        v = composite(response_mentions("done"), tool_was_called("delete_file"))
        result = _make_result(["read_file"], "done")
        assert v(result, "") is False


class TestDefaultValidator:
    def test_passes_with_tool_call(self):
        result = _make_result(["read_file"], "All good.")
        assert default_validator(result, "") is True

    def test_fails_with_error_response(self):
        result = _make_result(["read_file"], "Error: something broke")
        assert default_validator(result, "") is False

    def test_fails_with_no_tools(self):
        result = _make_result([], "All good.")
        assert default_validator(result, "") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validators.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evals.validators'`

- [ ] **Step 3: Implement validator primitives**

```python
# evals/validators.py
"""Ground-truth validators for EATP evaluation tasks.

Two tiers:
- Lightweight: single-condition checks (file exists, response keyword)
- Full: composite checks verifying correct approach (tool ordering + output)
"""
import os
import subprocess


def file_exists(path):
    """Validator: file was created at path (relative to workdir)."""
    def check(result, workdir):
        return os.path.exists(os.path.join(workdir, path))
    return check


def file_contains(path, substring):
    """Validator: file exists and contains substring."""
    def check(result, workdir):
        fpath = os.path.join(workdir, path)
        if not os.path.exists(fpath):
            return False
        try:
            with open(fpath, 'r', errors='replace') as f:
                return substring in f.read()
        except Exception:
            return False
    return check


def response_mentions(keyword):
    """Validator: agent response contains keyword (case-insensitive)."""
    def check(result, workdir):
        response = result.get('response', '')
        return keyword.lower() in response.lower()
    return check


def tool_was_called(tool_name):
    """Validator: tool appears in execution history."""
    def check(result, workdir):
        history = result.get('history', [])
        return any(
            m.get('name') == tool_name
            for m in history if m.get('role') == 'tool'
        )
    return check


def script_runs(path):
    """Validator: Python script executes with return code 0."""
    def check(result, workdir):
        fpath = os.path.join(workdir, path)
        if not os.path.exists(fpath):
            return False
        try:
            r = subprocess.run(
                ['python', fpath],
                capture_output=True, cwd=workdir, timeout=15
            )
            return r.returncode == 0
        except Exception:
            return False
    return check


def tool_called_before(before_tool, after_tool):
    """Validator: before_tool appears earlier in history than after_tool."""
    def check(result, workdir):
        called = [
            m.get('name') for m in result.get('history', [])
            if m.get('role') == 'tool'
        ]
        if before_tool not in called or after_tool not in called:
            return False
        return called.index(before_tool) < called.index(after_tool)
    return check


def correct_tool_order(*expected_tools):
    """Validator: tools appear in specified order (not necessarily adjacent)."""
    def check(result, workdir):
        called = [
            m.get('name') for m in result.get('history', [])
            if m.get('role') == 'tool'
        ]
        idx = 0
        for tool in called:
            if idx < len(expected_tools) and tool == expected_tools[idx]:
                idx += 1
        return idx == len(expected_tools)
    return check


def composite(*validators):
    """Validator: all inner validators must pass."""
    def check(result, workdir):
        return all(v(result, workdir) for v in validators)
    return check


def default_validator(result, workdir):
    """Default: at least one tool called and response doesn't start with Error."""
    history = result.get('history', [])
    has_tool = any(m.get('role') == 'tool' for m in history)
    response = result.get('response', '')
    no_error = not response.startswith("Error")
    return has_tool and no_error


# ── Validator Registry ──────────────────────────────────────────────
# Populated in Task 7 after tasks.json is finalized.
# Keys are task IDs, values are validator callables.
VALIDATORS = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_validators.py -v`
Expected: 20 passed

- [ ] **Step 5: Commit**

```bash
git add evals/validators.py tests/test_validators.py
git commit -m "feat(eval): add validator framework with 8 primitives"
```

---

### Task 3: Static Few-shot Examples

**Files:**
- Create: `evals/static_fewshot.py`
- Test: `tests/test_static_fewshot.py`

- [ ] **Step 1: Write the test file**

```python
# tests/test_static_fewshot.py
from evals.static_fewshot import STATIC_EXAMPLES


class TestStaticFewshot:
    def test_is_nonempty_string(self):
        assert isinstance(STATIC_EXAMPLES, str)
        assert len(STATIC_EXAMPLES) > 100

    def test_contains_all_ten_lessons(self):
        # Each lesson should appear as a numbered guideline
        for i in range(1, 11):
            assert f"{i}." in STATIC_EXAMPLES, f"Lesson {i} missing"

    def test_mentions_key_tools(self):
        assert "list_files" in STATIC_EXAMPLES
        assert "read_file" in STATIC_EXAMPLES
        assert "check_syntax" in STATIC_EXAMPLES

    def test_no_eatp_reference(self):
        # Static examples should not reference the experience system
        assert "experience" not in STATIC_EXAMPLES.lower()
        assert "eatp" not in STATIC_EXAMPLES.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_static_fewshot.py -v`
Expected: FAIL

- [ ] **Step 3: Implement static_fewshot.py**

```python
# evals/static_fewshot.py
"""Static few-shot examples for Baseline B.

Contains the same 10 lessons EATP would learn dynamically, but
hardcoded as static text in the prompt. This is the fairest
comparison: same knowledge, different delivery mechanism.
"""

STATIC_EXAMPLES = """## Task Execution Guidelines

1. BEFORE DELETING OR RENAMING FILES: Always use list_files first to show which files will be affected. Never perform destructive file operations without listing affected files first.

2. BEFORE EDITING A FILE: Always use read_file first to understand the current contents. Never edit a file without reading it first — you might overwrite important content.

3. BEFORE RUNNING CODE: Use check_syntax first to catch errors statically. Running buggy code wastes time and may produce side effects.

4. BEFORE RUNNING SCRIPTS WITH IMPORTS: Verify that required packages are installed before running. Use run_code with a quick import check first.

5. BEFORE PROCESSING DATA FILES: Read the source data file to verify its structure, column names, and format match what your processing code expects.

6. BEFORE BULK OPERATIONS: List all affected items and show the total count before proceeding. Never perform bulk deletes, moves, or renames without confirming scope.

7. BEFORE CREATING DOCUMENTS: Read any existing document or template first. If the user references an existing file, inspect it before creating a new version.

8. BEFORE COMMITTING TO ACTIONS: Review search or list results before booking travel, creating PRs, or other irreversible actions. Confirm key details first.

9. BEFORE FILE FORMAT CONVERSIONS: Read the file header or first few lines to verify the format matches expectations before running conversion scripts.

10. AFTER CREATING FILES: Use read_file to verify the output file contains what you intended. Catch issues early rather than reporting success on incomplete work.
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_static_fewshot.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add evals/static_fewshot.py tests/test_static_fewshot.py
git commit -m "feat(eval): add static few-shot examples for Baseline B"
```

---

### Task 4: Seed Files

**Files:**
- Create: `evals/seeds/config.yaml`
- Create: `evals/seeds/data.csv`
- Create: `evals/seeds/users.json`
- Create: `evals/seeds/buggy.py`
- Create: `evals/seeds/notes.txt`
- Create: `evals/seeds/inventory.csv`
- Create: `evals/seeds/template_report.txt`
- Create: `evals/seeds/app_log.log`
- Create: `evals/seeds/legacy_code.py`

- [ ] **Step 1: Create seeds directory and files**

Create `evals/seeds/` with the following files:

**config.yaml:**
```yaml
app:
  name: MyApp
  version: 1.0
databases:
  primary:
    host: localhost
    port: 5432
    name: myapp_db
logging:
  level: INFO
  file: app.log
```

**data.csv:**
```csv
date,product,quantity,price
2026-01-15,Widget A,10,25.99
2026-01-16,Widget B,5,42.50
2026-01-17,Widget A,8,25.99
2026-01-18,Widget C,3,99.00
2026-01-19,Widget B,12,42.50
```

**users.json:**
```json
[
    {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "admin"},
    {"id": 2, "name": "Bob", "email": "bob@example.com", "role": "user"},
    {"id": 3, "name": "Carol", "email": "carol@example.com", "role": "user"}
]
```

**buggy.py:**
```python
def greet(name)
    return f"Hello, {name}!"

def add(a, b):
    return a + b

result = greet("World")
print(result)
```

**notes.txt:**
```
Meeting Notes - Q1 Planning
Date: 2026-01-10
Attendees: Alice, Bob, Carol

Action items:
- Alice: Update the dashboard by Friday
- Bob: Fix the login bug
- Carol: Write unit tests for the API
```

**inventory.csv:**
```csv
item_id,name,stock,reorder_level
1001,Laptop,45,20
1002,Mouse,120,50
1003,Keyboard,89,30
1004,Monitor,12,15
1005,USB Cable,250,100
```

**template_report.txt:**
```
QUARTERLY REPORT - Q1 2026
==========================

Department: [DEPARTMENT]
Author: [AUTHOR]
Date: [DATE]

1. Summary
[SUMMARY]

2. Key Metrics
[METRICS]

3. Action Items
[ACTIONS]
```

**app_log.log:**
```
2026-01-15 08:00:01 INFO  Server started on port 8080
2026-01-15 08:01:23 WARN  Slow query detected: 2.3s
2026-01-15 08:05:44 ERROR Connection timeout to database
2026-01-15 08:05:45 INFO  Retrying database connection
2026-01-15 08:05:46 INFO  Database connection restored
```

**legacy_code.py:**
```python
import os

def process_data(data):
    result = []
    for i in range(len(data)):
        item = data[i]
        if item['status'] == 'active':
            name = item['name']
            value = item['value']
            formatted = str(name) + ': ' + str(value)
            result.append(formatted)
        else:
            pass
    return result

def read_config(path):
    f = open(path, 'r')
    content = f.read()
    f.close()
    return content
```

- [ ] **Step 2: Verify seed files exist**

Run: `ls evals/seeds/`
Expected: 9 files listed

- [ ] **Step 3: Commit**

```bash
git add evals/seeds/
git commit -m "feat(eval): add seed files for task workspace isolation"
```

---

### Task 5: Expanded Tasks JSON (100 Tasks)

**Files:**
- Rewrite: `evals/tasks.json`

This is the largest task. Write all 100 tasks following the spec distribution (Section 2.2). Each task needs: `id`, `category`, `task_class`, `lesson_id` (or null), `prompt`, `expected_output`, `seed_files` (or empty list).

**Key constraints:**
- 20 correctable tasks: each teaches one of L1-L10 (2 per lesson)
- 20 transfer tasks: each tests one of L1-L10 (2 per lesson), similar but not identical to the correctable versions
- 60 standard tasks: baseline coverage, mix of easy/medium
- Tasks using external APIs (travel, GitHub, email, browser) will be mocked
- Tasks needing pre-existing files reference seed files
- Prompts must be specific enough that the agent knows what tool to call

- [ ] **Step 1: Write the complete tasks.json**

Write the full 100-task JSON to `evals/tasks.json`. Follow the ID ranges from the spec:
- task_001–015: File Operations (4 correctable L1/L2/L6/L10, 4 transfer, 7 standard)
- task_016–030: Code Tasks (4 correctable L3/L4/L5/L9, 4 transfer, 7 standard)
- task_031–045: Documents (3 correctable L2/L7/L10, 3 transfer, 9 standard)
- task_046–055: Travel (2 correctable L8, 2 transfer, 6 standard)
- task_056–065: GitHub (2 correctable L8, 2 transfer, 6 standard)
- task_066–075: Multimedia (2 correctable L5/L10, 2 transfer, 6 standard)
- task_076–085: Multi-tool (2 correctable L3/L6, 2 transfer, 6 standard)
- task_086–100: Cross-category (1 correctable L9, 1 transfer, 13 standard)

Each correctable task's prompt should naturally lead the agent to call the denied tool first (the "naive" approach). The correction teaches the better approach.

Each transfer task should be similar enough that the same lesson applies, but different enough that it's not a trivial match (different file names, different operations, different domain).

- [ ] **Step 2: Validate task counts**

Run:
```python
import json
with open('evals/tasks.json') as f:
    tasks = json.load(f)
print(f"Total: {len(tasks)}")
for tc in ['correctable', 'transfer', 'standard']:
    print(f"  {tc}: {sum(1 for t in tasks if t['task_class'] == tc)}")
cats = {}
for t in tasks:
    cats[t['category']] = cats.get(t['category'], 0) + 1
for c, n in sorted(cats.items()):
    print(f"  {c}: {n}")
```

Expected: Total 100, correctable 20, transfer 20, standard 60, per-category matches spec.

- [ ] **Step 3: Commit**

```bash
git add evals/tasks.json
git commit -m "feat(eval): expand task suite to 100 tasks across 8 categories"
```

---

### Task 6: Correction Policy + Transfer Map

**Files:**
- Rewrite: `evals/correction_policy.json`
- Create: `evals/transfer_map.json`

- [ ] **Step 1: Write correction_policy.json**

Must have exactly 20 entries — one for each correctable task. Each entry uses the denied tool and correction text from the lesson table (spec Section 3.1). The keys are the correctable task IDs from tasks.json.

```json
{
    "_comment": "Maps 20 correctable task IDs to denial/correction actions for Phase B.",
    "task_001": {"deny": "delete_file", "correction": "Use list_files first to show affected files before modifying."},
    "task_002": {"deny": "rename_file", "correction": "Use list_files first to show affected files before modifying."},
    "task_003": {"deny": "create_and_edit_file", "correction": "Use read_file first to understand current contents. Never edit blind."},
    "task_004": {"deny": "delete_file", "correction": "List all affected items and show count before bulk actions."}
}
```

(Continue for all 20 correctable tasks, using the lesson-specific denied tool and correction text.)

- [ ] **Step 2: Write transfer_map.json**

Must have exactly 20 entries — one for each transfer task. Links to the lesson ID and the correctable tasks that teach it.

```json
{
    "_comment": "Maps 20 transfer task IDs to their source lesson and correctable tasks.",
    "task_005": {"lesson_id": "L1", "source_tasks": ["task_001", "task_002"]},
    "task_006": {"lesson_id": "L2", "source_tasks": ["task_003"]}
}
```

(Continue for all 20 transfer tasks.)

- [ ] **Step 3: Validate counts**

Run:
```python
import json
with open('evals/correction_policy.json') as f:
    cp = json.load(f)
entries = {k: v for k, v in cp.items() if not k.startswith('_')}
print(f"Correction policies: {len(entries)}")

with open('evals/transfer_map.json') as f:
    tm = json.load(f)
entries = {k: v for k, v in tm.items() if not k.startswith('_')}
print(f"Transfer mappings: {len(entries)}")
lessons = set(v['lesson_id'] for v in entries.values())
print(f"Lessons covered: {sorted(lessons)}")
```

Expected: 20 policies, 20 mappings, 10 lessons (L1-L10).

- [ ] **Step 4: Commit**

```bash
git add evals/correction_policy.json evals/transfer_map.json
git commit -m "feat(eval): add correction policy (20 tasks) and transfer map (20 tasks)"
```

---

### Task 7: Validator Registry (100 entries)

**Files:**
- Modify: `evals/validators.py` (add VALIDATORS dict entries)

**Depends on:** Task 2 (framework), Task 5 (tasks.json finalized)

- [ ] **Step 1: Populate VALIDATORS dict**

Add 100 entries to the `VALIDATORS` dict in `validators.py`. The correctable and transfer tasks get **full validators** (composite with tool ordering), standard tasks get **lightweight validators**.

**Pattern for correctable/transfer tasks (L1 example — list before delete):**
```python
"task_001": composite(
    tool_called_before("list_files", "delete_file"),
),
```

**Pattern for correctable/transfer tasks (L2 example — read before edit):**
```python
"task_003": composite(
    tool_called_before("read_file", "create_and_edit_file"),
    file_exists("config.yaml"),
),
```

**Pattern for standard tasks:**
```python
"task_011": file_exists("hello_world.py"),
"task_012": composite(file_exists("factorial.py"), script_runs("factorial.py")),
"task_015": response_mentions("Python"),
```

**Pattern for mocked external tasks:**
```python
"task_046": tool_was_called("search_flights"),
"task_056": composite(
    tool_was_called("github_create_branch"),
    tool_was_called("github_commit_file"),
),
```

- [ ] **Step 2: Verify all 100 task IDs have validators**

Run:
```python
import json
from evals.validators import VALIDATORS
with open('evals/tasks.json') as f:
    tasks = json.load(f)
task_ids = {t['id'] for t in tasks}
validator_ids = set(VALIDATORS.keys())
missing = task_ids - validator_ids
print(f"Tasks: {len(task_ids)}, Validators: {len(validator_ids)}, Missing: {len(missing)}")
if missing:
    print(f"Missing: {sorted(missing)}")
```

Expected: 100 tasks, 100 validators, 0 missing.

- [ ] **Step 3: Commit**

```bash
git add evals/validators.py
git commit -m "feat(eval): populate validator registry with 100 task entries"
```

---

### Task 8: Runner Modifications

**Files:**
- Modify: `evals/runner.py`

**Depends on:** Tasks 1-7

Changes:
1. Add `static-fewshot` and `warm-successes` to `--eatp-mode` choices
2. Add mock interception after agent creation
3. Add workspace isolation (tempdir per task)
4. Add validator call after each task
5. Store `validated` field in results and use it for summary metrics

- [ ] **Step 1: Add imports at top of runner.py**

After the existing imports (around line 9), add:
```python
import shutil
import tempfile
```

- [ ] **Step 2: Add mock interception after agent creation**

After `agent = Agent(...)` line (around line 60), add:
```python
    # Mock external API tools for deterministic eval
    from evals.mocks import MOCK_REGISTRY
    original_execute = agent._execute_tool_by_name
    def mock_aware_execute(name, args):
        if name in MOCK_REGISTRY:
            return MOCK_REGISTRY[name](args)
        return original_execute(name, args)
    agent._execute_tool_by_name = mock_aware_execute
```

- [ ] **Step 3: Add new EATP modes**

In the EATP mode configuration block, add two new branches:

```python
    elif eatp_mode == 'static-fewshot':
        agent.experience_store = None
        from evals.static_fewshot import STATIC_EXAMPLES
        agent.system_instruction += "\n\n" + STATIC_EXAMPLES
    elif eatp_mode == 'warm-successes':
        experience_dir = os.path.join(os.path.expanduser("~"), ".ai_agent", "experiences_eval")
        from agents.experience_store import ExperienceStore
        agent.experience_store = ExperienceStore(persist_dir=experience_dir)
        original_format = agent.experience_store.format_for_prompt
        def format_without_corrections(records):
            for r in records:
                r.user_corrections = []
            return original_format(records)
        agent.experience_store.format_for_prompt = format_without_corrections
```

- [ ] **Step 4: Add workspace isolation in the task loop**

Before each task's `agent.chat_once()` call, add workspace setup:
```python
        # Create isolated workspace for this task
        task_workdir = tempfile.mkdtemp(prefix=f"eatp_eval_{task['id']}_")
        seed_files = task.get('seed_files', [])
        seeds_base = os.path.join(os.path.dirname(__file__), 'seeds')
        for sf in seed_files:
            src = os.path.join(seeds_base, sf['source'])
            dst = os.path.join(task_workdir, sf['name'])
            if os.path.exists(src):
                shutil.copy2(src, dst)

        # Point agent to task workspace
        agent._execute_tool_by_name('change_working_directory', {'path': task_workdir})
```

After the task completes and result is built, add:
```python
        # Cleanup workspace
        try:
            shutil.rmtree(task_workdir)
        except Exception:
            pass
```

- [ ] **Step 5: Add validator call after each task**

After building the result dict, before `results.append(result)`:
```python
        # Run ground-truth validator
        from evals.validators import VALIDATORS, default_validator
        validator = VALIDATORS.get(task['id'], default_validator)
        try:
            validated = validator(response_data if isinstance(response_data, dict) else {"response": response, "history": history}, task_workdir)
        except Exception:
            validated = False
        result["validated"] = validated
```

- [ ] **Step 6: Update summary metrics to use validated field**

Change the summary calculation:
```python
    completed_tasks = sum(1 for r in results if r['status'] == 'completed')
    validated_tasks = sum(1 for r in results if r.get('validated', False))
```

Add `validated_tasks` and `validated_percent` to the summary dict:
```python
    summary = {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "validated_tasks": validated_tasks,
        "validated_percent": round((validated_tasks / total_tasks) * 100, 2) if total_tasks > 0 else 0,
        ...
    }
```

- [ ] **Step 7: Update argparse choices**

```python
    parser.add_argument('--eatp-mode',
        choices=['cold', 'warm', 'off', 'static-fewshot', 'warm-successes'],
        default='off')
```

- [ ] **Step 8: Run existing tests**

Run: `pytest tests/ -v`
Expected: All existing tests still pass (runner changes don't affect unit tests).

- [ ] **Step 9: Commit**

```bash
git add evals/runner.py
git commit -m "feat(eval): add 2 modes, mocks, workspace isolation, validators to runner"
```

---

### Task 9: Update Compare Phases Script

**Files:**
- Modify: `evals/compare_phases.py`

Changes:
1. Support 5+ configs (auto-detect from CLI args)
2. Use `validated` field as primary success metric
3. Load `transfer_map.json` for per-lesson transfer analysis
4. Separate correctable vs transfer carryover rates

- [ ] **Step 1: Update CLI to accept arbitrary config files**

Replace the fixed `--a`, `--b`, `--c` args with a flexible `--configs` argument:
```python
    parser.add_argument("--configs", nargs="+",
        default=["results_off.json", "results_static_fewshot.json",
                 "results_phase_a.json", "results_warm_successes.json",
                 "results_phase_c.json"],
        help="Result files to compare")
    parser.add_argument("--labels", nargs="+",
        default=["Off", "Static Few-shot", "Cold (A)", "Warm (succ)", "Warm (full)"],
        help="Labels for each config")
```

- [ ] **Step 2: Update Section 1 to use validated metric**

Change the primary metric from `accuracy_percent` → `validated_percent`:
```python
    ("Validated Rate (%)", lambda d: d["summary"].get("validated_percent",
        d["summary"].get("accuracy_percent", 0))),
```

- [ ] **Step 3: Add transfer analysis in Section 3**

Load `transfer_map.json` and split carryover analysis into two sub-sections:
- **Correctable tasks:** Did tasks with corrections improve? (expected: high rate)
- **Transfer tasks:** Did the lesson carry over to unseen tasks? (the stronger claim)

```python
    # Load transfer map
    transfer_map = {}
    tm_path = os.path.join(os.path.dirname(__file__), "transfer_map.json")
    if os.path.exists(tm_path):
        with open(tm_path, 'r') as f:
            raw = json.load(f)
            transfer_map = {k: v for k, v in raw.items() if not k.startswith('_')}
```

For each transfer task, check whether the `validated` field is True in the warm config but False (or worse) in the off config. Group by lesson_id.

- [ ] **Step 4: Update Section 6 paper-ready summary**

Include both correctable and transfer carryover rates.

- [ ] **Step 5: Commit**

```bash
git add evals/compare_phases.py
git commit -m "feat(eval): update compare_phases for 5 configs, validated metric, transfer analysis"
```

---

### Task 10: Figure Generation

**Files:**
- Create: `evals/generate_figures.py`

- [ ] **Step 1: Implement generate_figures.py**

```python
# evals/generate_figures.py
"""Generate paper-quality figures from EATP experiment results.

Usage:
    python evals/generate_figures.py

Reads result files from evals/ and saves figures to evals/figures/.
"""
import json
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except ImportError:
    print("matplotlib required: pip install matplotlib")
    sys.exit(1)


EVALS_DIR = os.path.dirname(os.path.abspath(__file__))
FIGURES_DIR = os.path.join(EVALS_DIR, "figures")

RESULT_FILES = {
    "Off": "results_off.json",
    "Static\nFew-shot": "results_static_fewshot.json",
    "Cold (A)": "results_phase_a.json",
    "Warm\n(succ. only)": "results_warm_successes.json",
    "Warm\n(full EATP)": "results_phase_c.json",
}

# Colorblind-safe palette (Wong 2011)
COLORS = ["#999999", "#E69F00", "#56B4E9", "#009E73", "#D55E00"]

CATEGORIES = [
    "File Operations", "Code Tasks", "Document Creation/Editing",
    "Travel/Booking", "GitHub Operations", "Multimedia",
    "Multi-tool Orchestration", "Cross-category",
]


def load_all():
    """Load all result files. Returns {label: data} for those that exist."""
    configs = {}
    for label, fname in RESULT_FILES.items():
        path = os.path.join(EVALS_DIR, fname)
        if os.path.exists(path):
            with open(path, 'r') as f:
                configs[label] = json.load(f)
    return configs


def fig1_success_rate(configs):
    """Bar chart: validated success rate per config."""
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    labels = list(configs.keys())
    rates = []
    for data in configs.values():
        s = data["summary"]
        rate = s.get("validated_percent", s.get("accuracy_percent", 0))
        rates.append(rate)

    bars = ax.bar(range(len(labels)), rates, color=COLORS[:len(labels)], width=0.6)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Validated Success Rate (%)", fontsize=9)
    ax.set_ylim(0, 105)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{rate:.0f}%", ha='center', va='bottom', fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    return fig


def fig2_tool_efficiency(configs):
    """Bar chart: avg tool calls per validated task."""
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    labels = list(configs.keys())
    efficiencies = []
    for data in configs.values():
        s = data["summary"]
        efficiencies.append(s.get("tool_calls_per_completed_task", 0))

    bars = ax.bar(range(len(labels)), efficiencies, color=COLORS[:len(labels)], width=0.6)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Avg Tool Calls / Task", fontsize=9)
    for bar, val in zip(bars, efficiencies):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                f"{val:.1f}", ha='center', va='bottom', fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    return fig


def fig3_category_heatmap(configs):
    """Heatmap: success rate per category per config."""
    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    labels = list(configs.keys())
    matrix = []

    for cat in CATEGORIES:
        row = []
        for data in configs.values():
            tasks = [r for r in data["results"] if r["category"] == cat]
            if tasks:
                validated = sum(1 for r in tasks if r.get("validated", r["status"] == "completed"))
                row.append(validated / len(tasks) * 100)
            else:
                row.append(0)
        matrix.append(row)

    matrix = np.array(matrix)
    im = ax.imshow(matrix, cmap="Greens", aspect="auto", vmin=0, vmax=100)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_yticks(range(len(CATEGORIES)))
    ax.set_yticklabels(CATEGORIES, fontsize=7)

    for i in range(len(CATEGORIES)):
        for j in range(len(labels)):
            val = matrix[i, j]
            color = "white" if val > 60 else "black"
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=7, color=color)

    fig.colorbar(im, ax=ax, label="Success %", shrink=0.8)
    fig.tight_layout()
    return fig


def fig4_correction_carryover(configs):
    """Horizontal bar chart: carryover rate per lesson."""
    fig, ax = plt.subplots(figsize=(3.5, 3.0))

    # Load transfer map and tasks
    tm_path = os.path.join(EVALS_DIR, "transfer_map.json")
    tasks_path = os.path.join(EVALS_DIR, "tasks.json")
    if not os.path.exists(tm_path) or not os.path.exists(tasks_path):
        ax.text(0.5, 0.5, "transfer_map.json or tasks.json not found",
                transform=ax.transAxes, ha='center')
        return fig

    with open(tm_path) as f:
        transfer_map = {k: v for k, v in json.load(f).items() if not k.startswith('_')}
    with open(tasks_path) as f:
        tasks = json.load(f)

    # Get results from "Off" and "Warm (full EATP)" configs
    off_key = [k for k in configs if "Off" in k]
    warm_key = [k for k in configs if "full" in k.lower() or "warm\n(full" in k.lower()]
    if not off_key or not warm_key:
        ax.text(0.5, 0.5, "Need Off and Warm (full) results", transform=ax.transAxes, ha='center')
        return fig

    off_results = {r["id"]: r for r in configs[off_key[0]]["results"]}
    warm_results = {r["id"]: r for r in configs[warm_key[0]]["results"]}

    # Group transfer tasks by lesson
    lessons = {}
    for tid, info in transfer_map.items():
        lid = info["lesson_id"]
        if lid not in lessons:
            lessons[lid] = []
        lessons[lid].append(tid)

    lesson_ids = sorted(lessons.keys())
    carryover_rates = []
    for lid in lesson_ids:
        task_ids = lessons[lid]
        carried = 0
        total = 0
        for tid in task_ids:
            if tid in off_results and tid in warm_results:
                total += 1
                off_ok = off_results[tid].get("validated", off_results[tid]["status"] == "completed")
                warm_ok = warm_results[tid].get("validated", warm_results[tid]["status"] == "completed")
                if warm_ok and not off_ok:
                    carried += 1
                elif warm_ok and off_ok:
                    # Both pass — check tool efficiency
                    warm_tools = warm_results[tid]["tool_calls"]
                    off_tools = off_results[tid]["tool_calls"]
                    if warm_tools <= off_tools:
                        carried += 1
        rate = (carried / total * 100) if total > 0 else 0
        carryover_rates.append(rate)

    y_pos = range(len(lesson_ids))
    bars = ax.barh(y_pos, carryover_rates, color="#009E73", height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(lesson_ids, fontsize=8)
    ax.set_xlabel("Transfer Carryover Rate (%)", fontsize=9)
    ax.set_xlim(0, 105)

    for bar, rate in zip(bars, carryover_rates):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{rate:.0f}%", va='center', fontsize=8)

    overall = np.mean(carryover_rates) if carryover_rates else 0
    ax.axvline(x=overall, color='red', linestyle='--', linewidth=1, label=f"Mean: {overall:.0f}%")
    ax.legend(fontsize=7, loc='lower right')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    fig.tight_layout()
    return fig


def main():
    os.makedirs(FIGURES_DIR, exist_ok=True)
    configs = load_all()

    if len(configs) < 2:
        print(f"Found {len(configs)} result file(s). Need at least 2 to generate figures.")
        print("Run the experiment phases first.")
        return

    print(f"Loaded {len(configs)} configs: {', '.join(configs.keys())}")

    generators = [
        ("fig1_success_rate", fig1_success_rate),
        ("fig2_tool_efficiency", fig2_tool_efficiency),
        ("fig3_category_heatmap", fig3_category_heatmap),
        ("fig4_correction_carryover", fig4_correction_carryover),
    ]

    figs = []
    for name, gen_fn in generators:
        fig = gen_fn(configs)
        path = os.path.join(FIGURES_DIR, f"{name}.png")
        fig.savefig(path, dpi=300, bbox_inches='tight')
        print(f"Saved: {path}")
        figs.append(fig)

    # Combined 2x2 grid
    combined, axes = plt.subplots(2, 2, figsize=(7.5, 6))
    for idx, (name, gen_fn) in enumerate(generators):
        # Re-generate into subplot
        ax = axes[idx // 2][idx % 2]
        ax.set_title(name.replace("_", " ").title(), fontsize=9)
    # For a proper combined figure, we'd need to re-implement each in subplots.
    # For now, save individual figures which can be arranged in LaTeX.
    combined_path = os.path.join(FIGURES_DIR, "fig_all.png")
    # Skip combined for now — individual PNGs are more useful for LaTeX
    plt.close(combined)

    for fig in figs:
        plt.close(fig)

    print(f"\nAll figures saved to {FIGURES_DIR}/")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify matplotlib is available**

Run: `python -c "import matplotlib; print(matplotlib.__version__)"`
If missing: `pip install matplotlib`

- [ ] **Step 3: Commit**

```bash
git add evals/generate_figures.py
git commit -m "feat(eval): add paper figure generation (4 charts)"
```

---

### Task 11: Add .gitignore for figures

**Files:**
- Create: `evals/figures/.gitignore`

- [ ] **Step 1: Create gitignore**

```
# Generated figures — not tracked
*.png
```

- [ ] **Step 2: Commit**

```bash
git add evals/figures/.gitignore
git commit -m "chore: gitignore generated eval figures"
```

---

### Task 12: Full Verification

**Depends on:** All previous tasks

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass (existing + new mock/validator/fewshot tests).

- [ ] **Step 2: Validate tasks.json structure**

Run:
```python
python -c "
import json
with open('evals/tasks.json') as f:
    tasks = json.load(f)
assert len(tasks) == 100, f'Expected 100 tasks, got {len(tasks)}'
classes = {'correctable': 0, 'transfer': 0, 'standard': 0}
for t in tasks:
    assert t['task_class'] in classes, f'{t[\"id\"]} has invalid class'
    classes[t['task_class']] += 1
    assert 'prompt' in t and len(t['prompt']) > 10, f'{t[\"id\"]} has short prompt'
print(f'OK: {classes}')
"
```

Expected: `OK: {'correctable': 20, 'transfer': 20, 'standard': 60}`

- [ ] **Step 3: Validate correction policy and transfer map**

Run:
```python
python -c "
import json
with open('evals/correction_policy.json') as f:
    cp = {k: v for k, v in json.load(f).items() if not k.startswith('_')}
with open('evals/transfer_map.json') as f:
    tm = {k: v for k, v in json.load(f).items() if not k.startswith('_')}
with open('evals/tasks.json') as f:
    tasks = {t['id']: t for t in json.load(f)}
# Every correction policy key must be a correctable task
for tid in cp:
    assert tasks[tid]['task_class'] == 'correctable', f'{tid} is not correctable'
# Every transfer map key must be a transfer task
for tid in tm:
    assert tasks[tid]['task_class'] == 'transfer', f'{tid} is not transfer'
# Every correctable task must have a policy
correctable_ids = {t['id'] for t in tasks.values() if t['task_class'] == 'correctable'}
assert correctable_ids == set(cp.keys()), f'Mismatch: {correctable_ids - set(cp.keys())}'
# Every transfer task must have a mapping
transfer_ids = {t['id'] for t in tasks.values() if t['task_class'] == 'transfer'}
assert transfer_ids == set(tm.keys()), f'Mismatch: {transfer_ids - set(tm.keys())}'
print(f'OK: {len(cp)} policies, {len(tm)} mappings')
"
```

Expected: `OK: 20 policies, 20 mappings`

- [ ] **Step 4: Verify runner accepts all modes**

Run:
```bash
python evals/runner.py --eatp-mode off --help
```
Expected: Shows choices including `static-fewshot` and `warm-successes`.

- [ ] **Step 5: Commit any final fixes**

```bash
git add -A
git commit -m "chore: final verification pass for eval expansion"
```

---

## Future Work (Not in This Plan)

1. **Run the actual experiments** — 6 configs x 100 tasks = 600 API calls (~2.5 hours, ~$50-100 in API costs)
2. **Tune thresholds** — adjust similarity threshold (0.75) and correction policy denied tools based on initial results
3. **Write the paper** — use figure generation + compare_phases output
4. **User study** — recruit 10-15 classmates for subjective evaluation
