"""
Nexus — HTTP Trigger Server & REST API

Endpoints:
  POST /trigger          → queue a new pipeline run (returns run_id immediately)
  GET  /run/<run_id>     → full run detail (all stages, action result)
  GET  /runs             → recent run list (lightweight)
  GET  /stats            → aggregate counts by action / status
  GET  /                 → dashboard (dashboard.html)

The pipeline runs in a background thread so /trigger always returns < 50 ms.
"""

import os
import uuid
import threading
from datetime import datetime

from flask import Flask, request, jsonify, send_file
from store import Store
from pipeline import run_pipeline

app   = Flask(__name__)
store = Store()


# ── Trigger ────────────────────────────────────────────────────────────────────

@app.route("/trigger", methods=["POST"])
def trigger():
    """Accept any JSON payload and start the pipeline asynchronously."""
    payload = request.get_json(force=True, silent=True) or {}

    run_id = str(uuid.uuid4())[:8]
    run = {
        "run_id":      run_id,
        "received_at": datetime.utcnow().isoformat() + "Z",
        "payload":     payload,
        "status":      "queued",
        "stages":      [],
    }
    store.save_run(run)

    threading.Thread(
        target=run_pipeline,
        args=(run_id, payload, store),
        daemon=True,
    ).start()

    return jsonify({"run_id": run_id, "status": "queued"}), 202


# ── Run detail / history ───────────────────────────────────────────────────────

@app.route("/run/<run_id>", methods=["GET"])
def get_run(run_id):
    run = store.get_run(run_id)
    if not run:
        return jsonify({"error": "not found"}), 404
    return jsonify(run)


@app.route("/runs", methods=["GET"])
def list_runs():
    limit = int(request.args.get("limit", 50))
    return jsonify(store.list_runs(limit=limit))


@app.route("/stats", methods=["GET"])
def stats():
    return jsonify(store.stats())


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def dashboard():
    here = os.path.dirname(os.path.abspath(__file__))
    return send_file(os.path.join(here, "dashboard.html"))


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from config import SERVER_HOST, SERVER_PORT
    print(f"Nexus running on http://{SERVER_HOST}:{SERVER_PORT}")
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, threaded=True)
