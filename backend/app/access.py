"""First-party workspace cookies bound to approved Neon Auth identities."""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .neon_auth import auth_url, owner_email, verified_session

router = APIRouter(prefix="/api/session")
COOKIE = "pcn_session"


def secret():
    return os.getenv("PCN_ACCESS_KEY", "")


def required():
    return bool(secret() or auth_url())


def password_enabled():
    # When Neon is configured, old shared credentials no longer bypass approval.
    return bool(secret()) and (not auth_url() or os.getenv("PCN_ALLOW_PASSWORD_LOGIN") == "true")


def session_data(request):
    if hasattr(request.state, "workspace_session"):
        return request.state.workspace_session
    data = None
    try:
        payload, sig = request.cookies.get(COOKIE, "").split(".", 1)
        expected = hmac.new(secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
        if secret() and hmac.compare_digest(expected, sig):
            candidate = json.loads(base64.urlsafe_b64decode(payload.encode()))
            if candidate["exp"] > time.time() and isinstance(candidate.get("name"), str):
                if candidate.get("sid") and candidate.get("uid") and auth_url():
                    profile = verified_session(candidate["sid"], candidate["uid"])
                    if profile:
                        candidate.update(name=profile["name"], email=profile["email"],
                                         owner=profile["email"] == owner_email())
                        data = candidate
                elif not candidate.get("sid") and password_enabled():
                    candidate["owner"] = True  # Explicit local/bootstrap owner password.
                    data = candidate
    except (ValueError, KeyError, TypeError):
        pass
    request.state.workspace_session = data
    return data


def identity(request):
    data = session_data(request)
    return data["name"] if data else None


def require_owner(request):
    data = session_data(request)
    if not data or not data.get("owner"):
        raise HTTPException(403, "Only the workspace owner can manage access.")
    return data.get("email") or "workspace-owner"


def sign_in(response, name, profile=None):
    expires = min(time.time() + 43200, float(profile["expires_at"])) if profile else time.time() + 43200
    data = {"name": name.strip(), "exp": expires}
    if profile:
        data.update(email=profile["email"].lower(), sid=str(profile["session_id"]), uid=str(profile["user_id"]))
    payload = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
    sig = hmac.new(secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    response.set_cookie(COOKIE, f"{payload}.{sig}", httponly=True, samesite="strict", max_age=max(0, int(expires-time.time())),
                        secure=os.getenv("PCN_COOKIE_SECURE", "true" if os.getenv("RENDER") else "false").lower() == "true")
    return {"authenticated": True, "reviewer": data["name"]}


class Login(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(max_length=256)


@router.get("")
def session(request: Request):
    data = session_data(request)
    return {"required": required(), "authenticated": bool(data) or not required(),
            "reviewer": data["name"] if data else None, "email": data.get("email") if data else None,
            "owner": bool(data and data.get("owner")), "email_signin": bool(auth_url()),
            "password_signin": password_enabled(), "access_requests": bool(owner_email() and len(secret()) >= 16)}


@router.post("")
def login(body: Login, response: Response):
    if not password_enabled() or not hmac.compare_digest(body.password.encode(), secret().encode()):
        raise HTTPException(401, "Incorrect workspace password or password sign-in is disabled.")
    if not body.name.strip():
        raise HTTPException(422, "Enter your reviewer name.")
    return sign_in(response, body.name)


@router.delete("")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"authenticated": False}
