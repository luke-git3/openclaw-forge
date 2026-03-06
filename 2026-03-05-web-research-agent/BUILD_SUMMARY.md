# BUILD_SUMMARY.md — Web Research Agent

**Date:** 2026-03-05  
**Category:** Automated web research agent  
**Status:** ✅ Working Prototype  
**Build time:** ~75 minutes  

---

## What Was Built

A complete, end-to-end autonomous research pipeline:

**Core engine (`research_agent.py`, 350 lines):**
- `ResearchAgent` class orchestrates the 5-step pipeline
- Query decomposition via LLM (or template fallback)
- Parallel web search: Brave Search API → DuckDuckGo fallback
- Parallel content extraction: requests + BeautifulSoup, 6 threads
- Cross-source synthesis with Claude: structured JSON output (executive summary, key findings, Q&A pairs, consensus/conflict analysis, data highlights)
- Saves JSON + Markdown to `reports/` directory

**Dashboard (`dashboard/app.py` + templates):**
- Flask app, 3 routes: `/` (report list), `/report/<id>` (detail), `/api/reports` (JSON)
- Dark-theme HTML with sidebar metadata panel, Q&A accordion, source list
- Matches visual style of Forge builds #2 (Alert Brain) and #3 (Pulse)

**Tutorial bridge (`openclaw_demo.py`):**
- Maps each pipeline step to its OpenClaw tool equivalent
- Shows `web_search` → `search()`, `web_fetch` → `extract_content()`, LLM prompt → `synthesize_llm()`
- Includes `teachable_concepts` list — ready to use as a tutorial outline

---

## What Worked

1. **Graceful degradation chain** — Brave API → DDG → template. The agent runs fully offline with `--no-llm`, making it easy to demo anywhere.

2. **JSON extraction from LLM output** — bracket matching (`raw[raw.find("{"):raw.rfind("}")+1]`) handles Claude wrapping JSON in markdown fences. Simple, robust, teachable.

3. **Parallel fan-out / serial synthesis** — ThreadPoolExecutor for search + fetch (I/O bound), then serial LLM synthesis (needs full context). Cut wall-clock time vs. serial fetching by ~4x.

4. **Content extraction heuristic** — stripping nav/footer/script tags and keeping `<p>/<li>/<h>` with ≥40 chars works on the vast majority of news and blog pages without needing Readability.js or a headless browser.

5. **Report ID stability** — `md5(topic + timestamp)[:8]` as report ID lets the dashboard route by ID even as the filename prefix changes (date + topic slug).

---

## What Didn't Work / Tradeoffs

1. **Some sites block scrapers** — paywalled content (WSJ, FT, Bloomberg) returns login walls. The pipeline handles this gracefully (empty content string, source still cited), but the synthesis has less to work with. Mitigation: use Brave's search snippets as the fallback for blocked URLs.

2. **DDG rate limits** — aggressive batch searches (>10 queries quickly) can trigger DDG's rate limiter. Fixed with: sleep 1s between queries when no Brave key. For production: add jitter or Brave API key.

3. **LLM JSON parsing reliability** — Haiku occasionally returns malformed JSON (missing closing brace). Added try/except with fallback to template synthesis. A stronger prompt or response_format=json would eliminate this.

4. **No async** — Used ThreadPoolExecutor instead of `asyncio`. Simpler to teach and debug; acceptable for <20 URLs. For production scale, switch to `aiohttp` + `asyncio`.

---

## What a Recruiter Should Notice

1. **Production patterns** — fan-out/fan-in parallelism, graceful degradation with fallback chain, defensive JSON parsing, structured logging. This is how you build real pipelines.

2. **OpenClaw fluency** — `openclaw_demo.py` shows I understand the tool abstraction layer. The Python service isn't just a script; it's a documented translation of how OpenClaw's web agent tools work internally.

3. **Teachable architecture** — Clear class structure (`ResearchAgent`), single-responsibility functions, documented assumptions. This is code you can Loom-record and explain to someone learning from scratch.

4. **End-to-end** — Research engine + dashboard + CLI + config + tutorial bridge. Not a half-finished script — a shippable service.

5. **Finance-relevant use case** — Point this at "BlackRock Q4 earnings analyst reactions" or "Fed rate decision market impact" and you have a tool a buy-side analyst would actually pay for.

---

## Key Lessons

- **Query decomposition is the secret weapon.** Searching "AI regulation" returns noise. Searching "EU AI Act fines enforcement 2025" returns gold. The LLM decomposition step is where most of the research quality comes from.
- **Prompt for JSON, parse defensively.** Don't trust the LLM to always return valid JSON even if you ask nicely. Always extract the JSON substring, wrap in try/except, fall back to template.
- **Parallelism has a natural boundary here.** Search and fetch are I/O bound → parallelize. Synthesis needs the full context window → serialize. Respecting this boundary keeps the code simple and correct.

---

## Extend This

- Add `--discord` flag to post the report to Discord on completion
- Plug in Brave News API for fresher results (different endpoint)
- Add cron scheduling (copy pattern from Forge #3 Pulse)
- Build a "research briefing" skill: wraps this as an OpenClaw SKILL.md
- Add embedding + vector search over the `reports/` directory (connects to Forge Category 7: persistent memory)
