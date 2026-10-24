"""Neon's managed Better Auth owns email verification and identity sessions.

Only read the managed schema. Civic's first-party cookie references a Neon
session; revocation, expiry, verification and approval are checked on each request.
"""
import os
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from .db import PostgresConnection, transaction


def auth_url():
    return os.getenv("NEON_AUTH_BASE_URL", "").strip().rstrip("/")


def owner_email():
    return os.getenv("PCN_ACCESS_REQUEST_EMAIL", "").strip().lower()


def public_origin():
    return (os.getenv("PCN_PUBLIC_ORIGIN") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")


def call_auth(path, body):
    base = auth_url()
    parsed = urlsplit(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
        raise HTTPException(503, "Email sign-in is not configured yet.")
    try:
        result = httpx.post(base + path, json=body, timeout=15,
                            headers={"Origin": public_origin()})
        if result.status_code == 429:
            raise HTTPException(429, "Too many attempts. Please try again later.")
        if result.status_code in (400, 401, 403) and path == "/sign-in/email-otp":
            raise HTTPException(401, "That code is invalid or expired. Request a new code.")
        result.raise_for_status()
        data = result.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected authentication response")
        return data
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Email sign-in is temporarily unavailable. Please try again.") from None


def approved(email, conn):
    return bool(email and (email == owner_email() or conn.execute(
        "SELECT 1 FROM access_requests WHERE email=? AND status='approved'", (email,)).fetchone()))


def neon_profile(conn, *, session_id=None, token=None):
    if not isinstance(conn, PostgresConnection):
        return None
    # Session tokens never leave this call or enter Civic's database/cookie/logs.
    column, value = ("s.id", session_id) if session_id else ("s.token", token)
    row = conn.execute(f'''SELECT s.id AS session_id, u.id AS user_id, u.name, u.email,
            EXTRACT(EPOCH FROM s."expiresAt") AS expires_at
        FROM neon_auth.session s JOIN neon_auth."user" u ON u.id=s."userId"
        WHERE {column}=? AND s."expiresAt">CURRENT_TIMESTAMP AND u."emailVerified"=TRUE
            AND (u.banned IS NOT TRUE OR u."banExpires"<CURRENT_TIMESTAMP)
            AND s."impersonatedBy" IS NULL''', (value,)).fetchone()
    if not row:
        return None
    profile = dict(row)
    profile["name"] = profile["name"] or profile["email"].split("@", 1)[0]
    return profile


def verified_session(session_id, user_id):
    with transaction() as conn:
        profile = neon_profile(conn, session_id=session_id)
        if not profile or str(profile["user_id"]) != user_id:
            return None
        profile["email"] = profile["email"].lower()
        return profile if approved(profile["email"], conn) else None
