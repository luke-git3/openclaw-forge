"""
openclaw_agent.py — OpenClaw integration bridge for Mnemosyne.

This file documents how Mnemosyne maps to native OpenClaw patterns.
It also provides a standalone demo that runs the memory pipeline
using the same tool calls an OpenClaw agent would make.

═══════════════════════════════════════════════════════════════════
OPENCLAW MEMORY TOOL MAPPING
═══════════════════════════════════════════════════════════════════

OpenClaw Tool          → Mnemosyne Equivalent
─────────────────────────────────────────────────────────────────
memory_search(query)   → GET /api/search?q=<query>
                         Returns: ranked memories + context_block

memory_get(path)       → GET /api/memories/<id>
                         Returns: full memory dict

(no direct equivalent)  → POST /api/memories  (write new memory)
                         OpenClaw writes to MEMORY.md / daily files;
                         Mnemosyne writes structured records to SQLite

context_injector        → build_injected_prompt()
                         Assembles: system_prompt + context_block + query

═══════════════════════════════════════════════════════════════════
OPENCLAW WORKFLOW (from AGENTS.md memory recall section):
═══════════════════════════════════════════════════════════════════

Step 1: memory_search("user's career goals")
  → Returns top snippets with path + line numbers

Step 2: memory_get(path, from=line, lines=N)
  → Pull only needed context to keep token count small

Step 3: Inject into LLM prompt as [MEMORY CONTEXT] block

Step 4: Generate response using injected context

Step 5: (Optional) Write new learnings back to memory files

Mnemosyne automates steps 1–4 as a service, making the pattern
accessible via REST API and demonstrable via the dashboard.

═══════════════════════════════════════════════════════════════════
STANDALONE DEMO
═══════════════════════════════════════════════════════════════════

Run: python openclaw_agent.py
Simulates a stateful agent conversation using Mnemosyne's pipeline.
"""

import sys
from pathlib import Path

# Add project to path when run directly
sys.path.insert(0, str(Path(__file__).parent))

import memory_store
import context_injector


def demo_conversation():
    """
    Demonstrate the memory injection pipeline with 3 sample queries.
    Shows what happens at each step: retrieve → rank → inject → generate.
    """
    print("\n" + "═" * 60)
    print("  MNEMOSYNE — OpenClaw Memory Injection Demo")
    print("═" * 60)

    # Initialize
    memory_store.init_db()
    all_memories = memory_store.get_all_memories()

    if not all_memories:
        print("\n⚠️  No memories found. Run: curl -X POST http://localhost:5000/api/seed")
        print("   Or run: python seed_memories.py\n")
        return

    print(f"\n📦 Memory store: {len(all_memories)} memories loaded\n")

    demo_queries = [
        "What are Luke's career goals in AI?",
        "What is Luke's technical background?",
        "Does Luke have any running or fitness goals?",
    ]

    for i, query in enumerate(demo_queries, 1):
        print(f"\n{'─' * 60}")
        print(f"QUERY {i}: {query}")
        print("─" * 60)

        # Step 1: Retrieve
        retrieved, context_block = context_injector.retrieve_context(
            query=query,
            top_k=3,
        )

        print(f"\n📋 Retrieved {len(retrieved)} memories:")
        for m in retrieved:
            score = m.get('_score', 0)
            imp = m.get('importance', 5)
            print(f"  [{score:.3f}] [imp:{imp}] {m['content'][:80]}…")

        # Step 2: Show context block (what gets injected)
        print(f"\n💉 Injected context block:")
        for line in context_block.split("\n"):
            print(f"   {line}")

        # Step 3: Build full injected prompt
        system = "You are a helpful AI assistant with persistent memory about the user."
        full_prompt = context_injector.build_injected_prompt(
            system_prompt=system,
            query=query,
            context_block=context_block,
        )

        print(f"\n📏 Injected prompt: {len(full_prompt)} chars "
              f"({len(full_prompt) // 4} tokens est.)")
        print(f"\n💡 With ANTHROPIC_API_KEY, this prompt is sent to Claude.")
        print(f"   The response is personalized using {len(retrieved)} memory/memories.")

    print(f"\n{'═' * 60}")
    print("  ✅ Pipeline demo complete. Start the server to use the dashboard:")
    print("     python app.py")
    print("═" * 60 + "\n")


def simulate_openclaw_tools():
    """
    Show exactly what OpenClaw tool calls this pipeline replaces.
    Educational reference for the tutorial/course content.
    """
    print("\n" + "═" * 60)
    print("  OPENCLAW TOOL CALL EQUIVALENT")
    print("═" * 60)

    code = '''
# In an OpenClaw agent, memory retrieval looks like this:

# Step 1: Semantic search
results = memory_search("user career goals")
# → Returns top snippets with path + line numbers

# Step 2: Pull specific context
context = memory_get("memory/MEMORY.md", from=45, lines=20)

# Step 3: The agent injects this into its next LLM call automatically
# (OpenClaw handles injection at the framework level)

# ─── Mnemosyne makes this explicit as a REST API ───────────────
# GET /api/search?q=user+career+goals
# → {"results": [...], "context_block": "[MEMORY CONTEXT]..."}
# POST /api/chat with {"message": "What are my career goals?"}
# → {"response": "...", "memories_used": [...], "injected_prompt": "..."}
# ──────────────────────────────────────────────────────────────
# The injected_prompt field shows EXACTLY what went to the LLM.
# This transparency is what makes Mnemosyne a teaching tool.
'''
    print(code)


if __name__ == "__main__":
    demo_conversation()
    simulate_openclaw_tools()
