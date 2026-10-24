# Running and deploying Civic

Reviewed **24 October 2026**. Hosted app: **https://mubit-hunters.onrender.com/**. Default product: public signup and private driver appeals. The separate council workspace uses owner-approved membership. [Architecture](ARCHITECTURE.md) · [Capacity](CAPACITY.md).

## Existing Render service

| Setting | Value |
|---|---|
| Repository / deployment branch | `Shiv716/Mubit_Hunters` / `main` |
| Runtime | Docker |
| Dockerfile / build context | `./Dockerfile` / repository root |
| Health check | `/api/ready` |
| Docker command | Empty; use the Dockerfile default |
| Public URL | `https://mubit-hunters.onrender.com` |

The image builds React using Node 22 and runs FastAPI on Python 3.14 as a non-root user. `backend/start.py` starts one Uvicorn worker on Render's `PORT`. FastAPI serves both the frontend and API. Neon persists records and photos; Render's local filesystem is not the evidence store.

Push reviewed changes to `main`. Automatic deployment runs if enabled; otherwise choose **Manual Deploy → Deploy latest commit**. `render.yaml` is a blueprint for a **new** service, not an update mechanism for the existing service's environment. Do not create a duplicate service to update settings. Its example model route can differ from the existing service's configured route.

## Required environment

Store secrets in Render → Environment or an ignored local `.env`, never in Git, screenshots or chat.

| Variable | Purpose/value |
|---|---|
| `DATABASE_URL` | Neon PostgreSQL connection URL with SSL parameters; prefer the pooled endpoint for hosted workloads |
| `NEON_AUTH_BASE_URL` | HTTPS Auth URL from the **same Neon branch** as `DATABASE_URL`; current project URL below |
| `PCN_ACCESS_KEY` | Random cookie-signing secret, at least 16 characters; **not a sign-in code or a user's password** |
| `PCN_ACCESS_REQUEST_EMAIL` | Council workspace owner's email; currently required by startup validation whenever Neon Auth is enabled, even for a driver-focused deployment |
| `PCN_ENV` | `production` |
| `PCN_COOKIE_SECURE` | `true` on hosted HTTPS |
| `PCN_PUBLIC_ORIGIN` | `https://mubit-hunters.onrender.com`, with no path or trailing slash |
| `PCN_DB_SCHEMA` | `civic` by default |
| `PCN_EVIDENCE_STORAGE` | `database` on Render; driver photos always use database storage |
| `PCN_ALLOW_PASSWORD_LOGIN` | `false`; keep legacy council password login disabled with Neon Auth |
| `AI_PROVIDER` | `mubit` for real AI requests |
| `MUBIT_API_KEY` | Server-side Mubit credential |
| `MUBIT_ROUTE` | `openai` or `anthropic`, matching the account's supported gateway |
| `MUBIT_MODEL`, `MUBIT_BASE_URL` | Optional overrides; otherwise use the selected route's defaults |

Current project's public Auth URL:

```text
https://ep-dry-cake-za1nvk8t.neonauth.c-2.eu-west-2.aws.neon.tech/neondb/auth
```

Enter only that URL as the variable's value—no quotes, Markdown or `NEON_AUTH_BASE_URL=` prefix. Render supplies `PORT` and its external URL. Startup refuses a missing database on Render, local-file evidence storage on Render, an undersized signing key, or invalid Auth/origin/owner configuration. Startup applies additive migrations; it does not seed cases or create driver accounts.

For the current live service, OpenAI-compatible `gpt-6-luna` inference was verified on 24 October 2026. The examples/Blueprint default to `anthropic`, whose adapter default is `claude-haiku-4-5`. Preserve the existing environment unless intentionally changing models. A model must support images for ticket scanning. [Mubit configuration](04-mubit-integration.md).

## Public driver signup

In Neon Auth, enable Email OTP, email verification and **new user signup**, and trust `https://mubit-hunters.onrender.com`. Auth and application data must use the same branch. The application's database role needs read access to managed `neon_auth.session` and `neon_auth.user`; Civic never writes those tables directly.

Flow: **Sign up/sign in → Neon emails a code → verify the code → private appeals**. New drivers do not request council-owner approval. Neon delivers these codes through its configured email service. No Resend account is required for a driver, and `PCN_ACCESS_KEY` cannot be used as their code.

Civic's HttpOnly first-party cookie refers to the live Neon session, for up to 12 hours bounded by that session's expiry. Every private request rechecks it. Signing out clears the Civic cookie; it does not sign out other applications using Neon Auth.

## Optional council access notifications

The retained `/#workspace` flow is **Request access → owner approves → applicant verifies a Neon email code**. It is separate from driver signup.

| Variable | Purpose |
|---|---|
| `PCN_ACCESS_REQUEST_EMAIL` | Sole council workspace owner and request-notification inbox |
| `RESEND_API_KEY` | Optional Resend key for owner notifications only |
| `PCN_EMAIL_FROM` | Verified sender; without a domain use `Civic <onboarding@resend.dev>` and the Resend signup inbox as the owner |

Sign in to the council workspace as the owner email to bootstrap administration. Applicants need no Resend account. Requests persist in Neon even if mail fails; the owner can approve/revoke or retry from **Admin → Access requests**. A 202 response means the request was saved, not that email arrived. Approval persists if sending the Neon code fails; the approved user can request another code.

An owner notification includes a single-use, 24-hour review credential in the link fragment. Opening the link does not approve access; the owner explicitly confirms on the page. Treat that link as private. Approval and mailbox verification are separate gates. Provider “delivered” status does not establish that a message is visible in the inbox being checked.

References: [Neon Email OTP](https://neon.com/docs/auth/guides/plugins/email-otp), [Neon email configuration](https://neon.com/docs/auth/guides/customize-emails), [Resend sender domains](https://resend.com/docs/dashboard/domains/introduction).

## Local development

Requires Python 3.14 and Node 22.12+. From the repository root, start an isolated offline workspace:

```sh
DATABASE_URL='' NEON_AUTH_BASE_URL='' RENDER='' PCN_ENV=development \
  AI_PROVIDER=stub PCN_DB_PATH=/tmp/civic-local.db \
  PCN_EVIDENCE_DIR=/tmp/civic-local-evidence bash scripts/dev.sh
```

Open **http://127.0.0.1:5173**; the API is on port 8000. The script creates the virtual environment, installs dependencies and runs both servers. Ctrl-C stops them. Public home/map and the labelled sample walkthrough are available offline; real driver accounts and real AI are not simulated.

For account/AI development, create a **separate Neon test branch**, then use `.env.example` without replacing an existing `.env`:

```sh
test -f .env || cp .env.example .env
# Edit .env with test-only credentials and the matching test Auth URL.
bash scripts/dev.sh
```

Set `PCN_PUBLIC_ORIGIN=http://127.0.0.1:5173`, `PCN_COOKIE_SECURE=false`, the required owner/signing settings, and trust that local origin in the test Auth configuration. Use `AI_PROVIDER=mubit` for actual consumer scanning/advice; these calls can incur provider charges. Root `.env` is supported; existing environment variables win, then legacy `backend/.env`, then root `.env`. **The same URL and schema locally and on Render share the same data.** Never use production for development or tests.

## Local Docker

Docker is optional locally; Render uses the Dockerfile without requiring your laptop to keep Docker running.

Configure an ignored `.env` with a strong signing key and test-only database/Auth settings. For this mode use `PCN_PUBLIC_ORIGIN=http://localhost:8000`, `PCN_COOKIE_SECURE=false` and trust that origin in test Auth. Then:

```sh
docker compose up -d --build
docker compose ps
```

Open **http://localhost:8000**. Compose uses production mode, so stub AI cannot run real reviews; the explicit public sample walkthrough remains available. With no Neon Auth configured, private driver signup is unavailable; the legacy council bootstrap login can use the signing key as its shared password. Do not enable that flow on the hosted service.

When `DATABASE_URL` is blank, SQLite and council attachments use the named `civic-data` volume. With Neon configured, new database records and database-mode evidence go to Neon. Stop local containers with:

```sh
docker compose down
```

This keeps the volume. `docker compose down -v` deletes local volume data and should not be used when it must be retained.

## Existing SQLite council data

Changing `DATABASE_URL` does not copy data. `backend/migrate_sqlite.py` migrates **only its explicitly supported council tables and evidence**. It does **not** migrate driver cases/photos, Neon Auth users/sessions or council access-request memberships. It is not a general whole-product migration tool.

Before migration, stop source writes, retain a durable backup and use an empty destination for the supported council tables. For an older Docker workspace:

```sh
docker compose stop civic
mkdir -p /private/tmp/civic-backup
docker compose cp civic:/data/. /private/tmp/civic-backup/
docker compose start civic
```

Copy the backup somewhere durable. Older development data may be in `backend/pcn_copilot.db` and `backend/evidence_store`. With the intended destination URL configured, preview:

```sh
.venv/bin/python backend/migrate_sqlite.py \
  --source-db /private/tmp/civic-backup/civic.db \
  --evidence-dir /private/tmp/civic-backup/evidence
```

Review the preview before adding `--apply`. The source is read-only; the importer validates attachment hashes, preserves IDs and resets sequences. Nonempty supported destination tables are rejected; it does not merge datasets. This cannot recover an old Render SQLite file after that filesystem has been discarded.

## Post-deploy verification

1. Confirm the expected `main` commit in Render and a successful `/api/ready` response with `database: postgresql`.
2. Check `/api/health` for configured storage/provider and `/api/consumer/session` for driver Auth availability. Health/readiness are not tests of email delivery or live inference.
3. Open the home, sample ticket and map. Confirm assets load and that a refresh works.
4. For an auth/provider change, verify one synthetic driver's email code and one non-sensitive Mubit flow. Confirm the displayed model/request metadata. This is a paid live check, separate from mocked tests.
5. Check logs for errors without logging uploaded evidence, email codes, keys or connection strings. Do not re-seed production or create fake product outcomes as a health check.

Optional council samples: the retained workspace's **Explore sample appeals** action loads 17 fictional cases idempotently. These are not driver accounts, actual customer cases or marketing successes.

## Troubleshooting

| Symptom | Check |
|---|---|
| `requirements.txt` missing | Render must use Docker with repository-root context and `./Dockerfile`; remove an obsolete native build command |
| Auth URL startup error | Paste the plain HTTPS Auth URL; ensure it matches the database branch and required owner/origin settings |
| Cannot sign in with `PCN_ACCESS_KEY` | It signs cookies; enter the fresh Neon email code for driver sign-in |
| Request-access email missing | Council owner notifications use Resend; signup/sign-in codes use Neon. Check the appropriate service and exact recipient |
| Old hashed JS/CSS returns 404 | Confirm a completed deploy, then hard-refresh the page; an already-open page can reference the previous build's assets |
| AI unavailable / 503 | Check `AI_PROVIDER=mubit`, valid server-side key, supported route/model and provider credits; configured health is not successful inference |
| 429 | A documented request quota was reached; retries can consume quota. See [capacity](CAPACITY.md) |
| Slow first page after idle | If on Render Free, cold start is possible; inspect the actual plan and request timings before attributing all slowness to it |

## Backups, scaling and checks

Use Neon's restore facilities for the actual plan and verify a restoration on an isolated branch. Database blobs are included in the storage/backup budget. Consumer deletion and council append-only history have different retention behaviour; neither is a complete automated retention programme. See [capacity](CAPACITY.md) before increasing workers or adding instances.

Run only the checks relevant to a change. Application checks:

```sh
.venv/bin/python -m pytest backend/tests -q
npm test --prefix frontend
npm run build --prefix frontend
```

Build Docker when changing packaging/runtime: `docker build -t civic-check .`. CI also runs selected workflows against disposable PostgreSQL. Set `PCN_TEST_DATABASE_URL` only to a disposable test database; tests use isolated schemas and must never target the production Neon workspace. Documentation-only edits need link/schema/diagram checks, not a production load test.

For council exchange, configure `PCN_COUNCIL_ID`, `PCN_COUNCIL_NAME`, `PCN_CASE_SYSTEM`, versioned `PCN_POLICY_FILE` and a distinct `PCN_INTEGRATION_KEY` of at least 32 characters. Leave the machine key unset until needed. The exchange is synthetic; real supplier integration requires additional authorised work. [Council exchange contract](COUNCIL-INTEGRATION.md).

References: [Render Blueprint](https://render.com/docs/blueprint-spec), [health checks](https://render.com/docs/health-checks), [Neon Python connections](https://neon.com/docs/guides/python).
