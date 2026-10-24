"""Copy an existing SQLite workspace into an empty PostgreSQL Civic schema.

Preview: python backend/migrate_sqlite.py --source-db /path/civic.db --evidence-dir /path/evidence
Apply: append --apply. DATABASE_URL is read from the environment / .env, never a CLI argument.
The source is opened read-only. Missing or changed attachments abort the import.
"""
import argparse
import hashlib
import sqlite3
from pathlib import Path

from psycopg import sql

from app.config import get_settings
from app.db import PostgresConnection, init_db, transaction

TABLES = ("cases", "checks", "ai_reviews", "decisions", "feedback_examples", "audit_events",
          "evaluation_runs", "investigations", "evidence_files", "evidence_blobs")


def migrate(source_db: Path, evidence_dir: Path, apply: bool = False):
    if not get_settings().database_url:
        raise ValueError("Set DATABASE_URL to the destination PostgreSQL database.")
    source = sqlite3.connect(source_db.resolve().as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        source.execute("BEGIN")
        existing = {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "cases" not in existing:
            raise ValueError("The source is not a Civic database.")
        rows = {table: [dict(r) for r in source.execute(f'SELECT * FROM "{table}"')] if table in existing else []
                for table in TABLES}
        blobs = {r["storage_key"]: bytes(r["content"]) for r in rows["evidence_blobs"]}
        for row in rows["evidence_files"]:
            if row["stored_path"].startswith("db:"):
                content = blobs.get(row["stored_path"])
                if content is None:
                    raise ValueError("An attachment is missing from the source database.")
            else:
                # Resolve against the supplied export folder, including files exported from Docker /data.
                path = evidence_dir.resolve() / str(row["case_id"]) / Path(row["stored_path"]).name
                if not path.resolve().is_relative_to(evidence_dir.resolve()):
                    raise ValueError("Invalid evidence path.")
                content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != row["sha256"]:
                raise ValueError("An attachment does not match its recorded checksum.")
            key = f"db:{row['case_id']}/{row['sha256']}"
            blobs[key] = content
            row["stored_path"] = key
        rows["evidence_blobs"] = [{"storage_key": k, "content": v} for k, v in blobs.items()]
        counts = {table: len(values) for table, values in rows.items()}
        if not apply:
            return counts
        init_db()
        with transaction() as target:
            if not isinstance(target, PostgresConnection):
                raise ValueError("Destination must be PostgreSQL.")
            # Block writes for the short import; never merge into a nonempty workspace.
            target.raw.execute(sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(
                sql.SQL(",").join(map(sql.Identifier, TABLES))))
            if any(target.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone() for table in TABLES):
                raise ValueError("Destination contains data. Import only into an empty Civic schema.")
            for table in TABLES:
                for row in rows[table]:
                    statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, row)),
                        sql.SQL(",").join(sql.Placeholder() for _ in row))
                    target.raw.execute(statement, tuple(row.values()))
                if table != "evidence_blobs":
                    qualified = f"{get_settings().db_schema}.{table}"
                    target.execute("SELECT setval(pg_get_serial_sequence(?, 'id'), "
                                   f"COALESCE((SELECT MAX(id) FROM {table}),1), "
                                   f"EXISTS(SELECT 1 FROM {table}))", (qualified,))
        return counts
    finally:
        source.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = migrate(args.source_db, args.evidence_dir, args.apply)
        print("Imported" if args.apply else "Preview only", result)
    except Exception as exc:
        # Avoid printing provider exceptions that might contain connection details.
        print("Import stopped:", str(exc) if isinstance(exc, (ValueError, FileNotFoundError)) else type(exc).__name__)
        raise SystemExit(1)
