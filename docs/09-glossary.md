# 9. Glossary

## Parking enforcement

| Term | Meaning |
|------|---------|
| PCN | Penalty Charge Notice: the council's civil parking fine |
| CEO | Civil Enforcement Officer: the warden who issues PCNs |
| Contravention code | Standard code for the breach, e.g. 01 yellow line, 12 resident bay |
| Informal challenge | Driver's early objection, before a Notice to Owner |
| NtO | Notice to Owner: formal letter to the registered keeper if unpaid |
| Formal representation | Keeper's legal challenge after the NtO, on stated grounds |
| 56-day rule | Council must decide a formal representation within 56 days or the PCN is cancelled |
| Discretion policy | Council's published rules for when it may cancel a PCN |
| Procedural impropriety | The council made a legal or process error |
| Mitigation / compelling reasons | Circumstances (illness, emergency) that may justify cancelling |
| London Tribunals | Independent adjudicators for London appeals; decisions bind the council |
| Not contested | Council chose not to defend its rejection at tribunal; driver wins |
| Parking Services | Council department that issues and processes PCNs |

## Product

| Term | Meaning |
|------|---------|
| Case Bundle | The normalised case data sent to the AI |
| Rules engine | Deterministic checks (payment, permit, badge, deadline) |
| Recommendation | The AI's structured suggestion: decision, ground, clause, confidence, reasons |
| Guardrails | Checks that decide whether a recommendation is shown and in which lane |
| Lane | Fast-confirm, Review or Judgement queue |
| Override | Officer decides differently from the AI, with a reason code |
| Precedent | A past officer decision retrieved into a new case as context |
| Hotspot | A location producing repeated accepted challenges, e.g. faded signage |
| False-reject rate | Share of AI "reject" recommendations that officers accepted |

## Mubit and AI

| Term | Meaning |
|------|---------|
| Frontier model | Large, expensive model (e.g. GPT, Claude, Gemini) |
| Task | Calls with the same model, instructions, tools, tool choice and output format |
| Kept example | A call Mubit accepts for training or testing |
| Adapter | Small model trained for one task |
| Passed / Below target | Whether an adapter version matched the provider model closely enough |
| Prompt only | The base open model already did as well as the adapter |
| Run | One Mubit-billed request in a learning task, up to 8,000 tokens |

## Compliance

| Term | Meaning |
|------|---------|
| UK GDPR | UK law on personal data |
| DPIA | Data Protection Impact Assessment |
| Cyber Essentials Plus | UK government security certificate, externally tested |
| ISO 27001 | Information-security management certificate |
| ISO 42001 | AI management-system certificate |
| SOC 2 | Audit report on how a company protects customer data |
| WCAG 2.2 AA | Accessibility standard |
| ATRS | Algorithmic Transparency Recording Standard: government template for explaining AI tools |
| G-Cloud / ESPO | Government and council buying frameworks |
