# Current design decisions

Reviewed **24 October 2026**. This supersedes the original officer-only proposal; Git history retains earlier decisions.

| Decision | Reason / consequence |
|---|---|
| Driver-first public product | Public signup and private appeals match the current consumer use case; council review stays separate |
| One React/FastAPI deployment | Same-origin sessions and one build keep operations simple; no separate frontend host |
| Docker on Render, Neon for persistence/Auth | Packaging, hosting and persistent identity/data serve distinct purposes; local Docker is optional |
| Photos in PostgreSQL for the current release | No additional storage credentials; evidence volume consumes database capacity and must be monitored |
| Separate driver and council access | Public driver signup cannot grant council membership; council workspace remains shared, not multi-tenant |
| Mubit for real driver AI | Vision extraction and source-bounded advice use a configured gateway model; no silent simulation |
| Explicit no-account demo fallback | The app can demonstrate the flow during an outage without claiming prewritten answers are live AI |
| User confirmation and export approval | Extraction can be wrong; changes invalidate approval; the driver submits through the issuer |
| Limited, dated source library | Seven curated summaries are inspectable; no claim of complete or continuously refreshed legal knowledge |
| CEO photos optional by default | Required only when selected council policy says so; missing evidence is assessed in context |
| London snapshot for discovery | Fast map/list browsing without a paid map key; no live occupancy or guaranteed permissions |
| Self-reports separate from verified wins | No invented product success or savings; industry figures have explicit sources/denominators |
| Separate driver training opt-in | Full recording requires a saved optional choice; existing cases stay metadata-only. Fictional demo calls may be fully recorded; Mubit determines eligibility |
| Correction export before training integration | Preserve original inputs and approved targets without inventing unsupported provider APIs |
| One worker and explicit quotas | Current shared-state/capacity limits are documented; no unsupported concurrent-user claim |
| Focused tests and deploy checks | Verify changed behaviour and known boundaries; do not repeatedly run broad checks for documentation-only edits |

Canonical implementation: [architecture](ARCHITECTURE.md). Unbuilt work is listed in [business case](01-business-case.md), [capacity](CAPACITY.md) and [feedback](MUBIT-FEEDBACK.md); a proposal in these documents does not mean it is deployed.
