"""What this app can and cannot do with Mubit, as verified against public docs. Shown verbatim in the UI.

Source: https://docs.mubit.ai/llms-full.txt and https://mubit.ai/pricing.md, read 2026-10-24.
Re-verify with the Mubit team before relying on any 'not documented' item: a private API may exist.
"""

VERIFIED_ON = "2026-10-24"

CAPABILITIES = {
    "verified_on": VERIFIED_ON,
    "sources": [
        "https://docs.mubit.ai/llms-full.txt",
        "https://docs.mubit.ai/reference/api",
        "https://docs.mubit.ai/guides/first-adapter",
        "https://mubit.ai/pricing.md",
    ],
    "items": [
        {
            "capability": "Inference",
            "status": "implemented",
            "detail": "MUBIT_ROUTE=openai: POST https://api.mubit.ai/openai/v1/chat/completions (Bearer key). "
                      "MUBIT_ROUTE=anthropic: POST https://api.mubit.ai/anthropic/v1/messages (x-api-key, "
                      "anthropic-version). Both use the Mubit key only; Claude Pro/ChatGPT sign-ins are refused "
                      "(subscription_token_refused / jwt_refused). Request id read from x-middleware-request-id.",
        },
        {
            "capability": "Submitting reviewer feedback / corrections to Mubit",
            "status": "not_documented",
            "detail": "No public endpoint for feedback, labels or outcomes. Mubit records calls; adapters train on "
                      "'kept examples' and are tested against the provider model's own answers, not against officer "
                      "decisions. Reviewer corrections are therefore stored locally and used for precedent retrieval.",
        },
        {
            "capability": "Training / calibrating an adapter and job status",
            "status": "console_only",
            "detail": "Training starts automatically per task (default first training at 25 kept examples; daily "
                      "limits and pauses apply). Status is visible in the console (Tasks, Adapters > History). No "
                      "documented API to trigger training or poll job status. Model training: PENDING for this app.",
        },
        {
            "capability": "Retrieving model / adapter versions",
            "status": "console_only",
            "detail": "Adapter versions and test results (Passed, Below target, Prompt only, ...) are console-only. "
                      "There is no Mubit model ID to route a call to an adapter.",
        },
        {
            "capability": "Evaluating and selecting a candidate version",
            "status": "console_only",
            "detail": "Mubit grades versions against provider answers; 'Try models' compares side by side in the "
                      "console. This app runs its own holdout evaluation (eval/run_eval.py) on officer labels.",
        },
        {
            "capability": "Task grouping",
            "status": "implemented",
            "detail": "Calls with the same model, system instructions, tools, tool choice and output format form one "
                      "task. The system prompt is fixed; precedents go in the user message so baseline and "
                      "precedent-informed calls share one task.",
        },
        {
            "capability": "Data handling",
            "status": "configured",
            "detail": "Mubit records request and reply content by default. MUBIT_RECORD (sent as x-middleware-record: "
                      "full|metadata|off) lowers this; 'metadata' or 'off' means calls never become training "
                      "examples. Use synthetic data only.",
        },
        {
            "capability": "Rate limits, timeouts, cost",
            "status": "documented",
            "detail": "Gateway: 10 s connect, 610 s first byte, 60 min total. 429/503 carry retry-after (the adapter "
                      "waits once if <= 10 s). Starter credit has per-project concurrency limits. Pricing page: "
                      "$5 per 1,000 runs on pay-as-you-go; provider tokens on your own key; training/evals not charged.",
        },
        {
            "capability": "Provider / model eligibility",
            "status": "documented",
            "detail": "Starter credit serves a fixed model list (400 starter_credit_model otherwise). Training must be "
                      "enabled for the workspace; without it the console shows no Adapters page.",
        },
    ],
}
