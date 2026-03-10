# 🔭 Beacon — Scheduled AI Intelligence Report Pipeline

> **Forge Build #9** | Portfolio Category: Scheduled Intelligence Report | Date: 2026-03-10

Beacon is a multi-source intelligence pipeline that tracks topics you care about across the web — automatically, on a schedule. Every run, it collects articles from Hacker News, RSS feeds, and GitHub Trending; scores them by relevance to your tracked topics; deduplicates against everything it's already seen; synthesizes a structured brief via Claude (with a template fallback); and delivers a Discord embed.

This is the **scheduled intelligence** pattern: not just periodic fetching, but stateful tracking — the pipeline knows what it's already read and only surfaces genuinely new signals.

---

## What It Demonstrates (OpenClaw Concepts)

| Concept | Implementation |
|---|---|
| **Cron scheduling** | `openclaw-cron.yaml` — daily and weekly jobs |
| **Multi-source collection** | HN API + 6 RSS feeds + GitHub Trending scrape |
| **Stateful deduplication** | SQLite `url_hash` index — seen articles skip silently |
| **Relevance scoring** | TF-IDF-inspired scoring vs tracked topics (no ML libs) |
| **LLM synthesis** | Claude synthesizes structure from raw articles |
| **Graceful degradation** | Template fallback if no `ANTHROPIC_API_KEY` |
| **Discord delivery** | Rich embed via webhook |
| **Agent-facing REST API** | Every endpoint returns JSON consumable by OpenClaw agents |
| **OpenClaw bridge** | `openclaw_agent.py` maps each pipeline stage to tool calls |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    BEACON PIPELINE                          │
│                                                             │
│  [Collect]  →  [Dedupe]  →  [Score]  →  [Synthesize]  →    │
│                                                             │
│   HN API         SQLite      TF-IDF    Claude Haiku         │
│   6×RSS feeds    url_hash    scoring   (template fallback)  │
│   GitHub HTML                                               │
│                                          ↓                  │
│                              [Render]  →  [Deliver]  →      │
│                                                             │
│                               Markdown    Discord webhook   │
│                               SQLite      (optional)        │
└─────────────────────────────────────────────────────────────┘
                         ↕ REST API
              ┌─────────────────────────┐
              │  Flask Dashboard         │
              │  dark-mode · responsive  │
              │  localhost:7460          │
              └─────────────────────────┘
```

---

## How to Run

### Prerequisites
- Python 3.10+
- Optional: `ANTHROPIC_API_KEY` (enables AI synthesis; template fallback otherwise)
- Optional: `BEACON_DISCORD_WEBHOOK` (enables Discord delivery)

### Quick Start
```bash
cd forge/2026-03-10-intelligence-report

# One-shot pipeline run
./run.sh

# Run + deliver to Discord
BEACON_DISCORD_WEBHOOK=https://discord.com/api/webhooks/... ./run.sh --deliver

# Start the dashboard (http://localhost:7460)
./run.sh --server

# Show OpenClaw tool call mappings
./run.sh --demo
```

### Run pipeline directly
```bash
cd beacon
python3 pipeline.py           # run once, no delivery
python3 pipeline.py --deliver # run + deliver to Discord
```

### Start dashboard
```bash
cd beacon
python3 server.py             # http://localhost:7460
python3 server.py --port 8080 # custom port
```

### REST API
```
GET  /api/status           → pipeline stats + last run
GET  /api/runs             → list of all runs (id, date, status, count)
GET  /api/runs/<id>        → full run data including report_json + report_md
GET  /api/topics           → all tracked topics
GET  /api/articles/top     → top-scoring articles across all runs
POST /api/run              → trigger pipeline run (async)
POST /api/topics           → add new topic {"term": "..."}
DEL  /api/topics/<id>      → remove topic
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Enable Claude synthesis |
| `BEACON_DISCORD_WEBHOOK` | — | Discord embed delivery URL |

Default topics (configurable via dashboard):
`OpenClaw`, `AI agent`, `LLM`, `automation`, `multi-agent`, `Claude`, `GPT`, `agentic`, `workflow`, `orchestration`, `RAG`, `prompt engineering`

---

## Files

```
2026-03-10-intelligence-report/
├── beacon/
│   ├── pipeline.py         ← Main pipeline (collect → score → synthesize → deliver)
│   ├── server.py           ← Flask REST API + dashboard server  
│   ├── schema.sql          ← SQLite schema (articles, topics, runs)
│   ├── openclaw_agent.py   ← OpenClaw tool call bridge (teaching material)
│   └── static/
│       └── dashboard.html  ← Dark-mode SPA dashboard
├── openclaw-cron.yaml      ← Drop-in cron schedule (daily + weekly)
├── requirements.txt
├── run.sh
├── README.md
└── BUILD_SUMMARY.md
```

---

## Assumptions Made

1. **No ML libraries** — TF-IDF scoring implemented from scratch (~30 lines). Avoids numpy/sklearn dependency.
2. **stdlib HTTP** — `urllib.request` instead of `requests`. Zero extra deps for the core pipeline.
3. **stdlib HTTP server** — `http.server.HTTPServer` in server.py. Flask is listed in requirements.txt but the server works without it.
4. **24/48h recency window** — Articles older than 48h are collected but deprioritized. This prevents a run on a fresh DB from surfacing stale content.
5. **HN API** — Uses the official Firebase REST API, not scraping. Rate-limited conservatively (30 stories).
6. **GitHub Trending** — HTML scrape with regex. Fragile by design (documented); fails gracefully to empty list.
7. **Discord via webhook** — No bot token needed. Operator sets `BEACON_DISCORD_WEBHOOK` env var.
8. **SQLite** — Right-sized for a single-user intelligence pipeline. Would swap for Postgres at scale.

---

## Why This Differs from Pulse (Category 3)

| | Pulse | Beacon |
|---|---|---|
| **Domain** | Markets only | Configurable topics |
| **State** | Stateless (each run is fresh) | Stateful (dedup across runs) |
| **Scoring** | No relevance scoring | TF-IDF topic scoring |
| **Sources** | Yahoo Finance + 2 RSS | HN API + 6 RSS + GitHub |
| **Scheduling angle** | Cron-as-trigger | Cron + stateful tracking |
| **Key concept** | Pipeline automation | Scheduled intelligence |

---

*Built by Cortana (OpenClaw AI) — Forge build system — Luke Stephens portfolio*
