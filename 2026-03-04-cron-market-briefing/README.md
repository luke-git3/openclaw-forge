# Pulse — AI Daily Market Briefing Pipeline

**OpenClaw Forge Build · 2026-03-04 · Category: Cron Automation**

A complete, production-ready cron automation pipeline that runs every weekday after market close, fetches live price data and news, synthesizes an AI briefing with Claude, saves a formatted markdown report, and delivers a rich embed to Discord.

---

## What It Demonstrates

| OpenClaw Concept | Implementation |
|-----------------|----------------|
| **Cron scheduling** | `openclaw-cron.yaml` — 5:15 PM EST, Mon–Fri |
| **State persistence** | `run_log.json` survives between runs; dashboard reads history |
| **Multi-source ingestion** | Yahoo Finance API + RSS feeds aggregated in one pass |
| **AI-as-synthesizer** | Claude sits between raw data and human output; graceful fallback |
| **Webhook delivery** | Discord rich embed with per-asset-class color coding |
| **Graceful degradation** | Works without API keys via template synthesis |

---

## Project Structure

```
2026-03-04-cron-market-briefing/
├── pipeline.py           # Main pipeline (all stages in one file)
├── config.json           # Tickers, feeds, API keys, schedule
├── openclaw-cron.yaml    # Drop-in cron registration config
├── openclaw-setup.md     # Full setup + extension guide
├── requirements.txt      # pip dependencies (just: requests)
├── dashboard/
│   └── index.html        # Historical report viewer (dark mode)
├── reports/              # Generated markdown reports (one per run)
│   └── YYYY-MM-DD.md
└── run_log.json          # Rolling history of pipeline runs
```

---

## Quick Start

### 1. Install
```bash
pip install requests
# Optional (enables real Claude synthesis):
pip install anthropic
```

### 2. Test with synthetic data (zero dependencies)
```bash
python3 pipeline.py --demo
```

### 3. Test with live data (no Discord)
```bash
python3 pipeline.py --dry-run
```

### 4. Full run
```bash
# Set secrets (or add to config.json)
export ANTHROPIC_API_KEY="sk-ant-..."
export DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."

python3 pipeline.py
```

### 5. Register as OpenClaw cron job
```bash
openclaw cron add --file openclaw-cron.yaml
openclaw cron list
```

### 6. View dashboard
```bash
python3 -m http.server 8080
# Open: http://localhost:8080/dashboard/
```

---

## Configuration

Edit `config.json` to customize tickers, news feeds, API keys, and schedule:

```json
{
  "tickers": ["SPY", "QQQ", "IWM", "BTC-USD", "GLD", "TLT"],
  "news_feeds": ["https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US"],
  "headline_limit": 6,
  "discord_webhook": "https://discord.com/api/webhooks/YOUR_WEBHOOK",
  "anthropic_api_key": "sk-ant-..."
}
```

Any Yahoo Finance ticker works: equities, ETFs, crypto, commodities, FX.

---

## Pipeline Stages

```
[5:15 PM EST trigger]
        │
        ▼
 fetch_market_data()   ← Yahoo Finance v8 API (no key required)
 fetch_news_headlines() ← RSS aggregation
        │
        ▼
 synthesize_briefing()
   ├── Claude API (if ANTHROPIC_API_KEY set)
   └── Template fallback (always works)
        │
        ▼
 save_report()         → reports/YYYY-MM-DD.md
 update_run_log()      → run_log.json
 send_discord_notification() → rich embed
```

---

## Discord Output

The pipeline sends a rich Discord embed with:
- Title: `📊 Daily Market Briefing — 2026-03-04`
- AI synthesis in the description
- Per-ticker price snapshot with arrows
- Color-coded by market direction (green/red/blue)
- Timestamp and "Pulse Pipeline · Powered by OpenClaw" footer

---

## Assumptions Made

1. **Yahoo Finance API stability** — Yahoo's v8 chart API has been stable for years but is undocumented. Robust error handling added per-ticker.
2. **Claude model** — Uses `claude-3-5-haiku-20241022` for cost efficiency in a cron context. Swap to `claude-3-5-sonnet` for higher quality at higher cost.
3. **5:15 PM EST schedule** — Assumes US equities use case. Adjust cron expression for other markets/timezones.
4. **Local file storage** — Reports saved to disk. For production, swap `save_report()` to write to S3 or another persistent store.
5. **No rate limiting** — Yahoo Finance has informal rate limits; with 6 tickers this is never an issue.

---

## Extending This Project

- **Add sector analysis**: Compare XLK, XLF, XLE, XLV for sector rotation signals
- **Track your portfolio**: Add position sizes to config, calculate daily P&L
- **Email delivery**: Add SMTP step alongside Discord
- **Weekly digest**: Second cron job that synthesizes the week's daily reports
- **Slack integration**: Swap Discord webhook for Slack incoming webhook
- **S3 storage**: Replace local `reports/` with `boto3.put_object()` for cloud persistence

---

*Built by Cortana (OpenClaw) · Forge Series · 2026-03-04*
