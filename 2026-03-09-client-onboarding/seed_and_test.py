"""
seed_and_test.py — Standalone test/seed script for Intake

Run this without starting the Flask server to verify the core pipeline works.
Useful for CI or quick smoke tests.

Usage:
    python seed_and_test.py
    python seed_and_test.py --openclaw  # also run the openclaw_agent.py demo
"""

import json
import sys
import os

# Make sure onboard.py is importable
sys.path.insert(0, os.path.dirname(__file__))

from onboard import run_onboarding, get_all_clients, init_db

DEMO_CLIENTS = [
    {
        "contact_name":  "Sarah Chen",
        "company_name":  "Nexus Analytics",
        "email":         "sarah@nexus-analytics.example.com",
        "use_case":      "Automated daily market intelligence briefing for investment team",
        "industry":      "Financial Services",
        "team_size":     "11–50",
        "tech_stack":    "Python, Bloomberg Terminal, Slack",
        "comms_channel": "Slack",
        "goals":         "Save 2 hours per analyst per day; surface opportunities before market open",
    },
    {
        "contact_name":  "Marcus Webb",
        "company_name":  "DevHive",
        "email":         "marcus@devhive.example.com",
        "use_case":      "GitHub PR triage and engineering team daily digest",
        "industry":      "Software / SaaS",
        "team_size":     "1–10",
        "tech_stack":    "GitHub, Linear, Discord",
        "comms_channel": "Discord",
        "goals":         "Reduce time-in-review cycle; surface stale PRs automatically",
    },
    {
        "contact_name":  "Priya Ramos",
        "company_name":  "HealthBridge",
        "email":         "priya@healthbridge.example.com",
        "use_case":      "Patient onboarding automation and appointment reminder pipeline",
        "industry":      "Healthcare",
        "team_size":     "51–200",
        "tech_stack":    "Salesforce, Twilio, Email",
        "comms_channel": "Telegram",
        "goals":         "Cut no-show rate by 30%; automate intake paperwork reminders",
    },
]


def run_tests():
    print("\n" + "="*60)
    print("INTAKE — Pipeline Test")
    print("="*60 + "\n")
    
    init_db()
    
    for i, client in enumerate(DEMO_CLIENTS, 1):
        print(f"[{i}/{len(DEMO_CLIENTS)}] Onboarding: {client['company_name']}…")
        result = run_onboarding(client)
        
        ai = result["ai_used"]
        docs = result["documents"]
        
        print(f"  Client ID: {result['client_id']}")
        print(f"  Welcome letter: {'AI ✨' if ai['welcome_letter'] else 'Template 📄'} ({len(docs['welcome_letter'])} chars)")
        print(f"  Agent config:   {'AI ✨' if ai['agent_config'] else 'Rule-based 🔧'} ({len(docs['agent_config']['skills'])} skills, {len(docs['agent_config']['cron_jobs'])} crons)")
        print(f"  30-day checklist: {'AI ✨' if ai['checklist'] else 'Template 📄'} ({len(docs['checklist'])} chars)")
        print(f"  Discord notify: {'✅ Sent' if result['discord_sent'] else '⚠️  Skipped (no webhook)'}")
        print()
    
    all_clients = get_all_clients()
    print(f"✅ {len(all_clients)} total clients in registry")
    
    # Print one sample welcome letter
    sample = run_onboarding(DEMO_CLIENTS[0])
    print("\n" + "─"*60)
    print("SAMPLE WELCOME LETTER (Nexus Analytics):")
    print("─"*60)
    print(sample["documents"]["welcome_letter"][:600] + "…")
    
    print("\n" + "─"*60)
    print("SAMPLE AGENT CONFIG:")
    print("─"*60)
    cfg = sample["documents"]["agent_config"]
    print(json.dumps({
        "agent_name": cfg["agent"]["name"],
        "skills": cfg["skills"],
        "cron_jobs": [j["schedule"] + " — " + j["task"][:60] for j in cfg["cron_jobs"]],
        "notes": cfg["notes"][:100] + "…",
    }, indent=2))
    
    print("\n✅ All tests passed.\n")


if __name__ == "__main__":
    run_tests()
    
    if "--openclaw" in sys.argv:
        print("\n" + "="*60)
        print("OpenClaw Agent Bridge Demo")
        print("="*60)
        from openclaw_agent import run_openclaw_onboarding_demo
        run_openclaw_onboarding_demo()
