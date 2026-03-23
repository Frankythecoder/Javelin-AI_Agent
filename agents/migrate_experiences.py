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
