SCHEMA = """
CREATE TABLE IF NOT EXISTS driver_cases (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    facts_json TEXT NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 0,
    confirmed INTEGER NOT NULL DEFAULT 0,
    ai_consent INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'preparing',
    outcome TEXT,
    outcome_verified INTEGER NOT NULL DEFAULT 0,
    reported_refund_pence INTEGER NOT NULL DEFAULT 0,
    draft_text TEXT NOT NULL DEFAULT '',
    draft_review_id TEXT,
    draft_approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_driver_cases_owner ON driver_cases(owner_id, updated_at);
CREATE TABLE IF NOT EXISTS driver_evidence (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES driver_cases(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content BLOB NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_driver_evidence_case ON driver_evidence(case_id);
CREATE TABLE IF NOT EXISTS driver_reviews (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES driver_cases(id) ON DELETE CASCADE,
    input_version INTEGER NOT NULL,
    kind TEXT NOT NULL,
    output_json TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT,
    request_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_driver_reviews_case ON driver_reviews(case_id, created_at);
CREATE TABLE IF NOT EXISTS driver_events (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES driver_cases(id) ON DELETE CASCADE,
    event TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS driver_jobs (
    case_id TEXT PRIMARY KEY REFERENCES driver_cases(id) ON DELETE CASCADE,
    token TEXT NOT NULL,
    expires_at BIGINT NOT NULL
);
"""

# Additive migration: existing cases never opt into training implicitly.
RECORDING_SCHEMA = """
ALTER TABLE driver_cases ADD COLUMN training_consent INTEGER NOT NULL DEFAULT 0 CHECK (training_consent IN (0,1));
ALTER TABLE driver_reviews ADD COLUMN recording_requested TEXT NOT NULL DEFAULT 'metadata';
"""
