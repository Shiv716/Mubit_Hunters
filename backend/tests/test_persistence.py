import hashlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.config import get_settings
from app.db import claim_review, release_review, init_db, now_iso, transaction
from app.models import CaseIn, DecisionIn
from app.service import create_case, record_decision, WorkflowError
from app.storage import put_evidence
from migrate_sqlite import migrate


def test_database_attachments_survive_local_disk_change_and_rollback(client, demo_cases, monkeypatch, tmp_path):
    monkeypatch.setenv("PCN_EVIDENCE_STORAGE", "database")
    cid = client.post("/api/cases", json=demo_cases[0]).json()["id"]
    url = f"/api/cases/{cid}/evidence/E1/file"
    content = b"Synthetic shared evidence"
    assert client.post(url, files={"file": ("note.txt", content, "text/plain")}).status_code == 200
    monkeypatch.setenv("PCN_EVIDENCE_DIR", str(tmp_path / "different-server"))
    assert client.get(url).content == content
    with pytest.raises(RuntimeError):
        with transaction() as conn:
            key = put_evidence(conn, cid, b"rolled back", "note.txt")
            raise RuntimeError("Abort transaction")
    with transaction() as conn:
        assert conn.execute("SELECT 1 FROM evidence_blobs WHERE storage_key=?", (key,)).fetchone() is None


def test_review_claim_is_shared_and_only_its_owner_can_release(client, demo_cases):
    cid = client.post("/api/cases", json=demo_cases[0]).json()["id"]
    token = claim_review(cid, 60)
    assert token
    assert claim_review(cid, 60) is None
    release_review(cid, "different-worker")
    assert claim_review(cid, 60) is None
    release_review(cid, token)
    assert claim_review(cid, 60)


def test_postgres_serializes_competing_final_decisions(client, demo_cases):
    if not get_settings().database_url:
        pytest.skip("PostgreSQL concurrency check")
    cid = client.post("/api/cases", json=demo_cases[0]).json()["id"]
    barrier = Barrier(2)
    def decide():
        barrier.wait()
        try:
            with transaction() as conn:
                record_decision(conn, cid, DecisionIn(action="reject", final_outcome="representation_accepted",
                                                     reason="Manual review", reviewer="Test officer"))
            return "saved"
        except WorkflowError:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(lambda _: decide(), range(2))) == ["conflict", "saved"]
    assert len(client.get(f"/api/cases/{cid}").json()["decisions"]) == 1


def test_sqlite_import_preserves_records_files_and_id_sequences(client, demo_cases, tmp_path):
    if not get_settings().database_url:
        pytest.skip("PostgreSQL migration check")
    source = tmp_path / "old.db"
    evidence_dir = tmp_path / "old-evidence"
    init_db(source)
    content = b"Existing synthetic attachment"
    digest = hashlib.sha256(content).hexdigest()
    with transaction(source) as conn:
        cid = create_case(conn, CaseIn.model_validate(demo_cases[0]), "source-officer")
        folder = evidence_dir / str(cid)
        folder.mkdir(parents=True)
        (folder / digest).write_bytes(content)
        conn.execute("INSERT INTO evidence_files (case_id,evidence_id,filename,stored_path,sha256,size_bytes,content_type,uploaded_at) "
                     "VALUES (?,?,?,?,?,?,?,?)", (cid, "E1", "note.txt", f"/data/evidence/{cid}/{digest}", digest, len(content), "text/plain", now_iso()))
    assert migrate(source, evidence_dir)["cases"] == 1
    assert client.get("/api/queue").json() == []  # Preview cannot write destination data.
    migrate(source, evidence_dir, apply=True)
    assert client.get(f"/api/cases/{cid}/evidence/E1/file").content == content
    assert client.get(f"/api/cases/{cid}").json()["audit"][0]["actor"] == "source-officer"
    next_id = client.post("/api/cases", json=demo_cases[1]).json()["id"]
    assert next_id > cid
    with pytest.raises(ValueError, match="Destination contains data"):
        migrate(source, evidence_dir, apply=True)
