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
