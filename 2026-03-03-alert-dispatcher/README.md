# 🧠 Alert Brain — AI-Powered Alert Dispatcher

> **OpenClaw Forge Build #2** · Category: Messaging & Notification Integrations

Turn noisy, unstructured webhook events into routed, human-readable Discord
notifications — with AI triage in the middle.

---

## What It Does

```
Raw JSON webhook
       │
       ▼
┌─────────────────────────────────┐
│         Alert Brain (AI)        │  ← Claude classifies severity,
│  • Severity: critical/high/...  │    writes human summary, picks
│  • Title & human summary        │    routing channel
│  • Channel routing              │
│  • Action required / on-call?   │
└─────────────────────────────────┘
       │
       ├──────────────────► Discord webhook (rich embed, color-coded)
       │
       ├──────────────────► JSON store (persistent alert history)
       │
       └──────────────────► Live dashboard (polls every 5s)
```

No webhook structure required — send anything JSON. The AI figures out
what it is. Without an API key, a rule-based fallback handles classification
deterministically.

---

## OpenClaw Concepts Demonstrated

| Concept | Where |
|---------|-------|
| **AI as middleware** | `alert_brain.py` — LLM enriches unstructured events between ingestion and action |
| **Graceful degradation** | Rule-based fallback when AI is unavailable (zero config required) |
| **Structured output from LLM** | Prompt engineering for reliable JSON schema output |
| **Channel routing by AI classification** | Severity → Discord webhook URL routing |
| **Persistent state** | `alert_store.py` — JSON-backed store with file locking |
| **Rich Discord embeds** | Color-coded, fielded messages via webhook API |
| **Live dashboard** | Polling HTML UI reading from a local API |

---

## Quickstart

```bash
# 1. Install dependencies
pip install flask requests
# pip install anthropic  # optional — enables AI enrichment

# 2. (Optional) Configure
export ANTHROPIC_API_KEY="sk-ant-..."         # enables AI mode
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."  # real Discord

# 3. Start the server
python server.py

# 4. Fire test alerts (in another terminal)
python demo/fire_alerts.py

# 5. View the dashboard
open http://localhost:8765/
```

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PORT` | `8765` | Server listen port |
| `ANTHROPIC_API_KEY` | _(unset)_ | Enables AI enrichment via Claude |
| `AI_MODEL` | `claude-3-haiku-20240307` | Model for alert triage (haiku = fast + cheap) |
| `DISCORD_WEBHOOK_URL` | _(unset)_ | Default Discord webhook (all severity) |
| `DISCORD_WEBHOOK_CRITICAL` | _(unset)_ | Route critical alerts to separate channel |
| `DISCORD_WEBHOOK_HIGH` | _(unset)_ | Route high-severity alerts separately |
| `ALERT_DB_PATH` | `alerts.json` | Path to local JSON alert store |

**Zero config required** — without any env vars, the server runs in mock mode:
rule-based classification, Discord output printed to stdout.

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook` | `POST` | Ingest a raw alert (any JSON body) |
| `/alerts?limit=N` | `GET` | List recent alerts (JSON) |
| `/stats` | `GET` | Severity counts + uptime + mode info |
| `/health` | `GET` | Liveness probe |
| `/` | `GET` | Live dashboard |

### Sample webhook call

```bash
curl -s -X POST http://localhost:8765/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event": "database.failover",
    "service": "postgres-primary",
    "env": "production",
    "error": "Primary node unreachable after 3 health checks"
  }'
```

Response:
```json
{
  "status": "ok",
  "id": "a1b2c3d4",
  "severity": "critical",
  "channel": "critical-alerts",
  "enrichment_mode": "ai",
  "enrichment_ms": 847,
  "discord_sent": true
}
```

---

## Project Structure

```
2026-03-03-alert-dispatcher/
├── config.py             # All settings via env vars
├── alert_brain.py        # AI enrichment + rule-based fallback
├── alert_store.py        # JSON-backed persistence (thread-safe)
├── discord_notifier.py   # Discord webhook sender with rich embeds
├── server.py             # Flask webhook receiver + API + dashboard
├── dashboard/
│   └── index.html        # Live dashboard (polls /alerts every 5s)
├── demo/
│   └── fire_alerts.py    # 8 realistic test payloads
└── requirements.txt
```

---

## Assumptions Made

1. **Single-node deployment** — file locking (`fcntl`) covers concurrent requests but assumes one process. Production would use Postgres.
2. **Alert volume** — JSON store handles thousands of alerts comfortably. At 100k+, swap to SQLite.
3. **AI model** — defaulted to `claude-3-haiku` (fast, ~50ms, cheap). Upgrade to `claude-3-5-sonnet` for more nuanced triage.
4. **Discord embeds** — using webhook API directly (no bot token needed). Supports multiple channels via separate webhook URLs.
5. **No auth on `/webhook`** — production would add an `X-Webhook-Secret` HMAC check.

---

## Extending This

- **Add HMAC validation** on `/webhook` for production security
- **Slack support** — `discord_notifier.py` → `notifier.py` pattern, add `SlackNotifier`
- **PagerDuty integration** — trigger incidents when `oncall=true`
- **Metric aggregation** — add `/metrics` Prometheus endpoint
- **Alert deduplication** — hash raw payload, suppress duplicate fires within N minutes
- **Runbook links** — AI suggests relevant runbook URL based on alert type
