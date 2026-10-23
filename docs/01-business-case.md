# 1. Business case

## The problem in one paragraph

Every challenge to a council parking fine (PCN) must be read and decided by a person. London issued **9,462,185 PCNs in 2024-25**, up 13.5% in a year. A large share are challenged, most challenges follow a handful of repeat patterns, and many rejections do not survive tribunal. Today none of those outcomes feed back into how the next case is handled.

## Evidence

| Signal | Number | Why it matters |
|--------|--------|----------------|
| London PCNs issued, 2024-25 | 9,462,185 (+13.5% YoY) | Volume is large and rising |
| Challenge rate (Haringey, May 2021) | 2,836 challenges on 12,851 PCNs (~22%) | Roughly 1 in 5 tickets creates review work |
| London Tribunals appeals, 2024-25 | 47,935 (+13.6% YoY) | The final stage is growing too |
| Appellant win rate at London Tribunals, 2024-25 | 49.4% | Many council rejections do not hold up |
| Parking appeals allowed but **not contested** by the council, 2024-25 | 6,143 of 10,496 allowed | Councils rejected, then gave up: wasted work twice |
| Routine cancellation reasons (Herefordshire 2021/22) | 1,316 of 2,047 cancellations (~64%) were valid ticket, permit, badge, warden error or loading | Most accepted cases are evidence checks, not judgement |
| Mitigation share of cancellations (Herefordshire 2021/22) | 450 of 2,047 (~22%) | A real minority needs human judgement |
| Over-56-day cancellations (Stockton 2018/19) | 3 | Missed deadlines are rare: a safety net, not the headline |

Sources: [10-sources.md](10-sources.md).

## How the work runs today

Warden issues PCN → driver makes an informal challenge → if unpaid, Notice to Owner (NtO) after 28 days → keeper makes formal representations within 28 days → council must decide within 56 days → if rejected, driver may appeal to London Tribunals, whose decision binds the council.

At each challenge an officer manually: reads the letter, works out the ground being claimed, pulls payment/permit/badge records, checks warden notes and photos, applies the council's discretion policy, decides, and writes a letter.

## Who decides, uses and buys

| Role | Who | Need |
|------|-----|------|
| Decision maker + daily user | Representations / Notice Processing Officer, Parking Services (in-house or contractor) | A decision-ready case: recommendation, evidence, draft letter |
| QA | Team leader | Consistency, sampling, coaching |
| Buyer (ICP) | Head of Parking Services, London borough with high PCN volume | Lower backlog, fewer tribunal losses, lower cost per case |
| Cannot decide (by law) | Wardens (CEOs) and elected councillors | – |

Customer list: 32 London boroughs + City of London, TfL (red routes), English councils running civil parking enforcement, outsourced PCN processors, and later private parking operators.

## Value levers (ranked by size)

1. **Officer time on routine cases.** ~64% of accepted cases are evidence checks. Pre-assembled evidence + draft letter turns minutes of reading into a confirm.
2. **Fewer pointless rejections.** Flag cases that look like past "not contested" or lost tribunal cases before the officer rejects.
3. **Consistency.** Same policy applied the same way across officers, with a full audit trail.
4. **Street fixes.** Accept-clusters by location expose bad signage or bays for highways to fix.
5. **Deadline safety net.** Queue sorted by days left; rare but costly misses avoided.
6. **AI running cost.** Mubit moves routine calls onto a cheaper task model. Pennies per case: real, but the smallest lever.

**Unknown to validate first:** minutes per case and loaded officer cost. Ask a parking team or file an FOI.

## Pricing (assumption)

| Item | Proposal | Why |
|------|----------|-----|
| Annual subscription, tiered by challenge volume | S: <20k/yr £15k · M: 20–60k £30k · L: >60k £50k | Councils budget annually; similar software sells at ~£13k–£24k |
| Overage | ~£0.75 per case above tier | Price scales with workload |
| Enterprise | Custom | Private hosting, SSO, SLA |
| **Never** | A share of fines upheld | Would reward rejecting drivers and conflict with the duty to judge each case fairly |

Route to market: G-Cloud and the ESPO parking framework; partner with case-system vendors as an add-on.

## Market size

| Layer | Basis | Size |
|-------|-------|------|
| Money at stake | English council parking income 2024-25: London £1,007.0M + rest of England £1,163.5M | ~£2.17bn/yr |
| Review volume, London (assumption) | 9.46M PCNs × ~20% challenged | ~1.9M cases/yr |
| Review volume, England (assumption) | London scaled by income ratio (~2.2×) | ~4.1M cases/yr |
| Software spend, England (assumption) | ~4.1M cases × ~£1 | ~£4M/yr |
| Expansion | 14.4M private parking charges/yr; bus lane, moving traffic and environmental fines | Larger adjacent pools |

Honest read: PCN review is a strong wedge, not a large standalone market. Growth comes from other council penalty and appeal types and private parking.

## Competition

| Player | What it does | Our gap |
|--------|--------------|---------|
| **Unity5** (owns Chipside, Zatpark) | Adding AI to its appeals process: reviews evidence, guides the operator, groups appeals, predicts outcomes | Locked to its own platform; no public claim of per-council learning from overrides and tribunal results |
| Taranto, Imperial | PCN case management; Imperial also sells human processing | No public AI decision layer |
| PCN Beater, QuickAppeal, AppealIQ, Parksy, ParkAppeal, Resolvo, DoNotPay, Pine AI and others | AI appeal letters for drivers | Driver side; increases council workload |
| RBKC Chatbot Max | Helps drivers decide whether to challenge | Front door only |

## Moat

- **Per-council learning:** each council's overrides train its own adapter; a newcomer starts at zero.
- **Tribunal outcome labels:** "won / lost / not contested" is a rare ground-truth signal.
- **Vendor-neutral:** sits on Taranto, Imperial or Chipside exports.
- **Procurement + trust:** framework listings, certifications and an audit trail are slow to replicate.
- **Weak point:** Unity5 already owns Chipside's customers, so start with councils on other systems.
