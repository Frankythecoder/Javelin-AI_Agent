# EATP (Experience-Augmented Tool Planning) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a retrieval-based learning layer so the agent stores past task executions (especially user corrections) in a vector store and retrieves relevant experiences before planning new tasks, improving over time without fine-tuning.

**Architecture:** Two new modules (`experience_store.py`, `experience_logger.py`) plus a `feedback_tools.py` tool file. Retrieval + prompt augmentation happens in `chat_once()` before graph invocation (line 479 of `core.py`). Logging happens after graph completion (line 515). ChromaDB is used as a local vector store; OpenAI `text-embedding-3-small` for embeddings.

**Tech Stack:** Python, ChromaDB, OpenAI Embeddings API, pytest, existing Django/LangGraph agent

**Spec:** `docs/superpowers/specs/2026-03-23-eatp-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `agents/experience_store.py` | ChromaDB wrapper: store, retrieve, deduplicate, token budget enforcement |
| `agents/experience_logger.py` | Build ExperienceRecord from execution context, compute args_summary |
| `agents/feedback_tools.py` | `rate_experience` tool definition |
| `agents/migrate_experiences.py` | Re-embedding migration script for model version changes |
| `evals/correction_policy.json` | Maps task IDs to denial/correction actions for Phase B experiments |
| `tests/test_experience_store.py` | Tests for ExperienceStore |
| `tests/test_experience_logger.py` | Tests for ExperienceLogger |
| `tests/test_feedback_tools.py` | Tests for rate_experience tool |
| `tests/test_eatp_integration.py` | Integration tests for retrieval + augmentation in chat_once() |

### Modified Files
| File | Change |
|------|--------|
| `agents/core.py:452-535` | Add retrieval before graph invocation, logging after completion in `chat_once()` and `execute_dry_run()` |
| `agents/__init__.py:124-127` | Add exports for new modules |
| `evals/runner.py` | Add EATP mode flags (cold/warm), correction policy support |
| `requirements.txt` (or equivalent) | Add `chromadb` dependency |

---

## Task 1: Install ChromaDB and Verify Setup

**Files:**
- Modify: `requirements.txt` (if it exists, otherwise note the dependency)

- [ ] **Step 1: Install chromadb**

```bash
pip install chromadb
```

- [ ] **Step 2: Verify ChromaDB works**

```bash
python -c "import chromadb; client = chromadb.Client(); print('ChromaDB OK:', client.heartbeat())"
```

Expected: Prints heartbeat timestamp without errors.

- [ ] **Step 3: Add to requirements**

Add `chromadb` to the project's dependency list (check if `requirements.txt` exists at project root; if so, append `chromadb`).

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "deps: add chromadb for experience store"
```

---

## Task 2: ExperienceRecord Dataclass and ExperienceStore

**Files:**
- Create: `agents/experience_store.py`
- Create: `tests/test_experience_store.py`

This is the core EATP component. The ExperienceStore wraps ChromaDB and handles:
- Storing experience records with embeddings
- Retrieving similar experiences by cosine similarity
- Re-ranking (corrections first, then failures, then successes)
- Token budget enforcement (800 tokens max)
- Deduplication (>0.95 similarity consolidation)
- Confidence decay (recency weighting)

### Reference: ExperienceRecord Schema (from spec Section 3)

```
id, created_at, task_description, task_category, task_complexity,
plan_summary, tools_planned, tools_executed, tool_results, outcome,
user_corrections, approval_actions, embedding,
last_validated, confirmation_count, schema_version, embedding_model
```

- [ ] **Step 1: Write failing tests for ExperienceRecord dataclass**

Create `tests/test_experience_store.py`:

```python
import pytest
import os
import sys
import shutil
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestExperienceRecord:
    def test_create_record_with_required_fields(self):
        from agents.experience_store import ExperienceRecord
        record = ExperienceRecord(
            task_description="Delete old log files",
            task_category="file_ops",
            task_complexity="heavy",
            outcome="success",
        )
        assert record.task_description == "Delete old log files"
        assert record.task_category == "file_ops"
        assert record.outcome == "success"
        assert record.schema_version == 1
        assert record.embedding_model == "text-embedding-3-small"
        assert record.confirmation_count == 0
        assert record.id is not None
        assert record.created_at is not None

    def test_record_defaults(self):
        from agents.experience_store import ExperienceRecord
        record = ExperienceRecord(
            task_description="test",
            task_category="code",
            task_complexity="light",
            outcome="success",
        )
        assert record.plan_summary == ""
        assert record.tools_planned == []
        assert record.tools_executed == []
        assert record.tool_results == []
        assert record.user_corrections == []
        assert record.approval_actions == []

    def test_record_to_metadata_dict(self):
        from agents.experience_store import ExperienceRecord
        record = ExperienceRecord(
            task_description="Read a file",
            task_category="file_ops",
            task_complexity="light",
            outcome="success",
            tools_executed=["read_file"],
        )
        meta = record.to_metadata()
        assert meta["task_category"] == "file_ops"
        assert meta["outcome"] == "success"
        assert meta["schema_version"] == 1
        # Lists should be JSON-serialized for ChromaDB metadata
        assert isinstance(meta["tools_executed"], str)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_experience_store.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.experience_store'`

- [ ] **Step 3: Implement ExperienceRecord dataclass**

Create `agents/experience_store.py` with the dataclass:

```python
import json
import os
import uuid
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import chromadb
from openai import OpenAI
from django.conf import settings


EMBEDDING_MODEL = "text-embedding-3-small"
SCHEMA_VERSION = 1
SIMILARITY_THRESHOLD = 0.75
DEDUP_THRESHOLD = 0.95
TOKEN_BUDGET = 800
EXPERIENCE_DIR = os.path.join(os.path.expanduser("~"), ".ai_agent", "experiences")


@dataclass
class ExperienceRecord:
    """A single recorded task execution experience."""
    task_description: str
    task_category: str
    task_complexity: str
    outcome: str  # "success", "partial", "failure"

    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)

    # What was planned
    plan_summary: str = ""
    tools_planned: List[str] = field(default_factory=list)

    # What actually happened
    tools_executed: List[str] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)

    # What the human corrected
    user_corrections: List[str] = field(default_factory=list)
    approval_actions: List[Dict[str, Any]] = field(default_factory=list)

    # Learning metadata
    last_validated: datetime = field(default_factory=datetime.now)
    confirmation_count: int = 0

    # Versioning
    schema_version: int = SCHEMA_VERSION
    embedding_model: str = EMBEDDING_MODEL

    def to_metadata(self) -> Dict[str, Any]:
        """Convert to ChromaDB-compatible metadata dict.

        ChromaDB metadata values must be str, int, float, or bool.
        Lists and dicts are JSON-serialized.
        """
        return {
            "task_category": self.task_category,
            "task_complexity": self.task_complexity,
            "outcome": self.outcome,
            "plan_summary": self.plan_summary,
            "tools_planned": json.dumps(self.tools_planned),
            "tools_executed": json.dumps(self.tools_executed),
            "tool_results": json.dumps(self.tool_results),
            "user_corrections": json.dumps(self.user_corrections),
            "approval_actions": json.dumps(self.approval_actions),
            "created_at": self.created_at.isoformat(),
            "last_validated": self.last_validated.isoformat(),
            "confirmation_count": self.confirmation_count,
            "schema_version": self.schema_version,
            "embedding_model": self.embedding_model,
        }

    @classmethod
    def from_metadata(cls, id: str, task_description: str, metadata: Dict[str, Any]) -> "ExperienceRecord":
        """Reconstruct an ExperienceRecord from ChromaDB metadata."""
        return cls(
            id=id,
            task_description=task_description,
            task_category=metadata.get("task_category", ""),
            task_complexity=metadata.get("task_complexity", ""),
            outcome=metadata.get("outcome", ""),
            plan_summary=metadata.get("plan_summary", ""),
            tools_planned=json.loads(metadata.get("tools_planned", "[]")),
            tools_executed=json.loads(metadata.get("tools_executed", "[]")),
            tool_results=json.loads(metadata.get("tool_results", "[]")),
            user_corrections=json.loads(metadata.get("user_corrections", "[]")),
            approval_actions=json.loads(metadata.get("approval_actions", "[]")),
            created_at=datetime.fromisoformat(metadata.get("created_at", datetime.now().isoformat())),
            last_validated=datetime.fromisoformat(metadata.get("last_validated", datetime.now().isoformat())),
            confirmation_count=metadata.get("confirmation_count", 0),
            schema_version=metadata.get("schema_version", SCHEMA_VERSION),
            embedding_model=metadata.get("embedding_model", EMBEDDING_MODEL),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_experience_store.py::TestExperienceRecord -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Write failing tests for ExperienceStore**

Append to `tests/test_experience_store.py`:

```python
class TestExperienceStore:
    """Tests for the ExperienceStore ChromaDB wrapper.

    Uses a temporary directory for ChromaDB to avoid polluting real data.
    Mocks OpenAI embedding calls to avoid API costs during testing.
    """

    @pytest.fixture
    def temp_store_dir(self, tmp_path):
        return str(tmp_path / "test_experiences")

    @pytest.fixture
    def mock_embeddings(self):
        """Return deterministic fake embeddings for testing."""
        def fake_embed(texts):
            # Return a simple hash-based embedding (384 dims to match text-embedding-3-small)
            results = []
            for text in texts:
                h = hash(text) % (10**9)
                vec = [(h * (i + 1) % 997) / 997.0 for i in range(384)]
                # Normalize
                norm = sum(x**2 for x in vec) ** 0.5
                results.append([x / norm for x in vec])
            return results
        return fake_embed

    @pytest.fixture
    def store(self, temp_store_dir, mock_embeddings):
        from agents.experience_store import ExperienceStore
        with patch.object(ExperienceStore, '_embed_texts', side_effect=mock_embeddings):
            s = ExperienceStore(persist_dir=temp_store_dir)
            s._embed_texts = mock_embeddings
            yield s

    def test_store_and_retrieve(self, store):
        from agents.experience_store import ExperienceRecord
        record = ExperienceRecord(
            task_description="Delete old log files from project",
            task_category="file_ops",
            task_complexity="heavy",
            outcome="partial",
            user_corrections=["User denied delete_file, asked to list first"],
        )
        store.add(record)
        results = store.retrieve("Remove old log files")
        assert len(results) >= 1
        assert results[0].task_description == "Delete old log files from project"

    def test_retrieve_empty_store(self, store):
        results = store.retrieve("anything")
        assert results == []

    def test_retrieve_ranks_corrections_first(self, store):
        from agents.experience_store import ExperienceRecord
        # Add a success without corrections
        store.add(ExperienceRecord(
            task_description="Delete old log files",
            task_category="file_ops",
            task_complexity="heavy",
            outcome="success",
        ))
        # Add a failure with corrections
        store.add(ExperienceRecord(
            task_description="Delete old log files from project",
            task_category="file_ops",
            task_complexity="heavy",
            outcome="partial",
            user_corrections=["List files before deleting"],
        ))
        results = store.retrieve("Delete old log files")
        assert len(results) >= 2
        # Corrected experience should come first
        assert len(results[0].user_corrections) > 0

    def test_format_for_prompt_respects_token_budget(self, store):
        from agents.experience_store import ExperienceRecord
        # Add many experiences
        for i in range(20):
            store.add(ExperienceRecord(
                task_description=f"Task {i}: do something complex involving multiple steps",
                task_category="file_ops",
                task_complexity="heavy",
                outcome="failure",
                user_corrections=[f"Correction for task {i}: use a different approach"],
            ))
        results = store.retrieve("do something complex")
        prompt_text = store.format_for_prompt(results)
        # Rough token estimate: 1 token ≈ 4 chars
        estimated_tokens = len(prompt_text) / 4
        assert estimated_tokens <= 900  # 800 budget + some margin

    def test_deduplication(self, store):
        from agents.experience_store import ExperienceRecord
        record1 = ExperienceRecord(
            task_description="Delete log files from project",
            task_category="file_ops",
            task_complexity="heavy",
            outcome="partial",
            user_corrections=["List before deleting"],
        )
        store.add(record1)
        # Add near-duplicate
        record2 = ExperienceRecord(
            task_description="Delete log files from project",
            task_category="file_ops",
            task_complexity="heavy",
            outcome="partial",
            user_corrections=["List before deleting"],
        )
        store.add(record2)
        # Should have consolidated, not duplicated
        all_records = store.get_all()
        matching = [r for r in all_records if "Delete log files" in r.task_description]
        assert len(matching) == 1
        assert matching[0].confirmation_count >= 1
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_experience_store.py::TestExperienceStore -v
```

Expected: FAIL — `ExperienceStore` not yet implemented.

- [ ] **Step 7: Implement ExperienceStore class**

Append to `agents/experience_store.py`:

```python
class ExperienceStore:
    """ChromaDB-backed store for experience records.

    Handles embedding, storage, retrieval, re-ranking, deduplication,
    and token budget enforcement.
    """

    _lock = threading.Lock()

    def __init__(self, persist_dir: str = None, openai_client: OpenAI = None):
        self._persist_dir = persist_dir or EXPERIENCE_DIR
        os.makedirs(self._persist_dir, exist_ok=True)

        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._collection = self._client.get_or_create_collection(
            name="experiences",
            metadata={"hnsw:space": "cosine"},
        )
        self._openai = openai_client

    def _get_openai(self) -> OpenAI:
        if self._openai is None:
            self._openai = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed texts using OpenAI text-embedding-3-small."""
        response = self._get_openai().embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )
        return [item.embedding for item in response.data]

    def add(self, record: ExperienceRecord) -> None:
        """Store an experience record, deduplicating if a near-match exists."""
        with self._lock:
            embedding = self._embed_texts([record.task_description])[0]

            # Check for near-duplicates
            if self._collection.count() > 0:
                results = self._collection.query(
                    query_embeddings=[embedding],
                    n_results=1,
                    include=["metadatas", "documents", "distances"],
                )
                if results["distances"] and results["distances"][0]:
                    # ChromaDB cosine distance = 1 - similarity
                    similarity = 1 - results["distances"][0][0]
                    if similarity > DEDUP_THRESHOLD:
                        # Consolidate: update confirmation_count and last_validated
                        existing_id = results["ids"][0][0]
                        existing_meta = results["metadatas"][0][0]
                        existing_meta["confirmation_count"] = existing_meta.get("confirmation_count", 0) + 1
                        existing_meta["last_validated"] = datetime.now().isoformat()
                        # Merge user_corrections
                        existing_corrections = json.loads(existing_meta.get("user_corrections", "[]"))
                        new_corrections = [c for c in record.user_corrections if c not in existing_corrections]
                        existing_corrections.extend(new_corrections)
                        existing_meta["user_corrections"] = json.dumps(existing_corrections)
                        self._collection.update(
                            ids=[existing_id],
                            metadatas=[existing_meta],
                        )
                        return

            # No duplicate — add new record
            self._collection.add(
                ids=[record.id],
                embeddings=[embedding],
                documents=[record.task_description],
                metadatas=[record.to_metadata()],
            )

    def retrieve(self, query: str, n_results: int = 5) -> List[ExperienceRecord]:
        """Retrieve the most relevant experiences for a query.

        Re-ranks results: corrections first, then failures, then successes.
        Applies confidence decay based on recency.
        """
        if self._collection.count() == 0:
            return []

        embedding = self._embed_texts([query])[0]
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(n_results, self._collection.count()),
            include=["metadatas", "documents", "distances"],
        )

        records = []
        for i, doc_id in enumerate(results["ids"][0]):
            similarity = 1 - results["distances"][0][i]
            if similarity < SIMILARITY_THRESHOLD:
                continue
            record = ExperienceRecord.from_metadata(
                id=doc_id,
                task_description=results["documents"][0][i],
                metadata=results["metadatas"][0][i],
            )
            records.append((record, similarity))

        # Re-rank: corrections first, then failures, then successes
        def rank_key(item):
            record, sim = item
            has_corrections = 1 if record.user_corrections else 0
            is_failure = 1 if record.outcome in ("failure", "partial") else 0
            recency = self._recency_factor(record)
            # Higher = better (sort descending)
            return (has_corrections, is_failure, sim * recency)

        records.sort(key=rank_key, reverse=True)
        return [r for r, _ in records]

    def _recency_factor(self, record: ExperienceRecord) -> float:
        """Compute recency decay factor.

        1.0 for < 30 days, linear decay to 0.5 at 180 days.
        High confirmation_count resists decay.
        """
        age_days = (datetime.now() - record.last_validated).days
        if age_days < 30:
            base_factor = 1.0
        elif age_days > 180:
            base_factor = 0.5
        else:
            # Linear decay from 1.0 to 0.5 over 30-180 days
            base_factor = 1.0 - 0.5 * ((age_days - 30) / 150)

        # High confirmation count resists decay
        boost = min(record.confirmation_count * 0.05, 0.3)
        return min(base_factor + boost, 1.0)

    def format_for_prompt(self, records: List[ExperienceRecord]) -> str:
        """Format retrieved experiences as a prompt section.

        Enforces an 800-token budget (estimated at 4 chars/token).
        """
        if not records:
            return ""

        char_budget = TOKEN_BUDGET * 4  # ~800 tokens
        header = "## Lessons from Past Experience\n\n"
        sections = []

        for record in records:
            section = f'TASK: "{record.task_description}"\n'
            section += f"OUTCOME: {record.outcome}\n"
            if record.user_corrections:
                section += f"LESSON: {'; '.join(record.user_corrections)}\n"
            if record.plan_summary:
                section += f"PREFERRED APPROACH: {record.plan_summary}\n"
            section += "\n"
            sections.append(section)

        # Fit within budget
        result = header
        for section in sections:
            if len(result) + len(section) > char_budget:
                break
            result += section

        return result.rstrip()

    def get_all(self) -> List[ExperienceRecord]:
        """Return all stored experience records."""
        if self._collection.count() == 0:
            return []
        results = self._collection.get(include=["metadatas", "documents"])
        records = []
        for i, doc_id in enumerate(results["ids"]):
            records.append(ExperienceRecord.from_metadata(
                id=doc_id,
                task_description=results["documents"][i],
                metadata=results["metadatas"][i],
            ))
        return records
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_experience_store.py -v
```

Expected: All tests PASS.

- [ ] **Step 9: Commit**

```bash
git add agents/experience_store.py tests/test_experience_store.py
git commit -m "feat(eatp): add ExperienceRecord and ExperienceStore with ChromaDB"
```

---

## Task 3: ExperienceLogger

**Files:**
- Create: `agents/experience_logger.py`
- Create: `tests/test_experience_logger.py`

The logger takes the raw execution context from `chat_once()` and builds a structured `ExperienceRecord`. It handles args_summary generation (truncation per spec Section 3).

- [ ] **Step 1: Write failing tests**

Create `tests/test_experience_logger.py`:

```python
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestArgsSummary:
    def test_file_tool_summary(self):
        from agents.experience_logger import summarize_tool_args
        summary = summarize_tool_args("create_and_edit_file", {
            "path": "foo.py",
            "old_str": "",
            "new_str": "x" * 5000,
        })
        assert summary["path"] == "foo.py"
        assert "content_length" in summary
        assert isinstance(summary["content_length"], int)
        # Should NOT contain the full 5000-char string
        assert len(str(summary)) < 300

    def test_code_tool_summary(self):
        from agents.experience_logger import summarize_tool_args
        summary = summarize_tool_args("run_code", {
            "command": "python " + "x" * 500,
        })
        assert len(summary["command"]) <= 200

    def test_travel_tool_summary(self):
        from agents.experience_logger import summarize_tool_args
        summary = summarize_tool_args("search_flights", {
            "origin": "LAX",
            "destination": "JFK",
            "departure_date": "2026-05-15",
            "adults": 1,
        })
        assert summary["origin"] == "LAX"
        assert summary["destination"] == "JFK"

    def test_generic_tool_summary_truncates(self):
        from agents.experience_logger import summarize_tool_args
        summary = summarize_tool_args("some_tool", {
            "big_field": "x" * 1000,
        })
        assert len(str(summary["big_field"])) <= 200


class TestExperienceLogger:
    def test_build_record_from_execution(self):
        from agents.experience_logger import ExperienceLogger
        logger = ExperienceLogger()
        record = logger.build_record(
            task_description="Delete old log files",
            task_category="file_ops",
            task_complexity="heavy",
            plan_summary="List files, then delete .log files",
            tools_planned=["list_files", "delete_file"],
            tool_executions=[
                {"name": "list_files", "args": {"path": "."}, "result": "file1.log\nfile2.log", "success": True},
                {"name": "delete_file", "args": {"path": "file1.log"}, "result": "Deleted", "success": True},
            ],
            user_corrections=[],
            approval_actions=[],
            outcome="success",
        )
        assert record.task_description == "Delete old log files"
        assert record.tools_executed == ["list_files", "delete_file"]
        assert len(record.tool_results) == 2
        assert record.tool_results[0]["success"] is True
        assert record.outcome == "success"

    def test_build_record_captures_denials(self):
        from agents.experience_logger import ExperienceLogger
        logger = ExperienceLogger()
        record = logger.build_record(
            task_description="Delete old log files",
            task_category="file_ops",
            task_complexity="heavy",
            plan_summary="Delete .log files",
            tools_planned=["delete_file"],
            tool_executions=[],
            user_corrections=["User denied delete_file, asked to list first"],
            approval_actions=[{"tool_name": "delete_file", "action": "denied"}],
            outcome="partial",
        )
        assert len(record.user_corrections) == 1
        assert record.approval_actions[0]["action"] == "denied"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_experience_logger.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ExperienceLogger**

Create `agents/experience_logger.py`:

```python
from typing import Dict, List, Any, Optional
from agents.experience_store import ExperienceRecord


# Tool categories for args_summary generation
FILE_TOOLS = {"search_file", "read_file", "list_files", "create_and_edit_file",
              "delete_file", "rename_file", "find_file_broadly", "find_directory_broadly",
              "change_working_directory"}
CODE_TOOLS = {"run_code", "check_syntax", "run_tests", "lint_code"}
TRAVEL_TOOLS = {"search_flights", "book_travel", "get_booking", "list_bookings", "cancel_booking"}
CONTENT_FIELDS = {"new_str", "old_str", "content", "body"}


def summarize_tool_args(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a compact summary of tool arguments.

    Per spec Section 3: include identifying parameters (paths, names, codes),
    replace large content with length/type metadata, truncate at 200 chars.
    """
    summary = {}
    for key, value in args.items():
        str_val = str(value)
        if key in CONTENT_FIELDS:
            # Replace content blobs with length
            summary[key + "_length"] = len(str_val)
        elif len(str_val) > 200:
            summary[key] = str_val[:200]
        else:
            summary[key] = value
    return summary


class ExperienceLogger:
    """Builds ExperienceRecord instances from execution context."""

    def build_record(
        self,
        task_description: str,
        task_category: str,
        task_complexity: str,
        plan_summary: str,
        tools_planned: List[str],
        tool_executions: List[Dict[str, Any]],
        user_corrections: List[str],
        approval_actions: List[Dict[str, Any]],
        outcome: str,
    ) -> ExperienceRecord:
        """Build an ExperienceRecord from raw execution data.

        Args:
            tool_executions: List of dicts with keys:
                name, args, result, success (bool), error (str or None)
        """
        tools_executed = [t["name"] for t in tool_executions]
        tool_results = [
            {
                "tool_name": t["name"],
                "args_summary": summarize_tool_args(t["name"], t.get("args", {})),
                "success": t.get("success", True),
                "error": t.get("error"),
            }
            for t in tool_executions
        ]

        return ExperienceRecord(
            task_description=task_description,
            task_category=task_category,
            task_complexity=task_complexity,
            plan_summary=plan_summary,
            tools_planned=tools_planned,
            tools_executed=tools_executed,
            tool_results=tool_results,
            user_corrections=user_corrections,
            approval_actions=approval_actions,
            outcome=outcome,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_experience_logger.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/experience_logger.py tests/test_experience_logger.py
git commit -m "feat(eatp): add ExperienceLogger with args_summary generation"
```

---

## Task 4: Feedback Tool (rate_experience)

**Files:**
- Create: `agents/feedback_tools.py`
- Create: `tests/test_feedback_tools.py`
- Modify: `agents/__init__.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_feedback_tools.py`:

```python
import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRateExperienceTool:
    def test_definition_exists(self):
        from agents.feedback_tools import RATE_EXPERIENCE_DEFINITION
        assert RATE_EXPERIENCE_DEFINITION.name == "rate_experience"
        assert RATE_EXPERIENCE_DEFINITION.requires_approval is False

    def test_definition_has_rating_param(self):
        from agents.feedback_tools import RATE_EXPERIENCE_DEFINITION
        props = RATE_EXPERIENCE_DEFINITION.parameters["properties"]
        assert "rating" in props
        assert "feedback" in props

    def test_rate_stores_feedback(self):
        from agents.feedback_tools import rate_experience_tool
        # With no prior experience, should return a message
        result = rate_experience_tool({"rating": 5, "feedback": "Great job"})
        assert isinstance(result, str)
        assert "5" in result or "recorded" in result.lower() or "thank" in result.lower()

    def test_rate_validates_range(self):
        from agents.feedback_tools import rate_experience_tool
        result = rate_experience_tool({"rating": 0})
        assert "1" in result and "5" in result  # Should mention valid range

    def test_rate_rejects_above_range(self):
        from agents.feedback_tools import rate_experience_tool
        result = rate_experience_tool({"rating": 6})
        assert "1" in result and "5" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_feedback_tools.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement feedback_tools.py**

Create `agents/feedback_tools.py`:

```python
from typing import Dict, Any
from agents.control import ToolDefinition


# Module-level holder for last experience ID (set by experience logger after each task)
_last_experience_id: str = ""
_last_rating_info: Dict[str, Any] = {}


def set_last_experience_id(experience_id: str) -> None:
    """Called by the experience logger after storing a record."""
    global _last_experience_id
    _last_experience_id = experience_id


def get_last_rating() -> Dict[str, Any]:
    """Get the most recent rating info (for attaching to experience records)."""
    return _last_rating_info


def rate_experience_tool(args: Dict[str, Any]) -> str:
    """Rate how well the agent handled the last task."""
    global _last_rating_info
    rating = args.get("rating", 0)
    feedback = args.get("feedback", "")

    if not isinstance(rating, int) or rating < 1 or rating > 5:
        return "Rating must be an integer between 1 and 5."

    _last_rating_info = {
        "rating": rating,
        "feedback": feedback,
        "experience_id": _last_experience_id,
    }

    response = f"Rating of {rating}/5 recorded."
    if feedback:
        response += f" Feedback noted: {feedback}"
    response += " Thank you — this helps me improve."
    return response


RATE_EXPERIENCE_DEFINITION = ToolDefinition(
    name="rate_experience",
    description="Rate how well the agent handled the last task. Provide a rating from 1-5 and optional feedback on what could be improved.",
    parameters={
        "type": "object",
        "properties": {
            "rating": {
                "type": "integer",
                "description": "Rating from 1 (poor) to 5 (excellent)",
            },
            "feedback": {
                "type": "string",
                "description": "Optional feedback on what could be improved",
            },
        },
        "required": ["rating"],
    },
    function=rate_experience_tool,
    requires_approval=False,
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_feedback_tools.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Add exports to `agents/__init__.py`**

Add after the `document_rw_tools` import block (before the `core` import at line 126):

```python
from agents.feedback_tools import (
    rate_experience_tool,
    RATE_EXPERIENCE_DEFINITION,
)
```

- [ ] **Step 6: Add tool to the tools list in `agents/core.py`**

In `main()`, add the import (after the document_rw_tools import around line 41):

```python
from agents.feedback_tools import RATE_EXPERIENCE_DEFINITION
```

And add `RATE_EXPERIENCE_DEFINITION` to the `tools` list (after `CANCEL_BOOKING_DEFINITION` at line 83):

```python
RATE_EXPERIENCE_DEFINITION,
```

- [ ] **Step 7: Commit**

```bash
git add agents/feedback_tools.py tests/test_feedback_tools.py agents/__init__.py agents/core.py
git commit -m "feat(eatp): add rate_experience feedback tool"
```

---

## Task 5: Integrate Retrieval + Prompt Augmentation into chat_once()

**Files:**
- Modify: `agents/core.py:117-123` (Agent.__init__), `agents/core.py:452-499` (chat_once)
- Create: `tests/test_eatp_integration.py`

This is the core integration — experience retrieval before the graph runs.

- [ ] **Step 1: Write failing integration test**

Create `tests/test_eatp_integration.py`:

```python
import pytest
import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Minimal Django setup for testing
import django
from django.conf import settings
if not settings.configured:
    settings.configure(
        DEBUG=True,
        OPENAI_API_KEY="test-key",
        INSTALLED_APPS=['chat'],
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
    )
    django.setup()


class TestEATPIntegration:
    def test_agent_has_experience_store(self):
        """Agent.__init__ should create an ExperienceStore instance."""
        from agents.core import Agent
        from agents.experience_store import ExperienceStore
        from openai import OpenAI
        client = MagicMock(spec=OpenAI)
        client.api_key = "test-key"
        agent = Agent(client, "gpt-4.1", lambda: ("", False), [])
        assert hasattr(agent, 'experience_store')
        assert isinstance(agent.experience_store, ExperienceStore)

    def test_system_prompt_includes_experiences_when_available(self):
        """When experience store has relevant records, system prompt should include them."""
        from agents.core import Agent
        from agents.experience_store import ExperienceRecord
        from openai import OpenAI
        client = MagicMock(spec=OpenAI)
        client.api_key = "test-key"
        agent = Agent(client, "gpt-4.1", lambda: ("", False), [])

        # Mock the experience store
        mock_record = ExperienceRecord(
            task_description="Delete old log files",
            task_category="file_ops",
            task_complexity="heavy",
            outcome="partial",
            user_corrections=["List files before deleting"],
        )
        agent.experience_store.retrieve = MagicMock(return_value=[mock_record])
        agent.experience_store.format_for_prompt = MagicMock(
            return_value="## Lessons from Past Experience\n\nTASK: \"Delete old log files\"\nLESSON: List files before deleting"
        )

        # Mock the graph to capture the messages it receives
        captured_messages = []
        original_invoke = agent._graph.invoke
        def capture_invoke(state, config=None):
            captured_messages.extend(state["messages"])
            # Return a minimal valid result
            return {
                "messages": state["messages"],
                "status": "success",
                "response": "test",
                "response_history": [],
                "execution_path": ["test"],
                "dry_run_plan": [],
                "pending_tools": [],
            }
        agent._graph.invoke = capture_invoke

        agent.chat_once(conversation_history=[], message="Delete old log files")

        # The system message should contain the experience section
        system_msg = captured_messages[0].content
        assert "Lessons from Past Experience" in system_msg

    def test_no_experiences_leaves_prompt_unchanged(self):
        """When experience store is empty, system prompt should be unchanged."""
        from agents.core import Agent
        from openai import OpenAI
        client = MagicMock(spec=OpenAI)
        client.api_key = "test-key"
        agent = Agent(client, "gpt-4.1", lambda: ("", False), [])

        agent.experience_store.retrieve = MagicMock(return_value=[])
        agent.experience_store.format_for_prompt = MagicMock(return_value="")

        captured_messages = []
        def capture_invoke(state, config=None):
            captured_messages.extend(state["messages"])
            return {
                "messages": state["messages"],
                "status": "success",
                "response": "test",
                "response_history": [],
                "execution_path": ["test"],
                "dry_run_plan": [],
                "pending_tools": [],
            }
        agent._graph.invoke = capture_invoke

        agent.chat_once(conversation_history=[], message="Hello")

        system_msg = captured_messages[0].content
        assert "Lessons from Past Experience" not in system_msg
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_eatp_integration.py -v
```

Expected: FAIL — Agent doesn't have `experience_store` attribute yet.

- [ ] **Step 3: Add ExperienceStore to Agent.__init__**

In `agents/core.py`, add import at top (after line 11):

```python
from agents.experience_store import ExperienceStore
from agents.experience_logger import ExperienceLogger
```

In `Agent.__init__` (after `self._conversation_summary = None` at line 155), add:

```python
        # EATP: Experience store and logger
        self.experience_store = ExperienceStore()
        self.experience_logger = ExperienceLogger()
```

- [ ] **Step 4: Add retrieval + augmentation to chat_once()**

In `chat_once()`, after the system instruction message is created (line 479) but before conversation history is appended (line 480), add the experience retrieval:

Replace lines 478-479:
```python
            # Build LangChain message list
            messages = [SystemMessage(content=self.system_instruction)]
```

With:
```python
            # Build LangChain message list with EATP augmentation
            system_prompt = self.system_instruction
            if message:
                experiences = self.experience_store.retrieve(message)
                experience_section = self.experience_store.format_for_prompt(experiences)
                if experience_section:
                    system_prompt = system_prompt + "\n\n" + experience_section
            messages = [SystemMessage(content=system_prompt)]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_eatp_integration.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add agents/core.py tests/test_eatp_integration.py
git commit -m "feat(eatp): integrate experience retrieval into chat_once()"
```

---

## Task 6: Integrate Experience Logging After Execution

**Files:**
- Modify: `agents/core.py:515-535` (after graph.invoke in chat_once)
- Modify: `agents/core.py:545-606` (execute_dry_run)

After the graph completes, log the execution as an experience record.

- [ ] **Step 1: Write failing test**

Append to `tests/test_eatp_integration.py`:

```python
class TestExperienceLogging:
    def test_successful_execution_logs_experience(self):
        """After a successful chat_once, an experience should be logged."""
        from agents.core import Agent
        from openai import OpenAI
        client = MagicMock(spec=OpenAI)
        client.api_key = "test-key"
        agent = Agent(client, "gpt-4.1", lambda: ("", False), [])

        # Mock experience store
        agent.experience_store.retrieve = MagicMock(return_value=[])
        agent.experience_store.format_for_prompt = MagicMock(return_value="")
        agent.experience_store.add = MagicMock()

        # Mock graph to return success
        def mock_invoke(state, config=None):
            return {
                "messages": state["messages"],
                "status": "success",
                "response": "Done!",
                "response_history": [],
                "execution_path": ["__start__", "classify_task", "call_model", "format_output"],
                "dry_run_plan": [],
                "pending_tools": [],
                "task_class": "heavy",
            }
        agent._graph.invoke = mock_invoke

        agent.chat_once(conversation_history=[], message="List files in current directory")

        # Experience should have been logged
        assert agent.experience_store.add.called
        logged_record = agent.experience_store.add.call_args[0][0]
        assert logged_record.task_description == "List files in current directory"
        assert logged_record.outcome == "success"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_eatp_integration.py::TestExperienceLogging -v
```

Expected: FAIL — logging not implemented yet.

- [ ] **Step 3: Add experience logging to chat_once()**

In `chat_once()`, after the graph result is processed (after line 515 `result = self._graph.invoke(...)`) and before the output dict is built (line 521), add logging:

Insert after line 515:

```python
            # EATP: Log this execution as an experience
            if message and result.get("status") in ("success", "dry_run"):
                try:
                    # Extract tool executions from response history
                    history = result.get("response_history", [])
                    tool_executions = []
                    for msg in history:
                        if msg.get("role") == "tool":
                            is_error = msg.get("content", "").startswith("Error")
                            tool_executions.append({
                                "name": msg.get("name", ""),
                                "args": {},
                                "result": msg.get("content", "")[:200],
                                "success": not is_error,
                                "error": msg.get("content", "") if is_error else None,
                            })
                    record = self.experience_logger.build_record(
                        task_description=message,
                        task_category="general",
                        task_complexity=result.get("task_class", "heavy"),
                        plan_summary=result.get("response", "")[:200],
                        tools_planned=[t["name"] for t in result.get("dry_run_plan", [])],
                        tool_executions=tool_executions,
                        user_corrections=[],
                        approval_actions=[],
                        outcome=result.get("status", "success"),
                    )
                    self.experience_store.add(record)
                except Exception:
                    pass  # Never let logging break the main flow
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/test_eatp_integration.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/core.py tests/test_eatp_integration.py
git commit -m "feat(eatp): log experiences after successful execution in chat_once()"
```

---

## Task 7: Denial/Correction Feedback Capture

**Files:**
- Modify: `agents/core.py:545-606` (execute_dry_run)

When the user approves a dry-run plan and tools execute, OR when the user has previously denied tools, capture that context in the experience log.

- [ ] **Step 1: Add denial tracking to execute_dry_run()**

In `execute_dry_run()`, after the tool execution loop (line 568) and before the graph re-invocation (line 572), add experience logging for approved dry-run plans:

After line 568 (after the tool execution for-loop), insert:

```python
            # EATP: Log the approved dry-run execution as an experience
            try:
                tool_executions = []
                for tool_call in dry_run_plan:
                    tool_executions.append({
                        "name": tool_call["name"],
                        "args": tool_call.get("arguments", {}),
                        "result": "",
                        "success": True,
                        "error": None,
                    })
                # Extract original user message from history
                user_msg = ""
                for msg in reversed(history):
                    if msg.get("role") == "user":
                        user_msg = msg.get("content", "")
                        break
                if user_msg:
                    record = self.experience_logger.build_record(
                        task_description=user_msg,
                        task_category="general",
                        task_complexity="heavy",
                        plan_summary="",
                        tools_planned=[t["name"] for t in dry_run_plan],
                        tool_executions=tool_executions,
                        user_corrections=[],
                        approval_actions=[{"tool_name": t["name"], "action": "approved"} for t in dry_run_plan],
                        outcome="success",
                    )
                    self.experience_store.add(record)
            except Exception:
                pass  # Never let logging break the main flow
```

- [ ] **Step 2: Run all tests to verify nothing is broken**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add agents/core.py
git commit -m "feat(eatp): capture approval actions in execute_dry_run()"
```

---

## Task 8: Update Eval Runner for EATP Modes

**Files:**
- Modify: `evals/runner.py`
- Create: `evals/correction_policy.json`

The eval runner needs two new capabilities:
1. **Cold/warm mode flag** — run with empty or populated experience store
2. **Correction policy** — selectively deny tools during Phase B runs

- [ ] **Step 1: Create correction policy template**

Create `evals/correction_policy.json`:

```json
{
    "_comment": "Maps task IDs to denial/correction actions for EATP Phase B evaluation",
    "file_ops_delete": {
        "deny": "delete_file",
        "correction": "Use list_files first to show the user which files will be affected before deleting"
    },
    "file_ops_edit_blind": {
        "deny": "create_and_edit_file",
        "correction": "Use read_file first to understand the current file contents before editing"
    }
}
```

- [ ] **Step 2: Add EATP mode flags to runner**

In `evals/runner.py`, modify `run_evals()` to accept EATP parameters. After line 50 (`def run_evals(output_file='results.json'):`), change the signature to:

```python
def run_evals(output_file='results.json', eatp_mode='cold', correction_policy_file=None):
```

After agent creation (line 60), add:

```python
    # EATP: Configure experience store mode
    if eatp_mode == 'cold':
        # Clear experience store for baseline measurement
        import shutil
        experience_dir = os.path.join(os.path.expanduser("~"), ".ai_agent", "experiences_eval")
        if os.path.exists(experience_dir):
            shutil.rmtree(experience_dir)
        from agents.experience_store import ExperienceStore
        agent.experience_store = ExperienceStore(persist_dir=experience_dir)
    elif eatp_mode == 'warm':
        # Use existing experience store (populated from Phase B)
        experience_dir = os.path.join(os.path.expanduser("~"), ".ai_agent", "experiences_eval")
        from agents.experience_store import ExperienceStore
        agent.experience_store = ExperienceStore(persist_dir=experience_dir)

    # Load correction policy for Phase B
    correction_policy = {}
    if correction_policy_file:
        policy_path = os.path.join(os.path.dirname(__file__), correction_policy_file)
        if os.path.exists(policy_path):
            with open(policy_path, 'r') as f:
                correction_policy = json.load(f)
```

Update the `__main__` block to accept CLI args:

```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='results.json')
    parser.add_argument('--eatp-mode', choices=['cold', 'warm', 'off'], default='off')
    parser.add_argument('--correction-policy', default=None)
    args = parser.parse_args()
    run_evals(args.output, args.eatp_mode, args.correction_policy)
```

- [ ] **Step 3: Run eval runner with --help to verify args work**

```bash
cd C:/Users/Frank/ai_agent && python evals/runner.py --help
```

Expected: Shows `--output`, `--eatp-mode`, `--correction-policy` arguments.

- [ ] **Step 4: Commit**

```bash
git add evals/runner.py evals/correction_policy.json
git commit -m "feat(eatp): add EATP mode flags and correction policy to eval runner"
```

---

## Task 9: Migration Script

**Files:**
- Create: `agents/migrate_experiences.py`

A utility script to re-embed all experience records when the embedding model changes.

- [ ] **Step 1: Create migration script**

Create `agents/migrate_experiences.py`:

```python
"""Re-embed all experience records when the embedding model changes.

Usage:
    python -m agents.migrate_experiences [--new-model text-embedding-3-small]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.experience_store import ExperienceStore, EXPERIENCE_DIR, EMBEDDING_MODEL


def migrate(new_model: str = None, persist_dir: str = None):
    target_model = new_model or EMBEDDING_MODEL
    store_dir = persist_dir or EXPERIENCE_DIR

    if not os.path.exists(store_dir):
        print(f"No experience store found at {store_dir}")
        return

    store = ExperienceStore(persist_dir=store_dir)
    records = store.get_all()

    if not records:
        print("No records to migrate.")
        return

    needs_migration = [r for r in records if r.embedding_model != target_model]
    print(f"Found {len(records)} records, {len(needs_migration)} need re-embedding.")

    if not needs_migration:
        print("All records already use the target model.")
        return

    for record in needs_migration:
        record.embedding_model = target_model
        # Delete old record and re-add (re-embeds with new model)
        store._collection.delete(ids=[record.id])
        store.add(record)
        print(f"  Migrated: {record.id[:8]}... ({record.task_description[:50]})")

    print(f"Migration complete. {len(needs_migration)} records re-embedded.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-embed experience records")
    parser.add_argument("--new-model", default=None, help="Target embedding model name")
    parser.add_argument("--persist-dir", default=None, help="Experience store directory")
    args = parser.parse_args()
    migrate(args.new_model, args.persist_dir)
```

- [ ] **Step 2: Commit**

```bash
git add agents/migrate_experiences.py
git commit -m "feat(eatp): add embedding migration script"
```

---

## Task 10: Run Full Test Suite and Verify

**Files:** None (verification only)

- [ ] **Step 1: Run all tests**

```bash
cd C:/Users/Frank/ai_agent && python -m pytest tests/ -v
```

Expected: All tests PASS (existing + new EATP tests).

- [ ] **Step 2: Verify EATP cold start does not break existing agent**

```bash
cd C:/Users/Frank/ai_agent && python -c "
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django; django.setup()
from agents.core import Agent
from openai import OpenAI
from django.conf import settings
client = OpenAI(api_key=settings.OPENAI_API_KEY)
agent = Agent(client, 'gpt-4.1', lambda: ('', False), [])
print('Agent created successfully')
print(f'Experience store: {agent.experience_store}')
print(f'Experience logger: {agent.experience_logger}')
print('EATP integration verified.')
"
```

Expected: Prints success messages. Agent creates without errors. Experience store is initialized.

- [ ] **Step 3: Final commit with all files staged**

```bash
cd C:/Users/Frank/ai_agent && git status
```

If any unstaged files remain, add and commit them.

---

## Dependency Graph

```
Task 1 (chromadb) ──► Task 2 (ExperienceStore) ──► Task 5 (retrieval integration)
                                                  ──► Task 6 (logging integration)
                                                  ──► Task 7 (denial capture)
                      Task 3 (ExperienceLogger) ──► Task 5
                                                 ──► Task 6
                      Task 4 (feedback tool) ─────► Task 5 (independent, just needs __init__ export)
                      Task 8 (eval runner) ────────► (independent, after Tasks 2-3)
                      Task 9 (migration) ──────────► (independent, after Task 2)
                      Task 10 (verification) ──────► (after all tasks)
```

**Parallelizable pairs:**
- Tasks 2 + 3 can be developed in parallel (no dependency on each other)
- Tasks 4 + 8 + 9 can be developed in parallel (all depend only on Task 2)
- Tasks 5 + 6 + 7 must be sequential (each builds on the prior integration)
