"""FastAPI app for the PCN Review Copilot."""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote, urlsplit
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from .workspace import router as workspace_router
from .access import router as access_router, identity, secret, required
from .email_access import router as email_access_router
from .neon_auth import auth_url, owner_email, public_origin
from pydantic import EmailStr, TypeAdapter

from .ai.adapters import get_adapter
from .config import DATA_DIR, get_settings
from .db import audit, init_db, now_iso, row_to_dict, transaction, lock_case
from .storage import put_evidence, read_evidence
from .mubit_capabilities import CAPABILITIES
from .models import CaseIn, CurateIn, DecisionIn
from .policy import load_policy
from .service import (WorkflowError, case_detail, create_case, curate_feedback, load_case, record_decision,
                      run_ai_review, run_checks)

@asynccontextmanager
async def lifespan(_: FastAPI):
    if (os.getenv("PCN_ENV") == "production" or os.getenv("RENDER")) and len(secret()) < 16:
        raise RuntimeError("Production requires PCN_ACCESS_KEY with at least 16 characters.")
    if os.getenv("RENDER") and not get_settings().database_url:
        raise RuntimeError("Render requires DATABASE_URL so cases survive redeploys.")
    if os.getenv("RENDER") and get_settings().evidence_storage != "database":
        raise RuntimeError("Use PCN_EVIDENCE_STORAGE=database on Render so attachments survive redeploys.")
    if auth_url():
        if len(secret()) < 16 or not get_settings().database_url:
            raise RuntimeError("Neon Auth requires DATABASE_URL and PCN_ACCESS_KEY of at least 16 characters.")
        TypeAdapter(EmailStr).validate_python(owner_email())
        parsed_auth = urlsplit(auth_url())
        parsed_origin = urlsplit(public_origin())
        if parsed_auth.scheme != "https" or not parsed_auth.hostname or parsed_auth.username or parsed_auth.query or parsed_auth.fragment:
            raise RuntimeError("NEON_AUTH_BASE_URL must be the HTTPS Auth URL from Neon.")
        if parsed_origin.scheme not in ("http", "https") or not parsed_origin.hostname or parsed_origin.path or parsed_origin.query or parsed_origin.fragment or parsed_origin.username:
            raise RuntimeError("Set PCN_PUBLIC_ORIGIN to the application's origin, without a path.")
    init_db()
    yield


app = FastAPI(title="PCN Review Copilot", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(access_router)
app.include_router(email_access_router)
app.include_router(workspace_router)


@app.middleware("http")
async def access_gate(request: Request, call_next):
    path = request.url.path
    public_paths = {"/api/session", "/api/session/email/request", "/api/session/email/verify", "/api/health", "/api/ready"}
    if path == "/api/access-requests" and request.method == "POST":
        public_paths.add(path)
    public_paths.update({"/api/access-requests/inspect", "/api/access-requests/approve"})
    if required() and path.startswith("/api/") and path not in public_paths:
        name = await run_in_threadpool(identity, request)
        if not name:
            return JSONResponse({"detail": "Sign in to the workspace."}, status_code=401)
        request.state.reviewer = name
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("origin")
        allowed = {str(request.base_url).rstrip("/"), "http://localhost:5173", "http://127.0.0.1:5173"}
        configured = os.getenv("PCN_PUBLIC_ORIGIN")
        if configured:
            allowed.add(configured.rstrip("/"))
        if os.getenv("RENDER_EXTERNAL_URL"):
            allowed.add(os.environ["RENDER_EXTERNAL_URL"].rstrip("/"))
        if origin and origin not in allowed:
            return JSONResponse({"detail": "Origin is not allowed."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf", "text/plain"}


def get_conn():
    with transaction() as conn:
        yield conn


def _wf(fn, *args):
    try:
        return fn(*args)
    except KeyError:
        raise HTTPException(404, "Not found")
    except WorkflowError as exc:
        raise HTTPException(409, str(exc))


@app.get("/api/health")
def health():
    s = get_settings()
    return {
        "ok": True,
        "database": "postgresql" if s.database_url else "sqlite",
        "evidence_storage": s.evidence_storage,
        "ai_provider": s.ai_provider,
        "model": s.mubit_model if s.ai_provider == "mubit" else "offline-stub-v1",
        "mubit_configured": bool(s.mubit_api_key),
        "mubit_route": s.mubit_route if s.ai_provider == "mubit" else None,
        "mubit_base_url": s.mubit_base_url if s.ai_provider == "mubit" else None,
        "mubit_record": s.mubit_record if s.ai_provider == "mubit" else None,
        "policy_version": load_policy()["policy_version"],
        "ruleset_version": load_policy()["ruleset_version"],
    }


@app.get("/api/ready")
def ready():
    try:
        with transaction() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"ok": True, "database": "postgresql" if get_settings().database_url else "sqlite"}
    except Exception:
        return JSONResponse({"ok": False, "detail": "Database unavailable"}, status_code=503)


@app.get("/api/policy")
def policy():
    return load_policy()


@app.get("/api/mubit/capabilities")
def mubit_capabilities():
    return CAPABILITIES


@app.get("/api/cases")
def list_cases(conn=Depends(get_conn)):
    rows = conn.execute(
        """SELECT c.id, c.pcn_ref, c.status, c.created_at, c.case_json,
                  (SELECT effective_recommendation FROM ai_reviews a WHERE a.case_id=c.id ORDER BY a.id DESC LIMIT 1) AS ai_rec,
                  (SELECT final_outcome FROM decisions d WHERE d.case_id=c.id ORDER BY d.id DESC LIMIT 1) AS outcome
           FROM cases c ORDER BY c.id DESC"""
    ).fetchall()
    out = []
    for r in rows:
        case = json.loads(r["case_json"])
        out.append({"id": r["id"], "pcn_ref": r["pcn_ref"], "status": r["status"], "created_at": r["created_at"],
                    "contravention_code": case["contravention_code"], "location": case["location"],
                    "claimed_grounds": case["claimed_grounds"], "ai_recommendation": r["ai_rec"],
                    "final_outcome": r["outcome"]})
    return out


@app.post("/api/cases", status_code=201)
def create(case: CaseIn, actor: str = Query("intake-officer"), conn=Depends(get_conn)):
    if not case.synthetic:
        raise HTTPException(422, "Use synthetic cases in this demo.")
    case_id = _wf(create_case, conn, case, actor)
    return case_detail(conn, case_id)


@app.post("/api/cases/import")
def import_cases(cases: list[CaseIn], actor: str = Query("intake-officer"), conn=Depends(get_conn)):
    created, skipped = [], []
    for case in cases:
        if not case.synthetic:
            raise HTTPException(422, "Use synthetic cases in this demo.")
        if conn.execute("SELECT 1 FROM cases WHERE pcn_ref=?", (case.pcn_ref,)).fetchone():
            skipped.append(case.pcn_ref)
            continue
        created.append(create_case(conn, case, actor))
    return {"created": created, "skipped_duplicates": skipped}


@app.post("/api/demo/seed")
def seed_demo(conn=Depends(get_conn)):
    raw = json.loads((DATA_DIR / "demo_cases.json").read_text(encoding="utf-8"))
    return import_cases([CaseIn.model_validate(c) for c in raw], "demo-seed", conn)


@app.get("/api/cases/{case_id}")
def get_case(case_id: int, conn=Depends(get_conn)):
    return _wf(case_detail, conn, case_id)


@app.post("/api/cases/{case_id}/checks")
def rerun_checks(case_id: int, actor: str = Query("reviewer"), conn=Depends(get_conn)):
    _wf(run_checks, conn, case_id, actor)
    return case_detail(conn, case_id)


@app.post("/api/cases/{case_id}/ai-review")
def ai_review(case_id: int, mode: Literal["baseline", "precedent"] = "precedent",
              actor: str = Query("reviewer"), conn=Depends(get_conn)):
    s = get_settings()
    try:
        adapter = get_adapter(s)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    _wf(run_ai_review, conn, case_id, adapter, mode, actor, s.precedent_top_k)
    return case_detail(conn, case_id)


@app.post("/api/cases/{case_id}/decision")
def decide(case_id: int, decision: DecisionIn, conn=Depends(get_conn)):
    _wf(record_decision, conn, case_id, decision)
    return case_detail(conn, case_id)


@app.post("/api/cases/{case_id}/evidence/{evidence_id}/file")
async def upload_evidence(case_id: int, evidence_id: str, file: UploadFile = File(...),
                          actor: str = Query("intake-officer"), conn=Depends(get_conn)):
    lock_case(conn, case_id)
    row, case = _wf(load_case, conn, case_id)
    if row["status"] == "decided":
        raise HTTPException(409, "Evidence cannot change after a final decision.")
    item = next((e for e in case.evidence if e.id == evidence_id), None)
    if item is None:
        raise HTTPException(404, "Evidence id not on this case")
    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(415, f"Unsupported type {file.content_type}")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large")
    digest = hashlib.sha256(data).hexdigest()
    stored = put_evidence(conn, case_id, data, file.filename or "upload")
    conn.execute(
        """INSERT INTO evidence_files (case_id, evidence_id, filename, stored_path, sha256, size_bytes, content_type, uploaded_at)
           VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(case_id, evidence_id) DO UPDATE SET filename=excluded.filename,
           stored_path=excluded.stored_path, sha256=excluded.sha256, size_bytes=excluded.size_bytes,
           content_type=excluded.content_type, uploaded_at=excluded.uploaded_at""",
        (case_id, evidence_id, file.filename or "upload", str(stored), digest, len(data), file.content_type, now_iso()),
    )
    item.sha256, item.size_bytes, item.filename = digest, len(data), file.filename
    conn.execute("UPDATE cases SET case_json=?, updated_at=? WHERE id=?", (case.model_dump_json(), now_iso(), case_id))
    audit(conn, case_id, "evidence_file_uploaded", actor,
          {"evidence_id": evidence_id, "sha256": digest, "size_bytes": len(data)})
    run_checks(conn, case_id, actor)
    if row["status"] != "decided":
        conn.execute("UPDATE cases SET status='validated' WHERE id=?", (case_id,))
    return case_detail(conn, case_id)


@app.get("/api/cases/{case_id}/evidence/{evidence_id}/file")
def evidence_file(case_id: int, evidence_id: str, conn=Depends(get_conn)):
    row = conn.execute("SELECT * FROM evidence_files WHERE case_id=? AND evidence_id=?", (case_id, evidence_id)).fetchone()
    if not row:
        raise HTTPException(404, "No file attached. This item contains a description only.")
    try:
        content = read_evidence(conn, row["stored_path"])
    except FileNotFoundError:
        raise HTTPException(404, "Evidence file unavailable.")
    return Response(content, media_type=row["content_type"],
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(row['filename'], safe='')}"})


@app.get("/api/feedback")
def list_feedback(conn=Depends(get_conn)):
    rows = conn.execute(
        """SELECT f.*, c.pcn_ref FROM feedback_examples f LEFT JOIN cases c ON c.id=f.case_id
           WHERE f.source='review' ORDER BY f.id DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/feedback/{feedback_id}/curate")
def curate(feedback_id: int, body: CurateIn, conn=Depends(get_conn)):
    _wf(curate_feedback, conn, feedback_id, body)
    return dict(conn.execute("SELECT * FROM feedback_examples WHERE id=?", (feedback_id,)).fetchone())


@app.get("/api/audit")
def audit_log(limit: int = 200, conn=Depends(get_conn)):
    return [row_to_dict(r) for r in conn.execute(
        "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (min(limit, 1000),))]


@app.get("/api/evaluations")
def evaluations(conn=Depends(get_conn)):
    return [row_to_dict(r) for r in conn.execute("SELECT * FROM evaluation_runs ORDER BY id DESC LIMIT 20")]


# Docker serves the built UI and API from one origin. Vite proxies /api in development.
FRONTEND_DIST = Path(os.getenv("PCN_FRONTEND_DIST", str(Path(__file__).resolve().parents[2] / "frontend" / "dist")))
if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIST / "index.html", headers={"Cache-Control": "no-store"})
