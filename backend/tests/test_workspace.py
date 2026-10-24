"""Focused integration coverage for trial-2's new officer workflow."""
import json

from app.ai.adapters import ProviderResult, StubAdapter
from app.investigator import investigate
from app.models import CaseIn


def first_case(client):
    client.post("/api/demo/seed")
    return client.get("/api/queue").json()[0]["id"]


def test_review_decide_export_and_insights(client):
    cid = first_case(client)
    review = client.post(f"/api/cases/{cid}/review")
    assert review.status_code == 200
    r = review.json()["ai_reviews"][0]
    assert {s["tool"] for s in r["steps"]} >= {"required_checks", "evidence", "policy", "payment_records", "recommendation"}
    assert r["provider"] == "offline-stub"
    draft = client.get(f"/api/cases/{cid}/draft", params={"outcome": "accept"}).json()["text"]
    body = {"outcome": "accept", "review_id": r["id"], "reason": "Payment verified", "response": draft, "reviewer": "Priya"}
    assert client.post(f"/api/cases/{cid}/resolve", json=body).status_code == 200
    assert client.post(f"/api/cases/{cid}/resolve", json=body).status_code == 409
    assert client.get(f"/api/cases/{cid}/response").text == draft
    assert client.get("/api/insights").json()["decided"] == 1
    assert client.post(f"/api/cases/{cid}/review").status_code == 409


def test_correction_requires_reason_and_stale_review_is_rejected(client):
    cid = first_case(client)
    r = client.post(f"/api/cases/{cid}/review").json()["ai_reviews"][0]
    body = {"outcome": "reject", "review_id": r["id"], "response": "Officer draft.", "reviewer": "Priya"}
    assert client.post(f"/api/cases/{cid}/resolve", json=body).status_code == 422
    body["reason"] = "Additional facts considered"
    client.post(f"/api/cases/{cid}/evidence/E1/file", files={"file": ("note.txt", b"New evidence", "text/plain")})
    assert client.post(f"/api/cases/{cid}/resolve", json=body).status_code == 409
    assert next(c for c in client.get("/api/queue").json() if c["id"] == cid)["lane"] == "new"
    # A reasoned manual decision can still be recorded after evidence changes.
    body["review_id"] = None
    assert client.post(f"/api/cases/{cid}/resolve", json=body).status_code == 200
    assert client.get("/api/feedback").json()[0]["curation_status"] == "pending"


def test_investigator_rejects_unknown_tools_and_vulnerability_is_flagged(client, demo_cases):
    class BadPlanner(StubAdapter):
        def complete(self, system, user, schema):
            return ProviderResult(provider="test", model="test", raw_text=json.dumps({"tools": ["send_letter"], "complete": True}))
    steps, _ = investigate(CaseIn.model_validate(demo_cases[0]), BadPlanner(), [])
    assert not any(s["tool"] == "send_letter" for s in steps)
    assert any(s["status"] == "failed" for s in steps)
    c = dict(demo_cases[0], pcn_ref="DM-SENSITIVE", representation_text="My daughter was taken to hospital. I also paid.")
    cid = client.post("/api/cases", json=c).json()["id"]
    r = client.post(f"/api/cases/{cid}/review").json()["ai_reviews"][0]
    assert r["effective_recommendation"] == "needs_review"
    assert "human_judgement_required" in r["safety_flags"]


def test_private_workspace_gate(client, monkeypatch):
    monkeypatch.setenv("PCN_ACCESS_KEY", "local-test-password-123")
    assert client.get("/api/queue").status_code == 401
    assert client.post("/api/session", json={"name":"Priya", "password":"wrong"}).status_code == 401
    assert client.post("/api/session", json={"name":"Priya", "password":"local-test-password-123"}).status_code == 200
    assert client.get("/api/queue").status_code == 200
    assert client.post("/api/demo/seed", headers={"Origin":"https://untrusted.example"}).status_code == 403
    client.delete("/api/session")
    assert client.get("/api/queue").status_code == 401
