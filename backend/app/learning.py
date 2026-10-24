"""Reviewed correction packages. No undocumented Mubit training API is called here."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .access import required, session_data
from .ai.adapters import ProviderResult
from .ai.prompt import PROMPT_VERSION
from .ai.safety import assess
from .db import audit, lock_case, now_iso, row_to_dict, transaction
from .models import AIRecommendation
from .policy import load_policy

router = APIRouter(prefix="/api/learning", tags=["learning"])


def connection():
    with transaction() as conn:
        yield conn


def owner(request: Request):
    if not required():
        return "local-owner"
    session = session_data(request)
    if not session or not session.get("owner"):
        raise HTTPException(403, "Only the workspace owner can approve or export model corrections.")
    return session.get("email") or session["name"]


class CorrectedAnswer(AIRecommendation):
    model_config = ConfigDict(extra="forbid", strict=True)
    relevant_rule_references: list[str]
    evidence_references: list[str]
    missing_information: list[str]
    uncertainty_flags: list[str]
    draft_response: str | None


class CorrectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Literal["approved", "withdrawn"] = "approved"
    target: CorrectedAnswer | None = None
    note: str = Field(min_length=1, max_length=2000)
    previous_revision: int | None = None

    @field_validator("note")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Explain the correction or withdrawal.")
        return value.strip()


_ROWS = """SELECT f.id,f.case_id,f.decision_id,f.final_label,f.correction_reason,
    c.pcn_ref,c.synthetic,d.reviewer,d.final_response,
    r.id AS review_id,r.provider,r.model,r.provider_request_id,r.prompt_version,
    r.raw_output,r.parsed_json,r.effective_recommendation,r.status AS review_status,
    k.indicator,i.input_json,
    m.id AS correction_id,m.state,m.target_json,m.note,m.approved_by,m.created_at AS approved_at
    FROM feedback_examples f JOIN cases c ON c.id=f.case_id
    JOIN decisions d ON d.id=f.decision_id
    LEFT JOIN ai_reviews r ON r.id=d.ai_review_id
    LEFT JOIN checks k ON k.id=r.check_id
    LEFT JOIN review_inputs i ON i.ai_review_id=r.id
    LEFT JOIN model_corrections m ON m.id=(SELECT MAX(x.id) FROM model_corrections x WHERE x.feedback_id=f.id)
    WHERE f.source='review'"""


def examples(conn, feedback_id=None):
    query = _ROWS + (" AND f.id=?" if feedback_id is not None else "") + " ORDER BY f.id DESC"
    rows = conn.execute(query, (feedback_id,) if feedback_id is not None else ()).fetchall()
    policy_version = load_policy()["policy_version"]
    output = []
    for row in rows:
        item = row_to_dict(row)
        snapshot = item.get("input")
        blocked = None
        if not snapshot:
            blocked = "Original input was not captured. Corrections are available for new reviews only."
        elif not item["synthetic"]:
            blocked = "Only synthetic cases can be prepared in this workspace."
        elif item["review_status"] == "failed" or not item["parsed"]:
            blocked = "The original review failed; there is no successful answer to correct."
        elif snapshot["bundle"]["policy_version"] != policy_version or item["prompt_version"] != PROMPT_VERSION:
            blocked = "This review used an older policy or prompt. Keep it as history, not a current training example."
        item["blocked_reason"] = blocked
        item["exportable"] = not blocked and item["state"] == "approved" and item["provider"] == "mubit" and bool(item["provider_request_id"])
        output.append(item)
    return output


def public_example(item):
    # Detailed input is only included in an explicitly requested owner export.
    snapshot = item.pop("input", None)
    bundle = snapshot["bundle"] if snapshot else {}
    item["policy_version"] = bundle.get("policy_version")
    item["allowed_policy_references"] = [r["id"] for r in bundle.get("allowed_policy_references", [])]
    item["allowed_policy_references"] += [r["rule_id"] for r in bundle.get("rule_results", [])]
    item["allowed_evidence_references"] = [e["id"] for e in bundle.get("evidence", [])]
    item["human_judgement_required"] = any(r["rule_id"] == "R-MITIGATION" and r["status"] != "not_applicable"
                                          for r in bundle.get("rule_results", []))
    return item


@router.get("/examples")
def list_examples(conn=Depends(connection)):
    return {"training_status": "not_connected", "updated_model": None,
            "items": [public_example(item) for item in examples(conn)]}


@router.post("/examples/{feedback_id}/correction")
def save_correction(feedback_id: int, body: CorrectionIn, actor=Depends(owner), conn=Depends(connection)):
    found = conn.execute("SELECT case_id FROM feedback_examples WHERE id=? AND source='review'", (feedback_id,)).fetchone()
    if not found:
        raise HTTPException(404, "Feedback example not found.")
    lock_case(conn, found[0])
    rows = examples(conn, feedback_id)
    if not rows:
        raise HTTPException(404, "Feedback example not found.")
    item = rows[0]
    if item["correction_id"] != body.previous_revision:
        raise HTTPException(409, "This correction changed. Refresh before saving.")
    target = None
    if body.state == "approved":
        if item["blocked_reason"]:
            raise HTTPException(409, item["blocked_reason"])
        if not body.target:
            raise HTTPException(422, "A complete corrected answer is required.")
        target = body.target.model_dump()
        if not target["reason_summary"].strip() or len(json.dumps(target)) > 30000:
            raise HTTPException(422, "Provide a nonblank correction of at most 30,000 characters.")
        if target["recommendation"] != "needs_review" and target["missing_information"]:
            raise HTTPException(422, "Clear missing facts that no longer apply, or choose needs_review while facts needed to decide are missing.")
        checked = assess(ProviderResult(provider="officer-correction", model=None,
                         raw_text=json.dumps(target)), item["input"]["bundle"], item["indicator"])
        # An officer may decide a discretionary case; the model must still refer it to a human.
        flags = [flag for flag in checked.flags if flag != "human_judgement_required"]
        if checked.status == "failed" or flags or checked.effective_recommendation != target["recommendation"]:
            raise HTTPException(422, "Correction conflicts with the recorded facts or policy. Use needs_review for missing facts or human judgement, and cite only supplied references."
                                + (" Checks: " + ", ".join(flags) if flags else ""))
    elif item["state"] != "approved":
        raise HTTPException(409, "There is no approved correction to withdraw.")
    revision = conn.execute("""INSERT INTO model_corrections
        (feedback_id,state,target_json,note,approved_by,created_at) VALUES (?,?,?,?,?,?) RETURNING id""",
        (feedback_id, body.state, json.dumps(target) if target else None, body.note, actor, now_iso())).fetchone()[0]
    audit(conn, item["case_id"], "model_correction_" + body.state, actor,
          {"feedback_id": feedback_id, "correction_id": revision, "ai_review_id": item["review_id"],
           "previous_revision": body.previous_revision, "submitted_to_mubit": False})
    return public_example(examples(conn, feedback_id)[0])


@router.get("/export")
def export_corrections(actor=Depends(owner), conn=Depends(connection)):
    rows = [item for item in examples(conn) if item["exportable"]]
    if not rows:
        raise HTTPException(409, "No approved Mubit examples are ready. Local simulations and historical reviews without captured inputs are excluded.")
    package = {"format": "civic-corrections-v1", "created_at": now_iso(), "submitted_to_mubit": False,
               "training_status": "not_connected", "examples": []}
    for row in rows:
        content = {"input": row["input"], "target": row["target"]}
        digest = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        package["examples"].append({"correction_id": row["correction_id"], "review_id": row["review_id"],
            "decision_id": row["decision_id"], "provider": row["provider"], "model": row["model"],
            "provider_request_id": row["provider_request_id"], "prompt_version": row["prompt_version"],
            "original_output": row["raw_output"], "officer_final_outcome": row["final_label"],
            "approved_by": row["approved_by"], "approved_at": row["approved_at"], "note": row["note"],
            "sha256": digest, **content})
    audit(conn, None, "model_corrections_exported", actor,
          {"correction_ids": [row["correction_id"] for row in rows], "submitted_to_mubit": False})
    return Response(json.dumps(package, indent=2, ensure_ascii=False), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="civic-corrections.json"'})
