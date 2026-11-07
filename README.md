# BioMedicHospicare AI Supply Assistant

A Queens Tech Bros (QTB) full-stack portfolio project exploring a medical-supply business assistant. It is a synthetic-data demonstration under development—not a live commercial, fulfillment, payment, clinical-care, or customer-operations system. It does not use real customer data or connect public demo activity to real business operations.

## Phase 1 status

Phase 1 establishes the development foundation:

- A Next.js 16 / React 19 frontend that renders a small synthetic-demo landing page.
- A FastAPI service with database-independent `GET /api/v1/live` and PostgreSQL/pgvector-aware `GET /api/v1/ready` endpoints.
- Local PostgreSQL 16 with pgvector, separate development and test databases, async SQLAlchemy, Pydantic Settings, and an Alembic baseline migration that enables `vector`.
- Frontend and backend formatting, linting, type checks, tests, and the GitHub Actions `Quality` workflow.

The chatbot, product catalog, quotations, guest sessions, LangGraph, RAG, embeddings, and Google Sheets integration are planned work and are **not** functional yet. There is no catalog seed command in Phase 1 because catalog data belongs to a later roadmap phase.

## Tech stack

Implemented infrastructure uses Next.js, React, TypeScript, Tailwind CSS, Python, FastAPI, Pydantic Settings, SQLAlchemy async with psycopg, Alembic, PostgreSQL 16 with pgvector, Docker Compose, and GitHub Actions. Quality tooling is Prettier, ESLint, Vitest, Ruff, Pyright, and pytest.

The approved future architecture includes LangGraph/LangChain, OpenRouter, Google Gemini embeddings, and Google Sheets. Those integrations are not configured or required for local Phase 1 development.

## Prerequisites

- Git
- Node.js **26** and npm (the required Node major is in [`frontend/.nvmrc`](frontend/.nvmrc))
- Python **3.14**
- [uv](https://docs.astral.sh/uv/) 0.12 or newer
- Docker Engine/Desktop and Docker Compose v2+

Check the installed toolchain before starting:

```sh
node --version
npm --version
python3 --version
uv --version
docker compose version
```

If you use nvm, run `nvm use` inside `frontend/` to select Node 26. The backend project rejects Python versions outside 3.14.

## Quick start

Open separate terminals for the backend and frontend servers. The commands below use a POSIX-compatible shell (macOS/Linux).

### 1. Clone and configure the frontend runtime

From a directory where you keep projects:

```sh
git clone https://github.com/Lopez4163/medical_supply_ai_assistant-.git
cd medical_supply_ai_assistant-
cd frontend
nvm use
npm ci
cd ..
```

If you do not use nvm, install/select Node 26 before running `npm ci`.

### 2. Create local backend configuration

From the repository root:

```sh
cp backend/.env.example backend/.env
```

`backend/.env` contains local-only database credentials and is ignored by Git. The supplied values are safe development placeholders; change them together if you need different local credentials.

### 3. Start PostgreSQL with pgvector

From the repository root:

```sh
docker compose up -d
docker compose ps
```

The database listens on `127.0.0.1:55432` by default. Docker creates `medical_supply` for development and a separate `medical_supply_test` database for tests. The named Docker volume preserves development data between container restarts.

### 4. Install backend dependencies and apply migrations

From the repository root:

```sh
cd backend
uv sync --all-groups
set -a; . ./.env; set +a
uv run alembic upgrade head
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
```

The first migration enables the `vector` extension. Migrations—not application startup—own database initialization. The second command initializes the isolated test database; it is required before backend tests.

### 5. Start the backend

Keep the environment variables loaded in the same terminal and run, from `backend/`:

```sh
uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
```

### 6. Start the frontend

In another terminal, from `frontend/`:

```sh
nvm use
npm run dev -- --hostname 127.0.0.1 --port 3000
```

### 7. Smoke-check the running services

From any terminal:

```sh
curl -i http://127.0.0.1:8100/api/v1/live
curl -i http://127.0.0.1:8100/api/v1/ready
curl -I http://127.0.0.1:3000/
```

`/live` returns `200` with `{"status":"ok"}` whenever FastAPI is running; it deliberately does not require PostgreSQL. `/ready` returns `200` only when PostgreSQL is reachable and pgvector is enabled; otherwise it safely returns `503` with `{"status":"unavailable"}`. The frontend root should return `200` and display the synthetic-data demonstration page.

## Database operations

The Compose service uses `pgvector/pgvector:0.8.0-pg16`, bound only to loopback. The local settings file provides `DATABASE_URL` for `medical_supply` and `TEST_DATABASE_URL` for `medical_supply_test`.

After sourcing `backend/.env`, use these commands from `backend/` to migrate either database:

```sh
uv run alembic upgrade head
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
```

To confirm connectivity and the extension from the repository root:

```sh
docker compose exec -T postgres psql -U medical_supply_app -d medical_supply -c "SELECT 1;"
docker compose exec -T postgres psql -U medical_supply_app -d medical_supply_test -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

Stop the service without deleting the persistent development volume:

```sh
docker compose stop postgres
```

`docker compose down` also keeps the named volume by default. Do not use `docker compose down -v` unless you intentionally want to remove local database data.

## Quality checks

Run frontend checks from `frontend/`:

```sh
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

Run backend checks from `backend/` after `uv sync --all-groups`, sourcing `.env`, starting Docker, and migrating the test database:

```sh
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run python -m pytest -q
```

To apply local formatting, use `npm run format` or `uv run ruff format .`. The GitHub Actions **Quality** workflow runs the frontend checks plus backend formatting, linting, typing, migration, and pytest against a disposable pgvector service. It uses no external AI service or production credentials.

## Git workflow

Use the approved branch flow:

```text
feature/* → dev → main
```

Create a focused `feature/*` branch from current `dev`, open a pull request into `dev`, and use the Quality workflow results in review. Changes reach `main` only through the approved `dev` integration path. Do not commit local `.env` files, virtual environments, dependency folders, build output, or database data.

## Project documentation

- [01 — Product Requirements](docs/01-product-requirements.md)
- [02 — Conversation Flows](docs/02-conversation-flows.md)
- [03 — Product Catalog & Inventory](docs/03-product-catalog-inventory.md)
- [04 — Business Operations & Knowledge Base](docs/04-business-operations.md)
- [05 — System & AI Architecture](docs/05-system-ai-architecture.md)
- [06 — Frontend Implementation Design](docs/06-frontend-implementation-design.md)
- [07 — Backend & API Design](docs/07-backend-api-design.md)
- [08 — Development Roadmap](docs/08-development-roadmap.md)

## Troubleshooting

- **Node or Python version error:** Use Node 26 (`nvm use` in `frontend/`) and Python 3.14. Check both versions before reinstalling dependencies.
- **`docker compose up` cannot bind port 55432:** Another local service may already use it. Start Compose with a different loopback port, for example `POSTGRES_PORT=55433 docker compose up -d`, then update both URLs in `backend/.env` to the same port.
- **`/ready` returns 503:** Confirm `docker compose ps` reports the PostgreSQL container healthy, source `backend/.env` before starting Uvicorn, and run the migrations for the development database. `/live` remaining `200` during this condition is expected.
- **Backend settings validation fails:** Create `backend/.env` from `backend/.env.example`, or provide a valid `DATABASE_URL` in the environment. It must use the `postgresql+psycopg` driver.
