# PCN Review Copilot

An AI case reviewer for council Parking Services teams. It reads each parking-fine (PCN) challenge, checks the evidence, recommends accept or reject with the legal ground and policy clause, and drafts the decision letter. **A council officer always makes the decision.** Every officer correction is routed through [Mubit](https://mubit.ai) so the model gets better, and cheaper, at that council's cases.

Built for the Night Shift Mubit Hackathon, London, 23–25 October 2026.

## One-line pitch

Same officers, more cases handled, fewer wrong rejections, and a model that learns from every overturn.

## Architecture at a glance

![PCN Review Copilot architecture](docs/assets/architecture.svg)

Detail: [docs/03-architecture.md](docs/03-architecture.md).

## Read in this order

| # | Doc | What it answers |
|---|-----|-----------------|
| 1 | [Business case](docs/01-business-case.md) | Problem, numbers, buyer, pricing, market, competition, moat |
| 2 | [User process](docs/02-user-process.md) | Who uses it, the end-to-end flow, officer SOP, lanes, reason codes |
| 3 | [Architecture](docs/03-architecture.md) | Components, data flow, data model, APIs, guardrails |
| 4 | [Mubit integration](docs/04-mubit-integration.md) | How calls become a task, how adapters train and serve, cost curve |
| 5 | [Metrics](docs/05-metrics.md) | North star, business, model and Mubit metrics, targets |
| 6 | [Decision log](docs/06-decision-log.md) | Why things are the way they are (ADRs) |
| 7 | [Compliance and risks](docs/07-compliance-and-risks.md) | Legal duty, GDPR, certifications, risk register |
| 8 | [Hackathon plan](docs/08-hackathon-plan.md) | Scope, build order, demo script |
| 9 | [Glossary](docs/09-glossary.md) | Every term in plain words |
| – | [Sources](docs/10-sources.md) | Every figure and where it came from |
| – | [Recommendation schema](docs/schemas/recommendation.schema.json) | The exact JSON the AI must return |

## Status

Pre-build. These docs fix the design before any code is written. Figures marked **(assumption)** are hypotheses to validate; everything else links to a source.
