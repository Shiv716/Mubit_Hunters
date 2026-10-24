import sqlite3

import pytest

from app.config import get_settings


def _seed(client):
    r = client.post("/api/demo/seed")
    assert r.status_code == 200
    return {c["pcn_ref"]: c for c in client.get("/api/cases").json()}


def _first_with(client, cases, code):
    for c in cases.values():
        if c["contravention_code"] == code:
            return c["id"]
    raise AssertionError(code)


def test_end_to_end_accept(client):
    cases = _seed(client)
    case_id = next(iter(cases.values()))["id"]
    detail = client.get(f"/api/cases/{case_id}").json()
    assert detail["status"] == "validated" and detail["checks"]["ruleset_version"] == "rules-2026.10-v1"

    # payment-covered scenario is the first demo case generated
    paid = [c for c in cases.values() if c["claimed_grounds"] == ["paid"] and c["contravention_code"] == "11"][-1]
    d = client.post(f"/api/cases/{paid['id']}/ai-review?mode=baseline").json()
    review = d["ai_reviews"][0]
    assert review["provider"] == "offline-stub" and review["status"] in ("valid", "valid_with_warnings")
    assert review["effective_recommendation"] == "accept"
    assert review["prompt_version"] and review["ruleset_version"]

    d = client.post(f"/api/cases/{paid['id']}/decision",
                    json={"ai_review_id": review["id"], "action": "accept", "reviewer": "officer.a"}).json()
    assert d["status"] == "decided"
    assert d["decisions"][0]["final_outcome"] == "representation_accepted"
    assert d["decisions"][0]["ai_recommendation"] == "accept"
    types = [e["event_type"] for e in d["audit"]]
    assert types[:2] == ["case_created", "checks_run"]
    assert {"ai_review_requested", "ai_review_completed", "decision_recorded", "feedback_example_created"} <= set(types)

    # no second decision; no further AI review
    r = client.post(f"/api/cases/{paid['id']}/decision", json={"action": "escalate", "reason": "x", "reviewer": "b"})
    assert r.status_code == 409


def test_override_requires_reason_and_keeps_ai_record(client):
    cases = _seed(client)
    case_id = _first_with(client, cases, "12")
    review = client.post(f"/api/cases/{case_id}/ai-review").json()["ai_reviews"][0]
    body = {"ai_review_id": review["id"], "action": "override", "final_outcome": "representation_rejected",
            "reviewer": "officer.b"}
    r = client.post(f"/api/cases/{case_id}/decision", json=body)
    assert r.status_code == 409 and "reason" in r.json()["detail"]
    body |= {"reason": "Permit history shows repeated misuse.", "reason_code": "policy_discretion",
             "final_response": "Edited letter"}
    d = client.post(f"/api/cases/{case_id}/decision", json=body).json()
    dec = d["decisions"][0]
    assert dec["action"] == "override" and dec["final_response"] == "Edited letter"
    assert d["ai_reviews"][0]["parsed"] == review["parsed"]  # original AI output untouched


def test_needs_review_cannot_be_blindly_accepted_and_escalation_flow(client):
    cases = _seed(client)
    case_id = _first_with(client, cases, "40")
    d = client.post(f"/api/cases/{case_id}/ai-review").json()
    review = d["ai_reviews"][0]
    if review["effective_recommendation"] == "needs_review":
        r = client.post(f"/api/cases/{case_id}/decision",
                        json={"ai_review_id": review["id"], "action": "accept", "reviewer": "o"})
        assert r.status_code == 409
    assert client.post(f"/api/cases/{case_id}/decision",
                       json={"action": "escalate", "reviewer": "o"}).status_code == 409
    d = client.post(f"/api/cases/{case_id}/decision",
                    json={"ai_review_id": review["id"], "action": "escalate", "reason": "Badge check", "reviewer": "o"}).json()
    assert d["status"] == "escalated" and d["feedback"] == []
    d = client.post(f"/api/cases/{case_id}/decision",
                    json={"action": "reject", "final_outcome": "representation_accepted",
                          "reason": "Senior officer verified badge", "reviewer": "senior"}).json()
    assert d["status"] == "decided" and len(d["decisions"]) == 2


def test_ai_failure_is_recorded_safely(client, demo_cases):
    case = dict(demo_cases[0], pcn_ref="DMFAIL0001",
                representation_text=demo_cases[0]["representation_text"] + " [[STUB:timeout]]")
    created = client.post("/api/cases", json=case).json()
    d = client.post(f"/api/cases/{created['id']}/ai-review").json()
    assert d["status"] == "ai_failed"
    rv = d["ai_reviews"][0]
    assert rv["status"] == "failed" and rv["failure_kind"] == "timeout" and rv["effective_recommendation"] == "needs_review"
    r = client.post(f"/api/cases/{created['id']}/decision",
                    json={"ai_review_id": rv["id"], "action": "accept", "reviewer": "o"})
    assert r.status_code == 409


def test_duplicate_pcn_rejected(client, demo_cases):
    assert client.post("/api/cases", json=demo_cases[0]).status_code == 201
    assert client.post("/api/cases", json=demo_cases[0]).status_code == 409


def test_audit_and_ai_reviews_are_immutable(client):
    cases = _seed(client)
    case_id = next(iter(cases.values()))["id"]
    client.post(f"/api/cases/{case_id}/ai-review")
    conn = sqlite3.connect(get_settings().db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE ai_reviews SET effective_recommendation='reject'")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM audit_events")
    conn.close()


def test_feedback_curation_feeds_precedent_retrieval(client, demo_cases):
    cases = _seed(client)
    permit_ids = [c["id"] for c in cases.values() if c["contravention_code"] == "12"]
    first = permit_ids[0]
    rv = client.post(f"/api/cases/{first}/ai-review").json()["ai_reviews"][0]
    client.post(f"/api/cases/{first}/decision", json={
        "ai_review_id": rv["id"], "action": "override", "final_outcome": "representation_accepted",
        "reason": "First occurrence; permit valid.", "reviewer": "officer.c"})
    fb = client.get("/api/feedback").json()
    assert fb[0]["curation_status"] == "pending"
    # pending examples are not used
    d = client.post(f"/api/cases/{permit_ids[1]}/ai-review?mode=precedent").json()
    assert d["ai_reviews"][0]["precedent_ids"] == []
    client.post(f"/api/feedback/{fb[0]['id']}/curate", json={"eligible": True, "curator": "lead"})
    d = client.post(f"/api/cases/{permit_ids[1]}/ai-review?mode=precedent").json()
    assert d["ai_reviews"][0]["precedent_ids"] == [f"PREC-{fb[0]['id']}"]
    assert d["ai_reviews"][0]["mode"] == "precedent"


def test_upload_evidence_file(client, demo_cases):
    created = client.post("/api/cases", json=demo_cases[0]).json()
    r = client.post(f"/api/cases/{created['id']}/evidence/E1/file",
                    files={"file": ("photo.png", b"\x89PNG fake", "image/png")})
    assert r.status_code == 200
    d = r.json()
    assert d["evidence_files"][0]["sha256"] == d["case"]["evidence"][0]["sha256"]
    bad = client.post(f"/api/cases/{created['id']}/evidence/E1/file",
                      files={"file": ("x.exe", b"MZ", "application/x-msdownload")})
    assert bad.status_code == 415


def test_capabilities_and_health(client):
    h = client.get("/api/health").json()
    assert h["ai_provider"] == "stub" and h["mubit_configured"] is False
    caps = client.get("/api/mubit/capabilities").json()
    statuses = {i["capability"]: i["status"] for i in caps["items"]}
    assert statuses["Training / calibrating an adapter and job status"] == "console_only"
