import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PCN_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("PCN_EVIDENCE_DIR", str(tmp_path / "evidence"))
    monkeypatch.setenv("AI_PROVIDER", "stub")
    for name in list(os.environ):
        if name.startswith("MUBIT_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("PCN_ACCESS_KEY", raising=False)
    monkeypatch.delenv("PCN_ENV", raising=False)
    monkeypatch.delenv("PCN_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PCN_DB_SCHEMA", raising=False)
    monkeypatch.delenv("PCN_EVIDENCE_STORAGE", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("PCN_EMAIL_FROM", raising=False)
    for name in ("NEON_AUTH_BASE_URL", "PCN_ACCESS_REQUEST_EMAIL", "PCN_ALLOW_PASSWORD_LOGIN", "PCN_PUBLIC_ORIGIN", "RENDER_EXTERNAL_URL"):
        monkeypatch.delenv(name, raising=False)
    test_url = os.getenv("PCN_TEST_DATABASE_URL")
    schema = f"civic_test_{uuid4().hex}"
    if test_url:
        monkeypatch.setenv("DATABASE_URL", test_url)
        monkeypatch.setenv("PCN_DB_SCHEMA", schema)
        monkeypatch.setenv("PCN_EVIDENCE_STORAGE", "database")
    yield
    if test_url:
        import psycopg
        from psycopg import sql
        with psycopg.connect(test_url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
def demo_cases():
    return json.loads((ROOT / "data" / "demo_cases.json").read_text(encoding="utf-8"))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
