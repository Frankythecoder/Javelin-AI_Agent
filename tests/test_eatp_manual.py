"""Quick smoke test for EATP — run this to see the pipeline working."""
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Minimal Django setup
import django
from django.conf import settings
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

if not settings.configured:
    settings.configure(
        DEBUG=True,
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
        INSTALLED_APPS=['chat'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3',
                               'NAME': os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db.sqlite3')}},
        BASE_DIR=Path(__file__).resolve().parent,
    )
    django.setup()

from agents.experience_store import ExperienceStore, ExperienceRecord
from agents.experience_logger import ExperienceLogger

# Use a temp directory so we don't pollute the real store
TEST_DIR = os.path.join(os.path.expanduser("~"), ".ai_agent", "experiences_smoketest")
if os.path.exists(TEST_DIR):
    shutil.rmtree(TEST_DIR)

store = ExperienceStore(persist_dir=TEST_DIR)
logger = ExperienceLogger()

print("=" * 50)
print("EATP SMOKE TEST")
print("=" * 50)

# Step 1: Store a successful experience
print("\n[1] Storing a successful file operation experience...")
record1 = logger.build_record(
    task_description="List all Python files in the project directory",
    task_category="file_ops",
    task_complexity="light",
    plan_summary="Use list_files to show .py files in current directory",
    tools_planned=["list_files"],
    tool_executions=[{
        "name": "list_files",
        "args": {"path": ".", "pattern": "*.py"},
        "result": "Found 12 files",
        "success": True,
        "error": None,
    }],
    user_corrections=[],
    approval_actions=[],
    outcome="success",
)
store.add(record1)
print(f"   Stored: {record1.id[:8]}... | category={record1.task_category} | outcome={record1.outcome}")

# Step 2: Store an experience WITH a user correction (the most valuable kind)
print("\n[2] Storing an experience with user correction...")
record2 = logger.build_record(
    task_description="Delete the old log files from the project directory",
    task_category="file_ops",
    task_complexity="heavy",
    plan_summary="Use delete_file to remove .log files",
    tools_planned=["list_files", "delete_file"],
    tool_executions=[
        {"name": "list_files", "args": {"path": "."}, "result": "Found 5 .log files", "success": True, "error": None},
    ],
    user_corrections=["User denied delete_file. Use list_files first to show which files before deleting. Ask for confirmation with specific file list."],
    approval_actions=[{"tool_name": "delete_file", "action": "denied"}],
    outcome="partial",
)
store.add(record2)
print(f"   Stored: {record2.id[:8]}... | category={record2.task_category} | outcome={record2.outcome}")
print(f"   Correction: {record2.user_corrections[0][:80]}...")

# Step 3: Store a travel experience
print("\n[3] Storing a travel booking experience...")
record3 = logger.build_record(
    task_description="Find flights from London to New York next Friday",
    task_category="travel",
    task_complexity="heavy",
    plan_summary="Use search_flights with origin LHR, destination JFK",
    tools_planned=["search_flights"],
    tool_executions=[{
        "name": "search_flights",
        "args": {"origin": "LHR", "destination": "JFK"},
        "result": "Found 8 flights",
        "success": True,
        "error": None,
    }],
    user_corrections=[],
    approval_actions=[],
    outcome="success",
)
store.add(record3)
print(f"   Stored: {record3.id[:8]}... | category={record3.task_category} | outcome={record3.outcome}")

# Step 4: Retrieve experiences for a SIMILAR query
print("\n" + "=" * 50)
print("[4a] Raw similarity scores for various queries:")
print("=" * 50)
test_queries = [
    "Delete the log files from this project",           # Very similar to record2
    "Clean up temp files in the build folder",           # Moderately similar
    "List Python files in my project",                   # Very similar to record1
    "Book a flight from London to NYC",                  # Similar to record3
    "What is the weather today?",                        # Unrelated
]
for q in test_queries:
    emb = store._embed_texts([q])[0]
    raw = store._collection.query(query_embeddings=[emb], n_results=3, include=["documents", "distances"])
    print(f"\n   Query: '{q}'")
    for j in range(len(raw["ids"][0])):
        sim = 1 - raw["distances"][0][j]
        doc = raw["documents"][0][j][:60]
        marker = " <-- ABOVE 0.75" if sim >= 0.75 else ""
        print(f"     {sim:.3f} | {doc}{marker}")

# Step 4b: Retrieve with a close query
print("\n" + "=" * 50)
print("[4b] Retrieving experiences for: 'Delete the log files from this project'")
print("=" * 50)

results = store.retrieve("Delete the log files from this project")
print(f"\n   Retrieved {len(results)} experience(s):")
for i, r in enumerate(results):
    print(f"\n   --- Result {i+1} ---")
    print(f"   Task: {r.task_description}")
    print(f"   Outcome: {r.outcome}")
    print(f"   Corrections: {r.user_corrections if r.user_corrections else 'None'}")

# Step 5: Show what gets injected into the prompt
print("\n" + "=" * 50)
print("[5] Prompt augmentation (what the LLM sees):")
print("=" * 50)
prompt_section = store.format_for_prompt(results)
if prompt_section:
    print(f"\n{prompt_section}")
else:
    print("\n   (No experiences above similarity threshold)")

# Step 6: Verify deduplication
print("\n" + "=" * 50)
print("[6] Testing deduplication — storing near-identical experience...")
print("=" * 50)
record4 = logger.build_record(
    task_description="List all Python files in the project directory",  # Same as record1
    task_category="file_ops",
    task_complexity="light",
    plan_summary="Use list_files tool",
    tools_planned=["list_files"],
    tool_executions=[{"name": "list_files", "args": {}, "result": "Found 15 files", "success": True, "error": None}],
    user_corrections=[],
    approval_actions=[],
    outcome="success",
)
store.add(record4)
all_records = store.get_all()
print(f"   Total records in store: {len(all_records)} (should be 3, not 4 — duplicate was consolidated)")

# Cleanup
print("\n" + "=" * 50)
print("SMOKE TEST COMPLETE")
print("=" * 50)
print(f"\nTest store location: {TEST_DIR}")
print("Run 'shutil.rmtree' on that path to clean up, or leave it for inspection.")
