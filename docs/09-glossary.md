# Glossary

Reviewed **24 October 2026**. Terms are scoped to Civic's implemented workflow; statutory deadlines and legal eligibility depend on the specific notice and stage.

| Term | Meaning |
|---|---|
| Civic | Mubit-Hunters' consumer parking appeal preparation app, with a separate council review workspace |
| PCN | Can mean a council **Penalty Charge Notice** or a private **Parking Charge Notice**; these have different procedures |
| Issuer | Council or private operator identified on the notice; normally the first destination for the user's challenge |
| Driver / keeper | Different roles; Civic must not assume the registered keeper drove |
| CEO | **Civil Enforcement Officer**, not a company's chief executive. A CEO photo is optional unless selected council policy requires it |
| Challenge / representation / appeal | Stage-dependent procedures; an initial challenge is not automatically a tribunal or independent appeal |
| Evidence | Supplied material supporting the actual events. Consumer photos can be inspected by vision; council attachments currently supply descriptions to AI |
| Appeal pack | User-approved draft and supporting files for external submission; downloading it does not submit anything |
| Self-reported outcome | Cancellation, rejection, payment or refund entered by a user; not independent verification |
| Verified success | Outcome independently established and marked verified; this release has no user-facing verification workflow |
| Mubit | Hosted inference gateway and provider platform; Civic uses its configured model route |
| Model | The configured provider model performing extraction or generation, e.g. the observed `gpt-6-luna` deployment |
| Task / adapter | Provider-side grouping/training concepts; console entries do not establish Civic submitted corrections or activated a trained version |
| Precedent retrieval | Adding approved similar council examples to a prompt; does not update model weights |
| Correction export | Civic's owner-approved original/target package; not a training request or documented Mubit import format |
| Neon | Managed PostgreSQL and managed Better Auth for persistent records and email-code identity |
| Render | Hosting service running the application container and HTTPS endpoint |
| Docker | Reproducible application packaging; optional local runtime, not the hosted database |
| `PCN_ACCESS_KEY` | Application cookie-signing secret; not a driver's email code |
| OSM parking location | A mapped car park/parking area, not necessarily one bay or a currently available space |
| Keeper lookup | A request for registered-keeper information; not a count of distinct people or every parking ticket |
| Auth MAU | Unique users authenticating in a month under a provider's plan; not simultaneous application capacity |
| Synthetic case | Fictional council/demo input; must not be counted as a real customer or success |

[Documentation index](README.md) · [User flow](02-user-process.md).
