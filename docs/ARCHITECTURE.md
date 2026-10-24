# Product architecture

Reviewed against the implementation on **24 October 2026**. [Hosted Civic](https://mubit-hunters.onrender.com/) is a consumer parking appeal preparation app with a separate retained council workspace. This is the canonical system overview; [deployment](DEPLOYMENT.md), [capacity](CAPACITY.md) and [driver behaviour](CONSUMER.md) provide the operational detail.

![Civic system architecture](assets/architecture.svg)

## Runtime

Civic is a modular monolith: one non-root Docker container on Render serves the compiled React frontend and FastAPI API over one origin. `backend/start.py` starts one Uvicorn worker. Render supplies HTTPS and `PORT`; the application does not require a separate frontend service.

Neon PostgreSQL stores application records and image bytes. Managed Neon Auth (Better Auth) owns users and sessions in the same database branch. Civic stores its tables in the `civic` schema by default; startup applies migrations 1–5 under a PostgreSQL advisory lock. Offline development can use SQLite. The database pool is 1–8 connections per web worker; external AI requests are synchronous, with no durable job queue.

## Responsibilities and code

| Area | Implementation | Responsibility |
|---|---|---|
| Routing and presentation | [ProductRoot.jsx](../frontend/src/ProductRoot.jsx), [ConsumerApp.jsx](../frontend/src/ConsumerApp.jsx) | Public home/demo, account flow and private appeals; lazy-load map/council UI |
| Driver cases | [consumer.py](../backend/app/consumer.py), [DriverCase.jsx](../frontend/src/DriverCase.jsx) | Owner-scoped facts, photos, consent, assessment, draft, export and outcome |
| Driver identity | [consumer_auth.py](../backend/app/consumer_auth.py), [neon_auth.py](../backend/app/neon_auth.py) | Email OTP, live Neon session verification and a separate signed driver cookie |
| Consumer AI | [consumer_ai.py](../backend/app/consumer_ai.py), [adapters.py](../backend/app/ai/adapters.py) | Image processing, typed extraction/assessment and Mubit HTTP transport |
| Public sample | [consumer_demo.py](../backend/app/consumer_demo.py), [DemoTicket.jsx](../frontend/src/DemoTicket.jsx) | Fixed fictional inputs, bounded live inference and explicit sample fallback |
| Parking | [parking.py](../backend/app/parking.py), [ParkingMap.jsx](../frontend/src/ParkingMap.jsx) | Bundled OSM search, Photon geocoding, MapLibre/OpenFreeMap UI |
| Persistence | [db.py](../backend/app/db.py), [consumer_schema.py](../backend/app/consumer_schema.py) | Transactions, migrations, connection pool, quotas and per-case AI leases |
| Council workflow | [workspace.py](../backend/app/workspace.py), [investigator.py](../backend/app/investigator.py) | Shared officer queue, bounded read-only planning, checks and human decisions |
| Council exchange/learning | [integration.py](../backend/app/integration.py), [learning.py](../backend/app/learning.py) | Versioned synthetic intake/receipts and approved correction export |

## A driver case, end to end

1. Neon sends and verifies an email code. FastAPI sets an HttpOnly first-party cookie referencing the Neon user/session. Private requests recheck session validity, verification and ban status.
2. The driver creates a private case and uploads photos or types notice details. Images are decoded, EXIF metadata removed, resized and stored in `driver_evidence`. Input limits are eight photos/case, 8 MiB/photo and 24 megapixels; PDFs require page screenshots.
3. After consent, the ticket reader sends selected images to Mubit. A typed extraction response is validated and presented for the driver to correct and confirm. Unknown facts stay unknown; dates are not inferred from statutory periods.
4. The adviser receives confirmed facts, narrative, attached images and relevant entries from the seven-source bundled guidance library. It returns grounds, missing evidence, risks, next steps and a draft. Source/evidence references are checked; this does not establish legal correctness.
5. A database lease prevents overlapping AI work on the same case while valid. Network inference runs outside the case transaction; changed case versions cannot accept a stale response. There is no automatic retry queue after a process restart.
6. The driver edits and approves the current draft. Only an approved, current assessment can produce the ZIP evidence pack. Edits/evidence changes clear approval and require reassessment. Later or uncertain notice stages return specialist help without an initial-challenge draft.
7. The driver submits externally, then records the response. An `.ics` download uses a user-confirmed date and includes a two-day alert; Civic does not send deadline reminder emails. Outcomes/refunds remain self-reported.

## Data and access boundaries

| Boundary | Current implementation |
|---|---|
| Public | Home, aggregate context, fixed sample-ticket demo and map; no private case data |
| Driver | Separate session audience/cookie and `driver_*` tables; every private case operation checks ownership |
| Council | Separate session, owner-approved membership and shared synthetic officer workspace; driver signup does not grant access |
| Connector | Dedicated machine key for versioned council exchange; cannot approve cases or administer membership |
| Provider | Server-side Mubit key; consumer calls send consented facts/images and request metadata-only recording |
| Outcomes | User reports are stored but never marked independently verified by the current UI |

Deleting a driver case deletes its active case records and images, not its Neon Auth account, provider records or database backups. Council audit/review/decision history has different append-only rules. There is no general automatic retention purge or multi-council tenant model.

## What is live, and what is separate

Mubit handles consumer image reading and assessment. The retained council agent uses separate planner/reviewer prompts, allowlisted tools, deterministic policy checks and descriptions of evidence; council attachments are not passed through vision. CEO photos are optional in the default policy. See [council workspace](COUNCIL-WORKSPACE.md) and [exchange contract](COUNCIL-INTEGRATION.md).

Live consumer demo inference was verified on 24 October 2026 using `gpt-6-luna` through Mubit's OpenAI-compatible route. Examples/Blueprint default to the Anthropic-compatible route; the existing service's environment determines its actual route. Configured credentials, successful inference, retrieved precedents and trained adapters are different states. [Mubit integration](04-mubit-integration.md) and [feedback status](MUBIT-FEEDBACK.md) document them.

The demo stores temporary runs in bounded process memory; regular cases persist in Neon. Map discovery uses a bundled London snapshot, with external tiles and geocoding. Neither map pins nor public sample outputs are proof of live occupancy or product success.

## Deployment boundaries

Keep a single instance/worker until demo state, geocoder throttling and caches are shared and long AI work has a durable execution path. PostgreSQL removes dependence on Render's local disk but does not make every component horizontally scalable. No concurrent-user benchmark has been completed. See [capacity and scaling](CAPACITY.md).

The product does not include automatic council submission/cancellation, payment processing, subscription billing, verified outcome checks, universal supplier connections, model fine-tuning orchestration or guaranteed fraud detection.
