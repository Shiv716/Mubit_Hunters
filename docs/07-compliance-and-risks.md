# 7. Compliance and risks

## Legal position

| Requirement | How we meet it |
|-------------|----------------|
| Council must consider each representation and its evidence | Officer decides every case; AI output is advisory (ADR-001) |
| Discretion must not be fettered; each case on its merits | No blanket rules; Judgement lane; officer can always override |
| Discretion rests with back-office staff, not wardens or councillors | Role-based access: only officers and team leaders can decide |
| Formal representations decided within 56 days | Legal clock in rules engine; deadline sort and red flags |

## Data protection

- **UK GDPR + DPIA:** ship a ready-made DPIA template for councils.
- **Minimisation:** AI sees references and facts, not names, addresses or full plates (ADR-007).
- **UK hosting:** all case data stored in UK data centres.
- **Retention:** follow each council's retention schedule; audit log retained for the life of the case plus appeal window (assumption: confirm per council).
- **Processor terms:** council = controller, us = processor; Mubit as sub-processor (Mubit offers a DPA; Enterprise supports VPC/self-hosted).

## Certifications and trust signals (production)

| Item | What it is | Priority |
|------|------------|----------|
| Cyber Essentials Plus | UK government security certificate, externally tested | Before first council |
| ISO 27001 | Information-security management certificate | Year 1 |
| WCAG 2.2 AA | Accessibility standard for public-sector software | Before first council |
| ATRS record | Government AI transparency template; councils adopt it voluntarily for tools that influence public decisions | Provide pre-filled to each council |
| G-Cloud / ESPO listing | Government buying routes | Year 1 |
| Mubit Enterprise compliance | SOC 2, ISO 27001, ISO 42001 on Mubit's Enterprise plan | Lean on for the AI layer |

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| AI wrongly recommends reject; officer rubber-stamps | Medium | High | False-reject metric with hard alert; Fast-confirm only with a proving fact; QA sampling |
| Officers over-trust Fast-confirm | Medium | Medium | Evidence panel always shown; periodic blind QA |
| Policy change makes model stale | Medium | Medium | Versioned policy; new task on change; precedents retrieval |
| Unity5 bundles AI for Chipside councils | High | High | Target non-Chipside councils; partner as add-on; lead with per-council learning |
| Slow public-sector procurement | High | Medium | Frameworks; pilot with one borough; partner channel |
| Mubit correction path not available as hoped | Medium | Medium | Precedent-in-context fallback (ADR-012) |
| Personal-data leak | Low | High | Minimisation, UK hosting, access control, audit |
| Hackathon: adapter doesn't pass in time | Medium | High (demo) | Generate 200+ synthetic cases; send 60+ calls Friday night; rehearse Try models |
