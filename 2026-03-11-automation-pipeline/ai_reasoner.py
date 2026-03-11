"""
Nexus — AI Reasoning Layer

Two responsibilities:
  1. classify_event()  → categorise + urgency score any incoming event payload
  2. decide_action()   → given classification, choose LOG / ALERT / ESCALATE

Both functions return structured dicts and have deterministic template fallbacks
so the pipeline keeps running even without an API key.
"""

import json
import re
from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    URGENCY_ALERT_MIN,
    URGENCY_ESCALATE_MIN,
    ACTION_LOG,
    ACTION_ALERT,
    ACTION_ESCALATE,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _call_claude(system: str, user: str) -> str:
    """Call Claude and return the raw text response.  Raises on failure."""
    import urllib.request
    payload = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 512,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read())
    return body["content"][0]["text"].strip()


def _extract_json(text: str) -> dict:
    """Pull the first {...} block from a string and parse it."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {}


# ── Public API ─────────────────────────────────────────────────────────────────

def classify_event(payload: dict) -> dict:
    """
    Classify an incoming event.

    Returns:
        {
          "category":  str,    # e.g. "finance", "client", "system", "ops"
          "urgency":   int,    # 1 (trivial) – 5 (critical)
          "summary":   str,    # one-sentence human-readable description
          "ai_used":   bool,
        }
    """
    if not ANTHROPIC_API_KEY:
        return _classify_fallback(payload)

    system = (
        "You are an event triage system. Given an arbitrary JSON event payload, "
        "classify it and return ONLY valid JSON (no markdown fences) with these exact keys:\n"
        '  "category": one of ["finance","client","system","ops","security","other"]\n'
        '  "urgency": integer 1-5 (1=trivial, 3=important, 5=critical)\n'
        '  "summary": one sentence describing what happened\n'
        "Be concise. Do not add explanations outside the JSON object."
    )
    user = f"Event payload:\n{json.dumps(payload, indent=2)}"

    try:
        raw = _call_claude(system, user)
        result = _extract_json(raw)
        if not result:
            raise ValueError("no JSON in response")
        return {
            "category": str(result.get("category", "other")),
            "urgency":  max(1, min(5, int(result.get("urgency", 2)))),
            "summary":  str(result.get("summary", "Event received.")),
            "ai_used":  True,
        }
    except Exception as exc:
        result = _classify_fallback(payload)
        result["fallback_reason"] = str(exc)
        return result


def decide_action(classification: dict, payload: dict) -> dict:
    """
    Decide what action to take.

    Returns:
        {
          "action":     "LOG" | "ALERT" | "ESCALATE",
          "rationale":  str,
          "confidence": float,   # 0.0 – 1.0
          "ai_used":    bool,
        }
    """
    if not ANTHROPIC_API_KEY:
        return _decide_fallback(classification)

    system = (
        "You are an AI action router. Given an event classification and its original payload, "
        "decide what action the system should take. Return ONLY valid JSON (no markdown) with:\n"
        '  "action": one of ["LOG","ALERT","ESCALATE"]\n'
        '    LOG      = record silently, no notification\n'
        '    ALERT    = write a report and send a Discord notification\n'
        '    ESCALATE = ALERT + flag for human review / spawn a deep-dive agent\n'
        '  "rationale": one sentence explaining why\n'
        '  "confidence": float 0.0-1.0\n'
        "Consider the urgency, category, and payload context."
    )
    user = (
        f"Classification:\n{json.dumps(classification, indent=2)}\n\n"
        f"Original payload:\n{json.dumps(payload, indent=2)}"
    )

    try:
        raw = _call_claude(system, user)
        result = _extract_json(raw)
        if not result:
            raise ValueError("no JSON in response")
        action = str(result.get("action", ACTION_LOG)).upper()
        if action not in (ACTION_LOG, ACTION_ALERT, ACTION_ESCALATE):
            action = ACTION_LOG
        return {
            "action":     action,
            "rationale":  str(result.get("rationale", "AI decision.")),
            "confidence": float(result.get("confidence", 0.7)),
            "ai_used":    True,
        }
    except Exception as exc:
        result = _decide_fallback(classification)
        result["fallback_reason"] = str(exc)
        return result


# ── Fallbacks (no API key) ─────────────────────────────────────────────────────

def _classify_fallback(payload: dict) -> dict:
    """Rule-based classifier when Claude is unavailable."""
    text = json.dumps(payload).lower()

    if any(k in text for k in ["price", "stock", "trade", "market", "equity", "portfolio"]):
        category = "finance"
    elif any(k in text for k in ["client", "customer", "user", "email", "contact"]):
        category = "client"
    elif any(k in text for k in ["error", "exception", "crash", "fail", "down", "timeout"]):
        category = "system"
    elif any(k in text for k in ["deploy", "build", "release", "pipeline", "ci"]):
        category = "ops"
    else:
        category = "other"

    # Simple urgency heuristics
    urgency = 2
    if any(k in text for k in ["critical", "urgent", "emergency", "down", "crash"]):
        urgency = 5
    elif any(k in text for k in ["warning", "alert", "spike", "anomaly"]):
        urgency = 3
    elif any(k in text for k in ["info", "notice", "log"]):
        urgency = 1

    event_type = payload.get("event_type", payload.get("type", "event"))
    return {
        "category": category,
        "urgency":  urgency,
        "summary":  f"{category.title()} {event_type} received (rule-based classification).",
        "ai_used":  False,
    }


def _decide_fallback(classification: dict) -> dict:
    """Rule-based action decision when Claude is unavailable."""
    urgency = classification.get("urgency", 2)

    if urgency >= URGENCY_ESCALATE_MIN:
        action     = ACTION_ESCALATE
        rationale  = f"Urgency {urgency} ≥ {URGENCY_ESCALATE_MIN}: auto-escalate threshold."
        confidence = 0.9
    elif urgency >= URGENCY_ALERT_MIN:
        action     = ACTION_ALERT
        rationale  = f"Urgency {urgency} ≥ {URGENCY_ALERT_MIN}: send alert."
        confidence = 0.85
    else:
        action     = ACTION_LOG
        rationale  = f"Urgency {urgency} < {URGENCY_ALERT_MIN}: log silently."
        confidence = 0.95

    return {
        "action":     action,
        "rationale":  rationale,
        "confidence": confidence,
        "ai_used":    False,
    }
