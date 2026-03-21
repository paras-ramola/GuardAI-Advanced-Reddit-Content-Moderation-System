-- Reddit Content Moderation System — Database Schema (v2, offline dataset)
-- Run: python -m db.init_db

-- ─── Main content table ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS content (
    id              BIGSERIAL PRIMARY KEY,
    text            TEXT            NOT NULL,
    content_type    VARCHAR(20)     NOT NULL DEFAULT 'comment',
    subreddit       VARCHAR(100)    NOT NULL,
    score           INTEGER         DEFAULT 0,
    controversiality INTEGER        DEFAULT 0,
    reddit_id       VARCHAR(50),                 -- optional, from raw data
    author          VARCHAR(100),
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

-- ─── Predictions table ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
    id              BIGSERIAL PRIMARY KEY,
    content_id      BIGINT          NOT NULL REFERENCES content(id) ON DELETE CASCADE,
    label           VARCHAR(20)     NOT NULL CHECK (label IN ('hate', 'safe')),
    confidence      FLOAT           NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    severity        FLOAT           NOT NULL CHECK (severity BETWEEN 0 AND 1),
    toxic_words     TEXT[],
    model_version   VARCHAR(50)     NOT NULL DEFAULT 'bert-v1',
    is_low_confidence BOOLEAN       GENERATED ALWAYS AS (confidence BETWEEN 0.4 AND 0.6) STORED,
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

-- ─── Analytics cache ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analytics_cache (
    id              SERIAL PRIMARY KEY,
    subreddit       VARCHAR(100)    NOT NULL,
    total_analyzed  INTEGER         NOT NULL,
    hate_count      INTEGER         NOT NULL,
    hate_percentage FLOAT           NOT NULL,
    avg_severity    FLOAT           NOT NULL,
    computed_at     TIMESTAMPTZ     DEFAULT NOW()
);

-- ─── User Feedback (Active Learning) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_feedback (
    id              SERIAL PRIMARY KEY,
    prediction_id   BIGINT          NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    text            TEXT            NOT NULL,
    original_label  VARCHAR(20)     NOT NULL,
    corrected_label VARCHAR(20)     NOT NULL,
    model_version   VARCHAR(50)     NOT NULL,
    created_at      TIMESTAMPTZ     DEFAULT NOW()
);

-- ─── Indexes (critical for 1.9M row performance) ─────────────────────────────
-- Primary filter: subreddit lookup
CREATE INDEX IF NOT EXISTS idx_content_subreddit        ON content(subreddit);
-- Sort by score desc (top comments first)
CREATE INDEX IF NOT EXISTS idx_content_subreddit_score  ON content(subreddit, score DESC);
-- Filter by controversiality
CREATE INDEX IF NOT EXISTS idx_content_controversial    ON content(subreddit, controversiality);
-- Predictions join
CREATE INDEX IF NOT EXISTS idx_predictions_content_id  ON predictions(content_id);
CREATE INDEX IF NOT EXISTS idx_predictions_label        ON predictions(label);
-- Low-confidence error analysis
CREATE INDEX IF NOT EXISTS idx_predictions_low_conf     ON predictions(is_low_confidence)
    WHERE is_low_confidence = TRUE;
-- Analytics cache lookup
CREATE INDEX IF NOT EXISTS idx_analytics_subreddit      ON analytics_cache(subreddit, computed_at DESC);
