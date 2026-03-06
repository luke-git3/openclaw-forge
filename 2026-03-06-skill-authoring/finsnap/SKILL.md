---
name: finsnap
description: "Real-time financial snapshot for any stock ticker. Fetches live price, key metrics, and recent news; synthesizes a brief bull/bear analysis; delivers a formatted summary to Discord or inline. Use when: user asks about a stock price, wants a quick company overview, or says 'snap on [TICKER]'. NOT for: portfolio management, trade execution, historical analysis, or crypto."
homepage: https://github.com/luke-git3/openclaw-forge
metadata:
  openclaw:
    emoji: "📈"
    version: "1.0.0"
    author: "Luke Stephens"
    requires:
      bins: ["bash", "curl", "python3"]
      pip: ["requests"]
    config:
      DISCORD_WEBHOOK_URL:
        description: "Optional Discord webhook for push delivery"
        required: false
      FINSNAP_DEFAULT_CHANNEL:
        description: "Default Discord channel ID for delivery (e.g. 1234567890)"
        required: false
---

# finsnap — Financial Snapshot Skill

Deliver an instant, AI-synthesized financial snapshot for any US stock ticker.

---

## When to Use

✅ **USE this skill when:**
- "What's NVDA trading at?"
- "Give me a snap on Apple"
- "Quick overview of $MSFT"
- "How's Tesla doing today?"
- "Finsnap AAPL GOOGL AMZN"
- User asks for price, P/E, 52-week range, or recent news on a stock

## When NOT to Use

❌ **DON'T use this skill when:**
- Crypto queries → use a crypto-specific skill
- Portfolio rebalancing or trade execution → out of scope
- Historical backtesting → use a data science tool
- Options pricing or derivatives → use a specialized tool
- Non-US exchanges with unusual suffixes → data may be incomplete

---

## Step-by-Step Execution

When triggered, follow these steps **in order**:

### Step 1 — Extract Tickers

Parse the user's message for ticker symbols. Rules:
- `$AAPL`, `AAPL`, `Apple`, `apple stock` → all resolve to `AAPL`
- Common name → ticker mappings (use your knowledge):
  - Apple → AAPL, Google/Alphabet → GOOGL, Microsoft → MSFT, Amazon → AMZN
  - Tesla → TSLA, Nvidia → NVDA, Meta → META, Netflix → NFLX
  - S&P 500 → SPY (ETF proxy), Nasdaq → QQQ, Dow → DIA
- If ambiguous, pick the most common interpretation and note it
- Support 1–5 tickers per request (batch them)

### Step 2 — Fetch Price Data

For each ticker, run:

```bash
bash scripts/fetch_quote.sh TICKER
```

Or via curl directly:

```bash
# Live quote (price, change, volume, market cap)
curl -s "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?interval=1d&range=1d" \
  -H "User-Agent: Mozilla/5.0" | python3 scripts/parse_quote.py
```

**Key fields to extract:**
- `regularMarketPrice` — current price
- `regularMarketChangePercent` — % change today
- `regularMarketVolume` — volume
- `fiftyTwoWeekHigh` / `fiftyTwoWeekLow` — 52-week range
- `marketCap` — market cap (from summary detail endpoint)
- `trailingPE` — trailing P/E ratio
- `forwardPE` — forward P/E ratio

```bash
# For fundamental metrics (P/E, market cap, etc.)
curl -s "https://query1.finance.yahoo.com/v10/finance/quoteSummary/AAPL?modules=price,summaryDetail,defaultKeyStatistics" \
  -H "User-Agent: Mozilla/5.0"
```

### Step 3 — Fetch News Headlines

```bash
bash scripts/fetch_news.sh TICKER
```

Or directly:

```bash
# Yahoo Finance search returns up to 5 recent news items
curl -s "https://query1.finance.yahoo.com/v1/finance/search?q=AAPL&quotesCount=1&newsCount=5&enableFuzzyQuery=false" \
  -H "User-Agent: Mozilla/5.0"
```

Extract: `news[*].title` + `news[*].publisher` + `news[*].providerPublishTime`

### Step 4 — Synthesize Analysis

With the price data + headlines, synthesize a brief analysis:

**Prompt template:**
```
You are a financial analyst delivering a 60-second briefing.
Ticker: {TICKER}
Current price: ${price} ({change_pct}% today)
52-week range: ${wk52_low} – ${wk52_high}
P/E (trailing): {pe}
Recent headlines:
{headlines}

Write:
1. One sentence: where the stock sits vs its 52-week range (context)
2. One bull case point (one sentence, grounded in the data)
3. One bear case point (one sentence, grounded in the data)
4. One-word sentiment: BULLISH / NEUTRAL / BEARISH

Be direct. No disclaimers. Finance professional audience.
```

### Step 5 — Format Output

**For Discord (default):**
Use the embed template at `templates/discord_embed.json`.
Post via webhook (`DISCORD_WEBHOOK_URL` env var) or via OpenClaw `message` tool.

**For inline text (fallback):**
```
📈 **AAPL** — $182.45 (+1.2%)
52wk: $124.17 – $199.62 | P/E: 28.4x | MCap: $2.8T
📰 "Apple Reports Record Services Revenue" — Bloomberg
💡 Sitting near 52-week highs. Bull: services growth offsets hardware slowdown.
   Bear: China exposure and regulatory risk remain overhangs.
Sentiment: BULLISH
```

---

## Examples

**User:** "Quick snap on Nvidia"
**Action:** Fetch NVDA quote + news → synthesize → post to Discord

**User:** "How are AAPL, MSFT, and GOOGL doing today?"
**Action:** Fetch all three in parallel → synthesize each → post a combined summary

**User:** "Is Tesla a buy right now?"
**Action:** Fetch TSLA data → synthesize bull/bear → note you're not a financial advisor, just sharing the data picture

---

## Error Handling

| Situation | Handling |
|---|---|
| Market closed / weekend | Show last close price, note "MARKET CLOSED" |
| Invalid ticker | Reply: "Couldn't find data for [TICKER]. Check the symbol and try again." |
| API rate limited | Retry once after 2s; if still failing, use fallback message |
| Missing P/E (no earnings yet) | Show "N/A" for P/E; note "no earnings history" |
| Partial data | Show what you have; mark missing fields as "–" |

---

## Output Formatting Rules

- **Prices:** Always 2 decimal places (`$182.45`)
- **% changes:** Always include sign and 1 decimal (`+1.2%` / `-0.8%`)
- **Market cap:** Humanize (`$2.8T`, `$48.2B`, `$892M`)
- **Volume:** Humanize (`12.4M`, `890K`)
- **P/E:** One decimal (`28.4x`)
- **52-week position:** Calculate as `(price - wk52_low) / (wk52_high - wk52_low) * 100`
  - Show as: "trades at XX% of its 52-week range"

---

## Rate Limits & Caveats

- Yahoo Finance unofficial API: ~100 req/min before throttling
- Data is delayed ~15 minutes during market hours
- This is for informational purposes only; not investment advice
- For higher volume use, consider Yahoo Finance Premium or Alpha Vantage

---

## Configuration

Set in your OpenClaw environment or `.env` file:

```bash
# Optional: push results to Discord
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."

# Optional: default channel for delivery
export FINSNAP_DEFAULT_CHANNEL="1234567890"

# Optional: number of news items to include (default: 3)
export FINSNAP_NEWS_COUNT=3
```
