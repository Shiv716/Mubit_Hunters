# Privacy, safety and operational boundaries

Reviewed **24 October 2026**. This describes implemented controls and remaining work, not a legal compliance certification or security audit.

## Implemented controls

- Driver records/photos are owner-scoped; Neon sessions are rechecked on private requests. Council access uses a separate session audience and owner-approved membership.
- First-party HttpOnly cookies, secure cookies on hosted HTTPS, origin checks for mutations, server-side credentials and request quotas reduce common exposure paths.
- Photos are bounded, decoded, metadata-stripped and resized. Case-level consent is required before real consumer AI processing.
- Driver AI uses metadata-only recording requests. Inputs and outputs are typed/validated; source/evidence references are restricted to supplied IDs. User confirmation and approval remain required.
- Unsupported/later stages return specialist help. The driver submits externally; Civic has no tool that automatically cancels a ticket or sends an appeal.
- Council tools are bounded and read-only. Synthetic policy checks constrain recommendations; officer decisions and audit records are retained. Machine exchange credentials cannot approve decisions.

## Limits that matter

| Area | Boundary / remaining work |
|---|---|
| AI reliability | Validation cannot establish that a ticket, photo, claim or legal conclusion is genuine/correct; no fraud-proof or guaranteed-success claim |
| Guidance | Seven dated summaries are limited coverage; maintain them, verify rule applicability and obtain specialist review before expanding scope |
| Provider processing | Consented facts/images leave Civic for Mubit and its configured provider. Metadata recording is not anonymisation or a complete upstream retention guarantee |
| Deletion | Driver case deletion removes active app records/photos; Auth accounts, provider records and backups have separate lifecycles |
| Retention | No general automated retention purge. Council history has append-only rules and replaced council blobs can remain stored |
| Identity/roles | Driver ownership and council owner/member checks exist; enterprise SSO, detailed council roles, subscriptions and multi-council tenancy do not |
| Infrastructure | Hosting regions, provider terms, backup policies and contractual safeguards must be verified for the actual accounts; no universal UK residency/certification claim |
| Maps | OSM attributes may be incomplete/outdated; browser tiles and geocoder requests reach external services. The app stores no location history, but service logs can contain queries/coordinates |
| Outcomes | Self-reported outcomes are unverified. Do not advertise them as audited wins or measured savings |
| Availability | One instance, synchronous inference and external providers need measured capacity and failure handling; see [capacity](CAPACITY.md) |

## Data flows and real deployments

Real driver uploads are distinct from the retained synthetic council sandbox. A synthetic flag on a council case is only an assertion, not a detector of personal information. Masking a registration field does not anonymise free-text narratives or attachments.

Before a real council deployment, obtain approved policy/stage rules, authorised supplier access, an appropriate identity model, independent privacy/security review, agreed retention and tested backup restoration. Do not remove the synthetic guard merely because a council name or machine key has been configured.

Consumer expansion likewise needs current source maintenance, documented provider/data arrangements, clear user notices and measurable operational controls. Officer correction export is not permission to train on personal driver data. [Architecture](ARCHITECTURE.md) · [Mubit data handling](04-mubit-integration.md#data-handling) · [Council exchange](COUNCIL-INTEGRATION.md).
