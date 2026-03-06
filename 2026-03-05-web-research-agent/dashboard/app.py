#!/usr/bin/env python3
"""
dashboard/app.py — Research Report Browser
==========================================

Flask web UI for browsing and reading research reports.
Reports are read from the ../reports/ directory.

Run:
    python dashboard/app.py
    # then open http://localhost:5001

Shows:
  - /          → Report list (sorted by date desc)
  - /report/<id> → Full report view with synthesis + sources
  - /api/reports → JSON list of all reports (for integrations)
"""

import json
import glob
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, abort

app = Flask(__name__)

# Reports directory is one level up from dashboard/
REPORTS_DIR = Path(__file__).parent.parent / "reports"


def load_reports() -> list[dict]:
    """Load all JSON reports from the reports directory, sorted newest first."""
    reports = []
    for path in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Attach file path for linking
            data["_file"] = path.stem
            reports.append(data)
        except Exception:
            pass
    return reports


def find_report(report_id: str) -> dict | None:
    """Find a specific report by its ID hash or filename stem."""
    for path in REPORTS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("id") == report_id or path.stem.endswith(report_id):
                data["_file"] = path.stem
                return data
        except Exception:
            pass
    return None


@app.route("/")
def index():
    """Report list — sorted newest first."""
    reports = load_reports()
    return render_template("index.html", reports=reports, total=len(reports))


@app.route("/report/<report_id>")
def report_detail(report_id: str):
    """Full report detail view."""
    report = find_report(report_id)
    if not report:
        abort(404)

    # Find matching markdown file for raw content
    md_content = ""
    for path in REPORTS_DIR.glob(f"*{report_id}*.md"):
        try:
            md_content = path.read_text(encoding="utf-8")
            break
        except Exception:
            pass

    return render_template("report.html", report=report, md_content=md_content)


@app.route("/api/reports")
def api_reports():
    """JSON API — list of all reports (sans full source content)."""
    reports = load_reports()
    slim = []
    for r in reports:
        slim.append({
            "id": r.get("id"),
            "topic": r.get("topic"),
            "date": r.get("meta", {}).get("date"),
            "source_count": r.get("meta", {}).get("source_count"),
            "mode": r.get("meta", {}).get("mode"),
            "executive_summary": r.get("synthesis", {}).get("executive_summary", "")[:200],
        })
    return jsonify(slim)


if __name__ == "__main__":
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Report browser running at http://localhost:5001")
    print(f"Reading reports from: {REPORTS_DIR}")
    app.run(host="0.0.0.0", port=5001, debug=False)
