"""Deterministic, versioned rule checks. Plain functions over verifiable facts.

Each rule returns a RuleResult with:
  status - outcome of the check itself (pass / fail / not_applicable / insufficient_data)
  effect - which way the verified fact points for the representation
           (supports_accept / supports_reject / needs_review / neutral)
"""
from __future__ import annotations

from typing import Callable

from .models import CaseIn, RuleResult, ValidationIssue
from .policy import load_policy

RuleFn = Callable[[CaseIn, dict], RuleResult]
_RULES: dict[str, RuleFn] = {}


def rule(rule_id: str) -> Callable[[RuleFn], RuleFn]:
    def register(fn: RuleFn) -> RuleFn:
        _RULES[rule_id] = fn
        return fn
    return register


def _result(policy: dict, rule_id: str, status: str, effect: str, finding: str, refs: list[str] | None = None) -> RuleResult:
    return RuleResult(rule_id=rule_id, ruleset_version=policy["ruleset_version"], status=status,
                      effect=effect, finding=finding, policy_refs=refs or [])


def _norm(value: str) -> str:
    return "".join(value.split()).upper()


def _evidence_types(case: CaseIn) -> set[str]:
    return {e.type for e in case.evidence}


@rule("R-DEADLINE")
def check_deadline(case: CaseIn, policy: dict) -> RuleResult:
    window = policy["parameters"]["representation_window_days"]
    days = (case.representation_received_date - case.notice_date).days
    if days < 0:
        return _result(policy, "R-DEADLINE", "insufficient_data", "needs_review",
                       "Representation date precedes notice date; dates are inconsistent.", ["DEMO-POL-9.1"])
    if days <= window:
        return _result(policy, "R-DEADLINE", "pass", "neutral",
                       f"Received {days} day(s) after notice, within the {window}-day window.", ["DEMO-POL-2.1"])
    return _result(policy, "R-DEADLINE", "fail", "needs_review",
                   f"Received {days} day(s) after notice, outside the {window}-day window (officer discretion).",
                   ["DEMO-POL-2.1"])


@rule("R-PAYMENT")
def check_payment(case: CaseIn, policy: dict) -> RuleResult:
    payments = case.records.payments
    if payments is None:
        receipt = "payment_receipt" in _evidence_types(case)
        note = " A motorist receipt was supplied but is unverified." if receipt else ""
        return _result(policy, "R-PAYMENT", "insufficient_data", "needs_review",
                       "No council payment records supplied." + note, ["DEMO-POL-3.1", "DEMO-POL-9.1"])
    if not case.zone:
        return _result(policy, "R-PAYMENT", "insufficient_data", "needs_review",
                       "Case zone missing; cannot match payments to zone.", ["DEMO-POL-9.1"])
    t = case.contravention_datetime
    for p in payments:
        if _norm(p.vrm) == _norm(case.vrm) and p.zone == case.zone and p.start <= t <= p.end:
            return _result(policy, "R-PAYMENT", "pass", "supports_accept",
                           f"Payment {p.reference} covers {case.vrm} in zone {p.zone} at the contravention time.",
                           ["DEMO-POL-3.1"])
    return _result(policy, "R-PAYMENT", "fail", "supports_reject",
                   f"None of {len(payments)} supplied payment record(s) covers the vehicle, zone and time.",
                   ["DEMO-POL-3.1"])


@rule("R-GRACE")
def check_grace(case: CaseIn, policy: dict) -> RuleResult:
    grace = policy["parameters"]["paid_parking_grace_minutes"]
    payments = case.records.payments
    if payments is None or not case.zone:
        return _result(policy, "R-GRACE", "insufficient_data", "needs_review",
                       "Payment records or zone not supplied; grace period cannot be checked.", ["DEMO-POL-3.2"])
    t = case.contravention_datetime
    ended = [p for p in payments
             if _norm(p.vrm) == _norm(case.vrm) and p.zone == case.zone and p.end <= t]
    if not ended:
        return _result(policy, "R-GRACE", "not_applicable", "neutral",
                       "No expired paid session for this vehicle/zone before the contravention.", [])
    last = max(ended, key=lambda p: p.end)
    minutes = (t - last.end).total_seconds() / 60
    if minutes < grace:
        return _result(policy, "R-GRACE", "fail", "supports_accept",
                       f"Notice issued {minutes:.0f} min after paid time expired, inside the {grace}-min grace period.",
                       ["DEMO-POL-3.2"])
    return _result(policy, "R-GRACE", "pass", "neutral",
                   f"Notice issued {minutes:.0f} min after paid time expired; grace period of {grace} min respected.",
                   ["DEMO-POL-3.2"])


@rule("R-PERMIT")
def check_permit(case: CaseIn, policy: dict) -> RuleResult:
    permits = case.records.permits
    if permits is None:
        return _result(policy, "R-PERMIT", "insufficient_data", "needs_review",
                       "No council permit records supplied.", ["DEMO-POL-4.1", "DEMO-POL-9.1"])
    t = case.contravention_datetime
    for p in permits:
        if _norm(p.vrm) == _norm(case.vrm) and p.zone == case.zone and p.valid_from <= t <= p.valid_to:
            if p.displayed is False:
                if case.prior_undisplayed_permit_count == 0:
                    return _result(policy, "R-PERMIT", "pass", "needs_review",
                                   f"Permit {p.permit_id} valid but not displayed; first occurrence (discretion).",
                                   ["DEMO-POL-4.2"])
                return _result(policy, "R-PERMIT", "pass", "supports_reject",
                               f"Permit {p.permit_id} valid but not displayed; {case.prior_undisplayed_permit_count} "
                               "prior occurrence(s).", ["DEMO-POL-4.2"])
            return _result(policy, "R-PERMIT", "pass", "supports_accept",
                           f"Permit {p.permit_id} valid for {case.vrm} in zone {p.zone} at the contravention time.",
                           ["DEMO-POL-4.1"])
    return _result(policy, "R-PERMIT", "fail", "supports_reject",
                   f"No supplied permit is valid for the vehicle, zone and time ({len(permits)} checked).",
                   ["DEMO-POL-4.1"])


@rule("R-BADGE")
def check_badge(case: CaseIn, policy: dict) -> RuleResult:
    badges = case.records.badges
    if badges is None:
        return _result(policy, "R-BADGE", "insufficient_data", "needs_review",
                       "No badge records supplied.", ["DEMO-POL-5.1", "DEMO-POL-9.1"])
    d = case.contravention_datetime.date()
    for b in badges:
        if b.valid_from <= d <= b.valid_to:
            if b.displayed is False:
                return _result(policy, "R-BADGE", "pass", "needs_review",
                               f"Badge {b.badge_id} valid but recorded as not displayed.", ["DEMO-POL-5.1"])
            return _result(policy, "R-BADGE", "pass", "supports_accept",
                           f"Badge {b.badge_id} valid on {d.isoformat()}.", ["DEMO-POL-5.1"])
    return _result(policy, "R-BADGE", "fail", "supports_reject",
                   "No supplied badge was valid on the contravention date.", ["DEMO-POL-5.1"])


@rule("R-OBSERVATION")
def check_observation(case: CaseIn, policy: dict) -> RuleResult:
    spec = policy["contraventions"].get(case.contravention_code, {})
    minimum = spec.get("min_observation_minutes", policy["parameters"]["default_min_observation_minutes"])
    if minimum <= 0:
        return _result(policy, "R-OBSERVATION", "not_applicable", "neutral", "No observation period required.")
    if case.observation_minutes is None:
        return _result(policy, "R-OBSERVATION", "insufficient_data", "needs_review",
                       f"Observation period not recorded (minimum {minimum} min).", ["DEMO-POL-6.2"])
    if case.observation_minutes < minimum:
        return _result(policy, "R-OBSERVATION", "fail", "supports_accept",
                       f"Observed {case.observation_minutes} min, below the {minimum}-min minimum.", ["DEMO-POL-6.2"])
    return _result(policy, "R-OBSERVATION", "pass", "neutral",
                   f"Observed {case.observation_minutes} min, meets the {minimum}-min minimum.", ["DEMO-POL-6.2"])


@rule("R-LOADING")
def check_loading(case: CaseIn, policy: dict) -> RuleResult:
    if "loading" not in case.claimed_grounds:
        return _result(policy, "R-LOADING", "not_applicable", "neutral", "No loading claim made.")
    if "delivery_note" in _evidence_types(case):
        return _result(policy, "R-LOADING", "pass", "supports_accept",
                       "Loading claim supported by a delivery note.", ["DEMO-POL-6.1"])
    return _result(policy, "R-LOADING", "fail", "supports_reject",
                   "Loading claim made without documentary evidence.", ["DEMO-POL-6.1"])


@rule("R-SIGNAGE")
def check_signage(case: CaseIn, policy: dict) -> RuleResult:
    if "signage" not in case.claimed_grounds:
        return _result(policy, "R-SIGNAGE", "not_applicable", "neutral", "No signage claim made.")
    if "signage_photo" in _evidence_types(case):
        return _result(policy, "R-SIGNAGE", "pass", "needs_review",
                       "Signage claim has photographic evidence; site check needed.", ["DEMO-POL-7.1"])
    return _result(policy, "R-SIGNAGE", "fail", "supports_reject",
                   "Signage claim made without photographic evidence.", ["DEMO-POL-7.1"])


@rule("R-MITIGATION")
def check_mitigation(case: CaseIn, policy: dict) -> RuleResult:
    claims = [g for g in case.claimed_grounds if g in ("medical_emergency", "breakdown")]
    if not claims:
        return _result(policy, "R-MITIGATION", "not_applicable", "neutral", "No mitigation claim made.")
    types = _evidence_types(case)
    supported = ("medical_emergency" in claims and "medical_letter" in types) or \
                ("breakdown" in claims and "breakdown_report" in types)
    if supported:
        return _result(policy, "R-MITIGATION", "pass", "needs_review",
                       f"Mitigation ({', '.join(claims)}) has documentary evidence; officer judgement required.",
                       ["DEMO-POL-8.1"])
    return _result(policy, "R-MITIGATION", "fail", "supports_reject",
                   f"Mitigation ({', '.join(claims)}) made without documentary evidence.", ["DEMO-POL-8.1"])


GROUND_RULES = {"paid": "R-PAYMENT", "permit": "R-PERMIT", "blue_badge": "R-BADGE", "loading": "R-LOADING",
                "signage": "R-SIGNAGE", "medical_emergency": "R-MITIGATION", "breakdown": "R-MITIGATION"}


def applicable_rule_ids(case: CaseIn, policy: dict) -> list[str]:
    spec = policy["contraventions"].get(case.contravention_code)
    ids: list[str] = list(spec["applicable_rules"]) if spec else ["R-DEADLINE"]
    for ground in case.claimed_grounds:
        rid = GROUND_RULES.get(ground)
        # For "after paid time" codes the grace check is the payment check; a covering payment cannot exist.
        if rid == "R-PAYMENT" and "R-GRACE" in ids:
            continue
        if rid and rid not in ids:
            ids.append(rid)
    return ids


def run_rules(case: CaseIn, policy: dict | None = None) -> list[RuleResult]:
    policy = policy or load_policy()
    return [_RULES[rid](case, policy) for rid in applicable_rule_ids(case, policy)]


def all_rule_ids() -> list[str]:
    return list(_RULES)


def deterministic_indicator(rules: list[RuleResult], issues: list[ValidationIssue]) -> str:
    """Summarise verified facts into a direction. A guide for the reviewer and a guardrail, not a decision."""
    if any(i.severity == "error" for i in issues):
        return "needs_review"
    effects = {r.effect for r in rules}
    if "supports_accept" in effects and "supports_reject" not in effects:
        return "accept"
    if "supports_reject" in effects and not effects & {"supports_accept", "needs_review"}:
        return "reject"
    return "needs_review"
