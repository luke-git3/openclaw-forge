# finsnap — Sample Output

This file shows what finsnap produces so you can judge it before running it.
All values are illustrative but use realistic market data patterns.

---

## Terminal Output (`python3 finsnap.py NVDA AAPL`)

```
[finsnap] Fetching NVDA...
[finsnap] Fetching AAPL...

📈 NVIDIA Corporation (NVDA)
   Price:  $875.40  +3.2%
   52wk:   $405.12 – $974.00  (87% of range)
   P/E:    65.4x (fwd: 38.2x)  MCap: $2.1T
   Vol:    48.3M  |  Beta: 1.72

📰 Recent news:
   • NVIDIA Raises Q1 Guidance on Blackwell Demand — Reuters
   • Jensen Huang: "We are at the iPhone moment for AI" — Bloomberg
   • NVDA Institutional Buying Surges in Q4 — Barron's

💡 NVDA trades at 87% of its 52-week range, near the top of its band, with 65.4x P/E.
🐂 Bull: Blackwell GPU ramp and persistent hyperscaler capex acceleration support continued revenue beats well into FY2026.
🐻 Bear: P/E compression risk is significant if AI capex cools or TSMC supply constraints re-emerge.
   Sentiment: 🟢 BULLISH


📈 Apple Inc. (AAPL)
   Price:  $185.92  +0.4%
   52wk:   $164.08 – $199.62  (98% of range)
   P/E:    28.8x (fwd: 26.1x)  MCap: $2.8T
   Vol:    52.1M  |  Beta: 1.24

📰 Recent news:
   • Apple Intelligence Rolls Out to EU Users in Spring Update — 9to5Mac
   • Services Revenue Hits Record $26.3B in Holiday Quarter — CNBC
   • Apple Vision Pro Sales Disappoint, Analysts Cut Forecasts — The Verge

💡 AAPL trades at 98% of its 52-week range, near all-time highs, with 28.8x P/E.
🐂 Bull: Services flywheel (App Store, iCloud, Apple Pay) prints record revenue each quarter with 70%+ gross margin, providing durable earnings floor.
🐻 Bear: China exposure (~18% of revenue) remains a structural overhang as geopolitical tensions and Huawei competition intensify.
   Sentiment: 🟢 BULLISH
```

---

## Discord Embed (visual)

```
┌─────────────────────────────────────────────────────────┐
│ 📈 NVIDIA Corporation (NVDA)                            │  ← Green left border
│ $875.40  +3.2%                                          │
│ 52-wk: $405.12 – $974.00  (87% of range)               │
├────────────┬──────────────┬───────────────┐             │
│ Market Cap │ Trailing P/E │  Forward P/E  │             │
│    $2.1T   │    65.4x     │    38.2x      │             │
├────────────┴──────────────┴───────────────┘             │
│ 📰 Recent Headlines                                     │
│  • NVIDIA Raises Q1 Guidance on Blackwell Demand        │
│  • Jensen Huang: "We are at the iPhone moment for AI"   │
│  • NVDA Institutional Buying Surges in Q4               │
├─────────────────────────────────────────────────────────┤
│ 💡 AI Analysis                                          │
│  Context: NVDA trades at 87% of its 52-week range...   │
│  🐂 Bull: Blackwell GPU ramp and persistent...          │
│  🐻 Bear: P/E compression risk is significant if...     │
│  Verdict: BULLISH                                       │
├─────────────────────────────────────────────────────────┤
│ finsnap • Data ~15min delayed during market hours       │
└─────────────────────────────────────────────────────────┘
```

---

## JSON Output (`python3 finsnap.py --json NVDA`)

```json
[
  {
    "ticker": "NVDA",
    "quote": {
      "ticker": "NVDA",
      "short_name": "NVIDIA Corporation",
      "price": 875.40,
      "prev_close": 848.71,
      "change": 26.69,
      "change_pct": 3.15,
      "change_str": "+3.2%",
      "wk52_high": 974.00,
      "wk52_low": 405.12,
      "wk52_position_pct": 87.3,
      "volume": 48300000,
      "volume_str": "48.3M",
      "market_cap_raw": 2140000000000,
      "market_cap_str": "2.1T",
      "trailing_pe": 65.4,
      "forward_pe": 38.2,
      "dividend_yield_pct": 0.03,
      "beta": 1.72,
      "market_state": "REGULAR",
      "currency": "USD"
    },
    "news": [
      {
        "title": "NVIDIA Raises Q1 Guidance on Blackwell Demand",
        "publisher": "Reuters",
        "published_at": "2026-03-05 14:30 UTC",
        "url": "https://reuters.com/..."
      }
    ],
    "analysis": {
      "context": "NVDA trades at 87% of its 52-week range, near the top of its band, with 65.4x P/E.",
      "bull": "Blackwell GPU ramp and persistent hyperscaler capex acceleration support continued revenue beats well into FY2026.",
      "bear": "P/E compression risk is significant if AI capex cools or TSMC supply constraints re-emerge.",
      "sentiment": "BULLISH"
    }
  }
]
```

---

## OpenClaw Natural Language Invocation

When the finsnap skill is installed, the agent handles queries like:

| User says | Ticker extracted | Output |
|---|---|---|
| "What's Nvidia at?" | NVDA | Full snap |
| "Quick snap on Apple and Microsoft" | AAPL, MSFT | Both snaps |
| "Is Tesla a buy?" | TSLA | Snap + analysis note |
| "How's the S&P doing?" | SPY | ETF snap |
| "$GOOGL price check" | GOOGL | Price-focused snap |
