"""
alert_store.py — JSON-backed alert persistence

Deliberately simple: a single JSON file on disk. Production would swap
this for Postgres or Redis, but the interface stays the same.
Demonstrates the OpenClaw pattern of treating storage as a replaceable layer.
"""
import json
import os
import fcntl
import uuid
from datetime import datetime, timezone
from typing import Optional


class AlertStore:
    """
    Thread-safe append-only store for enriched alerts.

    File layout:
        { "alerts": [ ...alert records... ] }

    Each record is an enriched alert dict plus:
        id, timestamp, ts_epoch
    """

    def __init__(self, path: str):
        self.path = path
        self._ensure_file()

    # ── Private ───────────────────────────────────────────────────────────────

    def _ensure_file(self):
        if not os.path.exists(self.path):
            self._write_raw({"alerts": []})

    def _read_raw(self) -> dict:
        with open(self.path, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f, fcntl.LOCK_UN)
        return data

    def _write_raw(self, data: dict):
        with open(self.path, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(data, f, indent=2, default=str)
            fcntl.flock(f, fcntl.LOCK_UN)

    # ── Public API ────────────────────────────────────────────────────────────

    def save(self, enriched: dict) -> dict:
        """Append an enriched alert. Returns the stored record (with id + timestamp)."""
        now = datetime.now(timezone.utc)
        record = {
            "id":         str(uuid.uuid4())[:8],
            "timestamp":  now.isoformat(),
            "ts_epoch":   int(now.timestamp()),
            **enriched,
        }
        data = self._read_raw()
        data["alerts"].append(record)
        self._write_raw(data)
        return record

    def recent(self, limit: int = 50) -> list:
        """Return the N most recent alerts, newest first."""
        data = self._read_raw()
        return list(reversed(data["alerts"][-limit:]))

    def count(self) -> int:
        return len(self._read_raw()["alerts"])

    def get(self, alert_id: str) -> Optional[dict]:
        for alert in self._read_raw()["alerts"]:
            if alert.get("id") == alert_id:
                return alert
        return None

    def severity_counts(self) -> dict:
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unknown": 0}
        for alert in self._read_raw()["alerts"]:
            sev = alert.get("severity", "unknown")
            counts[sev] = counts.get(sev, 0) + 1
        return counts
