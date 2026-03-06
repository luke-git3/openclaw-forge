#!/usr/bin/env bash
# finsnap/scripts/fetch_news.sh
# Fetches recent news headlines for a ticker from Yahoo Finance search API.
# No API key required.
#
# Usage:   ./fetch_news.sh AAPL [N]
# Args:    TICKER — stock symbol (required)
#          N      — number of headlines to return (default: 5, max: 10)
# Output:  JSON array of {title, publisher, published_at, url}

set -euo pipefail

TICKER="${1:?Usage: fetch_news.sh TICKER [N]}"
TICKER="${TICKER^^}"
NEWS_COUNT="${2:-5}"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

SEARCH_URL="https://query1.finance.yahoo.com/v1/finance/search?q=${TICKER}&quotesCount=1&newsCount=${NEWS_COUNT}&enableFuzzyQuery=false&enableNavLinks=false"

RAW=$(curl -sf "$SEARCH_URL" -H "User-Agent: $UA") || {
  echo '[]' 
  exit 0
}

python3 - <<PYEOF
import json, sys
from datetime import datetime, timezone

raw = json.loads("""${RAW}""".replace('"""', '\\"\\"\\"'))
articles = raw.get("news", [])
out = []

for a in articles[:${NEWS_COUNT}]:
    ts = a.get("providerPublishTime")
    pub_time = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if ts else "unknown"
    out.append({
        "title": a.get("title", ""),
        "publisher": a.get("publisher", ""),
        "published_at": pub_time,
        "url": a.get("link", ""),
        "thumbnail": (a.get("thumbnail") or {}).get("resolutions", [{}])[0].get("url", "")
    })

print(json.dumps(out, indent=2))
PYEOF
