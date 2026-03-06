#!/usr/bin/env bash
# finsnap/scripts/fetch_quote.sh
# Fetches real-time quote data for a ticker from Yahoo Finance (unofficial API).
# No API key required. Data is ~15min delayed during market hours.
#
# Usage:   ./fetch_quote.sh AAPL
# Output:  JSON blob with price, change, volume, 52wk range, P/E, market cap
# Depends: curl, python3 (stdlib only)

set -euo pipefail

TICKER="${1:?Usage: fetch_quote.sh TICKER}"
TICKER="${TICKER^^}"   # Uppercase

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# ── Endpoint 1: chart (price, volume, 52-week range) ──────────────────────────
CHART_URL="https://query1.finance.yahoo.com/v8/finance/chart/${TICKER}?interval=1d&range=1d&includePrePost=false"

# ── Endpoint 2: quote summary (P/E, market cap, fundamentals) ─────────────────
SUMMARY_URL="https://query1.finance.yahoo.com/v10/finance/quoteSummary/${TICKER}?modules=price%2CsummaryDetail%2CdefaultKeyStatistics"

CHART_JSON=$(curl -sf "$CHART_URL" -H "User-Agent: $UA") || {
  echo '{"error": "Failed to fetch chart data for '"$TICKER"'"}' >&2
  exit 1
}

SUMMARY_JSON=$(curl -sf "$SUMMARY_URL" -H "User-Agent: $UA") || {
  echo '{"error": "Failed to fetch summary data for '"$TICKER"'"}' >&2
  # Non-fatal — continue without fundamentals
  SUMMARY_JSON="{}"
}

# ── Parse and combine into a clean output blob ────────────────────────────────
python3 - <<PYEOF
import json, sys

chart = json.loads("""${CHART_JSON}""".replace('"""', '\\"\\"\\"'))
summary = json.loads("""${SUMMARY_JSON}""".replace('"""', '\\"\\"\\"'))

def get_val(d, *keys, default=None):
    """Safely traverse nested dict."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k, {})
    if isinstance(d, dict):
        return d.get("raw", default)
    return d if d is not None else default

def humanize(n):
    """Turn 2_800_000_000_000 into '2.8T' etc."""
    if n is None:
        return "N/A"
    n = float(n)
    for suffix, div in [("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if abs(n) >= div:
            return f"{n/div:.1f}{suffix}"
    return f"{n:.2f}"

try:
    meta = chart["chart"]["result"][0]["meta"]
    price = meta.get("regularMarketPrice")
    prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
    change = (price - prev_close) if price and prev_close else None
    change_pct = (change / prev_close * 100) if change and prev_close else None
    wk52_high = meta.get("fiftyTwoWeekHigh")
    wk52_low = meta.get("fiftyTwoWeekLow")
    volume = meta.get("regularMarketVolume")
    market_state = meta.get("marketState", "UNKNOWN")

    # Position in 52-week range (0% = at 52wk low, 100% = at 52wk high)
    wk52_pos = None
    if wk52_high and wk52_low and price and (wk52_high - wk52_low) > 0:
        wk52_pos = round((price - wk52_low) / (wk52_high - wk52_low) * 100, 1)

    # Fundamentals from summary endpoint
    price_mod = get_val(summary, "quoteSummary", "result", 0, "price") or {}
    summary_mod = get_val(summary, "quoteSummary", "result", 0, "summaryDetail") or {}
    key_stats = get_val(summary, "quoteSummary", "result", 0, "defaultKeyStatistics") or {}

    # Try both summary and chart for market cap
    mkt_cap_raw = get_val(summary, "quoteSummary", "result", 0, "price", "marketCap")
    trailing_pe = get_val(summary, "quoteSummary", "result", 0, "summaryDetail", "trailingPE")
    forward_pe = get_val(summary, "quoteSummary", "result", 0, "summaryDetail", "forwardPE")
    dividend_yield = get_val(summary, "quoteSummary", "result", 0, "summaryDetail", "dividendYield")
    beta = get_val(summary, "quoteSummary", "result", 0, "summaryDetail", "beta")
    short_name = meta.get("instrumentType", "Equity")

    result = {
        "ticker": meta.get("symbol", TICKER.upper()),
        "short_name": meta.get("shortName") or TICKER.upper(),
        "price": round(price, 2) if price else None,
        "prev_close": round(prev_close, 2) if prev_close else None,
        "change": round(change, 2) if change else None,
        "change_pct": round(change_pct, 2) if change_pct else None,
        "change_str": f"{'+' if change_pct and change_pct >= 0 else ''}{change_pct:.1f}%" if change_pct else "N/A",
        "wk52_high": round(wk52_high, 2) if wk52_high else None,
        "wk52_low": round(wk52_low, 2) if wk52_low else None,
        "wk52_position_pct": wk52_pos,
        "volume": volume,
        "volume_str": humanize(volume),
        "market_cap_raw": mkt_cap_raw,
        "market_cap_str": humanize(mkt_cap_raw) if mkt_cap_raw else "N/A",
        "trailing_pe": round(trailing_pe, 1) if trailing_pe else None,
        "forward_pe": round(forward_pe, 1) if forward_pe else None,
        "dividend_yield_pct": round(dividend_yield * 100, 2) if dividend_yield else None,
        "beta": round(beta, 2) if beta else None,
        "market_state": market_state,
        "currency": meta.get("currency", "USD"),
    }

    print(json.dumps(result, indent=2))

except Exception as e:
    print(json.dumps({"error": str(e), "ticker": "$TICKER"}), file=sys.stderr)
    sys.exit(1)
PYEOF
