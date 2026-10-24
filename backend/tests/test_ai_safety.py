import json

import httpx

from app.ai.adapters import MubitAdapter, ProviderResult, StubAdapter
from app.ai.prompt import OUTPUT_JSON_SCHEMA, SYSTEM_PROMPT, build_bundle, build_user_message
from app.ai.safety import assess
from app.config import Settings
from app.models import CaseIn
from app.policy import load_policy
from app.rules import deterministic_indicator, run_rules
from app.service import review_core
from app.validation import validate_case


def _case(demo_cases, scenario_index=0, text_suffix=""):
    c = CaseIn.model_validate(demo_cases[scenario_index])
    if text_suffix:
        c.representation_text += " " + text_suffix
    return c


def _bundle(case):
    issues, rules = validate_case(case), run_rules(case)
    return build_bundle(case, issues, rules, load_policy()), deterministic_indicator(rules, issues)


def _out(**over):
    base = {"recommendation": "accept", "reason_summary": "Payment covers time.",
            "relevant_rule_references": ["DEMO-POL-3.1"], "evidence_references": ["E1"],
            "missing_information": [], "uncertainty_flags": [], "draft_response": None}
    base.update(over)
    return ProviderResult(provider="test", model="m", raw_text=json.dumps(base))


def test_valid_output_passes(demo_cases):
    bundle, ind = _bundle(_case(demo_cases))
    s = assess(_out(), bundle, ind)
    assert s.status == "valid" and s.effective_recommendation == "accept"


def test_code_fenced_json_is_accepted(demo_cases):
    bundle, ind = _bundle(_case(demo_cases))
    r = _out()
    r.raw_text = "```json\n" + r.raw_text + "\n```"
    assert assess(r, bundle, ind).status == "valid"


def test_invented_reference_removed_and_flagged(demo_cases):
    bundle, ind = _bundle(_case(demo_cases))
    s = assess(_out(relevant_rule_references=["DEMO-POL-3.1", "Road Traffic Act s.99", "DEMO-POL-99"]), bundle, ind)
    assert s.parsed["relevant_rule_references"] == ["DEMO-POL-3.1"]
    assert "unsupported_reference_removed:Road Traffic Act s.99" in s.flags
    assert s.status == "valid_with_warnings"


def test_unknown_evidence_removed(demo_cases):
    bundle, ind = _bundle(_case(demo_cases))
    s = assess(_out(evidence_references=["E1", "E42"]), bundle, ind)
    assert s.parsed["evidence_references"] == ["E1"]
    assert "unknown_evidence_removed:E42" in s.flags


def test_contradicting_rules_downgrades_to_needs_review(demo_cases):
    bundle, ind = _bundle(_case(demo_cases))
    assert ind == "accept"
    s = assess(_out(recommendation="reject"), bundle, ind)
    assert s.parsed["recommendation"] == "reject"  # original kept
    assert s.effective_recommendation == "needs_review"
    assert "conflicts_with_deterministic_checks:accept" in s.flags


def test_malformed_and_schema_violations(demo_cases):
    bundle, ind = _bundle(_case(demo_cases))
    bad = ProviderResult(provider="t", model="m", raw_text="not json at all")
    assert assess(bad, bundle, ind).failure_kind == "malformed_json"
    s = assess(_out(recommendation="cancel_pcn"), bundle, ind)
    assert s.status == "failed" and s.failure_kind == "schema_violation"
    assert s.effective_recommendation == "needs_review"


def test_draft_with_unverified_identifier_flagged(demo_cases):
    case = _case(demo_cases)
    bundle, ind = _bundle(case)
    s = assess(_out(draft_response=f"Re PCN {case.pcn_ref} and also PCN ZZ99999999, per DEMO-POL-7.7"), bundle, ind)
    assert any(f.startswith("draft_contains_unverified_identifier:ZZ99999999") for f in s.flags)
    assert "draft_cites_unsupported_reference:DEMO-POL-7.7" in s.flags


def test_stub_fault_injection(demo_cases):
    stub = StubAdapter()
    assert review_core(_case(demo_cases, text_suffix="[[STUB:timeout]]"), stub).safety.failure_kind == "timeout"
    assert review_core(_case(demo_cases, text_suffix="[[STUB:malformed]]"), stub).safety.failure_kind == "malformed_json"
    s = review_core(_case(demo_cases, text_suffix="[[STUB:invented_ref]]"), stub).safety
    assert any(f.startswith("unsupported_reference_removed:Traffic Management Act") for f in s.flags)


# ---- Mubit adapter against a mocked gateway (no network)

def _settings(**over):
    s = Settings(ai_provider="mubit", mubit_api_key="mbt_test", mubit_timeout_s=5)
    return Settings(**{**s.__dict__, **over})


def _ok(content: dict):
    return httpx.Response(200, headers={"x-middleware-request-id": "mreq_" + "a" * 32},
                          json={"model": "gpt-6-luna", "choices": [{"message": {"content": json.dumps(content)}}],
                                "usage": {"total_tokens": 10}})


def _adapter(handler, **over):
    MubitAdapter._working_format = None
    return MubitAdapter(_settings(**over), client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_mubit_success_captures_request_id_and_sends_record_header():
    seen = {}

    def handler(req):
        seen["auth"], seen["record"] = req.headers["authorization"], req.headers["x-middleware-record"]
        seen["body"] = json.loads(req.content)
        return _ok({"recommendation": "accept"})
    r = _adapter(handler, mubit_record="metadata").complete(SYSTEM_PROMPT, "Case bundle:\n{}", OUTPUT_JSON_SCHEMA)
    assert r.request_id.startswith("mreq_") and r.error_kind is None
    assert seen["auth"] == "Bearer mbt_test" and seen["record"] == "metadata"
    assert seen["body"]["response_format"]["type"] == "json_schema"
    assert seen["body"]["messages"][0]["content"] == SYSTEM_PROMPT


def test_mubit_falls_back_when_response_format_refused():
    calls = []

    def handler(req):
        body = json.loads(req.content)
        calls.append(body.get("response_format", {}).get("type"))
        if body.get("response_format", {}).get("type") == "json_schema":
            return httpx.Response(400, json={"error": {"code": "starter_credit_option", "message": "response_format not served"}})
        return _ok({"recommendation": "reject"})
    r = _adapter(handler).complete("s", "Case bundle:\n{}", OUTPUT_JSON_SCHEMA)
    assert calls == ["json_schema", "json_object"] and r.meta["response_format"] == "json_object"


def test_mubit_timeout_and_auth_errors():
    def timeout(req):
        raise httpx.ReadTimeout("slow", request=req)
    assert _adapter(timeout).complete("s", "u", {}).error_kind == "timeout"

    def unauth(req):
        return httpx.Response(401, json={"error": {"code": "invalid_key", "message": "Incorrect API key provided."}})
    r = _adapter(unauth).complete("s", "u", {})
    assert r.error_kind == "auth_error" and "invalid_key" in r.error_message


def _anthropic_ok(content: dict, stop_reason="end_turn", text=None):
    return httpx.Response(200, headers={"x-middleware-request-id": "mreq_" + "b" * 32}, json={
        "model": "claude-haiku-4-5", "stop_reason": stop_reason, "usage": {"input_tokens": 5, "output_tokens": 7},
        "content": [{"type": "text", "text": text if text is not None else json.dumps(content)}]})


def _anthropic(handler):
    return _adapter(handler, mubit_route="anthropic", mubit_base_url="", mubit_model="")


def test_anthropic_route_defaults_and_request_shape():
    seen = {}

    def handler(req):
        seen["url"], seen["headers"], seen["body"] = str(req.url), req.headers, json.loads(req.content)
        return _anthropic_ok({"recommendation": "accept"})
    r = _anthropic(handler).complete(SYSTEM_PROMPT, "Case bundle:\n{}", OUTPUT_JSON_SCHEMA)
    assert seen["url"] == "https://api.mubit.ai/anthropic/v1/messages"
    assert seen["headers"]["x-api-key"] == "mbt_test" and "authorization" not in seen["headers"]
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["body"]["model"] == "claude-haiku-4-5" and seen["body"]["max_tokens"] == 1500
    assert seen["body"]["system"] == SYSTEM_PROMPT
    assert [m["role"] for m in seen["body"]["messages"]] == ["user"]
    assert seen["body"]["output_format"]["type"] == "json_schema"
    assert r.error_kind is None and json.loads(r.raw_text)["recommendation"] == "accept"
    assert r.request_id.startswith("mreq_") and r.meta["route"] == "anthropic"


def test_anthropic_falls_back_to_prompt_only_when_output_format_refused():
    calls = []

    def handler(req):
        body = json.loads(req.content)
        calls.append(("output_format" in body, req.headers.get("anthropic-beta")))
        if "output_format" in body:
            return httpx.Response(400, json={"type": "error", "error": {
                "type": "middleware_gateway_error", "code": "starter_credit_option",
                "message": "output_format is not served on the starter credit"}})
        return _anthropic_ok({"recommendation": "reject"})
    r = _anthropic(handler).complete("s", "Case bundle:\n{}", OUTPUT_JSON_SCHEMA)
    assert calls == [(True, "structured-outputs-2025-11-13"), (False, None)]
    assert r.meta["response_format"] == "none" and r.error_kind is None


def test_anthropic_subscription_token_refused_is_auth_error():
    def handler(req):
        return httpx.Response(401, json={"type": "error", "error": {
            "type": "middleware_gateway_error", "code": "subscription_token_refused", "message": "Claude Pro..."}})
    r = _anthropic(handler).complete("s", "u", {})
    assert r.error_kind == "auth_error" and "subscription_token_refused" in r.error_message


def test_anthropic_truncated_output_is_reported(demo_cases):
    def handler(req):
        return _anthropic_ok({}, stop_reason="max_tokens", text='{"recommendation": "accept", "reason_summ')
    case = _case(demo_cases)
    s = review_core(case, _anthropic(handler)).safety
    assert s.status == "failed" and s.failure_kind == "truncated_output"


def test_invalid_route_rejected():
    import pytest
    with pytest.raises(ValueError):
        Settings(mubit_route="gemini")


def test_mubit_rate_limit_retries_once():
    n = {"c": 0}

    def handler(req):
        n["c"] += 1
        if n["c"] == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"code": "starter_credit_busy"}})
        return _ok({"recommendation": "accept"})
    assert _adapter(handler).complete("s", "u", {}).error_kind is None and n["c"] == 2
