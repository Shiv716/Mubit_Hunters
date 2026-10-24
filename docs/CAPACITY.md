# Capacity and scaling

Reviewed **24 October 2026**. **There is no application cap on registered driver accounts, but no load-tested maximum user count is established.** The live Render/Neon subscription tiers, available storage and provider budget have not been inspected. Account storage, monthly active users, concurrent visitors and AI throughput are different limits.

## Limits enforced by Civic

| Area | Current limit | Meaning |
|---|---|---|
| Driver AI | 200 requests/hour globally; 20/hour per driver | Scan and assessment share the budget; retries and some rejected attempts consume quota |
| New cases | 20/day per driver | Abuse control, not a lifetime case cap |
| Case list | Latest 200 cases per driver | Query/display limit; older records are not automatically deleted; pagination is not implemented |
| Sign-in codes | 100 requests/hour globally; one/minute per email | Signup and returning users share this flow; email-provider limits can be stricter |
| Code verification | 300 attempts/minute globally; 10/10 minutes per email | Separate from sending codes |
| Driver evidence | Eight photos/case; 8 MiB input/photo; ≤24 megapixels | JPEG/PNG/WebP; resized to fit 1800×1800 and stored as JPEG bytes in Neon |
| Case AI lease | 180 seconds per case | Avoids overlapping work while valid; not a background worker or overall latency guarantee |
| Public demo AI | 60 calls/hour and 200/day globally | Separate from driver AI; a scan plus assessment normally consumes two calls |
| Demo execution | One live call at a time per process; 100 temporary runs; 30-minute TTL | Run state disappears on restart; unsuitable for unmodified multi-instance deployment |
| Database connections | Pool minimum 1, maximum 8 per web worker | Connections are shared across requests; eight connections does not mean eight registered users |
| Destination search | One uncached Photon request/second per process | 24-hour cache, up to 200 queries; public geocoder has no availability guarantee |

Sources: [driver routes](../backend/app/consumer.py), [auth](../backend/app/consumer_auth.py), [demo](../backend/app/consumer_demo.py), [image handling](../backend/app/consumer_ai.py), [database](../backend/app/db.py), [map](../backend/app/parking.py). Council attachments have separate limits: 10 MiB/file and 20 MiB/package for the [exchange](COUNCIL-INTEGRATION.md).

**200 AI requests/hour permits a theoretical 100 scan-plus-assessment journeys/hour before retries.** That is a rate-budget calculation, not a measured completion rate or 100 simultaneous users. Model latency, hosting resources, provider concurrency/credits and database contention can reduce throughput. Manual entry may avoid the scan call. The sign-in quota independently limits new code requests.

## How many accounts fit?

Accounts and text are relatively small; retained photos can dominate storage. Estimate from actual stored image sizes, including expected cases/user, then reserve capacity for rows, indexes, review history and operational headroom.

For illustration only:

> 1,000 users × 2 cases/user × 3 photos/case × 0.5 MiB/stored photo = 3,000 MiB, approximately **2.93 GiB of photos alone**.

This is an assumption, not a measurement of Civic's real images or a supported account count. Uploaded files are recompressed, so the 8 MiB upload ceiling is not their usual stored size. Backups and retained history need their own budget. Deleting active driver cases does not immediately erase provider records or backups.

Check **Render service → compute/metrics**, **Neon → plan/usage**, and **Mubit → usage/credits** before setting a launch target. Record CPU, memory, database size, connection waits, request latency, error rates and real stored bytes/case. Test a representative workload on staging with synthetic data; agree the latency/error target before calling any user count supported.

## Hosting plans are separate constraints

As checked on 24 October 2026, Neon's published Free plan lists **1 GB PostgreSQL storage/project** and **60,000 Auth monthly active users**. Auth MAU is a billing/service allowance, not proof that Civic can support that many active drivers. Neon Object Storage is a separate allowance; Civic currently stores images inside PostgreSQL. [Neon plans](https://neon.com/docs/introduction/plans).

If the Render service uses its Free tier, it sleeps after 15 idle minutes and can take about a minute to wake. This explains a slow first visit, not every slow in-app navigation. Render recommends a paid instance for production; its Free web services cannot scale beyond one instance. These are conditional limits, not a claim about this service's current plan. [Render Free](https://render.com/docs/free), [scaling](https://render.com/docs/scaling).

## Scaling order

1. Confirm provider plans, observe a representative pilot and remove cold starts if the chosen tier sleeps. Set spend and storage alerts.
2. Use private object storage when evidence volume warrants it; introduce explicit retention and verify backup/restore procedures.
3. Move long AI work to durable jobs with status, idempotency, bounded retries and cancellation. The current HTTP request path is not a queue.
4. Share demo state, cache and geocoder throttling before adding workers/instances. Use a geocoder with an appropriate service agreement for larger traffic.
5. Review pool sizing: each additional web worker can open eight connections. Match aggregate connections and compute to Neon and provider concurrency limits.
6. Revisit the explicit request quotas after measured tests and cost review. Raising a quota alone does not add capacity.

No automatic scaling policy or production load test is included. [Deployment guide](DEPLOYMENT.md) · [Architecture](ARCHITECTURE.md).
