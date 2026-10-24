"""Owner-approved access requests, persisted alongside the workspace in Neon."""
import hashlib
import hmac
import html
import logging
import os
import secrets
import time
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from typing import Literal

from .access import require_owner, secret, sign_in
from .db import audit, transaction
from .neon_auth import approved, auth_url, call_auth, neon_profile, owner_email, public_origin

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
APPROVAL_TTL = 86400
CONFIRMATION = "Request received. The workspace owner will review it. You'll receive an email once access is approved."
CODE_CONFIRMATION = "If your access is approved, a sign-in code will arrive shortly. Check your inbox and spam folder."


def now():
    return int(time.time())


def digest(value):
    return hmac.new(secret().encode(), value.encode(), hashlib.sha256).hexdigest()


class EmailRequest(BaseModel):
    email: EmailStr = Field(max_length=254)


class EmailLogin(EmailRequest):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(pattern=r"^[0-9]{6,8}$")


class Approval(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class Decision(BaseModel):
    action: Literal["approve", "revoke", "notify"]


def take_quota(conn, bucket, limit, seconds, timestamp):
    return conn.execute("""INSERT INTO auth_rate_limits (bucket, count, expires_at) VALUES (?,1,?)
        ON CONFLICT(bucket) DO UPDATE SET
            count=CASE WHEN auth_rate_limits.expires_at<=? THEN 1 ELSE auth_rate_limits.count+1 END,
            expires_at=CASE WHEN auth_rate_limits.expires_at<=? THEN excluded.expires_at ELSE auth_rate_limits.expires_at END
        WHERE auth_rate_limits.expires_at<=? OR auth_rate_limits.count<? RETURNING count""",
        (bucket, timestamp + seconds, timestamp, timestamp, timestamp, limit)).fetchone() is not None


def quota(bucket, limit, seconds):
    with transaction() as conn:
        conn.execute("DELETE FROM auth_rate_limits WHERE expires_at<=?", (now(),))
        allowed = take_quota(conn, bucket, limit, seconds, now())
    if not allowed:
        raise HTTPException(429, "Too many requests. Please try again later.")


def send_email(recipient, subject, text, button_label, link, key):
    if not os.getenv("RESEND_API_KEY") or not os.getenv("PCN_EMAIL_FROM") or not public_origin():
        return False
    try:
        result = httpx.post("https://api.resend.com/emails", timeout=10,
            headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "Idempotency-Key": key},
            json={"from": os.environ["PCN_EMAIL_FROM"], "to": [recipient], "subject": subject,
                  "text": f"{text}\n\n{button_label}: {link}",
                  "html": f'<p>{html.escape(text)}</p><p><a href="{html.escape(link, quote=True)}">{html.escape(button_label)}</a></p>'})
        result.raise_for_status()
        return True
    except httpx.HTTPError:
        logger.warning("Access notification delivery failed; request retained for owner review.")
        return False


def notify_approved(row):
    sent = send_email(row["email"], "Your Civic workspace access is approved",
        "Your access has been approved. Open Civic and sign in with the same email address.",
        "Open workspace", public_origin(), f"access-approved-{row['id']}-{row['decided_at']}")
    if sent:
        with transaction() as conn:
            conn.execute("UPDATE access_requests SET applicant_email_sent=1 WHERE id=? AND status='approved' AND decided_at=?",
                         (row["id"], row["decided_at"]))
    return sent


@router.post("/access-requests", status_code=202)
def request_access(body: EmailRequest):
    if not owner_email() or len(secret()) < 16:
        raise HTTPException(503, "Access requests are not set up yet. Contact the workspace owner.")
    quota("access-requests:global", 100, 3600)
    email, timestamp = str(body.email).lower(), now()
    token = secrets.token_urlsafe(32)
    with transaction() as conn:
        if not take_quota(conn, f"access-request:{digest(email)}", 1, 600, timestamp):
            return {"message": CONFIRMATION}
        row = conn.execute("""INSERT INTO access_requests
            (id,email,status,requested_at,approval_token_hash,approval_expires_at) VALUES (?,?,'pending',?,?,?)
            ON CONFLICT(email) DO UPDATE SET approval_token_hash=excluded.approval_token_hash,
                approval_expires_at=excluded.approval_expires_at, owner_email_sent=0
            WHERE access_requests.status='pending' RETURNING id""",
            (uuid4().hex, email, timestamp, digest(token), timestamp + APPROVAL_TTL)).fetchone()
    if row:
        sent = send_email(owner_email(), "Civic workspace access request",
            f"{email} has requested access to your workspace. This review link expires in 24 hours.",
            "Review and approve access", f"{public_origin()}/#approve={token}", f"access-request-{digest(token)}")
        with transaction() as conn:
            conn.execute("UPDATE access_requests SET owner_email_sent=? WHERE id=? AND approval_token_hash=?",
                         (int(sent), row["id"], digest(token)))
    return {"message": CONFIRMATION}


@router.post("/access-requests/inspect")
def inspect_approval(body: Approval):
    quota("access-inspect:global", 300, 60)
    with transaction() as conn:
        row = conn.execute("""SELECT email,approval_expires_at FROM access_requests
            WHERE approval_token_hash=? AND approval_expires_at>? AND status='pending'""", (digest(body.token), now())).fetchone()
    if not row:
        raise HTTPException(410, "This approval link has expired or has already been used. Open Workspace admin to review requests.")
    return dict(row)


@router.post("/access-requests/approve")
def approve_link(body: Approval):
    quota("access-approve:global", 100, 60)
    with transaction() as conn:
        row = conn.execute("""UPDATE access_requests SET status='approved', decided_at=?, decided_by=?,
            approval_token_hash=NULL, approval_expires_at=NULL, applicant_email_sent=0
            WHERE approval_token_hash=? AND approval_expires_at>? AND status='pending' RETURNING *""",
            (now(), owner_email(), digest(body.token), now())).fetchone()
        if not row:
            raise HTTPException(410, "This approval link has expired or has already been used.")
        audit(conn, None, "access_approved", owner_email(), {"request_id": row["id"], "email": row["email"]})
    return {"approved": True, "email_sent": notify_approved(row)}


@router.get("/access-requests")
def list_requests(request: Request):
    require_owner(request)
    with transaction() as conn:
        rows = conn.execute("""SELECT id,email,status,requested_at,decided_at,owner_email_sent,applicant_email_sent
            FROM access_requests ORDER BY requested_at DESC LIMIT 200""").fetchall()
    return {"requests": [dict(row) for row in rows],
            "notifications_configured": bool(os.getenv("RESEND_API_KEY") and os.getenv("PCN_EMAIL_FROM") and public_origin())}


@router.post("/access-requests/{request_id}/decision")
def decide_request(request_id: str, body: Decision, request: Request):
    actor = require_owner(request)
    with transaction() as conn:
        row = conn.execute("SELECT * FROM access_requests WHERE id=?", (request_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Access request not found.")
        if body.action == "notify":
            if row["status"] != "approved":
                raise HTTPException(409, "Approve this request first.")
        else:
            status = "approved" if body.action == "approve" else "revoked"
            row = conn.execute("""UPDATE access_requests SET status=?,decided_at=?,decided_by=?,
                approval_token_hash=NULL,approval_expires_at=NULL,applicant_email_sent=0 WHERE id=? RETURNING *""",
                (status, now(), actor, request_id)).fetchone()
            audit(conn, None, f"access_{status}", actor, {"request_id": request_id, "email": row["email"]})
    return {"status": row["status"], "email_sent": notify_approved(row) if row["status"] == "approved" else False}


@router.post("/session/email/request", status_code=202)
def request_code(body: EmailRequest):
    if not auth_url() or len(secret()) < 16:
        raise HTTPException(503, "Email sign-in is not configured yet.")
    email = str(body.email).lower()
    quota("signin-send:global", 100, 3600)
    with transaction() as conn:
        send = take_quota(conn, f"signin-send:{digest(email)}", 1, 60, now()) and approved(email, conn)
    if send:
        call_auth("/email-otp/send-verification-otp", {"email": email, "type": "sign-in"})
    return {"message": CODE_CONFIRMATION}


@router.post("/session/email/verify")
def verify_code(body: EmailLogin, response: Response):
    if not auth_url() or len(secret()) < 16:
        raise HTTPException(503, "Email sign-in is not configured yet.")
    email, name = str(body.email).lower(), body.name.strip()
    if not name:
        raise HTTPException(422, "Enter your reviewer name.")
    quota("signin-verify:global", 300, 60)
    quota(f"signin-verify:{digest(email)}", 10, 600)
    with transaction() as conn:
        if not approved(email, conn):
            raise HTTPException(403, "Request access and wait for the workspace owner's approval before signing in.")
    data = call_auth("/sign-in/email-otp", {"email": email, "otp": body.code, "name": name})
    token = data.get("token")
    with transaction() as conn:
        profile = neon_profile(conn, token=token) if isinstance(token, str) and token else None
        if not profile or profile["email"].lower() != email or not approved(email, conn):
            raise HTTPException(401, "We couldn't verify your approved account. Please sign in again.")
    return sign_in(response, profile["name"], profile)
