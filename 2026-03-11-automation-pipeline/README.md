# ⚡ Nexus — AI-Powered End-to-End Automation Pipeline

A complete, runnable demonstration of the most important pattern in agentic AI engineering: **trigger → AI reasoning → conditional action → notification → optional sub-agent spawn**.

---

## What It Does

Any JSON event (price alert, system error, client message, ops notification) hits a webhook. Nexus runs it through a five-stage AI pipeline and takes the right action automatically:

| Urgency | Action     | What happens                                              |
|---------|------------|-----------------------------------------------------------|
| 1–2     | **LOG**    | Persisted to SQLite. No noise.                            |
| 3       | **ALERT**  | Markdown incident report written + Discord embed sent     |
| 4–5     | **ESCALATE** | ALERT + deep-dive sub-agent spawned for root-cause analysis |

The AI (Claude Haiku, or deterministic fallback) makes both the classification and the action decision. Rule-based logic kicks in if no API key is present — the pipeline **always runs**.

---

## OpenClaw Concepts Demonstrated

| Concept | Where |
|---------|-------|
| AI as middleware (LLM sits between ingestion and action) | `ai_reasoner.py` |
| Conditional action routing on AI output | `action_router.py` |
| Background threaded execution (non-blocking trigger) | `trigger_server.py` |
| Sub-agent spawning as first-class action | `action_router.py → _simulate_subagent_spawn()` |
| Structured audit trail (every decision recorded) | `store.py` + stages array |
| Discord notification integration | `notifier.py` |
| Graceful degradation (AI → rule fallback) | `ai_reasoner.py` |
| Full tool-call bridge (Python → OpenClaw) | `openclaw_agent.py` |

The `openclaw_agent.py` file is the teaching centrepiece — it maps every pipeline step to the exact OpenClaw `write` / `message` / `sessions_spawn` tool calls that would implement this natively.

---

## Architecture

```
POST /trigger  ──→  trigger_server.py
                         │
                    [background thread]
                         │
                    pipeline.py
                    ├── Stage 1: VALIDATE   (normalise payload)
                    ├── Stage 2: CLASSIFY   (ai_reasoner → category + urgency)
                    ├── Stage 3: DECIDE     (ai_reasoner → LOG/ALERT/ESCALATE)
                    ├── Stage 4: ACT        (action_router → report + notify + spawn)
                    └── Stage 5: FINALISE   (mark complete, record elapsed_ms)
                         │
                    store.py (SQLite)   reports/ (Markdown + JSON)
                         │
                    GET /run/<id>  →  dashboard.html
```

---

## How to Run

### 1. Install dependencies
```bash
cd /workspace/forge/2026-03-11-automation-pipeline
pip install flask
```

### 2. (Optional) Set your API key
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```
Without a key, the rule-based fallback handles classification and decisions automatically.

### 3. Start the server
```bash
python trigger_server.py
```
Server starts on `http://localhost:5010`.  Open the dashboard in your browser.

### 4. Fire demo triggers
In a second terminal:
```bash
python demo_triggers.py
```
This fires three events (low / medium / critical urgency) and prints the outcome for each, demonstrating all three action paths.

### 5. Fire a manual trigger
```bash
curl -X POST http://localhost:5010/trigger \
  -H "Content-Type: application/json" \
  -d '{"event_type":"price_alert","ticker":"NVDA","change_pct":-4.7,"urgency_hint":"high"}'
```

---

## Key Files

| File | Purpose |
|------|---------|
| `trigger_server.py` | Flask HTTP server, REST API, dashboard endpoint |
| `pipeline.py` | Five-stage pipeline orchestrator |
| `ai_reasoner.py` | Claude Haiku integration + rule-based fallbacks |
| `action_router.py` | Executes LOG / ALERT / ESCALATE actions |
| `notifier.py` | Discord webhook embed sender |
| `store.py` | SQLite persistence layer |
| `config.py` | All configuration in one place |
| `dashboard.html` | Dark-mode live dashboard (auto-refreshes every 3s) |
| `demo_triggers.py` | Fires test events and prints outcomes |
| `openclaw_agent.py` | **Teaching bridge** — maps every step to OpenClaw tools |
| `reports/` | Generated Markdown reports + sub-agent job stubs |

---

## Assumptions

1. **No OpenClaw API access in this demo** — `openclaw_agent.py` provides the exact tool calls that would run natively; the `action_router.py` simulates sub-agent spawning by writing a stub JSON file.
2. **Discord webhook** — if `DISCORD_WEBHOOK_URL` is not set, notifications are written to `reports/notify_<run_id>.json` instead.
3. **SQLite** — no external database required; `nexus.db` is created in the project directory.
4. **Flask only** — no Redis, Celery, or external queue. Pipeline runs in daemon threads for simplicity.

---

## For the Tutorial Video

**Core insight to teach:** *The LLM is not the product — the conditional branching on its output is.* Any webhook handler can route on HTTP status codes. Routing on AI reasoning (urgency, category, risk level) is the new primitive that makes pipelines intelligent rather than merely automated.

**Three teaching moments:**
1. `ai_reasoner.py` — show the dual-mode pattern (Claude → fallback)
2. `action_router.py` — the `if ESCALATE: spawn_subagent()` line — that's the payoff
3. `openclaw_agent.py` — walk through the tool-call sequence; this is how it runs natively in prod

---

*Built by Nexus Forge — 2026-03-11*
