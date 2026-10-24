"""Evidence and case validation: required fields, missing evidence, duplicates, inconsistent facts."""
from __future__ import annotations

from collections import Counter

from .models import CaseIn, ValidationIssue
from .policy import load_policy


def _norm_vrm(value: str) -> str:
    return "".join(value.split()).upper()


def validate_case(case: CaseIn, policy: dict | None = None) -> list[ValidationIssue]:
    policy = policy or load_policy()
    issues: list[ValidationIssue] = []
    contraventions = policy["contraventions"]

    def add(code: str, severity: str, message: str, field: str | None = None) -> None:
        issues.append(ValidationIssue(code=code, severity=severity, message=message, field=field))

    # Required / known fields
    if case.contravention_code not in contraventions:
        add("unknown_contravention_code", "error",
            f"Contravention code {case.contravention_code!r} is not in the policy fixture.", "contravention_code")
    if not case.representation_text.strip():
        add("missing_representation", "error", "Representation text is empty.", "representation_text")
    if not case.zone:
        add("missing_zone", "warning", "No zone recorded; payment/permit zone checks cannot run.", "zone")

    # Date consistency
    if case.notice_date < case.contravention_datetime.date():
        add("notice_before_contravention", "error", "Notice date is before the contravention date.", "notice_date")
    if case.representation_received_date < case.notice_date:
        add("representation_before_notice", "error",
            "Representation received before the notice date.", "representation_received_date")

    # Evidence: duplicates
    id_counts = Counter(e.id for e in case.evidence)
    for eid, n in id_counts.items():
        if n > 1:
            add("duplicate_evidence_id", "error", f"Evidence id {eid} is used {n} times.", "evidence")
    hash_counts = Counter(e.sha256 for e in case.evidence if e.sha256)
    for digest, n in hash_counts.items():
        if n > 1:
            ids = [e.id for e in case.evidence if e.sha256 == digest]
            add("duplicate_evidence_file", "warning",
                f"Evidence items {', '.join(ids)} have identical file content.", "evidence")

    # Only the selected council policy can make an evidence type mandatory.
    present_types = {e.type for e in case.evidence}
    spec = contraventions.get(case.contravention_code)
    if spec:
        for req in spec.get("required_evidence", []):
            if req not in present_types:
                add("missing_required_evidence", "error",
                    f"Required evidence '{req}' for code {case.contravention_code} is missing.", "evidence")

    # Evidence expected to support each claimed ground (record supplied by council also counts)
    record_backed = {
        "paid": case.records.payments is not None,
        "permit": case.records.permits is not None,
        "blue_badge": case.records.badges is not None,
    }
    for ground in case.claimed_grounds:
        expected = policy["claim_evidence"].get(ground, [])
        if expected and not (present_types & set(expected)) and not record_backed.get(ground, False):
            add("missing_claim_evidence", "warning",
                f"Claim '{ground}' has no supporting evidence ({' or '.join(expected)}).", "evidence")

    # Inconsistent facts between case and evidence/records
    case_vrm = _norm_vrm(case.vrm)
    for e in case.evidence:
        if e.vrm_seen and _norm_vrm(e.vrm_seen) != case_vrm:
            add("vrm_mismatch_evidence", "error",
                f"Evidence {e.id} shows VRM {e.vrm_seen}, case VRM is {case.vrm}.", "evidence")
        if e.captured_at and e.type == "ceo_photo":
            delta = abs((e.captured_at - case.contravention_datetime).total_seconds()) / 60
            if delta > 60:
                add("evidence_time_mismatch", "warning",
                    f"CEO photo {e.id} was captured {delta:.0f} min from the contravention time.", "evidence")
    for p in case.records.payments or []:
        if _norm_vrm(p.vrm) != case_vrm:
            add("vrm_mismatch_payment", "warning",
                f"Payment {p.reference} is for VRM {p.vrm}, not {case.vrm}.", "records.payments")
    for p in case.records.permits or []:
        if _norm_vrm(p.vrm) != case_vrm:
            add("vrm_mismatch_permit", "warning",
                f"Permit {p.permit_id} is for VRM {p.vrm}, not {case.vrm}.", "records.permits")

    if spec and spec.get("min_observation_minutes", 0) > 0 and case.observation_minutes is None:
        add("missing_observation_period", "warning",
            "Observation period not recorded for a code that requires one.", "observation_minutes")

    return issues
