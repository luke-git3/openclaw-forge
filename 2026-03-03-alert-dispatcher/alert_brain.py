"""
alert_brain.py — AI-powered alert enrichment

This is the core OpenClaw integration point. Raw webhook payloads arrive
unstructured; the Brain turns them into actionable, classified, routed alerts.

Two modes:
  AI mode   — Calls Claude via Anthropic SDK (set ANTHROPIC_API_KEY)
  Rule mode — Deterministic fallback using keyword heuristics (zero config)

In a production OpenClaw deployment, the AI call would go through the
OpenClaw agent runtime, enabling memory injection, skill chaining, and
multi-step reasoning. The prompt pattern here transfers directly.
"""
import json
import re
import time
import logging
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

# ── Prompt ───────────────────────────────────────────────────────────────────

TRIAGE_PROMPT = """You are an alert triage system for a software company.
Analyze the raw event below and respond with ONLY valid JSON — no prose.

Raw event:
{event_json}

Respond with this exact schema:
{{
  "severity": "critical|high|medium|low",
  "title": "Short alert title (max 60 chars)",
  "summary": "2-3 sentence human-readable explanation of what happened and why it matters",
  "channel": "critical-alerts|alerts|deployments|general",
  "action_required": true or false,
  "tags": ["tag1", "tag2"],
  "oncall": true or false
}}

Routing rules:
- critical → critical-alerts, oncall=true, action_required=true
- high     → alerts, oncall=false usually
- medium   → alerts or deployments depending on context
- low      → general
- Deployment events → channel=deployments
- Database, auth, payments → escalate severity"""


# ── Rule-based fallback ───────────────────────────────────────────────────────

_CRITICAL_KEYWORDS = {"down", "outage", "crash", "failed", "critical", "breach", "data loss",
                      "500", "timeout", "unresponsive", "payment failed", "auth failed"}
_HIGH_KEYWORDS     = {"error", "exception", "latency", "slow", "degraded", "high cpu",
                      "memory", "disk full", "warning", "alert", "spike"}
_LOW_KEYWORDS      = {"deployed", "started", "complete", "success", "healthy", "resumed",
                      "recovered", "info", "scheduled"}


def _rule_classify(payload: dict) -> dict:
    """Keyword-based triage when AI is not configured. Deterministic and fast."""
    text = json.dumps(payload).lower()

    if any(kw in text for kw in _CRITICAL_KEYWORDS):
        severity = "critical"
        channel  = "critical-alerts"
        oncall   = True
        action   = True
    elif any(kw in text for kw in _HIGH_KEYWORDS):
        severity = "high"
        channel  = "alerts"
        oncall   = False
        action   = True
    elif any(kw in text for kw in _LOW_KEYWORDS):
        severity = "low"
        channel  = "general"
        oncall   = False
        action   = False
    else:
        severity = "medium"
        channel  = "alerts"
        oncall   = False
        action   = False

    # Extract a usable title from common fields
    title = (
        payload.get("title") or
        payload.get("name") or
        payload.get("event") or
        payload.get("type") or
        "Unknown event"
    )[:60]

    # Build a minimal summary from available fields
    parts = []
    for key in ("message", "description", "detail", "error", "reason"):
        if payload.get(key):
            parts.append(str(payload[key]))
    summary = " ".join(parts)[:300] or f"Event received: {title}. Classified by rule engine."

    tags = []
    for key in ("service", "env", "environment", "region", "host"):
        if payload.get(key):
            tags.append(f"{key}:{payload[key]}")

    return {
        "severity":       severity,
        "title":          title,
        "summary":        summary,
        "channel":        channel,
        "action_required": action,
        "oncall":         oncall,
        "tags":           tags,
        "enrichment_mode": "rule-based",
    }


# ── AI enrichment ─────────────────────────────────────────────────────────────

def _ai_classify(payload: dict, config: Config) -> Optional[dict]:
    """Call Claude to enrich and classify the alert."""
    try:
        import anthropic  # optional dependency
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

        event_json = json.dumps(payload, indent=2)
        message = client.messages.create(
            model=config.AI_MODEL,
            max_tokens=512,
            timeout=config.AI_TIMEOUT,
            messages=[{"role": "user", "content": TRIAGE_PROMPT.format(event_json=event_json)}]
        )

        raw_text = message.content[0].text.strip()

        # Strip markdown code fences if the model wraps in ```json
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        result = json.loads(raw_text)
        result["enrichment_mode"] = "ai"
        return result

    except ImportError:
        logger.debug("anthropic SDK not installed — skipping AI enrichment")
        return None
    except Exception as exc:
        logger.warning("AI enrichment failed (%s) — falling back to rules", exc)
        return None


# ── Public API ────────────────────────────────────────────────────────────────

class AlertBrain:
    """
    The AlertBrain takes any raw JSON payload and returns a fully enriched,
    classified, routed alert record.

    Usage:
        brain = AlertBrain(config)
        enriched = brain.enrich(raw_webhook_payload)
    """

    def __init__(self, config: Config):
        self.config = config
        self._ai_available = bool(config.ANTHROPIC_API_KEY)
        mode = "AI" if self._ai_available else "rule-based"
        logger.info("AlertBrain initialized in %s mode", mode)

    def enrich(self, raw: dict) -> dict:
        """
        Enrich a raw event. Returns the classified, summarized alert dict.
        Always succeeds — rule-based fallback ensures no event is ever dropped.
        """
        t0 = time.time()

        # Try AI first; fall back to rules
        result = None
        if self._ai_available:
            result = _ai_classify(raw, self.config)

        if result is None:
            result = _rule_classify(raw)

        # Merge: keep the original payload as context, add enrichment on top
        enriched = {
            "raw":              raw,
            "severity":         result.get("severity", "unknown"),
            "title":            result.get("title", "Untitled alert"),
            "summary":          result.get("summary", ""),
            "channel":          result.get("channel", "alerts"),
            "action_required":  result.get("action_required", False),
            "oncall":           result.get("oncall", False),
            "tags":             result.get("tags", []),
            "enrichment_mode":  result.get("enrichment_mode", "unknown"),
            "enrichment_ms":    round((time.time() - t0) * 1000),
        }

        logger.info(
            "Enriched alert | severity=%s | channel=%s | mode=%s | %dms",
            enriched["severity"], enriched["channel"],
            enriched["enrichment_mode"], enriched["enrichment_ms"]
        )
        return enriched
