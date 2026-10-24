"""Provider adapters. Provider-specific request/response details stay in this module.

MubitAdapter talks to Mubit's OpenAI-compatible gateway (https://api.mubit.ai/openai/v1) as documented at
docs.mubit.ai. StubAdapter is an offline, deterministic stand-in used when no MUBIT_API_KEY is configured; it
is NOT Mubit and every record it produces is labelled provider='offline-stub'.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

import httpx

from ..config import Settings

STUB_PROVIDER = "offline-stub"
MUBIT_PROVIDER = "mubit"


@dataclass
class ProviderResult:
    provider: str
    model: str | None
    raw_text: str | None = None
    request_id: str | None = None
    latency_ms: int | None = None
    usage: dict | None = None
    error_kind: str | None = None  # timeout | provider_error | auth_error | rate_limited | transport_error
    error_message: str | None = None
    meta: dict = field(default_factory=dict)


class MubitAdapter:
    # Remember a response_format the gateway accepted. Changing output format changes Mubit's task grouping,
    # so we fall back once and then stick with what works.
    _working_format: str | None = None

    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        if not settings.mubit_api_key:
            raise RuntimeError("MUBIT_API_KEY is not set")
        self.settings = settings
        self.client = client or httpx.Client(timeout=httpx.Timeout(settings.mubit_timeout_s, connect=10.0))

    @property
    def provider(self) -> str:
        return MUBIT_PROVIDER

    @property
    def _anthropic(self) -> bool:
        return self.settings.mubit_route == "anthropic"

    def _url(self) -> str:
        base = self.settings.mubit_base_url.rstrip("/")
        return base + ("/v1/messages" if self._anthropic else "/chat/completions")

    def _headers(self, fmt: str) -> dict:
        headers = {"content-type": "application/json", "x-middleware-record": self.settings.mubit_record}
        if self._anthropic:
            headers["x-api-key"] = self.settings.mubit_api_key
            headers["anthropic-version"] = "2023-06-01"
            if fmt == "json_schema":
                headers["anthropic-beta"] = "structured-outputs-2025-11-13"
        else:
            headers["Authorization"] = f"Bearer {self.settings.mubit_api_key}"
        return headers

    def _payload(self, system: str, user: str, schema: dict, fmt: str) -> dict:
        if self._anthropic:
            payload: dict = {
                "model": self.settings.mubit_model,
                "max_tokens": self.settings.mubit_max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            if fmt == "json_schema":
                payload["output_format"] = {"type": "json_schema", "schema": schema}
            return payload
        payload = {
            "model": self.settings.mubit_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if fmt == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "pcn_recommendation", "strict": True, "schema": schema},
            }
        elif fmt == "json_object":
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _parse(self, body: dict, result: ProviderResult) -> None:
        if self._anthropic:
            result.raw_text = "".join(b.get("text", "") for b in body["content"] if b.get("type") == "text")
            if body.get("stop_reason") == "max_tokens":
                result.meta["truncated"] = True
        else:
            result.raw_text = body["choices"][0]["message"]["content"]
        result.model = body.get("model") or result.model
        result.usage = body.get("usage")

    def complete(self, system: str, user: str, schema: dict) -> ProviderResult:
        # json_object is an OpenAI-only option; the Anthropic route goes straight from schema to prompt-only.
        fmt_chain = ["json_schema", "none"] if self._anthropic else ["json_schema", "json_object", "none"]
        start_fmt = MubitAdapter._working_format or self.settings.mubit_response_format
        fmts = fmt_chain[fmt_chain.index(start_fmt):] if start_fmt in fmt_chain else ["none"]
        url = self._url()
        result = ProviderResult(provider=MUBIT_PROVIDER, model=self.settings.mubit_model)
        result.meta["route"] = self.settings.mubit_route
        rate_limit_retried = False
        i = 0
        while i < len(fmts):
            fmt = fmts[i]
            t0 = time.perf_counter()
            try:
                resp = self.client.post(url, headers=self._headers(fmt), json=self._payload(system, user, schema, fmt))
            except httpx.TimeoutException as exc:
                result.error_kind, result.error_message = "timeout", f"Mubit call timed out: {exc!s}"
                result.latency_ms = int((time.perf_counter() - t0) * 1000)
                return result
            except httpx.HTTPError as exc:
                result.error_kind, result.error_message = "transport_error", f"{type(exc).__name__}: {exc!s}"
                return result
            result.latency_ms = int((time.perf_counter() - t0) * 1000)
            result.request_id = resp.headers.get("x-middleware-request-id")
            result.meta["response_format"] = fmt

            if resp.status_code == 200:
                MubitAdapter._working_format = fmt
                try:
                    self._parse(resp.json(), result)
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    result.error_kind = "provider_error"
                    result.error_message = f"Unexpected response shape: {exc!s}"
                return result

            err = _error_info(resp)
            result.meta["error_code"] = err.get("code")
            if resp.status_code in (429, 503) and not rate_limit_retried:
                wait = _retry_after(resp)
                if wait is not None and wait <= 10:
                    rate_limit_retried = True
                    time.sleep(wait)
                    continue
            # A 400 that names the response_format/option: the provider refused before processing, so trying a
            # simpler output format is safe and cannot double-bill.
            if resp.status_code == 400 and fmt != "none" and _mentions_format(err):
                i += 1
                continue
            result.error_kind = {401: "auth_error", 403: "auth_error", 429: "rate_limited"}.get(
                resp.status_code, "provider_error")
            result.error_message = f"HTTP {resp.status_code} {err.get('code') or ''}: {err.get('message') or resp.text[:300]}"
            return result
        result.error_kind = "provider_error"
        result.error_message = "No response format accepted by the gateway."
        return result


def _error_info(resp: httpx.Response) -> dict:
    try:
        err = resp.json().get("error", {})
        return err if isinstance(err, dict) else {"message": str(err)}
    except ValueError:
        return {"message": resp.text[:300]}


def _retry_after(resp: httpx.Response) -> float | None:
    try:
        return float(resp.headers.get("retry-after", ""))
    except ValueError:
        return None


def _mentions_format(err: dict) -> bool:
    text = json.dumps(err).lower()
    return any(k in text for k in ("response_format", "output_format", "json_schema", "starter_credit_option",
                                   "structured output", "structured-outputs", "anthropic-beta", "beta"))


class StubAdapter:
    """Deterministic offline stand-in. Mirrors the deterministic indicator and ignores precedents.

    Fault injection for demos/tests: put [[STUB:timeout]], [[STUB:malformed]], [[STUB:invented_ref]] or
    [[STUB:contradict]] in the representation text.
    """

    provider = STUB_PROVIDER

    def complete(self, system: str, user: str, schema: dict) -> ProviderResult:
        t0 = time.perf_counter()
        bundle = json.loads(user.split("\n", 1)[1])
        text = bundle["representation_text"]
        result = ProviderResult(provider=STUB_PROVIDER, model="offline-stub-v1", request_id=None)
        fault = re.search(r"\[\[STUB:(\w+)\]\]", text)
        fault = fault.group(1) if fault else None
        if fault == "timeout":
            result.error_kind, result.error_message = "timeout", "Simulated timeout (stub fault injection)."
            return result
        if fault == "malformed":
            result.raw_text = '{"recommendation": "accept", "reason_summary": '
            return result

        effects = [r["effect"] for r in bundle["rule_results"]]
        has_errors = any(i["severity"] == "error" for i in bundle["validation_issues"])
        if has_errors:
            rec = "needs_review"
        elif "supports_accept" in effects and "supports_reject" not in effects:
            rec = "accept"
        elif "supports_reject" in effects and not {"supports_accept", "needs_review"} & set(effects):
            rec = "reject"
        else:
            rec = "needs_review"
        if fault == "contradict":
            rec = "reject" if rec == "accept" else "accept"
        refs = sorted({ref for r in bundle["rule_results"] for ref in r["policy_refs"]})
        if fault == "invented_ref":
            refs.append("Traffic Management Act 2004 s.99(9)")
        missing = [r["finding"] for r in bundle["rule_results"] if r["status"] == "insufficient_data"]
        decisive = [r["finding"] for r in bundle["rule_results"] if r["effect"] != "neutral"]
        out = {
            "recommendation": rec,
            "reason_summary": " ".join(decisive[:3]) or "No decisive rule findings.",
            "relevant_rule_references": refs,
            "evidence_references": [e["id"] for e in bundle["evidence"]],
            "missing_information": missing,
            "uncertainty_flags": ["offline stub output - not a Mubit model"],
            "draft_response": (
                f"Dear motorist, thank you for your representation regarding PCN {bundle['case']['pcn_ref']}. "
                "[Officer to complete after review.]"
            ),
        }
        result.raw_text = json.dumps(out)
        result.latency_ms = int((time.perf_counter() - t0) * 1000)
        return result


def get_adapter(settings: Settings):
    if settings.ai_provider == "mubit":
        return MubitAdapter(settings)
    return StubAdapter()
