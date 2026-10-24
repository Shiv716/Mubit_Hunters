# Running and deploying Civic

## Development

Use Python 3.14 and Node 22.12 or newer. From the repository root:

```sh
bash scripts/dev.sh
```

This installs the Python and frontend dependencies and starts FastAPI on loopback port 8000 and Vite on loopback port 5173. Open <http://127.0.0.1:5173> manually. Ctrl-C stops both processes. Choose **Explore sample appeals** to load 17 fictional appeals. Seeding is idempotent and is never done automatically on startup.

Optional root `.env` settings are listed in `.env.example`. Existing environment variables win; the legacy `backend/.env` is read before root `.env`. Avoid setting contradictory values in both files.

## One-container private demo

```sh
cp .env.example .env
# Edit .env: set PCN_ACCESS_KEY to a private password of at least 16 characters.
docker compose up -d --build
docker compose ps
```

Open <http://localhost:8000>. Enter a reviewer name and the workspace password. Compose exposes only the host loopback interface. It does not publish the app to the internet. The Docker build compiles React, installs Python runtime dependencies, and starts one Uvicorn worker as a non-root user. `/api/health` is the health check.

The named `civic-data` volume contains `/data/civic.db` and `/data/evidence`. Rebuilding or `docker compose down` retains it. Do not use `down -v` unless intentionally deleting the demo data. SQLite WAL mode requires persistent local disk; do not use an ephemeral serverless filesystem or multiple replicas.

## Hosting on a VM

Deploy the same repository and Compose file to a private VM with Docker. Put an HTTPS reverse proxy on that host in front of `127.0.0.1:8000`. Set:

```dotenv
PCN_PUBLIC_ORIGIN=https://your-demo-host.example
PCN_COOKIE_SECURE=true
```

Configure the proxy with a valid TLS certificate, a private network or allowlist, and request-rate limits including the login endpoint. Allow at least 300 seconds for a review request: a bounded planner plus review can take several model calls. Keep the API port on loopback. Set an upload limit compatible with the application's 10 MiB per-file limit. The shared-password gate is suitable for a private synthetic demo; it does not authenticate council staff identities.

## Enable Mubit

Set `AI_PROVIDER=mubit` and your private `MUBIT_API_KEY`. Choose the route, model and base URL shown by your Mubit account. The example defaults to the Anthropic route; leave model/base URL blank to use the adapter defaults, or override them for your account. Credentials are server-side and are never bundled into React.

`MUBIT_RECORD=full` requests provider recording; `metadata` or `off` reduces it where supported. Use only synthetic data. Start with one case and inspect Admin and its saved request metadata. Configuration alone is not a successful connection test. Local verification used the offline provider and mocked gateway responses, not paid inference or model training.

## Backup and updates

For this single-instance demo, stop the container before taking a host/volume snapshot so SQLite and attachments are consistent. Retain a copy outside the VM and verify restoration separately. For updates, preserve the volume and `.env`, pull the desired branch/commit and rebuild. There is no automatic model deployment, cloud provisioning or database migration service.

## Verification and current limits

- Backend: 44 tests (40 retained, four focused additions).
- Frontend: production build and browser smoke check of review, draft, save-and-next and insights.
- Container configuration: validated with `docker compose config`; a container build/run still needs a running Docker daemon.
- No public host has been provisioned. This branch supplies the runnable application and deployment configuration.

The built application and its safety boundaries are described in [ARCHITECTURE.md](ARCHITECTURE.md).
