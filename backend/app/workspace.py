"""Officer-facing API. Slow model calls run outside database write transactions."""
import json
from datetime import date
from zoneinfo import ZoneInfo
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .ai.adapters import get_adapter
from .config import get_settings
from .db import transaction, audit, now_iso, lock_case, claim_review, release_review
from .investigator import investigate
from .models import DecisionIn, ResolutionIn
from .precedents import load_eligible
from .service import (WorkflowError, case_detail, load_case, persist_review, record_decision,
                      review_core, run_checks)

router = APIRouter(prefix="/api")


def queue_rows(conn):
    today = datetime.now(ZoneInfo("Europe/London")).date()
    rows = conn.execute("""SELECT c.*,
        (SELECT effective_recommendation FROM ai_reviews WHERE case_id=c.id
         AND check_id=(SELECT id FROM checks WHERE case_id=c.id ORDER BY id DESC LIMIT 1)
         ORDER BY id DESC LIMIT 1) rec,
        (SELECT final_outcome FROM decisions WHERE case_id=c.id ORDER BY id DESC LIMIT 1) outcome
        FROM cases c""").fetchall()
    result = []
    for row in rows:
        c = json.loads(row["case_json"])
        due = c.get("response_due_date")
        days = (date.fromisoformat(due) - today).days if due else None
        lane = "done" if row["status"] == "decided" else "investigate" if row["status"] in ("escalated", "ai_failed") or row["rec"] == "needs_review" else "ready" if row["rec"] else "new"
        result.append({"id": row["id"], "pcn_ref": c["pcn_ref"], "location": c["location"],
            "claim": c["representation_text"], "grounds": c["claimed_grounds"], "lane": lane,
            "status": row["status"], "recommendation": row["rec"], "outcome": row["outcome"],
            "due_date": due, "days_left": days, "code": c["contravention_code"],
            "received": c["representation_received_date"], "evidence_count": len(c["evidence"])})
    return sorted(result, key=lambda r: (r["lane"] == "done", r["days_left"] if r["days_left"] is not None else 99999, r["received"], r["id"]))


@router.get("/queue")
def queue():
    with transaction() as conn:
        return queue_rows(conn)


@router.post("/cases/{case_id}/review")
def review(case_id: int, request: Request):
    token = None
    try:
        with transaction() as conn:
            snapshot, case = load_case(conn, case_id)
            if snapshot["status"] == "decided":
                raise HTTPException(409, "This case already has a final decision.")
            if not case.synthetic:
                raise HTTPException(422, "This demo accepts synthetic cases only.")
            examples = [e for e in load_eligible(conn) if e.get("case_id") != case_id]
            linked = conn.execute("SELECT 1 FROM integration_cases WHERE case_id=?", (case_id,)).fetchone()
        settings = get_settings()
        token = claim_review(case_id, max(600, int(settings.mubit_timeout_s * 16 + 120)))
        if not token:
            raise HTTPException(409, "This case is already being reviewed.")
        adapter = get_adapter(settings, require_mubit=bool(linked))
        try:
            steps, precedents = investigate(case, adapter, examples, settings.precedent_top_k)
            core = review_core(case, adapter, precedents)
        finally:
            if getattr(adapter, "client", None):
                adapter.client.close()
        steps.append({"tool": "recommendation", "label": "Recommendation prepared", "status": "failed" if core.safety.status == "failed" else "complete",
                      "summary": "Ready for the officer's decision." if core.safety.status != "failed" else "AI unavailable. Review the evidence and decide manually.",
                      "source": core.result.provider, "request_id": core.result.request_id,
                      "model": core.result.model, "latency_ms": core.result.latency_ms, "usage": core.result.usage})
        with transaction() as conn:
            lock_case(conn, case_id)
            lease = conn.execute("SELECT token FROM review_leases WHERE case_id=?", (case_id,)).fetchone()
            if not lease or lease[0] != token:
                raise HTTPException(409, "The review expired. Refresh and try again.")
            current, _ = load_case(conn, case_id)
            if current["updated_at"] != snapshot["updated_at"] or current["status"] == "decided":
                raise HTTPException(409, "The case changed during review. Refresh and review the latest evidence.")
            check_id = run_checks(conn, case_id, "review-agent")
            rid = persist_review(conn, case_id, check_id, core, "precedent", precedents)
            conn.execute("INSERT INTO investigations (ai_review_id, steps_json, created_at) VALUES (?,?,?)",
                         (rid, json.dumps(steps), now_iso()))
            audit(conn, case_id, "investigation_completed", "review-agent", {"review_id": rid, "steps": len(steps)})
            return case_detail(conn, case_id)
    except KeyError:
        raise HTTPException(404, "Case not found")
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    finally:
        if token:
            release_review(case_id, token)


def letter_text(case, outcome, explanation=""):
    lead = {"accept": "We have accepted your appeal. The proposed outcome is cancellation of the penalty charge.",
            "reject": "We have considered your appeal. The proposed outcome is that the penalty charge remains payable.",
            "needs_review": "Your appeal requires further investigation before a decision can be made."}[outcome]
    return f"Dear motorist,\n\nRe: {case.pcn_ref}\n\nThank you for your appeal concerning {case.location}.\n\n{lead}\n\n{explanation.strip()}\n\nYours sincerely,\nParking Services".replace("\n\n\n", "\n\n")


@router.get("/cases/{case_id}/draft")
def draft(case_id: int, outcome: str, reason: str = ""):
    if outcome not in ("accept", "reject", "needs_review"):
        raise HTTPException(422, "Choose an appeal outcome.")
    with transaction() as conn:
        try:
            _, c = load_case(conn, case_id)
        except KeyError:
            raise HTTPException(404, "Case not found")
        return {"text": letter_text(c, outcome, reason)}


@router.post("/cases/{case_id}/resolve")
def resolve(case_id: int, body: ResolutionIn, request: Request):
    try:
        with transaction() as conn:
            lock_case(conn, case_id)
            detail = case_detail(conn, case_id)
            latest = detail["ai_reviews"][0] if detail["ai_reviews"] else None
            if latest and detail["checks"] and latest["check_id"] != detail["checks"]["id"]:
                if body.review_id is not None:
                    raise HTTPException(409, "Evidence changed. Review again or make a reasoned manual decision.")
                latest = None
            if (latest["id"] if latest else None) != body.review_id:
                raise HTTPException(409, "The recommendation changed. Refresh before saving.")
            agrees = latest and latest["status"] != "failed" and body.outcome == latest["effective_recommendation"] and body.outcome != "needs_review"
            if not agrees and not body.reason.strip():
                raise HTTPException(422, "Add a reason for changing the recommendation or investigating further.")
            if body.outcome != "needs_review" and not body.response.strip():
                raise HTTPException(422, "Review and complete the response before saving.")
            reviewer = getattr(request.state, "reviewer", None) or body.reviewer
            d = DecisionIn(ai_review_id=body.review_id,
                action="escalate" if body.outcome == "needs_review" else "accept" if agrees else "override" if latest else "reject",
                final_outcome={"accept": "representation_accepted", "reject": "representation_rejected", "needs_review": "escalated"}[body.outcome],
                reason=body.reason, reason_code="officer_judgement" if not agrees else None,
                final_response=body.response if body.outcome != "needs_review" else None, reviewer=reviewer)
            record_decision(conn, case_id, d)
            return case_detail(conn, case_id)
    except KeyError:
        raise HTTPException(404, "Case not found")
    except WorkflowError as e:
        raise HTTPException(409, str(e))


@router.get("/cases/{case_id}/response")
def download_response(case_id: int):
    with transaction() as conn:
        row = conn.execute("SELECT final_response FROM decisions WHERE case_id=? AND final_outcome!='escalated' ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
        if not row or not row[0]:
            raise HTTPException(404, "No approved response is available.")
        return PlainTextResponse(row[0], headers={"Content-Disposition": f'attachment; filename="appeal-{case_id}-response.txt"'})


@router.get("/insights")
def insights():
    with transaction() as conn:
        rows = queue_rows(conn)
        decisions = conn.execute("SELECT * FROM decisions WHERE final_outcome!='escalated'").fetchall()
        mapping = {"representation_accepted": "accept", "representation_rejected": "reject"}
        comparable = [d for d in decisions if d["ai_recommendation"] in ("accept", "reject")]
        agree = sum(mapping[d["final_outcome"]] == d["ai_recommendation"] for d in comparable)
        corrections = sum(mapping[d["final_outcome"]] != d["ai_recommendation"] for d in decisions if d["ai_recommendation"])
        groups = {}
        for r in rows:
            if r["outcome"] == "representation_accepted":
                g = groups.setdefault(r["location"], {"location": r["location"], "accepted": 0, "cases": []})
                g["accepted"] += 1
                g["cases"].append(r["pcn_ref"])
        return {"total": len(rows), "pending": sum(r["lane"] != "done" for r in rows),
            "reviewed": sum(r["recommendation"] is not None for r in rows),
            "decided": len(decisions), "accepted": sum(d["final_outcome"] == "representation_accepted" for d in decisions),
            "rejected": sum(d["final_outcome"] == "representation_rejected" for d in decisions),
            "investigating": sum(r["status"] == "escalated" for r in rows),
            "agreement": round(100 * agree / len(comparable)) if comparable else None, "compared": len(comparable),
            "corrections": corrections, "eligible": conn.execute("SELECT count(*) FROM feedback_examples WHERE curation_status='eligible' AND source='review'").fetchone()[0],
            "locations": sorted(groups.values(), key=lambda g: -g["accepted"]), "training_status": "unverified"}
