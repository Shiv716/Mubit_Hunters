"""Correction provenance, permissions and export boundaries; no external model calls."""
import hashlib
import json

import pytest

from app.ai.adapters import StubAdapter
from app.ai.prompt import OUTPUT_JSON_SCHEMA, SYSTEM_PROMPT
from app.db import INTEGRITY_ERRORS, init_db, transaction


def reviewed(client, case, monkeypatch=None):
    if monkeypatch:
        class MockGateway(StubAdapter):
            def complete(self, *args):
                result = super().complete(*args)
                result.provider = "mubit"
                result.model = "test-gateway-model"
                result.request_id = "test-request-1"
                return result
        monkeypatch.setattr("app.main.get_adapter", lambda *a, **k: MockGateway())
    cid = client.post("/api/cases", json=case).json()["id"]
    result = client.post(f"/api/cases/{cid}/ai-review?mode=baseline")
    assert result.status_code == 200, result.text
    rv = result.json()["ai_reviews"][0]
    decision = client.post(f"/api/cases/{cid}/decision", json={
        "ai_review_id": rv["id"], "action": "override", "final_outcome": "representation_accepted",
        "reason": "Officer checked the supplied records.", "reviewer": "test-officer"})
    assert decision.status_code == 200, decision.text
    item = client.get("/api/learning/examples").json()["items"][0]
    return item, rv


def approve(client, item, target=None, **extra):
    return client.post(f"/api/learning/examples/{item['id']}/correction", json={
        "target": target or item["parsed"], "note": "Verified against the supplied evidence.",
        "previous_revision": item["correction_id"], **extra})


def test_capture_approval_revisions_and_original_answer_are_immutable(client, demo_cases):
    item, original = reviewed(client, demo_cases[0])
    with transaction() as conn:
        snapshot = json.loads(conn.execute("SELECT input_json FROM review_inputs WHERE ai_review_id=?", (original["id"],)).fetchone()[0])
    assert snapshot["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert snapshot["messages"][1]["content"].startswith("Case bundle:\n")
    assert snapshot["output_schema"] == OUTPUT_JSON_SCHEMA
    assert snapshot["bundle"]["case"]["pcn_ref"] == demo_cases[0]["pcn_ref"]
    assert "input" not in item  # Full input appears only in an owner export.
    target = {**item["parsed"], "reason_summary": "The supplied payment record covers this parking session."}
    result = approve(client, item, target)
    assert result.status_code == 200, result.text
    saved = result.json()
    assert saved["target"] == target and saved["approved_by"] == "local-owner"
    assert client.get(f"/api/cases/{item['case_id']}").json()["ai_reviews"][0] == original
    assert approve(client, item, target).status_code == 409  # Stale or duplicate submission.
    assert client.get("/api/learning/export").status_code == 409  # Never export offline simulations.
    for query in ("UPDATE review_inputs SET input_json='{}'", "DELETE FROM model_corrections"):
        with pytest.raises(INTEGRITY_ERRORS):
            with transaction() as conn:
                conn.execute(query)
    state = client.get("/api/learning/examples").json()
    assert state["training_status"] == "not_connected" and state["updated_model"] is None


def test_export_binds_corrected_target_to_original_mubit_request_and_withdraws(client, demo_cases, monkeypatch):
    item, _ = reviewed(client, demo_cases[0], monkeypatch)
    saved = approve(client, item).json()
    assert saved["exportable"]
    exported = client.get("/api/learning/export")
    assert exported.status_code == 200
    package = exported.json()
    assert package["submitted_to_mubit"] is False and package["training_status"] == "not_connected"
    example = package["examples"][0]
    assert example["provider_request_id"] == "test-request-1"
    assert example["original_output"] == item["raw_output"]
    content = {"input": example["input"], "target": example["target"]}
    assert example["sha256"] == hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    withdrawn = approve(client, saved, state="withdrawn", target=None)
    assert withdrawn.status_code == 200
    assert client.get("/api/learning/export").status_code == 409
    with transaction() as conn:
        assert conn.execute("SELECT COUNT(*) FROM model_corrections").fetchone()[0] == 2


def test_correction_rejects_invented_refs_contradictions_and_unsafe_discretion(client, demo_cases):
    item, _ = reviewed(client, demo_cases[0])
    for changes in ({"recommendation": "reject"}, {"evidence_references": ["E-DOES-NOT-EXIST"]},
                    {"relevant_rule_references": ["invented-policy"]}, {"reason_summary": "   "},
                    {"recommendation": "accept", "missing_information": ["Required evidence"]}):
        assert approve(client, item, {**item["parsed"], **changes}).status_code == 422
    sensitive = next(case for case in demo_cases if "medical_emergency" in case["claimed_grounds"])
    item, _ = reviewed(client, sensitive)
    assert item["human_judgement_required"]
    assert item["final_label"] == "accept"
    assert approve(client, item, {**item["parsed"], "recommendation": "accept"}).status_code == 422
    assert approve(client, item, {**item["parsed"], "recommendation": "needs_review"}).status_code == 200


def test_owner_required_for_approval_and_export(client, demo_cases, monkeypatch):
    item, _ = reviewed(client, demo_cases[0])
    monkeypatch.setenv("PCN_ACCESS_KEY", "test-workspace-password-only")
    assert approve(client, item).status_code == 401
    assert client.get("/api/learning/export").status_code == 401
    client.post("/api/session", json={"name": "Owner", "password": "test-workspace-password-only"})
    monkeypatch.setattr("app.learning.session_data", lambda request: {"name": "Officer", "owner": False})
    assert approve(client, item).status_code == 403
    assert client.get("/api/learning/export").status_code == 403
    monkeypatch.setattr("app.learning.session_data", lambda request: {"name": "Owner", "owner": True, "email": "owner@example.test"})
    result = approve(client, item)
    assert result.status_code == 200 and result.json()["approved_by"] == "owner@example.test"


def test_historical_inputs_are_not_reconstructed_and_migration_is_repeatable(client, demo_cases):
    # A manual decision has no captured model input. Re-running migrations must not invent it.
    cid = client.post("/api/cases", json=demo_cases[0]).json()["id"]
    client.post(f"/api/cases/{cid}/decision", json={"action": "reject", "final_outcome": "representation_accepted",
                "reason": "Reviewed manually.", "reviewer": "officer"})
    init_db()
    item = client.get("/api/learning/examples").json()["items"][0]
    assert "not captured" in item["blocked_reason"] and not item["exportable"]
    assert approve(client, item, target={"recommendation": "accept", "reason_summary": "Manual",
        "relevant_rule_references": [], "evidence_references": [], "missing_information": [],
        "uncertainty_flags": [], "draft_response": None}).status_code == 409


def test_new_policy_excludes_old_approved_corrections(client, demo_cases, monkeypatch):
    item, _ = reviewed(client, demo_cases[0], monkeypatch)
    saved = approve(client, item).json()
    monkeypatch.setattr("app.learning.load_policy", lambda: {"policy_version": "next-policy"})
    assert client.get("/api/learning/export").status_code == 409
    assert "older policy" in client.get("/api/learning/examples").json()["items"][0]["blocked_reason"]
    assert approve(client, saved).status_code == 409
    assert approve(client, saved, state="withdrawn").status_code == 200
