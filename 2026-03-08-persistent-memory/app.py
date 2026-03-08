"""
app.py — Mnemosyne Flask API + static dashboard server.

Endpoints:
  GET  /                          → dashboard HTML
  GET  /api/memories              → list all memories (optional ?tag=)
  POST /api/memories              → add a new memory
  DELETE /api/memories/<id>       → delete a memory
  GET  /api/search?q=<query>      → semantic search, returns ranked memories + context block
  POST /api/chat                  → stateful agent chat (memory-injected LLM response)
  GET  /api/stats                 → memory store statistics
  POST /api/seed                  → seed demo memories (for demos/testing)

OpenClaw Integration Pattern:
  - /api/search maps directly to memory_search() tool behavior
  - /api/chat demonstrates the inject-then-generate pattern
  - The context block format mirrors OpenClaw's MEMORY CONTEXT injection
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import memory_store
import context_injector

app = Flask(__name__)

# ─── Initialize DB on startup ─────────────────────────────────────────────────
memory_store.init_db()


# ─── HTML Dashboard ───────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("index.html")


# ─── Memory CRUD ──────────────────────────────────────────────────────────────

@app.route("/api/memories", methods=["GET"])
def list_memories():
    tag = request.args.get("tag")
    memories = memory_store.get_all_memories(tag_filter=tag)
    return jsonify({"memories": memories, "count": len(memories)})


@app.route("/api/memories", methods=["POST"])
def add_memory():
    data = request.get_json(force=True)
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "content is required"}), 400

    tags = data.get("tags", [])
    if isinstance(tags, str):
        # Accept comma-separated string from simple form posts
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    memory = memory_store.add_memory(
        content=content,
        tags=tags,
        source=data.get("source", "user"),
        importance=int(data.get("importance", 5)),
    )
    return jsonify({"memory": memory}), 201


@app.route("/api/memories/<memory_id>", methods=["DELETE"])
def delete_memory(memory_id: str):
    deleted = memory_store.delete_memory(memory_id)
    if not deleted:
        return jsonify({"error": "memory not found"}), 404
    return jsonify({"deleted": memory_id})


# ─── Semantic Search ──────────────────────────────────────────────────────────

@app.route("/api/search", methods=["GET"])
def search_memories():
    """
    Semantic search over stored memories.
    Returns ranked results + the formatted context block for LLM injection.

    This is the memory_search() tool equivalent in OpenClaw.
    """
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "q parameter required"}), 400

    top_k = int(request.args.get("top_k", 5))
    tag_filter = request.args.get("tag") or None
    min_score = float(request.args.get("min_score", 0.01))

    retrieved, context_block = context_injector.retrieve_context(
        query=query,
        top_k=top_k,
        tag_filter=tag_filter,
        min_score=min_score,
    )

    return jsonify({
        "query": query,
        "results": retrieved,
        "count": len(retrieved),
        "context_block": context_block,  # Ready to inject into any LLM prompt
    })


# ─── Stateful Agent Chat ──────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Memory-injected agent chat endpoint.

    Flow:
      1. Receive user message
      2. Retrieve relevant memories via semantic search
      3. Build injected prompt (system + memory context + user message)
      4. Send to LLM (Claude via Anthropic SDK, or template fallback)
      5. Optionally extract and store new facts from the response
      6. Return: LLM response + memories used + injected prompt

    This demonstrates the core OpenClaw stateful agent pattern.
    """
    data = request.get_json(force=True)
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    top_k = int(data.get("top_k", 5))

    # Step 1: Retrieve relevant memories
    retrieved, context_block = context_injector.retrieve_context(
        query=message,
        top_k=top_k,
    )

    # Step 2: Build injected system prompt
    system_prompt = (
        "You are a helpful AI assistant with access to a persistent memory store. "
        "You remember facts about the user across sessions — preferences, context, history. "
        "Use the provided memory context to give personalized, informed responses."
    )
    injected_prompt = context_injector.build_injected_prompt(
        system_prompt=system_prompt,
        query=message,
        context_block=context_block,
    )

    # Step 3: Generate response (Claude or template fallback)
    response_text, model_used = _generate_response(message, injected_prompt)

    return jsonify({
        "message": message,
        "response": response_text,
        "model": model_used,
        "memories_used": retrieved,
        "memory_count": len(retrieved),
        "injected_prompt": injected_prompt,  # Visible in dashboard for learning
    })


def _generate_response(user_message: str, injected_prompt: str) -> tuple[str, str]:
    """
    Try Anthropic Claude, fall back to intelligent template response.
    Returns (response_text, model_name).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            result = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1024,
                messages=[{"role": "user", "content": injected_prompt}],
            )
            return result.content[0].text, "claude-3-5-haiku-20241022"
        except Exception as e:
            app.logger.warning(f"Anthropic API error, using fallback: {e}")

    # Template fallback — demonstrates the pipeline even without an API key
    template_response = _template_response(user_message, injected_prompt)
    return template_response, "template-fallback"


def _template_response(message: str, injected_prompt: str) -> str:
    """
    Simulated intelligent response for demo/testing without an API key.
    Parses the injected prompt to surface retrieved memories in the response.
    """
    # Extract memory lines from the context block
    lines = injected_prompt.split("\n")
    memory_lines = []
    in_context = False
    for line in lines:
        if "[MEMORY CONTEXT]" in line:
            in_context = True
            continue
        if "[END MEMORY CONTEXT]" in line:
            in_context = False
            continue
        if in_context and line.strip() and line[0].isdigit():
            # Numbered memory line
            content = re.sub(r"^\d+\.\s*\[.*?\]\s*", "", line).strip()
            if content:
                memory_lines.append(content)

    if memory_lines:
        memories_text = "\n".join(f"  • {m}" for m in memory_lines[:3])
        return (
            f"[Template response — set ANTHROPIC_API_KEY for live LLM]\n\n"
            f"Based on your question '{message}', I found {len(memory_lines)} relevant memory/memories:\n\n"
            f"{memories_text}\n\n"
            f"With a live LLM, these would be woven naturally into a personalized response. "
            f"The memory injection pipeline is working correctly — memories retrieved, context built, "
            f"prompt assembled. Only the final generation step needs an API key."
        )
    else:
        return (
            f"[Template response — set ANTHROPIC_API_KEY for live LLM]\n\n"
            f"No strongly relevant memories found for '{message}'. "
            f"Try adding some memories first via the dashboard or POST /api/memories."
        )


# ─── Stats & Utilities ────────────────────────────────────────────────────────

@app.route("/api/stats", methods=["GET"])
def stats():
    return jsonify(memory_store.get_stats())


@app.route("/api/seed", methods=["POST"])
def seed():
    """Load demo memories for portfolio demos and testing."""
    from seed_memories import SEED_MEMORIES
    added = []
    for m in SEED_MEMORIES:
        memory = memory_store.add_memory(
            content=m["content"],
            tags=m.get("tags", []),
            source=m.get("source", "seed"),
            importance=m.get("importance", 5),
        )
        added.append(memory)
    return jsonify({"seeded": len(added), "memories": added}), 201


# ─── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🧠 Mnemosyne — Persistent Memory Agent")
    print(f"   Dashboard:  http://localhost:{port}/")
    print(f"   API docs:   http://localhost:{port}/api/stats")
    print(f"   Seed data:  curl -X POST http://localhost:{port}/api/seed")
    print(f"   ANTHROPIC_API_KEY: {'✅ set' if os.environ.get('ANTHROPIC_API_KEY') else '⚠️  not set (template fallback active)'}\n")
    app.run(debug=True, port=port)
