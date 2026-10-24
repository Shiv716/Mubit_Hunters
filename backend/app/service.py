"""Case workflow orchestration: intake -> checks -> AI review -> human decision -> feedback curation."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass

from .ai.adapters import ProviderResult
from .ai.prompt import OUTPUT_JSON_SCHEMA, PROMPT_VERSION, SYSTEM_PROMPT, build_bundle, build_user_message
from .ai.safety import SafetyOutcome, assess
from .db import Connection, audit, lock_case, now_iso, row_to_dict
from .models import CaseIn, CurateIn, DecisionIn, RuleResult, ValidationIssue
from .policy import load_policy
from .precedents import load_eligible, retrieve, summary_text
from .rules import deterministic_indicator, run_rules
from .validation import validate_case


class WorkflowError(ValueError):
    """A request that breaks a workflow rule (maps to HTTP 409/422)."""


@dataclass
class CoreReview:
    issues: list[ValidationIssue]
    rules: list[RuleResult]
    indicator: str
    bundle: dict
    result: ProviderResult
    safety: SafetyOutcome
    input_snapshot: dict


def review_core(case: CaseIn, adapter, precedents: list[dict] | None = None, policy: dict | None = None) -> CoreReview:
    """Pure pipeline used by both the API and the evaluation harness."""
    policy = policy or load_policy()
    issues = validate_case(case, policy)
    rules = run_rules(case, policy)
    indicator = deterministic_indicator(rules, issues)
    bundle = build_bundle(case, issues, rules, policy, precedents)
    user_message = build_user_message(bundle)
    # Capture at inference time, never reconstruct historical requests from current policy.
    snapshot = {"messages": [{"role": "system", "content": SYSTEM_PROMPT},
                             {"role": "user", "content": user_message}],
                "output_schema": deepcopy(OUTPUT_JSON_SCHEMA), "bundle": deepcopy(bundle)}
    settings = getattr(adapter, "settings", None)
    if settings:
        snapshot["gateway"] = {"route": settings.mubit_route, "requested_model": settings.mubit_model,
                               "record": settings.mubit_record, "max_tokens": settings.mubit_max_tokens}
    result = adapter.complete(SYSTEM_PROMPT, user_message, OUTPUT_JSON_SCHEMA)
    snapshot["response_format"] = result.meta.get("response_format")
    safety = assess(result, bundle, indicator)
    return CoreReview(issues, rules, indicator, bundle, result, safety, snapshot)


# ---------------------------------------------------------------- intake & checks

def create_case(conn: Connection, case: CaseIn, actor: str) -> int:
    if conn.execute("SELECT 1 FROM cases WHERE pcn_ref=?", (case.pcn_ref,)).fetchone():
        raise WorkflowError(f"Case {case.pcn_ref} already exists (duplicate PCN reference).")
    ts = now_iso()
    cur = conn.execute(
        "INSERT INTO cases (pcn_ref, case_json, synthetic, created_at, updated_at) VALUES (?,?,?,?,?) ON CONFLICT(pcn_ref) DO NOTHING RETURNING id",
        (case.pcn_ref, case.model_dump_json(), int(case.synthetic), ts, ts),
    )
    inserted = cur.fetchone()
    if not inserted:
        raise WorkflowError(f"Case {case.pcn_ref} already exists (duplicate PCN reference).")
    case_id = inserted[0]
    audit(conn, case_id, "case_created", actor, {"pcn_ref": case.pcn_ref, "synthetic": case.synthetic})
    run_checks(conn, case_id, actor)
    return case_id


def load_case(conn: Connection, case_id: int) -> tuple[dict, CaseIn]:
    row = conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not row:
        raise KeyError(case_id)
    return dict(row), CaseIn.model_validate_json(row["case_json"])


def run_checks(conn: Connection, case_id: int, actor: str) -> int:
    lock_case(conn, case_id)
    _, case = load_case(conn, case_id)
    policy = load_policy()
    issues = validate_case(case, policy)
    rules = run_rules(case, policy)
    indicator = deterministic_indicator(rules, issues)
    cur = conn.execute(
        "INSERT INTO checks (case_id, ruleset_version, policy_version, validation_json, rules_json, indicator, created_at)"
        " VALUES (?,?,?,?,?,?,?) RETURNING id",
        (case_id, policy["ruleset_version"], policy["policy_version"],
         json.dumps([i.model_dump() for i in issues]), json.dumps([r.model_dump() for r in rules]),
         indicator, now_iso()),
    )
    check_id = cur.fetchone()[0]
    _set_status(conn, case_id, "validated", only_from=("new", "validated"))
    audit(conn, case_id, "checks_run", actor, {
        "check_id": check_id, "ruleset_version": policy["ruleset_version"], "indicator": indicator,
        "errors": sum(i.severity == "error" for i in issues), "warnings": sum(i.severity == "warning" for i in issues),
    })
    return check_id


def _set_status(conn: Connection, case_id: int, status: str, only_from: tuple[str, ...] | None = None) -> None:
    if only_from:
        conn.execute(f"UPDATE cases SET status=?, updated_at=? WHERE id=? AND status IN ({','.join('?' * len(only_from))})",
                     (status, now_iso(), case_id, *only_from))
    else:
        conn.execute("UPDATE cases SET status=?, updated_at=? WHERE id=?", (status, now_iso(), case_id))


# ---------------------------------------------------------------- AI review

def run_ai_review(conn: Connection, case_id: int, adapter, mode: str, actor: str, top_k: int = 3) -> int:
    lock_case(conn, case_id)
    row, case = load_case(conn, case_id)
    if row["status"] in ("decided",):
        raise WorkflowError("Case already decided; AI review is closed.")
    check_id = run_checks(conn, case_id, actor)
    precedents: list[dict] = []
    if mode == "precedent":
        query = {"contravention_code": case.contravention_code, "claimed_grounds": case.claimed_grounds,
                 "text": case.representation_text}
        precedents = retrieve(query, load_eligible(conn), top_k=top_k, exclude_case_id=case_id)
    audit(conn, case_id, "ai_review_requested", actor, {
        "provider": adapter.provider, "mode": mode, "prompt_version": PROMPT_VERSION,
        "precedent_ids": [p["precedent_id"] for p in precedents],
    })
    core = review_core(case, adapter, precedents)
    return persist_review(conn, case_id, check_id, core, mode, precedents)


def persist_review(conn, case_id, check_id, core, mode, precedents):
    s, r = core.safety, core.result
    cur = conn.execute(
        """INSERT INTO ai_reviews (case_id, check_id, status, failure_kind, provider, model, provider_request_id,
           prompt_version, ruleset_version, mode, precedent_ids_json, raw_output, parsed_json, safety_flags_json,
           effective_recommendation, latency_ms, usage_json, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING id""",
        (case_id, check_id, s.status, s.failure_kind, r.provider, r.model, r.request_id, PROMPT_VERSION,
         core.bundle["ruleset_version"], mode, json.dumps([p["precedent_id"] for p in precedents]),
         r.raw_text if r.raw_text is not None else r.error_message,
         json.dumps(s.parsed) if s.parsed else None, json.dumps(s.flags), s.effective_recommendation,
         r.latency_ms, json.dumps(r.usage) if r.usage else None, now_iso()),
    )
    review_id = cur.fetchone()[0]
    conn.execute("INSERT INTO review_inputs (ai_review_id,input_json,created_at) VALUES (?,?,?)",
                 (review_id, json.dumps(core.input_snapshot, ensure_ascii=False), now_iso()))
    _set_status(conn, case_id, "ai_failed" if s.status == "failed" else "ai_reviewed",
                only_from=("new", "validated", "ai_reviewed", "ai_failed", "escalated"))
    audit(conn, case_id, "ai_review_failed" if s.status == "failed" else "ai_review_completed", "system", {
        "ai_review_id": review_id, "status": s.status, "failure_kind": s.failure_kind,
        "provider": r.provider, "model": r.model, "provider_request_id": r.request_id,
        "effective_recommendation": s.effective_recommendation, "flags": s.flags, "latency_ms": r.latency_ms,
        "response_format": r.meta.get("response_format"),
    })
    return review_id


# ---------------------------------------------------------------- human decision

REASON_REQUIRED = {"override", "reject", "escalate"}
_LABEL = {"representation_accepted": "accept", "representation_rejected": "reject", "escalated": "needs_review"}
_OUTCOME = {"accept": "representation_accepted", "reject": "representation_rejected"}


def record_decision(conn: Connection, case_id: int, d: DecisionIn) -> int:
    lock_case(conn, case_id)
    row, case = load_case(conn, case_id)
    if row["status"] == "decided":
        raise WorkflowError("Case already has a final decision.")
    review = None
    if d.ai_review_id is not None:
        review = conn.execute("SELECT * FROM ai_reviews WHERE id=? AND case_id=?", (d.ai_review_id, case_id)).fetchone()
        if not review:
            raise WorkflowError("ai_review_id does not belong to this case.")
    if d.action in REASON_REQUIRED and not (d.reason and d.reason.strip()):
        raise WorkflowError(f"A reason is required for '{d.action}'.")

    ai_rec = review["effective_recommendation"] if review else None
    latest = conn.execute("SELECT id FROM ai_reviews WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
    if review and latest and review["id"] != latest["id"]:
        raise WorkflowError("This recommendation has been replaced. Refresh the case before deciding.")
    last_check = conn.execute("SELECT id FROM checks WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
    if review and last_check and review["check_id"] != last_check["id"]:
        raise WorkflowError("The evidence changed after this recommendation. Review the case again.")
    if d.action == "accept":
        if not review or review["status"] == "failed":
            raise WorkflowError("No valid AI recommendation to accept; use override or reject with a reason.")
        if ai_rec not in _OUTCOME:
            raise WorkflowError("The AI recommends needs_review; choose override, reject or escalate.")
        final_outcome = _OUTCOME[ai_rec]
    elif d.action == "escalate":
        final_outcome = "escalated"
    else:
        if d.final_outcome not in ("representation_accepted", "representation_rejected"):
            raise WorkflowError(f"'{d.action}' requires final_outcome accepted or rejected.")
        if d.action == "override" and review is None:
            raise WorkflowError("override needs an ai_review_id; use reject to decide without the AI.")
        final_outcome = d.final_outcome

    final_response = d.final_response
    if final_response is None and review and review["parsed_json"] and d.action == "accept":
        final_response = json.loads(review["parsed_json"]).get("draft_response")

    linked = conn.execute("SELECT 1 FROM integration_cases WHERE case_id=?", (case_id,)).fetchone()
    if linked and final_outcome != "escalated":
        if not review or review["provider"] != "mubit" or review["status"] == "failed":
            raise WorkflowError("Council-connected cases require a successful Mubit review before a final decision. You can refer the case for investigation while Mubit is unavailable.")
        if not final_response or not final_response.strip():
            raise WorkflowError("An approved response is required before returning a council decision.")

    cur = conn.execute(
        """INSERT INTO decisions (case_id, ai_review_id, action, final_outcome, ai_recommendation, reason_code, reason,
           final_response, reviewer, created_at) VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING id""",
        (case_id, d.ai_review_id, d.action, final_outcome, ai_rec, d.reason_code, d.reason, final_response,
         d.reviewer, now_iso()),
    )
    decision_id = cur.fetchone()[0]
    _set_status(conn, case_id, "escalated" if final_outcome == "escalated" else "decided")
    audit(conn, case_id, "decision_recorded", d.reviewer, {
        "decision_id": decision_id, "ai_review_id": d.ai_review_id, "action": d.action,
        "final_outcome": final_outcome, "ai_recommendation": ai_rec, "reason_code": d.reason_code,
        "reason": d.reason, "agrees_with_ai": _LABEL[final_outcome] == ai_rec if ai_rec else None,
        "note": "Decision recorded only. This tool does not issue, cancel or submit PCN decisions.",
    })

    if final_outcome != "escalated":
        fcur = conn.execute(
            """INSERT INTO feedback_examples (case_id, decision_id, source, contravention_code, claimed_grounds,
               summary_text, final_label, ai_label, correction_reason, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING id""",
            (case_id, decision_id, "review", case.contravention_code, ",".join(case.claimed_grounds),
             summary_text(case.model_dump()), _LABEL[final_outcome], ai_rec, d.reason, now_iso()),
        )
        audit(conn, case_id, "feedback_example_created", "system",
              {"feedback_id": fcur.fetchone()[0], "curation_status": "pending"})
    return decision_id


def curate_feedback(conn: Connection, feedback_id: int, c: CurateIn) -> None:
    row = conn.execute("SELECT * FROM feedback_examples WHERE id=?", (feedback_id,)).fetchone()
    if not row:
        raise KeyError(feedback_id)
    if c.eligible and row["case_id"]:
        case_row = conn.execute("SELECT synthetic FROM cases WHERE id=?", (row["case_id"],)).fetchone()
        if case_row and not case_row["synthetic"]:
            raise WorkflowError("Only synthetic/authorised data may be curated in the demo.")
    conn.execute(
        "UPDATE feedback_examples SET curation_status=?, curated_by=?, curation_note=?, curated_at=? WHERE id=?",
        ("eligible" if c.eligible else "ineligible", c.curator, c.note, now_iso(), feedback_id),
    )
    audit(conn, row["case_id"], "feedback_curated", c.curator,
          {"feedback_id": feedback_id, "eligible": c.eligible, "note": c.note})


# ---------------------------------------------------------------- read models

def case_detail(conn: Connection, case_id: int) -> dict:
    row, case = load_case(conn, case_id)
    check = row_to_dict(conn.execute("SELECT * FROM checks WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone())
    reviews = [row_to_dict(r) for r in conn.execute("SELECT * FROM ai_reviews WHERE case_id=? ORDER BY id DESC", (case_id,))]
    decisions = [dict(r) for r in conn.execute("SELECT * FROM decisions WHERE case_id=? ORDER BY id DESC", (case_id,))]
    events = [row_to_dict(r) for r in conn.execute("SELECT * FROM audit_events WHERE case_id=? ORDER BY id", (case_id,))]
    files = [dict(r) for r in conn.execute("SELECT * FROM evidence_files WHERE case_id=?", (case_id,))]
    feedback = [dict(r) for r in conn.execute("SELECT * FROM feedback_examples WHERE case_id=?", (case_id,))]
    for review in reviews:
        trace = conn.execute("SELECT steps_json FROM investigations WHERE ai_review_id=?", (review["id"],)).fetchone()
        review["steps"] = json.loads(trace[0]) if trace else []
    policy = load_policy()
    integration = conn.execute("""SELECT i.source_case_id,i.source_version,i.imported_at,
        w.council_id,w.source_system FROM integration_cases i CROSS JOIN integration_identity w
        WHERE i.case_id=? AND w.id=1""", (case_id,)).fetchone()
    connection = dict(integration) if integration else None
    if connection:
        final = next((d for d in decisions if d["final_outcome"] != "escalated"), None)
        receipt = conn.execute("SELECT received_at FROM integration_receipts WHERE decision_id=?", (final["id"],)).fetchone() if final else None
        connection["delivery_status"] = "received" if receipt else "awaiting_receipt" if final else "awaiting_decision"
        connection["received_at"] = receipt[0] if receipt else None
    return {
        "id": row["id"], "status": row["status"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        "case": case.model_dump(mode="json"),
        "contravention_description": policy["contraventions"].get(case.contravention_code, {}).get("description"),
        "checks": check, "ai_reviews": reviews, "decisions": decisions, "audit": events,
        "evidence_files": files, "feedback": feedback, "integration": connection,
    }
