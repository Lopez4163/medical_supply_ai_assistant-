# Medical Supply AI Assistant

A portfolio-first, full-stack AI engineering demonstration by **Queens Tech Bros (QTB)**. The project models a guest-facing assistant for a family-owned medical-supply and pharmaceutical-distribution business, helping visitors discover products, check indicative availability, draft quotation requests, and request human support.

## Demonstration boundaries

This is a pro bono, real-business-inspired demonstration. Catalog items, inventory, prices, customers, operational information, and public submissions are synthetic. Use of any real business branding is contingent on permission. The project is not represented as a production system, does not take payments or create commercial orders, and does not connect public demo submissions to real business operations.

## Planned MVP capabilities

- AI-guided catalog discovery with in-chat product result cards
- Hybrid keyword, attribute, and semantic product retrieval
- Guest sessions, resumable conversation state, and persistent draft quotation requests
- Availability-aware alternatives and a confirmed quotation-submission flow
- Approved-information RAG for company and policy questions
- Optional human-support inquiry workflow
- PostgreSQL-first persistence with one-way Google Sheets demonstration synchronization
- Medical-information safety controls, abuse safeguards, automated tests, and AI evaluations

## Architectural baseline

The proposed stack is Next.js, React, TypeScript, and Tailwind CSS on the frontend; Python, FastAPI, and Pydantic on the backend; LangGraph and LangChain for AI orchestration; PostgreSQL with pgvector; Google Sheets API; Docker; GitHub Actions; and automated testing/evaluation. OpenRouter is the initial conversational LLM gateway, while the selected compatible model remains configurable; Google Gemini Embedding API is used for RAG embeddings. AWS validation is planned as a separate, time-bounded milestone and is not assumed to host the permanent public demo.

## Documentation status

The [Product Requirements Document baseline](docs/01-product-requirements.md) is approved at version 1.2 for product requirements and MVP scope, including the approved five-request conversational-memory and natural-language-only topic-resumption amendments. The [Conversation Flow Specification](docs/02-conversation-flows.md) is approved at version 1.1 for the customer conversation-flow baseline. The [Product Catalog & Inventory baseline](docs/03-product-catalog-inventory.md) is approved at version 1.0 for the synthetic catalog specification. The [Business Operations & Knowledge Base Specification](docs/04-business-operations.md) is approved at version 1.0 for fictional demo business rules and knowledge-base specifications. The [System & AI Architecture](docs/05-system-ai-architecture.md) is version 1.0, Approved. The [Frontend Implementation Design](docs/06-frontend-implementation-design.md) is version 1.0, Approved. The [Backend & API Design](docs/07-backend-api-design.md) is version 1.0, Approved. The [Development Roadmap](docs/08-development-roadmap.md) is version 1.0, Approved. These statuses do not resolve business permissions, privacy/safety review, image rights, live-business claims, regulatory compliance, deployment readiness, implementation, or public-release decisions; documented open decisions remain outstanding.

## Planned phases

1. Requirements, architecture, data model, and safety design
2. Synthetic catalog and backend foundations
3. Conversational product discovery, RAG, and quotation workflows
4. Integration, testing, AI evaluation, and public-demo hardening
5. Affordable public-demo deployment, followed by a separately documented AWS validation and teardown milestone

## Quality checks

FOUND-03 establishes deterministic local and CI quality checks. Use Node 26 (see `frontend/.nvmrc`), Python 3.14, uv 0.12+, and Docker Compose v2 for backend tests.

Frontend commands, from `frontend/`:

```sh
npm ci
npm run format:check
npm run lint
npm run typecheck
npm test
```

Backend commands require a local copy of `backend/.env.example` as `backend/.env` and the local PostgreSQL container:

```sh
docker compose up -d
cd backend
uv sync --all-groups
set -a; . ./.env; set +a
uv run alembic upgrade head
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run python -m pytest -q
```

The GitHub Actions `Quality` workflow runs these same formatter, lint, type, migration, and test checks with a disposable pgvector service. It uses no external AI, embedding, Sheets, or production credentials. Format failures are corrected locally with `npm run format` or `uv run ruff format .`; lint, type, and test failures report the affected file and rule or assertion.
