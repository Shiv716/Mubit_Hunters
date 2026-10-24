# Officer corrections and model updates

This branch prepares corrections locally. **It does not yet submit corrections to Mubit,
train an adapter, or change the model used for live reviews.**

## Before and after

1. A case review captures the application messages, requested output schema and case bundle
   at inference time. The original output, model, gateway request ID and policy version remain
   attached to that review. No keys or request headers are stored in the snapshot.
2. The officer records a decision and reason using the existing workflow.
3. In **Admin → Learning & evaluation**, the owner selects the case and checks the original
   answer beside a proposed corrected answer. The owner edits and explicitly approves the target.
4. Approval checks references and consistency with the original facts and rules. A human's
   discretionary acceptance is not automatically an AI acceptance label: mitigation cases must
   still teach the model to request officer judgement.
5. Approved revisions and withdrawals are append-only. The original answer is unchanged.
   Only the latest approved revision can be exported. Superseded policy or prompt versions,
   offline simulations, failed reviews and records without captured inputs are excluded.
6. **After model update** remains pending. An officer target is not a measured model result.

Inputs are captured for future reviews only. Historical reviews cannot be reliably reconstructed
from today's policy or evidence, so they remain visible without a training approval action.
Existing precedent curation and its evaluation remain separate.

## What Mubit needs to provide

The [API reference](https://docs.mubit.ai/reference/api) documents inference. The
[first-adapter guide](https://docs.mubit.ai/guides/first-adapter) describes automatic training
from kept calls and console comparisons, but does not document correction submission or a
versioned inference API. The workspace guide checked on 24 October 2026 also supplied only
inference examples. At that check, the review task had 0/25 kept examples and no adapter;
this is an observation, not a live status supplied by Civic.

Before connecting training, obtain a supported contract for:

- Submitting an approved replacement answer against its original request ID, with deduplication,
  acknowledgement and revocation semantics.
- Identifying the task and resulting training run/version; reporting failures and completion.
- Evaluating a specific trained version and selecting or reverting the production version.

`GET /api/learning/export` is an owner-only download in **Civic's own JSON format**. It is not a
documented Mubit import file. It includes source request IDs, original inputs/outputs, approved
targets, reviewers and content hashes, and explicitly reports `submitted_to_mubit: false`.
No network request or training job is triggered. Preserve the distinction between a downloaded
package, accepted examples, a completed adapter and a version that has passed evaluation.

## Completing the loop before deployment

Connect an acknowledged submission and training-status adapter once that contract is available.
Freeze a separate holdout set; never train on its cases or retrieve their answers as precedents.
Run the same inputs and council policy against the current model and a named candidate version
with recording disabled for evaluation. Compare accuracy against independently approved labels,
unsafe decisions, unsupported references, failures and latency. Keep provider request IDs and
version IDs with both outputs. The existing precedent experiment is not evidence of model training.

Only enable a candidate after the paired evaluation is reviewed; preserve the existing model
configuration for rollback. Do not manufacture calls to reach the 25-example threshold.

## Local verification

Run `python -m pytest backend/tests/test_learning.py -q` in the project virtual environment.
The tests use simulated model replies and isolated databases. For PostgreSQL migration verification,
set `PCN_TEST_DATABASE_URL` to a **disposable local database**, never the deployed Neon workspace.
The app applies additive schema migration 4 on startup. Existing records are not rewritten.

Build the UI with `npm run build --prefix frontend`. Preview the original answer, approved target
and explicit pending state in Admin. No deployment environment variable changes are needed for
this preparation; Mubit inference configuration remains unchanged.
