# 🔷 Iris — AI Portfolio Intelligence Dashboard

**OpenClaw Forge | Build #6 | Category: Client-Facing Dashboards**  
Built: 2026-03-07 | Status: ✅ Working Prototype

---

## What It Does

Iris is a live, client-facing portfolio dashboard with an AI synthesis layer.  
It demonstrates the full stack pattern for OpenClaw client deployments:

```
Yahoo Finance API → Flask backend → LLM insight generation → Live HTML/JS dashboard
                                  ↕
                         OpenClaw agent (trigger, read, alert)
```

**Features:**
- **Live prices** from Yahoo Finance (no API key) with automatic 60-second refresh
- **AI-generated analyst commentary** per position (Claude → structured template fallback)
- **Agent activity feed** — a real-time log of every pipeline event (price fetch, AI synthesis, manual trigger)
- **Per-ticker refresh button** — triggers cache invalidation and fresh AI insight
- **SSE endpoint** for push updates (no WebSocket dependency)
- **REST API** designed for OpenClaw agent integration (`/api/portfolio`, `/api/refresh/<TICKER>`)
- **Dark mode, responsive UI** — looks like a real SaaS product

---

## OpenClaw Concepts Demonstrated

| Concept | Where |
|---|---|
| **Dashboard-as-API** — agent-readable REST endpoints | `iris.py` `/api/portfolio`, `/api/refresh` |
| **LLM synthesis layer** — Claude sits between raw data and client output | `generate_insight()` in `iris.py` |
| **Graceful degradation** — template fallback if no API key | `generate_insight()` |
| **Agent activity logging** — every pipeline step is visible to the client | `log_event()` + `/api/agent-feed` |
| **Push pattern** — agent reads dashboard data and posts Discord embed | `openclaw_agent.py --report` |
| **Pull pattern** — agent triggers refresh and polls for new state | `openclaw_agent.py --ticker NVDA` |
| **SSE streaming** — dashboard pushes heartbeats to browser | `/api/stream` |

---

## How to Run

### 1. Install dependencies
```bash
cd /workspace/forge/2026-03-07-client-dashboard
pip install -r requirements.txt
```

### 2. Start the dashboard
```bash
python iris.py
# → http://localhost:5007
```

Optionally add your Anthropic key for real AI insights:
```bash
ANTHROPIC_API_KEY=sk-ant-... python iris.py
```

### 3. Open the dashboard
```
http://localhost:5007
```

### 4. Test the OpenClaw agent integration layer
```bash
# Trigger a refresh for NVDA and print fresh insight
python openclaw_agent.py --ticker NVDA

# Build a Discord embed from live portfolio data
python openclaw_agent.py --report

# Print the agent activity log
python openclaw_agent.py --feed
```

---

## Architecture

```
iris.py (Flask)
├── GET  /                  → serves static/index.html
├── GET  /api/portfolio     → live prices + AI insights (JSON)
├── GET  /api/agent-feed    → agent activity log (JSON)
├── POST /api/refresh/<T>   → expire cache for ticker T
├── GET  /api/stream        → SSE heartbeat stream
└── GET  /api/health        → health check

static/index.html + JS
├── Fetch /api/portfolio on load + every 60s
├── Fetch /api/agent-feed every 15s
├── Per-ticker ↻ button → POST /api/refresh/<T>
└── Dark-mode responsive layout (no framework — vanilla JS/CSS)

openclaw_agent.py
├── push pattern: get_portfolio() → build_discord_embed() → (post to Discord)
└── pull pattern: trigger_refresh() → poll_until_refreshed()
```

---

## Assumptions

1. **Portfolio is hardcoded** — swap `PORTFOLIO` list in `iris.py` for real client data or a DB query.
2. **No authentication** — add Flask-Login or a Bearer token for production client deployments.
3. **In-memory state** — `price_cache`, `insight_cache`, `agent_log` reset on restart. Use Redis for persistence.
4. **Yahoo Finance** — unofficial endpoint, no API key. Use a paid data vendor for production.
5. **Claude Haiku** — cheap and fast for short analytical snippets. Upgrade to Sonnet for richer prose.
6. **Port 5007** — set `PORT` env var to change.

---

## File Map

```
2026-03-07-client-dashboard/
├── iris.py                 # Flask backend (prices, insights, REST API)
├── static/
│   └── index.html          # Dark-mode dashboard (HTML + vanilla JS)
├── openclaw_agent.py       # OpenClaw integration layer (push + pull patterns)
├── requirements.txt        # flask, requests
├── demo_data.json          # Sample API response (frontend dev without server)
├── README.md               # This file
└── BUILD_SUMMARY.md        # Recruiter-facing build summary
```
