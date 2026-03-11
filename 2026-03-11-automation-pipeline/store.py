"""
Nexus — SQLite persistence layer.

Stores pipeline run records as JSON blobs so the dashboard and API can
retrieve full run history without any schema migrations.
"""

import sqlite3
import json
from datetime import datetime
from config import DB_PATH


class Store:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id      TEXT PRIMARY KEY,
                    received_at TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'queued',
                    action      TEXT,
                    urgency     INTEGER,
                    summary     TEXT,
                    data        TEXT NOT NULL    -- full JSON blob
                )
            """)
            conn.commit()

    # ── write ──────────────────────────────────────────────────────────────────

    def save_run(self, run: dict):
        """Insert or replace a run record."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO runs
                    (run_id, received_at, status, action, urgency, summary, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                run["run_id"],
                run.get("received_at", datetime.utcnow().isoformat() + "Z"),
                run.get("status", "queued"),
                run.get("action"),
                run.get("urgency"),
                run.get("summary"),
                json.dumps(run),
            ))
            conn.commit()

    # ── read ───────────────────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return json.loads(row["data"]) if row else None

    def list_runs(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM runs ORDER BY received_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(r["data"]) for r in rows]

    def stats(self) -> dict:
        with self._connect() as conn:
            total   = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            by_act  = conn.execute(
                "SELECT action, COUNT(*) as n FROM runs GROUP BY action"
            ).fetchall()
            by_stat = conn.execute(
                "SELECT status, COUNT(*) as n FROM runs GROUP BY status"
            ).fetchall()
        return {
            "total": total,
            "by_action": {r["action"] or "pending": r["n"] for r in by_act},
            "by_status": {r["status"]: r["n"] for r in by_stat},
        }
