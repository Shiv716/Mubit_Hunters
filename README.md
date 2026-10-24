# civic. — Review Copilot

A working full-stack demo for the **parking appeals officer**: the person who reads a driver's challenge, weighs the evidence and decides the outcome.

**Open case → review evidence → get a suggested outcome → choose and edit the reply → save and move on.**

The `trial-2` branch builds on `trial/pcn-trial1`. The interface uses warm paper, charcoal, electric blue and lime, with restrained retro details. Northgate Borough, its policies and all sample cases are fictional.

## Run locally

Requires Python 3.14 and Node 22.12+.

```sh
bash scripts/dev.sh
```

Open <http://127.0.0.1:5173>, then choose **Explore sample appeals**. No key is required: the default is a clearly labelled, deterministic AI simulation. You can also add a synthetic appeal through the form. Put optional settings in root `.env` using `.env.example`; `backend/.env` remains supported and takes precedence when both exist.

## What is built

- Searchable queue with explicit response dates; evidence and council records beside the copilot.
- A bounded agent that selects read-only checks, plus mandatory deterministic rules.
- Mubit gateway adapter or offline simulation; validated recommendations and visible investigation steps.
- Explicit officer choices, editable response drafts, save-and-next, response downloads and a persistent case history.
- Evidence attachments, JSON import, feedback approval, example retrieval and evaluation tools under Admin.
- Insights calculated from saved decisions; no invented accuracy or savings claims.
- Optional shared-password demo access, SQLite persistence and a single-container deployment.

```mermaid
flowchart LR
  Officer[Officer in React UI] --> API[FastAPI]
  API --> DB[(SQLite + evidence files)]
  API --> Agent[Bounded investigation]
  Agent --> Checks[Rules + supplied records + policy]
  Agent --> Model[Mubit gateway or offline stub]
  Agent --> Past[Approved past examples]
  API --> Guard[Validate references and safety]
  Guard --> Officer
  Officer --> Decision[Decision + editable reply]
  Decision --> DB
  DB --> QA[Human feedback approval]
  QA --> Past
```

## Deploy

```sh
cp .env.example .env
# Set a private PCN_ACCESS_KEY of at least 16 characters in .env.
docker compose up -d --build
```

Open <http://localhost:8000>. React is served by FastAPI; one persistent volume holds the database and evidence. For a hosted private demo, use one VM, HTTPS and a reverse proxy. See [deployment instructions](docs/DEPLOYMENT.md) and [implemented architecture](docs/ARCHITECTURE.md).

## Focused verification

```sh
.venv/bin/python -m pytest backend/tests -q
npm run build --prefix frontend
```

The 40 existing tests are retained. Four additional workflow tests cover review-to-decision persistence, reasons and stale reviews, agent boundaries, and the private demo session. A browser smoke check covers the main user flow. There is no extra test framework.

## Scope

This is a **synthetic-data MVP**, not a live council system. The agent reads supplied records and evidence descriptions; it does not fetch council records, interpret uploaded image/PDF contents, send letters or cancel PCNs. Response dates are imported or entered, not calculated as legal advice. The shared password is not SSO or role-based access. Audit rows are append-only in the application, not independently tamper-proof.

Approved examples already inform later reviews. Mubit model training, deployment and measured model improvement remain unverified until exercised with account credentials. The older [design notes](docs/03-architecture.md) describe future scope; `docs/ARCHITECTURE.md` is the implementation reference.

The [revised business case](docs/01-business-case.md) separates evidence, pricing assumptions and competitive risks. The opportunity is to reduce routine review time while preserving officer judgement; a pilot must establish whether it does.
