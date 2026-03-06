"""
server.py — Alert Dispatcher webhook server + API

Runs a Flask server that:
  POST /webhook  → receive raw event, enrich via AI, store, notify Discord
  GET  /alerts   → list recent alerts (JSON API for dashboard)
  GET  /stats    → severity counts + uptime
  GET  /health   → liveness probe
  GET  /         → serve the live dashboard

Usage:
    python server.py

Environment variables (all optional):
    PORT                    — listen port (default: 8765)
    ANTHROPIC_API_KEY       — enables AI enrichment
    DISCORD_WEBHOOK_URL     — enables real Discord notifications
    ALERT_DB_PATH           — path to JSON store (default: alerts.json)
"""
import logging
import os
import time
from flask import Flask, request, jsonify, send_from_directory

from config import Config
from alert_brain import AlertBrain
from alert_store import AlertStore
from discord_notifier import DiscordNotifier

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)
config    = Config()
brain     = AlertBrain(config)
store     = AlertStore(config.ALERT_DB_PATH)
notifier  = DiscordNotifier(config)
START_TIME = time.time()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def receive_alert():
    """
    Main ingestion endpoint.

    Accepts any JSON body — no fixed schema required. The AlertBrain
    figures out what it is and classifies it accordingly.

    Returns:
        {
          "status": "ok",
          "id": "a1b2c3d4",
          "severity": "high",
          "channel": "alerts",
          "enrichment_mode": "ai|rule-based",
          "discord_sent": true
        }
    """
    raw = request.get_json(force=True, silent=True)
    if not raw:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    # Enrich → persist → notify (the core pipeline, 3 lines)
    enriched    = brain.enrich(raw)
    record      = store.save(enriched)
    discord_ok  = notifier.send(enriched)

    return jsonify({
        "status":           "ok",
        "id":               record["id"],
        "severity":         enriched["severity"],
        "channel":          enriched["channel"],
        "enrichment_mode":  enriched["enrichment_mode"],
        "enrichment_ms":    enriched["enrichment_ms"],
        "discord_sent":     discord_ok,
    }), 201


@app.route("/alerts", methods=["GET"])
def list_alerts():
    """Return recent alerts for the dashboard. Supports ?limit=N (max 100)."""
    limit = min(int(request.args.get("limit", 50)), 100)
    return jsonify(store.recent(limit=limit))


@app.route("/stats", methods=["GET"])
def stats():
    """Severity breakdown + uptime — useful for dashboards and healthchecks."""
    counts  = store.severity_counts()
    uptime  = round(time.time() - START_TIME)
    ai_mode = bool(config.ANTHROPIC_API_KEY)
    discord = bool(config.DISCORD_WEBHOOK_URL)
    return jsonify({
        "total_alerts":     store.count(),
        "severity_counts":  counts,
        "uptime_seconds":   uptime,
        "ai_mode":          ai_mode,
        "discord_live":     discord,
    })


@app.route("/health", methods=["GET"])
def health():
    """Kubernetes/load-balancer liveness probe."""
    return jsonify({"status": "ok", "alerts": store.count()}), 200


@app.route("/", methods=["GET"])
def dashboard():
    """Serve the live alert dashboard."""
    dashboard_dir = os.path.join(os.path.dirname(__file__), "dashboard")
    return send_from_directory(dashboard_dir, "index.html")


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ai_tag      = "🧠 AI" if config.ANTHROPIC_API_KEY else "📐 Rules"
    discord_tag = "📣 Discord live" if config.DISCORD_WEBHOOK_URL else "🖨️  Discord mock"
    print(f"\n🔔 Alert Dispatcher starting on http://{config.HOST}:{config.PORT}")
    print(f"   Enrichment : {ai_tag}")
    print(f"   Notify     : {discord_tag}")
    print(f"   DB         : {config.ALERT_DB_PATH}")
    print(f"   Dashboard  : http://localhost:{config.PORT}/")
    print(f"   Webhook    : POST http://localhost:{config.PORT}/webhook\n")
    app.run(host=config.HOST, port=config.PORT, debug=False)
