"""Approval, identity and persistence boundaries; never sends real email."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app import email_access as access, neon_auth
from app.config import get_settings
from app.db import init_db, transaction

REQUEST = "/api/access-requests"
SEND = "/api/session/email/request"
VERIFY = "/api/session/email/verify"


def test_auth_url_validation_accepts_neon_url_and_explains_bad_pastes_without_secrets(monkeypatch):
    url = "https://ep-dry-cake-za1nvk8t.neonauth.c-2.eu-west-2.aws.neon.tech/neondb/auth"
    monkeypatch.setenv("NEON_AUTH_BASE_URL", f"  {url}/  ")
    assert neon_auth.auth_url() == url
    assert neon_auth.auth_url_error(neon_auth.auth_url()) is None
    invalid = [
        (f"NEON_AUTH_BASE_URL={url}", "must start with https://"),
        (f'"{url}"', "must start with https://"),
        (f"[{url}]({url})", "must start with https://"),
        (url.replace("https:", "http:"), "must start with https://"),
        (url + "\nextra", "contains whitespace"),
        ("https:///auth", "missing its hostname"),
        ("https://owner:private-secret@auth.example/auth", "contains credentials"),
        (url + "?token=private-secret", "query (?) or fragment (#)"),
        (url + "#private-secret", "query (?) or fragment (#)"),
        ("https://[invalid", "invalid hostname or port"),
    ]
    for value, reason in invalid:
        detail = neon_auth.auth_url_error(value)
        assert reason in detail and "private-secret" not in detail


def test_invalid_auth_url_blocks_startup_and_requests_without_echoing_value(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv("PCN_ACCESS_KEY", "test-workspace-password-only")
    monkeypatch.setenv("PCN_ACCESS_REQUEST_EMAIL", "owner@example.com")
    monkeypatch.setenv("PCN_PUBLIC_ORIGIN", "https://civic.example")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused/unused")
    monkeypatch.setenv("NEON_AUTH_BASE_URL", "https://auth.example/auth?token=private-secret")
    def no_network(*args, **kwargs):
        pytest.fail("Invalid Auth URLs must be rejected before making a request")
    monkeypatch.setattr(neon_auth.httpx, "post", no_network)
    with pytest.raises(RuntimeError) as error:
        with TestClient(app):
            pytest.fail("Invalid Auth URLs must prevent startup")
    assert "NEON_AUTH_BASE_URL contains a query" in str(error.value)
    assert "private-secret" not in str(error.value)
    with pytest.raises(HTTPException) as error:
        neon_auth.call_auth("/email-otp/send-verification-otp", {})
    assert error.value.status_code == 503
    assert "private-secret" not in str(error.value)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("PCN_ACCESS_KEY", "test-workspace-password-only")
    monkeypatch.setenv("PCN_ACCESS_REQUEST_EMAIL", "owner@example.com")
    monkeypatch.setenv("NEON_AUTH_BASE_URL", "https://test.neonauth.example/neondb/auth")
    monkeypatch.setenv("PCN_PUBLIC_ORIGIN", "https://civic.example")
    monkeypatch.setenv("RESEND_API_KEY", "test-provider-key")
    monkeypatch.setenv("PCN_EMAIL_FROM", "Civic <signin@example.com>")
    sent = []
    def send(*args):
        sent.append(args)
        return True
    monkeypatch.setattr(access, "send_email", send)
    monkeypatch.setattr(access, "call_auth", lambda path, body: {"success": True})
    return sent


def request_token(client, sent, email="reviewer@gmail.com"):
    response = client.post(REQUEST, json={"email": email})
    assert response.status_code == 202
    return sent[-1][4].split("#approve=", 1)[1]


def fake_identity(monkeypatch, email="reviewer@gmail.com"):
    profile = {"session_id": str(uuid4()), "user_id": str(uuid4()), "email": email,
               "name": "Reviewer", "expires_at": int(time.time()) + 3600}
    valid = [True]
    def lookup(conn, *, token=None, session_id=None):
        return profile if valid[0] and (token == "neon-session-token" or session_id == profile["session_id"]) else None
    monkeypatch.setattr(access, "neon_profile", lookup)
    monkeypatch.setattr(neon_auth, "neon_profile", lookup)
    monkeypatch.setattr(access, "call_auth", lambda path, body: {"token": "neon-session-token", "success": True})
    return valid


def test_request_does_not_grant_access_and_link_requires_explicit_single_use_approval(client, configured, monkeypatch):
    monkeypatch.setenv("PCN_EMAIL_FROM", "Civic <onboarding@resend.dev>")
    codes = []
    monkeypatch.setattr(access, "call_auth", lambda *args: codes.append(args) or {"success": True})
    token = request_token(client, configured, "New.User@gmail.com")
    assert configured[0][0] == "owner@example.com"
    assert client.get("/api/queue").status_code == 401
    assert client.get(REQUEST).status_code == 401
    assert client.get(f"/api/access-requests/approve?token={token}").status_code == 405
    inspected = client.post(REQUEST+"/inspect", json={"token": token})
    assert inspected.json()["email"] == "new.user@gmail.com"
    with transaction() as conn:
        row = dict(conn.execute("SELECT * FROM access_requests").fetchone())
        assert row["status"] == "pending" and token not in json.dumps(row)
    assert client.post(REQUEST+"/approve", json={"token": "x"*43}).status_code == 410
    result = client.post(REQUEST+"/approve", json={"token": token}).json()
    assert result["approved"] is True and result["email_sent"] is True
    assert "I already have a code" in result["message"]
    assert len(configured) == 1  # Resend is used only for the owner's inbox.
    assert codes == [("/email-otp/send-verification-otp", {"email": "new.user@gmail.com", "type": "sign-in"})]
    with transaction() as conn:
        assert conn.execute("SELECT applicant_email_sent FROM access_requests").fetchone()[0] == 1
    assert client.post(REQUEST+"/approve", json={"token": token}).status_code == 410
    assert client.get("/api/queue").status_code == 401  # Approval does not authenticate the email reader.
    assert client.post("/api/session", json={"name":"Attacker", "password":"test-workspace-password-only"}).status_code == 401


def test_only_approved_verified_neon_identity_can_enter_and_revocation_is_immediate(client, configured, monkeypatch):
    valid = fake_identity(monkeypatch)
    body = {"email":"reviewer@gmail.com", "name":"Reviewer", "code":"123456"}
    assert client.post(VERIFY,json=body).status_code == 403
    token = request_token(client, configured)
    client.post(REQUEST+"/approve",json={"token":token})
    valid[0] = False  # Invalid, unverified, banned or missing Neon session.
    assert client.post(VERIFY,json=body).status_code == 401
    valid[0] = True
    signed_in = client.post(VERIFY,json=body)
    assert signed_in.status_code == 200
    assert "HttpOnly" in signed_in.headers["set-cookie"]
    assert "neon-session-token" not in signed_in.headers["set-cookie"]
    assert client.get("/api/queue").status_code == 200
    assert client.get(REQUEST).status_code == 403  # Approved members are not owners.
    assert client.get("/api/session").json()["owner"] is False
    valid[0] = False
    assert client.get("/api/queue").status_code == 401  # Neon session revoked.
    valid[0] = True
    with transaction() as conn:
        conn.execute("UPDATE access_requests SET status='revoked'")
    assert client.get("/api/queue").status_code == 401  # Civic membership revoked.
    client.post(REQUEST,json={"email":body["email"]})
    with transaction() as conn:
        assert conn.execute("SELECT status FROM access_requests").fetchone()[0] == "revoked"


def test_owner_can_review_database_requests_when_mail_fails_and_retry_notice(client, configured, monkeypatch):
    monkeypatch.setattr(access,"send_email",lambda *args:False)
    client.post(REQUEST,json={"email":"reviewer@gmail.com"})
    fake_identity(monkeypatch,"owner@example.com")
    assert client.post(VERIFY,json={"email":"owner@example.com","name":"Owner","code":"123456"}).status_code == 200
    assert client.get("/api/session").json()["owner"] is True
    row = client.get(REQUEST).json()["requests"][0]
    assert row["owner_email_sent"] == 0
    decision = f"{REQUEST}/{row['id']}/decision"
    def fail(*args):
        raise HTTPException(503, "Neon unavailable")
    monkeypatch.setattr(access,"call_auth",fail)
    result = client.post(decision,json={"action":"approve"}).json()
    assert result["status"] == "approved" and result["email_sent"] is False
    assert "No new sign-in code" in result["message"]
    with transaction() as conn:
        conn.execute("DELETE FROM auth_rate_limits WHERE bucket LIKE 'signin-send:%'")
    monkeypatch.setattr(access,"call_auth",lambda *args:{"success":True})
    assert client.post(decision,json={"action":"notify"}).json()["email_sent"] is True
    assert client.get(REQUEST).json()["requests"][0]["applicant_email_sent"] == 1
    assert client.post(decision,json={"action":"revoke"}).json()["status"] == "revoked"
    with transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE event_type LIKE 'access_%'").fetchone()[0] == 2


def test_expiry_duplicates_validation_origin_and_rate_limits(client, configured, monkeypatch):
    timestamp = [1_800_000_000]
    monkeypatch.setattr(access,"now",lambda:timestamp[0])
    token = request_token(client, configured)
    client.post(REQUEST,json={"email":"reviewer@gmail.com"})
    assert len(configured) == 1
    timestamp[0] += access.APPROVAL_TTL
    assert client.post(REQUEST+"/approve",json={"token":token}).status_code == 410
    token = request_token(client, configured)
    assert len(configured) == 2
    assert client.post(REQUEST+"/approve",json={"token":token},headers={"Origin":"https://evil.example"}).status_code == 403
    assert client.post(REQUEST,json={"email":"invalid"}).status_code == 422
    with transaction() as conn:
        conn.execute("UPDATE auth_rate_limits SET count=100 WHERE bucket='access-requests:global'")
    assert client.post(REQUEST,json={"email":"other@example.com"}).status_code == 429


def test_neon_otp_is_only_requested_for_approved_email_and_errors_do_not_leak(client, configured, monkeypatch):
    calls=[]
    monkeypatch.setattr(access,"call_auth",lambda *args:calls.append(args) or {"success":True})
    before=client.post(SEND,json={"email":"reviewer@gmail.com"})
    assert before.status_code == 202 and not calls
    token=request_token(client,configured)
    client.post(REQUEST+"/approve",json={"token":token})
    after=client.post(SEND,json={"email":"reviewer@gmail.com"})
    assert before.json() == after.json()
    assert calls == [("/email-otp/send-verification-otp",{"email":"reviewer@gmail.com","type":"sign-in"})]
    # Approval and self-service share a cooldown, preserving the emailed code.
    client.post(SEND,json={"email":"reviewer@gmail.com"})
    assert len(calls)==1
    with transaction() as conn:
        conn.execute("DELETE FROM auth_rate_limits WHERE bucket LIKE 'signin-send:%'")
    client.post(SEND,json={"email":"reviewer@gmail.com"})
    assert len(calls)==2
    def fail(*args,**kwargs):
        raise httpx.ConnectError("private provider detail")
    monkeypatch.setattr(neon_auth.httpx,"post",fail)
    with pytest.raises(Exception) as error:
        neon_auth.call_auth("/sign-in/email-otp",{"email":"reviewer@gmail.com","otp":"123456"})
    assert error.value.status_code==503 and "private" not in str(error.value)


@pytest.mark.parametrize("missing_auth", [True, False])
def test_approval_survives_missing_auth_or_rejected_email_without_claiming_delivery(client, configured, monkeypatch, missing_auth):
    if missing_auth:
        monkeypatch.delenv("NEON_AUTH_BASE_URL")
    monkeypatch.setattr(access,"call_auth",lambda *args:{"success":False})
    token=request_token(client,configured)
    response=client.post(REQUEST+"/approve",json={"token":token})
    assert response.status_code==200
    result=response.json()
    assert result["approved"] is True and result["email_sent"] is False
    assert ("NEON_AUTH_BASE_URL" if missing_auth else "No new sign-in code") in result["message"]
    with transaction() as conn:
        row=conn.execute("SELECT status,applicant_email_sent FROM access_requests").fetchone()
        assert row["status"]=="approved" and row["applicant_email_sent"]==0
    assert len(configured)==1
    assert client.get("/api/queue").status_code==401


def test_notification_contract_escapes_html_and_never_mails_password(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY","test-key")
    monkeypatch.setenv("PCN_EMAIL_FROM","Civic <access@example.com>")
    monkeypatch.setenv("PCN_PUBLIC_ORIGIN","https://civic.example")
    monkeypatch.setenv("PCN_ACCESS_KEY","never-email-this-password")
    def capture(url,**kwargs):
        assert url=="https://api.resend.com/emails"
        payload=kwargs["json"]
        assert "never-email-this-password" not in json.dumps(payload)
        assert "&lt;script&gt;" in payload["html"]
        assert kwargs["headers"]["Idempotency-Key"]=="request-id"
        return httpx.Response(200,json={"id":"test"},request=httpx.Request("POST",url))
    monkeypatch.setattr(access.httpx,"post",capture)
    assert access.send_email("owner@example.com","Access request","<script>","Approve","https://civic.example/#approve=secret","request-id")


def test_postgres_migration_preserves_cases_and_approval_has_one_winner(client, configured, monkeypatch):
    if not get_settings().database_url:
        pytest.skip("PostgreSQL migration and concurrent approval")
    monkeypatch.setenv("PCN_ALLOW_PASSWORD_LOGIN","true")
    client.post("/api/session",json={"name":"Owner","password":"test-workspace-password-only"})
    client.post("/api/demo/seed")
    with transaction() as conn:
        conn.execute("DROP TABLE access_requests")
        conn.execute("DROP TABLE auth_rate_limits")
        conn.execute("DELETE FROM schema_migrations WHERE version=2")
    init_db();init_db()
    assert len(client.get("/api/queue").json())==17
    token=request_token(client,configured)
    barrier=Barrier(2)
    def approve():
        barrier.wait()
        return client.post(REQUEST+"/approve",json={"token":token}).status_code
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(lambda _:approve(),range(2)))==[200,410]


def test_postgres_neon_session_query_checks_ownership_expiry_and_bans(client):
    if not get_settings().database_url:
        pytest.skip("Managed-auth schema contract on disposable PostgreSQL")
    # Only PCN_TEST_DATABASE_URL is used here, never the configured Neon database.
    uid,sid,token=str(uuid4()),str(uuid4()),uuid4().hex
    with transaction() as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS neon_auth")
        conn.execute('''CREATE TABLE IF NOT EXISTS neon_auth."user" (id uuid PRIMARY KEY,name text,email text,
            "emailVerified" boolean,banned boolean,"banExpires" timestamptz)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS neon_auth.session (id uuid PRIMARY KEY,"userId" uuid,
            token text,"expiresAt" timestamptz,"impersonatedBy" text)''')
        conn.execute('''INSERT INTO neon_auth."user" VALUES (?,?,?,TRUE,FALSE,NULL)''',(uid,"Reviewer","person@example.com"))
        conn.execute('''INSERT INTO neon_auth.session VALUES (?,?,?,CURRENT_TIMESTAMP+INTERVAL '1 hour',NULL)''',(sid,uid,token))
        assert str(neon_auth.neon_profile(conn,token=token)["session_id"])==sid
        conn.execute('UPDATE neon_auth."user" SET "emailVerified"=FALSE WHERE id=?',(uid,))
        assert neon_auth.neon_profile(conn,session_id=sid) is None
        conn.execute('UPDATE neon_auth."user" SET "emailVerified"=TRUE,banned=TRUE WHERE id=?',(uid,))
        assert neon_auth.neon_profile(conn,session_id=sid) is None
        conn.execute('UPDATE neon_auth."user" SET banned=FALSE WHERE id=?',(uid,))
        conn.execute('UPDATE neon_auth.session SET "expiresAt"=CURRENT_TIMESTAMP WHERE id=?',(sid,))
        assert neon_auth.neon_profile(conn,session_id=sid) is None
        conn.execute('DELETE FROM neon_auth.session WHERE id=?',(sid,))
        conn.execute('DELETE FROM neon_auth."user" WHERE id=?',(uid,))
