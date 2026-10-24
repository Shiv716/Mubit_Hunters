"""Repeatable public demonstration using only the bundled fictional ticket.

No private cases, uploads, user prompts or model choices are accepted here.
Live results are held briefly in memory; demo runs never enter product metrics.
"""
import json
import secrets
import threading
import time
from datetime import date

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from . import consumer_ai
from .config import DATA_DIR, get_settings
from .consumer import Facts
from .db import now_iso
from .email_access import quota

router = APIRouter(prefix="/api/consumer/demo", tags=["sample ticket"])
DIRECTORY = DATA_DIR / "consumer-demo"
_runs = {}
_state_lock = threading.Lock()
_ai_lock = threading.Lock()
RUN_TTL = 1800
MAX_RUNS = 100


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssessmentRequest(ScanRequest):
    run_id: str = Field(min_length=16, max_length=64)
    confirmed: bool


def sample():
    return json.loads((DIRECTORY / "sample.json").read_text(encoding="utf-8"))


def images():
    return [{"id": "demo-ticket", "kind": "ticket", "content": (DIRECTORY / "ticket.jpg").read_bytes()},
            {"id": "demo-receipt", "kind": "payment", "content": (DIRECTORY / "receipt.jpg").read_bytes()}]


def live_available():
    settings = get_settings()
    return settings.ai_provider == "mubit" and bool(settings.mubit_api_key)


@router.get("")
def information():
    data = sample()
    guide = consumer_ai.knowledge()
    data["assessment"]["sources"] = [s for s in guide["sources"] if s["id"] in data["assessment"]["source_ids"]]
    data["assessment"]["knowledge_version"] = guide["version"]
    return {**data, "fictional": True, "live_available": live_available(),
            "recording_requested": consumer_ai.recording_mode(True),
            "ticket_url": "/api/consumer/demo/ticket", "receipt_url": "/api/consumer/demo/receipt",
            "walkthrough_provider": "prewritten-example"}


@router.get("/ticket")
def ticket_image():
    return FileResponse(DIRECTORY / "ticket.jpg", media_type="image/jpeg")


@router.get("/receipt")
def receipt_image():
    return FileResponse(DIRECTORY / "receipt.jpg", media_type="image/jpeg")


def take_live_slot():
    if not live_available():
        raise HTTPException(503, "Live Mubit is unavailable here. You can still use the clearly labelled sample walkthrough.")
    if not _ai_lock.acquire(blocking=False):
        raise HTTPException(429, "Another sample is processing. Try again shortly or use the sample walkthrough.")
    try:
        # A public demonstration may call AI only on our fixed sample. Limits
        # are atomic in the shared database, including across web workers.
        quota("consumer-demo:hour", 60, 3600)
        quota("consumer-demo:day", 200, 86400)
    except Exception:
        _ai_lock.release()
        raise


def metadata(result):
    return {"mode": "live", "provider": result.provider, "model": result.model,
            "request_id": result.request_id, "processed_at": now_iso(),
            "recording_requested": result.meta.get("recording_requested", consumer_ai.recording_mode(True))}


def confirmed_facts(extracted):
    facts = sample()["facts"]
    # Carry the actual scan into assessment; narrative and receipt come only
    # from the fixed example. Bad extraction is surfaced, never silently fixed.
    for key in ("issuer_kind", "issuer", "ticket_ref", "vehicle_registration", "location", "notice_stage"):
        facts[key] = extracted[key]
    for key in ("incident_date", "issue_date", "date_received", "deadline", "discount_deadline"):
        facts[key] = date.fromisoformat(extracted[key]) if extracted[key] else None
    facts["amount_pounds"] = float(extracted["amount_pounds"]) if extracted["amount_pounds"] else None
    return Facts.model_validate(facts).model_dump(mode="json")


@router.post("/scan")
def scan(_: ScanRequest):
    take_live_slot()
    try:
        output, result = consumer_ai.scan(images()[:1], allow_training=True)
        try:
            facts = confirmed_facts(output)
        except (ValueError, TypeError, KeyError):
            raise HTTPException(502, "Mubit could not read valid sample details. Retry the scan or use the sample walkthrough.") from None
        run_id = secrets.token_urlsafe(24)
        response = {**metadata(result), "run_id": run_id, "extracted": output}
        with _state_lock:
            now = time.monotonic()
            for key in list(_runs):
                if _runs[key]["expires"] <= now:
                    del _runs[key]
            while len(_runs) >= MAX_RUNS:
                del _runs[next(iter(_runs))]
            _runs[run_id] = {"facts": facts, "expires": now + RUN_TTL, "assessment": None}
        return response
    finally:
        _ai_lock.release()


@router.post("/assess")
def assess(body: AssessmentRequest):
    if not body.confirmed:
        raise HTTPException(422, "Check and confirm the scanned details first.")
    with _state_lock:
        run = _runs.get(body.run_id)
        if not run or run["expires"] <= time.monotonic():
            raise HTTPException(409, "This demo run expired or the server restarted. Start again to scan the sample.")
        if run["assessment"]:
            return {**run["assessment"], "reused": True}
        facts = dict(run["facts"])
    if facts["issuer_kind"] != "private" or not facts["issuer"] or not facts["ticket_ref"]:
        raise HTTPException(422, "The sample scan missed key details. Start again or use the sample walkthrough.")
    take_live_slot()
    try:
        with _state_lock:
            if run["assessment"]:
                return {**run["assessment"], "reused": True}
        output, result = consumer_ai.assess(facts, images(), allow_training=True)
        response = {**metadata(result), "run_id": body.run_id, "assessment": output, "reused": False}
        with _state_lock:
            run["assessment"] = response
        return response
    finally:
        _ai_lock.release()
