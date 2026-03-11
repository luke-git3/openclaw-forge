"""
Nexus — Demo Trigger Script

Fires three test events that exercise all three action paths:
  Event 1 → urgency 1  → expects LOG
  Event 2 → urgency 3  → expects ALERT
  Event 3 → urgency 5  → expects ESCALATE

Usage:
  python demo_triggers.py [--host http://localhost:5010]

The script polls for each run's completion and prints the final outcome.
"""

import sys
import time
import json
import urllib.request
import urllib.error
import argparse

BASE = "http://localhost:5010"

DEMO_EVENTS = [
    {
        "label": "Low-urgency info event",
        "payload": {
            "event_type": "system_info",
            "source":     "monitoring",
            "message":    "Scheduled backup completed successfully.",
            "host":       "prod-db-01",
            "duration_s": 142,
        },
    },
    {
        "label": "Medium-urgency price alert",
        "payload": {
            "event_type": "price_alert",
            "source":     "market-data",
            "ticker":     "NVDA",
            "change_pct": -4.7,
            "price":      820.14,
            "threshold":  -4.0,
            "message":    "NVDA dropped 4.7% in the last hour, breaching the -4% alert threshold.",
        },
    },
    {
        "label": "Critical system error",
        "payload": {
            "event_type": "system_error",
            "source":     "order-management",
            "severity":   "critical",
            "error":      "OrderRouter: connection pool exhausted — 0 of 50 connections available",
            "service":    "order-router-v2",
            "pod":        "order-router-74d9b8c-xq7rz",
            "error_rate": "87%",
            "message":    "Order management system is rejecting 87% of incoming requests. Immediate intervention required.",
        },
    },
]


def post(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req  = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def poll_run(base: str, run_id: str, max_wait: int = 30) -> dict:
    """Poll /run/<id> until status is complete or failed."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        run = get(f"{base}/run/{run_id}")
        if run.get("status") in ("complete", "failed"):
            return run
        time.sleep(0.5)
    return {"status": "timeout", "run_id": run_id}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=BASE)
    args = parser.parse_args()
    base = args.host.rstrip("/")

    # Check server is up
    try:
        get(f"{base}/stats")
    except Exception as exc:
        print(f"[ERROR] Cannot reach Nexus at {base} — {exc}")
        print("  Start the server first:  python trigger_server.py")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Nexus Demo — firing {len(DEMO_EVENTS)} test events")
    print(f"{'='*60}\n")

    for i, event in enumerate(DEMO_EVENTS, 1):
        print(f"[{i}/{len(DEMO_EVENTS)}] {event['label']}")
        resp = post(f"{base}/trigger", event["payload"])
        run_id = resp["run_id"]
        print(f"  → queued as run_id: {run_id}")

        run = poll_run(base, run_id)
        status   = run.get("status", "?")
        action   = run.get("action", "?")
        urgency  = run.get("urgency", "?")
        summary  = run.get("summary", "")
        elapsed  = run.get("elapsed_ms")
        ai_used  = run.get("classification", {}).get("ai_used", False)

        status_icon = "✅" if status == "complete" else "⚠️"
        action_icon = {"LOG": "📋", "ALERT": "⚠️", "ESCALATE": "🚨"}.get(action, "❓")

        print(f"  {status_icon} Status:  {status}")
        print(f"  {action_icon} Action:  {action}  (urgency {urgency}/5)")
        print(f"  🤖 AI:     {'Claude' if ai_used else 'template fallback'}")
        print(f"  💬 Summary: {summary[:80]}")
        if elapsed:
            print(f"  ⏱  Elapsed: {elapsed} ms")

        # Show what was produced
        act_result = run.get("action_result", {})
        if act_result.get("report"):
            print(f"  📄 Report:  {act_result['report']}")
        if act_result.get("notify", {}).get("sent"):
            print(f"  📨 Discord: sent via webhook")
        elif act_result.get("notify", {}).get("method") == "file":
            print(f"  📨 Discord: saved to {act_result['notify']['detail']}")
        if act_result.get("subagent", {}).get("spawned"):
            print(f"  🤖 SubAgent: job queued → {act_result['subagent']['job_file']}")

        print()

    # Summary
    stats = get(f"{base}/stats")
    print(f"{'='*60}")
    print("  Pipeline Stats")
    print(f"{'='*60}")
    print(f"  Total runs:  {stats.get('total', 0)}")
    for act, cnt in (stats.get("by_action") or {}).items():
        icon = {"LOG": "📋", "ALERT": "⚠️", "ESCALATE": "🚨"}.get(act, "?")
        print(f"  {icon} {act}: {cnt}")
    print(f"\n  Dashboard: {base}/")
    print()


if __name__ == "__main__":
    main()
