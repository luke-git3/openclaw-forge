#!/usr/bin/env python3
"""
openclaw_demo.py — How This Maps to OpenClaw
=============================================

This file is the bridge between the standalone research agent and the
OpenClaw tool ecosystem. It shows the SAME research loop, expressed as
OpenClaw tool calls.

The standalone research_agent.py wraps these three OpenClaw patterns:
  1. web_search  → search()
  2. web_fetch   → extract_content()
  3. LLM prompt  → synthesize_llm()

Study both files side-by-side to understand how Python agents translate
to OpenClaw multi-step reasoning chains.

This is the file to reference when teaching this pattern in a tutorial.
"""

# ── OpenClaw-equivalent pseudocode ────────────────────────────────────────────
#
# The research loop in OpenClaw agent YAML would look like:
#
#   tools:
#     - web_search    # Brave/DDG under the hood
#     - web_fetch     # URL → clean text
#
#   reasoning: |
#     1. Break the topic into sub-questions
#     2. For each sub-question: call web_search → collect URLs
#     3. For each URL: call web_fetch → extract content
#     4. Synthesize all content into a structured report
#     5. Save to workspace file
#
#   This is exactly what research_agent.py does — the difference is that
#   OpenClaw handles the tool infrastructure; you just write the reasoning.
# ──────────────────────────────────────────────────────────────────────────────


def demo_openclaw_research_loop(topic: str) -> dict:
    """
    Pseudocode showing the OpenClaw tool call sequence
    that research_agent.py replicates in pure Python.

    In a real OpenClaw skill, these would be tool invocations
    handled by the framework. Here they're documented as a reference.
    """
    steps = []

    # Step 1: Decompose topic (OpenClaw: LLM system prompt call)
    steps.append({
        "step": 1,
        "name": "decompose_topic",
        "openclaw_equivalent": "LLM call with decomposition system prompt",
        "python_equivalent": "decompose_topic_llm() / decompose_topic_template()",
        "input": {"topic": topic},
        "output": f"List of {4} focused sub-questions",
    })

    # Step 2: Web search (OpenClaw: web_search tool)
    steps.append({
        "step": 2,
        "name": "parallel_search",
        "openclaw_equivalent": "web_search(query=sub_question, count=3) × N sub-questions",
        "python_equivalent": "search_brave() / search_ddg() via ThreadPoolExecutor",
        "input": {"sub_questions": 4, "results_per": 3},
        "output": "~12 unique URLs with titles and snippets",
    })

    # Step 3: Web fetch (OpenClaw: web_fetch tool)
    steps.append({
        "step": 3,
        "name": "parallel_extract",
        "openclaw_equivalent": "web_fetch(url=...) × N unique URLs",
        "python_equivalent": "extract_content() via requests + BeautifulSoup, parallel",
        "input": {"urls": "~12 unique URLs"},
        "output": "Clean text blocks, up to 4000 chars per source",
    })

    # Step 4: Synthesize (OpenClaw: LLM call with gathered context)
    steps.append({
        "step": 4,
        "name": "synthesize",
        "openclaw_equivalent": "LLM call with all source content in context window",
        "python_equivalent": "synthesize_llm() — builds prompt with all sources, asks Claude",
        "input": {"sources": "~12 text blocks + topic + sub-questions"},
        "output": "Structured JSON: executive_summary, key_findings, qa_pairs, data_highlights",
    })

    # Step 5: Save (OpenClaw: write tool)
    steps.append({
        "step": 5,
        "name": "save_report",
        "openclaw_equivalent": "write(path='reports/<topic>.md', content=formatted_report)",
        "python_equivalent": "save_report() — writes JSON + Markdown to reports/",
        "input": {"synthesis": "structured dict", "sources": "list of dicts"},
        "output": "reports/<date>_<topic>_<id>.md and .json",
    })

    return {
        "topic": topic,
        "pattern": "Autonomous Research Loop",
        "openclaw_tools_used": ["web_search", "web_fetch", "write", "LLM prompt"],
        "python_equivalent_modules": [
            "search.py (search_brave / search_ddg)",
            "extraction (extract_content via requests+bs4)",
            "synthesis (synthesize_llm via anthropic SDK)",
            "report (format_markdown, save_report)",
        ],
        "steps": steps,
        "key_insight": (
            "The research loop pattern — decompose → search → fetch → synthesize — is "
            "provider-agnostic. OpenClaw executes it via tool calls; Python executes it via "
            "API calls. The intelligence lives in the prompts, not the runtime."
        ),
        "teachable_concepts": [
            "Query decomposition: broad topic → focused sub-questions → better results",
            "Fan-out/fan-in: parallel search/fetch, serial synthesis",
            "Graceful degradation: LLM → template fallback, Brave → DDG fallback",
            "Structured LLM output: ask for JSON, parse defensively",
            "Content extraction: strip noise (nav/footer/scripts), keep signal (p/li tags)",
        ],
    }


if __name__ == "__main__":
    import json
    result = demo_openclaw_research_loop("AI agent frameworks comparison 2025")
    print(json.dumps(result, indent=2))
    print("\n" + "=" * 60)
    print("KEY INSIGHT:")
    print(result["key_insight"])
    print("\nTEACHABLE CONCEPTS:")
    for concept in result["teachable_concepts"]:
        print(f"  • {concept}")
