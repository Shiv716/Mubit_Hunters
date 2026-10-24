"""Private driver cases and user-controlled appeal preparation. No portal submission."""
import io
import json
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import consumer_ai
from .consumer_auth import require_driver
from .db import PostgresConnection, now_iso, transaction
from .email_access import digest, quota
from .parking import snapshot

router = APIRouter(prefix="/api/consumer", tags=["driver cases"])


class Facts(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    issuer_kind: Literal["council", "private", "unknown", "other"] = "unknown"
    region: Literal["England", "Other"] = "England"
    issuer: str = Field(default="", max_length=200)
    ticket_ref: str = Field(default="", max_length=100)
    vehicle_registration: str = Field(default="", max_length=30)
    location: str = Field(default="", max_length=250)
    incident_date: date | None = None
    issue_date: date | None = None
    date_received: date | None = None
    amount_pounds: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)
    deadline: date | None = None
    discount_deadline: date | None = None
    notice_stage: Literal["initial", "notice_to_owner", "rejection", "debt_collection", "court", "unknown"] = "initial"
    capacity: Literal["driver", "keeper", "both", "unsure"] = "unsure"
    narrative: str = Field(default="", max_length=12000)
    appeal_url: str = Field(default="", max_length=500)

    @field_validator("appeal_url")
    @classmethod
    def portal(cls, value):
        if value:
            try:
                parsed = urlsplit(value)
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in value):
                    raise ValueError()
            except ValueError:
                raise ValueError("Use the full HTTPS appeal link printed on the notice.") from None
        return value


class Update(BaseModel):
    facts: Facts
    version: int = Field(ge=0)
    confirmed: bool
    ai_consent: bool = False
    training_consent: bool = False


class Draft(BaseModel):
    text: str = Field(min_length=20, max_length=15000)
    review_id: str
    approved: bool


class Submitted(BaseModel):
    reference: str = Field(min_length=1, max_length=200)
    submitted_on: date


class Outcome(BaseModel):
    outcome: Literal["cancelled", "rejected", "paid", "refunded"]
    refund_pounds: float = Field(default=0, ge=0, le=10000, allow_inf_nan=False)
    note: str = Field(default="", max_length=2000)


def event(conn, case_id, kind, detail):
    conn.execute("INSERT INTO driver_events (id,case_id,event,detail_json,created_at) VALUES (?,?,?,?,?)",
                 (uuid4().hex, case_id, kind, json.dumps(detail), now_iso()))


def own(conn, case_id, owner, lock=False):
    if lock and not isinstance(conn, PostgresConnection) and not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    suffix = " FOR UPDATE" if lock and isinstance(conn, PostgresConnection) else ""
    row = conn.execute("SELECT * FROM driver_cases WHERE id=? AND owner_id=?" + suffix, (case_id, owner)).fetchone()
    if not row:
        raise HTTPException(404, "Appeal not found.")
    return dict(row)


def detail(conn, row):
    row = dict(row)
    row.pop("owner_id", None)
    row["facts"] = Facts.model_validate_json(row.pop("facts_json")).model_dump(mode="json")
    row["evidence"] = [dict(e) for e in conn.execute("SELECT id,kind,filename,size_bytes,created_at FROM driver_evidence WHERE case_id=? ORDER BY created_at", (row["id"],)).fetchall()]
    review = conn.execute("SELECT * FROM driver_reviews WHERE case_id=? AND kind='assessment' ORDER BY created_at DESC LIMIT 1", (row["id"],)).fetchone()
    row["assessment"] = {**dict(review), "output": json.loads(review["output_json"]), "stale": review["input_version"] != row["version"]} if review else None
    if row["assessment"]:
        row["assessment"].pop("output_json")
    row["events"] = [{"id": e["id"], "event": e["event"], "detail": json.loads(e["detail_json"]), "created_at": e["created_at"]}
        for e in conn.execute("SELECT * FROM driver_events WHERE case_id=? ORDER BY created_at DESC", (row["id"],)).fetchall()]
    return row


@router.get("/public")
def public_info():
    guide = consumer_ai.knowledge()
    with transaction() as conn:
        assisted = conn.execute("SELECT COUNT(DISTINCT case_id) FROM driver_reviews WHERE kind='assessment'").fetchone()[0]
        verified = conn.execute("SELECT COUNT(*) FROM driver_cases WHERE outcome_verified=1 AND outcome IN ('cancelled','refunded')").fetchone()[0]
    return {"assessed_cases": assisted, "verified_successes": verified, "parking_locations": len(snapshot()["places"]),
            "source_count": len(guide["sources"]), "knowledge": guide,
            "coverage": "England appeal preparation · London parking map", "automatic_submission": False}


@router.get("/cases")
def cases(owner=Depends(require_driver)):
    with transaction() as conn:
        rows = conn.execute("SELECT id,facts_json,status,outcome,created_at,updated_at FROM driver_cases WHERE owner_id=? ORDER BY updated_at DESC LIMIT 200", (owner,)).fetchall()
    return [{key: value for key, value in {**dict(row), "facts": json.loads(row["facts_json"])}.items() if key != "facts_json"} for row in rows]


@router.post("/cases", status_code=201)
def create(owner=Depends(require_driver)):
    quota(f"driver-create:{digest(owner)}", 20, 86400)
    case_id, now = uuid4().hex, now_iso()
    with transaction() as conn:
        conn.execute("INSERT INTO driver_cases (id,owner_id,facts_json,created_at,updated_at) VALUES (?,?,?,?,?)",
                     (case_id, owner, Facts().model_dump_json(), now, now))
        event(conn, case_id, "created", {})
        return detail(conn, own(conn, case_id, owner))


@router.get("/cases/{case_id}")
def read(case_id: str, owner=Depends(require_driver)):
    with transaction() as conn:
        return detail(conn, own(conn, case_id, owner))


@router.put("/cases/{case_id}")
def update(case_id: str, body: Update, owner=Depends(require_driver)):
    if body.training_consent and not body.ai_consent:
        raise HTTPException(422, "Allow AI processing before choosing optional training use.")
    if body.confirmed and (not body.facts.issuer or not body.facts.ticket_ref):
        raise HTTPException(422, "Confirm the issuer and ticket reference from your notice.")
    with transaction() as conn:
        row = own(conn, case_id, owner, lock=True)
        if row["version"] != body.version:
            raise HTTPException(409, "This appeal changed in another tab. Reload it before saving.")
        conn.execute("""UPDATE driver_cases SET facts_json=?,version=version+1,confirmed=?,ai_consent=?,training_consent=?,draft_approved=0,
            status=CASE WHEN status='assessed' THEN 'preparing' ELSE status END,updated_at=? WHERE id=? AND owner_id=?""",
            (body.facts.model_dump_json(), int(body.confirmed), int(body.ai_consent), int(body.training_consent), now_iso(), case_id, owner))
        if bool(row["training_consent"]) != body.training_consent:
            event(conn, case_id, "training_consent_changed", {"allowed": body.training_consent,
                "notice_version": "consumer-training-v1", "case_version": row["version"] + 1})
        event(conn, case_id, "details_saved", {"confirmed": body.confirmed})
        return detail(conn, own(conn, case_id, owner))


@router.delete("/cases/{case_id}")
def delete(case_id: str, owner=Depends(require_driver)):
    with transaction() as conn:
        own(conn, case_id, owner, lock=True)
        conn.execute("DELETE FROM driver_cases WHERE id=? AND owner_id=?", (case_id, owner))
    return {"deleted": True}


@router.post("/cases/{case_id}/evidence", status_code=201)
def upload(case_id: str, file: UploadFile = File(...), kind: Literal["ticket", "payment", "signage", "permit", "other"] = Form("ticket"), owner=Depends(require_driver)):
    with transaction() as conn:
        own(conn, case_id, owner)
    content = file.file.read(8 * 1024 * 1024 + 1)
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(413, "Choose a photo smaller than 8 MB.")
    content = consumer_ai.image_bytes(content)
    evidence_id = uuid4().hex
    with transaction() as conn:
        own(conn, case_id, owner, lock=True)
        if conn.execute("SELECT COUNT(*) FROM driver_evidence WHERE case_id=?", (case_id,)).fetchone()[0] >= 8:
            raise HTTPException(422, "Each appeal supports up to eight photos. Remove an old photo before adding another.")
        filename = (Path(file.filename or "photo").stem[:80] or "photo") + ".jpg"
        conn.execute("INSERT INTO driver_evidence (id,case_id,kind,filename,content_type,content,size_bytes,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (evidence_id, case_id, kind, filename, "image/jpeg", content, len(content), now_iso()))
        conn.execute("UPDATE driver_cases SET version=version+1,draft_approved=0,updated_at=? WHERE id=?", (now_iso(), case_id))
        event(conn, case_id, "evidence_added", {"kind": kind, "evidence_id": evidence_id})
        return detail(conn, own(conn, case_id, owner))


@router.get("/cases/{case_id}/evidence/{evidence_id}")
def image(case_id: str, evidence_id: str, owner=Depends(require_driver)):
    with transaction() as conn:
        own(conn, case_id, owner)
        row = conn.execute("SELECT content FROM driver_evidence WHERE case_id=? AND id=?", (case_id, evidence_id)).fetchone()
    if not row:
        raise HTTPException(404, "Photo not found.")
    return Response(bytes(row["content"]), media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


@router.delete("/cases/{case_id}/evidence/{evidence_id}")
def remove_image(case_id: str, evidence_id: str, owner=Depends(require_driver)):
    with transaction() as conn:
        own(conn, case_id, owner, lock=True)
        if not conn.execute("DELETE FROM driver_evidence WHERE case_id=? AND id=? RETURNING id", (case_id, evidence_id)).fetchone():
            raise HTTPException(404, "Photo not found.")
        conn.execute("UPDATE driver_cases SET version=version+1,draft_approved=0,updated_at=? WHERE id=?", (now_iso(), case_id))
        event(conn, case_id, "evidence_removed", {})
        return detail(conn, own(conn, case_id, owner))


@router.post("/cases/{case_id}/{action}")
def run(case_id: str, action: Literal["scan", "assess"], owner=Depends(require_driver)):
    # Fixed action route: more specific POST routes are declared on a separate prefix below.
    quota(f"driver-ai:{digest(owner)}", 20, 3600)
    quota("driver-ai:global", 200, 3600)
    token = uuid4().hex
    with transaction() as conn:
        row = own(conn, case_id, owner, lock=True)
        if not row["ai_consent"]:
            raise HTTPException(422, "Allow Mubit to read this ticket and evidence before continuing.")
        facts = Facts.model_validate_json(row["facts_json"]).model_dump(mode="json")
        if action == "assess":
            if not row["confirmed"] or len(facts["narrative"]) < 20:
                raise HTTPException(422, "Confirm your ticket details and explain what happened in at least 20 characters.")
            if facts["region"] != "England" or facts["issuer_kind"] not in ("private", "council"):
                raise HTTPException(422, "This release supports England council parking PCNs and private parking charges. Check your notice type or seek specialist help.")
        images = [dict(e) for e in conn.execute("SELECT * FROM driver_evidence WHERE case_id=? ORDER BY created_at", (case_id,)).fetchall()]
        if action == "scan":
            images = [e for e in images if e["kind"] == "ticket"]
            if not images:
                raise HTTPException(422, "Add a ticket photo first.")
        claimed = conn.execute("""INSERT INTO driver_jobs (case_id,token,expires_at) VALUES (?,?,?)
            ON CONFLICT(case_id) DO UPDATE SET token=excluded.token,expires_at=excluded.expires_at
            WHERE driver_jobs.expires_at<? RETURNING token""", (case_id, token, int(time.time())+180, int(time.time()))).fetchone()
        if not claimed:
            raise HTTPException(409, "This appeal is already being read. Wait for the current request to finish.")
        allow_training = bool(row["training_consent"])
        recording = consumer_ai.recording_mode(allow_training)
        event(conn, case_id, "ai_recording_requested", {"action": action, "recording": recording,
            "training_consent": allow_training, "case_version": row["version"]})
    try:
        output, result = (consumer_ai.scan(images, allow_training=allow_training) if action == "scan"
            else consumer_ai.assess(facts, images, allow_training=allow_training))
        with transaction() as conn:
            current = own(conn, case_id, owner, lock=True)
            if current["version"] != row["version"]:
                raise HTTPException(409, "The evidence changed while Mubit was working. Run it again using the latest details.")
            review_id = uuid4().hex
            conn.execute("INSERT INTO driver_reviews (id,case_id,input_version,kind,output_json,provider,model,request_id,recording_requested,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (review_id, case_id, row["version"], "scan" if action == "scan" else "assessment", json.dumps(output), result.provider, result.model, result.request_id, recording, now_iso()))
            if action == "assess":
                conn.execute("UPDATE driver_cases SET draft_text=?,draft_review_id=?,draft_approved=0,status=CASE WHEN status='preparing' THEN 'assessed' ELSE status END,updated_at=? WHERE id=?",
                    (output["draft_letter"], review_id, now_iso(), case_id))
            event(conn, case_id, "ticket_scanned" if action == "scan" else "assessed", {"provider": result.provider, "model": result.model})
            return {"extracted": output, "case": detail(conn, current)} if action == "scan" else detail(conn, own(conn, case_id, owner))
    finally:
        with transaction() as conn:
            conn.execute("DELETE FROM driver_jobs WHERE case_id=? AND token=?", (case_id, token))


# Multi-segment routes avoid colliding with the two AI actions above.
@router.put("/cases/{case_id}/draft")
def save_draft(case_id: str, body: Draft, owner=Depends(require_driver)):
    with transaction() as conn:
        row = own(conn, case_id, owner, lock=True)
        review = conn.execute("SELECT * FROM driver_reviews WHERE case_id=? AND id=? AND kind='assessment'", (case_id, body.review_id)).fetchone()
        if not review or review["input_version"] != row["version"] or row["draft_review_id"] != body.review_id:
            raise HTTPException(409, "Get a current assessment before approving a draft.")
        if json.loads(review["output_json"])["verdict"] == "specialist_help":
            raise HTTPException(422, "This stage needs specialist advice rather than an initial appeal draft.")
        conn.execute("UPDATE driver_cases SET draft_text=?,draft_approved=?,updated_at=? WHERE id=?", (body.text, int(body.approved), now_iso(), case_id))
        event(conn, case_id, "draft_approved" if body.approved else "draft_saved", {})
        return detail(conn, own(conn, case_id, owner))


@router.post("/cases/{case_id}/tracking/submitted")
def submitted(case_id: str, body: Submitted, owner=Depends(require_driver)):
    if body.submitted_on > date.today() or not body.reference.strip():
        raise HTTPException(422, "Enter the actual submission date and confirmation reference.")
    with transaction() as conn:
        row = own(conn, case_id, owner, lock=True)
        if not row["draft_approved"]:
            raise HTTPException(409, "Review and approve your current draft first.")
        conn.execute("UPDATE driver_cases SET status='submitted',updated_at=? WHERE id=?", (now_iso(), case_id))
        event(conn, case_id, "submission_reported", body.model_dump(mode="json"))
        return detail(conn, own(conn, case_id, owner))


@router.post("/cases/{case_id}/tracking/outcome")
def outcome(case_id: str, body: Outcome, owner=Depends(require_driver)):
    with transaction() as conn:
        own(conn, case_id, owner, lock=True)
        conn.execute("UPDATE driver_cases SET status='closed',outcome=?,outcome_verified=0,reported_refund_pence=?,updated_at=? WHERE id=?",
            (body.outcome, round(body.refund_pounds*100) if body.outcome == "refunded" else 0, now_iso(), case_id))
        event(conn, case_id, "outcome_reported", body.model_dump())
        return detail(conn, own(conn, case_id, owner))


@router.get("/cases/{case_id}/pack")
def pack(case_id: str, owner=Depends(require_driver)):
    with transaction() as conn:
        row = own(conn, case_id, owner)
        data = detail(conn, row)
        if not row["draft_approved"] or not data["assessment"] or data["assessment"]["stale"]:
            raise HTTPException(409, "Review and approve a current draft before downloading the pack.")
        photos = conn.execute("SELECT id,kind,content FROM driver_evidence WHERE case_id=? ORDER BY created_at", (case_id,)).fetchall()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("appeal.txt", row["draft_text"])
        archive.writestr("read-me.txt", "Civic appeal pack — not submitted.\nCheck every fact and remove any placeholders before submitting through the route on your notice.\n\n" +
            "\n".join(f"{s['title']}: {s['url']}" for s in data["assessment"]["output"]["sources"]))
        for index, photo in enumerate(photos, 1):
            archive.writestr(f"evidence/{index:02d}-{photo['kind']}-{photo['id'][:8]}.jpg", bytes(photo["content"]))
    return Response(buffer.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="civic-appeal-pack.zip"', "Cache-Control": "private, no-store"})


@router.get("/cases/{case_id}/reminder")
def reminder(case_id: str, owner=Depends(require_driver)):
    with transaction() as conn:
        row = own(conn, case_id, owner)
    facts = Facts.model_validate_json(row["facts_json"])
    if not row["confirmed"] or not facts.deadline:
        raise HTTPException(422, "Confirm the deadline printed on your notice before adding a reminder.")
    start = facts.deadline.strftime("%Y%m%d")
    end = (facts.deadline + timedelta(days=1)).strftime("%Y%m%d")
    text = "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Civic//Appeal reminder//EN", "BEGIN:VEVENT",
        f"UID:{case_id}@civic", f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;VALUE=DATE:{start}", f"DTEND;VALUE=DATE:{end}", "SUMMARY:Check your parking appeal deadline",
        "DESCRIPTION:Deadline entered from your notice. Confirm the issuer's cut-off time. Civic has not submitted an appeal.",
        "BEGIN:VALARM", "TRIGGER:-P2D", "ACTION:DISPLAY", "DESCRIPTION:Parking appeal deadline in two days", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", ""])
    return Response(text, media_type="text/calendar", headers={"Content-Disposition": 'attachment; filename="civic-reminder.ics"', "Cache-Control": "private, no-store"})
