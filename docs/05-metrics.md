# Metrics and evidence

Reviewed **24 October 2026**. Keep industry context, application activity, self-reports and independently verified outcomes separate.

## What is measured now

| Measure | Meaning and limit |
|---|---|
| `assessed_cases` | Distinct saved consumer cases with an assessment; not users, wins or demo runs. Deleted cases no longer count |
| `verified_successes` | Cancelled/refunded cases explicitly marked verified in stored data; current user flows never set that flag, and no independent verification workflow exists |
| Self-reported outcome/refund | What a driver records about their case; neither proof of cancellation nor bank/payment verification |
| Parking count | 4,339 mapped locations in the bundled London snapshot; not vacant bays or customers |
| Guidance count | Seven dated source summaries; not seven full books, all council policies or complete legal coverage |
| AI metadata | Provider/model, gateway request ID, usage and latency when returned; successful inference does not demonstrate legal accuracy or training |
| Council Insights | Queue totals, reviewed/pending/final decisions, accepted/rejected/investigating, agreement on comparable recommendations, corrections and curated examples |

Council figures come from the shared synthetic workspace and must not be mixed with real driver outcomes. Empty charts can reflect no corresponding stored decisions. Agreement with an officer is a workflow signal, not an independent correctness measure; the API explicitly reports training status as unverified. [Insights implementation](../backend/app/workspace.py).

## Homepage numbers

The homepage presents sourced market context rather than fabricated customer counts: London PCNs, private keeper lookups, POPLA cancellations and Westminster enforcement revenue. Each has a different geography, period and denominator. A £60 saving is a labelled illustration only. [Exact calculations and citations](CONSUMER.md#homepage-figures).

Never convert cancelled charges into refunds, keeper lookups into unique people, an appealed subset's outcome rate into a guaranteed win rate, or revenue into profit. Do not count the fixed public demo or fictional council cases as customers helped.

## What a pilot should measure next

- **Usefulness:** completion rate, abandonment point, time to a usable pack and repeat use, with defined denominators.
- **Quality:** extraction corrections, unsupported claims, missing-evidence detection and independently reviewed draft quality.
- **Economics:** actual AI cost/case, support effort, storage/case, willingness to pay and confirmed avoided payments/refunds.
- **Operations:** request latency/errors, provider failures, connection waits and resource saturation under a representative staging workload.
- **Training:** paired base/candidate results on the same independent holdout, with candidate version IDs and unsafe-decision rates.

These are proposed measurements, not a claim that analytics, verified outcomes or model evaluation automation are implemented. No measured concurrent-user capacity, conversion rate, customer saving or trained-model improvement is currently claimed. [Capacity](CAPACITY.md) · [Feedback](MUBIT-FEEDBACK.md).
