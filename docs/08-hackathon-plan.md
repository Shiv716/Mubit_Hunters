# 8. Hackathon plan

Night Shift, London. Hacking started Fri 23 Oct 19:30. **Code freeze Sun 25 Oct 10:00.** UK clocks go back at 02:00 Sunday (extra hour).

## Judging (equal weight) and how we hit each

| Criterion | Our answer |
|-----------|-----------|
| Use of Mubit | Live: officer override → new adapter version → similar cases now correct; adapter vs frontier side by side |
| Usefulness | Real recurring council task with public numbers behind it |
| Technical execution | Rules + AI + guardrails + audit log; works on 200+ cases |
| Demo | One story, one borough, under the time limit |

Track fit: **Recurring tasks** (primary), with the **Own your intelligence layer** comparison (quality, cost, latency).

## Scope

**In:** one synthetic borough, formal + informal challenges, 5 contravention codes, rules engine, AI review via Mubit, guardrails, three lanes, officer console, override with reason codes, letters from templates, metrics page, held-out eval.

**Out:** real data, vision, email ingestion, tribunal import (mocked), SSO, multi-council UI.

## Build order

| When | Deliverable | Done when |
|------|-------------|-----------|
| Fri 20:00–23:00 | Synthetic generator: 1 borough policy (10 clauses), 5 codes, 250 cases incl. signage-at-one-street pattern; 50-case held-out set | Fixtures load |
| Fri 23:00–01:00 | Reviewer: fixed prompt + schema + Mubit client; **send 80+ varied calls** | Task visible in Mubit console, examples counting |
| Sat 01:00–09:00 | Sleep / rules engine + guardrails + lanes | Every case lands in a lane |
| Sat 09:00–14:00 | Backend API + SQLite + audit log | All endpoints return data |
| Sat 14:00–20:00 | Officer console: queue, case view, evidence panel, confirm/override, letter preview | Officer can work 20 cases end to end |
| Sat 20:00–23:00 | Correction loop: precedents store (ADR-012) + Mubit native path if confirmed at office hours | Override changes the next similar recommendation |
| Sat 23:00–Sun 03:00 | Metrics page + eval script (before/after, adapter vs frontier) | Numbers on screen |
| Sun 03:00–08:00 | Rehearse demo; record backup video | Demo < limit |
| Sun 08:00–10:00 | Buffer, README polish, submit | Submitted before 10:00 |

Owners: assign at team matching.

## Synthetic data spec

- **Borough:** fictional "Borough of Northgate" (no real council branding).
- **Codes:** 01 restricted street (yellow line), 12 resident/shared bay without permit or payment, 16 permit space without permit, 30 overstay, 40 disabled bay without badge.
- **Patterns (target mix):** ~45% provable by payment/permit/badge record, ~20% clear reject, ~15% signage disputes (concentrated on "Alder Road"), ~12% mitigation, ~8% procedural claims.
- **Letters:** varied tone, length and spelling; some multi-claim.
- **Held-out set:** 50 cases including 15 Alder Road signage cases, never sent before the correction.

## Demo script (3 minutes)

1. **Problem (20s):** 9.46M London PCNs, ~1 in 5 challenged, half of tribunal appeals lost, 6,143 rejections not even defended.
2. **Priya's queue (30s):** lanes, deadline sort, Fast-confirm batch cleared in seconds with proof shown.
3. **The miss (30s):** AI rejects an Alder Road signage case. Priya overrides: `OVR_SIGNAGE`.
4. **Mubit (45s):** console shows the task, kept examples and the new adapter version; held-out Alder Road cases now flagged accept.
5. **Own your model (30s):** adapter vs frontier: agreement, cost per 1,000 cases, latency.
6. **Close (25s):** per-council learning, vendor-neutral, officer always decides.

## Questions to ask Mubit at office hours

See [04-mubit-integration.md](04-mubit-integration.md#open-questions-for-the-mubit-team).
