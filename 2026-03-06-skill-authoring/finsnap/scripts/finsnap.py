#!/usr/bin/env python3
"""
finsnap/scripts/finsnap.py
──────────────────────────
OpenClaw finsnap skill — orchestration entry point.

Fetches quote + news for one or more tickers, generates an AI-synthesized
analysis, and delivers a formatted snapshot to Discord (webhook) or stdout.

Usage:
    python3 finsnap.py AAPL
    python3 finsnap.py NVDA MSFT AAPL
    python3 finsnap.py --text TSLA          # plain text output (no Discord)
    python3 finsnap.py --webhook AAPL       # force Discord webhook delivery
    python3 finsnap.py --no-ai AAPL         # skip AI synthesis (data only)

Environment variables:
    ANTHROPIC_API_KEY        Claude API key (for AI synthesis)
    OPENAI_API_KEY           OpenAI fallback (if Anthropic unavailable)
    DISCORD_WEBHOOK_URL      Discord webhook for push delivery
    FINSNAP_NEWS_COUNT       Headlines to include (default: 3)
    FINSNAP_NO_AI            Set to "1" to disable AI synthesis
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional

# ── Optional imports — graceful degradation ────────────────────────────────────
try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False
    # Fallback: use urllib
    import urllib.request
    import urllib.error


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEWS_COUNT = int(os.getenv("FINSNAP_NEWS_COUNT", "3"))
NO_AI = os.getenv("FINSNAP_NO_AI", "0") == "1"
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")

# Colour coding for Discord embeds
SENTIMENT_COLORS = {
    "BULLISH": 0x2ECC71,   # green
    "NEUTRAL": 0x95A5A6,   # grey
    "BEARISH": 0xE74C3C,   # red
    "UNKNOWN": 0x3498DB,   # blue fallback
}

CHANGE_EMOJI = {True: "📈", False: "📉"}


# ── Data fetching ──────────────────────────────────────────────────────────────

def _run_bash(script: str, *args: str) -> dict | list:
    """Run a finsnap bash script and return parsed JSON output."""
    script_path = os.path.join(SCRIPT_DIR, script)
    result = subprocess.run(
        ["bash", script_path, *args],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"{script} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def fetch_quote(ticker: str) -> dict:
    """Return structured quote data for ticker."""
    return _run_bash("fetch_quote.sh", ticker)


def fetch_news(ticker: str, n: int = NEWS_COUNT) -> list:
    """Return list of recent news items for ticker."""
    return _run_bash("fetch_news.sh", ticker, str(n))


# ── AI synthesis ───────────────────────────────────────────────────────────────

def build_synthesis_prompt(ticker: str, quote: dict, news: list) -> str:
    headlines_text = "\n".join(
        f"  - {a['title']} ({a['publisher']}, {a['published_at']})"
        for a in news[:NEWS_COUNT]
    ) or "  No recent headlines found."

    wk52_pos = quote.get("wk52_position_pct")
    wk52_desc = f"{wk52_pos:.0f}% of its 52-week range" if wk52_pos is not None else "unknown position in 52-week range"

    return f"""You are a financial analyst delivering a 60-second briefing. Be direct; finance professional audience.

Ticker: {ticker}
Company: {quote.get('short_name', ticker)}
Current price: ${quote.get('price', 'N/A')} ({quote.get('change_str', 'N/A')} today)
52-week range: ${quote.get('wk52_low', 'N/A')} – ${quote.get('wk52_high', 'N/A')} (currently at {wk52_desc})
Trailing P/E: {quote.get('trailing_pe') or 'N/A'}x | Forward P/E: {quote.get('forward_pe') or 'N/A'}x
Market cap: {quote.get('market_cap_str', 'N/A')}
Beta: {quote.get('beta') or 'N/A'}
Market state: {quote.get('market_state', 'UNKNOWN')}

Recent headlines:
{headlines_text}

Write exactly this structure (no extra text before or after):
CONTEXT: [One sentence on where the stock sits vs its 52-week range and broader trend]
BULL: [One sentence — strongest bull case grounded in available data/headlines]
BEAR: [One sentence — biggest risk or bear case grounded in available data/headlines]
SENTIMENT: [exactly one word: BULLISH, NEUTRAL, or BEARISH]"""


def synthesize_ai(prompt: str) -> Optional[dict]:
    """
    Call AI for synthesis. Tries Anthropic first, then OpenAI.
    Returns dict: {context, bull, bear, sentiment} or None on failure.
    """
    raw_text = None

    # ── Anthropic ──────────────────────────────────────────────────────────────
    if ANTHROPIC_KEY and _ANTHROPIC_AVAILABLE:
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
            msg = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )
            raw_text = msg.content[0].text
        except Exception as e:
            print(f"[finsnap] Anthropic error: {e}", file=sys.stderr)

    # ── OpenAI fallback ────────────────────────────────────────────────────────
    if not raw_text and OPENAI_KEY:
        try:
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.3
            }
            if _REQUESTS_AVAILABLE:
                import requests as req
                r = req.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                    json=payload, timeout=15
                )
                r.raise_for_status()
                raw_text = r.json()["choices"][0]["message"]["content"]
            else:
                import urllib.request, json as _json
                data = _json.dumps(payload).encode()
                req2 = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=data,
                    headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req2, timeout=15) as resp:
                    raw_text = _json.loads(resp.read())["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[finsnap] OpenAI error: {e}", file=sys.stderr)

    if not raw_text:
        return None

    # ── Parse structured response ──────────────────────────────────────────────
    result = {"context": "", "bull": "", "bear": "", "sentiment": "NEUTRAL"}
    for line in raw_text.strip().splitlines():
        if line.startswith("CONTEXT:"):
            result["context"] = line[8:].strip()
        elif line.startswith("BULL:"):
            result["bull"] = line[5:].strip()
        elif line.startswith("BEAR:"):
            result["bear"] = line[5:].strip()
        elif line.startswith("SENTIMENT:"):
            s = line[10:].strip().upper()
            if s in ("BULLISH", "NEUTRAL", "BEARISH"):
                result["sentiment"] = s

    return result


def template_synthesis(ticker: str, quote: dict, news: list) -> dict:
    """
    Rule-based fallback synthesis when no AI key is available.
    Generates a mechanical but correct snapshot.
    """
    change_pct = quote.get("change_pct") or 0
    wk52_pos = quote.get("wk52_position_pct")
    trailing_pe = quote.get("trailing_pe")
    beta = quote.get("beta") or 1.0

    # Sentiment: weighted combination of momentum signals
    score = 0
    if change_pct > 1.5:
        score += 2
    elif change_pct > 0:
        score += 1
    elif change_pct < -1.5:
        score -= 2
    elif change_pct < 0:
        score -= 1
    if wk52_pos and wk52_pos > 75:
        score += 1
    elif wk52_pos and wk52_pos < 25:
        score -= 1

    sentiment = "BULLISH" if score >= 2 else "BEARISH" if score <= -2 else "NEUTRAL"

    wk52_desc = f"{wk52_pos:.0f}% of its 52-week range" if wk52_pos is not None else "its 52-week range"
    pe_str = f"{trailing_pe:.1f}x P/E" if trailing_pe else "no trailing P/E (no earnings)"

    context = (
        f"{ticker} trades at {wk52_desc}, "
        f"{'near the top' if wk52_pos and wk52_pos > 70 else 'near the bottom' if wk52_pos and wk52_pos < 30 else 'mid-range'} "
        f"of its 52-week band, with {pe_str}."
    )
    bull = (
        f"{'Positive momentum today' if change_pct > 0 else 'Elevated beta'} "
        f"({'up ' + str(abs(round(change_pct, 1))) + '%' if change_pct > 0 else f'β={beta:.1f}'}) "
        f"suggests active institutional interest."
    )
    bear = (
        f"{'High valuation relative to peers' if trailing_pe and trailing_pe > 30 else 'Market sensitivity'} "
        f"({'P/E > 30x with limited margin of safety' if trailing_pe and trailing_pe > 30 else f'β={beta:.1f} amplifies drawdowns in risk-off environments'})."
    )

    return {"context": context, "bull": bull, "bear": bear, "sentiment": sentiment}


# ── Output formatting ──────────────────────────────────────────────────────────

def format_text(ticker: str, quote: dict, news: list, analysis: dict) -> str:
    """Plain-text snapshot for terminal / Telegram."""
    up = (quote.get("change_pct") or 0) >= 0
    emoji = CHANGE_EMOJI[up]
    sentiment_label = {"BULLISH": "🟢 BULLISH", "BEARISH": "🔴 BEARISH", "NEUTRAL": "⚪ NEUTRAL"}

    lines = [
        f"{emoji} {quote.get('short_name', ticker)} ({ticker})",
        f"   Price:  ${quote.get('price', 'N/A')}  {quote.get('change_str', '')}",
        f"   52wk:   ${quote.get('wk52_low', '?')} – ${quote.get('wk52_high', '?')}  "
        f"({quote.get('wk52_position_pct', '?')}% of range)",
        f"   P/E:    {quote.get('trailing_pe') or 'N/A'}x (fwd: {quote.get('forward_pe') or 'N/A'}x)  "
        f"MCap: {quote.get('market_cap_str', 'N/A')}",
        f"   Vol:    {quote.get('volume_str', 'N/A')}  |  Beta: {quote.get('beta') or 'N/A'}",
        "",
    ]

    if news:
        lines.append("📰 Recent news:")
        for a in news[:NEWS_COUNT]:
            lines.append(f"   • {a['title']} — {a['publisher']}")
        lines.append("")

    if analysis:
        lines += [
            f"💡 {analysis['context']}",
            f"🐂 Bull: {analysis['bull']}",
            f"🐻 Bear: {analysis['bear']}",
            f"   Sentiment: {sentiment_label.get(analysis['sentiment'], analysis['sentiment'])}",
        ]

    market_state = quote.get("market_state", "")
    if market_state != "REGULAR":
        lines.append(f"\n   ℹ️  Market is {market_state.lower()} — price reflects last close")

    return "\n".join(lines)


def build_discord_embed(ticker: str, quote: dict, news: list, analysis: dict) -> dict:
    """Build a Discord embed payload for webhook delivery."""
    up = (quote.get("change_pct") or 0) >= 0
    price_emoji = CHANGE_EMOJI[up]
    sentiment = analysis.get("sentiment", "UNKNOWN") if analysis else "UNKNOWN"
    color = SENTIMENT_COLORS.get(sentiment, SENTIMENT_COLORS["UNKNOWN"])

    title = f"{price_emoji} {quote.get('short_name', ticker)} ({ticker})"
    description = (
        f"**${quote.get('price', 'N/A')}**  `{quote.get('change_str', 'N/A')}`\n"
        f"52-wk: ${quote.get('wk52_low', '?')} – ${quote.get('wk52_high', '?')} "
        f"({quote.get('wk52_position_pct', '?')}% of range)"
    )

    fields = [
        {"name": "Market Cap", "value": quote.get("market_cap_str", "N/A"), "inline": True},
        {"name": "Trailing P/E", "value": f"{quote.get('trailing_pe') or 'N/A'}x", "inline": True},
        {"name": "Forward P/E", "value": f"{quote.get('forward_pe') or 'N/A'}x", "inline": True},
        {"name": "Volume", "value": quote.get("volume_str", "N/A"), "inline": True},
        {"name": "Beta", "value": str(quote.get("beta") or "N/A"), "inline": True},
        {"name": "Market", "value": quote.get("market_state", "?"), "inline": True},
    ]

    if news:
        headlines = "\n".join(
            f"• [{a['title'][:60]}...]({a['url']}) — *{a['publisher']}*"
            if a.get("url") else f"• {a['title'][:70]}... — *{a['publisher']}*"
            for a in news[:NEWS_COUNT]
        )
        fields.append({"name": "📰 Recent Headlines", "value": headlines, "inline": False})

    if analysis:
        analysis_text = (
            f"**Context:** {analysis['context']}\n"
            f"**🐂 Bull:** {analysis['bull']}\n"
            f"**🐻 Bear:** {analysis['bear']}\n"
            f"**Verdict:** {analysis['sentiment']}"
        )
        fields.append({"name": "💡 AI Analysis", "value": analysis_text, "inline": False})

    market_state = quote.get("market_state", "")
    footer_text = f"finsnap • Data ~15min delayed"
    if market_state != "REGULAR":
        footer_text = f"⚠️ Market {market_state} — last close shown  |  {footer_text}"

    return {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "footer": {"text": footer_text},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }


def send_discord_webhook(payload: dict, webhook_url: str) -> bool:
    """POST embed payload to Discord webhook. Returns True on success."""
    try:
        if _REQUESTS_AVAILABLE:
            import requests as req
            r = req.post(webhook_url, json=payload, timeout=10)
            r.raise_for_status()
            return True
        else:
            import urllib.request, json as _json
            data = _json.dumps(payload).encode()
            req2 = urllib.request.Request(
                webhook_url, data=data,
                headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req2, timeout=10):
                return True
    except Exception as e:
        print(f"[finsnap] Discord webhook error: {e}", file=sys.stderr)
        return False


# ── Main orchestration ─────────────────────────────────────────────────────────

def snap(ticker: str, use_ai: bool = True, text_only: bool = False) -> dict:
    """
    Run a full snapshot for one ticker.
    Returns dict with all data + formatted outputs.
    """
    print(f"[finsnap] Fetching {ticker}...", file=sys.stderr)

    # 1. Fetch data (parallelisable — left as sequential for readability)
    try:
        quote = fetch_quote(ticker)
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}

    try:
        news = fetch_news(ticker)
    except Exception:
        news = []

    # 2. Synthesize
    analysis = None
    if use_ai and not NO_AI:
        prompt = build_synthesis_prompt(ticker, quote, news)
        analysis = synthesize_ai(prompt)
        if not analysis:
            print(f"[finsnap] AI unavailable — using template synthesis", file=sys.stderr)
            analysis = template_synthesis(ticker, quote, news)
    else:
        analysis = template_synthesis(ticker, quote, news)

    # 3. Format
    text_out = format_text(ticker, quote, news, analysis)
    embed = None if text_only else build_discord_embed(ticker, quote, news, analysis)

    return {
        "ticker": ticker,
        "quote": quote,
        "news": news,
        "analysis": analysis,
        "text": text_out,
        "embed": embed,
    }


def main():
    parser = argparse.ArgumentParser(description="finsnap — financial snapshot skill")
    parser.add_argument("tickers", nargs="+", help="Ticker symbols (e.g. AAPL MSFT NVDA)")
    parser.add_argument("--text", action="store_true", help="Output plain text only (no Discord embed)")
    parser.add_argument("--webhook", action="store_true", help="Force Discord webhook delivery")
    parser.add_argument("--no-ai", action="store_true", help="Skip AI synthesis")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    use_ai = not args.no_ai
    results = []

    for ticker in args.tickers:
        result = snap(ticker.upper(), use_ai=use_ai, text_only=args.text)
        results.append(result)

        if "error" in result:
            print(f"[finsnap] Error for {ticker}: {result['error']}", file=sys.stderr)
            continue

        # Always print text output to stdout
        if not args.as_json:
            print(result["text"])
            print()

        # Discord webhook delivery
        if not args.text and result.get("embed"):
            webhook = DISCORD_WEBHOOK
            if webhook:
                ok = send_discord_webhook(result["embed"], webhook)
                if ok:
                    print(f"[finsnap] ✅ Delivered {ticker} to Discord", file=sys.stderr)
                else:
                    print(f"[finsnap] ⚠️  Discord delivery failed for {ticker}", file=sys.stderr)

    if args.as_json:
        print(json.dumps(results, indent=2))

    # Exit non-zero if any ticker had an error
    if any("error" in r for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
