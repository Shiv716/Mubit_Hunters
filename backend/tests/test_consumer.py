"""Driver identity isolation, consent, evidence and a complete appeal lifecycle."""
import io
import json
import time
import zipfile
from uuid import uuid4

import httpx
import pytest
from PIL import Image

from app import consumer, consumer_ai, consumer_auth
from app.ai.adapters import MubitAdapter, ProviderResult
from app.db import transaction


@pytest.fixture
def driver(client, monkeypatch):
    user = {"user_id": "driver-one", "name": "Test driver", "email": "driver@example.test"}
    monkeypatch.setattr(consumer_auth, "profile", lambda request: user)
    return user


def photo():
    image = io.BytesIO()
    Image.new("RGB", (60, 40), "white").save(image, "PNG")
    return image.getvalue()


def saved(client, *, consent=True):
    row = client.post("/api/consumer/cases").json()
    facts = {**row["facts"], "issuer_kind": "private", "issuer": "Fictional operator", "ticket_ref": "TEST-ONLY-01",
             "narrative": "I paid for this session and have the matching payment receipt.", "deadline": "2026-11-15"}
    response = client.put(f"/api/consumer/cases/{row['id']}", json={"facts": facts, "version": row["version"], "confirmed": True, "ai_consent": consent})
    assert response.status_code == 200, response.text
    return response.json()


def assessment(facts, images):
    sources = consumer_ai.knowledge()["sources"][:1]
    output = {"verdict": "grounds_to_explore", "summary": "Check the receipt against the notice.", "grounds": [],
        "missing_evidence": [], "risks": ["Check the discount terms on the notice."], "next_steps": ["Check all facts before submitting."],
        "draft_letter": "Please review the parking charge. I have supplied a receipt for the session described in the notice.",
        "source_ids": [sources[0]["id"]], "sources": sources, "knowledge_version": "test-guidance"}
    return output, ProviderResult(provider="mubit", model="test-model", request_id="test-request")


def test_public_signup_does_not_grant_council_access_and_revocation_is_live(client, monkeypatch):
    monkeypatch.setenv("PCN_ACCESS_KEY", "consumer-test-secret-only")
    monkeypatch.setenv("NEON_AUTH_BASE_URL", "https://auth.example.test/auth")
    profile = {"session_id": "test-session", "user_id": "test-user", "name": "Driver", "email": "driver@example.com", "expires_at": time.time()+3600}
    active = [True]
    monkeypatch.setattr(consumer_auth, "call_auth", lambda path, body: {"success": True, "token": "private-provider-token"})
    monkeypatch.setattr(consumer_auth, "neon_profile", lambda *args, **kwargs: profile if active[0] else None)
    assert client.post("/api/consumer/session/request", json={"email": profile["email"]}).status_code == 202
    response = client.post("/api/consumer/session/verify", json={"email": profile["email"], "name": "Driver", "code": "123456"})
    assert response.status_code == 200 and "HttpOnly" in response.headers["set-cookie"]
    assert "private-provider-token" not in response.headers["set-cookie"]
    assert client.get("/api/consumer/cases").status_code == 200
    assert client.get("/api/cases").status_code == 401
    with transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM access_requests").fetchone()[0] == 0
    active[0] = False
    assert client.get("/api/consumer/cases").status_code == 401


def test_case_photos_reviews_export_and_mutations_are_owner_scoped(client, driver):
    row = saved(client)
    path = f"/api/consumer/cases/{row['id']}"
    upload = client.post(path+"/evidence", files={"file": ("notice.png", photo(), "image/png")}, data={"kind": "ticket"})
    assert upload.status_code == 201
    evidence_id = upload.json()["evidence"][0]["id"]
    driver["user_id"] = "driver-two"
    assert client.get("/api/consumer/cases").json() == []
    for endpoint in (path, path+f"/evidence/{evidence_id}", path+"/pack", path+"/reminder"):
        assert client.get(endpoint).status_code == 404
    assert client.delete(path).status_code == 404
    assert client.delete(path+f"/evidence/{evidence_id}").status_code == 404
    assert client.post(path+"/assess").status_code == 404
    assert client.post(path+"/tracking/outcome", json={"outcome":"cancelled"}).status_code == 404
    assert client.post(path+"/evidence", files={"file": ("x.png", photo())}).status_code == 404


def test_consent_confirmation_and_provider_failure_never_produce_fake_advice(client, driver):
    row = saved(client, consent=False)
    path = f"/api/consumer/cases/{row['id']}"
    assert client.post(path+"/assess").status_code == 422
    updated = client.put(path, json={"facts":row["facts"], "version":row["version"], "confirmed":False, "ai_consent":True}).json()
    assert client.post(path+"/assess").status_code == 422
    client.put(path, json={"facts":row["facts"], "version":updated["version"], "confirmed":True, "ai_consent":True})
    assert client.post(path+"/assess").status_code == 503
    assert client.get(path).json()["assessment"] is None
    assert client.get("/api/consumer/public").json()["assessed_cases"] == 0
    assert client.post(path+"/evidence", files={"file": ("fake.png", b"not-an-image", "image/png")}).status_code == 422


def test_assess_edit_approve_export_track_and_delete(client, driver, monkeypatch):
    row = saved(client)
    path = f"/api/consumer/cases/{row['id']}"
    uploaded = client.post(path+"/evidence", files={"file": ("payment.png", photo(), "image/png")}, data={"kind":"payment"}).json()
    assert client.get(path+"/pack").status_code == 409
    monkeypatch.setattr(consumer_ai, "assess", assessment)
    result = client.post(path+"/assess")
    assert result.status_code == 200, result.text
    reviewed = result.json()
    response = client.put(path+"/draft", json={"text": reviewed["draft_text"], "review_id":reviewed["assessment"]["id"], "approved":True})
    assert response.status_code == 200
    package = client.get(path+"/pack")
    assert package.status_code == 200
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        assert archive.read("appeal.txt").decode() == reviewed["draft_text"]
        assert len([f for f in archive.namelist() if f.endswith(".jpg")]) == 1
    calendar = client.get(path+"/reminder")
    assert "DTSTART;VALUE=DATE:20261115" in calendar.text and "TRIGGER:-P2D" in calendar.text
    assert client.post(path+"/tracking/submitted", json={"reference":"TEST-RECEIPT", "submitted_on":"2026-10-01"}).json()["status"] == "submitted"
    reported = client.post(path+"/tracking/outcome", json={"outcome":"refunded", "refund_pounds":60}).json()
    assert reported["outcome_verified"] == 0 and reported["reported_refund_pence"] == 6000
    stats = client.get("/api/consumer/public").json()
    assert stats["assessed_cases"] == 1 and stats["verified_successes"] == 0
    assert client.delete(path).status_code == 200
    assert client.get(path+f"/evidence/{uploaded['evidence'][0]['id']}").status_code == 404
    with transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM driver_evidence").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM driver_reviews").fetchone()[0] == 0


def test_changes_invalidate_draft_and_inflight_assessment(client, driver, monkeypatch):
    row = saved(client)
    path = f"/api/consumer/cases/{row['id']}"
    monkeypatch.setattr(consumer_ai,"assess",assessment)
    reviewed = client.post(path+"/assess").json()
    client.put(path+"/draft",json={"text":reviewed["draft_text"],"review_id":reviewed["assessment"]["id"],"approved":True})
    changed = client.put(path,json={"facts":row["facts"],"version":row["version"],"confirmed":True,"ai_consent":True}).json()
    assert changed["assessment"]["stale"] and not changed["draft_approved"]
    assert client.get(path+"/pack").status_code == 409
    assert client.put(path,json={"facts":row["facts"],"version":row["version"],"confirmed":True}).status_code == 409
    def changed_during_call(facts,images):
        with transaction() as conn:
            conn.execute("UPDATE driver_cases SET version=version+1 WHERE id=?",(row["id"],))
        return assessment(facts,images)
    monkeypatch.setattr(consumer_ai,"assess",changed_during_call)
    assert client.post(path+"/assess").status_code == 409
    with transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM driver_jobs").fetchone()[0] == 0


@pytest.mark.parametrize("route", ["anthropic", "openai"])
def test_vision_uses_mubit_without_training_bodies_and_rejects_invented_sources(monkeypatch, route):
    monkeypatch.setenv("AI_PROVIDER","mubit")
    monkeypatch.setenv("MUBIT_API_KEY","synthetic-test-key")
    monkeypatch.setenv("MUBIT_ROUTE",route)
    output,_ = assessment({},[])
    output.pop("sources");output.pop("knowledge_version")
    calls=[]
    def transport(request):
        calls.append(request)
        body = {"content":[{"type":"text","text":json.dumps(output)}]} if route == "anthropic" else {"choices":[{"message":{"content":json.dumps(output)}}]}
        return httpx.Response(200,json={**body,"model":"test-model"})
    monkeypatch.setattr(consumer_ai,"MubitAdapter",lambda settings:MubitAdapter(settings,httpx.Client(transport=httpx.MockTransport(transport))))
    evidence=[{"id":"photo-1","kind":"ticket","content":consumer_ai.image_bytes(photo())}]
    result,_=consumer_ai.assess({"issuer_kind":"private","notice_stage":"initial"},evidence)
    assert result["summary"]
    body=json.loads(calls[0].content)
    assert calls[0].headers["x-middleware-record"] == "metadata"
    if route == "anthropic":
        assert body["messages"][0]["content"][-1]["source"]["media_type"] == "image/jpeg"
    else:
        assert body["messages"][1]["content"][-1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    output["source_ids"]=["invented-law"]
    with pytest.raises(Exception) as error:
        consumer_ai.assess({"issuer_kind":"private","notice_stage":"initial"},evidence)
    assert getattr(error.value,"status_code",None)==502
