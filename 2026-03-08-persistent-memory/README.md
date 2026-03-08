# 🧠 Mnemosyne — Persistent Memory & Context Injection Agent

> **OpenClaw Forge Build #7 · Category: Persistent Memory & Context Injection**  
> Built: 2026-03-08

Mnemosyne is a complete persistent memory system for AI agents — SQLite storage, TF-IDF semantic search, context injection pipeline, and a live dark-mode dashboard. It demonstrates the exact memory pattern that OpenClaw's `memory_search` + `memory_get` tools implement, made visible and teachable as a REST API.

---

## What It Does

```
User message → Semantic search → Retrieve top-k memories
            → Build context block → Inject into LLM prompt
            → Generate personalized response
            → Display injected prompt for learning
```

An agent using Mnemosyne knows things across sessions — preferences, identity, project history, constraints — without fine-tuning the model. It retrieves and injects on every call.

---

## OpenClaw Concepts Demonstrated

| OpenClaw Pattern | Mnemosyne Implementation |
|---|---|
| `memory_search(query)` | `GET /api/search?q=<query>` — TF-IDF semantic ranking |
| `memory_get(path, from, lines)` | `GET /api/memories/<id>` — precise retrieval |
| `[MEMORY CONTEXT]` injection | `context_injector.py` → `build_injected_prompt()` |
| Importance weighting | 1–10 score blended into retrieval rank |
| Recency weighting | `access_count` bump on every retrieval |
| Write-back (`memory/YYYY-MM-DD.md`) | `POST /api/memories` with source tagging |
| `MEMORY.md` curated long-term store | SQLite with `importance >= 7` filter |

The `openclaw_agent.py` file documents this mapping explicitly — it's the tutorial layer.

---

## Architecture

```
mnemosyne/
├── app.py               # Flask API + static server (8 endpoints)
├── memory_store.py      # SQLite CRUD layer (pure storage, no ranking)
├── embedder.py          # TF-IDF semantic search engine + cosine similarity
├── context_injector.py  # Retrieval pipeline + prompt assembly
├── seed_memories.py     # 18 realistic demo memories for Luke's profile
├── openclaw_agent.py    # OpenClaw tool mapping + standalone demo
├── templates/
│   └── index.html       # Dark-mode dashboard (Search / Chat / Add)
└── mnemosyne.db         # SQLite store (created on first run)
```

### Why TF-IDF instead of vector embeddings?

- **Zero API dependencies** — runs fully offline
- **Surprisingly effective** for factual memory retrieval (user prefs, identity, projects)
- **Upgrade path documented in-code** — swap `MemoryIndex` for `SentenceTransformer("all-MiniLM-L6-v2")` with identical interface

---

## How to Run

### Prerequisites
```bash
pip install flask anthropic  # anthropic is optional
```

### Quick start
```bash
cd /workspace/forge/2026-03-08-persistent-memory/

# Option A: Run server (with dashboard)
python app.py

# Open http://localhost:5000
# Click "🌱 Seed Demo" to load 18 demo memories
# Then search, chat, or add memories
```

### Seed demo data
```bash
# Via API (server must be running)
curl -X POST http://localhost:5000/api/seed

# Via script (no server needed)
python seed_memories.py
```

### Standalone pipeline demo (no server)
```bash
python openclaw_agent.py
```

### With live LLM responses
```bash
ANTHROPIC_API_KEY=sk-ant-... python app.py
# Chat tab now uses claude-3-5-haiku-20241022 instead of template fallback
```

---

## API Reference

```
GET  /                          Dashboard HTML
GET  /api/memories              List all memories (?tag= filter)
POST /api/memories              Add memory (content, tags, source, importance)
DEL  /api/memories/<id>         Delete memory
GET  /api/search?q=<query>      Semantic search → ranked results + context block
POST /api/chat                  Memory-injected agent chat
GET  /api/stats                 Store statistics
POST /api/seed                  Load 18 demo memories
```

### Example: semantic search
```bash
curl "http://localhost:5000/api/search?q=career+goals&top_k=3"
```
```json
{
  "query": "career goals",
  "results": [
    {
      "_rank": 1,
      "_score": 0.6234,
      "content": "Luke is actively building an OpenClaw portfolio...",
      "importance": 9,
      "tags": ["career", "goals", "ai"]
    }
  ],
  "context_block": "[MEMORY CONTEXT]\nQuery: career goals\n...[END MEMORY CONTEXT]"
}
```

### Example: memory-injected chat
```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What are my top career goals?"}'
```
```json
{
  "response": "...",
  "model": "claude-3-5-haiku-20241022",
  "memory_count": 3,
  "memories_used": [...],
  "injected_prompt": "[full prompt visible for learning]"
}
```

---

## Assumptions Made

1. **TF-IDF over embeddings** — chosen for zero-dependency portability. The upgrade path to `sentence-transformers` is documented in `embedder.py`.
2. **SQLite over vector DB** — Chroma/Pinecone would be overkill for <10k memories. SQLite with JSON columns handles everything needed.
3. **Importance is explicit** — users assign 1–10 manually. Production improvement: auto-score via LLM classification on ingest.
4. **No auth** — this is a localhost portfolio demo. Add Flask-Login or a bearer token for client deployments.
5. **Index rebuilt per request** — fast enough (<10ms) for <1000 memories. Add Redis/in-memory cache if latency matters.
6. **claude-3-5-haiku** — cheapest Claude model for live responses. Swap to Sonnet for better quality at higher cost.

---

## Production Upgrade Path

| Component | Current | Production |
|---|---|---|
| Search | TF-IDF cosine | `all-MiniLM-L6-v2` embeddings |
| Storage | SQLite | PostgreSQL + pgvector |
| Index cache | None (rebuild per request) | Redis / in-memory LRU |
| Auth | None | Bearer token / API key |
| Write-back | Manual POST | Agent auto-extracts facts on response |
| Scale | <1000 memories | Pinecone / Chroma for millions |
