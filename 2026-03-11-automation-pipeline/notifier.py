"""
Nexus — Discord notification layer.

Sends a rich embed to a Discord webhook.  If no webhook URL is configured,
writes the notification to a local file instead so the pipeline still completes.
"""

import json
import os
import urllib.request
from datetime import datetime
from config import DISCORD_WEBHOOK_URL, REPORTS_DIR, ACTION_ESCALATE, ACTION_ALERT


# Colour codes per action type
COLOURS = {
    ACTION_ESCALATE: 0xFF4444,   # red
    ACTION_ALERT:    0xFF9900,   # amber
    "LOG":           0x22AA55,   # green (not normally notified, but available)
    "default":       0x5865F2,   # discord blurple
}


def send_discord(run: dict) -> dict:
    """
    Send a Discord embed for the completed run.

    Returns {"sent": bool, "method": "webhook"|"file"|"error", "detail": str}
    """
    action       = run.get("action", "unknown").upper()
    urgency      = run.get("urgency", "?")
    summary      = run.get("summary", "Event processed.")
    run_id       = run.get("run_id", "???")
    received_at  = run.get("received_at", "")
    rationale    = run.get("decision", {}).get("rationale", "")
    category     = run.get("classification", {}).get("category", "unknown")
    ai_used      = run.get("classification", {}).get("ai_used", False)

    action_emoji = {"ESCALATE": "🚨", "ALERT": "⚠️", "LOG": "✅"}.get(action, "ℹ️")
    title        = f"{action_emoji} Nexus Pipeline — {action} | Run `{run_id}`"
    colour       = COLOURS.get(action, COLOURS["default"])

    fields = [
        {"name": "Category",  "value": category.title(), "inline": True},
        {"name": "Urgency",   "value": f"{urgency}/5",    "inline": True},
        {"name": "AI Used",   "value": "Yes" if ai_used else "No (template)", "inline": True},
        {"name": "Summary",   "value": summary[:200],     "inline": False},
    ]
    if rationale:
        fields.append({"name": "AI Rationale", "value": rationale[:200], "inline": False})
    if action == ACTION_ESCALATE:
        fields.append({
            "name":  "⚡ Sub-Agent Spawned",
            "value": "A deep-dive research agent has been queued for this event.",
            "inline": False,
        })

    embed = {
        "title":       title,
        "color":       colour,
        "fields":      fields,
        "footer":      {"text": f"Nexus Automation Pipeline  •  {received_at[:19]}Z"},
        "timestamp":   datetime.utcnow().isoformat() + "Z",
    }

    webhook_url = DISCORD_WEBHOOK_URL
    if webhook_url:
        try:
            body = json.dumps({"embeds": [embed]}).encode()
            req  = urllib.request.Request(
                webhook_url,
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
            return {"sent": True, "method": "webhook", "detail": f"HTTP {status}"}
        except Exception as exc:
            # fall through to file method
            return _write_notification_file(run, embed, f"webhook_error: {exc}")
    else:
        return _write_notification_file(run, embed, "no webhook configured")


def _write_notification_file(run: dict, embed: dict, reason: str) -> dict:
    """Persist the notification locally when no webhook is available."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    path = os.path.join(REPORTS_DIR, f"notify_{run['run_id']}.json")
    with open(path, "w") as f:
        json.dump({"reason": reason, "embed": embed, "run": run}, f, indent=2)
    return {"sent": False, "method": "file", "detail": path}
