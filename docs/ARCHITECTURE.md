# Implemented architecture — trial-2

## Product and user flow

The daily user is a council representations / notice processing officer. The officer opens a case, checks the evidence, asks the copilot to investigate, explicitly chooses an outcome, edits the response and saves. The next case opens automatically. Nothing is sent to the driver or an external enforcement system.

The three outcomes are **Accept appeal**, **Reject appeal**, and **Needs investigation**. No outcome is preselected. Changing the recommendation or deciding manually requires a reason. Investigation is reversible by recording a later decision; final decisions remain in the case history. Reviewers can still decide manually if inference fails.

## Components

| Component | Implementation | Responsibility |
|---|---|---|
| Web interface | React 18, Vite 8, plain CSS | Cases, evidence, copilot, replies, insights and admin |
| API | FastAPI + Pydantic | Validated intake, review orchestration, decisions, exports and sessions |
| Agent | `backend/app/investigator.py` | Up to three planning turns; allowlisted, read-only tool dispatch |
| Model transport | Existing Mubit adapter | OpenAI-compatible or Anthropic-compatible Mubit route; explicit offline stub |
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
4. Tools inspect supplied payment/permit/badge records, evidence descriptions, synthetic policy and approved examples. There are no external council credentials or write-capable agent tools.
5. Ask the reviewer model for a structured recommendation. Validate schema, evidence IDs, policy IDs and consistency. Escalate uncertainty and vulnerability.
6. Re-open a short write transaction. Confirm the case has not changed during inference, persist the checks, response, trace and audit, and return the result.
7. An officer explicitly chooses the outcome. Generate an outcome-specific template, let the officer edit, then save the final response and decision transactionally.

Evidence changes invalidate the displayed review. The API rejects superseded review IDs and checks that changed after inference. The officer-facing review request does not hold a database write lock during network calls. A database lease prevents duplicate reviews across processes; expired claims can be replaced, and only their current owner can save the result or release them. PostgreSQL row locks serialize case mutations and prevent competing final decisions. SQLite uses an immediate transaction for case writes.

The default remains one web service and one Uvicorn worker. PostgreSQL removes the local-disk dependency and coordinates case writes across instances, but long reviews still use synchronous HTTP requests. A durable job queue, cancellation and retry handling would be the next step for heavier traffic. The older `/ai-review` endpoint holds its case lock during inference; the main UI uses `/review`.

Startup runs versioned PostgreSQL schema creation under a transaction-level advisory lock. Application tables live in the `civic` schema by default. Immutable review, decision, investigation and audit rows reject updates and deletes. Uploaded bytes and their metadata commit together in database-storage mode. The migration command copies an existing SQLite workspace only into an empty destination, verifies attachment hashes and preserves IDs and history.

## Mubit’s role

Mubit is the optional inference gateway for the planner and reviewer. The two tasks have separate stable system prompts and JSON schemas. Request IDs, provider/model, latency and usage are recorded where supplied. Account configuration is visible separately from successful inference.

The application already collects officer feedback, requires human approval before examples are reused, and supports baseline-versus-precedent evaluation from the older branch. The existing evaluation labels predate the stricter mitigation guard: those scores are a historical fixture check, not proof of legal correctness or improvement. Real savings require a timed pilot and independent quality review.

No live Mubit credential was needed for implementation or the offline tests. Automatic fine-tuning, trained-adapter activation, rollback and improvement against a fixed independent holdout are **not verified features**. Do not describe retrieval as model training. Do not claim that a configured gateway proves a trained model is in use.

## Access and data

For private demos, `PCN_ACCESS_KEY` enables a 12-hour signed, HTTP-only session. Reviewer names are self-declared. Everyone with the shared password has the same capabilities; Admin is navigation separation, not a permission boundary. Production mode and Render require a password of at least 16 characters. Render defaults to secure cookies and accepts its supplied external URL as the application origin. `/api/health` reports configuration; `/api/ready` checks database connectivity without exposing credentials.

Only synthetic cases are accepted by intake. This flag is an assertion, not a personal-data detector. Upload only synthetic attachments. Mubit calls can contain appeal text, evidence descriptions and rule findings; masking an explicit registration field does not guarantee anonymisation of free text. `MUBIT_RECORD=full` permits provider-side recording, subject to the provider account settings.

## Before a real council rollout

This MVP deliberately stays one web service plus Neon. A live pilot would first require approved council policies, validated statutory-stage/deadline logic, SSO and roles, independent security/privacy review, retention and backup policies, OCR/image handling if needed, and authorised case-system integrations. Move large or numerous files to object storage and add a background job queue when workloads justify them. Database attachments count toward Neon storage and backup usage; replaced blobs are retained, with no automatic retention cleanup.

## Design

Warm cream surfaces and ticket-like case files give the work a familiar structure. Electric blue identifies actions; lime highlights copilot information. Small monospace labels and a pixel-style mark supply the retro character. The main screen contains queue, evidence and decision; technical provider details, feedback curation and evaluation remain in Admin. Responsive layouts stack the panels on smaller screens. Keyboard focus, labelled controls and reduced-motion styles are included.
