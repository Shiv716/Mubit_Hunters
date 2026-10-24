# Retained council workspace

Reviewed against the implementation on 24 October 2026. Open [the council workspace](https://mubit-hunters.onrender.com/#workspace). The default product is the separate [driver application](CONSUMER.md); see [whole-product architecture](ARCHITECTURE.md).

## Product and user flow

The daily user is a council representations / notice processing officer. The officer opens a case, checks the evidence, asks the copilot to investigate, explicitly chooses an outcome, edits the response and saves. The next case opens automatically. Civic does not send a letter or cancel a PCN. The council exchange API can provide an officer-approved result to an authorised connector; its receipt is tracked separately.

The three outcomes are **Accept appeal**, **Reject appeal**, and **Needs investigation**. No outcome is preselected. Changing the recommendation or deciding manually requires a reason. Investigation is reversible by recording a later decision; final decisions remain in the case history. Ordinary synthetic cases retain manual review. Council-connected cases require a successful current Mubit review before a final decision; investigation is still available when inference fails.

## Components

| Component | Implementation | Responsibility |
|---|---|---|
| Web interface | React 18, Vite 8, plain CSS | Cases, evidence, copilot, replies, insights and admin |
| API | FastAPI + Pydantic | Validated intake, review orchestration, decisions, exports and sessions |
| Agent | `backend/app/investigator.py` | Up to three planning turns; allowlisted, read-only tool dispatch |
| Model transport | Existing Mubit adapter | OpenAI-compatible or Anthropic-compatible Mubit route; stub restricted to local development/tests |
| Checks | Versioned rules and synthetic council policy | Payment, grace, permit, badge, loading, mitigation and case consistency |
| Recommendation guard | JSON schema + reference and rule validation | Invalid references, missing data or vulnerability require human review |
| Persistence | Neon/PostgreSQL when `DATABASE_URL` is set; SQLite WAL offline | Cases, checks, model responses, investigation trace, decisions, feedback and audit |
| Evidence | Database blobs on Render; local disk optionally offline | Store/download attachments up to 10 MiB each, with metadata and hashes; contents are not interpreted by AI |
| Learning | Human-approved examples + lexical retrieval | Context for similar later cases; no automatic training claim |
| Hosting | Existing Render service running one non-root Docker container | FastAPI serves API and built frontend on the same HTTPS origin; Neon persists data across deploys |

## A review request

1. Read a snapshot of the case and approved examples. Reject duplicate in-flight reviews or already-decided cases.
2. Run mandatory deterministic checks independently of the planner.
3. Ask the configured model which allowlisted tools to use. Validate its JSON; reject unknown tools and repeats. Supply tool results for the next turn.
4. Tools inspect supplied payment/permit/badge records, evidence descriptions, synthetic policy and approved examples. The agent has no council credentials or write-capable tools. The separate council exchange API accepts supplier-mapped snapshots and exposes only human-approved results.
5. Ask the reviewer model for a structured recommendation. Validate schema, evidence IDs, policy IDs and consistency. Escalate uncertainty and vulnerability.
6. Re-open a short write transaction. Confirm the case has not changed during inference, persist the checks, response, trace and audit, and return the result.
7. An officer explicitly chooses the outcome. Generate an outcome-specific template, let the officer edit, then save the final response and decision transactionally.

Evidence changes invalidate the displayed review. The API rejects superseded review IDs and checks that changed after inference. The officer-facing review request does not hold a database write lock during network calls. A database lease prevents duplicate reviews across processes; expired claims can be replaced, and only their current owner can save the result or release them. PostgreSQL row locks serialize case mutations and prevent competing final decisions. SQLite uses an immediate transaction for case writes.

The default remains one web service and one Uvicorn worker. PostgreSQL removes the local-disk dependency and coordinates case writes across instances, but long reviews still use synchronous HTTP requests. A durable job queue, cancellation and retry handling would be the next step for heavier traffic. The older `/ai-review` endpoint holds its case lock during inference; the main UI uses `/review`.

Each web worker reuses a small PostgreSQL connection pool (1–8 connections), checks connection health before reuse, and returns connections after commit or rollback. Command-line scripts retain direct connections. Dashboard reads are cached in browser memory for 10 seconds, with concurrent requests for the same view shared. Edits, uploads, sign-in/out, access-denied responses and returning to the browser tab clear the cache. Sessions and access-request administration are never cached. Changes from other reviewers may appear on the next fetch after that short cache window; server-side decision and access checks still run for writes.

Startup runs versioned PostgreSQL schema creation under a transaction-level advisory lock. Application tables live in the `civic` schema by default. Immutable review, decision, investigation and audit rows reject updates and deletes. Uploaded bytes and their metadata commit together in database-storage mode. The migration command copies its supported council tables into an empty council destination, verifies attachment hashes and preserves IDs and history. It does not migrate driver accounts/cases or workspace memberships; see [deployment](DEPLOYMENT.md#existing-sqlite-council-data).

## Mubit’s role

Mubit is the required hosted inference gateway for the planner and reviewer. Production does not fall back to a simulated provider. Connected cases also require Mubit in local development. The two tasks have separate stable system prompts and JSON schemas. Request IDs, provider/model, latency and usage are recorded where supplied. Account configuration is visible separately from successful inference.

The application already collects officer feedback, requires human approval before examples are reused, and supports baseline-versus-precedent evaluation from the older branch. The existing evaluation labels predate the stricter mitigation guard: those scores are a historical fixture check, not proof of legal correctness or improvement. Real savings require a timed pilot and independent quality review.

Offline tests use simulated responses; live consumer inference was separately verified on 24 October 2026. Neither establishes council model quality or training improvement. Automatic fine-tuning, trained-adapter activation, rollback and improvement against a fixed independent holdout are **not verified features**. Do not describe retrieval as model training. Do not claim that a configured gateway proves a trained model is in use.

## Access and data

Neon Better Auth email verification and owner-approved membership protect the hosted workspace (see below). `PCN_ACCESS_KEY` signs the first-party cookie and must be at least 16 characters in production. Without Neon Auth configured, the older shared-password flow remains available for local/bootstrap use; its reviewer names are self-declared. Access management and model-correction approval/export are owner-only; ordinary review and precedent tools remain shared workspace capabilities. Render defaults to secure cookies and accepts its supplied external URL as the application origin. `/api/health` reports configuration; `/api/ready` checks database connectivity without exposing credentials.

Only synthetic cases are accepted by intake. This flag is an assertion, not a personal-data detector. Upload only synthetic attachments. Mubit calls can contain appeal text, evidence descriptions and rule findings; masking an explicit registration field does not guarantee anonymisation of free text. `MUBIT_RECORD=full` permits provider-side recording, subject to the provider account settings.

## Before a real council rollout

This MVP deliberately stays one web service plus Neon. A live pilot would first require approved council policies, validated statutory-stage/deadline logic, enterprise SSO and detailed council roles, independent security/privacy review, retention and backup policies, OCR/image handling if needed, and authorised case-system integrations. Move large or numerous files to object storage and add a background job queue when workloads justify them. Database attachments count toward Neon storage and backup usage; replaced blobs are retained, with no automatic retention cleanup.

## Design

Warm cream surfaces and ticket-like case files give the work a familiar structure. Electric blue identifies actions; lime highlights copilot information. Small monospace labels and a pixel-style mark supply the retro character. The main screen contains queue, evidence and decision; technical provider details, feedback curation and evaluation remain in Admin. Responsive layouts stack the panels on smaller screens. Keyboard focus, labelled controls and reduced-motion styles are included.


## Approved workspace membership

React offers Request access and email-code sign-in, including direct entry of a code received after approval. FastAPI stores pending requests, expiry-limited hashed approval links and decisions in the Civic schema in Neon. Resend delivers request notifications only to the owner; its test sender works when that inbox is the Resend signup address. Neon sends applicants their sign-in codes after approval and on request. Both paths share approval checks and a one-minute cooldown. Approval remains saved if email fails, and the owner review list is the fallback when owner notifications fail. The configured owner email is the only identity allowed to administer membership. All other approved members can review the shared synthetic case workspace.

Neon's managed Better Auth issues and verifies sign-in codes. FastAPI calls the fixed Auth Base URL server-side, obtains the authenticated session token, and resolves it against the same branch's read-only managed `neon_auth` tables. The raw token is neither returned to the browser nor saved by Civic. A signed, first-party HttpOnly cookie references the Neon session/user IDs for up to 12 hours, bounded by the Neon session expiry. Every API request rechecks the live session, email verification, ban status and Civic approval, so revoked access is enforced immediately. No custom OTP generator or email-password provisioning remains.

Owner email links carry a single-use approval credential in the fragment (removed from browser history when opened). Reading a link has no approval side effect; an explicit POST approves it. Approval and Neon mailbox verification are distinct gates. The app still has one shared workspace; multi-tenant subscriptions and verified organization domains remain future work.

## Council exchange

The Council connection page identifies the configured council and source system and labels the current exchange as a synthetic sandbox. The versioned API imports complete case/evidence packages transactionally, rejects stale/conflicting versions, invalidates old reviews on source updates, and refuses to overwrite officer-modified evidence or final decisions. Final Mubit-reviewed, officer-approved decisions remain pending until the connector confirms storage in its source system. Dedicated machine credentials cannot approve decisions or access workspace sessions. The first import binds the schema to one council/system. No supplier-specific connector is built; one isolated deployment/schema is needed per council. See [contract and user flow](COUNCIL-INTEGRATION.md).
