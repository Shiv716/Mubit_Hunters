"""Public driver accounts, isolated from the approval-gated council workspace."""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from .access import secret
from .db import transaction
from .email_access import digest, quota
from .neon_auth import auth_url, call_auth, neon_profile

router = APIRouter(prefix="/api/consumer/session", tags=["driver accounts"])
COOKIE = "civic_driver_session"


def profile(request):
    if hasattr(request.state, "driver_profile"):
        return request.state.driver_profile
    found = None
    try:
        payload, signature = request.cookies.get(COOKIE, "").split(".", 1)
        expected = hmac.new(secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
        if len(secret()) >= 16 and auth_url() and hmac.compare_digest(expected, signature):
            data = json.loads(base64.urlsafe_b64decode(payload))
            if data.get("aud") == "driver" and data["exp"] > time.time():
                with transaction() as conn:
                    current = neon_profile(conn, session_id=data["sid"])
                if current and str(current["user_id"]) == data["uid"]:
                    found = current
    except (ValueError, KeyError, TypeError):
        pass
    request.state.driver_profile = found
    return found


def require_driver(request: Request):
    user = profile(request)
    if not user:
        raise HTTPException(401, "Sign in to your personal account to continue.")
    return str(user["user_id"])


class Email(BaseModel):
    email: EmailStr = Field(max_length=254)


class Verify(Email):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(pattern=r"^[0-9]{6,8}$")


@router.get("")
def session(request: Request):
    user = profile(request)
    return {"authenticated": bool(user), "configured": bool(auth_url() and len(secret()) >= 16),
            "name": user["name"] if user else None, "email": user["email"] if user else None}


@router.post("/request", status_code=202)
def request_code(body: Email):
    if not auth_url() or len(secret()) < 16:
        raise HTTPException(503, "Account sign-in is awaiting setup. Parking discovery is available now.")
    email = str(body.email).lower()
    quota("driver-signin:global", 100, 3600)
    quota(f"driver-signin:{digest(email)}", 1, 60)
    data = call_auth("/email-otp/send-verification-otp", {"email": email, "type": "sign-in"})
    if data.get("success") is not True:
        raise HTTPException(503, "The sign-in email could not be sent. Please try again.")
    return {"message": "Check your inbox for a sign-in code. New accounts are created when your email is verified. No approval is needed."}


@router.post("/verify")
def verify(body: Verify, response: Response):
    if not auth_url() or len(secret()) < 16:
        raise HTTPException(503, "Account sign-in is awaiting setup.")
    email, name = str(body.email).lower(), body.name.strip()
    if not name:
        raise HTTPException(422, "Enter your name.")
    quota("driver-verify:global", 300, 60)
    quota(f"driver-verify:{digest(email)}", 10, 600)
    data = call_auth("/sign-in/email-otp", {"email": email, "otp": body.code, "name": name})
    token = data.get("token")
    with transaction() as conn:
        user = neon_profile(conn, token=token) if isinstance(token, str) and token else None
    if not user or user["email"].lower() != email:
        raise HTTPException(401, "Your email could not be verified. Request a new code.")
    expires = min(time.time() + 43200, float(user["expires_at"]))
    payload = base64.urlsafe_b64encode(json.dumps({"aud": "driver", "sid": str(user["session_id"]),
        "uid": str(user["user_id"]), "exp": expires}).encode()).decode()
    signature = hmac.new(secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    response.set_cookie(COOKIE, payload + "." + signature, httponly=True, samesite="strict",
        secure=os.getenv("PCN_COOKIE_SECURE", "true" if os.getenv("RENDER") else "false").lower() == "true",
        max_age=max(0, int(expires-time.time())))
    return {"authenticated": True, "configured": True, "name": user["name"], "email": email}


@router.delete("")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"authenticated": False}
