# 🔍 Automated Web Research Agent

**OpenClaw Forge — Build #4 | Category: Automated Web Research Agent**  
*2026-03-05 | Luke Stephens*

---

## What It Does

Autonomous research pipeline that takes any topic and produces a structured intelligence report:

```
Topic → Decompose → Parallel Search → Extract → Synthesize → Report
```

1. **Query decomposition** — LLM breaks a broad topic into N focused sub-questions
2. **Parallel web search** — Brave Search API (or DuckDuckGo fallback, no key needed)  
3. **Parallel content extraction** — fetches URLs, strips noise, extracts signal  
4. **Cross-source synthesis** — Claude assembles findings, cites sources, flags conflicts  
5. **Structured output** — JSON + Markdown report saved to `reports/`  
6. **Flask dashboard** — Browse and read reports at `http://localhost:5001`

Works with or without API keys. Degrades gracefully at every step.

---

## OpenClaw Concepts Demonstrated

| Concept | Where |
|---|---|
| Autonomous reasoning loop | `research_agent.py` → `ResearchAgent.research()` |
| Parallel tool invocation (fan-out/fan-in) | `parallel_search()` + `parallel_extract()` via `ThreadPoolExecutor` |
| Structured LLM output | `synthesize_llm()` — asks Claude for JSON, parses defensively |
| Graceful degradation | LLM → template fallback; Brave → DDG fallback |
| Query decomposition | `decompose_topic_llm()` — broad topic → focused sub-questions |
| Tool mapping | `openclaw_demo.py` — shows exact OpenClaw tool call equivalents |

See `openclaw_demo.py` for a side-by-side comparison of how each step maps to `web_search`, `web_fetch`, and LLM tool calls in the OpenClaw framework.

---

## How to Run

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set API keys (optional)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # Enables LLM synthesis
export BRAVE_API_KEY="BSA..."           # Enables Brave search (DDG used if absent)
```

### 3. Run a research job

```bash
# Basic
python research_agent.py "AI regulation in Europe"

# More depth (6 sub-questions)
python research_agent.py "prompt injection attacks" --depth 6

# Fully offline (no API calls)  
python research_agent.py "LLM benchmarks 2025" --no-llm

# Custom output directory
python research_agent.py "quantum computing breakthroughs" --output /tmp/reports
```

### 4. Launch the dashboard

```bash
cd dashboard && python app.py
# Open http://localhost:5001
```

---

## Project Structure

```
2026-03-05-web-research-agent/
├── research_agent.py       # Main agent — full pipeline
├── openclaw_demo.py        # OpenClaw mapping reference + tutorial hooks
├── config.yaml             # Configuration defaults
├── requirements.txt        # Python dependencies
├── dashboard/
│   ├── app.py              # Flask report browser
│   └── templates/
│       ├── index.html      # Report list (dark theme)
│       └── report.html     # Single report view (sidebar + tabs)
├── reports/                # Generated reports (gitignored)
├── README.md               # This file
└── BUILD_SUMMARY.md        # Build notes for portfolio
```

---

## Configuration

Edit `config.yaml` or set env vars:

| Setting | Default | Description |
|---|---|---|
| `depth` | 4 | Number of sub-questions to generate |
| `results_per_query` | 3 | Search results per sub-question |
| `llm_model` | `claude-3-5-haiku-20241022` | Model for decompose + synthesize |
| `fetch_timeout` | 10 | Seconds per URL fetch |

---

## Assumptions Made

1. **Search fallback order** — Brave API (if key provided) → DuckDuckGo (free, no key). This makes the agent runnable in any environment.
2. **Content extraction strategy** — Remove script/style/nav/footer tags, keep `<p>`, `<li>`, `<h2-4>` with ≥40 chars. Simple heuristic that works on 80%+ of news/blog pages.
3. **LLM output parsing** — Ask Claude for JSON, extract JSON substring by bracket matching. This defensive approach handles models that wrap JSON in markdown code fences.
4. **Report storage** — JSON (structured data for integrations) + Markdown (human-readable). No database needed; filesystem is the store.
5. **Parallelism** — ThreadPoolExecutor with 6 workers. `asyncio` would be faster for pure I/O but ThreadPoolExecutor is easier to teach and debug.

---

## Architecture Note

The research loop pattern is **provider-agnostic**:
- OpenClaw executes it via `web_search` + `web_fetch` tool calls
- This Python service executes it via direct API/HTTP calls
- The intelligence lives in the prompts, not the runtime

This means any OpenClaw skill that does research (news monitoring, competitive intelligence, due diligence) is built on this same pattern. Understand this loop and you understand 80% of OpenClaw web agent patterns.
