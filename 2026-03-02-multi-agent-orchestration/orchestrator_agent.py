"""
orchestrator_agent.py — The OpenClaw Agent Task

This is the script that runs INSIDE an OpenClaw agent session.
It uses OpenClaw's tool-calling interface (sessions_spawn, sessions_history)
to actually spawn sub-agents and collect results.

Usage (as an OpenClaw agent task):
  Pass this file's content as the task to sessions_spawn with runtime="subagent"
  OR run it as a standalone orchestrator session.

OpenClaw Tools Used:
  - sessions_spawn(task, runtime="subagent", runTimeoutSeconds=180)
  - sessions_history(sessionKey) to retrieve sub-agent output
  - write (to save results)
  - message (to notify Discord on completion)

This file is the "teaching version" — heavily commented so readers can
understand each orchestration step and adapt it for their own use cases.
"""

# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATION PATTERN: Fan-Out / Fan-In
#
# Fan-Out:  Coordinator spawns N sub-agents simultaneously (non-blocking).
#           Each sub-agent is isolated, has its own context, and works independently.
#
# Fan-In:   After all sub-agents complete (or timeout), coordinator collects
#           their outputs and synthesizes a unified result.
#
# Why use this pattern?
#   - Parallelism: 4 research tasks that each take 60s now take ~60s total, not 240s
#   - Isolation: one sub-agent crashing doesn't kill the others
#   - Specialization: each agent can be tuned (prompt, model, tools) for its task
#   - Observability: each sub-agent has its own session history for debugging
# ─────────────────────────────────────────────────────────────────────────────

ORCHESTRATOR_TASK = """
You are a multi-agent research coordinator. Your job:

1. SPAWN 4 sub-agents in parallel using sessions_spawn (runtime="subagent").
   Each sub-agent researches one angle of the topic: "AI automation platforms for enterprise"

   Sub-agent tasks (spawn all 4 before waiting for any):

   SUB-AGENT 1 — Market Size:
   Research the market size and CAGR for AI automation platforms for enterprise.
   Use web_search and web_fetch. Write results as JSON to:
   /workspace/forge/2026-03-02-multi-agent-orchestration/result_market_size.json
   JSON keys: market_size_usd, cagr_percent, year_range, top_sources, key_findings
   Reply DONE:market_size when finished.

   SUB-AGENT 2 — Competitors:
   Identify top 5 enterprise AI automation platforms.
   Use web_search and web_fetch. Write results as JSON to:
   /workspace/forge/2026-03-02-multi-agent-orchestration/result_competitors.json
   JSON key: competitors (list: name, positioning, funding_or_revenue, differentiator)
   Reply DONE:competitors when finished.

   SUB-AGENT 3 — Trends:
   Find 3 major trends in enterprise AI automation for 2025-2026.
   Use web_search and web_fetch. Write results as JSON to:
   /workspace/forge/2026-03-02-multi-agent-orchestration/result_trends.json
   JSON key: trends (list: title, description, evidence_url)
   Reply DONE:trends when finished.

   SUB-AGENT 4 — Use Cases:
   Find top enterprise use cases for AI automation with ROI evidence.
   Use web_search and web_fetch. Write results as JSON to:
   /workspace/forge/2026-03-02-multi-agent-orchestration/result_use_cases.json
   JSON key: use_cases (list: use_case, industry, roi_claim, example_company)
   Reply DONE:use_cases when finished.

2. After spawning all 4, wait for them to complete (poll sessions_history every 15s).
   Timeout: 180 seconds per sub-agent. If one times out, note it and continue.

3. Run: python3 /workspace/forge/2026-03-02-multi-agent-orchestration/coordinator.py
   This synthesizes all result files into final_report.md.

4. Read the final_report.md and send a Discord message to channel:1477502144612667544
   with the report summary (first 1500 chars if long).

5. Write a status file to:
   /workspace/forge/2026-03-02-multi-agent-orchestration/run_status.json
   with: { "status": "complete", "agents_succeeded": N, "agents_failed": N, "timestamp": "..." }
"""

# This file documents the agent task but also serves as the authoritative
# reference for how to structure a fan-out orchestration in OpenClaw.
# To run this for real:
#   1. Open an OpenClaw session
#   2. Paste ORCHESTRATOR_TASK as your message (or use sessions_spawn with it as the task)
#   3. Watch the coordinator spawn 4 sub-agents and synthesize results

if __name__ == "__main__":
    print("Orchestrator Agent Task:")
    print("=" * 60)
    print(ORCHESTRATOR_TASK)
    print()
    print("To execute: paste the task above into an OpenClaw session,")
    print("or use sessions_spawn(task=ORCHESTRATOR_TASK, runtime='subagent')")
