# finsnap — OpenClaw Skill Authoring Demo

> **Portfolio Category:** Skills authoring — a complete, ClawHub-ready OpenClaw skill package

---

## What It Does

**finsnap** is a production-ready OpenClaw skill that delivers AI-synthesized financial snapshots for any US stock ticker — on demand, via natural language.

Ask your OpenClaw agent:
- *"What's Nvidia trading at?"*
- *"Quick snap on AAPL and MSFT"*
- *"Is Tesla worth looking at right now?"*

The skill fetches live price data + recent news (no API key required), synthesizes a concise bull/bear analysis via Claude or GPT, and delivers a rich Discord embed.

---

## OpenClaw Concepts Demonstrated

| Concept | Where |
|---|---|
| **SKILL.md authoring** | `finsnap/SKILL.md` — full spec: frontmatter, when-to-use, step-by-step agent instructions, output formatting rules, error handling table |
| **Step-by-step agent instruction design** | SKILL.md §§ Step 1–5: teaching the LLM to parse intent → fetch → synthesize → format |
| **Graceful degradation** | `finsnap.py`: AI → template fallback; Anthropic → OpenAI fallback; Brave → DDG fallback |
| **Tool composition** | bash scripts (data fetch) + Python (orchestration + formatting) + Discord webhook (delivery) |
| **ClawHub packaging** | `clawhub.json` — full publishing manifest with config schema, examples, dependency declarations |
| **Skill installation** | `install.sh` — auto-detects OpenClaw workspace, validates deps, self-documents |
| **Multi-surface output** | Terminal text + Discord rich embeds from same data pipeline |
| **Error taxonomy** | SKILL.md error handling table: invalid ticker, market closed, rate limited, partial data |

---

## Project Structure

```
finsnap/
├── SKILL.md                   ← OpenClaw skill manifest (the core artifact)
├── clawhub.json               ← ClawHub publishing metadata
├── install.sh                 ← Auto-installer
├── scripts/
│   ├── fetch_quote.sh         ← Yahoo Finance price/metrics via curl + python3
│   ├── fetch_news.sh          ← Yahoo Finance news via curl + python3
│   └── finsnap.py             ← Orchestration entry point (fetch → synthesize → deliver)
├── templates/
│   └── discord_embed.json     ← Discord embed template with placeholders
└── demo/
    └── sample_output.md       ← Example terminal + Discord + JSON output
```

---

## How to Run

### Prerequisites

```bash
pip3 install requests           # HTTP client
pip3 install anthropic          # AI synthesis (optional — template fallback if missing)
```

### Quick Start

```bash
# Single ticker
python3 finsnap/scripts/finsnap.py AAPL

# Multiple tickers
python3 finsnap/scripts/finsnap.py NVDA MSFT AAPL

# Plain text only (no Discord)
python3 finsnap/scripts/finsnap.py --text TSLA

# Skip AI synthesis
python3 finsnap/scripts/finsnap.py --no-ai GOOGL

# JSON output (pipe to jq, store to file, etc.)
python3 finsnap/scripts/finsnap.py --json AAPL | jq .
```

### Discord Push Delivery

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/TOKEN"
python3 finsnap/scripts/finsnap.py NVDA
# → rich embed posted to Discord automatically
```

### Install as OpenClaw Skill

```bash
cd finsnap
./install.sh
# Then ask your agent: "What's Apple trading at?"
```

### Fetch Scripts (standalone)

```bash
# Just the data — useful for piping
bash finsnap/scripts/fetch_quote.sh AAPL | jq '.price, .change_pct'
bash finsnap/scripts/fetch_news.sh NVDA 5 | jq '.[].title'
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | No | Claude API key for AI synthesis |
| `OPENAI_API_KEY` | No | OpenAI fallback for AI synthesis |
| `DISCORD_WEBHOOK_URL` | No | Discord webhook for push delivery |
| `FINSNAP_NEWS_COUNT` | No | Headlines to include (default: 3) |
| `FINSNAP_NO_AI` | No | Set to `1` to disable AI synthesis |

The skill works with **zero environment variables** — data is free via Yahoo Finance's unofficial API, and synthesis falls back to rule-based analysis if no AI key is present.

---

## Design Assumptions

1. **Yahoo Finance unofficial API** — used instead of paid APIs (Alpha Vantage, Polygon) for zero-cost operation and maximum portability. Rate limit is ~100 req/min — well above any human interaction rate.

2. **~15 min delay** — Yahoo Finance's free tier doesn't offer real-time data. Noted prominently in all output and the SKILL.md error table.

3. **Claude claude-3-5-haiku-20241022** chosen for synthesis — fastest + cheapest Claude model; 300-token outputs cost fractions of a cent. Correct choice for a high-frequency skill.

4. **Graceful degradation is non-negotiable** — a portfolio skill that crashes when the API is down isn't demoable. Every external call has a fallback path.

5. **ClawHub spec** — `clawhub.json` structure mirrors what ClawHub expects based on available skill packages in the registry. This is ready to publish once ClawHub v2 launches.

6. **SKILL.md is the main deliverable** — in OpenClaw, the SKILL.md *is* the skill. The bash/Python scripts are its implementation; the SKILL.md is what teaches the agent to use them.

---

## Teaching Notes (for Loom/Tutorial)

This project is designed as tutorial content. Key teaching moments:

**1. SKILL.md is a prompt, not just docs**
The `When to Use / When NOT to Use` sections are literally injected into the agent's context. Writing good skill docs = writing good prompts.

**2. Step-by-step agent instructions**
Notice how SKILL.md §§ Step 1–5 reads like pseudocode for the agent. This is intentional — LLMs follow explicit sequential instructions far better than vague descriptions.

**3. The fallback pyramid**
`anthropic key → openai key → template synthesis` and `Brave → DDG → empty`. Every production skill needs this. Teach it as a pattern.

**4. clawhub.json = npm package.json for skills**
The config_schema block is what ClawHub uses to render the install UI. Teaching this parallel makes it instantly memorable.

**5. install.sh teaches skill deployment**
Most tutorials skip the "how do I actually ship this" step. The install script auto-detects the workspace, validates deps, and self-documents. That's the professional touch.
