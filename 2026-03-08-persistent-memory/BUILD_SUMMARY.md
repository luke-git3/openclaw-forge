# BUILD SUMMARY — Mnemosyne
**Date:** 2026-03-08  
**Category:** Persistent Memory & Context Injection  
**Status:** ✅ Working Prototype  
**Build time:** ~75 min

---

## What Was Built

A full persistent memory agent system with four decoupled components:

1. **`memory_store.py`** — SQLite layer. Pure CRUD, no intelligence. Importance (1-10), source tagging, access tracking, tag-based filtering. Clean separation means you can swap SQLite for Postgres without touching anything else.

2. **`embedder.py`** — TF-IDF semantic search engine written from scratch (no sklearn). Custom stopword removal, L2-normalized sparse vectors, cosine similarity with importance + recency blending. Includes a complete upgrade path to `sentence-transformers` — identical interface, drop-in swap.

3. **`context_injector.py`** — The pipeline that converts retrieved memories into an LLM-ready `[MEMORY CONTEXT]` block, then assembles the full injected prompt. This is the single most important file: it's the pattern that makes agents stateful.

4. **`app.py`** — Flask REST API with 8 endpoints. Claude integration with template fallback. The `/api/chat` endpoint exposes `injected_prompt` in the response — this transparency is what makes the dashboard a teaching tool, not just a demo.

5. **`templates/index.html`** — 500-line dark-mode dashboard. Three tabs: semantic search with scored result cards + context block viewer, memory-injected chat with inline prompt inspector, memory add form with importance guide.

6. **`openclaw_agent.py`** — Explicit OpenClaw tool mapping. Shows which tool calls Mnemosyne replaces (`memory_search` → `/api/search`, `memory_get` → `/api/memories/<id>`, context injection → `build_injected_prompt()`). Runs standalone as a pipeline demo.

7. **`seed_memories.py`** — 18 realistic demo memories drawn from Luke's actual profile: identity, career goals, Python skills, OpenClaw projects, preferences, health goals, daily tools. Makes every demo conversation meaningful, not generic.

---

## What Worked

- **TF-IDF from scratch works well for factual memory.** Cosine similarity on user preferences and factual statements is surprisingly effective. The importance + recency blend (0.7 / 0.25 / 0.05) produces good retrieval without needing embeddings.
- **The `injected_prompt` in the API response is the killer feature.** Showing the user exactly what was sent to the LLM makes this educational. You can see memory retrieval fail gracefully (score too low → falls below threshold → context block says "no relevant memories").
- **Decoupled layers compose cleanly.** `memory_store` → `embedder` → `context_injector` → `app` — each layer has one job. The test for "did you get the architecture right" is: can you swap the search engine? Yes — 30 lines in `embedder.py`, zero changes elsewhere.
- **Template fallback makes demos reliable.** Without `ANTHROPIC_API_KEY`, the pipeline still runs and shows retrieved memories and the assembled prompt. Hiring managers can see the full flow without needing a key.

## What Didn't Work / Trade-offs

- **TF-IDF can't handle semantic synonyms.** "Running goals" won't retrieve a memory about "half marathon training" unless both phrases appear. Sentence-transformers solve this — the upgrade path is documented. This is an intentional trade-off for portability, not an oversight.
- **Index rebuild per request.** For portfolios / demos this is fine (~2ms for 18 memories). At scale (>10k memories), cache the index or move to a vector DB. Noted in the README upgrade table.
- **No auto write-back.** The agent doesn't extract new facts from conversations and store them automatically. That would require a second LLM call (classify + extract) on every response. Left out to keep the architecture legible — it's the obvious next feature.

---

## What a Recruiter Should Notice

1. **Architecture maturity.** Four decoupled layers with clean interfaces. A recruiter reading this code sees someone who thinks in systems, not scripts.
2. **TF-IDF from scratch.** Implementing cosine similarity over sparse vectors without reaching for sklearn demonstrates comfort with the underlying math — relevant for roles that require debugging embedding pipelines.
3. **The OpenClaw mapping.** `openclaw_agent.py` explicitly maps Python functions to OpenClaw tool calls. This proves framework-native thinking, not just "I can write Python."
4. **The teaching layer.** The dashboard shows the injected prompt. The upgrade path is documented inline. This is the work of someone who builds for others to learn from — directly relevant to the AI educator track.
5. **Production awareness.** The README has an explicit upgrade table (SQLite → pgvector, TF-IDF → MiniLM, no auth → bearer token). Shows professional engineering judgment, not just "it works on my machine."

---

## Key Lesson

**The context block is the product.** The memory store is plumbing. The semantic search is routing. What matters is the formatted `[MEMORY CONTEXT]` block that lands in the LLM prompt — because that's what makes the response feel like the agent actually knows you. Everything else in Mnemosyne is infrastructure in service of producing that block cleanly, reliably, and with observable scoring.

This is the same lesson as the SKILL.md principle from Forge #5: in OpenClaw, the instruction layer IS the product. The Python is just how you get there.
