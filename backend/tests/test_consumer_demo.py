import copy

import pytest
from fastapi import HTTPException

from app import consumer_demo as demo
from app.ai.adapters import ProviderResult
from app.db import transaction


@pytest.fixture(autouse=True)
def isolated_demo(monkeypatch):
    monkeypatch.setattr(demo, "_runs", {})
    monkeypatch.setenv("PCN_ACCESS_KEY", "test-public-demo-secret")


def test_public_sample_is_labelled_and_does_not_open_private_endpoints(client):
    response = client.get("/api/consumer/demo")
    assert response.status_code == 200
    data = response.json()
    assert data["fictional"] and data["walkthrough_provider"] == "prewritten-example"
    assert data["recording_requested"] == "full"
    assert not data["live_available"]
    for name in ("ticket", "receipt"):
        response = client.get(f"/api/consumer/demo/{name}")
        assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
        assert client.post(f"/api/consumer/demo/{name}").status_code == 401
    assert client.get("/api/consumer/cases").status_code == 401
    assert client.get("/api/cases").status_code == 401
    assert client.post("/api/consumer/demo/scan", json={"prompt":"not allowed"}).status_code == 422
    assert client.post("/api/consumer/demo/scan", json={}).status_code == 503
    assert client.get("/api/consumer/public").json()["assessed_cases"] == 0


def test_live_scan_flows_to_confirmed_assessment_without_cases_or_fake_metrics(client, monkeypatch):
    monkeypatch.setattr(demo, "live_available", lambda: True)
    calls = []
    result = ProviderResult(provider="mubit", model="test-transport", request_id="test-request")
    extraction = copy.deepcopy(demo.sample()["extracted"])
    extraction["issuer"] = "Willow Yard Parking"  # Distinguishable from the reference fixture.
    def scan(images, *, allow_training=False):
        assert allow_training
        assert [image["id"] for image in images] == ["demo-ticket"]
        calls.append("scan")
        return extraction, result
    def assess(facts, images, *, allow_training=False):
        assert allow_training
        assert facts["issuer"] == extraction["issuer"]
        assert facts["amount_pounds"] == 100
        assert facts["date_received"] is None
        assert {image["id"] for image in images} == {"demo-ticket", "demo-receipt"}
        calls.append("assess")
        return demo.information()["assessment"], result
    monkeypatch.setattr(demo.consumer_ai, "scan", scan)
    monkeypatch.setattr(demo.consumer_ai, "assess", assess)
    first = client.post("/api/consumer/demo/scan", json={}).json()
    assert first["mode"] == "live" and first["request_id"] == "test-request"
    assert first["recording_requested"] == "full"
    path = "/api/consumer/demo/assess"
    assert client.post(path, json={"run_id":first["run_id"],"confirmed":False}).status_code == 422
    response = client.post(path, json={"run_id":first["run_id"],"confirmed":True})
    assert response.status_code == 200 and response.json()["mode"] == "live"
    assert client.post(path,json={"run_id":first["run_id"],"confirmed":True}).json()["reused"]
    assert calls == ["scan", "assess"]
    second = client.post("/api/consumer/demo/scan",json={}).json()
    assert second["run_id"] != first["run_id"] and calls[-1] == "scan"
    demo._runs[second["run_id"]]["expires"] = 0
    assert client.post(path,json={"run_id":second["run_id"],"confirmed":True}).status_code == 409
    with transaction() as conn:
        for table in ("driver_cases", "driver_reviews", "driver_evidence", "cases"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert client.get("/api/consumer/public").json()["assessed_cases"] == 0


def test_model_failure_and_quota_remain_errors_and_release_the_demo_slot(client, monkeypatch):
    monkeypatch.setattr(demo, "live_available", lambda: True)
    def unavailable(*args, **kwargs):
        raise HTTPException(503, "Provider unavailable")
    monkeypatch.setattr(demo.consumer_ai, "scan", unavailable)
    response = client.post("/api/consumer/demo/scan",json={})
    assert response.status_code == 503 and "extracted" not in response.json()
    assert not demo._runs and not demo._ai_lock.locked()
    def denied(*args):
        raise HTTPException(429, "Demo quota reached")
    monkeypatch.setattr(demo, "quota", denied)
    assert client.post("/api/consumer/demo/scan",json={}).status_code == 429
    assert not demo._ai_lock.locked()
    demo._ai_lock.acquire()
    try:
        assert client.post("/api/consumer/demo/scan",json={}).status_code == 429
    finally:
        demo._ai_lock.release()
