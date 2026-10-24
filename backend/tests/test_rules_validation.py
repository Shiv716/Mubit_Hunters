import json
from copy import deepcopy

import pytest

from app.ai.adapters import StubAdapter
from app.config import DATA_DIR
from app.models import CaseIn
from app.policy import load_policy
from app.rules import deterministic_indicator, run_rules
from app.service import review_core
from app.validation import validate_case


def _scenario_cases():
    data = json.loads((DATA_DIR / "eval_dataset.json").read_text(encoding="utf-8"))
    out = {}
    for item in data["pool"]:
        out.setdefault(item["scenario"], CaseIn.model_validate(item["case"]))
    return out


CASES = _scenario_cases()


def _rule(case, rule_id):
    return next(r for r in run_rules(case) if r.rule_id == rule_id)


def _indicator(case):
    return deterministic_indicator(run_rules(case), validate_case(case))


def test_payment_covering_time_supports_accept():
    case = CASES["paid_covered"]
    r = _rule(case, "R-PAYMENT")
    assert (r.status, r.effect) == ("pass", "supports_accept")
    assert r.policy_refs == ["DEMO-POL-3.1"]
    assert _indicator(case) == "accept"


def test_payment_not_covering_supports_reject():
    assert _rule(CASES["paid_not_found"], "R-PAYMENT").effect == "supports_reject"
    assert _indicator(CASES["paid_not_found"]) == "reject"
    assert _indicator(CASES["paid_wrong_zone"]) == "reject"


def test_grace_period_and_no_payment_rule_for_code_05():
    case = CASES["grace"]
    ids = [r.rule_id for r in run_rules(case)]
    assert "R-PAYMENT" not in ids
    assert _rule(case, "R-GRACE").effect == "supports_accept"
    assert _indicator(case) == "accept"


def test_permit_variants():
    assert _indicator(CASES["permit_valid"]) == "accept"
    assert _rule(CASES["permit_undisplayed_first"], "R-PERMIT").effect == "needs_review"
    assert _indicator(CASES["permit_expired"]) == "reject"


def test_observation_and_loading():
    assert _rule(CASES["short_observation"], "R-OBSERVATION").effect == "supports_accept"
    assert _indicator(CASES["loading_with_note"]) == "accept"
    assert _indicator(CASES["loading_no_note"]) == "reject"


def test_missing_records_are_insufficient_not_negative():
    case = CASES["paid_covered"].model_copy(deep=True)
    case.records.payments = None
    r = _rule(case, "R-PAYMENT")
    assert r.status == "insufficient_data"
    assert "unverified" in r.finding
    assert _indicator(case) == "needs_review"


def test_late_representation_flags_deadline():
    r = _rule(CASES["late_but_paid"], "R-DEADLINE")
    assert r.status == "fail" and r.effect == "needs_review"


def test_vrm_mismatch_is_validation_error():
    issues = validate_case(CASES["vrm_mismatch"])
    assert any(i.code == "vrm_mismatch_evidence" and i.severity == "error" for i in issues)
    assert _indicator(CASES["vrm_mismatch"]) == "needs_review"


def test_duplicate_evidence():
    case = CASES["paid_covered"].model_copy(deep=True)
    dup = case.evidence[1].model_copy(update={"id": "E9"})
    case.evidence.append(dup)
    case.evidence.append(case.evidence[0].model_copy())
    codes = {i.code for i in validate_case(case)}
    assert {"duplicate_evidence_file", "duplicate_evidence_id"} <= codes


@pytest.mark.parametrize("code", ["01", "05", "11", "12", "40"])
def test_default_policy_does_not_require_ceo_photos(code):
    case = next(c for c in CASES.values() if c.contravention_code == code).model_copy(deep=True)
    case.evidence = [e for e in case.evidence if e.type != "ceo_photo"]
    core = review_core(case, StubAdapter())
    assert core.bundle["required_evidence"] == []
    assert not any(i.code == "missing_required_evidence" for i in core.issues)


def test_selected_council_policy_requires_photos_only_for_configured_code(monkeypatch, tmp_path):
    from app import policy as policy_module

    policy = deepcopy(load_policy())
    policy["policy_version"] = "test-council-photo-policy-v1"
    policy["contraventions"]["11"]["required_evidence"] = ["ceo_photo"]
    policy["contraventions"]["12"].pop("required_evidence")  # Omission also means optional.
    filename = "council-photo-required.json"
    (tmp_path / filename).write_text(json.dumps(policy))
    monkeypatch.setattr(policy_module, "POLICY_DIR", tmp_path)
    monkeypatch.setenv("PCN_POLICY_FILE", filename)

    case = CASES["paid_covered"].model_copy(deep=True)
    original = case.evidence
    case.evidence = [e for e in original if e.type != "ceo_photo"]
    core = review_core(case, StubAdapter())
    assert core.bundle["policy_version"] == policy["policy_version"]
    assert core.bundle["required_evidence"] == ["ceo_photo"]
    assert any(i.code == "missing_required_evidence" and i.severity == "error" for i in core.issues)
    assert core.safety.effective_recommendation == "needs_review"
    case.evidence = original
    assert review_core(case, StubAdapter()).safety.effective_recommendation == "accept"

    other = CASES["permit_valid"].model_copy(deep=True)
    other.evidence = [e for e in other.evidence if e.type != "ceo_photo"]
    core = review_core(other, StubAdapter())
    assert core.bundle["required_evidence"] == []
    assert core.safety.effective_recommendation == "accept"


def test_inconsistent_dates():
    case = CASES["paid_covered"].model_copy(deep=True)
    case.representation_received_date = case.notice_date.replace(year=case.notice_date.year - 1)
    assert "representation_before_notice" in {i.code for i in validate_case(case)}
