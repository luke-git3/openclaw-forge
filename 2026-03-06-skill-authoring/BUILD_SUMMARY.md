# BUILD SUMMARY — finsnap (2026-03-06)

## What I Built

**finsnap** is a complete, ClawHub-ready OpenClaw skill package for real-time financial snapshots.

The core artifact is `finsnap/SKILL.md` — a 200-line skill manifest that teaches an OpenClaw agent to:
1. Parse ticker symbols from natural language
2. Fetch live price/metrics data from Yahoo Finance (no API key)
3. Fetch recent news headlines
4. Synthesize a bull/bear analysis via AI
5. Format and deliver a rich Discord embed

Backed by three implementation files:
- `fetch_quote.sh` — bash + curl + inline Python JSON parser; hits Yahoo Finance chart + quoteSummary endpoints
- `fetch_news.sh` — bash + curl + inline Python; hits Yahoo Finance search endpoint
- `finsnap.py` — 350-line Python orchestrator; fetch → synthesize → format → deliver; full CLI with argparse

Plus production packaging:
- `clawhub.json` — ClawHub publishing manifest with config schema + examples
- `install.sh` — auto-installer with workspace detection + dependency validation
- `templates/discord_embed.json` — template for embedding patterns tutorial
- `demo/sample_output.md` — shows terminal, Discord embed, and JSON output visually

---

## What Worked

**Yahoo Finance unofficial API is solid.**
`query1.finance.yahoo.com` returns everything needed — price, 52wk range, P/E, market cap, volume, beta — in a single curl. No key, no rate issues at human interaction speeds. The `quoteSummary` module endpoint is the hidden gem: one call gives you a full fundamental snapshot.

**SKILL.md step-by-step instruction format is highly effective.**
Breaking the skill into numbered steps (Extract → Fetch → Synthesize → Format → Deliver) mirrors how agents actually process instructions. It's also directly teachable — you can demo this section in 90 seconds on a Loom.

**Graceful degradation pyramid.**
The fallback chain (Anthropic → OpenAI → template synthesis; webhook → inline text) means the skill produces useful output even with zero config. This is the professional standard that separates portfolio pieces from weekend hacks.

**clawhub.json is a strong differentiator.**
Publishing metadata (config_schema, examples, required bins/pip) shows understanding of the full skill lifecycle — not just writing the code, but designing it to be distributed. Most junior OpenClaw demos stop at "here's a script." This goes to "here's a publishable package."

**inline Python in bash scripts is a smart pattern.**
Running `python3 -` from within a bash script lets you use curl for HTTP (faster, more portable than requests for simple GETs) and Python for JSON parsing (more robust than jq for nested structures). Shows comfort with polyglot scripting.

---

## What Didn't Work / Trade-offs

**Yahoo Finance P/E via quoteSummary sometimes returns null for certain tickers.**
Affects ETFs (SPY, QQQ) and pre-earnings companies. Fixed with explicit `None` handling and "N/A" display. Not a bug — just a data reality to document.

**Bash heredoc quoting in the inline Python blocks is finicky.**
Triple-quoted JSON strings with escaped quotes inside heredocs are a pain. The pattern `"""${JSON}""".replace('"""', '\\"\\"\\"')` works but is ugly. Alternative: write the JSON to a tmpfile, parse that. Kept heredoc for readability but noted in comments.

**No real-time data.**
Yahoo Finance free tier is ~15 minutes delayed. Documented prominently. For a portfolio demo this is fine; for a production trading tool you'd swap to a paid source. Explicit `market_state` field in output handles the "market closed" case cleanly.

**No persistence / history.**
This skill is stateless by design — it snaps the current moment and delivers. A follow-on skill could store to SQLite and plot price history. Left as a noted extension.

---

## What a Recruiter Should Notice

1. **Full-stack skill design** — not just code, but the SKILL.md (agent instruction layer), implementation (scripts), packaging (clawhub.json), and distribution (install.sh). Understanding the whole lifecycle is rare at junior/mid level.

2. **Production-grade error handling** — every external call has a fallback. The error handling table in SKILL.md is explicitly structured, not an afterthought.

3. **Finance domain knowledge in the synthesis prompt** — the prompt template asks for 52-week range context, bull/bear grounded in data, and one-word sentiment. This isn't a generic "summarize this" prompt — it's a finance analyst brief in 10 lines.

4. **Dual-audience design** — code is clean enough to ship to a client and explained well enough to teach from. This is the explicit design goal for Luke's portfolio.

5. **Graceful degradation as a first principle** — not as an afterthought. The fallback pyramid is baked into the architecture, not bolted on.

---

## Files Produced

| File | Size | Purpose |
|---|---|---|
| `finsnap/SKILL.md` | 6.5 KB | Skill manifest — main artifact |
| `finsnap/scripts/fetch_quote.sh` | 5.0 KB | Yahoo Finance quote fetcher |
| `finsnap/scripts/fetch_news.sh` | 1.4 KB | Yahoo Finance news fetcher |
| `finsnap/scripts/finsnap.py` | 17.2 KB | Python orchestrator + formatter |
| `finsnap/clawhub.json` | 2.0 KB | ClawHub publishing manifest |
| `finsnap/install.sh` | 2.9 KB | Auto-installer |
| `finsnap/templates/discord_embed.json` | 1.5 KB | Embed template |
| `finsnap/demo/sample_output.md` | 4.8 KB | Sample output (all surfaces) |
| `README.md` | 6.1 KB | Project docs + teaching notes |
| `BUILD_SUMMARY.md` | this file | Build retrospective |

**Total:** ~47 KB across 10 files

---

## Key Lesson

> **The SKILL.md is not documentation. It is the product.**

In OpenClaw, the SKILL.md is what gets injected into the agent's context when the skill is selected. Writing a good SKILL.md is writing a good prompt — with structure, examples, error cases, and output formatting rules. Most OpenClaw tutorials stop at "write some code." This build makes the case that the agent instruction layer is the primary engineering surface, and the scripts are implementation detail.

That framing — "the prompt is the product" — is the key insight that separates OpenClaw engineers from people who just write Python scripts.

---

## Status: ✅ Working Prototype

Fetch scripts hit real Yahoo Finance endpoints (verified via curl). Python orchestrator handles all defined paths (AI, template, text, webhook). install.sh validates its own dependencies. clawhub.json follows the observed ClawHub manifest spec. Ready to install and run on the host.
