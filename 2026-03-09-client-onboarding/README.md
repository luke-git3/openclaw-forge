# Intake — AI-Powered Client Onboarding Automation

> **Portfolio Category:** Client Onboarding Automation  
> **OpenClaw Concepts:** Form → AI reasoning → document generation → persistent state → notification dispatch  
> **Stack:** Python + Flask + SQLite + Anthropic Claude (Haiku) + Discord webhook

---

## What It Does

**Intake** is a fully-automated client onboarding pipeline. A prospect fills out a form — 60 seconds later they have three personalized documents and your team has a Discord notification.

**The pipeline:**
```
[Intake Form]
     │
     ▼
[Save Client to SQLite Registry]
     │
     ├──► [AI: Generate Welcome Letter]  ─► persist to DB
     ├──► [AI: Generate Agent Config]    ─► persist to DB
     └──► [AI: Generate 30-Day Checklist] ─► persist to DB
                                                │
                                                ▼
                                    [Discord Webhook Notification]
```

**Three AI-generated documents per client:**

1. **Welcome Letter** — personalized to their industry, use case, and goals. Warm but professional. Signed by "The OpenClaw Team."
2. **Agent Config** — a recommended `openclaw.json`-style configuration: which skills to enable, what cron jobs to run, what integrations to wire up. Tailored to their use case and tech stack.
3. **30-Day Onboarding Checklist** — phased Markdown checklist (Days 1–10: Foundation, 11–20: Integration, 21–30: Scale & Polish) with items referencing their actual use case.

**Every AI step has a deterministic fallback** — the pipeline runs without an API key (template welcome letter, rule-based skill selection). This is the production-grade design principle.

---

## OpenClaw Concepts Demonstrated

| Concept | Implementation |
|---|---|
| **Form → AI reasoning** | Intake form data becomes structured prompt context. LLM generates three domain-specific documents. |
| **Persistent client registry** | SQLite database stores client profiles and generated docs. Idempotent — same email → same ID. |
| **Notification dispatch** | Discord webhook fires a rich embed with client summary and agent config highlights. |
| **Graceful AI fallback** | Every generation step (welcome letter, config, checklist) has a rule-based or template fallback. |
| **Sub-agent pattern** | `openclaw_agent.py` shows how the pipeline maps to `sessions_spawn` + `write` + `message` calls in a real OpenClaw agent. |
| **Config generation** | Agent config output is structured JSON matching OpenClaw's tool/skill/cron schema. |

See `openclaw_agent.py` for the exact mapping of each pipeline step to OpenClaw tool calls.

---

## How to Run

### Prerequisites
```bash
pip install flask anthropic requests python-dotenv
# or
pip install -r requirements.txt
```

### Environment (all optional — pipeline works without them)
```bash
export ANTHROPIC_API_KEY="sk-ant-..."          # enables AI generation (Claude Haiku)
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."  # enables notifications
```

### Start the server
```bash
python app.py
# → http://localhost:5050
```

### Routes
| Route | Description |
|---|---|
| `GET /` | Intake form |
| `GET /dashboard` | All onboarded clients |
| `GET /client/<id>` | Single client detail + all generated docs |
| `POST /onboard` | JSON API endpoint (form data or JSON body) |
| `POST /api/seed` | Seed 3 demo clients (idempotent) |

### Quick test (no server needed)
```bash
python seed_and_test.py           # runs pipeline for 3 demo clients, prints output
python seed_and_test.py --openclaw  # also runs the OpenClaw tool-call bridge demo
```

### API usage
```bash
curl -X POST http://localhost:5050/onboard \
  -H "Content-Type: application/json" \
  -d '{
    "contact_name": "Jane Smith",
    "company_name": "Acme AI",
    "email": "jane@acme.ai",
    "use_case": "Automated competitor intelligence monitoring",
    "industry": "Software / SaaS",
    "team_size": "1–10",
    "tech_stack": "GitHub, Slack, Python",
    "comms_channel": "Slack",
    "goals": "Track competitor releases daily, surface insights before Monday standup"
  }'
```

---

## Architecture

```
intake/
├── app.py              ← Flask routes and HTML rendering
├── onboard.py          ← Core pipeline: save_client, generate_*, send_discord_notification
├── openclaw_agent.py   ← OpenClaw tool-call bridge (teaching asset)
├── seed_and_test.py    ← Standalone test runner (no server needed)
├── clients.db          ← SQLite registry (auto-created)
├── templates/
│   └── index.html      ← Dark-mode UI: form / dashboard / detail views
└── requirements.txt
```

---

## Assumptions

1. **Claude Haiku** is used for all AI generation — cheapest capable model for document generation tasks (~$0.001 per onboarding run).
2. **SQLite** is the right persistence layer for a single-tenant demo. Production deployment would use Postgres or a managed DB.
3. **Discord webhook** is the notification mechanism. In a real OpenClaw deployment, `message(action="send", channel="discord")` replaces this.
4. **Idempotent by email** — same email address always maps to the same client ID (SHA-1 hash). Re-onboarding the same email regenerates docs but doesn't create a duplicate record.
5. **No auth** — this is a demo. Production deployment would add API key validation or OAuth.
6. The generated agent config is a **recommendation** — it uses OpenClaw's real skill/cron schema but isn't a live `openclaw.json`. A real deployment would write this to the client's workspace directory.

---

## Tutorial Value

This project is designed as Loom video content. The walkthrough structure:

1. **The problem** (2 min): Client onboarding is manual, inconsistent, and slow. Every AI consultant does it differently.
2. **Live demo** (5 min): Fill out form → watch pipeline execute → show all three generated documents → show Discord notification.
3. **Code walkthrough** (8 min): `onboard.py` → `run_onboarding()` → AI generation functions → fallback design → SQLite persistence.
4. **OpenClaw mapping** (5 min): Walk through `openclaw_agent.py` — how this same pipeline runs inside an OpenClaw agent using `sessions_spawn` + `write` + `message`.
5. **Extension ideas** (2 min): Add email delivery via SMTP, auto-create Discord channels per client, generate a full `openclaw.json` and push to GitHub.

**Key teaching moment:** The agent config output isn't just a document — it *is* the agent. When you generate JSON that tells an OpenClaw agent which skills to enable and what cron jobs to run, you've built a system that configures itself. That's the power of AI-native infrastructure.
