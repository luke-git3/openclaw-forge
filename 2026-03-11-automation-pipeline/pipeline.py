"""
Nexus — Core Pipeline Orchestrator

Stages:
  1. VALIDATE   — normalise payload, extract metadata
  2. CLASSIFY   — AI categorises event + assigns urgency 1-5
  3. DECIDE     — AI chooses action: LOG / ALERT / ESCALATE
  4. ACT        — action_router executes the chosen action
  5. FINALISE   — mark run complete, persist to SQLite

Each stage appends a record to run["stages"] for full auditability.
Errors in any stage are caught; the run is marked "failed" and saved.
"""

import traceback
from datetime import datetime
from ai_reasoner import classify_event, decide_action
from action_router import execute_action


def run_pipeline(run_id: str, payload: dict, store):
    """Entry point — called in a background thread by trigger_server.py."""
    run = store.get_run(run_id)
    if not run:
        return

    try:
        run = _stage_validate(run, payload)
        store.save_run(run)

        run = _stage_classify(run)
        store.save_run(run)

        run = _stage_decide(run)
        store.save_run(run)

        run = _stage_act(run)
        store.save_run(run)

        run = _stage_finalise(run, success=True)
        store.save_run(run)

    except Exception as exc:
        run["status"]       = "failed"
        run["error"]        = str(exc)
        run["traceback"]    = traceback.format_exc()
        run["completed_at"] = _now()
        store.save_run(run)


# ── Stage implementations ──────────────────────────────────────────────────────

def _stage_validate(run: dict, payload: dict) -> dict:
    """Normalise payload and extract top-level metadata."""
    _start = _now()

    # Pull common fields if present; fall back to empty string
    event_type = (
        payload.get("event_type")
        or payload.get("type")
        or payload.get("event")
        or "unknown"
    )
    source = (
        payload.get("source")
        or payload.get("system")
        or payload.get("origin")
        or "unknown"
    )

    run["event_type"] = event_type
    run["source"]     = source
    run["payload"]    = payload
    run["status"]     = "classifying"

    run.setdefault("stages", []).append({
        "stage": "validate",
        "started_at": _start,
        "finished_at": _now(),
        "result": {"event_type": event_type, "source": source},
    })
    return run


def _stage_classify(run: dict) -> dict:
    """Ask the AI (or fallback) to categorise the event and score urgency."""
    _start = _now()
    clf = classify_event(run["payload"])

    run["classification"] = clf
    run["urgency"]        = clf["urgency"]
    run["summary"]        = clf["summary"]
    run["status"]         = "deciding"

    run["stages"].append({
        "stage": "classify",
        "started_at": _start,
        "finished_at": _now(),
        "result": clf,
    })
    return run


def _stage_decide(run: dict) -> dict:
    """Ask the AI (or fallback) to choose LOG / ALERT / ESCALATE."""
    _start = _now()
    dec = decide_action(run["classification"], run["payload"])

    run["decision"] = dec
    run["action"]   = dec["action"]
    run["status"]   = "acting"

    run["stages"].append({
        "stage": "decide",
        "started_at": _start,
        "finished_at": _now(),
        "result": dec,
    })
    return run


def _stage_act(run: dict) -> dict:
    """Execute the chosen action: write report, notify, spawn agent."""
    _start = _now()
    execute_action(run)   # mutates run in-place

    run["stages"].append({
        "stage": "act",
        "started_at": _start,
        "finished_at": _now(),
        "result": run.get("action_result", {}),
    })
    return run


def _stage_finalise(run: dict, success: bool) -> dict:
    """Mark the run complete and record elapsed time."""
    run["status"]       = "complete" if success else "failed"
    run["completed_at"] = _now()

    received  = run.get("received_at", run["completed_at"])
    try:
        from datetime import datetime as _dt
        start = _dt.fromisoformat(received.rstrip("Z"))
        end   = _dt.fromisoformat(run["completed_at"].rstrip("Z"))
        run["elapsed_ms"] = int((end - start).total_seconds() * 1000)
    except Exception:
        run["elapsed_ms"] = None

    return run


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"
