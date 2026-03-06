# OpenClaw Cron Setup Guide

This document explains how to wire the Pulse pipeline into OpenClaw as a scheduled cron job — the core concept this project demonstrates.

## What Is OpenClaw Cron?

OpenClaw cron lets you schedule any command or agent task to run automatically on a schedule, with:
- Standard cron expressions (or English-language schedules via some providers)
- Timezone-aware execution
- Discord/Telegram failure notifications
- Manual trigger support for testing

## Architecture Pattern Demonstrated

```
OpenClaw Cron Scheduler
        │
        ▼
  pipeline.py (triggered at 17:15 EST Mon-Fri)
        │
        ├─▶ Yahoo Finance API  → market_data dict
        ├─▶ RSS Feeds          → headlines list
        │
        ├─▶ Claude API (if key) ─┐
        │   or Template fallback ┘
        │                        ▼
        │                   briefing string
        │
        ├─▶ /reports/YYYY-MM-DD.md   (persists to disk)
        ├─▶ run_log.json             (rolling history)
        └─▶ Discord webhook          (real-time notification)
```

## Quick Start (5 minutes)

### 1. Install dependencies
```bash
cd /workspace/forge/2026-03-04-cron-market-briefing
pip install requests
# Optional for real AI synthesis:
pip install anthropic
```

### 2. Test with demo data (no network, no API keys)
```bash
python3 pipeline.py --demo
```

### 3. Test with live data (no Discord)
```bash
python3 pipeline.py --dry-run
```

### 4. Configure secrets (optional but recommended)
Edit `config.json`:
```json
{
  "discord_webhook": "https://discord.com/api/webhooks/YOUR_WEBHOOK",
  "anthropic_api_key": "sk-ant-..."
}
```

Or set as environment variables:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."
python3 pipeline.py
```

### 5. Register as OpenClaw cron job
```bash
openclaw cron add --file openclaw-cron.yaml
openclaw cron list   # verify it appears
```

### 6. View the dashboard
```bash
python3 -m http.server 8080
# Then open: http://localhost:8080/dashboard/
```

## Customizing the Schedule

Edit `openclaw-cron.yaml`:

| Schedule | Cron Expression |
|----------|-----------------|
| Daily at 5:15 PM EST (weekdays) | `15 17 * * 1-5` |
| Daily at 8 AM EST | `0 8 * * *` |
| Twice daily (9 AM + 4 PM) | `0 9,16 * * 1-5` |
| Every weekday morning | `30 7 * * 1-5` |

## Customizing the Tickers

Edit `config.json`:
```json
{
  "tickers": ["SPY", "QQQ", "AAPL", "TSLA", "BTC-USD", "GLD"],
  "headline_limit": 8
}
```

Any Yahoo Finance-compatible ticker works: equities, ETFs, crypto, commodities, FX pairs.

## Key OpenClaw Concepts Shown

1. **Cron scheduling** — time-triggered pipeline execution
2. **State persistence** — `run_log.json` survives between cron runs; the dashboard reads historical data
3. **Graceful degradation** — pipeline runs without API keys, falls back cleanly
4. **Multi-source ingestion** — multiple Yahoo Finance tickers + RSS feeds in a single run
5. **AI-as-synthesizer** — LLM sits between raw data and human-readable output
6. **Webhook delivery** — Discord notification with rich embed on completion

## Extending This

- Add an email delivery step (SMTP or SendGrid)
- Add sector rotation analysis (compare sector ETFs)
- Add portfolio P&L tracking (compare against your holdings)
- Store reports in S3 for long-term history
- Add a `/briefing` Discord slash command to trigger on-demand
