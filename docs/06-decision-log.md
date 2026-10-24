> Original planning notes retained from `main`. Proposals and legal/process assumptions below are not a statement of implemented or verified capability. See [current architecture](ARCHITECTURE.md) and [deployment](DEPLOYMENT.md).

# 6. Decision log

Why things are the way they are. Each entry: decision, why, what we gave up.

### ADR-001 · The AI recommends; the officer decides
- **Why:** Councils have a legal duty to consider each representation and its evidence. Statutory guidance puts discretion with back-office staff; councillors and unauthorised staff must play no part.
- **Gave up:** Full automation. We sell capacity, not headcount cuts.

### ADR-002 · Deterministic checks run before the AI
- **Why:** ~64% of accepted cases (Herefordshire 2021/22) are evidence checks a lookup can prove: valid ticket, permit, badge, warden error, loading. Lookups are cheaper, exact and explainable.
- **Gave up:** A "pure AI" demo. Judges see we used AI only where it adds value.

### ADR-003 · One fixed AI task shape per council
- **Why:** Mubit groups calls by model, instructions, tools, tool choice and output format. Fixing these, with the council's policy in the instructions, gives one task, and one adapter, per council. That is the per-council learning moat.
- **Gave up:** Free prompt iteration. Prompt changes are versioned and rare.

### ADR-004 · Structured JSON output against a schema
- **Why:** Validatable (guardrails), trainable (one clean pattern for the adapter), auditable (every field logged).
- **Gave up:** Free-text explanations beyond five short reasons.

### ADR-005 · Letters come from approved templates; AI only fills fields
- **Why:** Decision letters have legal consequences. Councils control wording; the AI supplies `outcome_summary` and `reason_paragraph`.
- **Gave up:** Fully generated letters.

### ADR-006 · Text only; no computer vision
- **Why:** Mubit's documented connectors are text LLM APIs. Since April 2015, councils cannot post parking PCNs from CCTV evidence except school zig-zags, bus lanes, bus stops and red routes, so a CCTV detection product is a weak fit. Photo evidence enters as text descriptions and references.
- **Gave up:** The original "AI Smart Parking with CCTV" idea.

### ADR-007 · Synthetic data for the hackathon; minimised personal data in production
- **Why:** Real cases hold names, addresses and plates (UK GDPR). The AI needs facts, not identities.
- **Gave up:** Realism of real letters; mitigated by generating varied, realistic synthetic challenges.

### ADR-008 · Informal and formal stages both in scope; deadline is a safety net
- **Why:** Review work happens at both stages. Published data shows few PCNs lost to the 56-day rule (Stockton: 3 in 2018/19), so it is not the headline.
- **Gave up:** A dramatic "lost revenue" pitch.

### ADR-009 · Vendor-neutral: sit on case-system exports
- **Why:** Unity5's AI lives inside Chipside/Zatpark. Councils on Taranto or Imperial have no option. Working from exports keeps us neutral and partner-friendly.
- **Gave up:** Owning the system of record.

### ADR-010 · Subscription + overage; never a share of fines
- **Why:** Councils budget annually and already buy PCN software this way (~£13k–£24k). A share of upheld fines would reward rejecting drivers and conflict with the duty to judge fairly.
- **Gave up:** Upside tied to council revenue.

### ADR-011 · Start with a strong frontier model as teacher
- **Why:** Mubit tests adapters against the provider model's answers; the adapter cannot beat a weak teacher. Savings come when the cheap adapter replaces an expensive model.
- **Gave up:** Lowest possible cost during the learning phase.

### ADR-012 · Corrections reach the model via precedents in context (fallback) plus Mubit's native path once confirmed
- **Why:** Precedents in the user message keep the task shape fixed and work without special APIs; Mubit then distils the corrected behaviour.
- **Gave up:** Nothing; native path added when confirmed.

### ADR-013 · Mitigation always goes to a human lane
- **Why:** Vulnerability and compelling-reason cases need judgement and carry the highest fairness risk (~22% of Herefordshire's cancellations).
- **Gave up:** Some throughput.
