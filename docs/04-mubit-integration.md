# Mubit integration

Reviewed against the implementation on **24 October 2026**. Mubit is Civic's hosted inference gateway. It routes requests to the configured model provider; it is not the database, identity provider or authority deciding whether a ticket is cancelled.

## Four prompt families

| Task | Inputs | Output |
|---|---|---|
| Driver ticket reader | Uploaded notice images | Typed extraction with unknown fields and uncertainties |
| Driver appeal adviser | Confirmed facts, narrative, images and relevant source summaries | Grounds, evidence gaps, risks, next steps and editable draft |
| Council investigation planner | Synthetic case and allowlisted tool results | Bounded read-only investigation plan |
| Council reviewer | Synthetic facts, deterministic checks, policy and optional approved precedents | Structured accept/reject/needs-review recommendation for an officer |

Driver calls can use vision. Council reviews currently use structured records and evidence descriptions; council attachments are stored for the officer, not interpreted as pixels. The public sample uses the driver reader/adviser on fixed fictional documents. It never submits an appeal or records a customer outcome.

## Gateway configuration

[adapters.py](../backend/app/ai/adapters.py) uses `httpx` to call one of these routes with a server-side Mubit key:

| `MUBIT_ROUTE` | Default base URL | Request path | Default model |
|---|---|---|---|
| `openai` | `https://api.mubit.ai/openai/v1` | `/chat/completions` | `gpt-6-luna` |
| `anthropic` | `https://api.mubit.ai/anthropic` | `/v1/messages` | `claude-haiku-4-5` |

Set `AI_PROVIDER=mubit`, `MUBIT_API_KEY` and the supported route. `MUBIT_MODEL` and `MUBIT_BASE_URL` override route defaults. The code defaults to OpenAI compatibility; `.env.example`, Compose and the Render Blueprint explicitly default to Anthropic compatibility. **The existing hosted environment controls the live service**, not an example file.

Live public-demo scan and assessment were verified on **24 October 2026** with `gpt-6-luna` through the OpenAI-compatible route. The UI shows returned model/request metadata when available. A health endpoint or configured key alone does not establish successful inference. Available models, quotas, pricing and training eligibility depend on the Mubit account; do not promise every upstream model is available. Check the [Mubit API reference](https://docs.mubit.ai/reference/api) and account integration guide when changing providers.

The adapter prefers structured JSON output, with compatible format fallbacks when a route rejects a format, and bounded retry handling. Civic validates parsed responses and references. Failed real driver inference is reported; saved evidence remains available. The dedicated public demo alone offers an explicit prewritten fallback. Production council reviews do not silently use the local stub.

## Data handling

Driver calls require AI processing consent and default to `x-middleware-record: metadata`. A separate, default-off case-level training choice permits `full` recording. The fixed fictional demo also permits full recording. `MUBIT_RECORD=metadata|off` can lower this globally; Mubit account settings can lower it further. Facts/photos still pass through Mubit and the selected provider. See [consent, history and withdrawal limits](CONSUMER.md#optional-training-recording).

Council requests use configured `MUBIT_RECORD=full|metadata|off`; keep that workspace synthetic. The app records provider/model/request IDs, usage and latency when returned. Secrets and request authentication headers are not part of correction snapshots. [Privacy boundaries](07-compliance-and-risks.md).

## Corrections are not trained adapters

Civic supports approved council precedents in later prompts, and separate owner-approved before/target correction exports. It does **not** submit those corrections to a training endpoint, monitor training jobs, select a trained version or prove a before/after improvement. A Mubit console task or learning entry is not proof of these actions.

The supported correction-submission and version-selection contract is still needed from Mubit. Do not assume one adapter per council or one adapter for all tasks; the task prompts/output shapes differ and the provider determines grouping. Real drivers now have a separate recording/training opt-in; this does not establish photo-based adapter eligibility, accepted examples or a trained version. Original inference recordings and corrected-answer submission remain different workflows. [Feedback workflow and completion criteria](MUBIT-FEEDBACK.md).

## Verification

Provider transport/schema tests use mocked HTTP responses. Verify a changed live configuration with one non-sensitive case and returned request metadata, then check the Mubit console. Before claiming an improved trained model, evaluate a named candidate against a fixed independent holdout and preserve a rollback path. Existing precedent fixture scores are not that evaluation.
