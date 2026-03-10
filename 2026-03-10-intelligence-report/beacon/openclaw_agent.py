#!/usr/bin/env python3
"""
Beacon — OpenClaw Agent Bridge
================================
This file maps every stage of the Beacon pipeline to the equivalent
OpenClaw tool call an agent would make.

Think of it as a Rosetta Stone: Python function on the left,
OpenClaw tool call + arguments on the right.

Purpose: teaching material for the Loom video / course module.
Each function documents:
  - What the pipeline does natively (Python)
  - How an OpenClaw agent would do the same thing
  - Why the agent approach is different (async, distributed, event-driven)
"""

# ────────────────────────────────────────────────────────────────────────────
# STAGE 1: COLLECT — Gathering raw articles
# ────────────────────────────────────────────────────────────────────────────

def collect_hackernews_openclaw():
    """
    Python version: urllib.request.urlopen(HN_API_URL)

    OpenClaw equivalent:
        web_fetch("https://hacker-news.firebaseio.com/v0/topstories.json")

    In an OpenClaw agent, web_fetch handles rate limiting, retries,
    and returns structured content without managing HTTP sessions.

    For N stories, you'd spawn sub-agents in parallel:
        sessions_spawn(task="Fetch HN story #{id} and extract title/URL/summary")

    Key difference: OpenClaw agents can parallelize fetches via sessions_spawn
    without threading — the runtime manages concurrency.
    """
    tool = "web_fetch"
    args = {"url": "https://hacker-news.firebaseio.com/v0/topstories.json"}
    return tool, args


def collect_rss_openclaw(feed_url: str):
    """
    Python version: urllib.request.urlopen(feed_url) + xml.etree.ElementTree.parse()

    OpenClaw equivalent:
        web_fetch(feed_url, extractMode="text")

    The agent then passes the raw XML to the LLM for extraction, or
    uses a sessions_spawn to handle each feed independently.

    Pattern: fan-out collection
        parent_agent → sessions_spawn(collect feed 1)
                     → sessions_spawn(collect feed 2)
                     → sessions_spawn(collect feed N)
        All write results to /workspace/beacon/feeds/<name>.json
        Parent reads and merges after all complete.
    """
    tool = "web_fetch"
    args = {"url": feed_url, "extractMode": "text"}
    return tool, args


# ────────────────────────────────────────────────────────────────────────────
# STAGE 2: DEDUPLICATE — Skip previously seen articles
# ────────────────────────────────────────────────────────────────────────────

def deduplicate_openclaw(article_url: str):
    """
    Python version: sqlite3 lookup by url_hash

    OpenClaw equivalent:
        memory_search("article URL: <url>", minScore=0.95)

    The OpenClaw memory system acts as the dedup store.
    High minScore (0.95) ensures we only match exact or near-exact URLs.

    On a miss (new article):
        write("/workspace/beacon/seen/<url_hash>.json", content=article_json)

    This is the OpenClaw-native state persistence pattern:
    instead of a DB, the workspace IS the state store.
    """
    tool = "memory_search"
    args = {"query": f"article URL: {article_url}", "minScore": 0.95}
    return tool, args


# ────────────────────────────────────────────────────────────────────────────
# STAGE 3: SCORE — Relevance scoring vs tracked topics
# ────────────────────────────────────────────────────────────────────────────

def score_articles_openclaw(articles: list, topics: list):
    """
    Python version: TF-IDF scoring loop (see pipeline.py score_articles())

    OpenClaw equivalent: delegate scoring to the LLM directly.

    The agent builds a prompt like:
        "Given these topics: [topics]
         Score each article 0.0-1.0 for relevance.
         Return JSON: [{"url": ..., "score": ..., "matched": [...]}]"

    This trades compute efficiency for simplicity. For <20 articles,
    LLM scoring is more accurate than TF-IDF because it understands
    semantic similarity (e.g., "language model" matches "LLM").

    The hybrid approach: use TF-IDF for fast pre-filtering,
    then LLM for final ranking of the top candidates.

    In OpenClaw, this is just the normal Claude interaction — no special tool.
    The agent IS the scoring function.
    """
    prompt = f"""
    Topics to track: {topics}

    Articles to score (JSON array):
    {articles[:10]}

    For each article, score 0.0-1.0 relevance to the tracked topics.
    Return JSON array: [{{"url": "...", "score": 0.0-1.0, "matched_topics": [...]}}]
    """
    return "llm_call", {"prompt": prompt}


# ────────────────────────────────────────────────────────────────────────────
# STAGE 4: SYNTHESIZE — Generate the intelligence brief
# ────────────────────────────────────────────────────────────────────────────

def synthesize_openclaw(top_articles: list, topics: list):
    """
    Python version: _call_claude() with structured JSON prompt

    OpenClaw equivalent: the agent IS Claude.

    The synthesis step in OpenClaw requires no special tool call because
    the agent's own reasoning IS the synthesis. You structure the context,
    hand it to the agent, and its response IS the report.

    In a multi-agent scenario:
        sessions_spawn(
            task="Synthesize these articles into an intelligence brief: [articles]",
            mode="run"
        )

    The spawned sub-agent returns the report as its completion message.
    The parent writes it to disk and delivers it.

    Key insight: in OpenClaw, synthesis is not a function call — it's a
    session. The agent's output is the artifact.
    """
    tool = "sessions_spawn"
    args = {
        "task": f"""You are an AI intelligence analyst. Topics tracked: {topics}.

Synthesize these articles into a structured brief with:
- Executive summary (3-4 sentences)
- Top 5 signals (title, source, why it matters)
- Emerging trends (topic + evidence)
- Key developments (title, source, URL)

Articles:
{top_articles[:10]}

Write the brief as structured JSON matching this schema:
{{
  "executive_summary": "...",
  "top_signals": [{{"title":"...","source":"...","url":"...","why":"..."}}],
  "emerging_trends": [{{"trend":"...","signal":"..."}}],
  "key_developments": [{{"title":"...","source":"...","url":"..."}}]
}}""",
        "mode": "run",
        "runtime": "subagent"
    }
    return tool, args


# ────────────────────────────────────────────────────────────────────────────
# STAGE 5: DELIVER — Send to Discord
# ────────────────────────────────────────────────────────────────────────────

def deliver_discord_openclaw(report: dict, channel_id: str = "1477502144612667544"):
    """
    Python version: urllib.request.urlopen(DISCORD_WEBHOOK, embed_payload)

    OpenClaw equivalent:
        message(action="send", channel="discord", target=channel_id, message=embed_text)

    The message tool handles authentication, rate limiting, and retry.
    For rich embeds, you build the embed dict and pass via components.

    In practice, an OpenClaw cron job runs this pipeline and calls:
        message(action="send", channel="discord",
                target="channel:1477502144612667544",
                message="🔭 **Beacon Brief — 2026-03-10**\n[full report text]")

    This is the "last mile" — data becomes action.
    """
    embed_text = f"""🔭 **Beacon Intelligence Brief — {report.get('date', 'today')}**

**Topics:** {', '.join(report.get('topics_tracked', [])[:5])}
**Surfaced:** {report.get('articles_surfaced', 0)} articles

{report.get('executive_summary', 'No summary available.')}

**Top Signal:** {report.get('top_signals', [{}])[0].get('title', 'N/A')}"""

    tool = "message"
    args = {
        "action":  "send",
        "channel": "discord",
        "target":  f"channel:{channel_id}",
        "message": embed_text,
    }
    return tool, args


# ────────────────────────────────────────────────────────────────────────────
# SCHEDULED PIPELINE — The cron pattern
# ────────────────────────────────────────────────────────────────────────────

OPENCLAW_CRON_CONFIG = """
# beacon-daily — add to your OpenClaw cron configuration
# Runs every morning at 7:00 AM local time

jobs:
  - name: beacon-daily
    schedule: "0 7 * * *"
    task: |
      Run the Beacon intelligence pipeline:
        1. cd /path/to/beacon && python pipeline.py --deliver
        2. The pipeline collects from HN, RSS feeds, and GitHub Trending
        3. Scores articles against tracked topics
        4. Synthesizes a report via Claude (template fallback if no key)
        5. Delivers to Discord via BEACON_DISCORD_WEBHOOK
      Report any errors to the Discord alert channel.
    env:
      ANTHROPIC_API_KEY: "${ANTHROPIC_API_KEY}"
      BEACON_DISCORD_WEBHOOK: "${BEACON_DISCORD_WEBHOOK}"
"""

# OpenClaw-native alternative: the agent itself is the scheduler.
# Store the cron config in workspace, the runtime reads it.
# No subprocess, no crontab — the agent loop IS the scheduler.

OPENCLAW_NATIVE_CRON = """
# In an OpenClaw deployment, you don't need a cron file.
# The agent can self-schedule via HEARTBEAT.md:

# HEARTBEAT.md:
# Every morning between 7:00-7:30 AM:
#   1. Run Beacon pipeline (web_search + web_fetch collection)
#   2. Use your own synthesis (you ARE Claude)
#   3. Send report to Discord (message tool)
#   4. Write report to /workspace/beacon/reports/YYYY-MM-DD.md

# This is the "agent-native scheduling" pattern:
# the agent's heartbeat loop replaces cron entirely.
"""

# ────────────────────────────────────────────────────────────────────────────
# DEMO: Run the bridge and show the mappings
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("BEACON — OpenClaw Tool Call Mappings")
    print("=" * 60)

    print("\n[1] COLLECT from Hacker News")
    tool, args = collect_hackernews_openclaw()
    print(f"    Tool: {tool}")
    print(f"    Args: {args}")

    print("\n[2] COLLECT from RSS feed")
    tool, args = collect_rss_openclaw("https://techcrunch.com/category/artificial-intelligence/feed/")
    print(f"    Tool: {tool}")
    print(f"    Args: {args}")

    print("\n[3] DEDUPLICATE via memory search")
    tool, args = deduplicate_openclaw("https://example.com/article")
    print(f"    Tool: {tool}")
    print(f"    Args: {args}")

    print("\n[4] SCORE via LLM")
    tool, args = score_articles_openclaw(["article1","article2"], ["AI agents","LLM"])
    print(f"    Tool: {tool}")
    print(f"    Args: (prompt truncated)")

    print("\n[5] SYNTHESIZE via sub-agent session")
    tool, args = synthesize_openclaw([], ["OpenClaw","automation"])
    print(f"    Tool: {tool}")
    print(f"    Mode: {args['mode']} | Runtime: {args['runtime']}")
    print(f"    Task: (truncated)")

    print("\n[6] DELIVER to Discord")
    tool, args = deliver_discord_openclaw({"date": "2026-03-10", "topics_tracked": ["AI"], "articles_surfaced": 12})
    print(f"    Tool: {tool}")
    print(f"    Args: {args}")

    print("\n[CRON CONFIG]")
    print(OPENCLAW_CRON_CONFIG)
    print("\n[AGENT-NATIVE SCHEDULING]")
    print(OPENCLAW_NATIVE_CRON)
