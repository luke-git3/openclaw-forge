"""
demo/fire_alerts.py — Fire 8 realistic test alerts at the dispatcher

Run from the project root WHILE the server is running:
    python demo/fire_alerts.py

Adjust BASE_URL if running on a non-default port.
"""
import json
import sys
import time
import requests

BASE_URL = "http://localhost:8765"

# ── Sample alert payloads (realistic, varied) ─────────────────────────────────

ALERTS = [
    {
        "label": "Database failover",
        "payload": {
            "event":        "database.failover",
            "service":      "postgres-primary",
            "env":          "production",
            "region":       "us-east-1",
            "error":        "Primary node unreachable after 3 consecutive health checks",
            "action":       "Failover to replica initiated automatically",
            "connections":  847,
        }
    },
    {
        "label": "Successful deployment",
        "payload": {
            "event":      "deployment.success",
            "service":    "api-gateway",
            "version":    "v2.14.3",
            "env":        "production",
            "deployed_by": "github-actions",
            "duration_s": 142,
            "message":    "Deployment complete. All health checks passed.",
        }
    },
    {
        "label": "Payment processing error",
        "payload": {
            "event":        "payment.failed",
            "service":      "payments",
            "error":        "Stripe webhook timeout after 30s. 14 transactions in flight.",
            "amount_at_risk_usd": 8420,
            "env":          "production",
            "retry_count":  3,
        }
    },
    {
        "label": "High memory usage",
        "payload": {
            "event":       "infra.alert",
            "host":        "worker-07.us-east-1",
            "metric":      "memory_used_pct",
            "value":       91.4,
            "threshold":   85,
            "env":         "production",
            "message":     "Memory usage has exceeded warning threshold. OOM risk elevated.",
        }
    },
    {
        "label": "New user signup spike",
        "payload": {
            "event":        "product.signup_spike",
            "service":      "auth",
            "env":          "production",
            "signups_1h":   1842,
            "baseline_1h":  320,
            "message":      "Signup rate 5.7x above baseline — possible viral moment or bot activity.",
        }
    },
    {
        "label": "SSL cert expiry warning",
        "payload": {
            "event":       "security.cert_expiry",
            "domain":      "api.acme.io",
            "expires_in":  "7 days",
            "env":         "production",
            "message":     "TLS certificate for api.acme.io expires in 7 days. Renewal required.",
        }
    },
    {
        "label": "Scheduled job completed",
        "payload": {
            "event":       "cron.complete",
            "job":         "weekly-invoice-generation",
            "service":     "billing",
            "env":         "production",
            "records":     4821,
            "duration_s":  38,
            "message":     "Weekly invoices generated and emailed successfully.",
        }
    },
    {
        "label": "Auth service 500 surge",
        "payload": {
            "event":        "auth.error_spike",
            "service":      "auth-service",
            "env":          "production",
            "error_rate":   "23%",
            "baseline":     "0.4%",
            "error":        "500 Internal Server Error",
            "message":      "Auth service error rate surged to 23%. Users unable to log in.",
            "host":         "auth-01.us-east-1",
        }
    },
]


def fire(alert: dict) -> dict:
    label   = alert["label"]
    payload = alert["payload"]
    try:
        resp = requests.post(f"{BASE_URL}/webhook", json=payload, timeout=15)
        result = resp.json()
        print(f"  ✓ {label:35s} → [{result.get('severity','?'):8s}] #{result.get('id','?')}  "
              f"({result.get('enrichment_ms','?')}ms, {result.get('enrichment_mode','?')})")
        return result
    except requests.ConnectionError:
        print(f"  ✗ {label} — could not connect to {BASE_URL}. Is the server running?")
        sys.exit(1)
    except Exception as exc:
        print(f"  ✗ {label} — {exc}")
        return {}


def main():
    print(f"\n🔔 Alert Dispatcher demo — firing {len(ALERTS)} test alerts at {BASE_URL}\n")

    results = []
    for alert in ALERTS:
        r = fire(alert)
        results.append(r)
        time.sleep(0.4)  # slight delay so timestamps differ visibly in dashboard

    severities = [r.get("severity", "?") for r in results if r]
    print(f"\n─────────────────────────────────────────")
    print(f"Fired {len(ALERTS)} alerts. Severities: {', '.join(severities)}")
    print(f"Dashboard: {BASE_URL}/\n")


if __name__ == "__main__":
    main()
