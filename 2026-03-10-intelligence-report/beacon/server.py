#!/usr/bin/env python3
"""
Beacon — Flask Dashboard & REST API
=====================================
Serves the dark-mode web dashboard and provides a REST API that:
  - Lists runs and their reports
  - Renders individual reports (Markdown + JSON)
  - Allows triggering a new pipeline run
  - Manages tracked topics (add / toggle / delete)

This is the "agent-facing API" layer: every endpoint is designed for
both human consumption (browser) and machine consumption (OpenClaw agent tool calls).
"""

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

# Import the pipeline (same package)
import sys
sys.path.insert(0, str(Path(__file__).parent))
from pipeline import get_db, run_pipeline, seed_default_topics

BASE_DIR = Path(__file__).parent
STATIC   = BASE_DIR / "static"

# ── API Helpers ───────────────────────────────────────────────────────────────

def json_response(handler, data: dict | list, status: int = 200) -> None:
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


def html_response(handler, html: str, status: int = 200) -> None:
    body = html.encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_body(handler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    raw    = handler.rfile.read(length) if length else b"{}"
    try:
        return json.loads(raw.decode())
    except Exception:
        return {}

# ── Request Handler ───────────────────────────────────────────────────────────

class BeaconHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Quiet the default access log spam
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"

        # ── Serve dashboard ─────────────────────────────────────────────────
        if path in ("/", "/dashboard"):
            html = (STATIC / "dashboard.html").read_text()
            html_response(self, html)
            return

        # ── API routes ──────────────────────────────────────────────────────
        conn = get_db()

        if path == "/api/status":
            last = conn.execute(
                "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            topic_count = conn.execute("SELECT COUNT(*) FROM topics WHERE active=1").fetchone()[0]
            article_count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            json_response(self, {
                "status":        "ok",
                "last_run":      dict(last) if last else None,
                "topic_count":   topic_count,
                "article_count": article_count,
            })

        elif path == "/api/runs":
            rows = conn.execute(
                "SELECT id, started_at, finished_at, articles_fetched, articles_surfaced, status, delivered "
                "FROM runs ORDER BY id DESC LIMIT 20"
            ).fetchall()
            json_response(self, [dict(r) for r in rows])

        elif path.startswith("/api/runs/"):
            run_id = path.split("/")[-1]
            row = conn.execute(
                "SELECT * FROM runs WHERE id=?", (run_id,)
            ).fetchone()
            if not row:
                json_response(self, {"error": "not found"}, 404)
                return
            data = dict(row)
            # Parse report_json for structured access
            if data.get("report_json"):
                data["report"] = json.loads(data["report_json"])
            json_response(self, data)

        elif path == "/api/topics":
            rows = conn.execute(
                "SELECT * FROM topics ORDER BY active DESC, id ASC"
            ).fetchall()
            json_response(self, [dict(r) for r in rows])

        elif path == "/api/articles/top":
            # Most relevant articles across all runs
            rows = conn.execute(
                "SELECT title, url, source, score, matched_topics, seen_at "
                "FROM articles WHERE score > 0.05 ORDER BY score DESC LIMIT 30"
            ).fetchall()
            json_response(self, [dict(r) for r in rows])

        else:
            json_response(self, {"error": "not found"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip("/")
        conn   = get_db()

        if path == "/api/run":
            # Trigger a pipeline run asynchronously
            body    = read_body(self)
            deliver = body.get("deliver", False)

            # Check if a run is already in progress
            running = conn.execute(
                "SELECT id FROM runs WHERE status='running'"
            ).fetchone()
            if running:
                json_response(self, {"error": "run already in progress", "run_id": running["id"]}, 409)
                return

            def _run():
                run_pipeline(deliver=deliver)

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            json_response(self, {"status": "started", "message": "Pipeline running in background"})

        elif path == "/api/topics":
            body = read_body(self)
            term = (body.get("term") or "").strip()
            if not term:
                json_response(self, {"error": "term required"}, 400)
                return
            now = datetime.now(timezone.utc).isoformat()
            try:
                conn.execute(
                    "INSERT INTO topics (term, active, created_at) VALUES (?,1,?)",
                    (term, now)
                )
                conn.commit()
                json_response(self, {"status": "added", "term": term})
            except sqlite3.IntegrityError:
                json_response(self, {"error": "topic already exists"}, 409)

        else:
            json_response(self, {"error": "not found"}, 404)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip("/")
        conn   = get_db()

        if path.startswith("/api/topics/"):
            topic_id = path.split("/")[-1]
            conn.execute("DELETE FROM topics WHERE id=?", (topic_id,))
            conn.commit()
            json_response(self, {"status": "deleted"})
        else:
            json_response(self, {"error": "not found"}, 404)


# ── Server entry point ────────────────────────────────────────────────────────

def run_server(port: int = 7460) -> None:
    # Initialize DB + seed topics before serving
    conn = get_db()
    seed_default_topics(conn)
    conn.close()

    server = HTTPServer(("0.0.0.0", port), BeaconHandler)
    print(f"[beacon] Dashboard: http://localhost:{port}")
    print(f"[beacon] API:       http://localhost:{port}/api/status")
    print(f"[beacon] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[beacon] Server stopped.")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=7460)
    args = p.parse_args()
    run_server(port=args.port)
