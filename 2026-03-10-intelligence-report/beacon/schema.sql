-- Beacon — Database Schema
-- Three tables: articles (raw), topics (config), runs (history)

CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash    TEXT UNIQUE NOT NULL,       -- SHA256 of normalized URL (dedup key)
    url         TEXT NOT NULL,
    title       TEXT NOT NULL,
    summary     TEXT,
    source      TEXT NOT NULL,             -- Feed name
    published   TEXT,                      -- ISO8601
    score       REAL DEFAULT 0.0,          -- Relevance score vs tracked topics
    matched_topics TEXT,                   -- JSON array of matched topics
    seen_at     TEXT NOT NULL,             -- When we first ingested it
    reported_in INTEGER                    -- run_id this article was surfaced in
);

CREATE TABLE IF NOT EXISTS topics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    term        TEXT UNIQUE NOT NULL,
    active      INTEGER DEFAULT 1,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    articles_fetched  INTEGER DEFAULT 0,
    articles_scored   INTEGER DEFAULT 0,
    articles_surfaced INTEGER DEFAULT 0,
    report_md   TEXT,                      -- Full rendered markdown report
    report_json TEXT,                      -- Structured report (JSON)
    delivered   INTEGER DEFAULT 0,         -- 1 if sent to Discord
    status      TEXT DEFAULT 'running'     -- running | complete | failed
);

CREATE INDEX IF NOT EXISTS idx_articles_score   ON articles(score DESC);
CREATE INDEX IF NOT EXISTS idx_articles_seen    ON articles(seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_articles_run     ON articles(reported_in);
