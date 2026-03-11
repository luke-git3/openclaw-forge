"""
Nexus — Configuration & Constants
All tuneable knobs in one place.
"""

import os

# ─── AI ───────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL   = "claude-haiku-20240307"   # cheap, fast, good enough for triage

# ─── Discord ──────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv(
    "DISCORD_WEBHOOK_URL",
    ""
)
DISCORD_CHANNEL_ID = "1477502144612667544"   # forge-builds channel

# ─── Server ───────────────────────────────────────────────────────────────────
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5010

# ─── Storage ──────────────────────────────────────────────────────────────────
DB_PATH      = os.path.join(os.path.dirname(__file__), "nexus.db")
REPORTS_DIR  = os.path.join(os.path.dirname(__file__), "reports")

# ─── Action thresholds ────────────────────────────────────────────────────────
# Urgency is 1-5 (1 = trivial, 5 = critical).
# The AI recommends an action; these are the *minimum* overrides if AI is absent.
URGENCY_ALERT_MIN    = 3   # urgency >= 3 → at least ALERT
URGENCY_ESCALATE_MIN = 4   # urgency >= 4 → at least ESCALATE

# ─── Action labels ────────────────────────────────────────────────────────────
ACTION_LOG       = "LOG"
ACTION_ALERT     = "ALERT"
ACTION_ESCALATE  = "ESCALATE"
