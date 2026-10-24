# Council exchange and user flow

Reviewed **24 October 2026**. This describes the retained [council workspace](COUNCIL-WORKSPACE.md), not the separate [driver product](CONSUMER.md).

## What is available

Civic now implements a reusable, versioned case-and-evidence intake API and an acknowledged result export API. The **Council connection** page names the configured council and source system, explains each step, lists imported source references and shows result receipts. The same contract can be mapped to different suppliers; no Taranto, Imperial or other supplier connector has been implemented or verified.

The council exchange remains a **synthetic-data sandbox with demonstration policies**. Private consumer cases use a separate data model and are not imported through this contract. Configuring a council name or a connector key does not establish a live integration. One deployment and isolated database schema serve one council/source system. This is not a multi-council SaaS tenant boundary. Use separate deployments, credentials, schemas and access configuration for separate councils.

## The officer's flow

1. The council connector sends the appeal, source reference/version, records and evidence files together. Alternatively, the owner imports a test package on Council connection.
2. The case appears in the officer's existing queue. Its source system, reference and version remain visible on the case.
3. The officer requests a **Mubit review**. The planner and reviewer use Mubit; mandatory checks and output validation constrain its recommendation. Mubit currently reads structured records and evidence descriptions. File bytes are stored for officers, not interpreted through OCR or vision.
4. The officer checks the recommendation, chooses accept/reject/investigate and edits the response. A connected case cannot receive a final accept/reject decision without a successful, current Mubit review. Investigation remains available when Mubit is unavailable. Nothing is automatically accepted or rejected.
5. Saving a final decision makes it available to the connector. The connector collects it, matches the original source reference/version, and writes it into the council system using that supplier's API.
6. Only after successful source-system storage does the connector acknowledge the decision. Until then Civic shows **Awaiting receipt** and keeps returning it. Acknowledgment changes this to **Receipt confirmed**. Civic does not send a letter or execute a PCN cancellation itself.

## Setup

Before the first import, configure the server:

| Setting | Purpose |
|---|---|
| `PCN_COUNCIL_ID` | Stable ID; default `northgate-sandbox` |
| `PCN_COUNCIL_NAME` | Officer-facing name; default `Northgate Borough` |
| `PCN_CASE_SYSTEM` | Stable source-system name; default `generic` |
| `PCN_POLICY_FILE` | JSON filename in `backend/policy`; default `policy_v2.json` |
| `PCN_INTEGRATION_KEY` | Dedicated random secret of at least 32 characters, shared only with the connector |
| `AI_PROVIDER` | `mubit` |
| `MUBIT_API_KEY` | Mubit inference credential, stored server-side |
| `MUBIT_ROUTE`, `MUBIT_MODEL` | Route and model enabled in your Mubit account |

The first successful import binds the database to its council ID and source system. Changing those settings afterward is refused; do not repurpose a populated workspace for another council. A display name can change. Existing Render services need these values set through Environment; changing `render.yaml` alone does not change their environment.

Hosted AI reviews fail with a clear setup error when Mubit is unavailable or `AI_PROVIDER=stub`. The stub remains usable for local development on ordinary synthetic cases and automated tests. Connected cases always require Mubit, including local development. Setting credentials does not prove successful inference; inspect a completed review's provider and request ID.

### Evidence requirements

CEO (Civil Enforcement Officer) photos are optional in the default policy. For a council that explicitly requires one for a particular contravention, package a versioned policy JSON in `backend/policy`, add `"ceo_photo"` to that contravention's `required_evidence` list, and select the filename with `PCN_POLICY_FILE` before redeploying. An empty or omitted list imposes no mandatory evidence types. Other record checks, claim-support checks and officer judgement still apply.

The same selected policy drives validation and the evidence requirements sent to Mubit. Give each changed policy a new `policy_version`. Existing checks and reviews retain their original versions; choose **Review again** to apply the new policy to an open case. The original `policy_v1.json` is retained for historical reference and is no longer the default. Council-specific files remain subject to the current synthetic-data limitation.

## Exchange contract v1

The machine endpoints use `Authorization: Bearer <PCN_INTEGRATION_KEY>`. This credential cannot read general workspace routes, approve decisions or administer users. Browser routes use the existing session; test imports require the owner (or unauthenticated local development).

| Endpoint | Meaning |
|---|---|
| `POST /api/integration/v1/cases` | Create/update a complete source case snapshot |
| `GET /api/integration/v1/results?limit=100` | Collect oldest unacknowledged final decisions; limit 1–200 |
| `POST /api/integration/v1/results/{decision_id}/receipt` | Confirm the result was saved in the source system |
| `GET /api/integration/sample` | Download a complete synthetic example with an attachment (browser session) |
| `POST /api/integration/test-import` | Import a test package using an owner session |
| `GET /api/integration/status` | Connection configuration and latest 100 cases/results |
| `GET /api/integration/export` | Download latest 100 approved results, including receipt status; does not acknowledge |

Download the example from Council connection for the complete `CaseIn` fields. Its envelope is:

```json
{
  "schema_version": 1,
  "council_id": "northgate-sandbox",
  "source_system": "generic",
  "source_case_id": "example-001",
  "source_version": 1,
  "case": { "...": "complete CaseIn object from the example" },
  "attachments": [{
    "evidence_id": "E1",
    "filename": "synthetic-note.txt",
    "content_type": "text/plain",
    "content_base64": "U3ludGhldGljIGV2aWRlbmNlLg=="
  }]
}
```

Versions are positive, increasing integers. Identical repeats return `unchanged`; a reused version with different content or an older version returns 409. New versions must include the complete case and all attachments. Evidence IDs must be unique and each attachment must refer to one. Limits: 10 MiB per attachment and 20 MiB decoded files per package. Supplied file hashes/size metadata are replaced with values calculated from the bytes. Unsupported file types, invalid packages and non-synthetic cases are rejected without importing a partial case.

Updated source snapshots invalidate prior reviews. Updates are refused after a final decision or if an officer changed the evidence in Civic; reconcile those cases rather than overwriting their work. Duplicate PCN references cannot silently attach an existing manual case to a connector.

Results include `decision_id`, council/source IDs, `source_case_id`, `source_version`, PCN reference, final outcome/response, reason, reviewer, approval time, Mubit model/request/review IDs, AI recommendation and policy/ruleset versions. Use `decision_id` as the connector's idempotency key. Commit the write to the supplier system before sending a receipt:

```json
{
  "receipt_id": "supplier-transaction-123",
  "source_case_id": "example-001",
  "source_version": 1
}
```

Repeat receipts with the same values succeed; mismatched versions/cases or a different receipt ID return 409. If result storage succeeds but acknowledgment fails, the connector must recognize the decision ID and resend its original receipt, not repeat the council mutation. Keep polling and acknowledging batches until the pending list is empty. This is at-least-once delivery, not an exactly-once guarantee across systems.

## Work needed for a real council

Choose a pilot and obtain its supplier API specification and sandbox access. Implement the mapping to/from this contract, including attachment retrieval, source versions and decision codes, then verify both directions against that sandbox. Configure and validate council-specific policies, identity/roles, privacy and retention before enabling real data. The present synthetic guard is intentionally unchanged. There is no claim that any council can connect without this work.

Taranto publicly documents two-way API support and a sandbox in its [service listing](https://www.applytosupply.digitalmarketplace.service.gov.uk/g-cloud/services/342557571234466). That establishes an integration opportunity, not confirmation of particular evidence or decision endpoints.
