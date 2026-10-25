# Officer corrections and model updates

Reviewed **25 October 2026**. The deployed council workspace captures corrections in Civic and exports approved targets. **It does not submit corrections to Mubit, train an adapter, or change the model used for live reviews.** This is separate from [consumer AI](04-mubit-integration.md), which now supports a separate, optional driver training-recording choice and full recording for the fictional demo. Recorded inference examples are not officer-corrected training labels.

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
versioned inference API. The signed-in console checked on **25 October 2026, approximately
00:15 UTC**, showed both council review tasks at **2/25 kept examples**, the investigation
planner at **8/25**, and **no adapters yet**. A recorded demo request exposed Good/Bad
ratings; no corrected-answer editor was found. Several pages intermittently reported
"Engine unreachable". These are dated observations, not live status supplied by Civic.

Mubit's [model-ID guide](https://docs.mubit.ai/guides/model-ids) explicitly says that an
adapter cannot be selected by putting its name in the model field. The documented way to
compare a passing adapter is **Try models**. Do not replace `MUBIT_MODEL` with an invented
adapter ID or present a console comparison as production activation.

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

## Correction demo: exact evidence required

The correction-to-model-update demonstration is **blocked on Mubit's supported correction
submission workflow**, then on sufficient kept examples and completed training. Completion
before the stated **25 October 2026, 07:00 GMT** freeze is not guaranteed.

1. **Before:** select a genuinely incorrect synthetic PCN review. Preserve its original input,
   answer, policy, prompt, schema, model and gateway request ID. Freeze a separate unseen
   synthetic PCN with independently checked expected behaviour for the later review.
2. **Correction:** approve the corrected answer in Civic. Obtain Mubit's UI steps or API
   contract, submit through that supported path, and retain its acknowledgement linking the
   correction to the source call and task. A downloaded Civic export or Good/Bad rating alone
   does not prove a replacement answer was accepted for training.
3. **Update:** show the resulting adapter/version and completed test result in Mubit. The
   console currently requires 25 kept examples; provide useful, varied synthetic examples
   of the same task if required. More calls alone do not demonstrate correction learning.
4. **After:** compare the provider and passing adapter on the frozen unseen PCN in Try models.
   Keep instructions, policy, evidence and output requirements unchanged. Save both answers,
   the selected version, timestamp and a screenshot; Try models comparisons are not stored
   in Requests. Retesting the corrected training case alone does not establish generalisation.
5. **Report:** show the actual changed reasoning or outcome and check it against the expected
   answer. If both answers are already correct, unchanged or the adapter is worse, report that;
   do not claim improvement. A single comparison illustrates behaviour, not an accuracy rate
   or proof that one correction alone caused the change.

Suggested organiser question: **For project `ws-11e5866490fbe6ff`, how do we attach an
approved corrected answer to its original call, confirm it was used in an adapter version,
and compare that version on an unseen PCN?** Ask separately for supported production routing
if the demonstration must run inside Civic rather than the Mubit console.

## Before deploying a trained adapter

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
Correction tables were added in migration 4; the current app also applies consumer migrations 5–6. Existing records are not rewritten.

Build the UI with `npm run build --prefix frontend`. Preview the original answer, approved target
and explicit pending state in Admin. No deployment environment variable changes are needed for
this preparation; Mubit inference configuration remains unchanged.
