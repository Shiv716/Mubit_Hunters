"""Optional shared-password gate for a private synthetic demo; not council SSO/RBAC."""
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/session")
COOKIE = "pcn_session"


def secret():
    return os.getenv("PCN_ACCESS_KEY", "")


def identity(request):
    token = request.cookies.get(COOKIE, "")
    try:
        payload, sig = token.split(".", 1)
        expected = hmac.new(secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not secret() or not hmac.compare_digest(expected, sig):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        return data["name"] if data["exp"] > time.time() else None
    except (ValueError, KeyError, TypeError):
        return None


class Login(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(max_length=256)


@router.get("")
def session(request: Request):
    return {"required": bool(secret()), "authenticated": bool(identity(request)) or not secret(),
            "reviewer": identity(request)}


@router.post("")
def login(body: Login, response: Response):
    if not secret() or not hmac.compare_digest(body.password.encode(), secret().encode()):
        raise HTTPException(401, "Incorrect workspace password.")
    if not body.name.strip():
        raise HTTPException(422, "Enter your reviewer name.")
    payload = base64.urlsafe_b64encode(json.dumps({"name": body.name.strip(), "exp": time.time() + 43200}).encode()).decode()
    sig = hmac.new(secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    response.set_cookie(COOKIE, f"{payload}.{sig}", httponly=True, samesite="strict", max_age=43200,
                        secure=os.getenv("PCN_COOKIE_SECURE", "true" if os.getenv("RENDER") else "false").lower() == "true")
    return {"authenticated": True, "reviewer": body.name.strip()}


@router.delete("")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"authenticated": False}
