"""
openclaw_agent.py — OpenClaw Integration Bridge for Intake

This file shows how the Intake onboarding pipeline maps to OpenClaw tool calls.
In a real OpenClaw deployment, an agent running in main-session receives the
intake form data (e.g., from a Discord slash command or webhook), then executes
these tool calls instead of calling Flask endpoints directly.

PURPOSE: Teaching asset — makes the invisible visible.
Each Python function here is the direct OpenClaw equivalent of the onboard.py logic.

──────────────────────────────────────────────────────────────────────────────
OPENCLAW PATTERN: Client Onboarding Automation
──────────────────────────────────────────────────────────────────────────────

Trigger:
  A new client fills out a form, sends a DM, or submits a Discord slash command.
  OpenClaw receives the message and the agent wakes up.

Pipeline (maps 1:1 to onboard.py run_onboarding()):
  1. sessions_spawn  → spin up a sub-agent with client data as context
  2. write           → persist client config to /workspace/clients/<id>/config.json
  3. sessions_spawn  → sub-agent generates welcome letter (returns text)
  4. write           → /workspace/clients/<id>/welcome_letter.md
  5. sessions_spawn  → sub-agent generates agent config (returns JSON)
  6. write           → /workspace/clients/<id>/agent_config.json
  7. sessions_spawn  → sub-agent generates 30-day checklist (returns markdown)
  8. write           → /workspace/clients/<id>/checklist.md
  9. message         → Discord embed to #new-clients channel
  10. message        → DM to client (if Telegram/Discord ID provided)
"""

import json
import os

# ── Step 1: Receive intake form data ──────────────────────────────────────────
# In OpenClaw, this arrives as the triggering message content or webhook payload.
# The main agent extracts structured fields from it.

EXAMPLE_INTAKE = {
    "contact_name": "Sarah Chen",
    "company_name": "Nexus Analytics",
    "email": "sarah@nexus.example.com",
    "use_case": "Automated daily market intelligence briefing",
    "industry": "Financial Services",
    "team_size": "11–50",
    "tech_stack": "Python, Bloomberg Terminal, Slack",
    "comms_channel": "Slack",
    "goals": "Save 2 hours per analyst per day; surface opportunities before market open",
}


# ── Step 2: Persist client record ─────────────────────────────────────────────

def openclaw_save_client(client_data: dict, client_id: str) -> str:
    """
    OpenClaw equivalent: write tool
    
    tool: write
    path: /workspace/clients/{client_id}/profile.json
    content: JSON.stringify(client_data, indent=2)
    
    Returns the absolute path written.
    """
    # Python equivalent:
    path = f"/workspace/clients/{client_id}/profile.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(client_data, f, indent=2)
    return path


# ── Step 3: Generate documents via sub-agent ──────────────────────────────────

WELCOME_LETTER_PROMPT_TEMPLATE = """
You are onboarding a new OpenClaw client. Generate a personalized welcome letter.

Client: {contact_name} at {company_name} ({industry})
Use case: {use_case}
Goals: {goals}
Comms channel: {comms_channel}

Write a warm, professional letter under 350 words. Include:
1. Warm welcome acknowledging their specific use case
2. Three-phase 30-day onboarding preview
3. Concrete next step (schedule kickoff)
"""

def openclaw_generate_welcome_letter(client_data: dict, client_id: str) -> str:
    """
    OpenClaw equivalent: sessions_spawn (subagent, mode=run)
    
    tool: sessions_spawn
    runtime: subagent
    mode: run
    task: WELCOME_LETTER_PROMPT_TEMPLATE.format(**client_data)
    
    The sub-agent returns the letter text. Main agent then writes it:
    
    tool: write
    path: /workspace/clients/{client_id}/welcome_letter.md
    content: <sub-agent output>
    
    Returns the generated letter text.
    """
    # Python simulation (calls onboard.py directly in this demo):
    from onboard import generate_welcome_letter
    letter, ai_used = generate_welcome_letter(client_data)
    
    path = f"/workspace/clients/{client_id}/welcome_letter.md"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(letter)
    
    return letter


AGENT_CONFIG_PROMPT_TEMPLATE = """
Generate an OpenClaw agent configuration JSON for this client.
Return ONLY valid JSON.

Client: {company_name} | Industry: {industry}
Use case: {use_case} | Goals: {goals}
Tech stack: {tech_stack} | Channel: {comms_channel}

Available skills: web-search, summarize, github, discord, telegram, finsnap, qmd

JSON structure:
{{
  "agent": {{"name": "...", "model": "...", "channel": "...", "memory_enabled": true}},
  "skills": [...],
  "cron_jobs": [{{"schedule": "...", "task": "...", "output_channel": "..."}}],
  "integrations": [...],
  "notes": "..."
}}
"""

def openclaw_generate_config(client_data: dict, client_id: str) -> dict:
    """
    OpenClaw equivalent: sessions_spawn → write
    
    Same pattern as welcome letter — spawn sub-agent with config prompt,
    write the returned JSON to /workspace/clients/{client_id}/agent_config.json.
    
    In production, also write openclaw.json and AGENTS.md to a new
    workspace directory for this client's dedicated agent instance.
    """
    from onboard import generate_agent_config
    config, ai_used = generate_agent_config(client_data)
    
    path = f"/workspace/clients/{client_id}/agent_config.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
    
    return config


# ── Step 4: Send Discord notification ─────────────────────────────────────────

def openclaw_notify_discord(client_data: dict, client_id: str, config: dict) -> str:
    """
    OpenClaw equivalent: message tool
    
    tool: message
    action: send
    channel: discord
    target: channel:<channel_id>   # e.g. #new-clients
    message: |
      🆕 **New Client Onboarded — {company_name}**
      **Contact:** {contact_name} | **Industry:** {industry}
      **Use Case:** {use_case}
      **Skills Enabled:** {skills}
      **Cron Jobs:** {cron_count}
    
    Note: In OpenClaw, this is ONE tool call. No webhook URL needed —
    the agent uses the configured Discord channel directly.
    This is the key advantage of native OpenClaw over raw webhook calls.
    """
    skills = ", ".join(config.get("skills", []))
    cron_count = len(config.get("cron_jobs", []))
    
    message = (
        f"🆕 **New Client Onboarded — {client_data['company_name']}**\n"
        f"**Contact:** {client_data['contact_name']} | **Industry:** {client_data['industry']}\n"
        f"**Use Case:** {client_data['use_case']}\n"
        f"**Skills Enabled:** {skills}\n"
        f"**Cron Jobs:** {cron_count}\n"
        f"Client ID: `{client_id}`"
    )
    
    # In real OpenClaw:
    # message(action="send", channel="discord", target="channel:1477502144612667544", message=message)
    
    print(f"[openclaw_notify_discord] Would send:\n{message}")
    return message


# ── Step 5: Send DM to new client (if Telegram ID provided) ───────────────────

def openclaw_welcome_dm(client_data: dict, welcome_text: str, telegram_id: str = None) -> None:
    """
    OpenClaw equivalent: message tool (Telegram DM)
    
    tool: message
    action: send
    channel: telegram
    target: user:{telegram_id}
    message: welcome_text
    
    This is the "closes the loop" step — the client gets their welcome letter
    directly in their preferred channel moments after submitting the form.
    No email system needed. This is native OpenClaw.
    """
    if not telegram_id:
        print("[openclaw_welcome_dm] No Telegram ID — skipping DM")
        return
    
    # In real OpenClaw:
    # message(action="send", channel="telegram", target=f"user:{telegram_id}", message=welcome_text)
    print(f"[openclaw_welcome_dm] Would DM {telegram_id}: {welcome_text[:80]}…")


# ── Full pipeline demo ─────────────────────────────────────────────────────────

def run_openclaw_onboarding_demo(client_data: dict = None) -> None:
    """
    Demonstrates the full OpenClaw onboarding pipeline.
    Run this file directly to see the pipeline execute end-to-end.
    """
    import hashlib
    if client_data is None:
        client_data = EXAMPLE_INTAKE
    
    client_id = hashlib.sha1(client_data["email"].lower().encode()).hexdigest()[:8]
    print(f"\n{'='*60}")
    print(f"INTAKE — OpenClaw Onboarding Pipeline")
    print(f"Client: {client_data['company_name']} | ID: {client_id}")
    print(f"{'='*60}\n")
    
    print("Step 1/4 — Saving client profile…")
    profile_path = openclaw_save_client(client_data, client_id)
    print(f"  ✓ Written: {profile_path}\n")
    
    print("Step 2/4 — Generating welcome letter…")
    letter = openclaw_generate_welcome_letter(client_data, client_id)
    print(f"  ✓ {len(letter)} chars generated\n")
    
    print("Step 3/4 — Generating agent config…")
    config = openclaw_generate_config(client_data, client_id)
    skills = config.get("skills", [])
    crons = config.get("cron_jobs", [])
    print(f"  ✓ {len(skills)} skills, {len(crons)} cron jobs configured\n")
    
    print("Step 4/4 — Sending notifications…")
    openclaw_notify_discord(client_data, client_id, config)
    print()
    
    print(f"{'='*60}")
    print(f"Pipeline complete. Files in /workspace/clients/{client_id}/")
    print(f"  - profile.json")
    print(f"  - welcome_letter.md")
    print(f"  - agent_config.json")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    run_openclaw_onboarding_demo()
