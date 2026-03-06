"""
Pulse — AI Daily Market Briefing Pipeline
==========================================
Demonstrates the OpenClaw cron automation pattern:
  1. Scheduled data ingestion (market prices + news RSS)
  2. AI synthesis layer (Claude if API key present, template fallback otherwise)
  3. Structured report generation (timestamped markdown)
  4. Discord webhook delivery
  5. Persistent run log for dashboard history

Usage:
  python3 pipeline.py              # live run
  python3 pipeline.py --demo       # demo run with synthetic data (no network)
  python3 pipeline.py --dry-run    # fetch real data, skip Discord + file write
"""

import json
import os
import sys
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).parent
CONFIG_FILE  = PROJECT_DIR / "config.json"
REPORTS_DIR  = PROJECT_DIR / "reports"
RUN_LOG      = PROJECT_DIR / "run_log.json"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------
def fetch_market_data(tickers: list[str]) -> dict:
    """
    Fetch latest price data from Yahoo Finance v8 API.
    Returns dict keyed by ticker symbol.
    No API key required.
    """
    results = {}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PulsePipeline/1.0)"}

    for ticker in tickers:
        try:
            url = (
                f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                f"?interval=1d&range=5d"
            )
            resp = requests.get(url, headers=headers, timeout=12)
            resp.raise_for_status()
            data = resp.json()

            result = data["chart"]["result"][0]
            meta   = result["meta"]
            closes = result["indicators"]["quote"][0]["close"]

            # Filter out None values Yahoo sometimes returns for partial trading days
            closes = [c for c in closes if c is not None]

            if len(closes) >= 2:
                current    = closes[-1]
                prev       = closes[-2]
                change_pct = ((current - prev) / prev) * 100
            elif closes:
                current    = closes[-1]
                change_pct = 0.0
            else:
                raise ValueError("No close data returned")

            results[ticker] = {
                "price":      round(current, 2),
                "change_pct": round(change_pct, 2),
                "currency":   meta.get("currency", "USD"),
                "name":       meta.get("longName", ticker),
            }

        except Exception as exc:
            results[ticker] = {"error": str(exc)}

    return results


def fetch_news_headlines(feed_urls: list[str], limit: int = 6) -> list[dict]:
    """
    Parse RSS feeds and return top headlines.
    Aggregates across multiple feeds, deduplicates by title.
    """
    headlines = []
    seen_titles: set[str] = set()
    headers = {"User-Agent": "Mozilla/5.0 (compatible; PulsePipeline/1.0)"}

    for url in feed_urls:
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            resp.raise_for_status()
            root  = ET.fromstring(resp.content)
            items = root.findall(".//item")

            for item in items:
                title = (item.findtext("title") or "").strip()
                link  = (item.findtext("link") or "").strip()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    headlines.append({"title": title, "link": link})
                if len(headlines) >= limit:
                    break

        except Exception as exc:
            # Non-fatal — just note it and continue
            print(f"  [warn] RSS fetch failed for {url}: {exc}")

    return headlines[:limit]


def fetch_demo_data() -> tuple[dict, list[dict]]:
    """Return realistic synthetic data for demo/test runs."""
    market_data = {
        "SPY":     {"price": 521.34, "change_pct":  0.82, "currency": "USD", "name": "SPDR S&P 500 ETF"},
        "QQQ":     {"price": 445.12, "change_pct":  1.14, "currency": "USD", "name": "Invesco QQQ Trust"},
        "IWM":     {"price": 207.88, "change_pct": -0.43, "currency": "USD", "name": "iShares Russell 2000 ETF"},
        "BTC-USD": {"price": 94200.0,"change_pct":  2.31, "currency": "USD", "name": "Bitcoin"},
        "GLD":     {"price": 193.55, "change_pct":  0.17, "currency": "USD", "name": "SPDR Gold Shares"},
        "TLT":     {"price": 91.20,  "change_pct": -0.61, "currency": "USD", "name": "iShares 20+ Year Treasury Bond ETF"},
    }
    headlines = [
        {"title": "Fed signals patience on rate cuts amid sticky services inflation", "link": "https://finance.yahoo.com"},
        {"title": "Tech stocks lead broad market rally as AI spending outlook brightens", "link": "https://finance.yahoo.com"},
        {"title": "Bitcoin surges past $94k as institutional buying accelerates", "link": "https://finance.yahoo.com"},
        {"title": "Small-caps lag as regional bank concerns resurface", "link": "https://finance.yahoo.com"},
        {"title": "Gold steady despite dollar strength; geopolitical risk priced in", "link": "https://finance.yahoo.com"},
    ]
    return market_data, headlines


# ---------------------------------------------------------------------------
# AI synthesis
# ---------------------------------------------------------------------------
def synthesize_briefing(market_data: dict, headlines: list[dict], config: dict) -> str:
    """
    Route to Claude (Anthropic API) if key is available, else template fallback.
    This is the core pattern: AI-as-synthesizer sitting between data ingestion
    and report generation.
    """
    api_key = (
        os.environ.get("ANTHROPIC_API_KEY")
        or config.get("anthropic_api_key", "")
    )

    if api_key:
        result = _synthesize_with_claude(market_data, headlines, api_key)
        if result:
            return result

    return _synthesize_template(market_data, headlines)


def _synthesize_with_claude(market_data: dict, headlines: list[dict], api_key: str) -> str | None:
    """Real AI synthesis via Anthropic API (claude-3-5-haiku for cost efficiency)."""
    try:
        import anthropic  # optional dependency — graceful fallback if absent

        market_lines = "\n".join(
            f"  {ticker}: ${d['price']:,.2f} ({d['change_pct']:+.2f}%)"
            for ticker, d in market_data.items()
            if "error" not in d
        )
        news_lines = "\n".join(
            f"  - {h['title']}"
            for h in headlines
            if "error" not in h
        )

        prompt = f"""You are a financial analyst writing a concise daily market briefing for an institutional audience.

Market data (today's close):
{market_lines}

Top headlines:
{news_lines}

Write a 3–5 sentence executive briefing that:
1. Summarizes the key directional moves across asset classes
2. Weaves in relevant headline context (don't just repeat headlines verbatim)
3. Closes with a one-sentence sentiment read (bullish / bearish / mixed / risk-off / risk-on)

Be direct and specific. No filler phrases. No disclaimers. No bullet points — flowing prose only."""

        client  = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    except ImportError:
        print("  [info] anthropic package not installed; using template synthesis")
        return None
    except Exception as exc:
        print(f"  [warn] Claude synthesis failed ({exc}); falling back to template")
        return None


def _synthesize_template(market_data: dict, headlines: list[dict]) -> str:
    """
    Deterministic template synthesis — no API key required.
    Demonstrates the pattern without AI dependency for demos/tests.
    """
    gainers, losers, flat = [], [], []

    for ticker, data in market_data.items():
        if "error" in data:
            continue
        change = data["change_pct"]
        label  = f"{ticker} ({change:+.1f}%)"
        if change > 0.1:
            gainers.append(label)
        elif change < -0.1:
            losers.append(label)
        else:
            flat.append(label)

    parts = []

    if gainers and losers:
        parts.append(
            f"Markets closed mixed: {', '.join(gainers)} led gains "
            f"while {', '.join(losers)} declined."
        )
    elif gainers:
        parts.append(f"Broad-based gains today: {', '.join(gainers)} all finished higher.")
    elif losers:
        parts.append(f"Risk-off session: {', '.join(losers)} weighed on markets.")
    else:
        parts.append("Markets closed largely flat with no clear directional bias.")

    if headlines:
        top = headlines[0]["title"]
        parts.append(f"Top story: \"{top}\"")
        if len(headlines) > 1:
            parts.append(f"Also notable: \"{headlines[1]['title']}\"")

    # Sentiment heuristic
    if len(gainers) >= len(losers) * 2:
        sentiment = "risk-on"
    elif len(losers) >= len(gainers) * 2:
        sentiment = "risk-off"
    else:
        sentiment = "mixed"
    parts.append(f"Overall market sentiment: {sentiment}.")

    return " ".join(parts)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def save_report(
    date_str: str,
    market_data: dict,
    headlines: list[dict],
    briefing: str,
    is_demo: bool = False,
) -> Path:
    """Write a timestamped markdown report to the reports/ directory."""
    REPORTS_DIR.mkdir(exist_ok=True)
    suffix     = "-demo" if is_demo else ""
    report_path = REPORTS_DIR / f"{date_str}{suffix}.md"

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# 📊 Market Briefing — {date_str}{'  *(demo)*' if is_demo else ''}",
        "",
        "## AI Synthesis",
        "",
        briefing,
        "",
        "## Market Snapshot",
        "",
        "| Ticker | Name | Price | Change |",
        "|--------|------|-------|--------|",
    ]

    for ticker, data in market_data.items():
        if "error" in data:
            lines.append(f"| {ticker} | — | Error | — |")
        else:
            arrow = "📈" if data["change_pct"] > 0 else "📉" if data["change_pct"] < 0 else "➡️"
            lines.append(
                f"| {ticker} | {data.get('name', ticker)} "
                f"| ${data['price']:,.2f} "
                f"| {arrow} {data['change_pct']:+.2f}% |"
            )

    lines += ["", "## Top Headlines", ""]
    for h in headlines:
        if "error" not in h:
            link = h.get("link", "#")
            lines.append(f"- [{h['title']}]({link})")

    lines += [
        "",
        "---",
        f"*Generated by **Pulse Pipeline** (OpenClaw cron demo) at {now_utc}*",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def update_run_log(date_str: str, status: str, report_path: Path, briefing: str, is_demo: bool) -> None:
    """Append this run to run_log.json (capped at last 60 runs for dashboard)."""
    log: list[dict] = []
    if RUN_LOG.exists():
        try:
            log = json.loads(RUN_LOG.read_text())
        except json.JSONDecodeError:
            log = []

    log.append({
        "date":             date_str,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "status":           status,
        "demo":             is_demo,
        "report":           report_path.name,
        "briefing_preview": (briefing[:250] + "…") if len(briefing) > 250 else briefing,
    })

    # Keep rolling window of 60 runs
    log = log[-60:]
    RUN_LOG.write_text(json.dumps(log, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Discord delivery
# ---------------------------------------------------------------------------
def send_discord_notification(
    market_data: dict,
    briefing: str,
    date_str: str,
    config: dict,
) -> bool:
    """
    Post a rich embed to a Discord webhook.
    Webhook URL must be set in config.json or DISCORD_WEBHOOK env var.
    """
    webhook_url = os.environ.get("DISCORD_WEBHOOK") or config.get("discord_webhook", "")
    if not webhook_url:
        print("  [info] No Discord webhook configured — skipping notification")
        return False

    # Build the market snapshot field value
    ticker_lines = []
    for ticker, data in market_data.items():
        if "error" not in data:
            arrow = "📈" if data["change_pct"] > 0 else "📉" if data["change_pct"] < 0 else "➡️"
            ticker_lines.append(
                f"{arrow} **{ticker}** `${data['price']:,.2f}` ({data['change_pct']:+.2f}%)"
            )

    # Embed color: green if majority gainers, red if majority losers, blue otherwise
    gainers = sum(1 for d in market_data.values() if "error" not in d and d["change_pct"] > 0)
    losers  = sum(1 for d in market_data.values() if "error" not in d and d["change_pct"] < 0)
    color   = 0x2ecc71 if gainers > losers else 0xe74c3c if losers > gainers else 0x3498db

    payload = {
        "embeds": [{
            "title":       f"📊 Daily Market Briefing — {date_str}",
            "description": briefing,
            "color":       color,
            "fields": [
                {
                    "name":   "Market Snapshot",
                    "value":  "\n".join(ticker_lines) or "No data available",
                    "inline": False,
                }
            ],
            "footer": {"text": "Pulse Pipeline · Powered by OpenClaw"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        success = resp.status_code in (200, 204)
        if not success:
            print(f"  [warn] Discord returned {resp.status_code}: {resp.text[:200]}")
        return success
    except Exception as exc:
        print(f"  [warn] Discord notification failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run(demo: bool = False, dry_run: bool = False) -> dict:
    """
    Full pipeline execution.

    Args:
        demo:    Use synthetic data instead of live API calls.
        dry_run: Fetch real data but skip file writes and Discord.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    ts       = datetime.now().strftime("%H:%M:%S")
    mode     = "DEMO" if demo else "DRY-RUN" if dry_run else "LIVE"
    print(f"[{ts}] Pulse pipeline starting — {date_str} [{mode}]")

    config = load_config()

    # --- Step 1: Ingest ---
    if demo:
        print("  Using synthetic demo data...")
        market_data, headlines = fetch_demo_data()
    else:
        print("  Fetching market data from Yahoo Finance...")
        market_data = fetch_market_data(config.get("tickers", ["SPY", "QQQ", "BTC-USD"]))
        ok_count    = sum(1 for d in market_data.values() if "error" not in d)
        print(f"  → {ok_count}/{len(market_data)} tickers fetched successfully")

        print("  Fetching news headlines from RSS...")
        headlines = fetch_news_headlines(
            config.get("news_feeds", []),
            limit=config.get("headline_limit", 6),
        )
        print(f"  → {len(headlines)} headlines fetched")

    # --- Step 2: Synthesize ---
    print("  Synthesizing briefing...")
    briefing = synthesize_briefing(market_data, headlines, config)
    print(f"  → {briefing[:80]}…")

    if dry_run:
        print("\n[DRY-RUN] Skipping file write and Discord — here's the full briefing:\n")
        print(briefing)
        print()
        return {"mode": "dry-run", "briefing": briefing, "market_data": market_data}

    # --- Step 3: Save report ---
    print("  Writing report...")
    report_path = save_report(date_str, market_data, headlines, briefing, is_demo=demo)
    print(f"  → {report_path}")

    # --- Step 4: Notify ---
    print("  Sending Discord notification...")
    notified = send_discord_notification(market_data, briefing, date_str, config)
    print(f"  → {'sent ✓' if notified else 'skipped (no webhook)'}")

    # --- Step 5: Log ---
    status = "demo" if demo else "success"
    update_run_log(date_str, status, report_path, briefing, is_demo=demo)
    print("  Run log updated.")

    result = {
        "date":      date_str,
        "mode":      mode.lower(),
        "tickers":   len(market_data),
        "headlines": len(headlines),
        "report":    str(report_path),
        "discord":   notified,
    }

    print(f"\n✅ Pipeline complete: {json.dumps(result, indent=2)}")
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pulse — AI Daily Market Briefing Pipeline")
    parser.add_argument("--demo",    action="store_true", help="Use synthetic data (no network calls)")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="Fetch real data but skip writes and Discord")
    args = parser.parse_args()

    run(demo=args.demo, dry_run=args.dry_run)
