"""
context_injector.py — The core value-prop of Mnemosyne.

This module converts retrieved memories into a formatted context block
that gets injected into LLM prompts. This is the pattern that makes agents
stateful across sessions without touching the model's weights.

Injection pattern (in a Claude prompt):
    ─────────────────────────────────────
    [MEMORY CONTEXT]
    The following facts were retrieved as relevant to the current query.
    Use them to personalize and inform your response.

    1. [importance: 8] User is a CFA charterholder and VP at BlackRock.
       Source: user | Tags: finance, identity
    2. [importance: 6] User prefers dark mode dashboards.
       Source: agent | Tags: preference, ui
    ...
    [END MEMORY CONTEXT]
    ─────────────────────────────────────

The agent doesn't "know" these facts natively — they're retrieved and injected
fresh on every call. This is how OpenClaw's memory_search + memory_get
pattern works under the hood.
"""

from embedder import MemoryIndex
from memory_store import get_all_memories, record_access
from typing import Optional


def retrieve_context(
    query: str,
    top_k: int = 5,
    tag_filter: Optional[str] = None,
    min_score: float = 0.01,
) -> tuple[list[dict], str]:
    """
    Core retrieval pipeline:
      1. Load all memories from SQLite
      2. Build TF-IDF index (fast, ~5ms for 500 memories)
      3. Rank by semantic similarity + importance
      4. Format as a context block for LLM injection
      5. Record access for recency weighting

    Returns:
        (memories_list, context_string)
        - memories_list: raw retrieved memories (for API response / logging)
        - context_string: formatted block ready to prepend to any LLM prompt
    """
    memories = get_all_memories(tag_filter=tag_filter)

    if not memories:
        return [], _empty_context()

    index = MemoryIndex(memories)
    retrieved = index.search(query, top_k=top_k, tag_filter=tag_filter, min_score=min_score)

    if retrieved:
        record_access([m["id"] for m in retrieved])

    context_block = _format_context(query, retrieved)
    return retrieved, context_block


def _format_context(query: str, memories: list[dict]) -> str:
    """Format retrieved memories as an LLM-ready context block."""
    if not memories:
        return _empty_context()

    lines = [
        "[MEMORY CONTEXT]",
        f"Query: {query}",
        f"Retrieved {len(memories)} relevant memory/memories. Use these to personalize your response.",
        "",
    ]

    for m in memories:
        importance_label = _importance_label(m.get("importance", 5))
        tags_str = ", ".join(m.get("tags", [])) or "none"
        score = m.get("_score", 0)
        lines.append(
            f"{m['_rank']}. [{importance_label}] {m['content']}"
        )
        lines.append(
            f"   Source: {m.get('source', 'unknown')} | Tags: {tags_str} | Relevance: {score:.2f}"
        )
        lines.append("")

    lines.append("[END MEMORY CONTEXT]")
    return "\n".join(lines)


def _empty_context() -> str:
    return "[MEMORY CONTEXT]\nNo relevant memories found.\n[END MEMORY CONTEXT]"


def _importance_label(importance: int) -> str:
    """Convert numeric importance (1-10) to human-readable label."""
    if importance >= 9:
        return "importance: CRITICAL"
    elif importance >= 7:
        return f"importance: HIGH ({importance})"
    elif importance >= 4:
        return f"importance: MEDIUM ({importance})"
    else:
        return f"importance: LOW ({importance})"


def build_injected_prompt(system_prompt: str, query: str, context_block: str) -> str:
    """
    Combine a system prompt, memory context, and user query into a
    fully-assembled prompt ready for any LLM.

    This is the "injection" step — the context block sits between system
    instructions and the user message so the model treats memories as
    authoritative background knowledge.
    """
    return f"""{system_prompt}

{context_block}

User query: {query}

Respond helpfully, using the memory context above to personalize your answer.
If a memory is directly relevant, reference it naturally (don't say "According to memory #2").
If no memories are relevant, answer from general knowledge."""
