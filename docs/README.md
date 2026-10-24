# Documentation index

Reviewed against the implementation on **24 October 2026**. Start with the [project README](../README.md) or [hosted app](https://mubit-hunters.onrender.com/).

| Topic | Canonical document |
|---|---|
| Product walkthrough | [README](../README.md) |
| Whole-system architecture and code map | [Architecture](ARCHITECTURE.md) |
| Hosting, environment and local setup | [Deployment](DEPLOYMENT.md) |
| Accounts, request limits, storage and scaling | [Capacity](CAPACITY.md) |
| Driver behaviour, demo and homepage figures | [Consumer product](CONSUMER.md) |
| Parking map, provenance and refresh | [Map](PARKING-MAP.md) |
| Retained officer workflow | [Council workspace](COUNCIL-WORKSPACE.md) |
| Synthetic council import/result contract | [Council exchange](COUNCIL-INTEGRATION.md) |
| Gateway and actual model configuration | [Mubit integration](04-mubit-integration.md) |
| Before/target correction export and training gap | [Feedback](MUBIT-FEEDBACK.md) |
| Business reasoning and measurement | [Business case](01-business-case.md), [metrics](05-metrics.md) |
| User journeys and design decisions | [Process](02-user-process.md), [decisions](06-decision-log.md) |
| Privacy and product boundaries | [Risks](07-compliance-and-risks.md) |
| Presentation and terminology | [Demo runbook](08-hackathon-plan.md), [glossary](09-glossary.md) |
| External evidence | [Sources](10-sources.md) |

[Architecture guide](03-architecture.md) and the [solution brief](../README_Solution_Architect.md) are concise entry points, not competing specifications. Previous proposals remain in Git history. A roadmap item is not an implemented feature.

## Keep documentation current with changes

The person changing a feature should update its canonical document in the same change. This is a maintenance checklist, not an installed scheduled sync or automated guarantee.

- User-visible flow, theme or scope: update the root README, consumer/process docs and demo runbook where affected.
- Data/API/auth changes: update architecture, deployment, privacy boundaries and the relevant consumer/council contract.
- Provider/model changes: update Mubit docs and distinguish configured, live-verified and trained/evaluated status. Date observations; do not turn example defaults into claims about production.
- Quota, worker, pool, upload or hosting changes: update capacity and environment comments; keep registered accounts separate from throughput/concurrency.
- Guidance, map or marketing data: retain source, version/date, geography, units and calculation; recheck the source before moving its checked date forward.
- Before release: verify documented commands/paths, relative links/anchors and diagrams. Regenerate the council recommendation schema snapshot if `OUTPUT_JSON_SCHEMA` changes. Run focused application tests only when behaviour changes.

Never put credentials, private approval URLs, personal evidence or fabricated customer metrics in documentation. Plan allowances must be dated and conditional until the actual account is inspected. [Deployment verification](DEPLOYMENT.md#post-deploy-verification) describes the minimum live checks.
