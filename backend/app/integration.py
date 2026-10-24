"""Versioned council exchange contract. One council/system per isolated workspace.

The supplier connector pushes full case snapshots and pulls approved results.
Only its explicit receipt marks a result received; downloading never does.
"""
import base64
import binascii
import hashlib
import hmac
import json
import os

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .access import require_owner, required
from .config import DATA_DIR, get_settings
from .db import PostgresConnection, audit, lock_case, now_iso, transaction
from .models import CaseIn
from .policy import load_policy
from .service import WorkflowError, create_case, load_case, run_checks
from .storage import put_evidence

router = APIRouter(prefix="/api/integration")
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PACKAGE_BYTES = 20 * 1024 * 1024
FILE_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf", "text/plain"}


def configuration():
    return {"council_id": os.getenv("PCN_COUNCIL_ID", "northgate-sandbox"),
            "council_name": os.getenv("PCN_COUNCIL_NAME", "Northgate Borough"),
            "source_system": os.getenv("PCN_CASE_SYSTEM", "generic")}


def check_machine_key(request):
    key = os.getenv("PCN_INTEGRATION_KEY", "")
    if len(key) < 32:
        raise HTTPException(503, "The council connector is not enabled. Configure PCN_INTEGRATION_KEY (at least 32 characters).")
    supplied = request.headers.get("authorization", "")
    if not hmac.compare_digest(supplied.encode(), f"Bearer {key}".encode()):
        raise HTTPException(401, "Invalid council connector credential.")


def verify_identity(conn):
    identity = conn.execute("SELECT council_id,source_system FROM integration_identity WHERE id=1").fetchone()
    config = configuration()
    if identity and (identity["council_id"], identity["source_system"]) != (config["council_id"], config["source_system"]):
        raise HTTPException(409, "This workspace is already bound to a different council/system. Use a separate workspace and database schema.")


class Attachment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str = Field(min_length=1, max_length=20)
    filename: str = Field(min_length=1, max_length=200, pattern=r"^[^/\\]+$")
    content_type: str
    content_base64: str = Field(max_length=14 * 1024 * 1024)


class CasePackage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(default=1, ge=1, le=1)
    council_id: str = Field(min_length=1, max_length=100)
    source_system: str = Field(min_length=1, max_length=100)
    source_case_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9._:-]+$")
    source_version: int = Field(ge=1)
    case: CaseIn
    attachments: list[Attachment] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def evidence_ids(self):
        evidence = [e.id for e in self.case.evidence]
        attached = [a.evidence_id for a in self.attachments]
        if len(set(evidence)) != len(evidence) or len(set(attached)) != len(attached):
            raise ValueError("Evidence IDs must be unique within the case and attachments.")
        if not set(attached).issubset(evidence):
            raise ValueError("Every attachment must reference an evidence item in the case.")
        return self


class Receipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    receipt_id: str = Field(min_length=1, max_length=200)
    source_case_id: str = Field(min_length=1, max_length=100)
    source_version: int = Field(ge=1)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def import_package(body, actor):
    config = configuration()
    if (body.council_id, body.source_system) != (config["council_id"], config["source_system"]):
        raise HTTPException(409, "The package council/system does not match this workspace.")
    if not body.case.synthetic:
        raise HTTPException(422, "This integration sandbox accepts synthetic cases only. A live council rollout requires its approved policy and supplier connection.")
    files, total = [], 0
    for attachment in body.attachments:
        if attachment.content_type not in FILE_TYPES:
            raise HTTPException(415, "Unsupported evidence file type.")
        try:
            content = base64.b64decode(attachment.content_base64, validate=True)
        except (ValueError, binascii.Error):
            raise HTTPException(422, "Attachment content must be valid base64.") from None
        total += len(content)
        if len(content) > MAX_FILE_BYTES or total > MAX_PACKAGE_BYTES:
            raise HTTPException(413, "Evidence limit: 10 MiB per file and 20 MiB per package.")
        files.append((attachment, content))
    payload_hash = digest(body.model_dump(mode="json"))
    case = body.case.model_copy(deep=True)
    for evidence in case.evidence:
        evidence.filename = evidence.sha256 = evidence.size_bytes = None
    try:
        with transaction() as conn:
            # Serialize source IDs and PCN uniqueness, including first-time imports.
            if isinstance(conn, PostgresConnection):
                conn.execute("SELECT pg_advisory_xact_lock(hashtext(?))", ("civic-integration-import",))
            else:
                conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO integration_identity (id,council_id,source_system) VALUES (1,?,?) ON CONFLICT(id) DO NOTHING",
                         (body.council_id, body.source_system))
            verify_identity(conn)
            linked = conn.execute("SELECT * FROM integration_cases WHERE source_case_id=?", (body.source_case_id,)).fetchone()
            if linked:
                cid = linked["case_id"]
                lock_case(conn, cid)
                if body.source_version == linked["source_version"] and payload_hash == linked["payload_hash"]:
                    return {"case_id": cid, "source_version": body.source_version, "status": "unchanged"}
                if body.source_version <= linked["source_version"]:
                    raise HTTPException(409, "This source version is stale or was already used with different content.")
                row, existing = load_case(conn, cid)
                if row["status"] == "decided":
                    raise HTTPException(409, "A final decision already exists. Reconcile this case in the council system.")
                if existing.pcn_ref != case.pcn_ref:
                    raise HTTPException(409, "A source case cannot change its PCN reference.")
                if digest(existing.model_dump(mode="json")) != linked["case_hash"]:
                    raise HTTPException(409, "Evidence was changed in Civic. Reconcile it before replacing the source snapshot.")
            else:
                cid = create_case(conn, case, actor)
            # A new source version is a complete snapshot, including every attachment.
            conn.execute("DELETE FROM evidence_files WHERE case_id=?", (cid,))
            for attachment, content in files:
                evidence = next(e for e in case.evidence if e.id == attachment.evidence_id)
                evidence.filename = attachment.filename
                evidence.sha256 = hashlib.sha256(content).hexdigest()
                evidence.size_bytes = len(content)
                stored = put_evidence(conn, cid, content, attachment.filename)
                conn.execute("""INSERT INTO evidence_files
                    (case_id,evidence_id,filename,stored_path,sha256,size_bytes,content_type,uploaded_at)
                    VALUES (?,?,?,?,?,?,?,?)""", (cid, evidence.id, attachment.filename, stored,
                    evidence.sha256, len(content), attachment.content_type, now_iso()))
            conn.execute("UPDATE cases SET case_json=?,status='validated',updated_at=? WHERE id=?",
                         (case.model_dump_json(), now_iso(), cid))
            run_checks(conn, cid, actor)
            conn.execute("""INSERT INTO integration_cases
                (case_id,source_case_id,source_version,payload_hash,case_hash,imported_at) VALUES (?,?,?,?,?,?)
                ON CONFLICT(case_id) DO UPDATE SET source_version=excluded.source_version,
                    payload_hash=excluded.payload_hash,case_hash=excluded.case_hash,imported_at=excluded.imported_at""",
                (cid, body.source_case_id, body.source_version, payload_hash, digest(case.model_dump(mode="json")), now_iso()))
            audit(conn, cid, "council_case_imported", actor, {"source_case_id": body.source_case_id,
                  "source_version": body.source_version, "attachments": len(files)})
            return {"case_id": cid, "source_version": body.source_version, "status": "updated" if linked else "created"}
    except WorkflowError as exc:
        raise HTTPException(409, str(exc)) from None


def result_rows(conn, *, pending=False, decision_id=None, limit=100):
    verify_identity(conn)
    where = " AND r.decision_id IS NULL" if pending else ""
    params = []
    if decision_id is not None:
        where += " AND d.id=?"
        params.append(decision_id)
    params.append(limit)
    rows = conn.execute("""SELECT d.id AS decision_id,d.final_outcome,d.final_response,d.reason,d.reviewer,
        d.created_at AS decided_at,i.source_case_id,i.source_version,c.pcn_ref,a.model,a.provider_request_id,
        a.id AS ai_review_id,a.effective_recommendation AS ai_recommendation,k.policy_version,k.ruleset_version,
        r.receipt_id,r.received_at FROM decisions d JOIN integration_cases i ON i.case_id=d.case_id
        JOIN cases c ON c.id=d.case_id JOIN ai_reviews a ON a.id=d.ai_review_id JOIN checks k ON k.id=a.check_id
        LEFT JOIN integration_receipts r ON r.decision_id=d.id
        WHERE d.final_outcome!='escalated' AND a.provider='mubit' AND a.status!='failed'""" + where +
        (" ORDER BY d.id LIMIT ?" if pending else " ORDER BY d.id DESC LIMIT ?"), params).fetchall()
    config = configuration()
    return [{"schema_version": 1, "council_id": config["council_id"], "source_system": config["source_system"],
             **dict(row), "ai_provider": "mubit", "delivery_status": "received" if row["received_at"] else "awaiting_receipt"} for row in rows]


@router.post("/v1/cases")
def ingest(body: CasePackage):
    return import_package(body, "council-connector")


@router.get("/v1/results")
def pending_results(limit: int = Query(100, ge=1, le=200)):
    with transaction() as conn:
        return {"results": result_rows(conn, pending=True, limit=limit)}


@router.post("/v1/results/{decision_id}/receipt")
def receive_result(decision_id: int, body: Receipt):
    with transaction() as conn:
        rows = result_rows(conn, decision_id=decision_id)
        if not rows:
            raise HTTPException(404, "No exportable decision found.")
        row = rows[0]
        if (body.source_case_id, body.source_version) != (row["source_case_id"], row["source_version"]):
            raise HTTPException(409, "The receipt does not match the result's source case and version.")
        saved = conn.execute("""INSERT INTO integration_receipts (decision_id,receipt_id,received_at) VALUES (?,?,?)
            ON CONFLICT(decision_id) DO NOTHING RETURNING decision_id""", (decision_id, body.receipt_id, now_iso())).fetchone()
        if saved:
            audit(conn, None, "council_result_received", "council-connector", {"decision_id": decision_id, "receipt_id": body.receipt_id})
        elif conn.execute("SELECT receipt_id FROM integration_receipts WHERE decision_id=?", (decision_id,)).fetchone()[0] != body.receipt_id:
            raise HTTPException(409, "A different receipt is already recorded for this decision.")
        return {"decision_id": decision_id, "delivery_status": "received"}


@router.get("/status")
def status():
    with transaction() as conn:
        verify_identity(conn)
        cases = [dict(r) for r in conn.execute("""SELECT i.source_case_id,i.source_version,i.imported_at,
            c.id AS case_id,c.pcn_ref,c.status FROM integration_cases i JOIN cases c ON c.id=i.case_id
            ORDER BY i.imported_at DESC LIMIT 100""")]
        results = [{key: value for key, value in row.items() if key not in ("final_response", "reason")}
                   for row in result_rows(conn)]
    s = get_settings()
    return {**configuration(), "synthetic_only": True, "connector_enabled": len(os.getenv("PCN_INTEGRATION_KEY", "")) >= 32,
            "mubit_ready": s.ai_provider == "mubit" and bool(s.mubit_api_key),
            "cases": cases, "results": results, "policy_version": load_policy()["policy_version"]}


@router.get("/sample")
def sample_package():
    case = json.loads((DATA_DIR / "demo_cases.json").read_text())[0]
    case["pcn_ref"] = "CONNECT-0001"
    case["evidence"].append({"id": "E3", "type": "other", "source": "council",
                             "description": "Synthetic note for connector testing"})
    config = configuration()
    return JSONResponse({"schema_version": 1, "council_id": config["council_id"], "source_system": config["source_system"],
        "source_case_id": "example-001", "source_version": 1, "case": case,
        "attachments": [{"evidence_id": "E3", "filename": "synthetic-note.txt", "content_type": "text/plain",
                         "content_base64": base64.b64encode(b"Synthetic evidence for connector testing only.").decode()}]},
        headers={"Content-Disposition": 'attachment; filename="civic-council-package.json"'})


@router.post("/test-import")
def test_import(body: CasePackage, request: Request):
    actor = require_owner(request) if required() else "local-connector-test"
    return import_package(body, actor)


@router.get("/export")
def export_results():
    with transaction() as conn:
        return JSONResponse({"results": result_rows(conn)},
            headers={"Content-Disposition": 'attachment; filename="civic-approved-results.json"'})
