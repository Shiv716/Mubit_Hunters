"""Validates AI output against the contract and the facts the application supplied.

The raw output is always stored as-is. This module produces a *sanitised* copy plus safety flags and an
effective recommendation shown to the reviewer. It never upgrades a needs_review into a decision.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from ..models import AIRecommendation
from .adapters import ProviderResult


@dataclass
class SafetyOutcome:
    status: str  # valid | valid_with_warnings | failed
    failure_kind: str | None
    parsed: dict | None
    flags: list[str] = field(default_factory=list)
    effective_recommendation: str = "needs_review"


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_POLICY_ID = re.compile(r"\bDEMO-POL-[0-9.]+\b")
_REF_LIKE = re.compile(r"\b([A-Z]{2,3}\d{6,})\b")


def _extract_json(raw: str) -> dict:
    text = _FENCE.sub("", raw.strip())
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


def assess(result: ProviderResult, bundle: dict, indicator: str) -> SafetyOutcome:
    if result.error_kind:
        return SafetyOutcome("failed", result.error_kind, None, [f"provider_failure:{result.error_kind}"])
    if not result.raw_text:
        return SafetyOutcome("failed", "empty_output", None, ["empty_output"])
    try:
        data = _extract_json(result.raw_text)
    except (json.JSONDecodeError, ValueError):
        kind = "truncated_output" if result.meta.get("truncated") else "malformed_json"
        return SafetyOutcome("failed", kind, None, [kind])
    if not isinstance(data, dict):
        return SafetyOutcome("failed", "malformed_json", None, ["malformed_json"])
    try:
        rec = AIRecommendation.model_validate(data)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
        return SafetyOutcome("failed", "schema_violation", None, [f"schema_violation:{f}" for f in fields])

    flags: list[str] = []
    extra = set(data) - set(AIRecommendation.model_fields)
    if extra:
        flags.append("unexpected_fields_ignored:" + ",".join(sorted(extra)))

    allowed_refs = {r["id"] for r in bundle["allowed_policy_references"]} | {r["rule_id"] for r in bundle["rule_results"]}
    evidence_ids = {e["id"] for e in bundle["evidence"]}

    unsupported = [r for r in rec.relevant_rule_references if r not in allowed_refs]
    for ref in unsupported:
        flags.append(f"unsupported_reference_removed:{ref}")
    rec.relevant_rule_references = [r for r in rec.relevant_rule_references if r in allowed_refs]

    unknown_ev = [e for e in rec.evidence_references if e not in evidence_ids]
    for ev in unknown_ev:
        flags.append(f"unknown_evidence_removed:{ev}")
    rec.evidence_references = [e for e in rec.evidence_references if e in evidence_ids]

    if rec.draft_response:
        known_tokens = {bundle["case"]["pcn_ref"].upper()}
        for pid in _POLICY_ID.findall(rec.draft_response):
            if pid not in allowed_refs:
                flags.append(f"draft_cites_unsupported_reference:{pid}")
        for tok in _REF_LIKE.findall(rec.draft_response.upper()):
            if tok not in known_tokens:
                flags.append(f"draft_contains_unverified_identifier:{tok}")

    effective = rec.recommendation
    if unsupported or unknown_ev or any(f.startswith("draft_") for f in flags):
        effective = "needs_review"
        rec.draft_response = None
    has_errors = any(i["severity"] == "error" for i in bundle["validation_issues"])
    if rec.recommendation != "needs_review":
        if has_errors:
            flags.append("decision_despite_validation_errors")
            effective = "needs_review"
        if indicator in ("accept", "reject") and indicator != rec.recommendation:
            flags.append(f"conflicts_with_deterministic_checks:{indicator}")
            effective = "needs_review"
    insufficient = [r["rule_id"] for r in bundle["rule_results"] if r["status"] == "insufficient_data"]
    sensitive = any(r["rule_id"] == "R-MITIGATION" and r["status"] != "not_applicable" for r in bundle["rule_results"])
    if sensitive:
        flags.append("human_judgement_required")
        effective = "needs_review"
    if insufficient:
        effective = "needs_review"
    if rec.recommendation != "needs_review" and not rec.relevant_rule_references:
        flags.append("missing_policy_reference")
        effective = "needs_review"
    if insufficient and not rec.missing_information:
        flags.append("missing_information_not_reported:" + ",".join(insufficient))

    return SafetyOutcome(
        status="valid_with_warnings" if flags else "valid",
        failure_kind=None,
        parsed=rec.model_dump(),
        flags=flags,
        effective_recommendation=effective,
    )
