"""SQLite for local use; PostgreSQL/Neon when DATABASE_URL is configured."""
from __future__ import annotations

import json
import sqlite3
import psycopg
from psycopg import sql
from psycopg.rows import class_row
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from uuid import uuid4
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

CREATE TABLE IF NOT EXISTS investigations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ai_review_id INTEGER NOT NULL UNIQUE REFERENCES ai_reviews(id),
    steps_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Small attachments share the database so every application instance can read them.
CREATE TABLE IF NOT EXISTS evidence_blobs (
    storage_key TEXT PRIMARY KEY,
    content BLOB NOT NULL
);

-- A short-lived claim prevents duplicate model work across processes/instances.
CREATE TABLE IF NOT EXISTS review_leases (
    case_id INTEGER PRIMARY KEY REFERENCES cases(id),
    token TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS investigations_immutable BEFORE UPDATE ON investigations
BEGIN SELECT RAISE(ABORT, 'investigations are immutable'); END;

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
CREATE TRIGGER IF NOT EXISTS decisions_no_delete BEFORE DELETE ON decisions
BEGIN SELECT RAISE(ABORT, 'decisions rows are immutable'); END;
CREATE TRIGGER IF NOT EXISTS investigations_no_delete BEFORE DELETE ON investigations
BEGIN SELECT RAISE(ABORT, 'investigations are immutable'); END;
"""

INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)


class Record(dict):
    """Support the existing keyed and positional row access on both databases."""
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class PostgresConnection:
    def __init__(self, url, schema):
        # Disable prepared statements for transaction-pooler compatibility.
        self.raw = psycopg.connect(url, row_factory=class_row(Record), prepare_threshold=None,
                                   connect_timeout=10)
        self.raw.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))

    def execute(self, statement, params=()):
        # Application queries use qmark placeholders and never interpolate user input.
        # They contain no literal question marks. DDL is executed separately without rewriting.
        return self.raw.execute(statement.replace("?", "%s"), params or None)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


Connection = sqlite3.Connection | PostgresConnection


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def connect(db_path: Path | None = None) -> Connection:
    settings = get_settings()
    if db_path is None and settings.database_url:
        return PostgresConnection(settings.database_url, settings.db_schema)
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    with transaction(db_path) as conn:
        if isinstance(conn, PostgresConnection):
            schema = get_settings().db_schema
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(?))", (f"{schema}:migration",))
            conn.raw.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            if not conn.execute("SELECT 1 FROM schema_migrations WHERE version=1").fetchone():
                ddl = SCHEMA.split("CREATE TRIGGER", 1)[0].replace(
                    "INTEGER PRIMARY KEY AUTOINCREMENT", "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
                ).replace("content BLOB", "content BYTEA")
                conn.raw.execute(ddl)
                conn.raw.execute("""CREATE OR REPLACE FUNCTION civic_immutable() RETURNS trigger AS $$
                    BEGIN RAISE EXCEPTION 'Records in % are append-only', TG_TABLE_NAME USING ERRCODE='23000'; END;
                    $$ LANGUAGE plpgsql""")
                for table in ("ai_reviews", "decisions", "audit_events", "investigations"):
                    conn.raw.execute(sql.SQL("CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON {} "
                        "FOR EACH ROW EXECUTE FUNCTION civic_immutable()").format(sql.Identifier(table)))
                conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (1,?)", (now_iso(),))
        else:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)


@contextmanager
def transaction(db_path: Path | None = None) -> Iterator[Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lock_case(conn: Connection, case_id: int) -> None:
    """Serialize mutations of a case without holding a global lock on PostgreSQL."""
    if isinstance(conn, PostgresConnection):
        conn.execute("SELECT id FROM cases WHERE id=? FOR UPDATE", (case_id,)).fetchone()
    elif not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")


def claim_review(case_id: int, seconds: int) -> str | None:
    token = uuid4().hex
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="milliseconds")
    with transaction() as conn:
        # Coordinate ownership changes with the transaction that saves a review.
        lock_case(conn, case_id)
        row = conn.execute("""INSERT INTO review_leases (case_id, token, expires_at) VALUES (?,?,?)
            ON CONFLICT(case_id) DO UPDATE SET token=excluded.token, expires_at=excluded.expires_at
            WHERE review_leases.expires_at < ? RETURNING token""", (case_id, token, expiry, now_iso())).fetchone()
        return row[0] if row else None


def release_review(case_id: int, token: str) -> None:
    with transaction() as conn:
        conn.execute("DELETE FROM review_leases WHERE case_id=? AND token=?", (case_id, token))


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    for key in list(out):
        if key.endswith("_json") and isinstance(out[key], str):
            out[key[:-5]] = json.loads(out.pop(key))
    return out


def audit(conn: Connection, case_id: int | None, event_type: str, actor: str, detail: dict) -> None:
    conn.execute(
        "INSERT INTO audit_events (case_id, event_type, actor, detail_json, created_at) VALUES (?,?,?,?,?)",
        (case_id, event_type, actor, json.dumps(detail, default=str), now_iso()),
    )
