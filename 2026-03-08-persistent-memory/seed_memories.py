"""
seed_memories.py — Demo memory dataset for Mnemosyne.

These memories represent a realistic user profile for a finance professional
pivoting into AI implementation work. They're designed to:
  1. Show meaningful retrieval (varied topics, realistic importance weights)
  2. Demonstrate the tagging system
  3. Make demo conversations actually interesting (not just "user likes pizza")

Run as a script to populate the DB directly:
    python seed_memories.py

Or via API:
    curl -X POST http://localhost:5000/api/seed
"""

SEED_MEMORIES = [
    # ── Identity & Professional Context ────────────────────────────────────
    {
        "content": "User is Luke Stephens, VP at BlackRock in Transition Management. CFA charterholder with Series 7, 63, and 3 licenses.",
        "tags": ["identity", "finance", "career"],
        "source": "user",
        "importance": 9,
    },
    {
        "content": "Luke is actively building an OpenClaw portfolio to transition into AI implementation roles. Target: Automation Engineer at funded AI startups ($165-195k range).",
        "tags": ["career", "goals", "ai"],
        "source": "user",
        "importance": 9,
    },
    {
        "content": "Luke has real Python skills from prior roles: built Bloomberg API PnL dashboard at BlackRock, ran 30+ automation projects at Western Asset Management using Python and SQL.",
        "tags": ["skills", "python", "career"],
        "source": "user",
        "importance": 8,
    },
    {
        "content": "Luke completed his MBA at UVA Darden (top-10 program) and a BS in Business from USC.",
        "tags": ["education", "identity"],
        "source": "user",
        "importance": 6,
    },

    # ── Preferences & Working Style ─────────────────────────────────────────
    {
        "content": "Luke prefers information structured as tables and bullet points with metrics first, narrative second. Walls of text are a turn-off.",
        "tags": ["preference", "communication"],
        "source": "user",
        "importance": 8,
    },
    {
        "content": "Luke favors dark mode UIs — all dashboards and tools should default to dark theme.",
        "tags": ["preference", "ui"],
        "source": "agent",
        "importance": 6,
    },
    {
        "content": "Luke is in the America/New_York timezone (EST). Important for scheduling cron jobs and time-sensitive alerts.",
        "tags": ["preference", "timezone", "system"],
        "source": "system",
        "importance": 7,
    },
    {
        "content": "Luke's communication style preference: direct, dry humor appreciated, no filler words or sycophantic openers. Gets to the point.",
        "tags": ["preference", "communication"],
        "source": "user",
        "importance": 8,
    },

    # ── Health & Personal ───────────────────────────────────────────────────
    {
        "content": "Luke is training for a half marathon in April 2026 and is considering a full marathon in November 2026. Runs on Garmin, tracks on Strava.",
        "tags": ["health", "personal", "running"],
        "source": "user",
        "importance": 6,
    },
    {
        "content": "Luke lifts weights, prioritizes sleep, and eats well. Health is a priority, not just fitness.",
        "tags": ["health", "personal"],
        "source": "user",
        "importance": 5,
    },

    # ── Technical Projects ──────────────────────────────────────────────────
    {
        "content": "The OpenClaw Forge is Luke's nightly portfolio builder — one production-quality demo per night, rotating through 10 portfolio categories.",
        "tags": ["project", "ai", "openclaw"],
        "source": "agent",
        "importance": 8,
    },
    {
        "content": "Luke uses OpenClaw (AI automation platform) with Claude as the primary model. Gateway runs on a Mac Mini. Agent workspace is at /workspace.",
        "tags": ["system", "openclaw", "infrastructure"],
        "source": "system",
        "importance": 7,
    },
    {
        "content": "Luke has a Discord server for his AI portfolio showcase. Channel 1477502144612667544 is the forge build announcements channel.",
        "tags": ["discord", "system", "openclaw"],
        "source": "system",
        "importance": 6,
    },
    {
        "content": "Previous Forge builds: multi-agent orchestration (fan-out/fan-in), alert dispatcher (Flask + Discord routing), cron market briefing (Pulse), web research agent (Sage), finsnap skill (ClawHub-ready), Iris portfolio dashboard.",
        "tags": ["project", "openclaw", "portfolio"],
        "source": "agent",
        "importance": 7,
    },

    # ── Work Context ────────────────────────────────────────────────────────
    {
        "content": "BlackRock pays Luke approximately $150k base + $25k+ bonus for ~40 hours/week with low stress. The bar for leaving is high.",
        "tags": ["career", "finance"],
        "source": "user",
        "importance": 5,
    },
    {
        "content": "Luke's work tools are Microsoft 365 suite — no AI access in the work environment. All AI work happens in his personal OpenClaw setup.",
        "tags": ["work", "tools"],
        "source": "user",
        "importance": 5,
    },

    # ── Interests ───────────────────────────────────────────────────────────
    {
        "content": "Luke's interests include sports, video games (Mario, Pokémon), Harry Potter, and reading. Self-described huge nerd with a soft heart.",
        "tags": ["personal", "interests"],
        "source": "user",
        "importance": 4,
    },
    {
        "content": "Luke uses Gmail, X (Twitter), Strava, Garmin, Copilot (money manager), ESPN, and Habitify as his daily personal tools.",
        "tags": ["tools", "personal"],
        "source": "user",
        "importance": 4,
    },
]


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__file__))
    import memory_store

    memory_store.init_db()
    print(f"Seeding {len(SEED_MEMORIES)} memories...")
    for m in SEED_MEMORIES:
        added = memory_store.add_memory(
            content=m["content"],
            tags=m.get("tags", []),
            source=m.get("source", "seed"),
            importance=m.get("importance", 5),
        )
        print(f"  ✅ [{added['importance']:2d}] {added['content'][:70]}...")
    print(f"\nDone. {len(SEED_MEMORIES)} memories stored in mnemosyne.db")
