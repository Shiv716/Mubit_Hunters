> Original planning notes retained from `main`. Proposals and legal/process assumptions below are not a statement of implemented or verified capability. See [current architecture](ARCHITECTURE.md) and [deployment](DEPLOYMENT.md).

# 5. Metrics

Every metric below can be computed from the audit log ([03-architecture.md](03-architecture.md#audit-log)). Targets are **assumptions** to be replaced with a council's baseline in the first 4 weeks.

## North star

**Correct decisions per officer-hour** = decisions made ÷ officer hours, counting only decisions not later overturned (by QA sampling or tribunal).

Why: it rewards speed and quality together. Speed alone would reward rubber-stamping; quality alone would ignore the backlog.

## Business metrics (for the Head of Parking Services)

| Metric | Definition | Target (assumption) | Why it matters |
|--------|------------|---------------------|----------------|
| Cases per officer per day | Decisions ÷ officer-days | +30% vs baseline | Capacity without hiring |
| Median time to decision | Received → decided | −40% vs baseline | Backlog and driver experience |
| Not-contested rate | Tribunal appeals the council drops ÷ appeals | −25% vs baseline | Directly measures wasted rejections |
| Tribunal loss rate | Appeals allowed ÷ appeals decided | Down vs baseline | Quality of rejections |
| Deadline breaches | Formal reps decided after day 56 | 0 | Safety net |
| Cost per case | (Officer cost + software + AI) ÷ cases | Down vs baseline | Buyer's ROI |
| Hotspots actioned | Signage/bay issues raised to highways and fixed | Count | Fixes causes, not tickets |

## Product metrics (is the tool used and trusted?)

| Metric | Definition | Target (assumption) |
|--------|------------|---------------------|
| Recommendation coverage | Cases with a valid recommendation ÷ cases | ≥ 98% |
| Agreement rate | Officer final = AI recommendation, by lane | Fast-confirm ≥ 95%, Review ≥ 80% |
| Override rate by reason code | Overrides ÷ decisions, split by code | Falling over time |
| Time on case | Median seconds open per case, by lane | Fast-confirm < 60s (assumption) |
| QA disagreement | Team-leader sample where QA disagrees with final decision | < 5% |

## Model safety metrics (watched daily)

| Metric | Definition | Threshold | Action if breached |
|--------|------------|-----------|--------------------|
| **False-reject rate** | AI said reject, officer accepted ÷ AI rejects | Hard alert above 10% | Move affected pattern to Judgement lane, retrain |
| Fast-confirm precision | Fast-confirm cases officers changed ÷ Fast-confirm cases | Above 5% → alert | Tighten lane thresholds |
| Schema validity | Responses passing JSON schema ÷ responses | ≥ 99.5% | Retry once, then Judgement lane |
| Citation validity | Cited policy clause exists in council policy ÷ responses | 100% | Block and route to Judgement |
| Calibration | Agreement rate within each confidence band | Higher band → higher agreement | Recalibrate thresholds |

Why false-reject is the key safety metric: a wrong "accept" loses one fine; a wrong "reject" can unfairly charge a driver and later costs a tribunal case.

## Mubit metrics (is the model getting better and cheaper?)

| Metric | Source | What good looks like |
|--------|--------|----------------------|
| Kept examples per task | Mubit console, Tasks | Crosses 25 (first training default) |
| Adapter versions and results | Mubit console, Adapters → History | Latest version `Passed` |
| Adapter vs provider match | Version test result ("Matched X% of your provider model's answers") | Rising version on version |
| Share of calls served by adapter | Our logs (model ID per call) | Rising once a version passes |
| Cost per 1,000 cases | Provider spend + Mubit runs ($5 per 1,000) | Falls once adapter serves |
| Latency p50 / p95 | Our logs | Adapter ≤ provider |

## Hackathon demo metrics

Shown side by side on a held-out set of similar cases, before vs after the correction:

1. Agreement with officer decisions on the corrected pattern (e.g. "signage unclear").
2. Adapter vs frontier model: quality (agreement), cost per 1,000 cases, latency.
3. Count of officer corrections that became a new adapter version.
