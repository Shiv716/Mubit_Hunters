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

SQLite: 46 passed, two PostgreSQL-only skips. A separate PostgreSQL run covers 17 relevant API, workspace and persistence checks, including competing decisions and migration. CI provisions a disposable PostgreSQL service; tests use randomly named schemas and never use `DATABASE_URL` from `.env`. Set `PCN_TEST_DATABASE_URL` only to an expendable test database when running that suite yourself.

Deployment configuration follows the [Render Blueprint specification](https://render.com/docs/blueprint-spec), [health-check guidance](https://render.com/docs/health-checks) and [Neon's Python connection guidance](https://neon.com/docs/guides/python). See [ARCHITECTURE.md](ARCHITECTURE.md) for the implemented product and its current limits.
