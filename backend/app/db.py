"""SQLite persistence. AI reviews, human decisions and audit events are separate, append-only records."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pcn_ref         TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new','validated','ai_reviewed','ai_failed','decided','escalated')),
    case_json       TEXT NOT NULL,
    synthetic       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         INTEGER NOT NULL REFERENCES cases(id),
    evidence_id     TEXT NOT NULL,
    filename        TEXT NOT NULL,
    stored_path     TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    size_bytes      INTEGER NOT NULL,
    content_type    TEXT,
    uploaded_at     TEXT NOT NULL,
    UNIQUE (case_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS checks (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id             INTEGER NOT NULL REFERENCES cases(id),
    ruleset_version     TEXT NOT NULL,
    policy_version      TEXT NOT NULL,
    validation_json     TEXT NOT NULL,
    rules_json          TEXT NOT NULL,
    indicator           TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

-- Original AI output, never updated after insert.
CREATE TABLE IF NOT EXISTS ai_reviews (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id             INTEGER NOT NULL REFERENCES cases(id),
    check_id            INTEGER NOT NULL REFERENCES checks(id),
    status              TEXT NOT NULL CHECK (status IN ('valid','valid_with_warnings','failed')),
    failure_kind        TEXT,
    provider            TEXT NOT NULL,
    model               TEXT,
    provider_request_id TEXT,
    prompt_version      TEXT NOT NULL,
    ruleset_version     TEXT NOT NULL,
    mode                TEXT NOT NULL CHECK (mode IN ('baseline','precedent')),
    precedent_ids_json  TEXT NOT NULL DEFAULT '[]',
    raw_output          TEXT,
    parsed_json         TEXT,
    safety_flags_json   TEXT NOT NULL DEFAULT '[]',
    effective_recommendation TEXT NOT NULL,
    latency_ms          INTEGER,
    usage_json          TEXT,
    created_at          TEXT NOT NULL
);

-- Human decision, stored separately from the AI review it responds to.
CREATE TABLE IF NOT EXISTS decisions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id             INTEGER NOT NULL REFERENCES cases(id),
    ai_review_id        INTEGER REFERENCES ai_reviews(id),
    action              TEXT NOT NULL CHECK (action IN ('accept','override','reject','escalate')),
    final_outcome       TEXT NOT NULL CHECK (final_outcome IN ('representation_accepted','representation_rejected','escalated')),
    ai_recommendation   TEXT,
    reason_code         TEXT,
    reason              TEXT,
    final_response      TEXT,
    reviewer            TEXT NOT NULL,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback_examples (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id             INTEGER REFERENCES cases(id),
    decision_id         INTEGER REFERENCES decisions(id),
    source              TEXT NOT NULL CHECK (source IN ('review','eval_pool')),
    contravention_code  TEXT NOT NULL,
    claimed_grounds     TEXT NOT NULL,
    summary_text        TEXT NOT NULL,
    final_label         TEXT NOT NULL CHECK (final_label IN ('accept','reject','needs_review')),
    ai_label            TEXT,
    correction_reason   TEXT,
    curation_status     TEXT NOT NULL DEFAULT 'pending' CHECK (curation_status IN ('pending','eligible','ineligible')),
    curated_by          TEXT,
    curation_note       TEXT,
    created_at          TEXT NOT NULL,
    curated_at          TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         INTEGER REFERENCES cases(id),
    event_type      TEXT NOT NULL,
    actor           TEXT NOT NULL,
    detail_json     TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_version TEXT NOT NULL,
    provider        TEXT NOT NULL,
    model           TEXT,
    report_json     TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_reviews_case ON ai_reviews(case_id);
CREATE INDEX IF NOT EXISTS idx_decisions_case ON decisions(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_events(case_id);
CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback_examples(curation_status, source);

CREATE TRIGGER IF NOT EXISTS ai_reviews_immutable BEFORE UPDATE ON ai_reviews
BEGIN SELECT RAISE(ABORT, 'ai_reviews rows are immutable'); END;
CREATE TRIGGER IF NOT EXISTS ai_reviews_no_delete BEFORE DELETE ON ai_reviews
BEGIN SELECT RAISE(ABORT, 'ai_reviews rows are immutable'); END;
CREATE TRIGGER IF NOT EXISTS audit_immutable BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events rows are append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(ABORT, 'audit_events rows are append-only'); END;
CREATE TRIGGER IF NOT EXISTS decisions_immutable BEFORE UPDATE ON decisions
BEGIN SELECT RAISE(ABORT, 'decisions rows are immutable; record a new decision instead'); END;
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_settings().db_path
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def transaction(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    for key in list(out):
        if key.endswith("_json") and isinstance(out[key], str):
            out[key[:-5]] = json.loads(out.pop(key))
    return out


def audit(conn: sqlite3.Connection, case_id: int | None, event_type: str, actor: str, detail: dict) -> None:
    conn.execute(
        "INSERT INTO audit_events (case_id, event_type, actor, detail_json, created_at) VALUES (?,?,?,?,?)",
        (case_id, event_type, actor, json.dumps(detail, default=str), now_iso()),
    )
