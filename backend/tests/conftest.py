import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PCN_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("PCN_EVIDENCE_DIR", str(tmp_path / "evidence"))
    monkeypatch.setenv("AI_PROVIDER", "stub")
    monkeypatch.delenv("MUBIT_API_KEY", raising=False)


@pytest.fixture
def demo_cases():
    return json.loads((ROOT / "data" / "demo_cases.json").read_text(encoding="utf-8"))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
