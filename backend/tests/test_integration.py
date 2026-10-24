"""Council exchange tests use synthetic data and a mocked Mubit response only."""
import base64
import copy

from app.ai.adapters import StubAdapter
from app.db import transaction

KEY = "connector-test-key-with-at-least-32-characters"
HEADERS = {"Authorization": f"Bearer {KEY}"}


def package(client, monkeypatch):
    monkeypatch.setenv("PCN_INTEGRATION_KEY", KEY)
    monkeypatch.setenv("PCN_EVIDENCE_STORAGE", "database")
    return client.get("/api/integration/sample").json()


class MockMubit(StubAdapter):
    @property
    def provider(self):
        return "mubit"

    def complete(self, *args):
        result = super().complete(*args)
        result.provider, result.model, result.request_id = "mubit", "mock-model", "mock-request"
        return result


def test_import_review_approve_export_and_receipt(client, monkeypatch):
    body = package(client, monkeypatch)
    imported = client.post("/api/integration/v1/cases", json=body, headers=HEADERS)
    assert imported.status_code == 200
    cid = imported.json()["case_id"]
    assert client.get(f"/api/cases/{cid}/evidence/E3/file").content == base64.b64decode(body["attachments"][0]["content_base64"])
    assert client.post("/api/integration/v1/cases", json=body, headers=HEADERS).json()["status"] == "unchanged"
    assert len(client.get("/api/queue").json()) == 1
    assert client.get("/api/integration/v1/results", headers=HEADERS).json()["results"] == []
    # Connected cases cannot silently use the development simulation.
    assert client.post(f"/api/cases/{cid}/review").status_code == 503
    manual = {"outcome": "accept", "reason": "Checked", "response": "Approved response", "reviewer": "Test officer"}
    assert client.post(f"/api/cases/{cid}/resolve", json=manual).status_code == 409
    monkeypatch.setattr("app.workspace.get_adapter", lambda *args, **kwargs: MockMubit())
    detail = client.post(f"/api/cases/{cid}/review").json()
    review = detail["ai_reviews"][0]
    assert review["provider"] == "mubit" and review["status"] != "failed"
    approved = client.post(f"/api/cases/{cid}/resolve", json={**manual, "review_id": review["id"]})
    assert approved.status_code == 200
    assert approved.json()["integration"]["delivery_status"] == "awaiting_receipt"
    result = client.get("/api/integration/v1/results", headers=HEADERS).json()["results"][0]
    assert result["source_case_id"] == body["source_case_id"] and result["source_version"] == 1
    assert result["ai_provider"] == "mubit" and result["final_response"] == manual["response"]
    assert client.get("/api/integration/export").json()["results"][0]["delivery_status"] == "awaiting_receipt"
    url = f"/api/integration/v1/results/{result['decision_id']}/receipt"
    receipt = {"receipt_id": "council-receipt-1", "source_case_id": body["source_case_id"], "source_version": 1}
    assert client.post(url, json={**receipt, "source_version": 2}, headers=HEADERS).status_code == 409
    assert client.post(url, json=receipt, headers=HEADERS).status_code == 200
    assert client.post(url, json=receipt, headers=HEADERS).status_code == 200
    assert client.post(url, json={**receipt, "receipt_id": "different"}, headers=HEADERS).status_code == 409
    assert client.get("/api/integration/v1/results", headers=HEADERS).json()["results"] == []
    assert client.get(f"/api/cases/{cid}").json()["integration"]["delivery_status"] == "received"
    assert client.post("/api/integration/v1/cases", json={**body, "source_version": 2}, headers=HEADERS).status_code == 409


def test_updates_invalidate_reviews_and_refuse_overwriting_local_evidence(client, monkeypatch):
    body = package(client, monkeypatch)
    cid = client.post("/api/integration/v1/cases", json=body, headers=HEADERS).json()["case_id"]
    monkeypatch.setattr("app.workspace.get_adapter", lambda *args, **kwargs: MockMubit())
    review = client.post(f"/api/cases/{cid}/review").json()["ai_reviews"][0]
    changed = copy.deepcopy(body)
    changed["case"]["representation_text"] += " More facts supplied."
    assert client.post("/api/integration/v1/cases", json=changed, headers=HEADERS).status_code == 409
    changed["source_version"] = 2
    assert client.post("/api/integration/v1/cases", json=changed, headers=HEADERS).json()["status"] == "updated"
    detail = client.get(f"/api/cases/{cid}").json()
    assert detail["checks"]["id"] != review["check_id"]
    assert client.post(f"/api/cases/{cid}/resolve", json={"outcome": "accept", "review_id": review["id"],
        "reason": "Checked", "response": "Response", "reviewer": "Test"}).status_code == 409
    assert client.post(f"/api/cases/{cid}/evidence/E1/file", files={"file": ("local.txt", b"Officer evidence", "text/plain")}).status_code == 200
    assert client.post("/api/integration/v1/cases", json={**changed, "source_version": 3}, headers=HEADERS).status_code == 409
    assert client.get(f"/api/cases/{cid}/evidence/E1/file").content == b"Officer evidence"


def test_machine_scope_council_binding_and_atomic_validation(client, monkeypatch):
    assert client.get("/api/integration/v1/results").status_code == 503
    body = package(client, monkeypatch)
    assert client.post("/api/integration/v1/cases", json=body).status_code == 401
    monkeypatch.setenv("PCN_ACCESS_KEY", "private-workspace-password")
    # A machine credential never grants workspace, user administration, or decision access.
    assert client.get("/api/queue", headers=HEADERS).status_code == 401
    assert client.post("/api/integration/test-import", json=body, headers=HEADERS).status_code == 401
    assert client.post("/api/integration/v1/cases", json={**body, "council_id": "another-council"}, headers=HEADERS).status_code == 409
    bad = copy.deepcopy(body)
    bad["attachments"][0]["content_base64"] = "invalid!"
    assert client.post("/api/integration/v1/cases", json=bad, headers=HEADERS).status_code == 422
    bad["case"]["synthetic"] = False
    assert client.post("/api/integration/v1/cases", json=bad, headers=HEADERS).status_code == 422
    with transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] == 0
    assert client.post("/api/integration/v1/cases", json=body, headers=HEADERS).status_code == 200
    monkeypatch.setenv("PCN_COUNCIL_ID", "another-council")
    assert client.get("/api/integration/v1/results", headers=HEADERS).status_code == 409


def test_production_never_falls_back_to_stub(client, monkeypatch):
    cid = client.post("/api/demo/seed").json()["created"][0]
    monkeypatch.setenv("PCN_ENV", "production")
    assert client.get("/api/health").json()["ai_available"] is False
    assert client.post(f"/api/cases/{cid}/review").status_code == 503
    assert client.post(f"/api/cases/{cid}/ai-review").status_code == 503
    monkeypatch.setenv("AI_PROVIDER", "mubit")
    assert client.post(f"/api/cases/{cid}/review").status_code == 503
    assert client.get(f"/api/cases/{cid}").json()["ai_reviews"] == []
    # Misplaced credentials must not be echoed by the public configuration endpoint.
    monkeypatch.setenv("AI_PROVIDER", "mbt_accidentally-pasted-test-secret")
    health = client.get("/api/health")
    assert health.json()["ai_provider"] == "unconfigured"
    assert "mbt_accidentally-pasted-test-secret" not in health.text
    assert client.post(f"/api/cases/{cid}/review").status_code == 503
