#!/usr/bin/env python3
"""
research_agent.py — Autonomous Web Research Agent
==================================================

Demonstrates the core OpenClaw web research loop:

  Topic → Decompose → Parallel Search → Extract → Synthesize → Structured Report

This pattern mirrors exactly how an OpenClaw agent chains web_search +
web_fetch in a reasoning loop — but packaged as a runnable Python service
any client can drop in and schedule.

Usage:
    python research_agent.py "AI regulation in 2025"
    python research_agent.py "AI regulation in 2025" --depth 3 --output reports/
    python research_agent.py "AI regulation in 2025" --depth 5 --no-llm

Architecture:
    ResearchAgent.research(topic)
        ├── decompose_topic()     → N focused sub-questions
        ├── parallel_search()     → Search results per sub-question
        ├── parallel_extract()    → Clean text from URLs
        ├── synthesize()          → LLM cross-source analysis
        └── save_report()         → JSON + Markdown output

Author: Cortana (OpenClaw Forge, 2026-03-05)
"""

import os
import sys
import json
import time
import hashlib
import logging
import argparse
import datetime
import textwrap
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml
import requests
from bs4 import BeautifulSoup

# ── Optional: Anthropic SDK ────────────────────────────────────────────────────
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# ── Optional: DuckDuckGo search (free, no API key required) ───────────────────
try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("research_agent")

# ── Constants ──────────────────────────────────────────────────────────────────
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"
REPORTS_DIR = Path(__file__).parent / "reports"
USER_AGENT = "Mozilla/5.0 (compatible; ResearchAgent/1.0; OpenClaw)"
FETCH_TIMEOUT = 10          # seconds per URL
MAX_CONTENT_CHARS = 4000    # chars to extract per page (keeps prompt sizes sane)
MAX_WORKERS = 6             # parallel fetch threads


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load YAML config, merging with defaults."""
    defaults = {
        "depth": 4,                   # number of sub-questions to generate
        "results_per_query": 3,       # search results per sub-question
        "llm_model": "claude-3-5-haiku-20241022",
        "brave_api_key": os.getenv("BRAVE_API_KEY", ""),
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "output_dir": str(REPORTS_DIR),
        "fetch_timeout": FETCH_TIMEOUT,
    }
    if path.exists():
        with open(path) as f:
            file_cfg = yaml.safe_load(f) or {}
        defaults.update(file_cfg)
    return defaults


# ══════════════════════════════════════════════════════════════════════════════
# SEARCH  — Brave API primary, DuckDuckGo fallback
# ══════════════════════════════════════════════════════════════════════════════

def search_brave(query: str, api_key: str, count: int = 3) -> list[dict]:
    """
    Search via Brave Search API.
    Returns list of {title, url, snippet} dicts.
    """
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {"q": query, "count": count, "safesearch": "moderate"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("web", {}).get("results", [])[:count]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
            })
        return results
    except Exception as e:
        log.warning(f"Brave search failed for '{query}': {e}")
        return []


def search_ddg(query: str, count: int = 3) -> list[dict]:
    """
    DuckDuckGo fallback — no API key needed.
    Uses the duckduckgo_search package.
    """
    if not HAS_DDG:
        log.warning("duckduckgo_search not installed. pip install duckduckgo-search")
        return []
    try:
        with DDGS() as ddgs:
            raw = ddgs.text(query, max_results=count)
        results = []
        for item in (raw or [])[:count]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("href", ""),
                "snippet": item.get("body", ""),
            })
        return results
    except Exception as e:
        log.warning(f"DDG search failed for '{query}': {e}")
        return []


def search(query: str, cfg: dict) -> list[dict]:
    """
    Search router: use Brave if API key is available, else DDG.
    Returns list of {title, url, snippet}.
    """
    if cfg.get("brave_api_key"):
        results = search_brave(query, cfg["brave_api_key"], cfg["results_per_query"])
        if results:
            return results
        log.info("Brave returned no results, falling back to DDG")
    return search_ddg(query, cfg["results_per_query"])


# ══════════════════════════════════════════════════════════════════════════════
# CONTENT EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════

def extract_content(url: str, timeout: int = FETCH_TIMEOUT) -> str:
    """
    Fetch a URL and extract readable plain text.

    Strategy:
    1. Download HTML with a browser-like User-Agent
    2. Remove script/style/nav/footer tags (noise)
    3. Extract paragraphs with ≥40 chars (skip boilerplate)
    4. Return up to MAX_CONTENT_CHARS characters

    This mirrors what OpenClaw's web_fetch tool does internally.
    """
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type:
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove noise elements
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "noscript", "iframe", "ads"]):
            tag.decompose()

        # Extract meaningful paragraphs
        paragraphs = []
        for p in soup.find_all(["p", "li", "h2", "h3", "h4"]):
            text = p.get_text(separator=" ", strip=True)
            if len(text) >= 40:  # skip one-liners and labels
                paragraphs.append(text)

        combined = "\n".join(paragraphs)
        return combined[:MAX_CONTENT_CHARS]

    except Exception as e:
        log.debug(f"Fetch failed for {url}: {e}")
        return ""


def parallel_extract(urls: list[str], timeout: int = FETCH_TIMEOUT) -> dict[str, str]:
    """
    Fetch and extract content from multiple URLs in parallel.
    Returns {url: extracted_text}.
    """
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(extract_content, url, timeout): url for url in urls}
        for future in as_completed(future_map):
            url = future_map[future]
            try:
                results[url] = future.result()
            except Exception as e:
                log.debug(f"Extraction error for {url}: {e}")
                results[url] = ""
    return results


# ══════════════════════════════════════════════════════════════════════════════
# LLM CALLS — Claude or template fallback
# ══════════════════════════════════════════════════════════════════════════════

def call_claude(prompt: str, system: str, model: str, api_key: str) -> str:
    """Single Claude API call with error handling."""
    if not HAS_ANTHROPIC:
        raise RuntimeError("anthropic package not installed")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def decompose_topic_llm(topic: str, depth: int, cfg: dict) -> list[str]:
    """
    Use Claude to break a broad topic into focused sub-questions.
    More targeted searches → higher quality sources → better synthesis.
    """
    system = (
        "You are a research strategist. Your job is to break a broad research topic "
        "into focused, searchable sub-questions that together give complete coverage. "
        "Return ONLY a JSON array of strings — no markdown, no explanation."
    )
    prompt = (
        f"Topic: {topic}\n\n"
        f"Generate exactly {depth} focused sub-questions that explore different angles. "
        f"Make each question specific and searchable (2-8 words each).\n\n"
        f"Return: [\"question 1\", \"question 2\", ...]"
    )
    raw = call_claude(prompt, system, cfg["llm_model"], cfg["anthropic_api_key"])
    # Parse JSON array from response
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start != -1 and end > start:
        return json.loads(raw[start:end])
    # Fallback: split by lines if JSON parsing fails
    lines = [l.strip().strip('"-,') for l in raw.split("\n") if l.strip()]
    return [l for l in lines if len(l) > 5][:depth]


def decompose_topic_template(topic: str, depth: int) -> list[str]:
    """
    Template fallback when no LLM is available.
    Generates generic sub-questions by applying common research angles.
    """
    angles = [
        f"What is {topic}",
        f"{topic} latest developments 2025",
        f"{topic} key challenges and limitations",
        f"{topic} industry applications examples",
        f"{topic} future trends predictions",
        f"{topic} expert analysis opinion",
        f"{topic} policy regulation government",
        f"{topic} market size statistics data",
    ]
    return angles[:depth]


def synthesize_llm(
    topic: str,
    sub_questions: list[str],
    sources: list[dict],
    cfg: dict,
) -> dict:
    """
    Cross-source synthesis using Claude.

    Builds a prompt with all extracted source text and asks Claude to:
    - Summarize findings per sub-question
    - Identify consensus and conflicting viewpoints
    - Highlight key facts and data points
    - Produce an executive summary
    """
    # Build source context block
    source_blocks = []
    for i, src in enumerate(sources):
        if src.get("content"):
            block = (
                f"[Source {i+1}] {src['title']}\n"
                f"URL: {src['url']}\n"
                f"Sub-question: {src['sub_question']}\n"
                f"Content:\n{src['content'][:2000]}\n"
            )
            source_blocks.append(block)

    if not source_blocks:
        return _synthesis_template(topic, sub_questions, sources)

    context = "\n---\n".join(source_blocks)

    system = (
        "You are an expert research analyst. Synthesize web research into a structured, "
        "insightful report. Be factual, cite sources by number [1], [2] etc., and flag "
        "any conflicting information. Output valid JSON only."
    )

    prompt = f"""Research topic: {topic}

Sub-questions investigated:
{chr(10).join(f"  {i+1}. {q}" for i, q in enumerate(sub_questions))}

Sources gathered:
{context}

Produce a JSON object with these exact keys:
{{
  "executive_summary": "3-5 sentence overview of the most important findings",
  "key_findings": ["finding 1 with source cite [N]", "finding 2", ...],
  "sub_question_answers": [
    {{"question": "...", "answer": "2-3 sentences with cites"}},
    ...
  ],
  "consensus_points": ["things all/most sources agree on"],
  "conflicting_points": ["areas where sources disagree or are unclear"],
  "data_highlights": ["specific stats, numbers, dates mentioned"],
  "confidence_level": "high | medium | low — with 1 sentence rationale"
}}"""

    raw = call_claude(prompt, system, cfg["llm_model"], cfg["anthropic_api_key"])
    # Extract JSON from response
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        return json.loads(raw[start:end])
    raise ValueError(f"Could not parse synthesis JSON: {raw[:200]}")


def _synthesis_template(topic: str, sub_questions: list[str], sources: list[dict]) -> dict:
    """
    Template-mode synthesis when LLM is unavailable.
    Extracts first meaningful sentence from each source as a "finding".
    """
    findings = []
    for src in sources:
        if src.get("content"):
            first_sentence = src["content"].split(".")[0].strip()
            if len(first_sentence) > 20:
                findings.append(f"{first_sentence}. [from: {src['title']}]")

    return {
        "executive_summary": (
            f"Research summary for '{topic}'. "
            f"Gathered {len(sources)} sources across {len(sub_questions)} sub-questions. "
            "LLM synthesis unavailable — showing extracted source highlights."
        ),
        "key_findings": findings[:8] if findings else ["No content extracted from sources."],
        "sub_question_answers": [
            {"question": q, "answer": "See key findings for extracted content."}
            for q in sub_questions
        ],
        "consensus_points": ["(LLM required for consensus analysis)"],
        "conflicting_points": [],
        "data_highlights": [],
        "confidence_level": "low — template mode, no LLM synthesis",
    }


# ══════════════════════════════════════════════════════════════════════════════
# REPORT FORMATTING
# ══════════════════════════════════════════════════════════════════════════════

def format_markdown(topic: str, synthesis: dict, sources: list[dict], meta: dict) -> str:
    """Render synthesis + sources as a clean Markdown report."""
    ts = meta["timestamp"]
    lines = [
        f"# Research Report: {topic}",
        f"",
        f"**Generated:** {ts}  ",
        f"**Sources:** {meta['source_count']}  ",
        f"**Sub-questions:** {meta['depth']}  ",
        f"**Mode:** {meta['mode']}  ",
        f"",
        "---",
        "",
        "## Executive Summary",
        "",
        synthesis.get("executive_summary", ""),
        "",
        "## Key Findings",
        "",
    ]
    for i, finding in enumerate(synthesis.get("key_findings", []), 1):
        lines.append(f"{i}. {finding}")
    lines += ["", "## Sub-Question Analysis", ""]
    for qa in synthesis.get("sub_question_answers", []):
        lines += [
            f"### {qa.get('question', '')}",
            "",
            qa.get("answer", ""),
            "",
        ]

    if synthesis.get("consensus_points"):
        lines += ["## Points of Consensus", ""]
        for pt in synthesis["consensus_points"]:
            lines.append(f"- {pt}")
        lines.append("")

    if synthesis.get("conflicting_points"):
        lines += ["## Conflicting Information", ""]
        for pt in synthesis["conflicting_points"]:
            lines.append(f"- {pt}")
        lines.append("")

    if synthesis.get("data_highlights"):
        lines += ["## Data & Statistics", ""]
        for pt in synthesis["data_highlights"]:
            lines.append(f"- {pt}")
        lines.append("")

    lines += [
        f"**Confidence:** {synthesis.get('confidence_level', 'unknown')}",
        "",
        "---",
        "",
        "## Sources",
        "",
    ]
    seen = set()
    for i, src in enumerate(sources, 1):
        url = src.get("url", "")
        if url and url not in seen:
            seen.add(url)
            lines.append(f"{i}. [{src.get('title', url)}]({url})")
            if src.get("sub_question"):
                lines.append(f"   *Sub-question: {src['sub_question']}*")

    return "\n".join(lines)


def save_report(
    topic: str,
    synthesis: dict,
    sources: list[dict],
    sub_questions: list[str],
    meta: dict,
    output_dir: Path,
) -> dict:
    """Save report as JSON + Markdown. Returns paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    # Stable ID from topic + timestamp
    uid = hashlib.md5(f"{topic}{meta['timestamp']}".encode()).hexdigest()[:8]
    safe_topic = "".join(c if c.isalnum() or c in "-_" else "_" for c in topic[:40])
    base = f"{meta['date']}_{safe_topic}_{uid}"

    report_data = {
        "id": uid,
        "topic": topic,
        "meta": meta,
        "sub_questions": sub_questions,
        "synthesis": synthesis,
        "sources": [
            {k: v for k, v in s.items() if k != "content"}
            for s in sources
        ],
    }

    json_path = output_dir / f"{base}.json"
    md_path = output_dir / f"{base}.md"

    json_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    md_path.write_text(format_markdown(topic, synthesis, sources, meta), encoding="utf-8")

    return {"json": str(json_path), "markdown": str(md_path), "id": uid}


# ══════════════════════════════════════════════════════════════════════════════
# MAIN AGENT CLASS
# ══════════════════════════════════════════════════════════════════════════════

class ResearchAgent:
    """
    Autonomous web research agent.

    Orchestrates the full pipeline:
      topic → sub-questions → search → extract → synthesize → report

    OpenClaw parallel: this class wraps the same reasoning loop that
    an OpenClaw agent would execute using web_search + web_fetch tools.
    """

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.use_llm = (
            bool(cfg.get("anthropic_api_key"))
            and HAS_ANTHROPIC
            and not cfg.get("no_llm", False)
        )
        self.output_dir = Path(cfg["output_dir"])
        log.info(f"ResearchAgent initialized | LLM: {self.use_llm} | depth: {cfg['depth']}")

    def decompose(self, topic: str) -> list[str]:
        """Step 1: Break topic into focused sub-questions."""
        log.info(f"Decomposing topic into {self.cfg['depth']} sub-questions...")
        if self.use_llm:
            try:
                questions = decompose_topic_llm(topic, self.cfg["depth"], self.cfg)
                log.info(f"LLM generated {len(questions)} sub-questions")
                return questions
            except Exception as e:
                log.warning(f"LLM decompose failed ({e}), using template")
        questions = decompose_topic_template(topic, self.cfg["depth"])
        log.info(f"Template generated {len(questions)} sub-questions")
        return questions

    def search_all(self, sub_questions: list[str]) -> list[dict]:
        """Step 2: Search each sub-question, collect results."""
        log.info(f"Searching {len(sub_questions)} sub-questions...")
        all_results = []
        seen_urls = set()

        def _search_one(question: str) -> list[dict]:
            results = search(question, self.cfg)
            for r in results:
                r["sub_question"] = question
            return results

        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(sub_questions))) as ex:
            futures = {ex.submit(_search_one, q): q for q in sub_questions}
            for future in as_completed(futures):
                try:
                    results = future.result()
                    for r in results:
                        if r["url"] not in seen_urls:
                            seen_urls.add(r["url"])
                            all_results.append(r)
                except Exception as e:
                    log.warning(f"Search future error: {e}")

        log.info(f"Collected {len(all_results)} unique search results")
        return all_results

    def extract_all(self, search_results: list[dict]) -> list[dict]:
        """Step 3: Fetch and extract content from all URLs in parallel."""
        urls = [r["url"] for r in search_results if r.get("url")]
        log.info(f"Extracting content from {len(urls)} URLs...")
        t0 = time.time()

        content_map = parallel_extract(urls, self.cfg["fetch_timeout"])

        # Merge extracted content back into result dicts
        enriched = []
        for result in search_results:
            url = result.get("url", "")
            content = content_map.get(url, "")
            enriched.append({**result, "content": content})

        nonempty = sum(1 for r in enriched if r.get("content"))
        log.info(f"Extracted content from {nonempty}/{len(enriched)} URLs in {time.time()-t0:.1f}s")
        return enriched

    def synthesize(self, topic: str, sub_questions: list[str], sources: list[dict]) -> dict:
        """Step 4: Cross-source synthesis → structured findings."""
        log.info("Synthesizing across sources...")
        if self.use_llm:
            try:
                result = synthesize_llm(topic, sub_questions, sources, self.cfg)
                log.info("LLM synthesis complete")
                return result
            except Exception as e:
                log.warning(f"LLM synthesis failed ({e}), using template")
        return _synthesis_template(topic, sub_questions, sources)

    def research(self, topic: str) -> dict:
        """
        Full research pipeline. Returns paths to saved report files.

        Trace:
          1. Decompose topic → sub-questions
          2. Parallel search each sub-question
          3. Parallel fetch + extract content
          4. LLM synthesis across all sources
          5. Save JSON + Markdown report
        """
        t_start = time.time()
        now = datetime.datetime.now()
        log.info(f"=== Starting research: '{topic}' ===")

        # Pipeline
        sub_questions = self.decompose(topic)
        search_results = self.search_all(sub_questions)
        enriched = self.extract_all(search_results)
        synthesis = self.synthesize(topic, sub_questions, enriched)

        # Metadata
        elapsed = time.time() - t_start
        meta = {
            "timestamp": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "topic": topic,
            "depth": len(sub_questions),
            "source_count": len(enriched),
            "elapsed_seconds": round(elapsed, 1),
            "mode": "llm" if self.use_llm else "template",
            "search_backend": "brave" if self.cfg.get("brave_api_key") else "ddg",
        }

        # Save
        paths = save_report(topic, synthesis, enriched, sub_questions, meta, self.output_dir)
        log.info(f"=== Research complete in {elapsed:.1f}s ===")
        log.info(f"  Markdown: {paths['markdown']}")
        log.info(f"  JSON:     {paths['json']}")

        return {**paths, "meta": meta, "synthesis": synthesis, "sub_questions": sub_questions}


# ══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def cli():
    parser = argparse.ArgumentParser(
        description="Autonomous Web Research Agent — OpenClaw Forge Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              python research_agent.py "AI regulation in Europe"
              python research_agent.py "prompt injection attacks" --depth 5
              python research_agent.py "LLM benchmarks 2025" --no-llm
              python research_agent.py "quantum computing breakthroughs" --output /tmp/reports
        """),
    )
    parser.add_argument("topic", help="Research topic or question")
    parser.add_argument("--depth", type=int, default=None,
                        help="Number of sub-questions (default: from config)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output directory for reports")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip LLM calls (template mode, fully offline)")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to config.yaml (default: ./config.yaml)")
    args = parser.parse_args()

    # Load config and apply CLI overrides
    cfg_path = Path(args.config) if args.config else DEFAULT_CONFIG_PATH
    cfg = load_config(cfg_path)
    if args.depth:
        cfg["depth"] = args.depth
    if args.output:
        cfg["output_dir"] = args.output
    if args.no_llm:
        cfg["no_llm"] = True

    agent = ResearchAgent(cfg)
    result = agent.research(args.topic)

    print("\n" + "=" * 60)
    print("RESEARCH COMPLETE")
    print("=" * 60)
    print(f"Topic:    {args.topic}")
    print(f"Sources:  {result['meta']['source_count']}")
    print(f"Duration: {result['meta']['elapsed_seconds']}s")
    print(f"Mode:     {result['meta']['mode']}")
    print(f"Markdown: {result['markdown']}")
    print(f"JSON:     {result['json']}")
    print("=" * 60)

    # Print executive summary to stdout
    summary = result["synthesis"].get("executive_summary", "")
    if summary:
        print(f"\n{summary}\n")


if __name__ == "__main__":
    cli()
