"""
onboard.py — Core onboarding engine for Intake

Handles:
  1. AI-powered welcome letter generation
  2. Dynamic agent config generation (which tools/skills to enable)
  3. 30-day onboarding checklist tailored to use case
  4. SQLite client registry
  5. Discord webhook notification (optional)

Design principle: every AI step has a deterministic template fallback.
The pipeline works without a Claude key — you just lose the personalization layer.
"""

import os
import json
import sqlite3
import hashlib
import datetime
import textwrap
import requests
from typing import Optional

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
DISCORD_WEBHOOK    = os.getenv("DISCORD_WEBHOOK_URL", "")   # optional
DB_PATH            = os.path.join(os.path.dirname(__file__), "clients.db")

CLAUDE_MODEL = "claude-3-5-haiku-20241022"   # fast + cheap for onboarding tasks

# ── Database helpers ──────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the clients table + documents table if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id          TEXT PRIMARY KEY,
            created_at  TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'active',
            contact_name  TEXT NOT NULL,
            company_name  TEXT NOT NULL,
            email         TEXT NOT NULL,
            use_case      TEXT NOT NULL,
            industry      TEXT NOT NULL,
            team_size     TEXT NOT NULL,
            tech_stack    TEXT NOT NULL,
            comms_channel TEXT NOT NULL,
            goals         TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS client_docs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id   TEXT NOT NULL,
            doc_type    TEXT NOT NULL,  -- 'welcome_letter' | 'agent_config' | 'checklist'
            content     TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );
    """)
    conn.commit()
    conn.close()


def save_client(data: dict) -> str:
    """
    Insert a new client record. Returns the client_id (short hash).
    Idempotent: if the same email is submitted twice, returns the existing ID.
    """
    client_id = hashlib.sha1(data["email"].lower().encode()).hexdigest()[:8]
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO clients
                (id, created_at, contact_name, company_name, email, use_case,
                 industry, team_size, tech_stack, comms_channel, goals)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            client_id,
            datetime.datetime.utcnow().isoformat(),
            data["contact_name"],
            data["company_name"],
            data["email"],
            data["use_case"],
            data["industry"],
            data["team_size"],
            data.get("tech_stack", ""),
            data["comms_channel"],
            data["goals"],
        ))
        conn.commit()
    except sqlite3.IntegrityError:
        pass   # already exists — idempotent
    finally:
        conn.close()
    return client_id


def save_doc(client_id: str, doc_type: str, content: str) -> None:
    conn = get_db()
    conn.execute("""
        INSERT INTO client_docs (client_id, doc_type, content, created_at)
        VALUES (?, ?, ?, ?)
    """, (client_id, doc_type, content, datetime.datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def get_all_clients() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM clients ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_client(client_id: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_client_docs(client_id: str) -> dict:
    conn = get_db()
    rows = conn.execute(
        "SELECT doc_type, content FROM client_docs WHERE client_id = ? ORDER BY created_at DESC",
        (client_id,)
    ).fetchall()
    conn.close()
    # latest version of each doc type
    docs: dict = {}
    for r in rows:
        if r["doc_type"] not in docs:
            docs[r["doc_type"]] = r["content"]
    return docs

# ── AI generation helpers ─────────────────────────────────────────────────────

def _call_claude(prompt: str, system: str = "") -> str:
    """Call Claude Haiku. Returns plain text. Raises on failure."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=system or "You are an expert AI implementation consultant producing concise, professional onboarding documents.",
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def generate_welcome_letter(client_data: dict) -> tuple[str, bool]:
    """
    Generate a personalized welcome letter.
    Returns (letter_text, ai_generated: bool).
    Falls back to a polished template if Claude is unavailable.
    """
    if ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
        prompt = textwrap.dedent(f"""
            Write a warm, professional welcome letter for a new OpenClaw AI automation client.

            Client details:
            - Contact: {client_data['contact_name']}
            - Company: {client_data['company_name']}
            - Industry: {client_data['industry']}
            - Primary use case: {client_data['use_case']}
            - Goals: {client_data['goals']}
            - Preferred comms: {client_data['comms_channel']}
            - Team size: {client_data['team_size']}

            The letter should:
            1. Welcome them warmly and acknowledge their specific use case
            2. Set clear expectations for the 30-day onboarding
            3. Name 2-3 specific capabilities we'll enable for their use case
            4. End with a concrete next step (schedule kickoff call)

            Keep it under 350 words. Professional but not robotic.
        """)
        try:
            return _call_claude(prompt), True
        except Exception as e:
            print(f"[welcome_letter] Claude failed: {e}. Using template.")

    # Template fallback
    letter = textwrap.dedent(f"""
        Dear {client_data['contact_name']},

        Welcome to OpenClaw — we're excited to have {client_data['company_name']} on board.

        Based on your intake form, we understand you're looking to automate "{client_data['use_case']}" for your {client_data['team_size']} team in the {client_data['industry']} space. That's exactly the kind of high-impact workflow where OpenClaw agents shine.

        Over the next 30 days, we'll work through three phases:

        **Phase 1 — Foundation (Days 1–10)**
        Deploy your first working agent, connect your preferred channel ({client_data['comms_channel']}), and run your first automated workflow end-to-end.

        **Phase 2 — Integration (Days 11–20)**
        Connect your existing tools and data sources, build out your primary use case pipeline, and establish your agent memory and context system.

        **Phase 3 — Scale & Polish (Days 21–30)**
        Harden the pipelines, add monitoring and alerting, document everything, and hand off to your team with full runbooks.

        Your stated goals — "{client_data['goals']}" — will be the north star for every decision we make.

        **Next step:** Please reply to schedule your kickoff call. We'll spend 30 minutes mapping your stack, setting up your first workspace, and deploying a live demo before we hang up.

        Looking forward to building something great together.

        — The OpenClaw Team
    """).strip()
    return letter, False


def generate_agent_config(client_data: dict) -> tuple[dict, bool]:
    """
    Generate a recommended OpenClaw agent configuration.
    Returns (config_dict, ai_generated: bool).
    """
    # Base config scaffold — always present
    base_config = {
        "agent": {
            "name": f"{client_data['company_name'].replace(' ', '_').lower()}-agent",
            "model": "anthropic/claude-sonnet-4-5",
            "channel": client_data["comms_channel"].lower(),
            "memory_enabled": True,
        },
        "skills": [],
        "cron_jobs": [],
        "integrations": [],
        "notes": "",
    }

    if ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
        prompt = textwrap.dedent(f"""
            You are configuring an OpenClaw AI agent for a new client. Return ONLY valid JSON (no markdown, no explanation).

            Client profile:
            - Company: {client_data['company_name']}
            - Industry: {client_data['industry']}
            - Use case: {client_data['use_case']}
            - Goals: {client_data['goals']}
            - Tech stack: {client_data.get('tech_stack', 'standard')}
            - Team size: {client_data['team_size']}
            - Comms channel: {client_data['comms_channel']}

            Available OpenClaw skills: web-search, summarize, github, discord, telegram, weather, finsnap, qmd, healthcheck, skill-creator

            Return this exact JSON structure, populated with your recommendations:
            {{
              "agent": {{
                "name": "<company-slug>-agent",
                "model": "anthropic/claude-sonnet-4-5",
                "channel": "{client_data['comms_channel'].lower()}",
                "memory_enabled": true
              }},
              "skills": ["<skill1>", "<skill2>"],
              "cron_jobs": [
                {{"schedule": "0 9 * * 1-5", "task": "<description>", "output_channel": "{client_data['comms_channel'].lower()}"}}
              ],
              "integrations": ["<integration1>"],
              "notes": "<2-3 sentence rationale for these choices>"
            }}
        """)
        try:
            raw = _call_claude(prompt)
            # Strip markdown fences if present
            raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            config = json.loads(raw)
            # Merge with base so required keys always exist
            base_config.update(config)
            return base_config, True
        except Exception as e:
            print(f"[agent_config] Claude failed: {e}. Using rule-based config.")

    # Rule-based fallback — map use case keywords to skills
    use_case_lower = client_data["use_case"].lower()
    goals_lower = client_data["goals"].lower()
    combined = use_case_lower + " " + goals_lower

    skills = []
    crons = []

    if any(w in combined for w in ["research", "web", "news", "market", "intelligence"]):
        skills.append("web-search")
        skills.append("summarize")
        crons.append({
            "schedule": "0 8 * * 1-5",
            "task": "Daily briefing: fetch top industry news, synthesize, deliver to channel",
            "output_channel": client_data["comms_channel"].lower(),
        })

    if any(w in combined for w in ["github", "code", "pr", "deploy", "engineering"]):
        skills.append("github")
        crons.append({
            "schedule": "0 9 * * 1-5",
            "task": "Morning PR/issue digest: pull open PRs and critical issues, summarize for team",
            "output_channel": client_data["comms_channel"].lower(),
        })

    if any(w in combined for w in ["finance", "portfolio", "market", "stock", "invest"]):
        skills.append("finsnap")
        crons.append({
            "schedule": "0 7 * * 1-5",
            "task": "Pre-market snapshot: prices, sentiment, key moves overnight",
            "output_channel": client_data["comms_channel"].lower(),
        })

    if any(w in combined for w in ["customer", "support", "ticket", "onboard", "crm"]):
        skills.append("summarize")
        crons.append({
            "schedule": "0 18 * * 1-5",
            "task": "EOD customer activity summary: new tickets, resolutions, escalations",
            "output_channel": client_data["comms_channel"].lower(),
        })

    if any(w in combined for w in ["report", "pipeline", "automat", "workflow", "schedule"]):
        skills.extend(["web-search", "summarize"])
        crons.append({
            "schedule": "0 7 * * 1",
            "task": "Weekly intelligence report: synthesize prior week data, send to channel",
            "output_channel": client_data["comms_channel"].lower(),
        })

    # Deduplicate
    skills = list(dict.fromkeys(skills)) or ["web-search", "summarize"]
    if not crons:
        crons.append({
            "schedule": "0 9 * * 1-5",
            "task": "Daily status check: system health + key metrics delivered to channel",
            "output_channel": client_data["comms_channel"].lower(),
        })

    base_config["skills"] = skills
    base_config["cron_jobs"] = crons
    base_config["integrations"] = [client_data["comms_channel"].lower()]
    base_config["notes"] = (
        f"Rule-based config for '{client_data['use_case']}' use case. "
        f"Skills selected based on keyword matching against goals. "
        f"Review and customize before deployment."
    )
    return base_config, False


def generate_checklist(client_data: dict) -> tuple[str, bool]:
    """
    Generate a 30-day onboarding checklist tailored to the client.
    Returns (checklist_markdown, ai_generated: bool).
    """
    if ANTHROPIC_AVAILABLE and ANTHROPIC_API_KEY:
        prompt = textwrap.dedent(f"""
            Create a detailed 30-day OpenClaw onboarding checklist for this client.
            Format as Markdown with three phases (Days 1-10, 11-20, 21-30).
            Each phase should have 5-8 specific, actionable items.
            Tailor every item to their specific use case and tech stack.

            Client:
            - Company: {client_data['company_name']}
            - Industry: {client_data['industry']}
            - Use case: {client_data['use_case']}
            - Goals: {client_data['goals']}
            - Tech stack: {client_data.get('tech_stack', 'standard')}
            - Team size: {client_data['team_size']}
            - Comms channel: {client_data['comms_channel']}

            Start each checkbox item with `- [ ]` for markdown checkbox format.
            Be specific — reference their actual use case, not generic steps.
        """)
        try:
            return _call_claude(prompt), True
        except Exception as e:
            print(f"[checklist] Claude failed: {e}. Using template.")

    # Template fallback
    checklist = textwrap.dedent(f"""
        # 30-Day OpenClaw Onboarding — {client_data['company_name']}

        ## Phase 1: Foundation (Days 1–10)

        - [ ] Complete kickoff call and confirm success metrics
        - [ ] Set up OpenClaw workspace and create `AGENTS.md` + `SOUL.md`
        - [ ] Connect {client_data['comms_channel']} integration and test message delivery
        - [ ] Deploy first agent with a simple hello-world cron trigger
        - [ ] Configure memory system — seed with 5–10 context entries for your domain
        - [ ] Define primary use case pipeline: "{client_data['use_case']}"
        - [ ] Run first end-to-end test with dummy data
        - [ ] Document your agent stack in `TOOLS.md`

        ## Phase 2: Integration (Days 11–20)

        - [ ] Connect primary data source(s) to the pipeline
        - [ ] Build and test the core automation for: "{client_data['use_case']}"
        - [ ] Add AI synthesis step (prompt engineering for your domain)
        - [ ] Set up cron schedule for recurring tasks
        - [ ] Integrate with existing tools in your stack: {client_data.get('tech_stack', 'TBD')}
        - [ ] Add error handling and template fallbacks
        - [ ] Test failure modes and verify graceful degradation
        - [ ] Peer review agent prompts with team member

        ## Phase 3: Scale & Polish (Days 21–30)

        - [ ] Stress test pipeline with realistic data volumes
        - [ ] Add monitoring cron: daily health check + alert on failure
        - [ ] Write full runbook (README + troubleshooting guide)
        - [ ] Train team on how to modify prompts and cron schedules
        - [ ] Set up staging vs. production workspace separation
        - [ ] Document all custom skills and their dependencies
        - [ ] Final review against original goals: "{client_data['goals']}"
        - [ ] Schedule 60-day check-in
    """).strip()
    return checklist, False


# ── Discord notification ──────────────────────────────────────────────────────

def send_discord_notification(client_data: dict, client_id: str, config: dict) -> bool:
    """
    Post a rich embed to a Discord webhook announcing a new client onboarding.
    Returns True on success, False if no webhook configured or request fails.
    """
    if not DISCORD_WEBHOOK:
        return False

    skills_str = ", ".join(config.get("skills", [])) or "TBD"
    cron_count = len(config.get("cron_jobs", []))

    payload = {
        "username": "Intake Bot",
        "avatar_url": "https://cdn-icons-png.flaticon.com/512/1077/1077063.png",
        "embeds": [{
            "title": f"🆕 New Client Onboarded — {client_data['company_name']}",
            "color": 0x5865F2,   # Discord blurple
            "fields": [
                {"name": "Contact",    "value": client_data["contact_name"],  "inline": True},
                {"name": "Industry",   "value": client_data["industry"],       "inline": True},
                {"name": "Team Size",  "value": client_data["team_size"],      "inline": True},
                {"name": "Use Case",   "value": client_data["use_case"],       "inline": False},
                {"name": "Goals",      "value": client_data["goals"][:200],    "inline": False},
                {"name": "Comms",      "value": client_data["comms_channel"],  "inline": True},
                {"name": "Skills Enabled", "value": skills_str,               "inline": True},
                {"name": "Cron Jobs",  "value": str(cron_count),              "inline": True},
            ],
            "footer": {"text": f"Client ID: {client_id} • {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
            "thumbnail": {"url": "https://cdn-icons-png.flaticon.com/512/6062/6062646.png"},
        }]
    }

    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        return r.status_code in (200, 204)
    except Exception as e:
        print(f"[discord] Failed to send webhook: {e}")
        return False


# ── Main onboarding orchestrator ──────────────────────────────────────────────

def run_onboarding(form_data: dict) -> dict:
    """
    Full onboarding pipeline for one client.

    Steps:
      1. Persist client to DB
      2. Generate welcome letter (AI or template)
      3. Generate agent config (AI or rule-based)
      4. Generate 30-day checklist (AI or template)
      5. Persist all docs to DB
      6. Fire Discord notification
      7. Return structured result dict

    Returns dict with: client_id, ai_used, documents, discord_sent
    """
    init_db()

    # 1. Save client record
    client_id = save_client(form_data)

    # 2–4. Generate all three documents
    welcome, ai_welcome = generate_welcome_letter(form_data)
    config,  ai_config  = generate_agent_config(form_data)
    checklist, ai_check = generate_checklist(form_data)

    # 5. Persist docs
    save_doc(client_id, "welcome_letter", welcome)
    save_doc(client_id, "agent_config",   json.dumps(config, indent=2))
    save_doc(client_id, "checklist",      checklist)

    # 6. Discord
    discord_sent = send_discord_notification(form_data, client_id, config)

    return {
        "client_id":    client_id,
        "company_name": form_data["company_name"],
        "ai_used": {
            "welcome_letter": ai_welcome,
            "agent_config":   ai_config,
            "checklist":      ai_check,
        },
        "documents": {
            "welcome_letter": welcome,
            "agent_config":   config,
            "checklist":      checklist,
        },
        "discord_sent": discord_sent,
    }
