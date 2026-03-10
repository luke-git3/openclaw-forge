#!/usr/bin/env python3
"""
Beacon — Scheduled AI Intelligence Report Pipeline
====================================================
Collect → Score → Deduplicate → Synthesize → Deliver

Data sources:
  - Hacker News (official Firebase API — no key needed)
  - Multiple RSS/Atom feeds (TechCrunch, VentureBeat, MIT TR, Ars Technica, The Decoder)
  - GitHub Trending (HTML scrape with graceful fallback)

Pipeline stages:
  1. collect()   — fetch raw articles from all sources
  2. score()     — TF-IDF-style relevance scoring vs tracked topics
  3. dedupe()    — skip articles we've seen before (URL hash)
  4. synthesize()— Claude (Anthropic API) → deterministic template fallback
  5. deliver()   — Discord webhook + SQLite persistence
"""

import os
import sys
import json
import re
import sqlite3
import hashlib
import time
import math
import textwrap
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "beacon.db"

# Default topics seeded on first run (user edits via dashboard)
DEFAULT_TOPICS = [
    "OpenClaw", "AI agent", "LLM", "automation",
    "multi-agent", "Claude", "GPT", "agentic",
    "workflow", "orchestration", "RAG", "prompt engineering",
]

# RSS/Atom feeds to monitor
RSS_FEEDS = [
    ("Hacker News",     "https://news.ycombinator.com/rss"),
    ("TechCrunch AI",   "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("VentureBeat AI",  "https://venturebeat.com/category/ai/feed/"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("The Decoder",     "https://the-decoder.com/feed/"),
    ("Ars Technica",    "https://feeds.arstechnica.com/arstechnica/index"),
]

# HackerNews: fetch top N stories
HN_TOP_N = 30

ANTHROPIC_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")
DISCORD_WEBHOOK  = os.environ.get("BEACON_DISCORD_WEBHOOK", "")

# Relevance threshold: only surface articles scoring above this
SCORE_THRESHOLD  = 0.05

# Max articles to surface per run
MAX_SURFACED     = 15

# Window for "new" articles (skip things published > N hours ago)
RECENCY_HOURS    = 48

# ── Database helpers ──────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    """Return an open DB connection, initializing schema on first use."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    schema = (BASE_DIR / "schema.sql").read_text()
    conn.executescript(schema)
    conn.commit()
    return conn


def seed_default_topics(conn: sqlite3.Connection) -> None:
    """Insert default topics if the table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
    if count == 0:
        now = datetime.now(timezone.utc).isoformat()
        for term in DEFAULT_TOPICS:
            conn.execute(
                "INSERT OR IGNORE INTO topics (term, active, created_at) VALUES (?,1,?)",
                (term, now)
            )
        conn.commit()
        print(f"[beacon] Seeded {len(DEFAULT_TOPICS)} default topics.")


def get_active_topics(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT term FROM topics WHERE active=1").fetchall()
    return [r["term"] for r in rows]

# ── Collection ────────────────────────────────────────────────────────────────

def _fetch_url(url: str, timeout: int = 10) -> str | None:
    """GET a URL and return text content, None on failure."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Beacon/1.0 Intelligence Pipeline (OpenClaw demo)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"[beacon] Fetch failed {url}: {exc}")
        return None


def _normalize_url(url: str) -> str:
    """Strip tracking params + fragments for dedup key."""
    try:
        parsed = urllib.parse.urlparse(url)
        # Drop common tracking params
        qs = urllib.parse.parse_qs(parsed.query)
        clean = {k: v for k, v in qs.items() if k not in ("utm_source","utm_medium","utm_campaign","ref","source")}
        new_query = urllib.parse.urlencode(clean, doseq=True)
        cleaned = parsed._replace(query=new_query, fragment="").geturl()
        return cleaned.rstrip("/")
    except Exception:
        return url.rstrip("/")


def _url_hash(url: str) -> str:
    return hashlib.sha256(_normalize_url(url).encode()).hexdigest()[:16]


def collect_hackernews() -> list[dict]:
    """Fetch top HN stories via the official Firebase REST API."""
    articles = []
    top_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
    raw = _fetch_url(top_url)
    if not raw:
        return articles

    try:
        ids = json.loads(raw)[:HN_TOP_N]
    except json.JSONDecodeError:
        return articles

    for story_id in ids:
        item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
        item_raw = _fetch_url(item_url)
        if not item_raw:
            continue
        try:
            item = json.loads(item_raw)
        except json.JSONDecodeError:
            continue

        if item.get("type") != "story" or not item.get("url"):
            continue

        # Convert Unix timestamp → ISO8601
        ts = item.get("time", 0)
        pub = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else None

        articles.append({
            "url":       item["url"],
            "title":     item.get("title", ""),
            "summary":   item.get("text", "")[:500] if item.get("text") else "",
            "source":    "Hacker News",
            "published": pub,
        })

    print(f"[beacon] HackerNews: {len(articles)} stories fetched")
    return articles


def _parse_rss(xml_text: str, source_name: str) -> list[dict]:
    """Parse RSS 2.0 or Atom feed, return list of article dicts."""
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        print(f"[beacon] XML parse error ({source_name}): {exc}")
        return articles

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # Detect feed format
    if root.tag == "rss" or root.tag.endswith("}rss"):
        # RSS 2.0
        for item in root.iter("item"):
            def _get(tag):
                el = item.find(tag)
                return (el.text or "").strip() if el is not None else ""

            url   = _get("link") or _get("guid")
            title = _get("title")
            desc  = re.sub(r"<[^>]+>", "", _get("description"))[:500]
            pub   = _get("pubDate")

            if url and title:
                articles.append({"url": url, "title": title, "summary": desc,
                                  "source": source_name, "published": pub})
    else:
        # Atom
        for entry in root.findall("atom:entry", ns) + root.findall("entry"):
            def _get_atom(tag):
                el = entry.find(f"atom:{tag}", ns) or entry.find(tag)
                return (el.text or "").strip() if el is not None else ""

            # link href
            link_el = entry.find("atom:link[@rel='alternate']", ns) or entry.find("link")
            url = ""
            if link_el is not None:
                url = link_el.get("href", "") or (link_el.text or "")

            title   = _get_atom("title")
            summary = re.sub(r"<[^>]+>", "", _get_atom("summary") or _get_atom("content"))[:500]
            pub     = _get_atom("published") or _get_atom("updated")

            if url and title:
                articles.append({"url": url, "title": title, "summary": summary,
                                  "source": source_name, "published": pub})

    return articles


def collect_rss() -> list[dict]:
    """Fetch and parse all configured RSS feeds."""
    all_articles = []
    for name, url in RSS_FEEDS:
        raw = _fetch_url(url)
        if raw:
            items = _parse_rss(raw, name)
            print(f"[beacon] RSS {name}: {len(items)} items")
            all_articles.extend(items)
        else:
            print(f"[beacon] RSS {name}: fetch failed, skipping")
    return all_articles


def collect_github_trending() -> list[dict]:
    """
    Scrape GitHub Trending (HTML).  Returns articles where the 'article'
    is a repo and the 'summary' is the description.  Fails gracefully.
    """
    raw = _fetch_url("https://github.com/trending?since=daily", timeout=15)
    if not raw:
        return []

    articles = []
    # Regex to find repo cards in the HTML
    # Pattern: <h2 class="..."><a href="/owner/repo">
    repo_pattern = re.compile(
        r'<h2[^>]*>\s*<a\s+href="(/[^/"]+/[^/"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL
    )
    desc_pattern = re.compile(
        r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL
    )

    repos    = repo_pattern.findall(raw)
    descs    = [re.sub(r"<[^>]+>", "", d).strip() for d in desc_pattern.findall(raw)]
    today    = datetime.now(timezone.utc).isoformat()

    for i, (path, name_raw) in enumerate(repos[:20]):
        name = re.sub(r"<[^>]+>", "", name_raw).strip().replace("\n", "").replace("  ", "")
        desc = descs[i] if i < len(descs) else ""
        url  = f"https://github.com{path}"
        if name:
            articles.append({
                "url":       url,
                "title":     f"[GitHub Trending] {name}",
                "summary":   desc[:300],
                "source":    "GitHub Trending",
                "published": today,
            })

    print(f"[beacon] GitHub Trending: {len(articles)} repos")
    return articles

# ── Relevance Scoring ─────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """Lowercase word tokenization."""
    return re.findall(r'\b[a-z]{2,}\b', text.lower())


def score_articles(articles: list[dict], topics: list[str]) -> list[dict]:
    """
    Score each article by relevance to tracked topics.

    Method: for each topic term, compute exact phrase match + token overlap.
    Score = weighted sum of matches / document length^0.5 (tf-idf inspired).
    Returns articles sorted by score descending.
    """
    topic_tokens = [_tokenize(t) for t in topics]
    topic_phrases = [t.lower() for t in topics]

    for art in articles:
        text = f"{art['title']} {art.get('summary', '')}".lower()
        tokens = _tokenize(text)
        token_set = set(tokens)
        doc_len = max(len(tokens), 1)

        raw_score = 0.0
        matched = []

        for phrase, t_tokens in zip(topic_phrases, topic_tokens):
            # Exact phrase match (high weight)
            if phrase in text:
                raw_score += 3.0
                matched.append(phrase)
                continue
            # Token overlap (lower weight)
            overlap = sum(1 for t in t_tokens if t in token_set)
            if overlap > 0:
                raw_score += overlap * 1.0
                if overlap >= len(t_tokens):
                    matched.append(phrase)

        # Normalize by sqrt(doc_length) to penalize long noisy docs less harshly
        art["score"]          = raw_score / math.sqrt(doc_len)
        art["matched_topics"] = list(set(matched))

    articles.sort(key=lambda a: a["score"], reverse=True)
    return articles

# ── Deduplication ─────────────────────────────────────────────────────────────

def dedupe_articles(articles: list[dict], conn: sqlite3.Connection) -> list[dict]:
    """
    Remove articles whose URL hash already exists in the DB.
    Insert new articles into DB (with score=0 placeholder).
    Returns only the new articles.
    """
    new_articles = []
    now = datetime.now(timezone.utc).isoformat()

    for art in articles:
        uh = _url_hash(art["url"])
        existing = conn.execute(
            "SELECT id FROM articles WHERE url_hash=?", (uh,)
        ).fetchone()

        if existing:
            continue  # already seen

        # Insert into DB (score will be updated after scoring)
        conn.execute("""
            INSERT INTO articles
                (url_hash, url, title, summary, source, published, seen_at)
            VALUES (?,?,?,?,?,?,?)
        """, (uh, art["url"], art["title"], art.get("summary",""),
              art["source"], art.get("published"), now))
        new_articles.append(art)

    conn.commit()
    print(f"[beacon] Dedup: {len(new_articles)} new / {len(articles)-len(new_articles)} seen before")
    return new_articles


def update_scores_in_db(articles: list[dict], conn: sqlite3.Connection) -> None:
    """Persist relevance scores back to the articles table."""
    for art in articles:
        uh = _url_hash(art["url"])
        conn.execute("""
            UPDATE articles SET score=?, matched_topics=?
            WHERE url_hash=?
        """, (art["score"], json.dumps(art["matched_topics"]), uh))
    conn.commit()

# ── Synthesis ─────────────────────────────────────────────────────────────────

def _call_claude(prompt: str) -> str | None:
    """Call Anthropic claude-haiku-3 and return the text response."""
    if not ANTHROPIC_KEY:
        return None
    try:
        payload = json.dumps({
            "model": "claude-haiku-4-5",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key":         ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode())
            return data["content"][0]["text"]
    except Exception as exc:
        print(f"[beacon] Claude call failed: {exc}")
        return None


def synthesize_template(top_articles: list[dict], topics: list[str], run_date: str) -> dict:
    """
    Deterministic template-based report when no API key is available.
    Produces the same structure as the AI synthesis.
    """
    # Group by source
    by_source = defaultdict(list)
    for art in top_articles:
        by_source[art["source"]].append(art)

    # Top signals = top 5 by score
    signals = top_articles[:5]

    # Emerging trends = most-common matched topics
    topic_counts = defaultdict(int)
    for art in top_articles:
        for t in art.get("matched_topics", []):
            topic_counts[t] += 1
    trends = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "date":             run_date,
        "topics_tracked":   topics,
        "sources_used":     list(by_source.keys()),
        "articles_surfaced": len(top_articles),
        "top_signals": [
            {
                "title":  a["title"],
                "source": a["source"],
                "url":    a["url"],
                "why":    f"Matched topics: {', '.join(a.get('matched_topics',[]) or ['general relevance'])}",
                "score":  round(a["score"], 3),
            }
            for a in signals
        ],
        "emerging_trends": [
            {"trend": t, "article_count": c, "signal": f"{c} article(s) mention this topic"}
            for t, c in trends
        ],
        "key_developments": [
            {"title": a["title"], "source": a["source"], "url": a["url"]}
            for a in top_articles[5:12]
        ],
        "recommended_reading": [
            {"title": a["title"], "url": a["url"], "source": a["source"]}
            for a in top_articles[:8]
        ],
        "synthesis_method": "template",
        "noise_filtered": 0,  # set by caller
    }


def synthesize_claude(top_articles: list[dict], topics: list[str], run_date: str) -> dict | None:
    """Ask Claude to synthesize a structured intelligence brief."""
    articles_text = "\n".join([
        f"[{i+1}] {a['title']} ({a['source']})\n    URL: {a['url']}\n    Summary: {a.get('summary','')[:200]}\n    Topics matched: {', '.join(a.get('matched_topics',[]))}"
        for i, a in enumerate(top_articles[:12])
    ])

    prompt = f"""You are an AI intelligence analyst. Today is {run_date}.

The user is tracking these topics: {', '.join(topics)}.

Here are the top-scored articles from the last 24-48 hours:

{articles_text}

Produce a structured intelligence brief as JSON with EXACTLY this schema:
{{
  "top_signals": [
    {{"title": "...", "source": "...", "url": "...", "why": "one sentence on why this matters", "score_rank": 1}}
  ],
  "emerging_trends": [
    {{"trend": "...", "article_count": N, "signal": "one sentence describing the pattern"}}
  ],
  "key_developments": [
    {{"title": "...", "source": "...", "url": "..."}}
  ],
  "recommended_reading": [
    {{"title": "...", "url": "...", "source": "..."}}
  ],
  "executive_summary": "3-4 sentence synthesis of what's happening in the tracked topic space today."
}}

Return ONLY valid JSON. No markdown fences, no commentary."""

    raw = _call_claude(prompt)
    if not raw:
        return None

    # Strip accidental markdown fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw.strip())

    try:
        result = json.loads(raw)
        result["date"]             = run_date
        result["topics_tracked"]   = topics
        result["articles_surfaced"] = len(top_articles)
        result["synthesis_method"] = "claude"
        return result
    except json.JSONDecodeError as exc:
        print(f"[beacon] JSON parse failed: {exc}")
        return None


def render_markdown(report: dict, run_id: int) -> str:
    """
    Convert a structured report dict to a human-readable Markdown document.
    This is what gets stored in runs.report_md and shown in the dashboard.
    """
    date = report.get("date", "Unknown date")
    topics = ", ".join(report.get("topics_tracked", []))
    method = report.get("synthesis_method", "unknown")
    method_badge = "🤖 AI-synthesized" if method == "claude" else "📋 Template (no API key)"
    surfaced = report.get("articles_surfaced", 0)
    noise = report.get("noise_filtered", 0)

    lines = [
        f"# 🔭 Beacon Intelligence Brief — {date}",
        f"",
        f"**Topics tracked:** {topics}  ",
        f"**Articles surfaced:** {surfaced}  |  **Noise filtered:** {noise}  |  {method_badge}  ",
        f"**Sources:** {', '.join(report.get('sources_used', []))}",
        f"",
    ]

    # Executive summary (AI only)
    if report.get("executive_summary"):
        lines += [
            "## 🧠 Executive Summary",
            "",
            report["executive_summary"],
            "",
        ]

    # Top signals
    signals = report.get("top_signals", [])
    if signals:
        lines += ["## 🔥 Top Signals", ""]
        for i, s in enumerate(signals, 1):
            lines += [
                f"**{i}. [{s['title']}]({s['url']})**  ",
                f"*{s['source']}* — {s.get('why', '')}",
                "",
            ]

    # Emerging trends
    trends = report.get("emerging_trends", [])
    if trends:
        lines += ["## 📈 Emerging Trends", ""]
        for t in trends:
            lines += [f"- **{t['trend']}** ({t.get('article_count','')} articles) — {t.get('signal','')}"]
        lines.append("")

    # Key developments
    devs = report.get("key_developments", [])
    if devs:
        lines += ["## 📰 Key Developments", ""]
        for d in devs:
            lines += [f"- [{d['title']}]({d['url']}) *({d['source']})*"]
        lines.append("")

    # Recommended reading
    reading = report.get("recommended_reading", [])
    if reading:
        lines += ["## 📚 Recommended Reading", ""]
        for r in reading:
            lines += [f"- [{r['title']}]({r['url']}) — {r['source']}"]
        lines.append("")

    lines += [
        "---",
        f"*Generated by Beacon v1.0 | Run #{run_id} | OpenClaw demo project*",
    ]

    return "\n".join(lines)

# ── Delivery ──────────────────────────────────────────────────────────────────

def deliver_discord(report: dict, report_md: str) -> bool:
    """
    Send a compact Discord embed via webhook.
    Full report is in the DB; Discord gets a summary.
    """
    if not DISCORD_WEBHOOK:
        print("[beacon] No BEACON_DISCORD_WEBHOOK set — skipping Discord delivery.")
        return False

    date    = report.get("date", "")
    method  = report.get("synthesis_method", "template")
    signals = report.get("top_signals", [])
    trends  = report.get("emerging_trends", [])
    summary = report.get("executive_summary", "No AI summary available.")

    # Build compact signals text
    sig_lines = "\n".join([
        f"**{i+1}.** [{s['title'][:60]}]({s['url']}) — *{s['source']}*"
        for i, s in enumerate(signals[:5])
    ])

    trend_lines = "\n".join([
        f"• **{t['trend']}** — {t.get('signal','')[:80]}"
        for t in trends[:4]
    ])

    embed = {
        "embeds": [{
            "title": f"🔭 Beacon Intelligence Brief — {date}",
            "description": summary[:400] if summary else "Multi-source AI intelligence report.",
            "color": 0x5865F2,
            "fields": [
                {"name": "🔥 Top Signals", "value": sig_lines or "None", "inline": False},
                {"name": "📈 Emerging Trends", "value": trend_lines or "None", "inline": False},
                {
                    "name": "📊 Stats",
                    "value": (
                        f"**Surfaced:** {report.get('articles_surfaced',0)} articles  "
                        f"**Sources:** {len(report.get('sources_used',[]))}  "
                        f"**Synthesis:** {'🤖 AI' if method=='claude' else '📋 Template'}"
                    ),
                    "inline": False,
                },
            ],
            "footer": {"text": "Beacon v1.0 — OpenClaw Intelligence Pipeline Demo"},
        }]
    }

    try:
        data = json.dumps(embed).encode()
        req  = urllib.request.Request(
            DISCORD_WEBHOOK,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[beacon] Discord delivered: HTTP {resp.status}")
            return True
    except Exception as exc:
        print(f"[beacon] Discord delivery failed: {exc}")
        return False

# ── Main Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(deliver: bool = False) -> int:
    """
    Execute the full Beacon pipeline. Returns the run_id.

    Steps:
      1. Open DB, seed topics
      2. Collect from all sources
      3. Deduplicate against seen articles
      4. Score for relevance
      5. Filter to threshold + recency
      6. Synthesize report (Claude → template fallback)
      7. Render Markdown
      8. Persist run + update article references
      9. Optionally deliver to Discord
    """
    conn = get_db()
    seed_default_topics(conn)

    now_str  = datetime.now(timezone.utc).isoformat()
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Create run record
    cur = conn.execute(
        "INSERT INTO runs (started_at, status) VALUES (?,?)",
        (now_str, "running")
    )
    run_id = cur.lastrowid
    conn.commit()
    print(f"\n[beacon] ─── Run #{run_id} started at {now_str} ───")

    try:
        # 1. Collect
        print("[beacon] Stage 1: Collect")
        raw_articles = []
        raw_articles.extend(collect_hackernews())
        raw_articles.extend(collect_rss())
        raw_articles.extend(collect_github_trending())
        total_fetched = len(raw_articles)
        print(f"[beacon] Total fetched: {total_fetched}")

        # 2. Deduplicate (also inserts new articles into DB)
        print("[beacon] Stage 2: Deduplicate")
        new_articles = dedupe_articles(raw_articles, conn)

        # 3. Score
        print("[beacon] Stage 3: Score")
        topics = get_active_topics(conn)
        scored = score_articles(new_articles, topics)

        # 4. Update scores in DB
        update_scores_in_db(scored, conn)

        # 5. Filter
        print("[beacon] Stage 4: Filter")
        above_threshold = [a for a in scored if a["score"] >= SCORE_THRESHOLD]
        noise_count     = len(scored) - len(above_threshold)
        top_articles    = above_threshold[:MAX_SURFACED]
        print(f"[beacon] Above threshold: {len(above_threshold)} | Surfaced: {len(top_articles)} | Noise: {noise_count}")

        # 6. Synthesize
        print("[beacon] Stage 5: Synthesize")
        report = synthesize_claude(top_articles, topics, run_date)
        if not report:
            print("[beacon] Claude unavailable — using template fallback")
            report = synthesize_template(top_articles, topics, run_date)

        report["noise_filtered"] = noise_count
        report["sources_used"]   = list({a["source"] for a in top_articles})

        # 7. Render Markdown
        print("[beacon] Stage 6: Render")
        report_md = render_markdown(report, run_id)

        # 8. Update articles: mark as reported in this run
        for art in top_articles:
            uh = _url_hash(art["url"])
            conn.execute(
                "UPDATE articles SET reported_in=? WHERE url_hash=?",
                (run_id, uh)
            )

        # 9. Persist run
        delivered_flag = 0
        if deliver:
            print("[beacon] Stage 7: Deliver")
            delivered_flag = 1 if deliver_discord(report, report_md) else 0

        conn.execute("""
            UPDATE runs SET
                finished_at=?, articles_fetched=?, articles_scored=?,
                articles_surfaced=?, report_md=?, report_json=?,
                delivered=?, status='complete'
            WHERE id=?
        """, (
            datetime.now(timezone.utc).isoformat(),
            total_fetched,
            len(scored),
            len(top_articles),
            report_md,
            json.dumps(report),
            delivered_flag,
            run_id,
        ))
        conn.commit()

        print(f"\n[beacon] ─── Run #{run_id} complete ───")
        print(f"[beacon] Fetched {total_fetched} | Deduped {len(new_articles)} new | Surfaced {len(top_articles)}")
        print(f"\n{'='*60}")
        print(report_md[:2000])
        print('='*60)

        return run_id

    except Exception as exc:
        conn.execute(
            "UPDATE runs SET status='failed', finished_at=? WHERE id=?",
            (datetime.now(timezone.utc).isoformat(), run_id)
        )
        conn.commit()
        print(f"[beacon] PIPELINE FAILED: {exc}")
        raise


if __name__ == "__main__":
    deliver_flag = "--deliver" in sys.argv
    run_pipeline(deliver=deliver_flag)
