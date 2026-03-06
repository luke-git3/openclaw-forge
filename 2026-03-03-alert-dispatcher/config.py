"""
config.py — Alert Dispatcher configuration

All settings are environment-variable driven so this deploys cleanly
to any environment. Sensible defaults make local dev zero-config.
"""
import os


class Config:
    # ── Webhook server ──────────────────────────────────────────────────────
    HOST: str = os.environ.get("HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("PORT", "8765"))

    # ── AI enrichment ───────────────────────────────────────────────────────
    # Set ANTHROPIC_API_KEY to enable real AI enrichment.
    # Leave unset → falls back to deterministic rule-based triage.
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    AI_MODEL: str = os.environ.get("AI_MODEL", "claude-3-haiku-20240307")
    AI_TIMEOUT: int = int(os.environ.get("AI_TIMEOUT", "10"))  # seconds

    # ── Discord ─────────────────────────────────────────────────────────────
    # Set DISCORD_WEBHOOK_URL to post real messages.
    # Leave unset → mock mode (prints to stdout, stores locally).
    DISCORD_WEBHOOK_URL: str = os.environ.get("DISCORD_WEBHOOK_URL", "")

    # Map severity → separate webhook URLs for channel routing.
    # Falls back to DISCORD_WEBHOOK_URL if not set.
    DISCORD_WEBHOOK_CRITICAL: str = os.environ.get("DISCORD_WEBHOOK_CRITICAL", "")
    DISCORD_WEBHOOK_HIGH: str = os.environ.get("DISCORD_WEBHOOK_HIGH", "")
    DISCORD_WEBHOOK_LOW: str = os.environ.get("DISCORD_WEBHOOK_LOW", "")

    # ── Persistence ─────────────────────────────────────────────────────────
    ALERT_DB_PATH: str = os.environ.get("ALERT_DB_PATH", "alerts.json")

    # ── Severity color map (Discord embed colors, decimal) ──────────────────
    SEVERITY_COLORS: dict = {
        "critical": 0xE53935,   # red
        "high":     0xFB8C00,   # orange
        "medium":   0xFDD835,   # yellow
        "low":      0x43A047,   # green
        "unknown":  0x90A4AE,   # grey
    }

    SEVERITY_EMOJI: dict = {
        "critical": "🔴",
        "high":     "🟠",
        "medium":   "🟡",
        "low":      "🟢",
        "unknown":  "⚪",
    }
