# Running and deploying Civic

## Existing Render service + Neon

Use the existing [mubit-hunters service](https://mubit-hunters.onrender.com). Render runs the Docker image and provides HTTPS. Neon stores the cases, decisions, audit history and small evidence attachments. Render's filesystem can be replaced during a deployment without losing those records. No separate file bucket or Render disk is required in this setup.

In the existing service's Render dashboard, set:

| Setting | Value |
|---|---|
| Repository / branch | `Shiv716/Mubit_Hunters` / `main` |
| Runtime | Docker |
| Dockerfile / context | `./Dockerfile` / repository root |
| Health check path | `/api/ready` |
| Docker command | Leave empty; use the Dockerfile default |

Under **Environment**, save:

| Variable | Value |
|---|---|
| `DATABASE_URL` | The Neon Connect dialog's PostgreSQL URL, including its SSL parameters; use the pooled URL for concurrent workloads |
| `PCN_ACCESS_KEY` | Your private workspace password, at least 16 characters |
| `PCN_ENV` | `production` |
| `PCN_COOKIE_SECURE` | `true` |
| `PCN_DB_SCHEMA` | `civic` |
| `PCN_EVIDENCE_STORAGE` | `database` |
| `PCN_PUBLIC_ORIGIN` | `https://mubit-hunters.onrender.com` |
| `AI_PROVIDER` | `stub`, or `mubit` with your provider settings below |

Keep credentials in Render Environment and local ignored `.env`, never in Git or chat. Render supplies `PORT` and its external URL; the app uses them automatically. Startup refuses Render deployments without a database or a password of at least 16 characters, and refuses local-file evidence storage on Render.

Choose **Manual Deploy → Deploy latest commit** if automatic deployment is disabled. A successful `/api/ready` response is `{"ok":true,"database":"postgresql"}`. `/api/health` must report `database: postgresql` and `evidence_storage: database`. Open the app, sign in and inspect the queue. Initial startup creates the application schema; it never automatically seeds sample cases. The optional **Explore sample appeals** action loads 17 fictional appeals idempotently.

`render.yaml` documents the same settings for a **new** service. Do not create a new Blueprint for this existing service: it can create a duplicate, and secret placeholders do not configure an existing service's environment. Apply the settings above to the current service instead.

## Request access and Neon Auth

Flow: **Request access → owner approves → Neon emails the applicant a code → applicant returns to Civic, chooses “I already have a code”, and opens the workspace**. Expired codes can be replaced using “Email sign-in code”. No workspace password is emailed. All email domains may request access; subscription/domain enforcement is not implemented.

In the existing Render service, add these variables together and redeploy:

| Variable | Value |
|---|---|
| `NEON_AUTH_BASE_URL` | `https://ep-dry-cake-za1nvk8t.neonauth.c-2.eu-west-2.aws.neon.tech/neondb/auth` |
| `PCN_ACCESS_REQUEST_EMAIL` | Your email address; it receives requests and becomes the sole workspace owner |
| `RESEND_API_KEY` | Your Resend API key, for owner request notifications only |
| `PCN_EMAIL_FROM` | Without a domain: `Civic <onboarding@resend.dev>`, with `PCN_ACCESS_REQUEST_EMAIL` set to your Resend signup email. Alternatively, use a sender on your verified domain. |
| `PCN_ALLOW_PASSWORD_LOGIN` | `false` (default with Neon Auth enabled) |

Keep the existing `DATABASE_URL`, `PCN_ACCESS_KEY` (now the cookie signing secret), `PCN_COOKIE_SECURE=true` and public origin. Auth and database must point to the **same Neon branch**. The database role needs read access to `neon_auth.session` and `neon_auth.user`; Civic never writes those managed tables.

In **Neon → Settings → Better Auth**, enable email sign-up/sign-in and add `https://mubit-hunters.onrender.com` as a trusted domain/origin. Enable email verification. The app uses Neon's Email OTP sign-in API, which verifies the mailbox and can create an account after approval. Sign in as `PCN_ACCESS_REQUEST_EMAIL` to bootstrap the owner; no manual user insert is needed. For local use, add your local origin too and set `PCN_COOKIE_SECURE=false`.

Neon sends applicant sign-in codes through its configured email provider, both on approval and when an approved user requests a new code. Resend sends only the owner's request notification, so the test sender works without an owned domain as long as the owner uses their Resend signup inbox. Applicants do not need Resend accounts. Code delivery shares a one-minute cooldown across approval, owner retries and user requests. Do not subscribe Neon email webhooks unless you also implement their delivery handler.

After redeployment, `/api/session` must report `email_signin: true`. If it is false, check `NEON_AUTH_BASE_URL` in the existing Render service's environment; editing `render.yaml` does not configure that service. An approval can be saved before setup is complete, but the applicant cannot enter until Neon email sign-in works. The owner UI identifies this missing setting. A successful provider response means the email was accepted for sending, not that it reached an inbox.

Requests live in the `civic.access_requests` table, with an additive version-2 migration. **Workspace admin → Access requests** lets the owner approve, revoke, or retry a failed Neon sign-in email. If Resend is unconfigured or unavailable, the request still persists and this list is the fallback. A successful HTTP request means the request was saved, not that email delivery succeeded. Approval survives an email failure; the user can request another code from the login page.

The owner email contains a private review link that expires after 24 hours. Opening it does not change access: the owner presses **Approve access** on the page, preventing email scanners from approving requests. The link is single-use and stored only as a hash. Treat it as an approval credential. Approved users receive a Neon code and return to the same Civic URL; they must prove ownership of their email before seeing cases.

Every authenticated request checks both the live Neon session and Civic approval. Unverified accounts, banned users, expired/revoked Neon sessions and revoked memberships are blocked. Civic uses a first-party HttpOnly cookie so this flow does not depend on Safari allowing third-party auth cookies. Signing out clears the Civic browser session; it does not sign the person out of other applications using Neon Auth. Shared-password sessions stop working once Neon Auth is enabled unless the owner explicitly enables `PCN_ALLOW_PASSWORD_LOGIN=true` for recovery. Keep that option off and rotate any previously shared workspace password.

References: [Neon Email OTP](https://neon.com/docs/auth/guides/plugins/email-otp), [email configuration](https://neon.com/docs/auth/guides/customize-emails), [Resend sender domains](https://resend.com/docs/dashboard/domains/introduction).

## Local development

Use Python 3.14 and Node 22.12 or newer:

```sh
bash scripts/dev.sh
```

Open <http://127.0.0.1:5173>. Ctrl-C stops the backend and frontend. Optional settings live in root `.env`; use `.env.example` as the template. Existing environment variables win; legacy `backend/.env` is read before root `.env`.

With `DATABASE_URL` configured, local development uses Neon too. **The same URL and schema locally and on Render share the same cases.** For an offline SQLite workspace, run:

```sh
DATABASE_URL='' bash scripts/dev.sh
```

## Local Docker

Create `.env` from `.env.example` only if you do not already have one, and set your workspace password:

```sh
docker compose up -d --build
docker compose ps
```

Open <http://localhost:8000>. Enter a reviewer name and the workspace password. Compose exposes only the host loopback interface. The Docker image builds React and starts one Uvicorn worker as a non-root user; `/api/ready` is its health check. Keep `PCN_COOKIE_SECURE=false` for local HTTP and `true` for hosted HTTPS.

When `DATABASE_URL` is blank, SQLite and attachments remain in the named `civic-data` volume. Rebuilds and `docker compose down` preserve it. `docker compose down -v` deletes it. When Neon is selected, the volume is retained for access to old local data but new records and database-mode uploads go to Neon.

## Preserve an existing SQLite workspace

Changing `DATABASE_URL` does not copy SQLite data automatically. Use the included migration command before adding new records to the destination. Stop writes to the source during export/import; retain the original database and evidence folder as a backup.

For an existing Docker workspace, stop the service briefly and export its `/data` folder to a private backup location:

```sh
docker compose stop civic
mkdir -p /private/tmp/civic-backup
docker compose cp civic:/data/. /private/tmp/civic-backup/
docker compose start civic
```

Keep another copy somewhere durable. For the older development workspace, the source is `backend/pcn_copilot.db` and the evidence folder is `backend/evidence_store`.

Set the destination `DATABASE_URL` in your ignored `.env`, then preview the migration:

```sh
.venv/bin/python backend/migrate_sqlite.py \
  --source-db /private/tmp/civic-backup/civic.db \
  --evidence-dir /private/tmp/civic-backup/evidence
```

Append `--apply` to import. The command opens the source read-only, validates attachment hashes and copies rows/files in one destination transaction. It preserves IDs, resets ID sequences and rejects any nonempty destination. It does not merge, overwrite or delete existing data. Do not import both Docker and development databases into the same schema.

Any records in an older Render deployment's local SQLite file must be exported before replacing that deployment; a local migration cannot recover a discarded Render filesystem.

## Mubit

Set `AI_PROVIDER=mubit` and your private `MUBIT_API_KEY` in the environment where the app runs. Choose the route, model and base URL shown by your Mubit account. The example uses the Anthropic route; leave model/base URL blank to use adapter defaults. Credentials stay server-side.

`MUBIT_RECORD=full` requests provider recording; `metadata` or `off` reduces it where supported. Use synthetic data. Run one review and inspect its provider metadata to verify live inference. The automated tests use the offline provider and mocked gateway responses; they do not exercise paid inference or model training.

## Backups and scaling

Use the Neon project's restore/backup facilities according to your chosen plan and verify restoration separately. A database backup includes attachments stored as blobs. Files are limited to 10 MiB each; they consume database storage and backup capacity. Replaced blobs are retained. Move files to S3/R2 or another object store when volume warrants it.

PostgreSQL case locks and database review leases coordinate concurrent requests. The default is still one web service and one worker. Long model reviews use synchronous HTTP requests, so allow for model latency when configuring a proxy and add a durable job queue before scaling heavy review workloads. SQLite remains a single-instance local option.

## Focused verification

```sh
.venv/bin/python -m pytest backend/tests -q
npm run build --prefix frontend
docker build -t civic-check .
```

The suite includes focused approval, verified-identity, revocation, mail-failure and migration checks alongside the existing case workflow checks. A separate PostgreSQL run covers concurrent approval and the managed-auth schema contract. CI provisions a disposable PostgreSQL service; tests use randomly named schemas and never use `DATABASE_URL` from `.env`. Set `PCN_TEST_DATABASE_URL` only to an expendable test database when running that suite yourself.

Deployment configuration follows the [Render Blueprint specification](https://render.com/docs/blueprint-spec), [health-check guidance](https://render.com/docs/health-checks) and [Neon's Python connection guidance](https://neon.com/docs/guides/python). See [ARCHITECTURE.md](ARCHITECTURE.md) for the implemented product and its current limits.
