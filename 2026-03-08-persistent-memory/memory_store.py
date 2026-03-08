"""
memory_store.py — SQLite-backed persistent memory store for Mnemosyne.

Responsibilities:
  - Store memories as text + JSON metadata in SQLite
  - Retrieve all memories for semantic ranking
  - CRUD operations: add, get, delete, list, tag-filter
  - Each memory has: id, content, tags, source, created_at, access_count

Design note: We keep this layer pure storage — no embedding/ranking logic lives here.
That separation lets you swap backends (Postgres, Redis, Chroma) without touching search.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).parent / "mnemosyne.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create schema on first run. Idempotent — safe to call every startup."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id          TEXT PRIMARY KEY,
                content     TEXT NOT NULL,
                tags        TEXT NOT NULL DEFAULT '[]',   -- JSON array
                source      TEXT NOT NULL DEFAULT 'user',
                importance  INTEGER NOT NULL DEFAULT 5,   -- 1 (low) to 10 (critical)
                created_at  TEXT NOT NULL,
                accessed_at TEXT NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories(tags)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC)
        """)
        conn.commit()


def add_memory(
    content: str,
    tags: list[str] | None = None,
    source: str = "user",
    importance: int = 5,
) -> dict:
    """
    Persist a new memory. Returns the full memory dict.

    Args:
        content:    The memory text (e.g. "User prefers dark mode UIs")
        tags:       Optional list of string tags for filtering (e.g. ["preference", "ui"])
        source:     Where this came from — 'user', 'agent', 'system', 'cron'
        importance: 1-10 weighting for retrieval scoring (10 = always surface)
    """
    now = datetime.now(timezone.utc).isoformat()
    memory = {
        "id": str(uuid.uuid4()),
        "content": content.strip(),
        "tags": json.dumps(tags or []),
        "source": source,
        "importance": max(1, min(10, importance)),
        "created_at": now,
        "accessed_at": now,
        "access_count": 0,
    }
    with _connect() as conn:
        conn.execute("""
            INSERT INTO memories (id, content, tags, source, importance, created_at, accessed_at, access_count)
            VALUES (:id, :content, :tags, :source, :importance, :created_at, :accessed_at, :access_count)
        """, memory)
        conn.commit()
    memory["tags"] = tags or []
    return memory


def get_all_memories(tag_filter: Optional[str] = None) -> list[dict]:
    """
    Retrieve all memories, optionally filtered by tag.
    Ordered by importance DESC, created_at DESC.
    """
    with _connect() as conn:
        if tag_filter:
            rows = conn.execute("""
                SELECT * FROM memories
                WHERE tags LIKE ?
                ORDER BY importance DESC, created_at DESC
            """, (f'%"{tag_filter}"%',)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM memories
                ORDER BY importance DESC, created_at DESC
            """).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_memory(memory_id: str) -> Optional[dict]:
    """Fetch a single memory by ID. Returns None if not found."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return _row_to_dict(row) if row else None


def delete_memory(memory_id: str) -> bool:
    """Delete a memory. Returns True if deleted, False if not found."""
    with _connect() as conn:
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
    return cursor.rowcount > 0


def record_access(memory_ids: list[str]):
    """Bump access_count and accessed_at for retrieved memories (recency weighting)."""
    if not memory_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    placeholders = ",".join("?" * len(memory_ids))
    with _connect() as conn:
        conn.execute(f"""
            UPDATE memories
            SET access_count = access_count + 1, accessed_at = ?
            WHERE id IN ({placeholders})
        """, [now] + memory_ids)
        conn.commit()


def get_stats() -> dict:
    """Return summary stats for the dashboard."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        by_source = conn.execute("""
            SELECT source, COUNT(*) as cnt FROM memories GROUP BY source
        """).fetchall()
        top_accessed = conn.execute("""
            SELECT id, content, access_count FROM memories
            ORDER BY access_count DESC LIMIT 5
        """).fetchall()
    return {
        "total": total,
        "by_source": {r["source"]: r["cnt"] for r in by_source},
        "top_accessed": [dict(r) for r in top_accessed],
    }


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d.get("tags", "[]"))
    return d
