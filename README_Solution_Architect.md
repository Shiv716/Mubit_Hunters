> Original design brief retained for reference. The implemented `trial-2` architecture is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), with runnable setup in [README.md](README.md).

# PCN Review Copilot

### Solution Architecture & Implementation Brief

**Repository:**
[Mubit_Hunters](https://github.com/Shiv716/Mubit_Hunters)\
**Status:** Proposed architecture for solution-architect review;
implementation details and provider capabilities must be verified.\
**Primary use case:** AI-assisted review of Penalty Charge Notice (PCN)
challenges, with human decision-making and a measurable Mubit-powered
feedback loop.

------------------------------------------------------------------------

## 1. Executive Summary

PCN Review Copilot is an intelligence layer for council
parking-enforcement teams. It helps authorised staff review a motorist's
representation against a PCN by organising case evidence, checking
verifiable facts, identifying relevant policy or rule references, and
producing a structured recommendation for human review.

The platform is **not** intended to replace existing CCTV, ANPR, PCN
issuance, or council case-management systems in the MVP. It should
initially run with synthetic or explicitly authorised case data and a
simulated integration boundary.

The differentiating capability is a learning loop: reviewer corrections
and verified outcomes are recorded, curated into suitable feedback
examples, used through Mubit's supported model-update workflow where
available, and evaluated before a new model version is deployed.

**Non-negotiable principle:** the AI provides decision support. An
authorised human remains responsible for consequential enforcement
decisions.

## 2. Product Scope and Positioning

### In scope for the MVP

-   Receive or create a synthetic PCN representation.
-   Assemble structured case details, representation text, evidence
    metadata, and applicable policy references.
-   Run deterministic checks for facts that can be reliably verified.
-   Call Mubit through a provider adapter for structured AI assistance.
-   Present the recommendation and supporting evidence to a reviewer.
-   Allow a reviewer to accept, correct, reject, or escalate a
    recommendation.
-   Record the original prediction, human correction, reason, reviewer,
    and timestamp.
-   Demonstrate a real, documented Mubit feedback/update path if the
    provider capability is confirmed.
-   Evaluate a candidate model/adapter against a fixed holdout dataset
    before deployment.
-   Provide basic audit history and evaluation metrics.

### Explicitly out of scope for the first demo

-   Connecting to live London CCTV or ANPR feeds.
-   Issuing or cancelling PCNs automatically.
-   Production write access to council or tribunal systems.
-   Building a new computer-vision or number-plate-recognition system.
-   Treating every successful appeal as proof of an AI or officer error.
-   Claiming a model improved unless a repeatable evaluation supports
    the claim.

### Future extension

Parking-event detection and CCTV/ANPR integrations may become upstream
data sources in a later phase. They are not a second MVP workflow and
should not distract from proving the PCN-review feedback loop first.

## 3. Primary User Workflow

1.  **Receive a representation:** create or ingest a PCN challenge and
    its case metadata.
2.  **Assemble evidence:** attach or reference the PCN, timestamps,
    location, payment/permit information, signage records, and submitted
    evidence where available.
3.  **Validate the case:** check required fields, evidence availability,
    duplicates, and data consistency.
4.  **Apply deterministic checks:** evaluate verifiable facts against a
    versioned rule set. Do not use an LLM as the authoritative source of
    legal rules.
5.  **Request AI assistance:** send a structured task to Mubit via the
    backend adapter.
6.  **Validate the response:** validate schema and required fields;
    handle timeouts, malformed output, and unsupported claims safely.
7.  **Human review:** show the recommendation, supporting evidence,
    relevant rule references, missing information, and any uncertainty
    flags.
8.  **Authorised decision:** the reviewer accepts, overrides, rejects,
    or escalates the recommendation. Generate a draft response only for
    review.
9.  **Record the outcome:** retain the original recommendation, final
    human decision, rationale, and subsequent case/appeal outcome as
    distinct records.
10. **Feedback and learning:** curate eligible reviewed examples, use
    the verified Mubit update mechanism, evaluate the candidate version,
    and deploy only if agreed thresholds are met.

### Workflow diagram

``` mermaid
flowchart TD
    A[PCN representation received] --> B[Assemble case and evidence]
    B --> C[Validate fields, evidence and duplicates]
    C --> D[Deterministic checks against versioned rules]
    D --> E[Mubit-powered structured review]
    E --> F[Validate AI output and flag uncertainty]
    F --> G[Human reviewer]
    G -->|Accept or edit| H[Authorised decision and draft response]
    G -->|Reject or escalate| I[Manual investigation]
    H --> J[Record decision and case outcome]
    I --> J
    J --> K[Curate reviewed feedback examples]
    K --> L[Invoke supported Mubit update workflow]
    L --> M[Evaluate candidate against fixed holdout set]
    M -->|Passes release gates| N[Controlled deployment]
    M -->|Fails release gates| O[Keep previous version and investigate]
    N --> E
```

## 4. Proposed Technical Architecture

Keep the MVP simple. A modular monolith is the default recommendation
unless the architect identifies a concrete reason to split services.

### Frontend

-   Reviewer dashboard for case details, evidence, recommendation,
    correction controls, and decision history.
-   Basic administrative view for evaluation runs and model-version
    status.
-   Exact framework to be confirmed against the existing repository and
    team capability.

### Backend

-   **Case API:** case lifecycle, representation details, decisions, and
    tasks.
-   **Ingestion/validation module:** input validation, evidence
    metadata, duplicate checks, and schema enforcement.
-   **Rules module:** versioned deterministic checks and policy
    references.
-   **AI orchestration module:** builds the task payload, invokes Mubit,
    validates responses, and records model/task metadata.
-   **Feedback module:** records corrections and prepares eligible
    feedback examples.
-   **Evaluation/release module:** manages datasets, metrics, release
    thresholds, and rollback.
-   **Integration adapter:** isolates Mubit and any future
    council-system integrations from application logic.

### Data storage

-   **SQLite** may be sufficient for a local, single-user hackathon demo
    if that is already what the repository uses.
-   **PostgreSQL** is the preferred next step if concurrent access,
    deployment, or stronger relational/tenant requirements justify it.
-   Store evidence files in object storage or a controlled local
    directory; keep file metadata and access policy in the database.
-   Do not add a queue, microservices, or infrastructure until the MVP
    requires them.

### Provider boundary

Implement a `MubitAdapter` (or equivalent interface) so
provider-specific request/response formats do not spread through the
codebase. Keep provider credentials in environment variables or a
secrets manager, never in source control.

The precise programming language, framework, deployment target, and
storage choice must be reconciled with the actual repository before
implementation.

## 5. Mubit Integration: Critical Verification Item

Mubit integration is the highest-priority technical dependency. Do not
assume a correction automatically trains a model or that every planned
endpoint exists.

The architect and team must confirm from current Mubit documentation or
directly with the provider:

1.  Supported inference API/SDK and authentication.
2.  Required task definition, payload format, response schema, and task
    grouping behaviour.
3.  Whether/how reviewer feedback can be submitted to Mubit.
4.  The actual model-update or adapter-training trigger and eligible
    feedback format.
5.  How to retrieve job status, resulting model/adapter version, and
    provider metadata.
6.  Available evaluation workflow, baseline comparison,
    deployment/version selection, and rollback options.
7.  Rate limits, latency, cost, data handling, retention, and any
    constraints on personal or sensitive data.

### Keep three mechanisms separate

-   **Outcome recording:** save the recommendation and the final human
    decision.
-   **Context/precedent retrieval:** provide relevant reviewed examples
    to a later case when appropriate. This is not proof of model
    training.
-   **Model calibration/update:** use Mubit's confirmed update path,
    evaluate the candidate version, and deploy only after passing
    release gates.

If automated model updating cannot be demonstrated within the hackathon,
be transparent. Demonstrate the real supported provider flow that is
available and label any simulated update clearly; do not present a
database write or precedent lookup as model training.

## 6. Proposed Data Model

The following are logical entities for architect review, not a claim
that every table already exists.

  -----------------------------------------------------------------------------
  Area                    Suggested entities            Purpose
  ----------------------- ----------------------------- -----------------------
  Access                  `organisations`, `users`,     Identity, permissions,
                          `roles`,                      tenant boundaries,
                          `organisation_memberships`,   audit
                          `audit_logs`

  Case                    `cases`, `representations`,   Case lifecycle and
                          `case_tasks`                  challenge text

  Evidence                `media_assets`,               Evidence metadata and
                          `representation_evidence`,    references
                          `signage_records`

  Rules                   `parking_rules`,              Versioned policy/rule
                          `rule_conditions`,            inputs
                          `rule_versions`

  Decision                `ai_predictions`,             Separate AI outputs
                          `human_corrections`,          from authorised
                          `case_decisions`,             decisions
                          `representation_decisions`

  Outcome                 `tribunal_appeals`,           Record later outcomes
                          `adjudicator_decisions`,      without assuming their
                          `outcome_labels`              meaning

  Mubit/evaluation        `model_versions`,             Traceability of updates
                          `model_update_jobs`,          and results
                          `evaluation_runs`,
                          `model_deployments`,
                          `dataset_versions`
  -----------------------------------------------------------------------------

### Data-model requirements

-   Use primary keys, foreign keys, constraints, and indexes for common
    queries.
-   Preserve the original prediction and later human decision; do not
    overwrite one with the other.
-   Store timestamps and the version of the rules used for a
    recommendation.
-   Store model/task/version identifiers returned by Mubit where
    available.
-   Record correction reason codes and reviewer identity where
    appropriate.
-   Define case lifecycle states and permitted transitions.
-   Add organisation-level access controls before multi-organisation
    use.
-   Treat an appeal result as an outcome signal requiring
    interpretation, not automatically as a model-error label.

## 7. AI Output Contract

The AI output should be schema-validated. The final schema should be
agreed with the architect and aligned with what Mubit supports. A
starting concept is:

``` json
{
  "recommendation": "accept | reject | needs_review",
  "reason_summary": "Short explanation based on supplied case facts",
  "relevant_rule_references": [],
  "evidence_references": [],
  "missing_information": [],
  "uncertainty_flags": [],
  "draft_response": null
}
```

Do not invent legal clauses or facts. Every rule reference must resolve
to a supplied, verified source. A confidence field should only be
included if its meaning and calibration are understood; model-generated
confidence must not be treated as a guarantee of correctness.

## 8. Evaluation and Success Metrics

Create a fixed, labelled test dataset with representative cases before
claiming improvement. Keep evaluation examples separate from
update/training examples to avoid leakage.

Minimum evaluation: - Recommendation quality against reviewed labels,
using suitable classification metrics. - Performance on important error
categories and ambiguous cases. - Quality of evidence/rule references
and rate of unsupported claims. - Human override/correction rate and
reasons. - Response latency and cost where measurable. - Regression on
previously handled cases after an update. - Update job status and time
from curated feedback to an evaluated candidate, if supported.

Define release thresholds before running the comparison. Keep the
previous version if the candidate fails. Report measured results,
dataset size, limitations, and whether any part of the demo uses
simulated data.

## 9. Security, Privacy, and Governance

-   Use synthetic or explicitly authorised data for the hackathon.
-   Minimise personal data; avoid real vehicle registration details
    unless authorised and necessary.
-   Restrict access to evidence and log sensitive access.
-   Store credentials outside the repository.
-   Encrypt data in transit and at rest for deployed environments.
-   Define retention, deletion, and backup policies.
-   Use role-based access and tenant isolation if multiple organisations
    are supported.
-   Maintain a traceable record of evidence, rule version, model
    version, recommendation, human decision, and outcome.
-   Keep a human authorisation step for consequential enforcement
    decisions.
-   Assess applicable UK data-protection obligations and whether a Data
    Protection Impact Assessment is required before real CCTV, ANPR, or
    vehicle data is used.

## 10. Implementation Plan

### Phase 0 --- Verify before building

-   Review the existing repository and design documents.
-   Confirm the exact Mubit inference and feedback/update capabilities.
-   Agree the input case schema, output contract, case states, and
    evaluation dataset.
-   Record unresolved assumptions as explicit decisions.

### Phase 1 --- End-to-end local vertical slice

-   Load synthetic cases.
-   Implement case/evidence validation and a small versioned ruleset.
-   Implement the Mubit adapter and a safe failure path.
-   Display the recommendation and evidence in the UI.
-   Implement accept/correct/reject and audit history.

### Phase 2 --- Feedback and evaluation

-   Curate reviewed corrections.
-   Implement the confirmed feedback/update mechanism.
-   Track update jobs and model versions where supported.
-   Run baseline-versus-candidate evaluation and enforce release gates.
-   Add regression tests and rollback.

### Phase 3 --- Demo hardening

-   Prepare repeatable seed data and demo instructions.
-   Test provider timeouts, invalid responses, missing evidence,
    ambiguous cases, and update failures.
-   Display real measured results and clearly identify simulated
    components.
-   Document known limitations and future integration points.

## 11. Definition of Done

The MVP is ready for demonstration when a synthetic PCN representation
can be processed end to end: evidence is validated, deterministic checks
run, Mubit returns a schema-valid recommendation, a human can correct or
approve it, the full decision history is stored, and the team can
demonstrate the confirmed feedback/update path plus a repeatable
evaluation against a baseline.

No model-improvement claim should be made without measured evidence. If
a provider capability is simulated, it must be labelled as simulated.

## 12. Questions for the Solution Architect

Please review and return decisions on:

1.  Does the proposed workflow match the current repository and intended
    hackathon track?
2.  Which components and data models already exist, and which should be
    changed?
3.  What exact Mubit APIs/SDK capabilities are confirmed for inference,
    feedback, updates, versioning, and evaluation?
4.  What is the smallest end-to-end slice that can be implemented and
    tested first?
5.  Is SQLite adequate for the demo, or is PostgreSQL needed now?
6.  What case states, permissions, and audit events are required?
7.  What dataset and release thresholds will make the evaluation
    credible?
8.  What privacy, security, and data-retention controls are necessary
    for the demo?
9.  Which features are explicitly deferred until after the hackathon?

### Recommended first action

**Verify Mubit's real feedback-to-update path, then implement one
complete synthetic-case workflow.** Do not expand into live CCTV/ANPR,
production integrations, or a complex distributed architecture until
that core loop works.
