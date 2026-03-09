"""
app.py — Intake: AI-Powered Client Onboarding Automation
Flask application serving both the intake form and the client dashboard.

Routes:
  GET  /               → intake form
  POST /onboard        → run full onboarding pipeline, return JSON
  GET  /dashboard      → all clients dashboard
  GET  /client/<id>    → single client detail view
  GET  /api/clients    → JSON list of all clients
  GET  /api/client/<id>/docs → JSON docs for a client
  POST /api/seed       → seed database with demo clients (dev convenience)
"""

import json
import os
import sys

from flask import Flask, render_template, request, jsonify, redirect, url_for

# Allow running from project root or from within the directory
sys.path.insert(0, os.path.dirname(__file__))
from onboard import (
    run_onboarding,
    get_all_clients,
    get_client,
    get_client_docs,
    init_db,
    save_client,
    save_doc,
    generate_welcome_letter,
    generate_agent_config,
    generate_checklist,
)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "intake-demo-secret")

# ── Helpers ────────────────────────────────────────────────────────────────────

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


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Intake form."""
    return render_template("index.html", page="form")


@app.route("/dashboard")
def dashboard():
    """Client dashboard — all onboarded clients."""
    clients = get_all_clients()
    return render_template("index.html", page="dashboard", clients=clients)


@app.route("/client/<client_id>")
def client_detail(client_id: str):
    """Single client detail view with all generated docs."""
    client = get_client(client_id)
    if not client:
        return "Client not found", 404
    docs = get_client_docs(client_id)
    # Parse agent config JSON for rendering
    if "agent_config" in docs:
        try:
            docs["agent_config_parsed"] = json.loads(docs["agent_config"])
        except Exception:
            docs["agent_config_parsed"] = None
    return render_template("index.html", page="detail", client=client, docs=docs)


@app.route("/onboard", methods=["POST"])
def onboard():
    """
    Main intake endpoint. Accepts JSON or form-encoded data.
    Runs the full onboarding pipeline and returns JSON result.
    """
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()

    # Minimal validation
    required = ["contact_name", "company_name", "email", "use_case",
                "industry", "team_size", "comms_channel", "goals"]
    missing = [f for f in required if not data.get(f, "").strip()]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    result = run_onboarding(data)
    return jsonify(result)


@app.route("/api/clients")
def api_clients():
    """JSON list of all clients."""
    return jsonify(get_all_clients())


@app.route("/api/client/<client_id>/docs")
def api_client_docs(client_id: str):
    """JSON documents for a specific client."""
    docs = get_client_docs(client_id)
    if not docs:
        return jsonify({"error": "No docs found"}), 404
    return jsonify(docs)


@app.route("/api/seed", methods=["POST"])
def api_seed():
    """
    Seed database with 3 demo clients for demo/testing purposes.
    Idempotent — safe to call multiple times.
    """
    init_db()
    seeded = []
    for demo in DEMO_CLIENTS:
        result = run_onboarding(demo)
        seeded.append({
            "client_id":    result["client_id"],
            "company_name": result["company_name"],
        })
    return jsonify({"seeded": seeded, "count": len(seeded)})


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 5050))
    print(f"\n🚀 Intake running on http://localhost:{port}")
    print("   Intake form:  http://localhost:{port}/")
    print("   Dashboard:    http://localhost:{port}/dashboard")
    print(f"   Seed demo data: POST http://localhost:{port}/api/seed\n")
    app.run(debug=True, host="0.0.0.0", port=port)
