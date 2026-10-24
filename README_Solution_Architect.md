# Civic — solution brief

Reviewed **24 October 2026**. This document replaces the original officer-only proposal; earlier designs remain in Git history. The implemented product is now driver-first.

**[Hosted app](https://mubit-hunters.onrender.com/) · [Sample ticket](https://mubit-hunters.onrender.com/#demo) · [Project walkthrough](README.md)**

## Product

A driver scans or enters a parking notice, confirms the facts, adds evidence and asks Mubit for a source-backed assessment. They edit and approve a draft, download the appeal pack, submit through the issuer and record the response. Public London parking discovery supports the next trip. Public signup uses Neon email codes; each driver's cases are private.

## Implementation

- React/Vite frontend and FastAPI API share one Render-hosted Docker image and origin.
- Neon PostgreSQL stores facts, photos, reviews and history; Neon Auth supplies managed Better Auth accounts/sessions.
- Mubit is the inference gateway for ticket vision and appeal guidance; the configured provider model performs inference. Live `gpt-6-luna` demo requests were verified on 24 October 2026.
- MapLibre/OpenFreeMap render the map; a bundled OSM snapshot supplies parking locations and Photon supplies place search.
- A separate, owner-approved council workspace retains bounded planning, policy checks, human decisions, synthetic exchange and correction exports.

## Operating boundaries

One web worker, a database pool of up to eight connections and 200 consumer AI requests/hour are the current configuration. There is no account cap or measured concurrent-user capacity. Uploaded photos consume PostgreSQL storage. See [capacity and scaling](docs/CAPACITY.md).

The app does not submit appeals automatically, cancel tickets, verify wins, guarantee fraud prevention or orchestrate adapter training. Council supplier connectors, subscriptions, multi-council tenancy, nationwide/live parking availability and enterprise identity controls are future work. Real driver AI requires processing consent. Recording defaults to metadata; a separate training opt-in permits full recording, subject to operator/provider settings.

## Detailed references

| Need | Current documentation |
|---|---|
| Components, flow and trust boundaries | [Architecture](docs/ARCHITECTURE.md) |
| Hosting, environment, local setup and migration | [Deployment](docs/DEPLOYMENT.md) |
| Driver behaviour and sourced homepage figures | [Consumer product](docs/CONSUMER.md) |
| Council workflow and integration contract | [Workspace](docs/COUNCIL-WORKSPACE.md), [exchange](docs/COUNCIL-INTEGRATION.md) |
| AI transport and correction status | [Mubit](docs/04-mubit-integration.md), [feedback](docs/MUBIT-FEEDBACK.md) |
| Documentation ownership and change checklist | [Documentation index](docs/README.md) |
