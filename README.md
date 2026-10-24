# civic. — Parking, with perspective

Civic helps drivers understand parking notices, prepare an evidence-backed challenge and find parking for their next trip.

**Sign up → scan and confirm a ticket → add evidence → get Mubit advice → review the draft → submit to the issuer → track the response.**

The public home is now the default. Personal appeals are private to each driver. The existing council review workspace is retained separately at `/#workspace`.

## Built now

- A permanent sample ticket at `/#demo`: live Mubit scan and assessment, explicitly labelled fallback walkthrough, and restart on reload.
- Public Neon Auth email-code signup and sign-in, without council owner approval.
- Private ticket details, photo uploads, Mubit vision extraction and user confirmation.
- Mubit assessments with reasons, missing evidence, risks and linked, dated guidance.
- Editable drafts, explicit approval, downloadable appeal packs and calendar reminders.
- User-reported submissions, responses and refunds; no invented wins or savings.
- London parking map with 4,339 mapped locations, place search, filters and directions.
- Light/dark themes, responsive layouts, cream/charcoal surfaces, blue actions and lime accents.

See [consumer architecture, deployment and limits](docs/CONSUMER.md), [parking data and map](docs/PARKING-MAP.md), and [officer feedback workflow](docs/MUBIT-FEEDBACK.md).

## Run locally

Requires Python 3.14 and Node 22.12+.

```sh
bash scripts/dev.sh
```

Open <http://127.0.0.1:5173>. The home and parking map are public. Private driver accounts need a Neon Auth test branch; scanning and advice require a live Mubit connection and a vision-capable model. Consumer AI does not silently fall back to demo answers. The older council sample tools remain at `/#workspace`.

Use `.env.example` for settings. Root `.env` is supported; `backend/.env` takes precedence. Use a disposable database for development, not the production Neon branch.

## Deploy

The existing Render service follows `main` and builds the repository's Dockerfile. FastAPI serves the built React app and API on the same origin. Neon stores application data and small evidence images and provides managed Better Auth. Schema migrations run at startup.

```sh
cp .env.example .env
# Configure a private PCN_ACCESS_KEY and test database/provider settings.
docker compose up -d --build
```

Local Docker serves <http://localhost:8000>. Docker packages the software; Render hosts it; Neon persists the data. See [deployment instructions](docs/DEPLOYMENT.md). No new hosting service or paid map key is required for this release.

## Relevant checks

```sh
.venv/bin/python -m pytest backend/tests -q
npm test --prefix frontend
npm run build --prefix frontend
```

Checks cover driver isolation, consent, Mubit transport, version conflicts, approved exports, reminders, outcomes, council review/auth, integration and persistence. CI repeats relevant database checks on disposable PostgreSQL. Mocked transport tests do not establish live email delivery, live AI quality or training improvement.

## Current scope

England council parking PCNs and private parking charges, focused on initial challenge preparation. Drivers confirm facts and deadlines and submit through the issuer's own route. Seven dated primary-source summaries provide a starting library; this is not complete legal knowledge or an automatic council integration. Later legal stages are routed to specialist help. The London map is sourced discovery data, not live availability.

Public metrics distinguish assessed cases from verified outcomes. Self-reported cancellations and refunds do not become verified wins. Real driver uploads are never automatically submitted as model training examples.

## Retained council workspace

The council route preserves the officer queue, bounded investigation, policy checks, editable decisions, insights, membership approvals and synthetic council exchange. Northgate Borough and the bundled council cases remain fictional. No real supplier-specific council connector is included. Officer correction snapshots can be approved/exported; automatic adapter training and activation remain unverified. See [implemented architecture](docs/ARCHITECTURE.md) and [council exchange contract](docs/COUNCIL-INTEGRATION.md).
