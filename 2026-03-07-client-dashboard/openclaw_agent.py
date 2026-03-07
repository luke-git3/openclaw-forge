"""
openclaw_agent.py — OpenClaw Integration Layer for Iris Dashboard
=================================================================
OpenClaw Forge | Category 6: Client-Facing Dashboards

This file shows HOW an OpenClaw agent or skill connects to the Iris
dashboard. In a real deployment this logic lives inside SKILL.md
instructions; here we demonstrate the equivalent Python calls.

Two integration patterns shown:
  1. Push pattern — agent fetches portfolio data and posts a formatted
     Discord embed (the agent drives; dashboard is data source)
  2. Pull pattern — agent triggers a refresh and waits for the dashboard
     to process the new prices (dashboard drives; agent is trigger)

Run this standalone to simulate an agent interacting with a live dashboard:
  python openclaw_agent.py --ticker NVDA
  python openclaw_agent.py --report
"""

import argparse
import json
import time
from datetime import datetime

import requests

DASHBOARD_URL = "http://localhost:5007"


# ── Helpers ────────────────────────────────────────────────────────────────


def get_portfolio() -> dict:
    """Fetch portfolio snapshot from Iris API."""
    r = requests.get(f"{DASHBOARD_URL}/api/portfolio", timeout=15)
    r.raise_for_status()
    return r.json()


def trigger_refresh(ticker: str) -> None:
    """POST to the refresh endpoint — equivalent to OpenClaw tool call."""
    r = requests.post(f"{DASHBOARD_URL}/api/refresh/{ticker}", timeout=10)
    r.raise_for_status()
    print(f"[agent] Refresh triggered for {ticker}: {r.json()['message']}")


def get_feed() -> list:
    """Pull the agent activity log."""
    r = requests.get(f"{DASHBOARD_URL}/api/agent-feed", timeout=10)
    r.raise_for_status()
    return r.json()["events"]


# ── Pattern 1: Push — agent builds and posts a Discord-style report ────────


def build_discord_embed(portfolio: dict) -> dict:
    """
    Convert portfolio JSON into a Discord embed payload.

    In an OpenClaw skill this is done by the agent following
    SKILL.md instructions. Here we make the transformation explicit
    so it's easy to teach and demo.
    """
    s = portfolio["summary"]
    pnl_emoji = "📈" if s["total_pnl"] >= 0 else "📉"
    sign = "+" if s["total_pnl_pct"] >= 0 else ""
    color = 0x3FB950 if s["total_pnl"] >= 0 else 0xF85149  # green / red

    fields = []
    for h in portfolio["holdings"]:
        chg_sign = "+" if h["change_pct"] >= 0 else ""
        arrow    = "▲" if h["change_pct"] >= 0 else "▼"
        fields.append({
            "name":   f"{arrow} {h['ticker']}",
            "value":  (
                f"${h['price']:.2f} ({chg_sign}{h['change_pct']:.2f}%)\n"
                f"P&L: {'+' if h['pnl'] >= 0 else ''}"
                f"${h['pnl']:,.0f} ({'+' if h['pnl_pct'] >= 0 else ''}{h['pnl_pct']:.1f}%)"
            ),
            "inline": True,
        })

    return {
        "embeds": [{
            "title":       f"{pnl_emoji} Iris Portfolio Snapshot",
            "description": (
                f"**Total Value:** ${s['total_value']:,.0f}\n"
                f"**Unrealized P&L:** {sign}${abs(s['total_pnl']):,.0f} "
                f"({sign}{s['total_pnl_pct']:.2f}%)"
            ),
            "color":  color,
            "fields": fields,
            "footer": {"text": f"Iris Dashboard · {s['last_updated']}"},
        }]
    }


# ── Pattern 2: Pull — agent waits for dashboard, reads new state ───────────


def poll_until_refreshed(ticker: str, timeout: int = 30) -> dict:
    """
    Trigger a refresh and poll until a fresh price appears.
    In OpenClaw this would be an agent loop with sleep + tool calls.
    """
    trigger_refresh(ticker)
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = get_portfolio()
        for h in data["holdings"]:
            if h["ticker"] == ticker:
                print(f"[agent] Fresh data for {ticker}: ${h['price']:.2f} ({h['change_pct']:+.2f}%)")
                print(f"[agent] Insight: {h['insight']}")
                return h
        time.sleep(2)
    raise TimeoutError(f"Refresh for {ticker} timed out after {timeout}s")


# ── CLI ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Iris Dashboard — OpenClaw Agent Demo")
    parser.add_argument("--ticker",  help="Trigger refresh for a specific ticker, then show insight")
    parser.add_argument("--report",  action="store_true", help="Print Discord embed JSON for portfolio")
    parser.add_argument("--feed",    action="store_true", help="Print the agent activity log")
    args = parser.parse_args()

    if args.ticker:
        holding = poll_until_refreshed(args.ticker.upper())
        print(json.dumps(holding, indent=2))

    elif args.report:
        portfolio = get_portfolio()
        embed = build_discord_embed(portfolio)
        print("\n── Discord Embed Payload ────────────────────────────────")
        print(json.dumps(embed, indent=2))
        print("\n(In OpenClaw: pass this payload to the message tool with action=send)")

    elif args.feed:
        events = get_feed()
        print(f"\n── Agent Activity Log ({len(events)} events) ───────────────")
        for ev in events:
            icons = {"fetch": "📡", "ai": "🤖", "user": "👤", "system": "⚙️"}
            print(f"  {icons.get(ev['type'], 'ℹ️')}  [{ev['ts']}] {ev['event']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
