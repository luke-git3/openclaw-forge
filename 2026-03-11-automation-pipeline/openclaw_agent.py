"""
Nexus — OpenClaw Agent Bridge
================================================================================
This file is the *teaching layer* for this project.

It maps every step of the Nexus pipeline to the exact OpenClaw tool calls that
would implement the same logic natively inside an OpenClaw agent session.

Pattern:  Python function → OpenClaw tool call
         (what Nexus does)   (how it would work in OpenClaw)

Read this file to understand how to build an end-to-end automation pipeline
as a native OpenClaw skill, without running a separate Flask server.
================================================================================
"""

from __future__ import annotations
import json
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
#  STAGE 1 — RECEIVE TRIGGER
#  In OpenClaw, events arrive as inbound messages (Discord, Telegram, webhook).
#  The agent is woken up by the platform; no Flask server is needed.
# ═══════════════════════════════════════════════════════════════════════════════

def receive_trigger_openclaw(channel: str, message: str) -> dict:
    """
    OPENCLAW EQUIVALENT:
    The platform delivers the event as an inbound message to the agent session.
    The agent parses it from the message content or attachments.

    No explicit tool call needed — the event arrives in the agent prompt.
    """
    # Example: Discord message arrives with JSON payload in message body
    payload = json.loads(message)
    return payload


# ═══════════════════════════════════════════════════════════════════════════════
#  STAGE 2 — CLASSIFY EVENT (AI reasoning)
#  Same as in Python — the LLM itself IS the classifier when running inside
#  an OpenClaw agent.  No API call needed.
# ═══════════════════════════════════════════════════════════════════════════════

def classify_event_openclaw(payload: dict) -> str:
    """
    OPENCLAW EQUIVALENT:
    Inside an OpenClaw agent, the LLM performs classification inline as part
    of its reasoning.  You ask it to produce structured JSON and parse the response.

    Prompt structure (included in the agent's SKILL.md):

        You are a triage system. Given this event payload, return JSON:
        {"category": ..., "urgency": 1-5, "summary": "..."}

        Payload: {payload}

    The agent parses the JSON and proceeds — no tool call for classification itself.
    """
    return "classification happens inline in the agent reasoning step"


# ═══════════════════════════════════════════════════════════════════════════════
#  STAGE 3 — PERSIST RUN RECORD
#  The SQLite store maps to the write tool (flat JSON files) in OpenClaw.
# ═══════════════════════════════════════════════════════════════════════════════

def persist_run_openclaw(run: dict) -> dict:
    """
    OPENCLAW EQUIVALENT:
        tool: write
        params:
          file_path: /workspace/nexus/runs/{run_id}.json
          content: json.dumps(run, indent=2)

    For run history queries, the agent uses:
        tool: exec
        params:
          command: ls /workspace/nexus/runs/ | tail -20
    """
    return {
        "tool":   "write",
        "params": {
            "file_path": f"/workspace/nexus/runs/{run['run_id']}.json",
            "content":   json.dumps(run, indent=2),
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  STAGE 4a — WRITE MARKDOWN REPORT (ALERT / ESCALATE)
#  Identical to the write tool call above, just a different target path.
# ═══════════════════════════════════════════════════════════════════════════════

def write_report_openclaw(run: dict) -> dict:
    """
    OPENCLAW EQUIVALENT:
        tool: write
        params:
          file_path: /workspace/nexus/reports/report_{run_id}.md
          content: <markdown report string>
    """
    return {
        "tool":   "write",
        "params": {
            "file_path": f"/workspace/nexus/reports/report_{run['run_id']}.md",
            "content":   f"# Incident Report\n\n{run.get('summary', '')}\n...",
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  STAGE 4b — SEND DISCORD NOTIFICATION (ALERT / ESCALATE)
# ═══════════════════════════════════════════════════════════════════════════════

def notify_discord_openclaw(run: dict) -> dict:
    """
    OPENCLAW EQUIVALENT:
        tool: message
        params:
          action: send
          channel: discord
          target: "1477502144612667544"   # forge-builds channel
          message: |
            ⚠️ **Nexus ALERT — {run_id}**
            **Category:** {category}  |  **Urgency:** {urgency}/5
            {summary}
            **Rationale:** {rationale}

    For ESCALATE, you'd also send to a DM or a separate #escalations channel:
        target: "user:732337070252621845"
    """
    urgency  = run.get("urgency", "?")
    summary  = run.get("summary", "")
    run_id   = run.get("run_id", "?")
    category = run.get("classification", {}).get("category", "?")
    action   = run.get("action", "ALERT")
    rationale = run.get("decision", {}).get("rationale", "")

    emoji = {"ALERT": "⚠️", "ESCALATE": "🚨"}.get(action, "ℹ️")

    return {
        "tool": "message",
        "params": {
            "action":  "send",
            "channel": "discord",
            "target":  "1477502144612667544",
            "message": (
                f"{emoji} **Nexus {action} — `{run_id}`**\n"
                f"**Category:** {category}  |  **Urgency:** {urgency}/5\n"
                f"{summary}\n"
                f"**Rationale:** {rationale}"
            ),
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  STAGE 4c — SPAWN DEEP-DIVE SUB-AGENT (ESCALATE only)
#  This is the OpenClaw superpower: one agent spawning another.
# ═══════════════════════════════════════════════════════════════════════════════

def spawn_research_agent_openclaw(run: dict) -> dict:
    """
    OPENCLAW EQUIVALENT:
        tool: sessions_spawn
        params:
          task: |
            You are a deep-dive research agent.
            A {category} event was escalated with urgency {urgency}/5.
            Summary: {summary}

            Your job:
            1. Search the web for related context and background
            2. Assess likely root cause and business impact
            3. Recommend 3 specific next actions
            4. Write your report to /workspace/nexus/reports/deepdive_{run_id}.md
            5. Send a Discord DM to Luke (user:732337070252621845) when complete

            Be thorough. This was flagged as critical.
          mode: run
          runtime: subagent

    The parent agent gets back a session ID and can poll for completion.
    Key insight: the LLM decides WHEN to spawn — this is AI-native conditional logic.
    """
    run_id   = run.get("run_id", "?")
    category = run.get("classification", {}).get("category", "?")
    urgency  = run.get("urgency", "?")
    summary  = run.get("summary", "")

    return {
        "tool": "sessions_spawn",
        "params": {
            "task": (
                f"You are a deep-dive research agent.\n"
                f"A {category} event was escalated with urgency {urgency}/5.\n"
                f"Summary: {summary}\n\n"
                f"1. Search the web for context\n"
                f"2. Assess root cause and impact\n"
                f"3. Recommend 3 next actions\n"
                f"4. Write report to /workspace/nexus/reports/deepdive_{run_id}.md\n"
                f"5. Send Discord DM to Luke (channel=discord, target=user:732337070252621845) when done"
            ),
            "mode":    "run",
            "runtime": "subagent",
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  FULL PIPELINE — end-to-end walkthrough
# ═══════════════════════════════════════════════════════════════════════════════

def full_pipeline_openclaw(event_payload: dict) -> list[dict]:
    """
    Returns the sequence of OpenClaw tool calls that implement the full pipeline
    for a given event payload.

    This is the canonical teaching reference for the pattern:
      Trigger → Classify → Decide → Act → Notify → (optionally) Spawn
    """
    run_id = "abc12345"   # illustrative
    run    = {"run_id": run_id, **event_payload}

    steps = []

    # 1. Persist initial run record
    steps.append({
        "step":        "1_persist_queued",
        "description": "Save run record to workspace",
        **persist_run_openclaw(run),
    })

    # 2. Classification & decision happen in the agent's reasoning (no tool call)
    steps.append({
        "step":        "2_classify_decide",
        "description": "LLM classifies event and decides action inline (no tool call)",
        "tool":        "(inline reasoning)",
        "params":      {"prompt": "Classify this event and decide: LOG / ALERT / ESCALATE"},
    })

    # 3a. If ALERT or ESCALATE: write report
    steps.append({
        "step":        "3a_write_report",
        "description": "Write Markdown incident report",
        **write_report_openclaw(run),
    })

    # 3b. Send Discord notification
    run["action"]   = "ALERT"
    run["urgency"]  = 3
    run["summary"]  = "Example alert event"
    run["classification"] = {"category": "finance"}
    run["decision"]       = {"rationale": "Urgency threshold exceeded."}
    steps.append({
        "step":        "3b_notify",
        "description": "Send Discord embed to forge-builds channel",
        **notify_discord_openclaw(run),
    })

    # 3c. If ESCALATE: spawn sub-agent
    run["action"] = "ESCALATE"
    run["urgency"] = 5
    steps.append({
        "step":        "3c_spawn_subagent",
        "description": "Spawn deep-dive research agent (ESCALATE only)",
        **spawn_research_agent_openclaw(run),
    })

    # 4. Update run record to 'complete'
    run["status"] = "complete"
    steps.append({
        "step":        "4_persist_complete",
        "description": "Update run record with final status",
        **persist_run_openclaw(run),
    })

    return steps


# ── Demo ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    payload = {
        "event_type": "system_error",
        "source":     "order-management",
        "message":    "Connection pool exhausted. 87% of requests failing.",
        "severity":   "critical",
    }
    steps = full_pipeline_openclaw(payload)
    print("\n=== Nexus Pipeline — OpenClaw Tool Call Sequence ===\n")
    for s in steps:
        print(f"  Step {s['step']}: {s['description']}")
        print(f"    Tool:   {s.get('tool', '?')}")
        params = s.get("params", {})
        for k, v in params.items():
            val = str(v)[:80] + ("…" if len(str(v)) > 80 else "")
            print(f"    {k}: {val}")
        print()
