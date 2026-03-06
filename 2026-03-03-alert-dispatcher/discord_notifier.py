"""
discord_notifier.py — Discord webhook sender with rich embeds

Sends structured alert embeds to Discord. Supports per-severity channel routing
via separate webhook URLs — critical alerts go to #critical-alerts, lower
severity to #alerts, etc.

Mock mode: when no webhook URL is configured, prints a formatted preview to
stdout so you can run the demo without any Discord setup.
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from config import Config

logger = logging.getLogger(__name__)


def _pick_webhook(config: Config, severity: str) -> Optional[str]:
    """Route to a severity-specific webhook, falling back to the default."""
    routing = {
        "critical": config.DISCORD_WEBHOOK_CRITICAL,
        "high":     config.DISCORD_WEBHOOK_HIGH,
        "low":      config.DISCORD_WEBHOOK_LOW,
    }
    return routing.get(severity) or config.DISCORD_WEBHOOK_URL or None


def _build_embed(alert: dict, config: Config) -> dict:
    """
    Build a Discord message embed from an enriched alert.

    Discord embed reference: https://discord.com/developers/docs/resources/channel#embed-object
    """
    severity   = alert.get("severity", "unknown")
    color      = config.SEVERITY_COLORS.get(severity, 0x90A4AE)
    emoji      = config.SEVERITY_EMOJI.get(severity, "⚪")
    tags       = alert.get("tags", [])
    action     = "⚠️ **Action required**" if alert.get("action_required") else "ℹ️ No immediate action needed"
    oncall     = "📟 On-call notified" if alert.get("oncall") else ""
    mode       = alert.get("enrichment_mode", "?")
    ms         = alert.get("enrichment_ms", 0)
    alert_id   = alert.get("id", "???")
    ts         = alert.get("timestamp", datetime.now(timezone.utc).isoformat())

    fields = [
        {"name": "Severity",  "value": f"{emoji} `{severity.upper()}`", "inline": True},
        {"name": "Channel",   "value": f"`#{alert.get('channel', '?')}`",  "inline": True},
        {"name": "Triage",    "value": f"`{mode}` ({ms}ms)",              "inline": True},
        {"name": "Status",    "value": f"{action}{' · ' + oncall if oncall else ''}", "inline": False},
    ]

    if tags:
        fields.append({"name": "Tags", "value": " · ".join(f"`{t}`" for t in tags), "inline": False})

    # Collapse the raw payload for context (truncated so it fits in Discord)
    raw_preview = json.dumps(alert.get("raw", {}), separators=(",", ":"))
    if len(raw_preview) > 800:
        raw_preview = raw_preview[:797] + "..."
    fields.append({"name": "Raw payload", "value": f"```json\n{raw_preview}\n```", "inline": False})

    embed = {
        "title":       f"{emoji} {alert.get('title', 'Alert')}",
        "description": alert.get("summary", ""),
        "color":       color,
        "fields":      fields,
        "footer":      {"text": f"Alert ID: {alert_id} · OpenClaw Alert Dispatcher"},
        "timestamp":   ts,
    }
    return embed


def _mock_print(alert: dict, config: Config):
    """Pretty-print the notification when no webhook is configured."""
    severity = alert.get("severity", "unknown")
    emoji    = config.SEVERITY_EMOJI.get(severity, "⚪")
    sep      = "─" * 60
    print(f"\n{sep}")
    print(f"  DISCORD MOCK — would send to #{alert.get('channel', 'alerts')}")
    print(sep)
    print(f"  {emoji} [{severity.upper()}] {alert.get('title', 'Alert')}")
    print(f"  {alert.get('summary', '')}")
    print(f"  Action required: {alert.get('action_required')}  |  On-call: {alert.get('oncall')}")
    print(f"  Tags: {', '.join(alert.get('tags', [])) or 'none'}")
    print(f"  Triage: {alert.get('enrichment_mode')} ({alert.get('enrichment_ms')}ms)")
    print(sep + "\n")


class DiscordNotifier:
    """
    Sends enriched alerts to Discord via webhook.

    Routing logic:
        DISCORD_WEBHOOK_CRITICAL → critical alerts
        DISCORD_WEBHOOK_HIGH     → high severity
        DISCORD_WEBHOOK_LOW      → low severity
        DISCORD_WEBHOOK_URL      → fallback / everything else

    All fields are optional — unset = mock mode.
    """

    def __init__(self, config: Config):
        self.config = config
        self._mock = not bool(config.DISCORD_WEBHOOK_URL)
        if self._mock:
            logger.info("DiscordNotifier: no webhook configured — running in mock mode")
        else:
            logger.info("DiscordNotifier: webhook configured — will send real messages")

    def send(self, alert: dict) -> bool:
        """
        Send an enriched alert to Discord. Returns True on success.

        Even in mock mode returns True so callers can treat it as success.
        """
        if self._mock:
            _mock_print(alert, self.config)
            return True

        webhook_url = _pick_webhook(self.config, alert.get("severity", "unknown"))
        if not webhook_url:
            _mock_print(alert, self.config)
            return True

        embed   = _build_embed(alert, self.config)
        payload = {
            "username": "🧠 Alert Brain",
            "embeds":   [embed],
        }

        try:
            resp = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            resp.raise_for_status()
            logger.info("Discord notification sent | status=%d | severity=%s",
                        resp.status_code, alert.get("severity"))
            return True
        except requests.RequestException as exc:
            logger.error("Failed to send Discord notification: %s", exc)
            return False
